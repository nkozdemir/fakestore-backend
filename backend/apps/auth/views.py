from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import (
    RefreshToken,
    OutstandingToken,
    BlacklistedToken,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.api.utils import error_response
from apps.common import get_logger
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from apps.api.schemas import ErrorResponseSerializer
from .serializers import (
    RegisterRequestSerializer,
    RegisterResponseSerializer,
    UsernameAvailabilityRequestSerializer,
    UsernameAvailabilityResponseSerializer,
    MeResponseSerializer,
    LogoutRequestSerializer,
    DetailResponseSerializer,
    CustomerTokenObtainPairSerializer,
    StaffTokenObtainPairSerializer,
)
from .container import build_registration_service

User = get_user_model()
logger = get_logger(__name__).bind(component="auth", layer="view")


@extend_schema(tags=["Auth"])
class UsernameAvailabilityView(APIView):
    permission_classes = [AllowAny]
    service = build_registration_service()
    log = logger.bind(view="UsernameAvailabilityView")

    @extend_schema(
        summary="Check username availability",
        parameters=[
            OpenApiParameter(
                name="username",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Username to check for uniqueness",
            )
        ],
        responses={
            200: UsernameAvailabilityResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request):
        serializer = UsernameAvailabilityRequestSerializer(
            data=request.query_params
        )
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        available = self.service.is_username_available(username)
        self.log.debug(
            "Username availability checked", username=username, available=available
        )
        payload = {"username": username, "available": available}
        return Response(
            UsernameAvailabilityResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Auth"])
class RegisterView(APIView):
    permission_classes = [AllowAny]
    service = build_registration_service()
    log = logger.bind(view="RegisterView")

    @extend_schema(
        summary="Register user",
        request=RegisterRequestSerializer,
        responses={
            201: RegisterResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.log.info(
            "Processing registration request",
            username=serializer.validated_data.get("username"),
        )
        result = self.service.register(serializer.validated_data)
        if isinstance(result, tuple):
            code, message, details = result
            self.log.warning(
                "Registration failed", code=code, detail=message, details=details
            )
            return error_response(code, message, details)
        self.log.info("Registration completed", user_id=result["id"])
        return Response(
            RegisterResponseSerializer(result).data, status=status.HTTP_201_CREATED
        )


@extend_schema(tags=["Auth"], summary="Login (JWT obtain pair)")
class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomerTokenObtainPairSerializer


@extend_schema(tags=["Auth"], summary="Refresh JWT")
class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]


@extend_schema(tags=["Auth"], summary="Staff/Admin Login (JWT obtain pair)")
class StaffLoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = StaffTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"], summary="Get current user", responses={200: MeResponseSerializer}
)
class MeView(APIView):
    permission_classes = [IsAuthenticated]
    log = logger.bind(view="MeView")

    def get(self, request):
        user = request.user
        self.log.debug("Returning current user profile", user_id=user.id)
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": getattr(user, "first_name", ""),
                "last_name": getattr(user, "last_name", ""),
                "last_login": user.last_login.isoformat()
                if getattr(user, "last_login", None)
                else None,
                "date_joined": user.date_joined.isoformat()
                if getattr(user, "date_joined", None)
                else None,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
            }
        )


@extend_schema(tags=["Auth"])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    log = logger.bind(view="LogoutView")

    @extend_schema(
        summary="Logout (blacklist refresh)",
        request=LogoutRequestSerializer,
        responses={
            200: DetailResponseSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            self.log.info("User logged out", user_id=getattr(request.user, "id", None))
            return Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
        except Exception as e:
            self.log.exception(
                "Logout failed", user_id=getattr(request.user, "id", None)
            )
            return error_response(
                "VALIDATION_ERROR", "Invalid token", {"error": str(e)}
            )


@extend_schema(
    tags=["Auth"],
    summary="Logout from all devices",
    responses={200: DetailResponseSerializer},
)
class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]
    log = logger.bind(view="LogoutAllView")

    @extend_schema(
        summary="Logout from all devices",
        request=None,
        responses={
            200: DetailResponseSerializer,
            401: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        user = request.user
        tokens_queryset = OutstandingToken.objects.filter(user=user)
        tokens = list(tokens_queryset)
        count = len(tokens)
        user_id = getattr(user, "id", None)
        for token in tokens:
            try:
                BlacklistedToken.objects.get_or_create(token=token)
            except Exception as exc:
                token_id = getattr(token, "id", getattr(token, "token", None))
                self.log.exception(
                    "Failed to blacklist token during logout-all",
                    user_id=user_id,
                    token_id=token_id,
                )
        self.log.info(
            "User logged out from all devices",
            user_id=user_id,
            tokens_invalidated=count,
        )
        return Response(
            {"detail": "Logged out from all devices"}, status=status.HTTP_200_OK
        )
