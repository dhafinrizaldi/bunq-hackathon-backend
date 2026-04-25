import json

import requests
from bunq import ApiEnvironmentType
from bunq.sdk.context.api_context import ApiContext
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import LoginUserSerializer, RegisterSerializer

User = get_user_model()


class AuthViewSet(viewsets.GenericViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Best-effort bunq sandbox provisioning. We don't fail registration if
        # the bunq sandbox is unreachable — the demo users hit bunq via the
        # shared bunq-api service which uses one global API key, not the
        # per-user keys generated here.
        try:
            bunq_api_key = self._create_bunq_api_key(serializer.instance)
            serializer.instance.bunq_api_key = bunq_api_key
            serializer.instance.bunq_context = self._create_bunq_context(bunq_api_key)
            serializer.instance.save()
        except Exception:
            pass

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _create_bunq_api_key(self, user):
        url = "https://public-api.sandbox.bunq.com/v1/sandbox-user-person"
        response = requests.post(
            url,
            headers={"User-Agent": "django-app", "Content-Type": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json()["Response"][0]["ApiKey"]["api_key"]

    def _create_bunq_context(self, api_key):
        api_context = ApiContext.create(
            ApiEnvironmentType.SANDBOX,
            api_key,
            "django-backend",
        )
        return json.loads(api_context.to_json())

    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        serializer = LoginUserSerializer(data=request.data)

        if not serializer.is_valid():
            error_code = serializer.errors.get('code', ["unknown"])[0]
            if error_code == 'user_inactive':
                return Response(
                    {'error': 'Your account is inactive.', 'code': 'user_inactive'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if error_code == 'invalid_credentials':
                return Response(
                    {'error': 'Invalid email or password.', 'code': 'invalid_credentials'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response = Response(
            {
                'message': 'Login Successful',
                'username': user.username,
                'email': user.email,
                'access': access_token,
                'refresh': refresh_token,
            },
            status=status.HTTP_200_OK,
        )

        # Also set HTTP-only cookies so the browser admin still works.
        response.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE'],
            value=access_token,
            expires=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            httponly=True,
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
        )
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
            httponly=True,
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
        )
        return response



class MonetaryAccountViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        try:
            user_id = user.get_bunq_id()
            session_token = user.get_session_token()
        except Exception:
            return Response({'error': 'No bunq context for user'}, status=400)

        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account-bank"
        response = requests.get(
            url,
            headers={
                "User-Agent": "django-app",
                "Content-Type": "application/json",
                "X-Bunq-Client-Authentication": session_token,
            },
            timeout=15,
        )
        response.raise_for_status()
        return Response(response.json(), status=status.HTTP_200_OK)


class ContactsViewSet(viewsets.GenericViewSet):
    """List other users on the platform — used as the friend picker."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        users = User.objects.exclude(id=request.user.id).filter(is_active=True).order_by('username')
        return Response([
            {
                'id': str(u.id),
                'email': u.email,
                'name': u.username or u.email.split('@')[0],
                'avatarUrl': '',
            }
            for u in users
        ])


class MeViewSet(viewsets.GenericViewSet):
    """Return the current authenticated user."""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        u = request.user
        return Response({
            'id': str(u.id),
            'email': u.email,
            'username': u.username,
            'name': u.username or u.email.split('@')[0],
        })
