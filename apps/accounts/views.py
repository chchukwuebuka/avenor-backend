from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
)

@extend_schema(
    summary='Obtain JWT Access & Refresh Token Pair',
    description='Authenticates a central Avenor user by email and password, returning tokens and profile.',
    responses={
        200: OpenApiResponse(description='Authentication successful'),
        401: OpenApiResponse(description='Invalid credentials'),
    }
)
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

@extend_schema(
    summary='Register a New User Identity',
    description='Creates a central Avenor user account.',
    responses={
        201: UserSerializer,
        400: OpenApiResponse(description='Validation error'),
    }
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'success': True,
                'message': 'Account created successfully.',
                'data': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED
        )

@extend_schema(
    summary='Get or Update Current Authenticated Profile',
    description='Retrieves the authenticated user identity or updates profile fields.',
    responses={200: UserSerializer}
)
class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'success': True,
            'data': serializer.data
        })

@extend_schema(
    summary='Change Account Password',
    description='Updates password for current authenticated user.',
    responses={200: OpenApiResponse(description='Password updated')}
)
class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return Response({
            'success': True,
            'message': 'Password has been updated successfully.'
        })


from rest_framework_simplejwt.tokens import RefreshToken, TokenError

@extend_schema(
    summary='Logout & Invalidate Refresh Token',
    description='Blacklists the provided refresh token so it cannot be used again.',
    responses={
        200: OpenApiResponse(description='Logged out successfully'),
        400: OpenApiResponse(description='Invalid or expired token'),
    }
)
class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'A refresh token is required for logout.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'success': True, 'message': 'Successfully logged out.'},
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {'error': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST
            )

