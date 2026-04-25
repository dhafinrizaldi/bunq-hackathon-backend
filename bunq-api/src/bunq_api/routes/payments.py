import json
import logging

from bunq.sdk.model.generated.endpoint import PaymentApiObject
from bunq.sdk.model.generated.object_ import AmountObject, PointerObject
from fastapi import APIRouter, Request

router = APIRouter(prefix="/payments", tags=["accounts"])
logger = logging.getLogger(__name__)


@router.get("/")
def list_payments():
    logger.info("Fetching payments")
    payments = PaymentApiObject.list().value

    # Load mock payments
    with open("mockdata/payments.json", "r") as f:
        mock_payments = json.load(f)
        payments.extend(mock_payments)

    with open("mockdata/deposits.json", "r") as f:
        payments.extend(json.load(f))

    logger.info("Returning %d payments", len(payments))
    return payments


@router.post("/")
async def create_payment(request: Request):
    payment = await request.json()
    logger.info("Creating payment: %s", payment)
    payment_id = PaymentApiObject.create(
        amount=AmountObject(payment.get("amount", 0), payment.get("currency", "EUR")),
        counterparty_alias=PointerObject(
            payment.get("counterparty_type"),
            payment.get("counterparty_alias"),
            payment.get("counterparty_name", "Unknown"),  # add this!
        ),
        description=payment.get("description"),
    ).value
    logger.info("Payment created with id: %s", payment_id)
    return PaymentApiObject.get(payment_id).value


@router.get("/{payment_id}")
def get_payment(payment_id: int):
    logger.info("Fetching payment %d", payment_id)
    payment = PaymentApiObject.get(payment_id).value
    return payment
