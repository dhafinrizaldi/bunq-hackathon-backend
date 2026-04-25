"""
Seed script — run once after `just setup` and `just all`.

Usage:
    python seed_all.py <email> <password>

What it does:
    1. Creates the main Django user (idempotent)
    2. Creates sandbox Bunq users for contacts (sister, mom) and seeds
       the Contact model + mcp-server/contacts.json
    3. Creates a Bunq savings pocket via the bunq-api
    4. Creates a SalarySetup with example rules via the Django API

Requires all services to be running:
    just bunq-api   (port 8000)
    just django     (port 8080)
"""

import json
import os
import sys
import time

import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from accounts.models import AllocationRule, Contact, CustomUser, SalarySetup  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))

DJANGO_BASE = "http://localhost:8080"
BUNQ_API_BASE = "http://localhost:8000"
BUNQ_SANDBOX = "https://public-api.sandbox.bunq.com/v1"
MCP_SERVER_DIR = os.path.join(os.path.dirname(__file__), "../mcp-server")

CONTACTS_TO_CREATE = [
    {"nickname": "sister", "email": "sister@test.com", "password": "test1234"},
    {"nickname": "mom", "email": "mom@test.com", "password": "test1234"},
]

SALARY_DESCRIPTION = (
    "I get paid monthly by ASML. When a payment over 2000 euros arrives, "
    "send 50 euros to sister, invest 10% in SPY, and put 15% in savings."
)


# ── helpers ───────────────────────────────────────────────────────────────────

def step(msg: str):
    print(f"\n▶ {msg}")


def ok(msg: str):
    print(f"  ✓ {msg}")


def skip(msg: str):
    print(f"  – {msg} (skipped — already exists)")


def fail(msg: str):
    print(f"  ✗ {msg}")


def get_iban(user_id: int, session_token: str) -> str | None:
    resp = requests.get(
        f"{BUNQ_SANDBOX}/user/{user_id}/monetary-account-bank",
        headers={"User-Agent": "seed-script", "X-Bunq-Client-Authentication": session_token},
    )
    if not resp.ok:
        return None
    for item in resp.json().get("Response", []):
        acc = item.get("MonetaryAccountBank", {})
        for alias in acc.get("alias", []):
            if alias.get("type") == "IBAN":
                return alias["value"]
    return None


