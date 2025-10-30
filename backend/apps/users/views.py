from typing import Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .container import build_user_service
from .serializers import UserSerializer, AddressWriteSerializer, AddressSerializer
from apps.api.utils import error_response
from rest_framework.permissions import IsAuthenticated
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer
from apps.common import get_logger

logger = get_logger(__name__).bind(component="users", layer="view")


@extend_schema(tags=["Users"])
class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view="UserListView")

    @extend_schema(
        summary="List users",
        responses={200: UserSerializer(many=True)},
    )
    def get(self, request):
        self.log.debug("Listing users via API")
        data = self.service.list_users()
        # Use instance for serialization rather than feeding as input data.
        serializer = UserSerializer(data, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Create user",
        request=UserSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning("User create validation failed", errors=exc.detail)
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        self.log.info(
            "Creating user via API",
            username=serializer.validated_data.get("username"),
        )
        dto, error = self.service.create_user(serializer.validated_data)
        if error:
            code, message, details = error
            return error_response(code, message, details)
        created_user_id = getattr(dto, "id", None)
        if created_user_id is None and isinstance(dto, dict):
            created_user_id = dto.get("id")
        self.log.info("User created via API", user_id=created_user_id)
        return Response(UserSerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Users"])
class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view="UserDetailView")

    @extend_schema(
        summary="Get user by ID",
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={
            200: UserSerializer,
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, user_id: int):
        self.log.debug("Fetching user detail", user_id=user_id)
        dto = self.service.get_user(user_id)
        if not dto:
            self.log.info("User not found", user_id=user_id)
            return error_response("NOT_FOUND", "User not found", {"id": str(user_id)})
        serializer = UserSerializer(dto)
        return Response(serializer.data)

    @extend_schema(
        summary="Replace user",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, user_id: int):
        self.log.info("Replacing user", user_id=user_id)
        dto, error = self.service.process_user_update(
            user_id, request.data, partial=False
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        return Response(UserSerializer(dto).data)

    @extend_schema(
        summary="Update user",
        request=UserSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, user_id: int):
        self.log.info("Patching user", user_id=user_id)
        dto, error = self.service.process_user_update(
            user_id, request.data, partial=True
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        return Response(UserSerializer(dto).data)

    @extend_schema(
        summary="Delete user",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, user_id: int):
        self.log.info("Deleting user via API", user_id=user_id)
        deleted = self.service.delete_user(user_id)
        if not deleted:
            self.log.warning("User delete failed: not found", user_id=user_id)
            return error_response("NOT_FOUND", "User not found", {"id": str(user_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressListView(APIView):
    # Auth required; user inferred from JWT
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view="UserAddressListView")

    @extend_schema(
        summary="List addresses for a user",
        description=(
            "Lists addresses for the specified user. Regular users may only access their "
            "own addresses; superusers may access any user's addresses."
        ),
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={
            200: AddressSerializer(many=True),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, user_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        self.log.debug(
            "Listing addresses for user",
            user_id=user_id,
            actor_id=actor_id,
            superuser=is_superuser,
        )
        addresses, error = self.service.list_user_addresses_with_auth(
            user_id,
            actor_id=actor_id,
            is_superuser=is_superuser,
        )
        if error:
            code, message, details = error
            hint = None
            if isinstance(details, dict) and "hint" in details:
                details = dict(details)
                hint = details.pop("hint")
            return error_response(code, message, details, hint=hint)
        return Response(AddressSerializer(addresses, many=True).data)

    @extend_schema(
        summary="Create address for a user",
        description=(
            "Creates an address owned by the specified user. Regular users may only create "
            "addresses for themselves; superusers may manage any user."
        ),
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        request=AddressWriteSerializer,
        responses={
            201: AddressSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def post(self, request, user_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        self.log.info(
            "Creating address for user",
            user_id=user_id,
            actor_id=actor_id,
            superuser=is_superuser,
        )
        dto, error = self.service.create_user_address_with_auth(
            user_id,
            request.data,
            actor_id=actor_id,
            is_superuser=is_superuser,
        )
        if error:
            code, message, details = error
            hint = None
            if isinstance(details, dict) and "hint" in details:
                details = dict(details)
                hint = details.pop("hint")
            return error_response(code, message, details, hint=hint)
        return Response(AddressSerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view="UserAddressDetailView")

    @extend_schema(
        summary="Get address by ID",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        description=(
            "Retrieves an address by ID. Regular users may only access their own addresses; "
            "superusers may access any user's addresses."
        ),
        responses={
            200: AddressSerializer,
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def get(self, request, address_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        self.log.debug(
            "Fetching address",
            actor_id=actor_id,
            address_id=address_id,
        )
        dto, _owner_id, error = self.service.get_address_with_auth(
            address_id,
            actor_id=actor_id,
            is_superuser=is_superuser,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        return Response(AddressSerializer(dto).data)

    @extend_schema(
        summary="Replace address by ID",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        request=AddressWriteSerializer,
        responses={
            200: AddressSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def put(self, request, address_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        dto, error = self.service.update_user_address_with_auth(
            address_id,
            request.data,
            actor_id=actor_id,
            is_superuser=is_superuser,
            partial=False,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        return Response(AddressSerializer(dto).data)

    @extend_schema(
        summary="Update address by ID",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        request=AddressWriteSerializer,
        responses={
            200: AddressSerializer,
            400: OpenApiResponse(response=ErrorResponseSerializer),
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def patch(self, request, address_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        dto, error = self.service.update_user_address_with_auth(
            address_id,
            request.data,
            actor_id=actor_id,
            is_superuser=is_superuser,
            partial=True,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        return Response(AddressSerializer(dto).data)

    @extend_schema(
        summary="Delete address by ID",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        responses={
            204: None,
            401: OpenApiResponse(response=ErrorResponseSerializer),
            403: OpenApiResponse(response=ErrorResponseSerializer),
            404: OpenApiResponse(response=ErrorResponseSerializer),
        },
    )
    def delete(self, request, address_id: int):
        actor_id = getattr(request, "validated_user_id", None)
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        deleted, error = self.service.delete_user_address_with_auth(
            address_id,
            actor_id=actor_id,
            is_superuser=is_superuser,
        )
        if error:
            code, message, details = error
            return error_response(code, message, details)
        if not deleted:
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
