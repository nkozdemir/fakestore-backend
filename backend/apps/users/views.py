from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import UserService, ServiceValidationError
from .serializers import UserSerializer, AddressWriteSerializer, AddressSerializer
from apps.api.utils import error_response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError as DRFValidationError
from .models import User
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from apps.api.schemas import ErrorResponseSerializer

@extend_schema(tags=["Users"])
class UserListView(APIView):
    permission_classes = [AllowAny]
    service = UserService()
    @extend_schema(
        summary="List users",
        responses={200: UserSerializer(many=True)},
    )
    def get(self, request):
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
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        try:
            dto = self.service.create_user(serializer.validated_data)
            return Response(UserSerializer(dto).data, status=status.HTTP_201_CREATED)
        except ServiceValidationError as e:
            return error_response('VALIDATION_ERROR', str(e), e.details)
        except IntegrityError as e:
            # Fallback: convert DB constraint errors to a neat validation response
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})

@extend_schema(tags=["Users"])
class UserDetailView(APIView):
    permission_classes = [AllowAny]
    service = UserService()
    @extend_schema(
        summary="Get user by ID",
        parameters=[OpenApiParameter("user_id", int, OpenApiParameter.PATH)],
        responses={200: UserSerializer, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, user_id: int):
        dto = self.service.get_user(user_id)
        if not dto:
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
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        try:
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
            return Response(UserSerializer(dto).data)
        except ServiceValidationError as e:
            return error_response('VALIDATION_ERROR', str(e), e.details)
        except IntegrityError as e:
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})
    @extend_schema(
        summary="Update user",
        request=UserSerializer,
        responses={200: UserSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, user_id: int):
        instance = User.objects.filter(id=user_id).first()
        serializer = UserSerializer(instance=instance, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        try:
            dto = self.service.update_user(user_id, serializer.validated_data)
            if not dto:
                return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
            return Response(UserSerializer(dto).data)
        except ServiceValidationError as e:
            return error_response('VALIDATION_ERROR', str(e), e.details)
        except IntegrityError as e:
            return error_response('VALIDATION_ERROR', 'Unique constraint violated', {'detail': str(e)})
    @extend_schema(
        summary="Delete user",
        responses={204: None, 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, user_id: int):
        deleted = self.service.delete_user(user_id)
        if not deleted:
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressListView(APIView):
    # Auth required; user inferred from JWT
    permission_classes = [IsAuthenticated]
    service = UserService()
    @extend_schema(
        summary="List addresses for current user",
        description="Lists addresses for the authenticated user (derived from JWT).",
        responses={200: AddressSerializer(many=True), 401: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        addresses = self.service.list_user_addresses(user_id)
        return Response(AddressSerializer(addresses, many=True).data)
    @extend_schema(
        summary="Create address for current user",
        description="Creates an address owned by the authenticated user.",
        request=AddressWriteSerializer,
        responses={201: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def post(self, request):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        dto = self.service.create_user_address(user_id, serializer.validated_data)
        return Response(AddressSerializer(dto).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Users", "Addresses"])
class UserAddressDetailView(APIView):
    permission_classes = [IsAuthenticated]
    service = UserService()
    @extend_schema(
        summary="Get address for current user",
        parameters=[OpenApiParameter("address_id", int, OpenApiParameter.PATH)],
        description="Retrieves an address owned by the authenticated user.",
        responses={200: AddressSerializer, 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def get(self, request, address_id: int):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        dto = self.service.get_user_address(user_id, address_id)
        if not dto:
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Replace address for current user",
        request=AddressWriteSerializer,
        responses={200: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def put(self, request, address_id: int):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        dto = self.service.update_user_address(user_id, address_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Update address for current user",
        request=AddressWriteSerializer,
        responses={200: AddressSerializer, 400: OpenApiResponse(response=ErrorResponseSerializer), 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def patch(self, request, address_id: int):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        serializer = AddressWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response('VALIDATION_ERROR', 'Invalid input', serializer.errors)
        dto = self.service.update_user_address(user_id, address_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(AddressSerializer(dto).data)
    @extend_schema(
        summary="Delete address for current user",
        responses={204: None, 401: OpenApiResponse(response=ErrorResponseSerializer), 404: OpenApiResponse(response=ErrorResponseSerializer)},
    )
    def delete(self, request, address_id: int):
        user_id = getattr(request.user, 'id', None)
        if not user_id:
            return error_response('UNAUTHORIZED', 'Authentication required')
        ok = self.service.delete_user_address(user_id, address_id)
        if not ok:
            return error_response('NOT_FOUND', 'Address not found', {'address_id': str(address_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
