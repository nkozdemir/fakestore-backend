from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .services import UserService
from .serializers import UserSerializer
from apps.api.utils import error_response

class UserListView(APIView):
    service = UserService()
    def get(self, request):
        data = self.service.list_users()
        serializer = UserSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=False)
        return Response(serializer.data)
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.create_user(serializer.validated_data)
        return Response(UserSerializer(dto).data, status=status.HTTP_201_CREATED)

class UserDetailView(APIView):
    service = UserService()
    def get(self, request, user_id: int):
        dto = self.service.get_user(user_id)
        if not dto:
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        serializer = UserSerializer(dto)
        return Response(serializer.data)
    def put(self, request, user_id: int):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_user(user_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        return Response(UserSerializer(dto).data)
    def patch(self, request, user_id: int):
        serializer = UserSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        dto = self.service.update_user(user_id, serializer.validated_data)
        if not dto:
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        return Response(UserSerializer(dto).data)
    def delete(self, request, user_id: int):
        deleted = self.service.delete_user(user_id)
        if not deleted:
            return error_response('NOT_FOUND', 'User not found', {'id': str(user_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)
