from typing import Optional

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .container import build_user_service
from .serializers import UserSerializer, AddressWriteSerializer, AddressSerializer
from apps.api.utils import error_response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError
from .models import User
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer
from apps.common import get_logger

logger = get_logger(__name__).bind(component="users", layer="view")


def _authorize_address_access(
    log, request, target_user_id: Optional[int], action: str
):
    """
    Ensures the authenticated actor may manage the target user's addresses.
    When target_user_id is provided the actor must either own that user or be
    a superuser. Returns a tuple of (response, actor_id). When response is not
    None the caller should return it immediately.
    """
    actor_id = getattr(request, "validated_user_id", None)
    if not actor_id:
        log.warning(
            "Unauthorized address action attempt",
            action=action,
            target_user_id=target_user_id,
        )
        return error_response("UNAUTHORIZED", "Authentication required"), None
    user_obj = getattr(request, "user", None)
    is_superuser = bool(getattr(user_obj, "is_superuser", False))
    if target_user_id is not None and actor_id != target_user_id and not is_superuser:
        log.warning(
            "Address action forbidden",
            action=action,
            actor_id=actor_id,
            target_user_id=target_user_id,
        )
        return (
            error_response(
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
            ),
            actor_id,
        )
    return None, actor_id


@extend_schema(tags=["Users"])
class UserListView(APIView):
    permission_classes = [AllowAny]
    service = build_user_service()
    log = logger.bind(view="UserListView")

    @extend_schema(
        summary="List users",
        responses={200: UserSerializer(many=True)},
    )
    def get(self, request):
        user = getattr(request, "user", None)
        is_authenticated = bool(
            user and getattr(user, "is_authenticated", False) and getattr(user, "id", None)
        )
        if not is_authenticated:
            self.log.warning("Unauthorized user list access attempt")
            return error_response("UNAUTHORIZED", "Authentication required")

        is_privileged = bool(
            getattr(request, "is_privileged_user", False)
            or getattr(user, "is_staff", False)
            or getattr(user, "is_superuser", False)
        )
        if not is_privileged:
            self.log.warning(
                "Forbidden user list access",
                user_id=getattr(user, "id", None),
            )
            return error_response(
                "FORBIDDEN", "You do not have permission to list users"
            )
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
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            is_privileged = bool(
                getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
            )
            if not is_privileged:
                self.log.warning(
                    "Authenticated user attempted to create account",
                    actor_id=getattr(user, "id", None),
                )
                return error_response(
                    "FORBIDDEN", "You do not have permission to create users"
                )
        serializer = UserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning("User create validation failed", errors=exc.detail)
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        try:
            self.log.info(
                "Creating user via API",
                username=serializer.validated_data.get("username"),
            )
            dto = self.service.create_user(serializer.validated_data)
            created_user_id = getattr(dto, "id", None)
            if created_user_id is None and isinstance(dto, dict):
                created_user_id = dto.get("id")
            self.log.info("User created via API", user_id=created_user_id)
            return Response(UserSerializer(dto).data, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            # Fallback: convert DB constraint errors to a neat validation response
            self.log.warning("User create failed due to integrity error", error=str(e))
            return error_response(
                "VALIDATION_ERROR", "Unique constraint violated", {"detail": str(e)}
            )


@extend_schema(tags=["Users"])
class UserDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    service = build_user_service()
    log = logger.bind(view="UserDetailView")

    @staticmethod
    def _ensure_user_access(request, user_id: int):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            raise PermissionError("unauthenticated")
        if getattr(user, "id", None) == user_id or getattr(user, "is_staff", False):
            return
        raise PermissionError("forbidden")

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
        try:
            self._ensure_user_access(request, user_id)
        except PermissionError as exc:
            if str(exc) == "unauthenticated":
                self.log.warning("Unauthenticated user replace attempt", user_id=user_id)
                return error_response("UNAUTHORIZED", "Authentication required")
            self.log.warning(
                "User replace forbidden", user_id=user_id, actor_id=getattr(request.user, "id", None)
            )
            return error_response("FORBIDDEN", "You do not have permission to modify this user")
        instance = User.objects.filter(id=user_id).first()
        serializer = UserSerializer(instance=instance, data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning(
                "User replace validation failed", user_id=user_id, errors=exc.detail
            )
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        try:
            self.log.info("Replacing user", user_id=user_id)
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                self.log.warning("User replace failed: not found", user_id=user_id)
                return error_response(
                    "NOT_FOUND", "User not found", {"id": str(user_id)}
                )
            return Response(UserSerializer(dto).data)
        except IntegrityError as e:
            self.log.warning(
                "User replace failed due to integrity error",
                user_id=user_id,
                error=str(e),
            )
            return error_response(
                "VALIDATION_ERROR", "Unique constraint violated", {"detail": str(e)}
            )

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
        try:
            self._ensure_user_access(request, user_id)
        except PermissionError as exc:
            if str(exc) == "unauthenticated":
                self.log.warning("Unauthenticated user patch attempt", user_id=user_id)
                return error_response("UNAUTHORIZED", "Authentication required")
            self.log.warning(
                "User patch forbidden", user_id=user_id, actor_id=getattr(request.user, "id", None)
            )
            return error_response("FORBIDDEN", "You do not have permission to modify this user")
        instance = User.objects.filter(id=user_id).first()
        serializer = UserSerializer(instance=instance, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning(
                "User patch validation failed", user_id=user_id, errors=exc.detail
            )
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        try:
            self.log.info("Patching user", user_id=user_id)
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                self.log.warning("User patch failed: not found", user_id=user_id)
                return error_response(
                    "NOT_FOUND", "User not found", {"id": str(user_id)}
                )
            return Response(UserSerializer(dto).data)
        except IntegrityError as e:
            self.log.warning(
                "User patch failed due to integrity error",
                user_id=user_id,
                error=str(e),
            )
            return error_response(
                "VALIDATION_ERROR", "Unique constraint violated", {"detail": str(e)}
            )

    @extend_schema(
        summary="Delete user",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, user_id: int):
        try:
            self._ensure_user_access(request, user_id)
        except PermissionError as exc:
            if str(exc) == "unauthenticated":
                self.log.warning("Unauthenticated user delete attempt", user_id=user_id)
                return error_response("UNAUTHORIZED", "Authentication required")
            self.log.warning(
                "User delete forbidden", user_id=user_id, actor_id=getattr(request.user, "id", None)
            )
            return error_response("FORBIDDEN", "You do not have permission to modify this user")
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
        response, actor_id = _authorize_address_access(self.log, request, user_id, "list")
        if response:
            return response
        self.log.debug(
            "Listing addresses for user",
            user_id=user_id,
            actor_id=actor_id,
        )
        addresses = self.service.list_user_addresses(user_id)
        if addresses is None:
            self.log.warning(
                "Address list failed: user missing",
                user_id=user_id,
                actor_id=actor_id,
                reason="user_not_found",
            )
            return error_response(
                "NOT_FOUND",
                "User not found",
                {"userId": str(user_id)},
                hint="Log in again" if actor_id == user_id else None,
            )
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
        response, actor_id = _authorize_address_access(
            self.log, request, user_id, "create"
        )
        if response:
            return response
        serializer = AddressWriteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning("Address create validation failed", errors=exc.detail)
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        self.log.info(
            "Creating address for user",
            user_id=user_id,
            actor_id=actor_id,
        )
        dto = self.service.create_user_address(user_id, serializer.validated_data)
        if dto is None:
            self.log.warning(
                "Address creation failed: user missing",
                user_id=user_id,
                actor_id=actor_id,
                reason="user_not_found",
            )
            return error_response(
                "NOT_FOUND",
                "User not found",
                {"userId": str(user_id)},
                hint="Log in again" if actor_id == user_id else None,
            )
        address_id = None
        if dto is not None:
            address_id = getattr(dto, "id", None)
            if address_id is None and isinstance(dto, dict):
                address_id = dto.get("id")
        self.log.info(
            "Address created via API",
            user_id=user_id,
            actor_id=actor_id,
            address_id=address_id,
        )
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
        auth_response, actor_id = _authorize_address_access(
            self.log, request, None, "retrieve"
        )
        if auth_response:
            return auth_response
        self.log.debug(
            "Fetching address",
            actor_id=actor_id,
            address_id=address_id,
        )
        dto, owner_id = self.service.get_address_with_owner(address_id)
        if not dto or owner_id is None:
            self.log.info(
                "Address not found",
                actor_id=actor_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        if actor_id != owner_id and not is_superuser:
            self.log.warning(
                "Address access forbidden",
                actor_id=actor_id,
                address_id=address_id,
                owner_id=owner_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
            )
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
        auth_response, actor_id = _authorize_address_access(
            self.log, request, None, "replace"
        )
        if auth_response:
            return auth_response
        existing_dto, owner_id = self.service.get_address_with_owner(address_id)
        if not existing_dto or owner_id is None:
            self.log.warning(
                "Address replace failed: not found",
                actor_id=actor_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        if actor_id != owner_id and not is_superuser:
            self.log.warning(
                "Address replace forbidden",
                actor_id=actor_id,
                address_id=address_id,
                owner_id=owner_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
            )
        serializer = AddressWriteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning(
                "Address replace validation failed",
                address_id=address_id,
                actor_id=actor_id,
                owner_id=owner_id,
                errors=exc.detail,
            )
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        self.log.info(
            "Replacing address",
            actor_id=actor_id,
            owner_id=owner_id,
            address_id=address_id,
        )
        dto = self.service.update_user_address(
            owner_id, address_id, serializer.validated_data
        )
        if not dto:
            self.log.warning(
                "Address replace failed during update",
                actor_id=actor_id,
                owner_id=owner_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
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
        auth_response, actor_id = _authorize_address_access(
            self.log, request, None, "patch"
        )
        if auth_response:
            return auth_response
        existing_dto, owner_id = self.service.get_address_with_owner(address_id)
        if not existing_dto or owner_id is None:
            self.log.warning(
                "Address patch failed: not found",
                actor_id=actor_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        if actor_id != owner_id and not is_superuser:
            self.log.warning(
                "Address patch forbidden",
                actor_id=actor_id,
                address_id=address_id,
                owner_id=owner_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
            )
        serializer = AddressWriteSerializer(data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning(
                "Address patch validation failed",
                address_id=address_id,
                actor_id=actor_id,
                owner_id=owner_id,
                errors=exc.detail,
            )
            return error_response("VALIDATION_ERROR", "Invalid input", exc.detail)
        self.log.info(
            "Patching address",
            actor_id=actor_id,
            owner_id=owner_id,
            address_id=address_id,
        )
        dto = self.service.update_user_address(
            owner_id, address_id, serializer.validated_data
        )
        if not dto:
            self.log.warning(
                "Address patch failed during update",
                actor_id=actor_id,
                owner_id=owner_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
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
        auth_response, actor_id = _authorize_address_access(
            self.log, request, None, "delete"
        )
        if auth_response:
            return auth_response
        dto, owner_id = self.service.get_address_with_owner(address_id)
        if not dto or owner_id is None:
            self.log.warning(
                "Address delete failed: not found",
                actor_id=actor_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        is_superuser = bool(getattr(request.user, "is_superuser", False))
        if actor_id != owner_id and not is_superuser:
            self.log.warning(
                "Address delete forbidden",
                actor_id=actor_id,
                address_id=address_id,
                owner_id=owner_id,
            )
            return error_response(
                "FORBIDDEN",
                "You do not have permission to manage this user's addresses",
            )
        self.log.info(
            "Deleting address",
            actor_id=actor_id,
            owner_id=owner_id,
            address_id=address_id,
        )
        ok = self.service.delete_user_address(owner_id, address_id)
        if not ok:
            self.log.warning(
                "Address delete failed during delete",
                actor_id=actor_id,
                owner_id=owner_id,
                address_id=address_id,
            )
            return error_response(
                "NOT_FOUND", "Address not found", {"address_id": str(address_id)}
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
