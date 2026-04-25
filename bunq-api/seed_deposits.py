"""
One-time script to seed the bunq sandbox account with the deposits from mockdata/deposits.json.
Each deposit becomes a request inquiry to the sandbox sugar daddy, which auto-approves them.

Run from the bunq-api directory:
    uv run python seed_deposits.py
"""

import json

from bunq.sdk.context.api_context import ApiContext
from bunq.sdk.context.bunq_context import BunqContext
from bunq.sdk.model.generated.endpoint import RequestInquiryApiObject
from bunq.sdk.model.generated.object_ import AmountObject, PointerObject

SUGAR_DADDY_EMAIL = "sugardaddy@bunq.com"

api_context = ApiContext.restore("bunq_api_context.conf")
BunqContext.load_api_context(api_context)

with open("mockdata/deposits.json") as f:
    deposits = json.load(f)

with open("mockdata/payments.json") as f:
    payments = json.load(f)

total_deposits = sum(float(d["_amount"]["_value"]) for d in deposits)
total_payments = sum(abs(float(p["_amount"]["_value"])) for p in payments)
net = total_deposits - total_payments

print("Mock data summary:")
print(f"Deposits: +€{total_deposits:,.2f}")
print(f"Payments: -€{total_payments:,.2f}")
print(f"Net: €{net:,.2f}")

CHUNK_SIZE = 500.0
request_count = 0

for deposit in deposits:
    total = float(deposit["_amount"]["_value"])
    currency = deposit["_amount"]["_currency"]
    description = deposit["_description"]

    # Split into <=500 chunks — sugar daddy rejects larger single requests
    remaining = total
    chunk_num = 1
    chunks = -(-total // CHUNK_SIZE)  # ceiling division
    while remaining > 0:
        chunk = min(remaining, CHUNK_SIZE)
        label = f"{description} ({chunk_num}/{int(chunks)})" if chunks > 1 else description
        print(f"  Requesting €{chunk:.2f} — {label}")
        RequestInquiryApiObject.create(
            amount_inquired=AmountObject(f"{chunk:.2f}", currency),
            counterparty_alias=PointerObject("EMAIL", SUGAR_DADDY_EMAIL, "Sugar Daddy"),
            description=label,
            allow_bunqme=False,
        )
        remaining -= chunk
        chunk_num += 1
        request_count += 1

print(f"\nDone — {len(deposits)} deposits seeded in {request_count} requests.")
