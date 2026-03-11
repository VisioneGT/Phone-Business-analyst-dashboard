# 📱 Phone Business Analytics

A full end-to-end data analytics system built to replace 
pen-and-paper tracking for a broken phone reselling business. 
The business sources damaged phones from insurance companies 
and resells them after repair. This system tracks every phone 
from purchase to sale, calculates real profit margins, and 
presents everything in a live interactive dashboard.

All monetary values are displayed in South African Rand (ZAR) 
using a live exchange rate fetched automatically on startup.

---

## What It Does

- Tracks inventory from purchase to sale across multiple 
  brands and models
- Calculates net profit per phone after purchase price, 
  repair costs, and shipping
- Identifies dead stock — phones sitting unsold for 30+ days
- Compares Month 1 vs Month 2 performance with percentage 
  change indicators
- Ranks phones from most to least popular by units sold
- Recommends maximum buy prices based on historical sales data
- Converts all values from USD to ZAR using a live exchange 
  rate API

---

## Tech Stack

| Tool | Purpose |
|------|---------|
| Python | Core language |
| SQLite | Local database |
| pandas | Data manipulation and aggregation |
| Plotly | Interactive charts and visualisations |
| Dash | Multi-page web dashboard |
| open.er-api.com | Live USD to ZAR exchange rate |

---

## Dashboard Pages

**Home** — Project overview and feature summary

**Dashboard** — Full analytics view with KPI cards, 
profit by model, platform analysis, inventory status, 
weekly revenue trends, and dead stock alerts

**Monthly Comparison** — Side by side comparison of 
Month 1 vs Month 2 with percentage change across revenue, 
profit, units sold, and every brand and model

**Popularity Rankings** — All phone models ranked from 
most to least popular with gold, silver, and bronze medals 
for the top 3

---

## Project Structure
```
PhoneBusinessAnalytics/
│
├── data/
│   ├── inventory.csv      ← phones purchased
│   ├── sales.csv          ← phones sold
│   └── costs.csv          ← repair and shipping costs
│
├── database/
│   └── setup_db.py        ← creates and populates database
│
├── analysis/
│   ├── profit_analysis.py
│   ├── inventory_analysis.py
│   └── market_tracker.py
│
├── dashboard/
│   └── app.py             ← run this to open the dashboard
│
└── requirements.txt
```

---

## How to Run

**1. Install dependencies**
```bash
pip install pandas plotly dash
```

**2. Set up the database**
```bash
cd database
python setup_db.py
```

**3. Start the dashboard**
```bash
cd dashboard
python app.py
```

**4. Open your browser and go to**
```
http://127.0.0.1:8050
```

---

## Key Analytical Findings

- eBay consistently generated higher profit per unit than 
  WhatsApp and Facebook despite lower total volume
- Cracked screen repairs produced the best average margin 
  of all damage types due to predictable repair costs
- Month 2 showed stronger overall performance across 
  revenue, units sold, and average profit per phone
- Apple and Samsung dominated units sold but Google Pixel 
  and OnePlus showed competitive profit margins per unit

---

## Skills Demonstrated

- End-to-end data pipeline design
- SQL database schema design and multi-table JOIN queries
- Python data manipulation with pandas
- Interactive data visualisation with Plotly
- Multi-page web application development with Dash
- Live API integration with error handling and fallback logic
- Business analytics and KPI tracking
- Month-on-month performance analysis
