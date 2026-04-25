from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from bunq.sdk.context.api_context import ApiContext
from bunq import ApiEnvironmentType
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, LoginUserSerializer
from django.conf import settings

import json
import requests

def create_bunq_api_key(self, user):
    url = "https://public-api.sandbox.bunq.com/v1/sandbox-user-person"
    
    response = requests.post(url, headers={"User-Agent": "django-app", "Content-Type": "application/json"})
    response.raise_for_status()
    
    data = response.json()
    api_key = data["Response"][0]["ApiKey"]["api_key"]
    
    print(f"Created bunq API key for user: {user.email}")
    return api_key
class AuthViewSet(viewsets.GenericViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='register')
    def register(self, request):
        print("REGISTER CALLED")
        print('request data: ', request.data)
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Create bunq api key here-
        # Endpoint: https://public-api.sandbox.bunq.com/v1/sandbox-user-person
        bunq_api_key = self.create_bunq_api_key(serializer.instance)
        serializer.instance.bunq_api_key = bunq_api_key
        serializer.instance.save()

        # Create bunq context
        bunq_context = self.create_bunq_context(bunq_api_key)
        serializer.instance.bunq_context = bunq_context
        serializer.instance.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def create_bunq_api_key(self, user):
        url = "https://public-api.sandbox.bunq.com/v1/sandbox-user-person"
        
        response = requests.post(url, headers={"User-Agent": "django-app", "Content-Type": "application/json"})
        response.raise_for_status()
        
        data = response.json()
        api_key = data["Response"][0]["ApiKey"]["api_key"]
        
        print(f"Created bunq API key for user: {user.email}")
        return api_key
    
    def create_bunq_context(self, api_key):
        api_context = ApiContext.create(
            ApiEnvironmentType.SANDBOX,
            api_key,
            "My Device Description"
        )
        return json.loads(api_context.to_json())
        
    
   
    @action(detail=False, methods=['post'], url_path='login')
    def login(self, request):
        serializer = LoginUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.validated_data

            # Generate tokens ONCE and store them in variables
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            # # Get the origin from request
            # origin = request.headers.get('Origin', '')
            # print(f'User-Agent: {request.META.get("HTTP_USER_AGENT", "")}')
            # print(f'Origin: {origin}')

            # Creating response with tokens in HTTP-only cookies
            response = Response(
                {
                    'message': 'Login Successful',
                    'username': user.username
                },
                status=status.HTTP_200_OK)

            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'],
                expires=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
                value=access_token,
                httponly=True,
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            )
            response.set_cookie(
                key='refresh_token',
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
                value=refresh_token,
                httponly=True,
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE'],
            )
            ##### CRITICAL: ADD CORS HEADERS #####
            # if origin:
            #     response['Access-Control-Allow-Origin'] = origin
            # response['Access-Control-Allow-Credentials'] = 'true'
            #######################################

            # Debug: print cookie details
            # print(f"Setting cookies for origin: {origin}")
            for cookie in response.cookies.values():
                print(f"  Cookie: {cookie.key}")
                print(f"    Value: {cookie.value[:20]}...")
                print(f"    secure={cookie['secure']}")
                print(f"    samesite={cookie['samesite']}")
                print(f"    httponly={cookie['httponly']}")
            # print('RETURNING LOGIN RESPONSE: ', response)
            return response
        else:
            print("login error: ", serializer.errors.get("error"))
            # For simple ValidationError, the error is in non_field_errors
            error_message = serializer.errors.get('error',
                                                  ['Authentication failed'])[0]
            # Check for specific error codes in the serializer errors
            error_code = serializer.errors.get('code',
                                               ["Unknown error code"])[0]

            if error_code == 'user_inactive':
                return Response(
                    {
                        'error': 'Your account is inactive. Please contact support.',
                        'code': 'user_inactive'
                    },
                    status=status.HTTP_403_FORBIDDEN)

            elif error_code == 'invalid_credentials':
                # print("wrong creds")
                return Response(
                    {
                        'error': 'Invalid email or password. Please try again.',
                        'code': 'invalid_credentials'
                    },
                    status=status.HTTP_401_UNAUTHORIZED)
            else:
                # Handle other validation errors
                return Response(serializer.errors,
                                status=status.HTTP_400_BAD_REQUEST)

class MonetaryAccountViewSet(viewsets.GenericViewSet):

    def list(self, request):
        user = request.user
        user_id = user.get_bunq_id()        
        session_token = user.get_session_token()        
        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account-bank"
        
        response = requests.get(url, headers={
            "User-Agent": "django-app", 
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token
            })
        response.raise_for_status()
        
        data = response.json()
       
        return Response(data,
                                status=status.HTTP_200_OK)
    

class PaymentViewSet(viewsets.GenericViewSet):

    def list(self, request):
        user = request.user
        user_id = user.get_bunq_id()        
        session_token = user.get_session_token()     
        primary_account = user.get_primary_account()
        # print('Primary account: ', primary_account) 
        
        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account/{primary_account['id']}/payment"
        
        response = requests.get(url, headers={
            "User-Agent": "django-app", 
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token
            })
        response.raise_for_status()
        
        data = response.json()
       
        return Response(data,
                                status=status.HTTP_200_OK)
    
    def create(self, request):
        user = request.user
        user_id = user.get_bunq_id()
        session_token = user.get_session_token()
        primary_account = user.get_primary_account()

        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account/{primary_account['id']}/payment"

        payload = {
            "amount": request.data.get("amount"),
            "counterparty_alias": request.data.get("counterparty_alias"),
            "description": request.data.get("description"),
        }

        if request.data.get("attachment"):
            payload["attachment"] = request.data.get("attachment")
        if request.data.get("merchant_reference"):
            payload["merchant_reference"] = request.data.get("merchant_reference")
        if request.data.get("allow_bunqto") is not None:
            payload["allow_bunqto"] = request.data.get("allow_bunqto")

        response = requests.post(url, json=payload, headers={
            "User-Agent": "django-app",
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token,
        })
        response.raise_for_status()

        return Response(response.json(), status=status.HTTP_201_CREATED)
