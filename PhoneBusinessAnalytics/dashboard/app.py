"""
dashboard/app.py
─────────────────
Multi-page dashboard with navbar.
All monetary values displayed in South African Rand (ZAR).

Pages:
  /            → Home
  /dashboard   → All charts
  /comparison  → Month 1 vs Month 2 comparison

Run with : python app.py
Then open: http://127.0.0.1:8050
"""

import sqlite3
import os
import json
import urllib.request
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "../database/phone_business.db")
TODAY    = date.today().isoformat()


# ── LIVE EXCHANGE RATE ────────────────────────────────────────────────────────

def get_exchange_rate():
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read())
            rate = data["rates"]["ZAR"]
            print(f"   💱 Live rate fetched: 1 USD = R{rate:.2f}")
            return rate
    except Exception as e:
        fallback = 18.50
        print(f"   ⚠️  Rate fetch failed ({e}) — using R{fallback:.2f}")
        return fallback


USD_TO_ZAR = get_exchange_rate()


def fmt_zar(value):
    return f"R {value:,.2f}"


# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_data():
    conn = sqlite3.connect(DB_PATH)

    # All sold phones joined with their costs and month label
    sales_df = pd.read_sql("""
        SELECT
            i.phone_id,
            i.brand, i.model, i.condition, i.supplier,
            i.purchase_price, i.date_purchased,
            i.month,
            s.sale_price, s.sale_date, s.platform,
            COALESCE(c.total_costs, 0) AS total_costs,
            s.sale_price - i.purchase_price - COALESCE(c.total_costs, 0) AS net_profit,
            CAST(JULIANDAY(s.sale_date) - JULIANDAY(i.date_purchased) AS INTEGER) AS days_to_sell
        FROM inventory i
        JOIN sales s ON i.phone_id = s.phone_id
        LEFT JOIN (
            SELECT phone_id, SUM(amount) AS total_costs
            FROM costs GROUP BY phone_id
        ) c ON i.phone_id = c.phone_id
    """, conn)

    stock_df = pd.read_sql(f"""
        SELECT brand, model, condition, purchase_price, status, month,
               CAST(JULIANDAY('{TODAY}') - JULIANDAY(date_purchased) AS INTEGER) AS days_in_stock
        FROM inventory WHERE status = 'in stock'
    """, conn)

    status_df = pd.read_sql("""
        SELECT status, COUNT(*) as count FROM inventory GROUP BY status
    """, conn)

    conn.close()

    # Convert all money to ZAR
    for col in ["purchase_price", "sale_price", "total_costs", "net_profit"]:
        sales_df[col] = sales_df[col] * USD_TO_ZAR
    stock_df["purchase_price"] = stock_df["purchase_price"] * USD_TO_ZAR

    return sales_df, stock_df, status_df


sales_df, stock_df, status_df = load_data()

# Split by month for comparison page
m1 = sales_df[sales_df["month"] == 1].copy()
m2 = sales_df[sales_df["month"] == 2].copy()

# ── SUMMARY NUMBERS ───────────────────────────────────────────────────────────

total_revenue  = sales_df["sale_price"].sum()
total_profit   = sales_df["net_profit"].sum()
total_sold     = len(sales_df)
avg_profit     = sales_df["net_profit"].mean()
in_stock_count = len(stock_df)
capital_tied   = stock_df["purchase_price"].sum()
dead_stock     = len(stock_df[stock_df["days_in_stock"] > 30])


# ── DASHBOARD CHARTS ──────────────────────────────────────────────────────────

profit_model = (
    sales_df.groupby(["brand", "model"])["net_profit"]
    .sum().reset_index().sort_values("net_profit", ascending=False)
)
fig_profit_model = px.bar(
    profit_model, x="model", y="net_profit", color="brand",
    title="Total Net Profit by Model",
    labels={"net_profit": "Net Profit (R)", "model": ""},
    color_discrete_sequence=px.colors.qualitative.Set2,
    template="plotly_dark"
)
fig_profit_model.update_traces(hovertemplate="R %{y:,.2f}")

fig_platform = px.pie(
    sales_df.groupby("platform")["net_profit"].sum().reset_index(),
    names="platform", values="net_profit",
    title="Profit by Selling Platform",
    color_discrete_sequence=px.colors.qualitative.Pastel,
    template="plotly_dark", hole=0.3
)

fig_condition = px.bar(
    sales_df.groupby("condition")["net_profit"].mean().reset_index()
            .sort_values("net_profit", ascending=False),
    x="condition", y="net_profit",
    title="Avg Profit by Damage Type",
    labels={"net_profit": "Avg Net Profit (R)", "condition": ""},
    color="net_profit", color_continuous_scale="Teal",
    template="plotly_dark"
)

