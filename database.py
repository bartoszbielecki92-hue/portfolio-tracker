import os
import psycopg2
import psycopg2.extras
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def ping():
    """Keep Supabase project alive — call on every app start."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS assets (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL CHECK(category IN ('stock', 'etf', 'bond', 'crypto')),
                    ticker TEXT NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'USD',
                    price_currency TEXT
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    buy_price REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS bonds (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    face_value REAL NOT NULL,
                    coupon_rate REAL NOT NULL,
                    buy_date TEXT NOT NULL,
                    maturity_date TEXT NOT NULL,
                    yield_to_maturity REAL
                );
            """)
        conn.commit()


def _rows(cur) -> list:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def add_asset(name: str, category: str, ticker: str, currency: str, price_currency: Optional[str] = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO assets (name, category, ticker, currency, price_currency) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (name, category, ticker.upper(), currency.upper(), price_currency.upper() if price_currency else None),
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id


def add_transaction(asset_id: int, date: str, quantity: float, buy_price: float):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO transactions (asset_id, date, quantity, buy_price) VALUES (%s, %s, %s, %s)",
                (asset_id, date, quantity, buy_price),
            )
        conn.commit()


def get_assets():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM assets ORDER BY category, name")
            return _rows(cur)


def get_transactions(asset_id: Optional[int] = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if asset_id:
                cur.execute(
                    "SELECT t.*, a.name as asset_name, a.ticker FROM transactions t JOIN assets a ON a.id = t.asset_id WHERE t.asset_id = %s ORDER BY t.date DESC",
                    (asset_id,),
                )
            else:
                cur.execute(
                    "SELECT t.*, a.name as asset_name, a.ticker FROM transactions t JOIN assets a ON a.id = t.asset_id ORDER BY t.date DESC"
                )
            return _rows(cur)


def add_bond(name: str, face_value: float, coupon_rate: float, buy_date: str, maturity_date: str, ytm: Optional[float]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bonds (name, face_value, coupon_rate, buy_date, maturity_date, yield_to_maturity) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, face_value, coupon_rate, buy_date, maturity_date, ytm),
            )
        conn.commit()


def get_bonds():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM bonds ORDER BY maturity_date")
            return _rows(cur)


def update_asset(asset_id: int, name: str, category: str, ticker: str, currency: str, price_currency: Optional[str] = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE assets SET name=%s, category=%s, ticker=%s, currency=%s, price_currency=%s WHERE id=%s",
                (name, category, ticker.upper(), currency.upper(), price_currency.upper() if price_currency else None, asset_id),
            )
        conn.commit()


def delete_asset(asset_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM assets WHERE id=%s", (asset_id,))
        conn.commit()


def update_transaction(transaction_id: int, date: str, quantity: float, buy_price: float):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE transactions SET date=%s, quantity=%s, buy_price=%s WHERE id=%s",
                (date, quantity, buy_price, transaction_id),
            )
        conn.commit()


def delete_transaction(transaction_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM transactions WHERE id=%s", (transaction_id,))
        conn.commit()


def update_bond(bond_id: int, name: str, face_value: float, coupon_rate: float, buy_date: str, maturity_date: str, ytm: Optional[float]):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE bonds SET name=%s, face_value=%s, coupon_rate=%s, buy_date=%s, maturity_date=%s, yield_to_maturity=%s WHERE id=%s",
                (name, face_value, coupon_rate, buy_date, maturity_date, ytm, bond_id),
            )
        conn.commit()


def delete_bond(bond_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bonds WHERE id=%s", (bond_id,))
        conn.commit()
