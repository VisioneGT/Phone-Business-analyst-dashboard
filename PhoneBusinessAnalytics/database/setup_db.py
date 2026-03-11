"""
setup_db.py
────────────
This script does two things:
  1. Creates all the tables in your SQLite database
  2. Loads the CSV files from the data/ folder into those tables

Run this FIRST before any other script.
Run with: python setup_db.py
"""

import sqlite3
import csv
import os

# ── PATHS ─────────────────────────────────────────────────────────────────────
# os.path.dirname(__file__) means "the folder this script is in" (database/)
# We go one level up (..) to reach the project root, then into data/

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../phone_business/database
ROOT_DIR = os.path.join(BASE_DIR, "..")                 # .../phone_business
DATA_DIR = os.path.join(ROOT_DIR, "data")               # .../phone_business/data
DB_PATH  = os.path.join(BASE_DIR, "phone_business.db")  # .../phone_business/database/phone_business.db


# ── STEP 1: CREATE TABLES ─────────────────────────────────────────────────────

def create_tables(conn):
    cursor = conn.cursor()

    # inventory — one row per phone you buy
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            phone_id        INTEGER PRIMARY KEY,
            brand           TEXT NOT NULL,
            model           TEXT NOT NULL,
            storage_gb      INTEGER,
            color           TEXT,
            condition       TEXT NOT NULL,
            date_purchased  TEXT NOT NULL,
            purchase_price  REAL NOT NULL,
            supplier        TEXT,
            status          TEXT DEFAULT 'in stock',
            month           INTEGER DEFAULT 1
        )
    """)

    # sales — one row per phone you sell
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            sale_id     INTEGER PRIMARY KEY,
            phone_id    INTEGER NOT NULL,
            sale_date   TEXT NOT NULL,
            sale_price  REAL NOT NULL,
            platform    TEXT,
            buyer_notes TEXT,
            FOREIGN KEY (phone_id) REFERENCES inventory(phone_id)
        )
    """)

    # costs — repairs, shipping, cleaning etc. per phone
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS costs (
            cost_id   INTEGER PRIMARY KEY,
            phone_id  INTEGER NOT NULL,
            cost_type TEXT,
            amount    REAL NOT NULL,
            date      TEXT NOT NULL,
            FOREIGN KEY (phone_id) REFERENCES inventory(phone_id)
        )
    """)

    # market_prices — weekly eBay price tracking per model
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_prices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            brand           TEXT NOT NULL,
            model           TEXT NOT NULL,
            avg_sold_price  REAL NOT NULL,
            date_checked    TEXT NOT NULL,
            source          TEXT DEFAULT 'eBay'
        )
    """)

    conn.commit()
    print("  ✅ Tables created.")


# ── STEP 2: LOAD CSVs INTO TABLES ─────────────────────────────────────────────

def load_csv(conn, table_name, csv_filename):
    """
    Reads a CSV file and inserts every row into the matching table.
    The CSV column names must match the table column names exactly.
    """
    filepath = os.path.join(DATA_DIR, csv_filename)

    if not os.path.exists(filepath):
        print(f"  ⚠️  File not found: {filepath} — skipping.")
        return

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)          # reads header row automatically
        rows = list(reader)

    if not rows:
        print(f"  ⚠️  {csv_filename} is empty — skipping.")
        return

    columns    = rows[0].keys()             # column names from the CSV header
    col_list   = ", ".join(columns)         # "col1, col2, col3"
    placeholders = ", ".join(["?"] * len(columns))  # "?, ?, ?"

    sql = f"INSERT OR IGNORE INTO {table_name} ({col_list}) VALUES ({placeholders})"

    cursor = conn.cursor()
    for row in rows:
        # Replace empty strings with None so SQLite stores them as NULL
        values = [None if v == "" else v for v in row.values()]
        cursor.execute(sql, values)

    conn.commit()
    print(f"  ✅ Loaded {len(rows)} rows into '{table_name}' from {csv_filename}")


# ── STEP 3: ADD MARKET PRICES (hardcoded — you'd update these weekly) ─────────

def insert_market_prices(conn):
    market = [
        ("Apple",   "iPhone 11",     120.00, "2024-11-01"),
        ("Apple",   "iPhone 12",     180.00, "2024-11-01"),
        ("Apple",   "iPhone 13",     270.00, "2024-11-01"),
        ("Apple",   "iPhone 13 Pro", 350.00, "2024-11-01"),
        ("Apple",   "iPhone 14",     420.00, "2024-11-01"),
        ("Samsung", "Galaxy S21",    160.00, "2024-11-01"),
        ("Samsung", "Galaxy S22",    220.00, "2024-11-01"),
        ("Samsung", "Galaxy S23",    310.00, "2024-11-01"),
        ("Samsung", "Galaxy A53",    130.00, "2024-11-01"),
    ]
    cursor = conn.cursor()
    cursor.executemany("""
        INSERT INTO market_prices (brand, model, avg_sold_price, date_checked)
        VALUES (?, ?, ?, ?)
    """, market)
    conn.commit()
    print(f"  ✅ Loaded {len(market)} rows into 'market_prices'")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n📦 Setting up database...")
    print(f"   Location: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)

    print("Step 1: Creating tables...")
    create_tables(conn)

    print("\nStep 2: Loading CSV data...")
    load_csv(conn, "inventory",     "inventory.csv")
    load_csv(conn, "sales",         "sales.csv")
    load_csv(conn, "costs",         "costs.csv")

    print("\nStep 3: Adding market prices...")
    insert_market_prices(conn)

    conn.close()

    print("\n🎉 Database ready!")
    print("   Next: run the analysis scripts or the dashboard.")