fig_status = px.pie(
    status_df, names="status", values="count",
    title="Inventory Status",
    hole=0.45, template="plotly_dark",
    color_discrete_sequence=["#2ecc71", "#3498db", "#e74c3c"]
)

fig_days = px.bar(
    sales_df.groupby(["brand","model"])["days_to_sell"].mean().reset_index()
            .sort_values("days_to_sell", ascending=False).head(12),
    x="model", y="days_to_sell", color="brand",
    title="Avg Days to Sell by Model",
    labels={"days_to_sell": "Days", "model": ""},
    color_discrete_sequence=px.colors.qualitative.Set1,
    template="plotly_dark"
)

sales_df["week"] = pd.to_datetime(sales_df["sale_date"]).dt.to_period("W").astype(str)
weekly = sales_df.groupby("week").agg(
    revenue=("sale_price","sum"),
    profit=("net_profit","sum")
).reset_index()
fig_weekly = px.line(
    weekly, x="week", y=["revenue","profit"],
    title="Weekly Revenue vs Profit (ZAR)",
    labels={"value":"R","week":"Week","variable":""},
    template="plotly_dark",
    color_discrete_sequence=["#3498db","#2ecc71"]
)

dead = stock_df[stock_df["days_in_stock"] > 30].sort_values("days_in_stock", ascending=False)
fig_dead = go.Figure(data=[go.Table(
    header=dict(
        values=["Brand","Model","Condition","Buy Price (R)","Days in Stock"],
        fill_color="#2c3e50", font_color="white",
        font_size=13, align="left", height=32
    ),
    cells=dict(
        values=[
            dead["brand"], dead["model"], dead["condition"],
            dead["purchase_price"].map(lambda x: f"R {x:,.2f}"),
            dead["days_in_stock"]
        ],
        fill_color=[["#1e272e","#2d3436"] * (len(dead)//2 + 1)],
        font_color="white", align="left", height=28
    )
)])
fig_dead.update_layout(
    title="⚠️ Dead Stock — Unsold 30+ Days",
    paper_bgcolor="#2d3436", font_color="white"
)


# ── COMPARISON CHARTS (Month 1 vs Month 2) ────────────────────────────────────

def pct_change(old, new):
    """Returns percentage change from old to new. Returns None if old is 0."""
    if old == 0:
        return None
    return ((new - old) / old) * 100


def arrow(pct):
    """Green up arrow or red down arrow based on direction."""
    if pct is None:
        return "—"
    if pct >= 0:
        return f"▲ +{pct:.1f}%"
    return f"▼ {pct:.1f}%"


def arrow_color(pct):
    if pct is None:
        return "#95a5a6"
    return "#2ecc71" if pct >= 0 else "#e74c3c"


# Key metrics per month
m1_revenue = m1["sale_price"].sum()
m2_revenue = m2["sale_price"].sum()
m1_profit  = m1["net_profit"].sum()
m2_profit  = m2["net_profit"].sum()
m1_units   = len(m1)
m2_units   = len(m2)
m1_avg     = m1["net_profit"].mean() if len(m1) > 0 else 0
m2_avg     = m2["net_profit"].mean() if len(m2) > 0 else 0

rev_pct    = pct_change(m1_revenue, m2_revenue)
profit_pct = pct_change(m1_profit,  m2_profit)
units_pct  = pct_change(m1_units,   m2_units)
avg_pct    = pct_change(m1_avg,     m2_avg)

# Revenue comparison bar chart
comp_revenue_df = pd.DataFrame({
    "Month": ["Month 1 (Oct)", "Month 2 (Nov)"],
    "Revenue": [m1_revenue, m2_revenue],
    "Profit":  [m1_profit,  m2_profit],
})
fig_comp_revenue = px.bar(
    comp_revenue_df, x="Month", y=["Revenue","Profit"],
    title="Revenue & Profit: Month 1 vs Month 2",
    labels={"value": "ZAR (R)", "variable": ""},
    barmode="group",
    color_discrete_sequence=["#3498db","#2ecc71"],
    template="plotly_dark"
)
fig_comp_revenue.update_traces(hovertemplate="R %{y:,.2f}")

# Units sold per brand per month
m1_brands = m1.groupby("brand")["phone_id"].count().reset_index().rename(columns={"phone_id":"units"})
m1_brands["Month"] = "Month 1 (Oct)"
m2_brands = m2.groupby("brand")["phone_id"].count().reset_index().rename(columns={"phone_id":"units"})
m2_brands["Month"] = "Month 2 (Nov)"
brands_combined = pd.concat([m1_brands, m2_brands])

fig_comp_brands = px.bar(
    brands_combined, x="brand", y="units", color="Month",
    title="Units Sold by Brand: Month 1 vs Month 2",
    labels={"units": "Units Sold", "brand": ""},
    barmode="group",
    color_discrete_sequence=["#6c5ce7","#fdcb6e"],
    template="plotly_dark"
)

# Profit by brand per month
m1_brand_profit = m1.groupby("brand")["net_profit"].sum().reset_index()
m1_brand_profit["Month"] = "Month 1 (Oct)"
m2_brand_profit = m2.groupby("brand")["net_profit"].sum().reset_index()
m2_brand_profit["Month"] = "Month 2 (Nov)"
brand_profit_combined = pd.concat([m1_brand_profit, m2_brand_profit])

fig_comp_brand_profit = px.bar(
    brand_profit_combined, x="brand", y="net_profit", color="Month",
    title="Total Profit by Brand: Month 1 vs Month 2",
    labels={"net_profit": "Net Profit (R)", "brand": ""},
    barmode="group",
    color_discrete_sequence=["#6c5ce7","#fdcb6e"],
    template="plotly_dark"
)
fig_comp_brand_profit.update_traces(hovertemplate="R %{y:,.2f}")

# Platform comparison
m1_plat = m1.groupby("platform")["net_profit"].sum().reset_index()
m1_plat["Month"] = "Month 1 (Oct)"
m2_plat = m2.groupby("platform")["net_profit"].sum().reset_index()
m2_plat["Month"] = "Month 2 (Nov)"
plat_combined = pd.concat([m1_plat, m2_plat])

fig_comp_platform = px.bar(
    plat_combined, x="platform", y="net_profit", color="Month",
    title="Profit by Platform: Month 1 vs Month 2",
    labels={"net_profit": "Net Profit (R)", "platform": ""},
    barmode="group",
    color_discrete_sequence=["#6c5ce7","#fdcb6e"],
    template="plotly_dark"
)

# Model-level comparison table
m1_models = m1.groupby(["brand","model"]).agg(
    m1_units=("phone_id","count"),
    m1_revenue=("sale_price","sum"),
    m1_profit=("net_profit","sum")
).reset_index()

m2_models = m2.groupby(["brand","model"]).agg(
    m2_units=("phone_id","count"),
    m2_revenue=("sale_price","sum"),
    m2_profit=("net_profit","sum")
).reset_index()

model_comp = pd.merge(m1_models, m2_models, on=["brand","model"], how="outer").fillna(0)
model_comp["profit_change_pct"] = model_comp.apply(
    lambda r: pct_change(r["m1_profit"], r["m2_profit"]), axis=1
)
model_comp["profit_arrow"] = model_comp["profit_change_pct"].apply(arrow)
model_comp = model_comp.sort_values("m2_profit", ascending=False)


# ── POPULARITY DATA ───────────────────────────────────────────────────────────

popularity = (
    sales_df.groupby(["brand", "model"])
    .agg(
        units_sold    = ("phone_id",     "count"),
        total_revenue = ("sale_price",   "sum"),
        total_profit  = ("net_profit",   "sum"),
        avg_profit    = ("net_profit",   "mean"),
        avg_days      = ("days_to_sell", "mean"),
    )
    .reset_index()
    .sort_values("units_sold", ascending=False)
    .reset_index(drop=True)
)
popularity["rank"] = popularity.index + 1

brand_popularity = (
    sales_df.groupby("brand")
    .agg(
        units_sold   = ("phone_id",   "count"),
        total_profit = ("net_profit", "sum"),
        avg_profit   = ("net_profit", "mean"),
    )
    .reset_index()
    .sort_values("units_sold", ascending=False)
    .reset_index(drop=True)
)
brand_popularity["rank"] = brand_popularity.index + 1

fig_pop_units = px.bar(
    popularity.head(15),
    x="units_sold", y="model", color="brand",
    orientation="h",
    title="Most Popular Models by Units Sold",
    labels={"units_sold": "Units Sold", "model": ""},
    color_discrete_sequence=px.colors.qualitative.Set2,
    template="plotly_dark"
)
fig_pop_units.update_layout(yaxis={"categoryorder": "total ascending"})

fig_pop_brands = px.bar(
    brand_popularity,
    x="brand", y="units_sold", color="brand",
    title="Most Popular Brands by Units Sold",
    labels={"units_sold": "Units Sold", "brand": ""},
    color_discrete_sequence=px.colors.qualitative.Pastel,
    template="plotly_dark"
)

fig_pop_pie = px.pie(
    brand_popularity,
    names="brand", values="units_sold",
    title="Sales Share by Brand",
    color_discrete_sequence=px.colors.qualitative.Set3,
    template="plotly_dark", hole=0.35
)


# ── STYLES ────────────────────────────────────────────────────────────────────

BG         = "#2d3436"
BG_CARD    = "#1e272e"
BG_CHART   = "#353b48"
ACCENT     = "#6c5ce7"
TEXT       = "#ffffff"
TEXT_MUTED = "#95a5a6"

CARD_STYLE = {
    "background": BG_CARD, "borderRadius": "14px",
    "padding": "20px 24px", "textAlign": "center",
    "flex": "1", "margin": "6px", "minWidth": "130px",
    "boxShadow": "0 4px 12px rgba(0,0,0,0.3)"
}

CHART_CARD = {
    "background": BG_CHART, "borderRadius": "14px",
    "padding": "12px", "flex": "1", "minWidth": "320px",
    "margin": "8px"
}

NAV_LINK = {
    "color": TEXT_MUTED, "textDecoration": "none",
    "padding": "8px 20px", "borderRadius": "8px",
    "fontSize": "15px", "fontWeight": "500",
}

NAV_LINK_ACTIVE = {
    **NAV_LINK, "color": TEXT, "background": ACCENT,
}


# ── COMPONENTS ────────────────────────────────────────────────────────────────

def metric_card(label, value, color=TEXT):
    return html.Div([
        html.P(label, style={
            "color": TEXT_MUTED, "margin": "0 0 4px 0",
            "fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "1px"
        }),
        html.H3(value, style={"color": color, "margin": "0", "fontSize": "22px", "fontWeight": "700"}),
    ], style=CARD_STYLE)


def comparison_card(label, m1_val, m2_val, pct):
    """Card showing month 1, month 2, and the % change between them."""
    return html.Div([
        html.P(label, style={
            "color": TEXT_MUTED, "margin": "0 0 10px 0",
            "fontSize": "11px", "textTransform": "uppercase", "letterSpacing": "1px"
        }),
        html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end"}, children=[
            html.Div([
                html.P("Month 1", style={"color": TEXT_MUTED, "margin": "0", "fontSize": "11px"}),
                html.P(m1_val, style={"color": "#6c5ce7", "margin": "0", "fontSize": "17px", "fontWeight": "700"}),
            ]),
            html.Div([
                html.P("Month 2", style={"color": TEXT_MUTED, "margin": "0", "fontSize": "11px"}),
                html.P(m2_val, style={"color": "#fdcb6e", "margin": "0", "fontSize": "17px", "fontWeight": "700"}),
            ]),
            html.Div([
                html.P("Change", style={"color": TEXT_MUTED, "margin": "0", "fontSize": "11px"}),
                html.P(arrow(pct), style={"color": arrow_color(pct), "margin": "0", "fontSize": "17px", "fontWeight": "700"}),
            ]),
        ]),
    ], style={**CARD_STYLE, "minWidth": "220px", "textAlign": "left"})