def write_contacts_json(contacts: list[dict]):
    path = os.path.join(MCP_SERVER_DIR, "contacts.json")
    data = {
        c["nickname"]: {"display_name": c["display_name"], "iban": c["iban"], "bunq_user_id": c["bunq_user_id"]}
        for c in contacts
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    ok(f"Wrote {path}")


# ── steps ─────────────────────────────────────────────────────────────────────

def create_main_user(email: str, password: str) -> CustomUser:
    step(f"Creating main Django user: {email}")
    user = CustomUser.objects.filter(email=email).first()
    if user:
        skip(email)
        return user

    resp = requests.post(
        f"{DJANGO_BASE}/api/auth/register/",
        json={"email": email, "password": password, "username": email.split("@")[0]},
    )
    if not resp.ok:
        fail(f"Registration failed: {resp.text[:200]}")
        sys.exit(1)

    user = CustomUser.objects.get(email=email)
    ok(f"Created user {email}")
    return user


def seed_contacts(owner: CustomUser) -> list[dict]:
    step("Seeding contacts")
    seeded = []

    for entry in CONTACTS_TO_CREATE:
        nickname = entry["nickname"]

        if Contact.objects.filter(user=owner, nickname=nickname).exists():
            contact = Contact.objects.get(user=owner, nickname=nickname)
            skip(f"{nickname} ({contact.iban})")
            seeded.append({
                "nickname": nickname,
                "display_name": contact.display_name,
                "iban": contact.iban,
                "bunq_user_id": contact.bunq_user_id,
            })
            continue

        # Register sandbox user via Django
        resp = requests.post(
            f"{DJANGO_BASE}/api/auth/register/",
            json={"email": entry["email"], "password": entry["password"], "username": nickname},
        )

        if resp.ok:
            django_user = CustomUser.objects.get(email=entry["email"])
        elif resp.status_code == 400:
            django_user = CustomUser.objects.filter(email=entry["email"]).first()
            if not django_user:
                fail(f"{nickname}: registration failed and user not found")
                continue
        else:
            fail(f"{nickname}: {resp.text[:120]}")
            continue

        ctx = django_user.bunq_context or {}
        user_id = ctx.get("session_context", {}).get("user_id")
        token = ctx.get("session_context", {}).get("token")
        display_name = ctx.get("session_context", {}).get("user_person", {}).get("display_name", nickname)

        if not user_id or not token:
            fail(f"{nickname}: missing Bunq context")
            continue

        iban = get_iban(user_id, token)
        if not iban:
            fail(f"{nickname}: could not fetch IBAN")
            continue

        Contact.objects.create(
            user=owner,
            nickname=nickname,
            display_name=display_name,
            iban=iban,
            bunq_user_id=user_id,
        )
        ok(f"{nickname}: {iban}")
        seeded.append({"nickname": nickname, "display_name": display_name, "iban": iban, "bunq_user_id": user_id})
        time.sleep(1)

    return seeded


def create_savings_pocket() -> str | None:
    step("Creating Bunq savings pocket")

    # Check if one already exists
    resp = requests.get(f"{BUNQ_API_BASE}/monetary-accounts/")
    if resp.ok:
        for acc in resp.json():
            inner = acc.get("_MonetaryAccountBank") or {}
            if "savings" in (inner.get("_description") or "").lower():
                aliases = inner.get("_alias") or []
                iban = next((a.get("_value") for a in aliases if a.get("_type_") == "IBAN"), None)
                if iban:
                    skip(f"Savings Pocket already exists ({iban})")
                    return iban

    resp = requests.post(
        f"{BUNQ_API_BASE}/monetary-accounts/",
        json={"description": "Savings Pocket", "currency": "EUR"},
    )
    if not resp.ok:
        fail(f"Could not create savings pocket: {resp.text[:200]}")
        return None

    # Fetch IBAN of newly created account
    time.sleep(1)
    resp = requests.get(f"{BUNQ_API_BASE}/monetary-accounts/")
    if resp.ok:
        for acc in resp.json():
            inner = acc.get("_MonetaryAccountBank") or {}
            if "savings" in (inner.get("_description") or "").lower():
                aliases = inner.get("_alias") or []
                iban = next((a.get("_value") for a in aliases if a.get("_type_") == "IBAN"), None)
                if iban:
                    ok(f"Created Savings Pocket ({iban})")
                    return iban

    fail("Savings pocket created but could not fetch IBAN")
    return None


def create_salary_setup(owner: CustomUser, contacts: list[dict]):
    step("Creating salary setup")

    if SalarySetup.objects.filter(user=owner).exists():
        skip("SalarySetup already exists")
        return

    # Login to get session cookie
    session = requests.Session()
    resp = session.post(
        f"{DJANGO_BASE}/api/auth/login/",
        json={"email": owner.email, "password": sys.argv[2]},
    )
    if not resp.ok:
        fail(f"Login failed: {resp.text[:200]}")
        return

    resp = session.post(
        f"{DJANGO_BASE}/api/salary-setup/",
        json={"description": SALARY_DESCRIPTION},
    )
    if resp.ok:
        data = resp.json()
        ok(f"Trigger: '{data.get('trigger_keyword')}' > €{data.get('trigger_min_amount')}")
        for rule in data.get("rules", []):
            ok(f"  Rule: {rule['rule_type']} {rule['amount_type']}={rule['amount']} — {rule['description']}")
    else:
        fail(f"Salary setup failed: {resp.text[:300]}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <email> <password>")
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]

    print("=" * 50)
    print("Seeding hackathon data")
    print("=" * 50)

    owner = create_main_user(email, password)
    contacts = seed_contacts(owner)
    write_contacts_json(contacts)
    create_savings_pocket()
    create_salary_setup(owner, contacts)

    print("\n" + "=" * 50)
    print("✓ Seed complete!")
    print(f"  Test allocation: curl -s -X POST http://localhost:8080/api/execute-allocation/")
    print(f"    -H 'Content-Type: application/json'")
    print(f"    -d '{{\"amount\": 4200.00, \"description\": \"Salaris ASML\"}}'")
    print("=" * 50)


if __name__ == "__main__":
    main()
