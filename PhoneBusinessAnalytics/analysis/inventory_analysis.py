"""
inventory_analysis.py
──────────────────────
Answers: what do we have in stock, what's sitting too long,
and how much money is tied up in unsold phones?

Run with: python inventory_analysis.py
"""

import sqlite3
import pandas as pd
import os
from datetime import date

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DB_PATH        = os.path.join(BASE_DIR, "../database/phone_business.db")
TODAY          = date.today().isoformat()
DEAD_STOCK_DAYS = 30    # flag phones unsold longer than this


# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_stock(conn):
    """All phones currently in stock with days sitting."""
    return pd.read_sql("""
        SELECT
            phone_id,
            brand,
            model,
            storage_gb,
            condition,
            purchase_price,
            date_purchased,
            supplier,
            CAST(JULIANDAY(?) - JULIANDAY(date_purchased) AS INTEGER) AS days_in_stock
        FROM inventory
        WHERE status = 'in stock'
        ORDER BY days_in_stock DESC
    """, conn, params=(TODAY,))


def load_all_status(conn):
    """Count of phones by status (sold / in stock / scrapped)."""
    return pd.read_sql("""
        SELECT status, COUNT(*) as count
        FROM inventory
        GROUP BY status
    """, conn)


# ── DISPLAY FUNCTIONS ─────────────────────────────────────────────────────────

def print_header(title):
    print("\n" + "=" * 58)
    print(f"  {title}")
    print("=" * 58)


def stock_overview(df, status_df):
    print_header("STOCK OVERVIEW")

    # Overall counts
    for _, row in status_df.iterrows():
        label = row["status"].upper()
        print(f"  {label:<12} : {int(row['count'])} phones")

    print()
    print(f"  Currently in stock   : {len(df)} phones")
    print(f"  Capital tied up      : ${df['purchase_price'].sum():,.2f}")
    print(f"  Avg days in stock    : {df['days_in_stock'].mean():.1f} days")


def stock_by_brand(df):
    print_header("STOCK BREAKDOWN BY BRAND")
    for brand, group in df.groupby("brand"):
        print(f"  {brand}")
        model_counts = group.groupby("model")["phone_id"].count()
        for model, count in model_counts.items():
            print(f"    └─ {model:<20} {count} phone(s)")


def dead_stock_alert(df):
    print_header(f"⚠️  DEAD STOCK  (unsold > {DEAD_STOCK_DAYS} days)")
    dead = df[df["days_in_stock"] > DEAD_STOCK_DAYS]

    if dead.empty:
        print("  None — everything is moving well! ✅")
        return

    for _, row in dead.iterrows():
        print(f"  ID {int(row['phone_id']):<4}"
              f"  {row['brand']} {row['model']:<18}"
              f"  {row['condition']:<20}"
              f"  bought for ${row['purchase_price']:.2f}"
              f"  → {int(row['days_in_stock'])} days in stock")

    capital = dead["purchase_price"].sum()
    print(f"\n  {len(dead)} phones flagged  |  ${capital:.2f} capital at risk")
    print("  💡 Consider lowering prices on these to free up cash.")


def full_stock_list(df):
    print_header("FULL STOCK LIST")
    if df.empty:
        print("  No phones currently in stock.")
        return
    for _, row in df.iterrows():
        print(f"  ID {int(row['phone_id']):<4}"
              f"  {row['brand']} {row['model']:<18}"
              f"  {row['storage_gb']}GB"
              f"  {row['condition']:<20}"
              f"  ${row['purchase_price']:.2f}"
              f"  {int(row['days_in_stock'])} days")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conn      = sqlite3.connect(DB_PATH)
    df        = load_stock(conn)
    status_df = load_all_status(conn)
    conn.close()

    stock_overview(df, status_df)
    stock_by_brand(df)
    dead_stock_alert(df)
    full_stock_list(df)

    print("\n")
