from rest_framework import serializers

from .models import (
    ItemAllocation,
    OriginalTransaction,
    PaymentRequest,
    ReceiptItem,
    SplitParticipant,
    SplitSession,
)


class OriginalTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = OriginalTransaction
        fields = ('id', 'initiator', 'merchant_name', 'total_amount', 'currency', 'date')


class ItemAllocationSerializer(serializers.ModelSerializer):
    participant_email = serializers.CharField(
        source='participant.user.email', read_only=True
    )

    class Meta:
        model = ItemAllocation
        fields = ('id', 'item', 'participant', 'participant_email', 'allocated_amount')


class ReceiptItemSerializer(serializers.ModelSerializer):
    allocations = ItemAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = ReceiptItem
        fields = ('id', 'description', 'total_price', 'quantity', 'allocations')


class SplitParticipantSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = SplitParticipant
        fields = ('id', 'user', 'user_email')


class PaymentRequestSerializer(serializers.ModelSerializer):
    payer_email = serializers.CharField(source='payer.email', read_only=True)
    payee_email = serializers.CharField(source='payee.email', read_only=True)

    class Meta:
        model = PaymentRequest
        fields = (
            'id',
            'payer',
            'payer_email',
            'payee',
            'payee_email',
            'amount',
            'bunq_request_id',
            'status',
            'created_at',
        )


class SplitSessionListSerializer(serializers.ModelSerializer):
    merchant_name = serializers.CharField(source='transaction.merchant_name', read_only=True)
    date = serializers.DateTimeField(source='transaction.date', read_only=True)
    total_amount = serializers.DecimalField(
        source='transaction.total_amount', read_only=True, max_digits=10, decimal_places=2
    )
    is_fully_paid = serializers.SerializerMethodField()

    class Meta:
        model = SplitSession
        fields = ('id', 'merchant_name', 'date', 'total_amount', 'is_fully_paid')

    def get_is_fully_paid(self, obj):
        requests = obj.payment_requests.all()
        return requests.exists() and requests.filter(status=PaymentRequest.Status.PAID).count() == requests.count()


class SplitSessionDetailSerializer(serializers.ModelSerializer):
    transaction = OriginalTransactionSerializer(read_only=True)
    participants = SplitParticipantSerializer(many=True, read_only=True)
    items = ReceiptItemSerializer(many=True, read_only=True)
    payment_requests = PaymentRequestSerializer(many=True, read_only=True)
    is_fully_paid = serializers.SerializerMethodField()

    class Meta:
        model = SplitSession
        fields = (
            'id',
            'transaction',
            'receipt_image',
            'user_prompt',
            'status',
            'ai_raw_response',
            'participants',
            'items',
            'payment_requests',
            'is_fully_paid',
            'created_at',
            'updated_at',
        )

    def get_is_fully_paid(self, obj):
        payment_requests = obj.payment_requests.all()
        if not payment_requests.exists():
            return False
        return payment_requests.filter(status=PaymentRequest.Status.PAID).count() == payment_requests.count()


class SplitSessionCreateSerializer(serializers.ModelSerializer):
    """Used to create a SplitSession from an existing OriginalTransaction id."""

    class Meta:
        model = SplitSession
        fields = ('id', 'transaction', 'status')
        read_only_fields = ('id', 'status')
