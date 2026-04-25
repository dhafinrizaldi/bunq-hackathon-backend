from django.contrib import admin

from .models import (
    ItemAllocation,
    OriginalTransaction,
    PaymentRequest,
    ReceiptItem,
    SplitParticipant,
    SplitSession,
)


@admin.register(OriginalTransaction)
class OriginalTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_name', 'total_amount', 'currency', 'initiator', 'date')
    search_fields = ('merchant_name', 'bunq_transaction_id', 'initiator__email')
    list_filter = ('currency', 'date')


@admin.register(SplitSession)
class SplitSessionAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'status', 'created_at', 'updated_at')
    list_filter = ('status',)
    readonly_fields = ('ai_raw_response',)


@admin.register(SplitParticipant)
class SplitParticipantAdmin(admin.ModelAdmin):
    list_display = ('session', 'user')
    search_fields = ('user__email',)


@admin.register(ReceiptItem)
class ReceiptItemAdmin(admin.ModelAdmin):
    list_display = ('session', 'description', 'quantity', 'total_price')
    search_fields = ('description',)


@admin.register(ItemAllocation)
class ItemAllocationAdmin(admin.ModelAdmin):
    list_display = ('item', 'participant', 'allocated_amount')


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = ('session', 'payer', 'payee', 'amount', 'status')
    list_filter = ('status',)
    search_fields = ('payer__email', 'payee__email', 'bunq_request_id')
