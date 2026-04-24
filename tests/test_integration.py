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
