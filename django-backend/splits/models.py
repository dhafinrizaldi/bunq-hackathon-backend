from django.conf import settings
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OriginalTransaction(BaseModel):
    """The initial payment detected via Bunq webhook."""

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='initiated_transactions',
        on_delete=models.CASCADE,
    )
    bunq_transaction_id = models.CharField(max_length=100, unique=True)
    merchant_name = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    date = models.DateTimeField()

    def __str__(self):
        return f"{self.merchant_name} - {self.total_amount} {self.currency}"


class SplitSession(BaseModel):
    """The overarching session for splitting a specific transaction."""

    class Status(models.TextChoices):
        DRAFT = 'DR', 'Draft'
        PROCESSING_AI = 'PA', 'Processing AI'
        PENDING_CONFIRMATION = 'PC', 'Pending Confirmation'
        COMPLETED = 'CO', 'Completed'
        FAILED = 'FA', 'Failed'

    transaction = models.OneToOneField(
        OriginalTransaction,
        on_delete=models.CASCADE,
        related_name='split_session',
    )
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    user_prompt = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=2,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    ai_raw_response = models.JSONField(blank=True, null=True)


class SplitParticipant(BaseModel):
    """Users selected to be part of this specific split."""

    session = models.ForeignKey(
        SplitSession,
        related_name='participants',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('session', 'user')


class ReceiptItem(BaseModel):
    """Individual items parsed from the receipt by Claude."""

    session = models.ForeignKey(
        SplitSession,
        related_name='items',
        on_delete=models.CASCADE,
    )
    description = models.CharField(max_length=255)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)


class ItemAllocation(BaseModel):
    """Maps how much a specific participant owes for a specific receipt item."""

    item = models.ForeignKey(
        ReceiptItem,
        related_name='allocations',
        on_delete=models.CASCADE,
    )
    participant = models.ForeignKey(
        SplitParticipant,
        related_name='allocations',
        on_delete=models.CASCADE,
    )
    allocated_amount = models.DecimalField(max_digits=8, decimal_places=2)


class PaymentRequest(BaseModel):
    """The actual payment request sent via the Bunq API to a participant."""

    class Status(models.TextChoices):
        PENDING = 'PE', 'Pending'
        PAID = 'PA', 'Paid'
        REJECTED = 'RE', 'Rejected'
        CANCELLED = 'CA', 'Cancelled'

    session = models.ForeignKey(
        SplitSession,
        related_name='payment_requests',
        on_delete=models.CASCADE,
    )
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='incoming_requests',
        on_delete=models.CASCADE,
    )
    payee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='outgoing_requests',
        on_delete=models.CASCADE,
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    bunq_request_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=2,
        choices=Status.choices,
        default=Status.PENDING,
    )

    def __str__(self):
        return f"Request to {self.payer} for {self.amount}"
