import httpx
import pytest

BUNQ_API = "http://localhost:8000"
MCP_CLIENT = "http://localhost:8001"

# bunq-api

def test_bunq_payments_returns_data():
    """GET /payments returns a non-empty list including mock data."""
    r = httpx.get(f"{BUNQ_API}/payments/", timeout=10)
    assert r.status_code == 200
    assert len(r.json()) > 0


# bunq-api + mcp-server + Claude + Alpaca test

def test_alpaca_account_via_agent():
    """Agent can fetch and report Alpaca buying power."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": "What is my Alpaca buying power?"},
        timeout=60,
    )
    assert r.status_code == 200
    response = r.json()["response"]
    assert response
    assert "failed" not in response.lower()
    assert "unauthorized" not in response.lower()


def test_alpaca_stock_quote_via_agent():
    """Agent can look up a stock price."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": "What is the latest price of AAPL?"},
        timeout=60,
    )
    assert r.status_code == 200
    response = r.json()["response"]
    assert response
    assert "failed" not in response.lower()


def test_investment_history_via_agent():
    """Agent can retrieve the investment history log."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": "Show me my investment history."},
        timeout=60,
    )
    assert r.status_code == 200
    assert r.json()["response"]


# analyze_receipt_savings

JUMBO_RECEIPT = """
Halfvolle melk 1L  1,09
Jong belegen kaas 500g  4,39
Volkoren brood 800g  2,49
Vrije uitloop eieren 12 stuks  3,79
Griekse yoghurt naturel 500g  2,19
Ongezouten roomboter 250g  2,89
Vers sinaasappelsap 1L  2,99
"""


def test_receipt_savings_returns_response():
    """Agent calls analyze_receipt_savings and returns a non-empty response."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": f"Here's my Jumbo receipt. How much could I save at Albert Heijn?\n{JUMBO_RECEIPT}"},
        timeout=60,
    )
    assert r.status_code == 200
    assert r.json()["response"]


def test_receipt_savings_mentions_albert_heijn():
    """Response references Albert Heijn as the comparison store."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": f"Can you check AH prices for this receipt?\n{JUMBO_RECEIPT}"},
        timeout=60,
    )
    assert r.status_code == 200
    response = r.json()["response"].lower()
    assert "albert heijn" in response or "ah" in response


def test_receipt_savings_mentions_euros():
    """Response contains euro amounts."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": f"Compare my Jumbo receipt against AH prices.\n{JUMBO_RECEIPT}"},
        timeout=60,
    )
    assert r.status_code == 200
    assert "€" in r.json()["response"] or "euro" in r.json()["response"].lower()


def test_receipt_savings_no_error_keywords():
    """Response does not contain failure or error indicators."""
    r = httpx.post(
        f"{MCP_CLIENT}/query",
        json={"query": f"How much would I save at AH for this receipt?\n{JUMBO_RECEIPT}"},
        timeout=60,
    )
    assert r.status_code == 200
    response = r.json()["response"].lower()
    assert "failed" not in response
    assert "error" not in response
    assert "could not connect" not in response
