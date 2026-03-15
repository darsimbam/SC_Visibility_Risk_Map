# Supply Chain Visibility & Risk Dashboard

A Streamlit MVP for monitoring distributor inventory, stock in transit,
production status, and vessel delays — with projected stockout alerts.

## Quick Start

```bash
# 1. Activate the existing virtual environment
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies (skip if already done)
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The dashboard opens at http://localhost:8501

---

## Project structure

```
SC_Visibility_Risk_Map/
├── app.py                   # Streamlit entry point (3 tabs)
├── requirements.txt
├── data/
│   ├── locations.csv        # Plants, distributors, ports (lat/lon)
│   ├── inventory.csv        # On-hand stock + daily demand per SKU/location
│   ├── production_orders.csv
│   ├── shipments.csv        # In-transit and planned shipments
│   └── vessels.csv          # Vessel positions and delay status
├── logic/
│   ├── data_loader.py       # CSV → typed DataFrames
│   └── risk_engine.py       # All risk calculations → alerts DataFrame
└── views/
    ├── map_view.py          # Plotly mapbox: locations, routes, vessels
    ├── alerts_view.py       # Filterable alert cards + compact table
    └── shipment_view.py     # Shipment drill-down with linked alerts
```

---

## Demo scenario (snapshot date: 2026-03-14)

| Signal | Detail |
|---|---|
| **Production slip** | PO-001 (Industrial Pump A, Chicago) slipped 10 days — only 40% complete |
| **Vessel delayed** | Atlantic Runner (VSL-002) delayed 7 days; position stale 4 days |
| **High demand** | New York DC: 5 days of cover for SKU-001; replenishment ETA 2026-03-28 |
| **CRITICAL alert** | 9-day projected stockout gap at New York DC for Industrial Pump A |
| **HIGH alert** | Miami DC: SKU-002 stockout before delayed vessel arrives |
| **HIGH alert** | Miami DC: SKU-003 truck shipment delayed by production slip |

---

## Risk rules

| Rule | Logic |
|---|---|
| Days of cover | `on_hand / avg_daily_demand` |
| Stockout date | `today + days_of_cover` |
| Stockout alert | `stockout_date < next_inbound_ETA` |
| Vessel delay | `vessel.delay_days > 0` |
| Stale position | No position update for > 3 days |
| Production slip | `actual_completion > planned_completion` |
| Combined risk | Worst signal per SKU-location |

---

## Severity thresholds

| Severity | Inventory | Vessel delay |
|---|---|---|
| CRITICAL | gap ≥ 5 days or doc < 3 | delay ≥ 7 days |
| HIGH | gap 1–4 days or doc < 7 | delay 3–6 days |
| MEDIUM | doc < 14, no gap | delay 1–2 days |
