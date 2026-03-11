"""
profit_analysis.py
───────────────────
Answers: which phones, damage types, and platforms make the most money?

Run with: python profit_analysis.py
"""

import sqlite3
import pandas as pd
import os

# ── PATH TO DATABASE ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))       # .../analysis/
DB_PATH  = os.path.join(BASE_DIR, "../database/phone_business.db")


# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_sales_data(conn):
    """
    Joins inventory + sales + costs into one flat table.
    Each row = one sold phone with all its numbers.
    """
    query = """
        SELECT
            i.phone_id,
            i.brand,
            i.model,
            i.storage_gb,
            i.condition,
            i.purchase_price,
            i.supplier,
            s.sale_price,
            s.sale_date,
            s.platform,
            COALESCE(c.total_costs, 0)                                      AS total_costs,
            s.sale_price - i.purchase_price - COALESCE(c.total_costs, 0)   AS net_profit,
            CAST(JULIANDAY(s.sale_date) - JULIANDAY(i.date_purchased) AS INTEGER) AS days_to_sell
        FROM inventory i
        JOIN sales s ON i.phone_id = s.phone_id
        LEFT JOIN (
            SELECT phone_id, SUM(amount) AS total_costs
            FROM costs
            GROUP BY phone_id
        ) c ON i.phone_id = c.phone_id
    """
    return pd.read_sql(query, conn)


# ── ANALYSIS FUNCTIONS ────────────────────────────────────────────────────────

def print_header(title):
    print("\n" + "=" * 58)
    print(f"  {title}")
    print("=" * 58)


def overall_summary(df):
    print_header("OVERALL BUSINESS SUMMARY")
    print(f"  Total phones sold       : {len(df)}")
    print(f"  Total revenue           : ${df['sale_price'].sum():,.2f}")
    print(f"  Total spend (buy+repair): ${(df['purchase_price'] + df['total_costs']).sum():,.2f}")
    print(f"  Total net profit        : ${df['net_profit'].sum():,.2f}")
    print(f"  Average profit per phone: ${df['net_profit'].mean():,.2f}")
    print(f"  Average days to sell    : {df['days_to_sell'].mean():.1f} days")


def profit_by_model(df):
    print_header("PROFIT BY MODEL  (best to worst)")
    result = (
        df.groupby(["brand", "model"])
        .agg(
            units_sold     = ("phone_id",       "count"),
            avg_buy_price  = ("purchase_price", "mean"),
            avg_sale_price = ("sale_price",     "mean"),
            avg_net_profit = ("net_profit",     "mean"),
            total_profit   = ("net_profit",     "sum"),
        )
        .round(2)
        .sort_values("total_profit", ascending=False)
        .reset_index()
    )
    for _, row in result.iterrows():
        print(f"  {row['brand']} {row['model']:<18}"
              f"  sold: {int(row['units_sold'])}"
              f"  avg profit: ${row['avg_net_profit']:.2f}"
              f"  total: ${row['total_profit']:.2f}")


def profit_by_condition(df):
    print_header("PROFIT BY DAMAGE TYPE")
    result = (
        df.groupby("condition")
        .agg(
            units      = ("phone_id",   "count"),
            avg_profit = ("net_profit", "mean"),
            total      = ("net_profit", "sum"),
        )
        .round(2)
        .sort_values("avg_profit", ascending=False)
        .reset_index()
    )
    for _, row in result.iterrows():
        print(f"  {row['condition']:<20}"
              f"  units: {int(row['units'])}"
              f"  avg profit: ${row['avg_profit']:.2f}"
              f"  total: ${row['total']:.2f}")


def profit_by_platform(df):
    print_header("PROFIT BY SELLING PLATFORM")
    result = (
        df.groupby("platform")
        .agg(
            units      = ("phone_id",   "count"),
            avg_profit = ("net_profit", "mean"),
            total      = ("net_profit", "sum"),
        )
        .round(2)
        .sort_values("total", ascending=False)
        .reset_index()
    )
    for _, row in result.iterrows():
        print(f"  {row['platform']:<12}"
              f"  units: {int(row['units'])}"
              f"  avg profit: ${row['avg_profit']:.2f}"
              f"  total: ${row['total']:.2f}")


def days_to_sell_by_model(df):
    print_header("AVERAGE DAYS TO SELL BY MODEL")
    result = (
        df.groupby(["brand", "model"])["days_to_sell"]
        .mean()
        .round(1)
        .sort_values(ascending=False)
        .reset_index()
    )
    for _, row in result.iterrows():
        bar = "█" * int(row["days_to_sell"])
        print(f"  {row['brand']} {row['model']:<18}  {row['days_to_sell']} days  {bar}")


def profit_by_supplier(df):
    print_header("BEST SUPPLIERS BY PROFIT")
    result = (
        df.groupby("supplier")
        .agg(
            units      = ("phone_id",   "count"),
            avg_profit = ("net_profit", "mean"),
            total      = ("net_profit", "sum"),
        )
        .round(2)
        .sort_values("total", ascending=False)
        .reset_index()
    )
    for _, row in result.iterrows():
        print(f"  {row['supplier']:<22}"
              f"  units: {int(row['units'])}"
              f"  avg profit: ${row['avg_profit']:.2f}"
              f"  total: ${row['total']:.2f}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    df   = load_sales_data(conn)
    conn.close()

    overall_summary(df)
    profit_by_model(df)
    profit_by_condition(df)
    profit_by_platform(df)
    days_to_sell_by_model(df)
    profit_by_supplier(df)

    print("\n")
