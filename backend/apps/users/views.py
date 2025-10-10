from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .container import build_user_service
from .serializers import UserSerializer, AddressWriteSerializer, AddressSerializer
from apps.api.utils import error_response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError
from .models import User
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer
from apps.common import get_logger

logger = get_logger(__name__).bind(component='users', layer='view')

@extend_schema(tags=["Users"])
class UserListView(APIView):
    permission_classes = [AllowAny]
    service = build_user_service()
    log = logger.bind(view='UserListView')

    @extend_schema(
        summary="List users",
        responses={200: UserSerializer(many=True)},
    )
    def get(self, request):
        self.log.debug('Listing users via API')
        data = self.service.list_users()
        # Use instance for serialization rather than feeding as input data.
        serializer = UserSerializer(data, many=True)
        return Response(serializer.data)
    @extend_schema(
        summary="Create user",
        request=UserSerializer,
        responses={201: UserSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('User create validation failed', errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        try:
            self.log.info('Creating user via API', username=serializer.validated_data.get('username'))
            dto = self.service.create_user(serializer.validated_data)
            created_user_id = getattr(dto, 'id', None)
            if created_user_id is None and isinstance(dto, dict):
                created_user_id = dto.get('id')
            self.log.info('User created via API', user_id=created_user_id)
            return Response(UserSerializer(dto).data, status=status.HTTP_201_CREATED)
        except IntegrityError as e:
            # Fallback: convert DB constraint errors to a neat validation response
            self.log.warning('User create failed due to integrity error', error=str(e))
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})

@extend_schema(tags=["Users"])
class UserDetailView(APIView):
    permission_classes = [AllowAny]
    service = build_user_service()
    log = logger.bind(view='UserDetailView')

    @extend_schema(
        summary="Get user by ID",
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={200: UserSerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, user_id: int):
        self.log.debug('Fetching user detail', user_id=user_id)
        dto = self.service.get_user(user_id)
        if not dto:
            self.log.info('User not found', user_id=user_id)
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        serializer = UserSerializer(dto)
        return Response(serializer.data)
    @extend_schema(
        summary="Replace user",
        request=UserSerializer,
        responses={200: UserSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def put(self, request, user_id: int):
        instance = User.objects.filter(id=user_id).first()
        serializer = UserSerializer(instance=instance, data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('User replace validation failed', user_id=user_id, errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        try:
            self.log.info('Replacing user', user_id=user_id)
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                self.log.warning('User replace failed: not found', user_id=user_id)
                return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
            return Response(UserSerializer(dto).data)
        except IntegrityError as e:
            self.log.warning('User replace failed due to integrity error', user_id=user_id, error=str(e))
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})
    @extend_schema(
        summary="Update user",
        request=UserSerializer,
        responses={200: UserSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, user_id: int):
        instance = User.objects.filter(id=user_id).first()
        serializer = UserSerializer(instance=instance, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('User patch validation failed', user_id=user_id, errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        try:
            self.log.info('Patching user', user_id=user_id)
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                self.log.warning('User patch failed: not found', user_id=user_id)
                return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
            return Response(UserSerializer(dto).data)
        except IntegrityError as e:
            self.log.warning('User patch failed due to integrity error', user_id=user_id, error=str(e))
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})
    @extend_schema(
        summary="Delete user",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, user_id: int):
        self.log.info('Deleting user via API', user_id=user_id)
        deleted = self.service.delete_user(user_id)
        if not deleted:
            self.log.warning('User delete failed: not found', user_id=user_id)
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressListView(APIView):
    # Auth required; user inferred from JWT
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view='UserAddressListView')

    @extend_schema(
        summary="List addresses for current user",
        description="Lists addresses for the authenticated user (derived from JWT).",
        responses={200: AddressSerializer(many=True), 401: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address list attempt')
            return error_response('UNAUTHORIZED', 'Authentication required')
        self.log.debug('Listing addresses for user', user_id=user_id)
        addresses = self.service.list_user_addresses(user_id)
        return Response(AddressSerializer(addresses, many=True).data)
    @extend_schema(
        summary="Create address for current user",
        description="Creates an address owned by the authenticated user.",
        request=AddressWriteSerializer,
        responses={201: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def post(self, request):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address create attempt')
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('Address create validation failed', errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        self.log.info('Creating address for user', user_id=user_id)
        dto = self.service.create_user_address(user_id, serializer.validated_data)
        address_id = None
        if dto is not None:
            address_id = getattr(dto, 'id', None)
            if address_id is None and isinstance(dto, dict):
                address_id = dto.get('id')
        self.log.info('Address created via API', user_id=user_id, address_id=address_id)
        return Response(AddressSerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]
    service = build_user_service()
    log = logger.bind(view='UserAddressDetailView')

    @extend_schema(
        summary="Get address for current user",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        description="Retrieves an address owned by the authenticated user.",
        responses={200: AddressSerializer, 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, address_id: int):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address read attempt', address_id=address_id)
            return error_response('UNAUTHORIZED', 'Authentication required')
        self.log.debug('Fetching address', user_id=user_id, address_id=address_id)
        dto = self.service.get_user_address(user_id, address_id)
        if not dto:
            self.log.info('Address not found', user_id=user_id, address_id=address_id)
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Replace address for current user",
        request=AddressWriteSerializer,
        responses={200: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def put(self, request, address_id: int):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address replace attempt', address_id=address_id)
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('Address replace validation failed', address_id=address_id, errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        self.log.info('Replacing address', user_id=user_id, address_id=address_id)
        dto = self.service.update_user_address(user_id, address_id, serializer.validated_data)
        if not dto:
            self.log.warning('Address replace failed: not found', user_id=user_id, address_id=address_id)
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Update address for current user",
        request=AddressWriteSerializer,
        responses={200: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, address_id: int):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address patch attempt', address_id=address_id)
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except DRFValidationError as exc:
            self.log.warning('Address patch validation failed', address_id=address_id, errors=exc.detail)
            return error_response('VALIDATION_ERROR', 'Invalid input', exc.detail)
        self.log.info('Patching address', user_id=user_id, address_id=address_id)
        dto = self.service.update_user_address(user_id, address_id, serializer.validated_data)
        if not dto:
            self.log.warning('Address patch failed: not found', user_id=user_id, address_id=address_id)
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Delete address for current user",
        responses={204: None, 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, address_id: int):
        user_id = getattr(request, 'validated_user_id', None)
        if not user_id:
            self.log.warning('Unauthorized address delete attempt', address_id=address_id)
            return error_response('UNAUTHORIZED', 'Authentication required')
        self.log.info('Deleting address', user_id=user_id, address_id=address_id)
        ok = self.service.delete_user_address(user_id, address_id)
        if not ok:
            self.log.warning('Address delete failed: not found', user_id=user_id, address_id=address_id)
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