def navbar(current_page):
    pages = [
        ("/",           "🏠  Home"),
        ("/dashboard",  "📊  Dashboard"),
        ("/comparison", "📅  Monthly Comparison"),
        ("/popularity", "🏆  Popularity"),
    ]
    links = []
    for path, label in pages:
        style = NAV_LINK_ACTIVE if current_page == path else NAV_LINK
        links.append(html.A(label, href=path, style=style))

    return html.Div(
        style={
            "background": BG_CARD, "padding": "0 32px",
            "display": "flex", "alignItems": "center",
            "justifyContent": "space-between", "height": "60px",
            "boxShadow": "0 2px 12px rgba(0,0,0,0.4)",
            "position": "sticky", "top": "0", "zIndex": "1000",
        },
        children=[
            html.Div([
                html.Span("📱", style={"fontSize": "22px", "marginRight": "10px"}),
                html.Span("PhoneBiz Analytics", style={
                    "color": TEXT, "fontWeight": "700", "fontSize": "17px",
                }),
            ], style={"display": "flex", "alignItems": "center"}),
            html.Div([
                *links,
                html.Span(f"💱 1 USD = R {USD_TO_ZAR:.2f}", style={
                    "color": "#2ecc71", "fontSize": "12px", "marginLeft": "16px",
                    "background": "#1e272e", "padding": "4px 12px",
                    "borderRadius": "20px", "fontWeight": "600",
                })
            ], style={"display": "flex", "gap": "8px", "alignItems": "center"}),
        ]
    )


