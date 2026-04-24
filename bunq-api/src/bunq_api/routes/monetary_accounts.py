import logging
from fastapi import APIRouter
from bunq.sdk.model.generated.endpoint import MonetaryAccountApiObject

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