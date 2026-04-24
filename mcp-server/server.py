import logging
import re
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


# Albert Heijn savings tool

AH_BASE = "https://api.ah.nl"
AH_SKIP_KEYWORDS = {
    "totaal", "subtotaal", "btw", "kassabon", "datum", "filiaal", "nummer", "pinpas",
    "betaald", "maestro", "statiegeld", "korting", "terminal", "periode", "transactie",
    "merchant", "omschrijving", "bedrag", "contactloze",
}


def _parse_receipt_lines(receipt_text: str) -> list[dict]:
    """Extract item name + price from receipt text using a trailing-price pattern."""
    pattern = re.compile(r"^(?:\d+x\s+)?(.+?)\s+(\d+[.,]\d{2})\s*$", re.MULTILINE)
    items = []
    for match in pattern.finditer(receipt_text):
        name = match.group(1).strip()
        if any(kw in name.lower() for kw in AH_SKIP_KEYWORDS):
            continue
        try:
            price = float(match.group(2).replace(",", "."))
        except ValueError:
            continue
        # Build a 2-3 word search term, dropping size tokens like "1L", "500g"
        words = [w for w in name.split() if not re.match(r"^\d", w) and not re.match(r"^\d*[a-z]+$", w, re.I)]
        search_term = " ".join(words[:3]) or name.split()[0]
        items.append({"name": name, "price_paid": price, "search_term": search_term})
    return items


async def _get_ah_token() -> str | None:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AH_BASE}/mobile-auth/v1/auth/token/anonymous",
                json={"clientId": "appie"},
                headers={"User-Agent": "Appie/8.22.3"},
                timeout=10.0,
            )
            return resp.json().get("access_token") if not resp.is_error else None
        except Exception:
            return None


async def _search_ah_products(query: str, token: str, size: int = 15) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Appie/8.22.3",
        "x-application": "AHWEBSHOP",
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{AH_BASE}/mobile-services/product/search/v2",
                params={"query": query, "sortOn": "RELEVANCE", "size": size, "page": 0},
                headers=headers,
                timeout=10.0,
            )
            return resp.json().get("products", []) if not resp.is_error else []
        except Exception:
            return []


def _pick_ah_product(products: list) -> dict | None:
    """Prefer a non-bundle with a known price; fall back to any priced product."""
    for p in products:
        if not p.get("isVirtualBundle") and p.get("currentPrice") is not None:
            return p
    for p in products:
        if p.get("currentPrice") is not None:
            return p
    return None


@mcp.tool()
async def analyze_receipt_savings(receipt_text: str) -> str:
    """Compare all items on a grocery receipt against live Albert Heijn prices to find savings.

    Use this tool whenever the user shares a grocery receipt — as plain text, copy-pasted
    from a photo, or extracted via OCR — and asks about savings, price comparisons, or
    whether they could have spent less at another supermarket.

    IMPORTANT — call this tool ONCE with the full receipt. Do NOT call it per item;
    passing the complete receipt lets the tool batch all AH lookups efficiently.

    IMPORTANT — Dutch supermarket receipts use abbreviated product codes that the AH
    search engine won't understand. Before calling this tool, rewrite each item line so
    the product name is a plain readable Dutch description. Keep the price unchanged.

    Abbreviation examples:
        "HELDER CRANB/LIMOEN  0,99"  →  "Cranberry limoen drank helder  0,99"
        "JUMBO HELDER FR-BOSB  0,99" →  "Fruitige bosbes drank  0,99"
        "RODE TOMATEN CHERRY  1,06"  →  "Rode cherry tomaten  1,06"
        "DESEM BAG MEER 2ST  2,39"   →  "Desembrood bagel meerganen 2 stuks  2,39"
        "GRILLWORST KAAS STUK  2,64" →  "Grillworst met kaas  2,64"
        "HONIG TOMATENSOEP  1,62"    →  "Tomatensoep  1,62"
        "LEFFE BLOND 6 PAK  7,91"    →  "Leffe Blond bier 6-pack  7,91"

    Args:
        receipt_text (str):
            All item lines from the receipt with abbreviated product names already
            expanded to plain Dutch. One item per line, price at the end of the line.
            Omit header rows, totals, payment lines, and deposits (statiegeld).

            Example:
                Cranberry limoen drank helder  0,99
                Fruitige bosbes drank  0,99
                Rode cherry tomaten  1,06
                Heks'nkaas roomkaas origineel XL  4,15
                Desembrood bagel meergranen 2 stuks  2,39
                Grillworst met kaas  2,64
                Komkommer  0,73
                Tomatensoep  1,62
                Leffe Blond bier 6-pack  7,91
                Brie  1,49

    Returns:
        str:
            A formatted per-item breakdown showing what was paid at the original store
            versus the current Albert Heijn price, whether an AH Bonus deal is active,
            and the total potential saving across all items.

            On success, each line follows the pattern:
                • <item>: paid €X.XX | AH €Y.YY → save €Z.ZZ [bonus info if applicable]

            Items with no AH match are listed as "AH: not found".

    Notes:
        - Prices are fetched live from the AH mobile API; results reflect today's stock.
        - Active Bonus deals (e.g. "2e Halve Prijs", "10% korting") are highlighted with
          their expiry date so the user knows if a deal is time-sensitive.
        - Virtual bundle products (multi-packs) are automatically skipped in favour of
          the equivalent single-unit product for a fair price comparison.
        - The tool does not store any data; each call is fully stateless.
    """
    logger.info("Tool called: analyze_receipt_savings")

    items = _parse_receipt_lines(receipt_text)
    if not items:
        return "Could not parse any items from the receipt — make sure item lines end with a price like '1.09'."

    token = await _get_ah_token()
    if not token:
        return "Could not connect to Albert Heijn API to fetch prices."

    rows = []
    total_saving = 0.0

    for item in items:
        products = await _search_ah_products(item["search_term"], token)
        ah = _pick_ah_product(products)

        if ah is None:
            rows.append(f"• {item['name']}: €{item['price_paid']:.2f} paid — AH: not found")
            continue

        ah_price = ah.get("currentPrice")
        saving = max(0.0, item["price_paid"] - ah_price) if ah_price is not None else 0.0
        total_saving += saving

        bonus_tag = ""
        if ah.get("isBonus"):
            bonus_tag = f" [{ah.get('bonusMechanism')} until {ah.get('bonusEndDate')}]"

        saving_tag = f" → save €{saving:.2f}" if saving > 0 else ""
        ah_label = f"AH €{ah_price:.2f}" if ah_price is not None else "AH: price unavailable"
        rows.append(f"• {item['name']}: paid €{item['price_paid']:.2f} | {ah_label}{saving_tag}{bonus_tag}")

    lines = ["Albert Heijn Price Comparison", "=" * 42]
    lines += rows
    lines += ["=" * 42, f"Total potential saving: €{total_saving:.2f}"]
    return "\n".join(lines)


def main():
    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
