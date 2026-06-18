import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "portfolio.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('stock', 'etf', 'bond', 'crypto')),
                ticker TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                price_currency TEXT
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                quantity REAL NOT NULL,
                buy_price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bonds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                face_value REAL NOT NULL,
                coupon_rate REAL NOT NULL,
                buy_date TEXT NOT NULL,
                maturity_date TEXT NOT NULL,
                yield_to_maturity REAL
            );
        """)
        # migrate: add price_currency if column doesn't exist yet
        cols = [r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()]
        if "price_currency" not in cols:
            conn.execute("ALTER TABLE assets ADD COLUMN price_currency TEXT")


def add_asset(name: str, category: str, ticker: str, currency: str, price_currency: Optional[str] = None) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO assets (name, category, ticker, currency, price_currency) VALUES (?, ?, ?, ?, ?)",
            (name, category, ticker.upper(), currency.upper(), price_currency.upper() if price_currency else None),
        )
        return cur.lastrowid


def add_transaction(asset_id: int, date: str, quantity: float, buy_price: float):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO transactions (asset_id, date, quantity, buy_price) VALUES (?, ?, ?, ?)",
            (asset_id, date, quantity, buy_price),
        )


def get_assets():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM assets ORDER BY category, name").fetchall()


def get_transactions(asset_id: Optional[int] = None):
    with get_connection() as conn:
        if asset_id:
            return conn.execute(
                "SELECT t.*, a.name as asset_name, a.ticker FROM transactions t JOIN assets a ON a.id = t.asset_id WHERE t.asset_id = ? ORDER BY t.date DESC",
                (asset_id,),
            ).fetchall()
        return conn.execute(
            "SELECT t.*, a.name as asset_name, a.ticker FROM transactions t JOIN assets a ON a.id = t.asset_id ORDER BY t.date DESC"
        ).fetchall()


def add_bond(name: str, face_value: float, coupon_rate: float, buy_date: str, maturity_date: str, ytm: Optional[float]):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO bonds (name, face_value, coupon_rate, buy_date, maturity_date, yield_to_maturity) VALUES (?, ?, ?, ?, ?, ?)",
            (name, face_value, coupon_rate, buy_date, maturity_date, ytm),
        )


def get_bonds():
    with get_connection() as conn:
        return conn.execute("SELECT * FROM bonds ORDER BY maturity_date").fetchall()


def update_asset(asset_id: int, name: str, category: str, ticker: str, currency: str, price_currency: Optional[str] = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE assets SET name=?, category=?, ticker=?, currency=?, price_currency=? WHERE id=?",
            (name, category, ticker.upper(), currency.upper(), price_currency.upper() if price_currency else None, asset_id),
        )


def delete_asset(asset_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM assets WHERE id=?", (asset_id,))


def update_transaction(transaction_id: int, date: str, quantity: float, buy_price: float):
    with get_connection() as conn:
        conn.execute(
            "UPDATE transactions SET date=?, quantity=?, buy_price=? WHERE id=?",
            (date, quantity, buy_price, transaction_id),
        )


def delete_transaction(transaction_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))


def update_bond(bond_id: int, name: str, face_value: float, coupon_rate: float, buy_date: str, maturity_date: str, ytm: Optional[float]):
    with get_connection() as conn:
        conn.execute(
            "UPDATE bonds SET name=?, face_value=?, coupon_rate=?, buy_date=?, maturity_date=?, yield_to_maturity=? WHERE id=?",
            (name, face_value, coupon_rate, buy_date, maturity_date, ytm, bond_id),
        )


def delete_bond(bond_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM bonds WHERE id=?", (bond_id,))
