import logging
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

import alpaca_tools
from custom_types import Receipt, UserSplit

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("bunq-mcp-server")
alpaca_tools.register(mcp)

# Constants
BUNQ_API_BASE = "http://127.0.0.1:8000"
USER_AGENT = "recipts-app/1.0"


async def make_bunq_request(
    url: str, method="get", payload=None
) -> dict[str, Any] | None:
    """Make a request to the BUNQ API with proper error handling."""
    logger.debug("Making %s request to %s", method.upper(), url)
    async with httpx.AsyncClient() as client:
        try:
            if method == "get":
                response = await client.get(url, timeout=30.0, follow_redirects=True)
            elif method == "post":
                response = await client.post(
                    url, json=payload, timeout=30.0, follow_redirects=True
                )

            if response.is_error:
                logger.error(
                    "Request to %s failed with status %d: %s",
                    url,
                    response.status_code,
                    response.text,
                )
                return None
            return response.json()
        except Exception as e:
            logger.error("Request to %s failed: %s", url, e)
            return None


@mcp.tool()
async def get_payments() -> str:
    """Get bunq payments"""
    logger.info("Tool called: get_payments")
    url = f"{BUNQ_API_BASE}/payments"
    data = await make_bunq_request(url)

    if not data:
        logger.warning("get_payments returned no data")
        return "No payments found"

    payments = [format_payment(payment) for payment in data]

    return "\n---\n".join(payments)
    # return {"payments": payments}


def format_payment(payment: dict) -> str:
    """Format a payment into readable string"""

    return f"""
Payment Details:
  ID: {payment.get("_id_", "Unknown")}
  Created: {payment.get("_created", "Unknown")}
  Amount: {payment.get("_amount", {}).get("_value", "0")} {payment.get("_amount", {}).get("_currency", "EUR")}
  Description: {payment.get("_description", "No description available")}
  Counterparty: {payment.get("_counterparty_alias", {}).get("label_monetary_account", {}).get("_display_name", "Unknown")}
"""


@mcp.tool()
async def create_payment(
    amount: str,
    description: str,
    counterparty_alias: str,
    counterparty_type: str = "EMAIL",
) -> str:
    """Create a bunq payment

    Args:
        amount: Payment amount (e.g., "10.00")
        description: Payment description
        counterparty_alias: Recipient email, IBAN, or phone number
        counterparty_type: Type of alias - "EMAIL", "IBAN", or "PHONE_NUMBER" (default: EMAIL)
    """
    logger.info(
        "Tool called: create_payment amount=%s counterparty=%s",
        amount,
        counterparty_alias,
    )
    payment_data = {
        "amount": amount,
        "description": description,
        "counterparty_alias": counterparty_alias,
        "counterparty_type": counterparty_type,
    }

    url = f"{BUNQ_API_BASE}/payments"
    data = await make_bunq_request(url, method="post", payload=payment_data)

    if not data:
        return "Payment creation failed"

    return format_payment(data)


@mcp.tool()
async def create_request_inquiry(
    amount: str,
    description: str,
    counterparty_alias: str,
    counterparty_type: str = "EMAIL",
) -> str:
    """Create a bunq request inquiry

    Args:
        amount: Payment amount (e.g., "10.00")
        description: Payment description
        counterparty_alias: Recipient email, IBAN, or phone number
        counterparty_type: Type of alias - "EMAIL", "IBAN", or "PHONE_NUMBER" (default: EMAIL)
    """
    logger.info(
        "Tool called: create_request_inquiry amount=%s counterparty=%s",
        amount,
        counterparty_alias,
    )
    request_inq_data = {
        "amount": amount,
        "description": description,
        "counterparty_alias": counterparty_alias,
        "counterparty_type": counterparty_type,
    }

    url = f"{BUNQ_API_BASE}/request_inqs"
    data = await make_bunq_request(url, method="post", payload=request_inq_data)

    if not data:
        return "Payment creation failed"

    return format_request_inquiry(data)