def feature_card(icon, title, description):
    return html.Div(style={
        "background": BG_CARD, "borderRadius": "14px", "padding": "24px",
        "flex": "1", "minWidth": "240px", "boxShadow": "0 4px 12px rgba(0,0,0,0.3)",
    }, children=[
        html.Div(icon, style={"fontSize": "28px", "marginBottom": "12px"}),
        html.H3(title, style={"color": TEXT, "margin": "0 0 8px 0", "fontSize": "16px", "fontWeight": "700"}),
        html.P(description, style={"color": TEXT_MUTED, "margin": "0", "fontSize": "14px", "lineHeight": "1.6"}),
    ])


def tech_badge(name):
    return html.Span(name, style={
        "background": ACCENT, "color": TEXT,
        "padding": "6px 16px", "borderRadius": "20px",
        "fontSize": "13px", "fontWeight": "600",
    })


# ── PAGES ─────────────────────────────────────────────────────────────────────

def page_home():
    return html.Div([
        navbar("/"),
        html.Div(style={"maxWidth": "860px", "margin": "60px auto", "padding": "0 24px"}, children=[
            html.Div(style={"textAlign": "center", "marginBottom": "56px"}, children=[
                html.Div("📱", style={"fontSize": "64px", "marginBottom": "16px"}),
                html.H1("Phone Business Analytics", style={
                    "color": TEXT, "fontSize": "36px", "margin": "0 0 12px 0", "fontWeight": "800"
                }),
                html.P(
                    "A data analytics system built to replace pen-and-paper tracking "
                    "for a broken phone reselling business. All values shown in South African Rand (ZAR) "
                    "using a live exchange rate fetched every time the app starts.",
                    style={"color": TEXT_MUTED, "fontSize": "17px", "lineHeight": "1.7",
                           "maxWidth": "620px", "margin": "0 auto"}
                ),
                html.Div(f"💱 Live Rate: 1 USD = R {USD_TO_ZAR:.2f} ZAR  •  {TODAY}", style={
                    "display": "inline-block", "marginTop": "16px",
                    "background": BG_CARD, "color": "#2ecc71",
                    "padding": "8px 20px", "borderRadius": "20px",
                    "fontSize": "13px", "fontWeight": "600",
                }),
                html.Br(),
                html.A("View Dashboard →", href="/dashboard", style={
                    **NAV_LINK_ACTIVE, "display": "inline-block",
                    "marginTop": "20px", "fontSize": "16px", "padding": "12px 32px",
                }),
            ]),
            html.H2("What this project does", style={"color": TEXT, "fontSize": "22px", "marginBottom": "20px"}),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "marginBottom": "48px"}, children=[
                feature_card("📦", "Inventory Tracking",
                    "Every phone bought is logged with its model, condition, purchase price, "
                    "and supplier. Tracks whether it's in stock, sold, or scrapped."),
                feature_card("💰", "Profit Analysis",
                    "Calculates net profit per phone after purchase costs and repairs. "
                    "Breaks down performance by model, damage type, and selling platform."),
                feature_card("📅", "Monthly Comparison",
                    "Compares Month 1 vs Month 2 sales with percentage change indicators "
                    "across revenue, profit, units sold, and every brand."),
                feature_card("📉", "Dead Stock Alerts",
                    "Flags phones unsold for over 30 days, showing capital at risk "
                    "and which models are moving slowest."),
                feature_card("📊", "Live Dashboard",
                    "Revenue trends, platform comparisons, inventory status, and weekly "
                    "profit tracking — all updated every time you run the app."),
                feature_card("💱", "Live Exchange Rate",
                    "All values automatically converted from USD to ZAR using a live rate "
                    "fetched from the internet on startup. No manual updates needed."),
            ]),
            html.H2("Built with", style={"color": TEXT, "fontSize": "22px", "marginBottom": "20px"}),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "12px", "marginBottom": "48px"}, children=[
                tech_badge("Python"), tech_badge("SQLite"), tech_badge("pandas"),
                tech_badge("Plotly"), tech_badge("Dash"), tech_badge("Live FX API"),
            ]),
            html.P(f"Last updated: {TODAY}  •  Rate: 1 USD = R {USD_TO_ZAR:.2f}",
                   style={"color": TEXT_MUTED, "textAlign": "center", "fontSize": "13px"}),
        ])
    ])


