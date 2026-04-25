import base64
import logging
import os
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import requests as http_requests
from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    ItemAllocation,
    OriginalTransaction,
    PaymentRequest,
    ReceiptItem,
    SplitParticipant,
    SplitSession,
)
from .serializers import (
    OriginalTransactionSerializer,
    ReceiptItemSerializer,
    SplitSessionCreateSerializer,
    SplitSessionDetailSerializer,
    SplitSessionListSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()

MCP_CLIENT_URL = os.getenv("MCP_CLIENT_URL", "http://localhost:8001")
BUNQ_API_URL = os.getenv("BUNQ_API_URL", "http://localhost:8002")


def _quantize(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _even_split(items, participant_emails, payee_email):
    """Compute even-split allocations.

    Splits each item across (participants + payee) evenly. Returns a list shaped
    like Claude's `interpret_split` output. Rounding remainder lands on the payee.
    """
    all_emails = list(participant_emails)
    if payee_email not in all_emails:
        all_emails = [payee_email] + all_emails
    n = len(all_emails)
    by_email = {e: {"participant_email": e, "total_amount": Decimal("0"), "items": []} for e in all_emails}

    for item in items:
        total = Decimal(str(item.total_price))
        share = _quantize(total / n)
        diff = total - share * n  # rounding remainder, lands on payee
        for email in all_emails:
            this_share = share + diff if email == payee_email else share
            by_email[email]["items"].append({
                "item_id": item.id,
                "description": item.description,
                "share_amount": float(this_share),
            })
            by_email[email]["total_amount"] += this_share

    return [
        {
            "participant_email": v["participant_email"],
            "total_amount": float(_quantize(v["total_amount"])),
            "items": v["items"],
        }
        for v in by_email.values()
    ]


class SplitSessionViewSet(viewsets.ModelViewSet):
    queryset = SplitSession.objects.select_related('transaction').prefetch_related(
        'participants', 'items', 'payment_requests'
    )
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(transaction__initiator=self.request.user).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return SplitSessionCreateSerializer
        if self.action == 'list':
            return SplitSessionListSerializer
        return SplitSessionDetailSerializer

    def create(self, request, *args, **kwargs):
        # Idempotent create: if a session already exists for this transaction,
        # return it instead of surfacing a uniqueness validation error.
        transaction_id = request.data.get('transaction')
        existing = None
        if transaction_id is not None:
            existing = SplitSession.objects.filter(
                transaction_id=transaction_id,
                transaction__initiator=request.user,
            ).first()
        if existing:
            return Response(SplitSessionDetailSerializer(existing).data, status=status.HTTP_200_OK)

        serializer = SplitSessionCreateSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            # If DRF hits the OneToOne uniqueness validator before our checks,
            # return the already-created session for this transaction.
            if transaction_id is not None:
                existing = SplitSession.objects.filter(
                    transaction_id=transaction_id,
                    transaction__initiator=request.user,
                ).first()
                if existing:
                    return Response(SplitSessionDetailSerializer(existing).data, status=status.HTTP_200_OK)
            raise
        # Ensure the transaction belongs to the requesting user
        txn = serializer.validated_data['transaction']
        if txn.initiator_id != request.user.id:
            return Response({'error': 'Transaction not yours'}, status=status.HTTP_403_FORBIDDEN)
        # OneToOne — bail if a session already exists for this transaction
        existing = SplitSession.objects.filter(transaction=txn).first()
        if existing:
            return Response(SplitSessionDetailSerializer(existing).data, status=status.HTTP_200_OK)
        session = serializer.save()
        return Response(SplitSessionDetailSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def extract_receipt(self, request):
        """Extract receipt items from an uploaded image without saving to a session."""
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image provided'}, status=400)

        image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        media_type = image_file.content_type or 'image/jpeg'

        try:
            mcp_resp = http_requests.post(
                f"{MCP_CLIENT_URL}/process_receipt",
                json={'image_base64': image_b64, 'media_type': media_type},
                timeout=60,
            )
            mcp_resp.raise_for_status()
        except Exception as exc:
            return Response({'error': f'MCP client error: {exc}'}, status=502)

        return Response(mcp_resp.json())

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def process_receipt(self, request, pk=None):
        """Upload a receipt image, extract items via MCP, and save them to the session."""
        session = self.get_object()
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'error': 'No image provided'}, status=400)

        session.receipt_image = image_file
        session.status = SplitSession.Status.PROCESSING_AI
        session.save()

        image_file.seek(0)
        image_b64 = base64.b64encode(image_file.read()).decode('utf-8')
        media_type = image_file.content_type or 'image/jpeg'

        try:
            mcp_resp = http_requests.post(
                f"{MCP_CLIENT_URL}/process_receipt",
                json={'image_base64': image_b64, 'media_type': media_type},
                timeout=60,
            )
            mcp_resp.raise_for_status()
        except Exception as exc:
            session.status = SplitSession.Status.FAILED
            session.save()
            return Response({'error': f'MCP client error: {exc}'}, status=502)

        receipt = mcp_resp.json()

        # Replace existing items + their allocations
        session.items.all().delete()
        saved_items = []
        for item in receipt.get('items', []):
            try:
                total = Decimal(str(item['total']))
            except Exception:
                continue
            saved_items.append(
                ReceiptItem.objects.create(
                    session=session,
                    description=item.get('name') or 'Item',
                    total_price=total,
                    quantity=int(item.get('quantity', 1) or 1),
                )
            )

        session.ai_raw_response = receipt
        session.status = SplitSession.Status.PENDING_CONFIRMATION
        session.save()

        return Response(ReceiptItemSerializer(saved_items, many=True).data)

    @action(detail=True, methods=['post'])
    def interpret(self, request, pk=None):
        """Map the user's free-text split description to per-participant allocations.

        Body: { participant_emails: [...], description: str, mode: 'even'|'specify' }
        Persists SplitParticipant + ItemAllocation rows. Returns full session detail.
        """
        session = self.get_object()
        payload = request.data
        mode = payload.get('mode') or 'specify'
        description = (payload.get('description') or '').strip()
        participant_emails = list(payload.get('participant_emails') or [])

        items = list(session.items.all())
        if not items:
            if mode == 'even':
                # No receipt scanned (pure even split). Create a synthetic line
                # item from the transaction total so the rest of the flow works
                # uniformly.
                synthetic = ReceiptItem.objects.create(
                    session=session,
                    description=session.transaction.merchant_name,
                    total_price=session.transaction.total_amount,
                    quantity=1,
                )
                items = [synthetic]
            else:
                return Response({'error': 'Session has no receipt items yet'}, status=400)

        # Resolve users
        users = {u.email: u for u in User.objects.filter(email__in=participant_emails)}
        missing = [e for e in participant_emails if e not in users]
        if missing:
            return Response({'error': f'Unknown users: {missing}'}, status=400)

        payee = request.user

        if mode == 'even':
            allocations_data = _even_split(items, participant_emails, payee.email)
        else:
            mcp_payload = {
                'description': description,
                'payee_email': payee.email,
                'participants': [
                    {'email': e, 'name': users[e].username or e.split('@')[0]}
                    for e in participant_emails
                ],
                'items': [
                    {
                        'id': item.id,
                        'description': item.description,
                        'total_price': float(item.total_price),
                        'quantity': item.quantity,
                    }
                    for item in items
                ],
            }
            try:
                resp = http_requests.post(
                    f"{MCP_CLIENT_URL}/interpret_split",
                    json=mcp_payload,
                    timeout=60,
                )
                resp.raise_for_status()
            except Exception as exc:
                logger.exception("interpret_split call failed")
                return Response({'error': f'MCP client error: {exc}'}, status=502)
            data = resp.json()
            allocations_data = data.get('allocations') or []

        # Wipe existing participants + allocations on the session
        ItemAllocation.objects.filter(item__session=session).delete()
        SplitParticipant.objects.filter(session=session).delete()

        # Persist participants — only non-payee, since payee doesn't owe themselves
        participants_by_email = {}
        for email in participant_emails:
            if email == payee.email:
                continue
            sp = SplitParticipant.objects.create(session=session, user=users[email])
            participants_by_email[email] = sp

        # Persist allocations (skip payee's own line)
        items_by_id = {item.id: item for item in items}
        for alloc in allocations_data:
            email = alloc.get('participant_email')
            if not email or email == payee.email:
                continue
            sp = participants_by_email.get(email)
            if not sp:
                continue
            for line in (alloc.get('items') or []):
                item = items_by_id.get(line.get('item_id'))
                if not item:
                    continue
                amt = _quantize(line.get('share_amount') or 0)
                if amt <= 0:
                    continue
                ItemAllocation.objects.create(
                    item=item,
                    participant=sp,
                    allocated_amount=amt,
                )

        session.user_prompt = description or session.user_prompt
        session.status = SplitSession.Status.PENDING_CONFIRMATION
        session.save()

        # Re-fetch so the serializer doesn't return the stale prefetch cache.
        fresh = self.get_queryset().get(pk=session.pk)
        return Response(SplitSessionDetailSerializer(fresh).data)

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Aggregate per-participant totals and fire bunq payment requests."""
        session = self.get_object()
        payee = request.user
        note = (request.data.get('note') or '').strip() or f"Split at {session.transaction.merchant_name}"

        # Sum allocations per participant
        totals = defaultdict(lambda: Decimal('0'))
        for item in session.items.all():
            for alloc in item.allocations.all():
                totals[alloc.participant_id] += alloc.allocated_amount

        if not totals:
            return Response({'error': 'No allocations — call /interpret/ first'}, status=400)

        # Wipe any prior payment requests so we don't double-send
        PaymentRequest.objects.filter(session=session).delete()

        for participant_id, amount in totals.items():
            amount = _quantize(amount)
            if amount <= 0:
                continue
            sp = SplitParticipant.objects.select_related('user').get(id=participant_id)
            payer = sp.user
            bunq_payload = {
                "amount": str(amount),
                "currency": "EUR",
                "description": note,
                "counterparty_type": "EMAIL",
                "counterparty_alias": payer.email,
                "counterparty_name": payer.username or payer.email,
            }
            bunq_id = None
            try:
                r = http_requests.post(
                    f"{BUNQ_API_URL}/request_inqs",
                    json=bunq_payload,
                    timeout=20,
                )
                r.raise_for_status()
                body = r.json() if r.content else {}
                bunq_id = str(body.get('_id_') or body.get('id') or '') or None
            except Exception as exc:
                # Demo robustness: still record the request locally so the UI shows it
                logger.warning("bunq request failed for %s: %s", payer.email, exc)

            PaymentRequest.objects.create(
                session=session,
                payer=payer,
                payee=payee,
                amount=amount,
                bunq_request_id=bunq_id,
                status=PaymentRequest.Status.PENDING,
            )

        session.status = SplitSession.Status.COMPLETED
        session.save()

        fresh = self.get_queryset().get(pk=session.pk)
        return Response(SplitSessionDetailSerializer(fresh).data)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def transcribe(self, request):
        """Proxy an audio file to the mcp-client /transcribe endpoint."""
        audio = request.FILES.get('audio')
        if not audio:
            return Response({'error': 'No audio provided'}, status=400)
        files = {
            'audio': (audio.name or 'audio.m4a', audio.read(), audio.content_type or 'audio/m4a'),
        }
        try:
            r = http_requests.post(f"{MCP_CLIENT_URL}/transcribe", files=files, timeout=60)
            r.raise_for_status()
        except Exception as exc:
            logger.exception("transcribe failed")
            return Response({'error': f'MCP client error: {exc}'}, status=502)
        return Response(r.json())


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """List the requesting user's bunq transactions (seeded fixtures for now)."""

    serializer_class = OriginalTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            OriginalTransaction.objects.filter(initiator=self.request.user)
            .order_by('-date')
        )
