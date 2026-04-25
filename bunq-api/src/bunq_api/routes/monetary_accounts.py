import logging

from bunq.sdk.model.generated.endpoint import MonetaryAccountApiObject, MonetaryAccountBankApiObject
from fastapi import APIRouter, Request

router = APIRouter(prefix="/monetary-accounts", tags=["accounts"])
logger = logging.getLogger(__name__)


@router.get("/")
def list_monetary_accounts():
    logger.info("Fetching monetary accounts")
    accounts = MonetaryAccountApiObject.list().value
    logger.info("Returning %d accounts", len(accounts))
    return accounts


@router.get("/{account_id}")
def get_monetary_account(account_id: int):
    logger.info("Fetching monetary account %d", account_id)
    account = MonetaryAccountApiObject.get(account_id).value
    return account


@router.post("/")
async def create_monetary_account(request: Request):
    body = await request.json()
    description = body.get("description", "Savings")
    currency = body.get("currency", "EUR")
    logger.info("Creating monetary account: %s (%s)", description, currency)
    account_id = MonetaryAccountBankApiObject.create(
        currency=currency,
        description=description,
    ).value
    logger.info("Created monetary account with id: %s", account_id)
    return MonetaryAccountApiObject.get(account_id).value
