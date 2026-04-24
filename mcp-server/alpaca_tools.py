import logging
import os
from typing import Any

import httpx

import investment_log

logger = logging.getLogger(__name__)

ALPACA_TRADE_URL = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA_URL = "https://data.alpaca.markets/v2"


def _headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": os.getenv("ALPACA_KEY", ""),
        "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET", ""),
    }


async def _request(
    url: str, method: str = "get", payload: dict | None = None
) -> Any | None:
    async with httpx.AsyncClient() as client:
        try:
            kwargs = {"headers": _headers(), "timeout": 30.0}
            if method == "get":
                response = await client.get(url, **kwargs)
            elif method == "post":
                response = await client.post(url, json=payload, **kwargs)
            elif method == "delete":
                response = await client.delete(url, **kwargs)
            else:
                return None

            if response.is_error:
                logger.error(
                    "Alpaca %s %s failed %d: %s",
                    method.upper(),
                    url,
                    response.status_code,
                    response.text,
                )
                return None
            return response.json()
        except Exception as e:
            logger.error("Alpaca request to %s failed: %s", url, e)
            return None


def _fmt_account(a: dict) -> str:
    return (
        f"Alpaca Account\n"
        f"  Status:          {a.get('status', 'unknown')}\n"
        f"  Cash:            ${a.get('cash', '0')}\n"
        f"  Buying Power:    ${a.get('buying_power', '0')}\n"
        f"  Portfolio Value: ${a.get('portfolio_value', '0')}\n"
        f"  Equity:          ${a.get('equity', '0')}\n"
    )


def _fmt_position(p: dict) -> str:
    plpc = float(p.get("unrealized_plpc", 0)) * 100
    return (
        f"Position: {p.get('symbol')}\n"
        f"  Qty:            {p.get('qty')} shares\n"
        f"  Market Value:   ${p.get('market_value')}\n"
        f"  Avg Entry:      ${p.get('avg_entry_price')}\n"
        f"  Unrealized P&L: ${p.get('unrealized_pl')} ({plpc:.2f}%)\n"
    )


def _fmt_order(o: dict) -> str:
    return (
        f"Order: {o.get('symbol')} {str(o.get('side', '')).upper()}\n"
        f"  Status:           {o.get('status')}\n"
        f"  Notional:         ${o.get('notional', 'N/A')}\n"
        f"  Qty:              {o.get('qty', 'N/A')} shares\n"
        f"  Filled Qty:       {o.get('filled_qty', '0')}\n"
        f"  Filled Avg Price: ${o.get('filled_avg_price', 'N/A')}\n"
        f"  Submitted:        {o.get('submitted_at')}\n"
    )


def _fmt_history_row(r: dict) -> str:
    notional = f"${r['notional']}" if r["notional"] else None
    qty = f"{r['qty']} shares" if r["qty"] else None
    size = notional or qty or "N/A"
    limit = f" @ limit ${r['limit_price']}" if r["limit_price"] else ""
    return (
        f"[{r['timestamp']}] {r['symbol']} {r['side'].upper()}"
        f" {r['order_type']}{limit} — {size}\n"
        f"  Status: {r['alpaca_status']}  "
        f"Filled: {r['filled_qty'] or '0'} @ ${r['filled_avg_price'] or 'N/A'}\n"
        f"  Note: {r['note'] or '—'}\n"
    )


