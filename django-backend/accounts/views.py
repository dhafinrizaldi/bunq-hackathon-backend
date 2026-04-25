import json
import os

import requests
from anthropic import Anthropic
from bunq import ApiEnvironmentType
from bunq.sdk.context.api_context import ApiContext
from django.conf import settings
from dotenv import load_dotenv
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .client import MCPClient
from .models import AllocationRule, Contact, SalarySetup
from .serializers import (
    ContactSerializer,
    LoginUserSerializer,
    RegisterSerializer,
    SalarySetupSerializer,
)

import json
import requests
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import load_pem_private_key
import base64
import hashlib

# Import MCP client
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

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

# ---------------------------------------------------------------------------
# Salary setup
# ---------------------------------------------------------------------------

def _parse_salary_description(raw_description: str, contacts: list) -> dict:
    """Call Claude to turn a natural-language salary description into structured rules."""
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    contact_list = "\n".join(
        f"- {c['nickname']}: IBAN {c['iban']}" for c in contacts
    ) or "No contacts saved yet."

    prompt = f"""Parse this salary allocation description into structured rules.

Available contacts:
{contact_list}

User's salary description:
"{raw_description}"

Return a JSON object with this exact shape:
{{
  "trigger_keyword": "employer name to match in incoming payment (e.g. ASML)",
  "trigger_min_amount": 1000,
  "rules": [
    {{
      "rule_type": "transfer",
      "amount_type": "fixed",
      "amount": 50.0,
      "contact_nickname": "sister",
      "invest_symbol": "",
      "description": "€50 to sister"
    }},
    {{
      "rule_type": "invest",
      "amount_type": "percent",
      "amount": 10.0,
      "contact_nickname": "",
      "invest_symbol": "SPY",
      "description": "10% invested in SPY"
    }},
    {{
      "rule_type": "save",
      "amount_type": "percent",
      "amount": 15.0,
      "contact_nickname": "",
      "invest_symbol": "",
      "description": "15% to savings pocket"
    }}
  ]
}}

Rules:
- rule_type must be one of: "transfer", "invest", "save"
- amount_type must be one of: "fixed" (EUR) or "percent" (0-100)
- contact_nickname must exactly match one of the available contacts (or empty string)
- invest_symbol: use a broad ETF like SPY or VOO if not specified
- List fixed transfers first, then percentage-based rules
- Return only valid JSON, no markdown fences"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(response.content[0].text)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def salary_setup_view(request):
    if request.method == "GET":
        try:
            setup = SalarySetup.objects.get(user=request.user)
            return Response(SalarySetupSerializer(setup).data)
        except SalarySetup.DoesNotExist:
            return Response({"detail": "No salary setup found."}, status=status.HTTP_404_NOT_FOUND)

    # POST — create or replace
    raw_description = request.data.get("description", "").strip()
    if not raw_description:
        return Response({"error": "'description' is required."}, status=status.HTTP_400_BAD_REQUEST)

    contacts = list(request.user.contacts.values("nickname", "iban", "display_name"))

    try:
        parsed = _parse_salary_description(raw_description, contacts)
    except Exception as e:
        return Response({"error": f"Failed to parse description: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    setup, _ = SalarySetup.objects.update_or_create(
        user=request.user,
        defaults={
            "raw_description": raw_description,
            "trigger_keyword": parsed.get("trigger_keyword", ""),
            "trigger_min_amount": parsed.get("trigger_min_amount", 1000),
            "is_active": True,
        },
    )

    setup.rules.all().delete()
    for i, rule in enumerate(parsed.get("rules", [])):
        contact = None
        nickname = (rule.get("contact_nickname") or "").strip().lower()
        if nickname:
            contact = request.user.contacts.filter(nickname=nickname).first()

        AllocationRule.objects.create(
            setup=setup,
            rule_type=rule["rule_type"],
            amount_type=rule["amount_type"],
            amount=rule["amount"],
            contact=contact,
            invest_symbol=rule.get("invest_symbol", ""),
            description=rule.get("description", ""),
            order=i,
        )

    return Response(SalarySetupSerializer(setup).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def contacts_internal(request):
    """Internal read-only endpoint for the MCP server — no auth required."""
    contacts = Contact.objects.all().values("nickname", "display_name", "iban", "bunq_user_id")
    return Response(list(contacts))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def contacts_view(request):
    if request.method == "GET":
        contacts = request.user.contacts.all()
        return Response(ContactSerializer(contacts, many=True).data)

    serializer = ContactSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Webhook + salary execution
# ---------------------------------------------------------------------------

MCP_CLIENT_URL = "http://localhost:8001/query"

import logging as _logging
_webhook_logger = _logging.getLogger("accounts.webhook")


def _compute_amount(rule, total: float) -> float:
    if rule.amount_type == AllocationRule.AMOUNT_TYPE_FIXED:
        return float(rule.amount)
    return round(total * float(rule.amount) / 100, 2)


def _build_allocation_query(setup: SalarySetup, total: float) -> str:
    lines = []
    for rule in setup.rules.all():
        eur = _compute_amount(rule, total)
        if rule.rule_type == AllocationRule.RULE_TYPE_TRANSFER:
            contact_name = rule.contact.nickname if rule.contact else "unknown"
            lines.append(f"- Send €{eur:.2f} to {contact_name} using send_to_contact")
        elif rule.rule_type == AllocationRule.RULE_TYPE_INVEST:
            symbol = rule.invest_symbol or "SPY"
            lines.append(f"- Invest €{eur:.2f} in {symbol} using place_stock_order (notional, buy, market)")
        elif rule.rule_type == AllocationRule.RULE_TYPE_SAVE:
            lines.append(f"- Transfer €{eur:.2f} to the savings pocket using get_monetary_accounts to find the savings IBAN, then create_payment")

    rules_text = "\n".join(lines)
    return f"""A salary payment of €{total:.2f} just arrived from '{setup.trigger_keyword}'.