def format_request_inquiry(inquiry: dict) -> str:
    """Format a request inquiry into readable string"""

    counterparty = (
        inquiry.get("_counterparty_alias", {})
        .get("label_monetary_account", {})
        .get("_display_name", "Unknown")
    )
    amount = inquiry.get("_amount_inquired", {})

    return f"""
Request Inquiry Details:
  ID: {inquiry.get("_id_", "Unknown")}
  Created: {inquiry.get("_created", "Unknown")}
  Amount: {amount.get("_value", "0")} {amount.get("_currency", "EUR")}
  Status: {inquiry.get("_status", "Unknown")}
  Description: {inquiry.get("_description", "No description available")}
  Counterparty: {counterparty}
"""


@mcp.tool()
async def send_payment_by_name(
    recipient_name: str, amount: str, description: str = ""
) -> str:
    """Send payment to a contact by their name from payment history

    Args:
        recipient_name: Name of recipient (e.g., "Sugar Daddy")
        amount: Amount in EUR (e.g., "10.00")
        description: Optional description
    """
    logger.info(
        "Tool called: send_payment_by_name recipient=%s amount=%s",
        recipient_name,
        amount,
    )
    # Get payments to find recipient
    url = f"{BUNQ_API_BASE}/payments"
    payments = await make_bunq_request(url)

    if not payments:
        return "No payment history found"

    # Find recipient's IBAN
    recipient_iban = None
    for payment in payments:
        counterparty = payment.get("_counterparty_alias", {}).get(
            "label_monetary_account", {}
        )
        name = counterparty.get("_display_name", "")
        if recipient_name.lower() in name.lower():
            recipient_iban = counterparty.get("_iban")
            break

    if not recipient_iban:
        logger.warning("Recipient '%s' not found in payment history", recipient_name)
        return f"Recipient '{recipient_name}' not found in history"

    # Now create payment
    return await create_payment(
        amount, description or f"Payment to {recipient_name}", recipient_iban, "IBAN"
    )


def get_user_alias(recipient_name: str, payments):
    recipient_iban = None
    for payment in payments:
        counterparty = payment.get("_counterparty_alias", {}).get(
            "label_monetary_account", {}
        )
        name = counterparty.get("_display_name", "")
        if recipient_name.lower() in name.lower():
            recipient_iban = counterparty.get("_iban")
            break

    return recipient_iban


@mcp.tool()
async def send_request_inq_by_name(
    recipient_name: str, amount: str, description: str = ""
) -> str:
    """Send request inquary to a contact by their name from payment history

    Args:
        recipient_name: Name of recipient (e.g., "Sugar Daddy")
        amount: Amount in EUR (e.g., "10.00")
        description: Optional description
    """
    logger.info(
        "Tool called: send_request_inq_by_name recipient=%s amount=%s",
        recipient_name,
        amount,
    )
    # Get payments to find recipient
    url = f"{BUNQ_API_BASE}/payments"
    payments = await make_bunq_request(url)

    if not payments:
        return "No payment history found"

    # Find recipient's IBAN
    recipient_iban = get_user_alias(recipient_name, payments)

    if not recipient_iban:
        return f"Recipient '{recipient_name}' not found in history"

    # Now create payment
    return await create_request_inquiry(
        amount,
        description or f"Payment request to {recipient_name}",
        recipient_iban,
        "IBAN",
    )


@mcp.tool()
async def get_user_detail() -> str:
    """Get user details like name, etc"""
    logger.info("Tool called: get_user_detail")
    url = f"{BUNQ_API_BASE}/users/me"
    data = await make_bunq_request(url)

    return format_user(data)


def format_user(user: dict) -> str:
    """Format a user into a readable string with important attributes only"""

    return f"""
User Details:
  ID: {user.get("_id_", "Unknown")}
  Name: {user.get("_display_name", "Unknown")}
  Email: {next((alias.get("_value") for alias in user.get("_alias", []) if alias.get("_type_") == "EMAIL"), "N/A")}
  Phone: {next((alias.get("_value") for alias in user.get("_alias", []) if alias.get("_type_") == "PHONE_NUMBER"), "N/A")}
  Status: {user.get("_status", "Unknown")}
  Country: {user.get("_country", "Unknown")}
  Created: {user.get("_created", "Unknown")}
"""