def register(mcp) -> None:
    """Register all Alpaca tools on the given FastMCP instance."""

    @mcp.tool()
    async def get_alpaca_account() -> str:
        """Get Alpaca account details: cash balance, buying power, and portfolio equity."""
        logger.info("Tool called: get_alpaca_account")
        data = await _request(f"{ALPACA_TRADE_URL}/account")
        if not data:
            return "Failed to fetch Alpaca account"
        return _fmt_account(data)

    @mcp.tool()
    async def get_stock_quote(symbol: str) -> str:
        """Get the latest trade price for a stock symbol.

        Args:
            symbol: Stock ticker (e.g., "MSFT", "AAPL", "TSLA")
        """
        logger.info("Tool called: get_stock_quote symbol=%s", symbol)
        url = f"{ALPACA_DATA_URL}/stocks/{symbol.upper()}/trades/latest"
        data = await _request(url)
        if not data:
            return f"Failed to fetch quote for {symbol.upper()}"
        trade = data.get("trade", {})
        return f"{symbol.upper()} latest trade: ${trade.get('p', 'N/A')} at {trade.get('t', 'N/A')}"

    @mcp.tool()
    async def place_stock_order(
        symbol: str,
        side: str,
        notional: float | None = None,
        qty: float | None = None,
        order_type: str = "market",
        limit_price: float | None = None,
        note: str | None = None,
    ) -> str:
        """Buy or sell a stock by dollar amount or share count.

        Args:
            symbol: Stock ticker (e.g., "MSFT")
            side: "buy" or "sell"
            notional: Dollar amount to trade (e.g., 20.0 for $20). Supports fractional shares.
            qty: Number of shares (e.g., 1.5). Use instead of notional for share-based orders.
            order_type: "market" (default) or "limit". Limit orders require
                limit_price and qty (notional is not supported).
            limit_price: Target price for limit orders (e.g., 400.0).
                Fills at this price or better. Persists until filled or cancelled.
            note: Brief reason for this trade (e.g., "round-up from bunq payment").
                Stored in the investment history log for transparency.
        """
        logger.info(
            "Tool called: place_stock_order symbol=%s side=%s "
            "notional=%s qty=%s type=%s limit=%s",
            symbol,
            side,
            notional,
            qty,
            order_type,
            limit_price,
        )
        if side not in ("buy", "sell"):
            return "side must be 'buy' or 'sell'"
        if order_type not in ("market", "limit"):
            return "order_type must be 'market' or 'limit'"
        if notional is None and qty is None:
            return "Provide either notional (dollar amount) or qty (share count)"
        if order_type == "limit" and limit_price is None:
            return "limit_price is required for limit orders"
        if order_type == "limit" and notional is not None:
            return "Limit orders require qty, not notional"

        # Limit orders persist until filled or cancelled; market orders expire end-of-day
        time_in_force = "gtc" if order_type == "limit" else "day"

        payload: dict = {
            "symbol": symbol.upper(),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price is not None:
            payload["limit_price"] = str(round(limit_price, 2))
        if notional is not None:
            payload["notional"] = str(round(notional, 2))
        else:
            payload["qty"] = str(qty)

        data = await _request(
            f"{ALPACA_TRADE_URL}/orders", method="post", payload=payload
        )
        if not data:
            return f"Failed to place {side} order for {symbol.upper()}"

        investment_log.log_order(
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            notional=notional,
            qty=qty,
            limit_price=limit_price,
            note=note,
            alpaca_order_id=data.get("id"),
            alpaca_status=data.get("status"),
            filled_qty=data.get("filled_qty"),
            filled_avg_price=data.get("filled_avg_price"),
        )
        return _fmt_order(data)

    @mcp.tool()
    async def get_alpaca_positions() -> str:
        """Get all current open Alpaca stock positions."""
        logger.info("Tool called: get_alpaca_positions")
        data = await _request(f"{ALPACA_TRADE_URL}/positions")
        if data is None:
            return "Failed to fetch positions"
        if not data:
            return "No open positions"
        return "\n---\n".join(_fmt_position(p) for p in data)

    @mcp.tool()
    async def get_alpaca_orders() -> str:
        """Get the 10 most recent Alpaca orders (all statuses)."""
        logger.info("Tool called: get_alpaca_orders")
        data = await _request(f"{ALPACA_TRADE_URL}/orders?limit=10&status=all")
        if data is None:
            return "Failed to fetch orders"
        if not data:
            return "No recent orders"
        return "\n---\n".join(_fmt_order(o) for o in data)

    @mcp.tool()
    async def get_investment_history() -> str:
        """Get the last 20 agent-placed investment orders with timestamps and notes."""
        logger.info("Tool called: get_investment_history")
        rows = investment_log.get_history()
        if not rows:
            return "No investment history yet"
        return "\n---\n".join(_fmt_history_row(r) for r in rows)

    investment_log.init()
