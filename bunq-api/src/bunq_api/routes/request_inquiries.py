import logging

from bunq.sdk.model.generated.endpoint import RequestInquiryApiObject
from bunq.sdk.model.generated.object_ import AmountObject, PointerObject
from fastapi import APIRouter, Request

router = APIRouter(prefix="/request_inqs", tags=["accounts"])
logger = logging.getLogger(__name__)


@router.get("/")
def list_request_inqs():
    logger.info("Fetching request inquiries")
    request_inqs = RequestInquiryApiObject.list().value

    # Load mock request_inqs
    # with open("mockdata/request_inqs.json", "r") as f:
    #     mock_request_inqs = json.load(f)
    #     request_inqs.extend(mock_request_inqs)

    return request_inqs


@router.post("/")
async def create_request_inq(request: Request):
    request_inq = await request.json()
    logger.info("Creating request inquiry: %s", request_inq)
    request_inq_id = RequestInquiryApiObject.create(
        amount_inquired=AmountObject(
            request_inq.get("amount", 0), request_inq.get("currency", "EUR")
        ),
        counterparty_alias=PointerObject(
            request_inq.get("counterparty_type"),
            request_inq.get("counterparty_alias"),
            request_inq.get("counterparty_name", "Unknown"),  # add this!
        ),
        description=request_inq.get("description"),
        allow_bunqme=True,
    ).value
    logger.info("Request inquiry created with id: %s", request_inq_id)
    return RequestInquiryApiObject.get(request_inq_id).value


@router.get("/{request_inq_id}")
def get_request_inq(request_inq_id: int):
    logger.info("Fetching request inquiry %d", request_inq_id)
    request_inq = RequestInquiryApiObject.get(request_inq_id).value
    return request_inq