def page_dashboard():
    return html.Div([
        navbar("/dashboard"),
        html.Div(style={"padding": "28px 32px", "background": BG, "minHeight": "100vh"}, children=[
            html.H2("📊 Dashboard", style={"color": TEXT, "margin": "0 0 4px 0", "fontSize": "24px"}),
            html.P(f"Data as of {TODAY}  •  All values in ZAR  •  Rate: 1 USD = R {USD_TO_ZAR:.2f}",
                   style={"color": TEXT_MUTED, "margin": "0 0 24px 0", "fontSize": "13px"}),

            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "24px"}, children=[
                metric_card("Total Revenue",    fmt_zar(total_revenue),  "#3498db"),
                metric_card("Total Net Profit", fmt_zar(total_profit),   "#2ecc71"),
                metric_card("Phones Sold",      str(total_sold),          TEXT),
                metric_card("Avg Profit/Phone", fmt_zar(avg_profit),     "#f39c12"),
                metric_card("In Stock",         str(in_stock_count),      TEXT),
                metric_card("Capital Tied Up",  fmt_zar(capital_tied),   "#e17055"),
                metric_card("Dead Stock ⚠️",    str(dead_stock),          "#e74c3c"),
            ]),

            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_profit_model, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "2"}),
                html.Div(dcc.Graph(figure=fig_platform,     config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_condition, config={"displayModeBar": False}), style=CHART_CARD),
                html.Div(dcc.Graph(figure=fig_status,    config={"displayModeBar": False}), style=CHART_CARD),
                html.Div(dcc.Graph(figure=fig_days,      config={"displayModeBar": False}), style=CHART_CARD),
            ]),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_weekly, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),
            html.Div(dcc.Graph(figure=fig_dead, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
        ])
    ])


