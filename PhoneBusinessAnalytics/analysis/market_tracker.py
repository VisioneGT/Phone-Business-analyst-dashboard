"""
market_tracker.py
──────────────────
Compares what you're selling phones for vs. the current eBay market price.

Two uses:
  1. See if you're underpricing or overpricing your phones
  2. Get a recommended buy price for any model before purchasing

Run with: python market_tracker.py
"""

import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "../database/phone_business.db")

# How much below market price do you typically sell?
# 0.85 means you sell at 85% of eBay market (accounts for fees, condition, speed)
SELL_RATIO = 0.85

# What's the minimum profit margin you want? (as a fraction of sale price)
MIN_MARGIN = 0.25   # 25% margin minimum


# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_comparison(conn):
    """
    For every sold phone, compare your sale price to the eBay market price
    at the time of sale.
    """
    return pd.read_sql("""
        SELECT
            i.brand,
            i.model,
            i.condition,
            i.purchase_price,
            s.sale_price,
            s.platform,
            m.avg_sold_price   AS market_price,
            m.date_checked,
            -- positive = you sold ABOVE market, negative = you undersold
            s.sale_price - m.avg_sold_price AS vs_market,
            COALESCE(c.total_costs, 0)      AS total_costs,
            s.sale_price - i.purchase_price - COALESCE(c.total_costs, 0) AS net_profit
        FROM inventory i
        JOIN sales s      ON i.phone_id  = s.phone_id
        JOIN market_prices m ON LOWER(i.brand) = LOWER(m.brand)
                             AND LOWER(i.model) = LOWER(m.model)
        LEFT JOIN (
            SELECT phone_id, SUM(amount) AS total_costs
            FROM costs GROUP BY phone_id
        ) c ON i.phone_id = c.phone_id
    """, conn)


def load_market_prices(conn):
    """Latest market price for every model."""
    return pd.read_sql("""
        SELECT brand, model, avg_sold_price, date_checked
        FROM market_prices
        WHERE (brand, model, date_checked) IN (
            SELECT brand, model, MAX(date_checked)
            FROM market_prices
            GROUP BY brand, model
        )
        ORDER BY brand, model
    """, conn)


def load_in_stock(conn):
    """Phones currently in stock to check pricing opportunities."""
    return pd.read_sql("""
        SELECT i.phone_id, i.brand, i.model, i.condition,
               i.purchase_price,
               COALESCE(c.total_costs, 0) AS total_costs,
               m.avg_sold_price           AS market_price
        FROM inventory i
        LEFT JOIN market_prices m ON LOWER(i.brand) = LOWER(m.brand)
                                  AND LOWER(i.model) = LOWER(m.model)
        LEFT JOIN (
            SELECT phone_id, SUM(amount) AS total_costs
            FROM costs GROUP BY phone_id
        ) c ON i.phone_id = c.phone_id
        WHERE i.status = 'in stock'
    """, conn)


# ── ANALYSIS FUNCTIONS ────────────────────────────────────────────────────────

def print_header(title):
    print("\n" + "=" * 62)
    print(f"  {title}")
    print("=" * 62)


def current_market_prices(df):
    print_header("CURRENT eBay MARKET PRICES  (your reference sheet)")
    print(f"  {'Brand':<10} {'Model':<18} {'eBay Avg':>10}  {'Your Target Sale':>16}  {'Checked'}")
    print(f"  {'-'*10} {'-'*18} {'-'*10}  {'-'*16}  {'-'*12}")
    for _, row in df.iterrows():
        target = row["avg_sold_price"] * SELL_RATIO
        print(f"  {row['brand']:<10} {row['model']:<18}"
              f"  ${row['avg_sold_price']:>8.2f}"
              f"  ${target:>14.2f}"
              f"  {row['date_checked']}")
    print(f"\n  * Target sale = eBay avg × {SELL_RATIO} (your typical discount vs market)")


def pricing_vs_market(df):
    print_header("HOW YOUR PAST SALES COMPARE TO MARKET")
    if df.empty:
        print("  No data — need market prices for sold models.")
        return
    for _, row in df.iterrows():
        direction = "▲ above" if row["vs_market"] >= 0 else "▼ below"
        color_flag = "✅" if row["vs_market"] >= -20 else "⚠️ "
        print(f"  {color_flag} {row['brand']} {row['model']:<18}"
              f"  sold ${row['sale_price']:.2f}"
              f"  market ${row['market_price']:.2f}"
              f"  → ${abs(row['vs_market']):.2f} {direction} market"
              f"  | profit ${row['net_profit']:.2f}")


def recommended_sell_prices(stock_df):
    print_header("RECOMMENDED SELL PRICES FOR CURRENT STOCK")
    if stock_df.empty:
        print("  Nothing in stock.")
        return

    print(f"  {'Brand+Model':<28} {'Condition':<20} {'Paid':>7}"
          f"  {'Market':>7}  {'Recommend':>9}  {'Est Profit':>10}")
    print(f"  {'-'*28} {'-'*20} {'-'*7}  {'-'*7}  {'-'*9}  {'-'*10}")

    for _, row in stock_df.iterrows():
        if pd.isna(row["market_price"]):
            rec = "No data"
            est = "—"
        else:
            rec_price  = row["market_price"] * SELL_RATIO
            total_cost = row["purchase_price"] + row["total_costs"]
            est_profit = rec_price - total_cost
            rec = f"${rec_price:.2f}"
            est = f"${est_profit:.2f}"

        label = f"{row['brand']} {row['model']}"
        print(f"  {label:<28} {row['condition']:<20}"
              f"  ${row['purchase_price']:>5.2f}"
              f"  ${row['market_price']:>5.2f}"
              f"  {rec:>9}"
              f"  {est:>10}")


def buy_price_calculator(market_df):
    print_header("BUY PRICE CALCULATOR  (max you should pay per model)")
    print("  Based on: market price × sell ratio − min margin − avg repair cost ($25)\n")

    avg_repair = 25.00

    print(f"  {'Brand+Model':<28} {'eBay Avg':>9}  {'Max Buy Price':>14}")
    print(f"  {'-'*28} {'-'*9}  {'-'*14}")

    for _, row in market_df.iterrows():
        target_sale = row["avg_sold_price"] * SELL_RATIO
        # Max buy = what you'd sell it for, minus repair cost, minus minimum margin
        max_buy = target_sale * (1 - MIN_MARGIN) - avg_repair
        label   = f"{row['brand']} {row['model']}"
        print(f"  {label:<28}  ${row['avg_sold_price']:>7.2f}  ${max(max_buy, 0):>12.2f}")

    print(f"\n  * Min margin set at {int(MIN_MARGIN*100)}%  |  Avg repair assumed ${avg_repair:.2f}")
    print("  * Adjust MIN_MARGIN at the top of this file to change thresholds.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    conn       = sqlite3.connect(DB_PATH)
    market_df  = load_market_prices(conn)
    compare_df = load_comparison(conn)
    stock_df   = load_in_stock(conn)
    conn.close()

    current_market_prices(market_df)
    pricing_vs_market(compare_df)
    recommended_sell_prices(stock_df)
    buy_price_calculator(market_df)

    print("\n")
