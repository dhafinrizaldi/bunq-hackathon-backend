import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "investments.db"

_CREATE = """
CREATE TABLE IF NOT EXISTS investment_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    symbol           TEXT    NOT NULL,
    side             TEXT    NOT NULL,
    order_type       TEXT    NOT NULL,
    notional         REAL,
    qty              REAL,
    limit_price      REAL,
    note             TEXT,
    alpaca_order_id  TEXT,
    alpaca_status    TEXT,
    filled_qty       TEXT,
    filled_avg_price TEXT
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _connect() as conn:
        conn.execute(_CREATE)


def log_order(
    *,
    symbol: str,
    side: str,
    order_type: str,
    notional: float | None,
    qty: float | None,
    limit_price: float | None,
    note: str | None,
    alpaca_order_id: str | None,
    alpaca_status: str | None,
    filled_qty: str | None,
    filled_avg_price: str | None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO investment_log
                (timestamp, symbol, side, order_type, notional, qty,
                 limit_price, note, alpaca_order_id, alpaca_status,
                 filled_qty, filled_avg_price)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                symbol,
                side,
                order_type,
                notional,
                qty,
                limit_price,
                note,
                alpaca_order_id,
                alpaca_status,
                filled_qty,
                filled_avg_price,
            ),
        )


def get_history(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM investment_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