def page_comparison():
    # Build the model comparison table rows
    table_rows = []
    for _, row in model_comp.iterrows():
        pct = row["profit_change_pct"]
        color = arrow_color(pct)
        table_rows.append(html.Tr([
            html.Td(f"{row['brand']} {row['model']}", style={"padding": "10px 14px", "color": TEXT}),
            html.Td(f"{int(row['m1_units'])}", style={"padding": "10px 14px", "color": "#6c5ce7", "textAlign": "center"}),
            html.Td(f"{int(row['m2_units'])}", style={"padding": "10px 14px", "color": "#fdcb6e", "textAlign": "center"}),
            html.Td(fmt_zar(row["m1_profit"]), style={"padding": "10px 14px", "color": "#6c5ce7"}),
            html.Td(fmt_zar(row["m2_profit"]), style={"padding": "10px 14px", "color": "#fdcb6e"}),
            html.Td(arrow(pct), style={"padding": "10px 14px", "color": color, "fontWeight": "700"}),
        ], style={"borderBottom": "1px solid #353b48"}))

    return html.Div([
        navbar("/comparison"),
        html.Div(style={"padding": "28px 32px", "background": BG, "minHeight": "100vh"}, children=[

            html.H2("📅 Monthly Comparison", style={"color": TEXT, "margin": "0 0 4px 0", "fontSize": "24px"}),
            html.P("Month 1 = October 2024  •  Month 2 = November 2024  •  All values in ZAR",
                   style={"color": TEXT_MUTED, "margin": "0 0 28px 0", "fontSize": "13px"}),

            # ── KEY METRIC COMPARISON CARDS ───────────────────────────
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "28px"}, children=[
                comparison_card("Total Revenue",    fmt_zar(m1_revenue), fmt_zar(m2_revenue), rev_pct),
                comparison_card("Total Net Profit", fmt_zar(m1_profit),  fmt_zar(m2_profit),  profit_pct),
                comparison_card("Phones Sold",      str(m1_units),       str(m2_units),        units_pct),
                comparison_card("Avg Profit/Phone", fmt_zar(m1_avg),     fmt_zar(m2_avg),      avg_pct),
            ]),

            # ── REVENUE & PROFIT BAR CHART ────────────────────────────
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_comp_revenue, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
                html.Div(dcc.Graph(figure=fig_comp_brands,  config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),

            # ── BRAND PROFIT + PLATFORM ───────────────────────────────
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_comp_brand_profit, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "2"}),
                html.Div(dcc.Graph(figure=fig_comp_platform,     config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),

            # ── MODEL BY MODEL TABLE ──────────────────────────────────
            html.Div(style={**CHART_CARD, "margin": "8px"}, children=[
                html.H3("Model-by-Model Breakdown", style={
                    "color": TEXT, "margin": "8px 8px 16px 8px", "fontSize": "16px"
                }),
                html.Table(style={"width": "100%", "borderCollapse": "collapse"}, children=[
                    html.Thead(html.Tr([
                        html.Th("Model",             style={"padding": "10px 14px", "color": TEXT_MUTED, "textAlign": "left", "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                        html.Th("M1 Units",          style={"padding": "10px 14px", "color": TEXT_MUTED, "textAlign": "center", "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                        html.Th("M2 Units",          style={"padding": "10px 14px", "color": TEXT_MUTED, "textAlign": "center", "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                        html.Th("M1 Profit",         style={"padding": "10px 14px", "color": TEXT_MUTED, "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                        html.Th("M2 Profit",         style={"padding": "10px 14px", "color": TEXT_MUTED, "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                        html.Th("% Change",          style={"padding": "10px 14px", "color": TEXT_MUTED, "fontSize": "12px", "textTransform": "uppercase", "borderBottom": "2px solid #2d3436"}),
                    ])),
                    html.Tbody(table_rows),
                ]),
            ]),
        ])
    ])


def page_popularity():
    # Medal colors for top 3
    def rank_badge(rank):
        medals = {1: ("🥇", "#f1c40f"), 2: ("🥈", "#95a5a6"), 3: ("🥉", "#e67e22")}
        if rank in medals:
            icon, color = medals[rank]
            return html.Span(f"{icon} #{rank}", style={"color": color, "fontWeight": "700"})
        return html.Span(f"#{rank}", style={"color": TEXT_MUTED, "fontWeight": "600"})

    # Build popularity table rows
    pop_rows = []
    for _, row in popularity.iterrows():
        pop_rows.append(html.Tr([
            html.Td(rank_badge(int(row["rank"])),
                    style={"padding": "12px 14px", "textAlign": "center"}),
            html.Td(f"{row['brand']}", style={"padding": "12px 14px", "color": TEXT_MUTED, "fontSize": "13px"}),
            html.Td(f"{row['model']}", style={"padding": "12px 14px", "color": TEXT, "fontWeight": "600"}),
            html.Td(str(int(row["units_sold"])),
                    style={"padding": "12px 14px", "textAlign": "center", "color": "#3498db", "fontWeight": "700", "fontSize": "16px"}),
            html.Td(fmt_zar(row["total_revenue"]),
                    style={"padding": "12px 14px", "color": "#2ecc71"}),
            html.Td(fmt_zar(row["total_profit"]),
                    style={"padding": "12px 14px", "color": "#f39c12"}),
            html.Td(fmt_zar(row["avg_profit"]),
                    style={"padding": "12px 14px", "color": TEXT_MUTED}),
            html.Td(f"{row['avg_days']:.1f} days",
                    style={"padding": "12px 14px", "color": TEXT_MUTED}),
        ], style={
            "borderBottom": "1px solid #353b48",
            "background": "#1e272e" if int(row["rank"]) % 2 == 0 else "transparent"
        }))

    # Brand table rows
    brand_rows = []
    for _, row in brand_popularity.iterrows():
        brand_rows.append(html.Tr([
            html.Td(rank_badge(int(row["rank"])),
                    style={"padding": "10px 14px", "textAlign": "center"}),
            html.Td(row["brand"], style={"padding": "10px 14px", "color": TEXT, "fontWeight": "600"}),
            html.Td(str(int(row["units_sold"])),
                    style={"padding": "10px 14px", "textAlign": "center", "color": "#3498db", "fontWeight": "700"}),
            html.Td(fmt_zar(row["total_profit"]),
                    style={"padding": "10px 14px", "color": "#f39c12"}),
            html.Td(fmt_zar(row["avg_profit"]),
                    style={"padding": "10px 14px", "color": TEXT_MUTED}),
        ], style={
            "borderBottom": "1px solid #353b48",
            "background": "#1e272e" if int(row["rank"]) % 2 == 0 else "transparent"
        }))

    TH = {"padding": "12px 14px", "color": TEXT_MUTED, "fontSize": "11px",
          "textTransform": "uppercase", "letterSpacing": "1px",
          "borderBottom": "2px solid #2d3436", "textAlign": "left"}

    return html.Div([
        navbar("/popularity"),
        html.Div(style={"padding": "28px 32px", "background": BG, "minHeight": "100vh"}, children=[

            html.H2("🏆 Phone Popularity Rankings", style={"color": TEXT, "margin": "0 0 4px 0", "fontSize": "24px"}),
            html.P(f"Ranked by units sold across all time  •  {total_sold} total phones sold  •  All values in ZAR",
                   style={"color": TEXT_MUTED, "margin": "0 0 28px 0", "fontSize": "13px"}),

            # ── TOP 3 HIGHLIGHT CARDS ─────────────────────────────────
            html.Div(style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "marginBottom": "28px"}, children=[
                html.Div(style={
                    "background": BG_CARD, "borderRadius": "14px", "padding": "20px 24px",
                    "flex": "1", "minWidth": "180px", "textAlign": "center",
                    "boxShadow": "0 4px 12px rgba(0,0,0,0.3)",
                    "border": f"1px solid {['#f1c40f','#95a5a6','#e67e22'][i]}"
                }, children=[
                    html.Div(["🥇","🥈","🥉"][i], style={"fontSize": "32px", "marginBottom": "8px"}),
                    html.P(f"{popularity.iloc[i]['brand']}", style={"color": TEXT_MUTED, "margin": "0", "fontSize": "12px"}),
                    html.H3(f"{popularity.iloc[i]['model']}", style={"color": TEXT, "margin": "4px 0", "fontSize": "16px"}),
                    html.P(f"{int(popularity.iloc[i]['units_sold'])} sold", style={
                        "color": ["#f1c40f","#95a5a6","#e67e22"][i],
                        "margin": "0", "fontSize": "20px", "fontWeight": "700"
                    }),
                ]) for i in range(min(3, len(popularity)))
            ]),

            # ── CHARTS ROW ────────────────────────────────────────────
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}, children=[
                html.Div(dcc.Graph(figure=fig_pop_units,  config={"displayModeBar": False}), style={**CHART_CARD, "flex": "2"}),
                html.Div(dcc.Graph(figure=fig_pop_pie,    config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),
            html.Div(style={"display": "flex", "flexWrap": "wrap", "marginBottom": "24px"}, children=[
                html.Div(dcc.Graph(figure=fig_pop_brands, config={"displayModeBar": False}), style={**CHART_CARD, "flex": "1"}),
            ]),

            # ── FULL MODEL RANKINGS TABLE ──────────────────────────────
            html.Div(style={**CHART_CARD, "margin": "8px", "overflowX": "auto"}, children=[
                html.H3("Full Model Rankings", style={"color": TEXT, "margin": "8px 8px 16px 8px", "fontSize": "16px"}),
                html.Table(style={"width": "100%", "borderCollapse": "collapse"}, children=[
                    html.Thead(html.Tr([
                        html.Th("Rank",         style=TH),
                        html.Th("Brand",        style=TH),
                        html.Th("Model",        style=TH),
                        html.Th("Units Sold",   style={**TH, "textAlign": "center"}),
                        html.Th("Total Revenue",style=TH),
                        html.Th("Total Profit", style=TH),
                        html.Th("Avg Profit",   style=TH),
                        html.Th("Avg Days Sold",style=TH),
                    ])),
                    html.Tbody(pop_rows),
                ]),
            ]),

            # ── BRAND RANKINGS TABLE ───────────────────────────────────
            html.Div(style={**CHART_CARD, "margin": "8px", "marginTop": "16px"}, children=[
                html.H3("Brand Rankings", style={"color": TEXT, "margin": "8px 8px 16px 8px", "fontSize": "16px"}),
                html.Table(style={"width": "100%", "borderCollapse": "collapse"}, children=[
                    html.Thead(html.Tr([
                        html.Th("Rank",        style=TH),
                        html.Th("Brand",       style=TH),
                        html.Th("Units Sold",  style={**TH, "textAlign": "center"}),
                        html.Th("Total Profit",style=TH),
                        html.Th("Avg Profit",  style=TH),
                    ])),
                    html.Tbody(brand_rows),
                ]),
            ]),
        ])
    ])


def page_404():
    return html.Div([
        navbar("/"),
        html.Div(style={"textAlign": "center", "marginTop": "100px"}, children=[
            html.H1("404", style={"color": ACCENT, "fontSize": "72px", "margin": "0"}),
            html.P("Page not found.", style={"color": TEXT_MUTED, "fontSize": "18px"}),
            html.A("← Go Home", href="/", style={**NAV_LINK_ACTIVE, "display": "inline-block", "marginTop": "16px"}),
        ])
    ])


# ── APP + ROUTING ─────────────────────────────────────────────────────────────

app = Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(
    style={"background": BG, "minHeight": "100vh", "fontFamily": "'Segoe UI', Arial, sans-serif"},
    children=[
        dcc.Location(id="url", refresh=False),
        html.Div(id="page-content"),
    ]
)


@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname")
)
def display_page(pathname):
    if pathname == "/" or pathname is None:
        return page_home()
    elif pathname == "/dashboard":
        return page_dashboard()
    elif pathname == "/comparison":
        return page_comparison()
    elif pathname == "/popularity":
        return page_popularity()
    else:
        return page_404()


if __name__ == "__main__":
    print("\n🚀 Dashboard starting...")
    print("   Open http://127.0.0.1:8050 in your browser")
    print("   Press Ctrl+C to stop\n")
    app.run(debug=True)

# ── POPULARITY PAGE (appended) ────────────────────────────────────────────────