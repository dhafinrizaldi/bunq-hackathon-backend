"""
Create sandbox Bunq users and populate the Contact address book.

Usage:
    python seed_contacts.py <owner_email>

The owner must already exist in Django (registered via /api/auth/register/).
Each entry in CONTACTS_TO_CREATE will be registered as a new sandbox user
and saved as a Contact linked to the owner.
"""

import os
import sys
import django
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from accounts.models import CustomUser, Contact  # noqa: E402 — after django.setup()

DJANGO_BASE = "http://localhost:8080"
BUNQ_SANDBOX = "https://public-api.sandbox.bunq.com/v1"

CONTACTS_TO_CREATE = [
    {"nickname": "sister",  "email": "sister@test.com",  "password": "test1234"},
    {"nickname": "mom",     "email": "mom@test.com",     "password": "test1234"},
    {"nickname": "friend",  "email": "friend@test.com",  "password": "test1234"},
]


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


def seed(owner_email: str):
    try:
        owner = CustomUser.objects.get(email=owner_email)
    except CustomUser.DoesNotExist:
        print(f"Owner '{owner_email}' not found. Register them first via /api/auth/register/.")
        sys.exit(1)

    for entry in CONTACTS_TO_CREATE:
        nickname = entry["nickname"]

        if Contact.objects.filter(user=owner, nickname=nickname).exists():
            print(f"  {nickname}: already exists, skipping")
            continue

        # Register sandbox user via Django
        resp = requests.post(
            f"{DJANGO_BASE}/api/auth/register/",
            json={"email": entry["email"], "password": entry["password"], "username": nickname},
        )
        if not resp.ok:
            if "already" in resp.text.lower() or resp.status_code == 400:
                # User exists in Django — fetch their context
                django_user = CustomUser.objects.filter(email=entry["email"]).first()
                if not django_user or not django_user.bunq_context:
                    print(f"  {nickname}: Django user exists but no bunq context, skipping")
                    continue
                ctx = django_user.bunq_context
            else:
                print(f"  {nickname}: registration failed — {resp.text[:120]}")
                continue
        else:
            ctx = resp.json().get("bunq_context") or {}
            if not ctx:
                # Fetch from DB after registration
                django_user = CustomUser.objects.get(email=entry["email"])
                ctx = django_user.bunq_context or {}

        user_id = ctx.get("session_context", {}).get("user_id")
        token = ctx.get("session_context", {}).get("token")

        if not user_id or not token:
            print(f"  {nickname}: could not extract user_id/token, skipping")
            continue

        iban = get_iban(user_id, token)
        if not iban:
            print(f"  {nickname}: could not fetch IBAN, skipping")
            continue

        Contact.objects.create(
            user=owner,
            nickname=nickname,
            display_name=ctx.get("session_context", {}).get("user_person", {}).get("display_name", nickname),
            iban=iban,
            bunq_user_id=user_id,
        )
        print(f"  {nickname}: {iban} (user_id={user_id}) ✓")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <owner_email>")
        sys.exit(1)
    seed(sys.argv[1])