@mcp.tool()
async def split_receipt_by_names(
    recipient_names: list[str], recepient_splits: list[UserSplit], receipt: Receipt
):
    """
    Split a receipt among multiple users and create payment requests via bunq.

    This tool takes a receipt and divides it among specified recipients, then initiates
    payment requests to each person's bunq account based on their allocated share. Perfect
    for splitting restaurant bills, group purchases, or shared expenses.

    Args:
        recipient_names (list[str]):
            List of recipient names/usernames to split the receipt with.
            Each name must correspond to a valid bunq user account (will be resolved to their IBAN).
            Example: ["alice", "bob", "charlie"]

        recepient_splits (List[UserSplit]):
            List of UserSplit objects defining each recipient's share of the receipt.
            Each UserSplit contains:
              - name: str — The recipient's username (must match a name in recipient_names)
              - total: float — The amount this recipient owes (must be > 0)
              - currency: str — ISO 4217 currency code (default: "EUR")
              - description: str — Human-readable description of items in this split
                (e.g., "pasta_bolognese x2, white_wine x1")

            Example:
                [
                    UserSplit(
                        name="alice",
                        total=31.0,
                        currency="EUR",
                        description="pasta_bolognese x2, white_wine x0.5"
                    ),
                    UserSplit(
                        name="bob",
                        total=31.0,
                        currency="EUR",
                        description="pasta_bolognese x0, white_wine x0.5"
                    )
                ]

        receipt (Receipt):
            The original receipt object containing all items, quantities, and totals.
            Used for context/reference; the actual splits are defined in recepient_splits.
            Contains:
              - currency: str — Currency code (ISO 4217, default: "EUR")
              - items: List[ReceiptItem] — List of items with name, quantity, and price

            Example receipt:
                Receipt(
                    currency="EUR",
                    items=[
                        ReceiptItem(name="pasta_bolognese", quantity=2, total=24),
                        ReceiptItem(name="white_wine", quantity=1, total=38)
                    ]
                )

    Returns:
        str:
            A newline-separated summary of payment requests created. Each line contains
            the result of a payment creation attempt.

            On success, typically returns confirmation details for each payment.
            On failure, returns error message(s) indicating:
              - Missing IBAN for a recipient (user not found in bunq)
              - Missing split information for a recipient
              - Payment creation failure (insufficient funds, API error, etc.)

    Raises:
        No exceptions are raised; errors are returned as strings in the response.

    Examples:
        >>> recipient_names = ["alice", "bob"]
        >>> splits = [
        ...     UserSplit(name="alice", total=31.0, currency="EUR", description="pasta x2"),
        ...     UserSplit(name="bob", total=31.0, currency="EUR", description="wine x1")
        ... ]
        >>> receipt = Receipt(
        ...     currency="EUR",
        ...     items=[
        ...         ReceiptItem(name="pasta_bolognese", quantity=2, total=24),
        ...         ReceiptItem(name="white_wine", quantity=1, total=38)
        ...     ]
        ... )
        >>> await split_receipt_by_names(recipient_names, splits, receipt)
        # Returns payment confirmation for alice and bob

    Notes:
        - All recipients in recipient_names must be registered bunq users with valid IBANs.
        - The sum of all splits does not need to equal the receipt total (allows for
          tip splitting, rounding, or partial splits).
        - Currency conversion is not currently supported; all splits should use the same
          currency as specified in the receipt.
        - Payments are created asynchronously; check the returned responses for success/failure.
        - The description field in each UserSplit is sent to the recipient as the payment memo.
    """

    # Get mapping of recipient IBANs
    url = f"{BUNQ_API_BASE}/payments"
    payments = await make_bunq_request(url)
    recipient_ibans = {name: get_user_alias(name, payments) for name in recipient_names}

    # Get mapping of recipient splits for quick lookup
    recipient_splits_map = {split["name"]: split for split in recepient_splits}

    # Generate request payments
    req_inqs = []
    for name, iban in recipient_ibans.items():
        # Early exit if user IBAN is not found
        if iban is None:
            return f"Failed to find IBAN for {name}"

        # Get split of recipient
        split = recipient_splits_map.get(name)

        # Early exist if split is not found
        if split is None:
            return f"No split found for {name}"

        # TODO handle different currencies
        req_inqs.append(
            {
                "amount": split["total"],
                "description": split["description"],
                "iban": iban,
            }
        )

    # Create requests
    responses = []
    for req in req_inqs:
        amount = req["amount"]
        desc = req["description"]
        iban = req["iban"]
        resp = await create_payment(str(amount), desc, iban, "IBAN")
        responses.append(resp)

    return "\n".join(responses)


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
