from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth.hashers import make_password
from apps.api.utils import error_response

User = get_user_model()

class RegisterView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        data = request.data.copy()
        required = ['username', 'email', 'password', 'firstname', 'lastname']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return error_response('VALIDATION_ERROR', 'Missing fields', {'missing': missing})
        if User.objects.filter(username=data['username']).exists():
            return error_response('VALIDATION_ERROR', 'Username already exists', {'username': data['username']})
        if User.objects.filter(email=data['email']).exists():
            return error_response('VALIDATION_ERROR', 'Email already exists', {'email': data['email']})
        data['password'] = make_password(data['password'])
        user = User.objects.create(**{k: data[k] for k in required if k != 'password'}, password=data['password'])
        return Response({'id': user.id, 'username': user.username, 'email': user.email}, status=status.HTTP_201_CREATED)

class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]

class RefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

class MeView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'firstname': getattr(user, 'firstname', ''),
            'lastname': getattr(user, 'lastname', ''),
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        })

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'detail': 'Logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            return error_response('VALIDATION_ERROR', 'Invalid token', {'error': str(e)})

class LogoutAllView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        user = request.user
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            try:
                BlacklistedToken.objects.get_or_create(token=token)
            except Exception:
                pass
        return Response({'detail': 'Logged out from all devices'}, status=status.HTTP_200_OK)