Execute each of the following allocation rules in order. Use the exact tools specified:
{rules_text}

After completing all steps, summarise what was done and confirm each action succeeded."""


def _call_mcp(query: str) -> str:
    resp = requests.post(MCP_CLIENT_URL, json={"query": query}, timeout=120)
    resp.raise_for_status()
    return resp.json().get("response", "")


def _trigger_allocation(setup: SalarySetup, amount: float):
    query = _build_allocation_query(setup, amount)
    _webhook_logger.info("Triggering allocation for %s — €%.2f", setup.user.email, amount)
    try:
        result = _call_mcp(query)
        _webhook_logger.info("Allocation complete: %s", result[:300])
    except Exception as e:
        _webhook_logger.error("Allocation failed: %s", e)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def bunq_webhook(request):
    """Receives Bunq payment notifications and triggers salary allocation."""
    try:
        notification = request.data.get("NotificationUrl", {})
        obj = notification.get("object", {})
        payment = obj.get("Payment", {})

        if not payment:
            return Response({"status": "ignored"})

        amount = float(payment.get("amount", {}).get("value", 0))
        description = payment.get("description", "")

        if amount <= 0:
            return Response({"status": "ignored - outgoing"})

        for setup in SalarySetup.objects.filter(is_active=True):
            if (
                setup.trigger_keyword.lower() in description.lower()
                and amount >= float(setup.trigger_min_amount)
            ):
                _trigger_allocation(setup, amount)
                return Response({"status": "triggered", "amount": amount})

        return Response({"status": "no matching setup"})

    except Exception as e:
        _webhook_logger.error("Webhook error: %s", e)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def simulate_salary(request):
    """
    Test endpoint — simulates a salary payment arriving without needing a real Bunq webhook.

    POST body:
        { "amount": 4200.00, "description": "Salaris ASML" }
    """
    amount = float(request.data.get("amount", 0))
    description = request.data.get("description", "")

    if not amount or not description:
        return Response({"error": "amount and description are required"}, status=400)

    matched = None
    for setup in SalarySetup.objects.filter(is_active=True):
        if (
            setup.trigger_keyword.lower() in description.lower()
            and amount >= float(setup.trigger_min_amount)
        ):
            matched = setup
            break

    if not matched:
        return Response({"status": "no matching salary setup found"})

    query = _build_allocation_query(matched, amount)
    return Response({
        "status": "matched",
        "setup": matched.trigger_keyword,
        "amount": amount,
        "mcp_query": query,
        "instruction": "Call POST /api/execute-allocation/ to actually run it",
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def execute_allocation(request):
    """
    Actually runs the allocation via the MCP client.
    Call simulate_salary first to preview the query, then call this to execute.

    POST body:
        { "amount": 4200.00, "description": "Salaris ASML" }
    """
    amount = float(request.data.get("amount", 0))
    description = request.data.get("description", "")

    matched = None
    for setup in SalarySetup.objects.filter(is_active=True):
        if (
            setup.trigger_keyword.lower() in description.lower()
            and amount >= float(setup.trigger_min_amount)
        ):
            matched = setup
            break

    if not matched:
        return Response({"status": "no matching salary setup found"})

    query = _build_allocation_query(matched, amount)
    try:
        result = _call_mcp(query)
        return Response({"status": "executed", "response": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


class MonetaryAccountViewSet(viewsets.GenericViewSet):

    def list(self, request):
        print('MonetaryAccountViewSet called for user: ', request.user.email)
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
        print('Monetary accounts data: ', data)
       
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
        primary_pem = user.get_private_pem()
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

        payload_str = json.dumps(payload, separators=(',', ':'))
        signature = self.sign_data(payload_str, primary_pem)

        print("[DEBUG] URL:", url)
        print("[DEBUG] Payload being sent:", payload_str)
        print("[DEBUG] Signature:", signature)
        print("[DEBUG] Session token (first 20):", session_token[:20] if session_token else None)

        response = requests.post(url, data=payload_str, headers={
            "User-Agent": "django-app",
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token,
            "X-Bunq-Client-Signature": signature,
        })

        print("[DEBUG] Response status:", response.status_code)
        print("[DEBUG] Response body:", response.text)

        if not response.ok:
            return Response(response.json(), status=response.status_code)

        return Response(response.json(), status=status.HTTP_201_CREATED)

    def load_private_key(self, private_key_pem):
        return load_pem_private_key(
            private_key_pem.encode('utf-8'),  # converts string → bytes
            password=None
        )
    def sign_data(self, data, private_key_pem):
        """Signs the given data with the provided private key using SHA256 and PKCS#1 v1.5 padding.
        
        Args:
            data (str): The data to sign (should be the JSON request body)
            private_key_pem (str): The private key in PEM format
        
        Returns:
            str: Base64 encoded signature
        """
        private_key = self.load_private_key(private_key_pem)
        
        # Ensure the data is encoded in UTF-8 exactly as it will be sent
        encoded_data = data.encode('utf-8')

        # Debug: Print exact bytes being signed
        print("\n[DEBUG] Signing Data Bytes:", encoded_data)
        print("[DEBUG] SHA256 Hash of Data:", hashlib.sha256(encoded_data).hexdigest())

        # Generate signature using SHA256 and PKCS#1 v1.5 padding as required by Bunq
        signature = private_key.sign(
            encoded_data,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Encode in Base64 (as required by Bunq API)
        encoded_signature = base64.b64encode(signature).decode('utf-8')

        # Debug: Print signature
        print("[DEBUG] Base64 Encoded Signature:", encoded_signature)

        return encoded_signature
class RequestInquiryViewSet(viewsets.GenericViewSet):

    def list(self, request):
        user = request.user
        user_id = user.get_bunq_id()        
        session_token = user.get_session_token()     
        primary_account = user.get_primary_account()
        # print('Primary account: ', primary_account) 
        
        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account/{primary_account['id']}/request-inquiry"
        
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
        print(request.data)
        user = request.user
        user_id = user.get_bunq_id()
        session_token = user.get_session_token()
        primary_account = user.get_primary_account()

        url = f"https://public-api.sandbox.bunq.com/v1/user/{user_id}/monetary-account/{primary_account['id']}/request-inquiry"

        payload = {
            "amount_inquired": request.data.get("amount_inquired"),
            "counterparty_alias": request.data.get("counterparty_alias"),
            "description": request.data.get("description"),
        }

        if request.data.get("attachment"):
            payload["attachment"] = request.data.get("attachment")
        if request.data.get("merchant_reference"):
            payload["merchant_reference"] = request.data.get("merchant_reference")
        if request.data.get("allow_bunqme") is not None:
            payload["allow_bunqme"] = request.data.get("allow_bunqme")

        response = requests.post(url, json=payload, headers={
            "User-Agent": "django-app",
            "Content-Type": "application/json",
            "X-Bunq-Client-Authentication": session_token,
        })
        response.raise_for_status()

        return Response(response.json(), status=status.HTTP_201_CREATED)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# async def agent_query(request):
#     query = request.data.get('query')
#     acc_tok = request.COOKIES.get('access_token')
#     ref_tok = request.COOKIES.get('refresh_token')
#     token = {
#         'access_token': acc_tok,    
#         'refresh_token': ref_tok
#     }
#     client = MCPClient(auth_token=token)
#     try:
#         await client.connect_to_server('accounts/server.py')
#         result = await client.process_query(query)
#         return Response({'result': result})
#     finally:
#         await client.cleanup()

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
import json
from asgiref.sync import sync_to_async

from django.http import JsonResponse
from django.contrib.auth import get_user_model
import jwt
from django.conf import settings

async def get_user_from_request(request):
    token = request.COOKIES.get('access_token')
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        User = get_user_model()
        user = await User.objects.aget(id=payload['user_id'])
        return user
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
        return None
@csrf_exempt
async def agent_query(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    user = await get_user_from_request(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    data = json.loads(request.body)
    query = data.get('query')
    acc_tok = request.COOKIES.get('access_token')
    ref_tok = request.COOKIES.get('refresh_token')
    token = {
        'access_token': acc_tok,
        'refresh_token': ref_tok
    }
    client = MCPClient(auth_token=token)
    try:
        server_path = os.path.join(os.path.dirname(__file__), 'server.py')
        await client.connect_to_server(server_path)
        result = await client.process_query(query)
        return JsonResponse({'result': result})
    finally:
        await client.cleanup()