# SC_Visibility_Risk_Map

Streamlit MVP for monitoring supply chain visibility and operational risk across a beauty and personal care network.

The current demo scenario models production in Switzerland and Turkey, with distribution across Gulf markets. It highlights projected stockouts, delayed vessels, missed ETAs, and production slips using CSV-backed sample data.

## Live Demo

Recruiters and reviewers can view the deployed app here:

[https://baselstraseriskmap.streamlit.app/](https://baselstraseriskmap.streamlit.app/)

## What It Does

- Shows plants, distribution centers, ports, vessels, and shipment routes on an interactive map
- Calculates inventory risk from days of cover and next inbound replenishment
- Surfaces transit risk from vessel delays, stale vessel positions, and overdue non-vessel shipments
- Surfaces production risk from slipped production orders
- Lets you click a map location to inspect detailed local inventory, inbound or outbound flows, vessels, and active alerts
- Provides a shipment drilldown tab for individual shipment status and linked destination alerts

## Current Demo Network

Snapshot date in the risk engine: `2026-03-15`

Current sample data includes:

- 2 plants in Switzerland
- 1 plant in Turkey
- 10 distribution centers across Saudi Arabia, UAE, Kuwait, Oman, and Qatar
- 7 ports
- 18 shipments
- 6 vessels
- 9 production orders

Example beauty SKUs in the demo:

- `SKU-001` Gentle Face Wash
- `SKU-002` Daily Moisture Lotion
- `SKU-003` Repair Shampoo
- `SKU-004` Nourishing Conditioner
- `SKU-005` Micellar Cleansing Water
- `SKU-006` Vitamin C Serum

## App Sections

### Risk Map

- Interactive network map with locations, routes, and vessels
- Severity-based risk coloring
- Click-to-open location detail panel
- Filters for location type, route visibility, and at-risk locations

### Alerts

- Filterable risk alert cards
- Grouping by severity or location
- Export-friendly table view

### Shipment Detail

- Shipment selector with route and timing detail
- Vessel status when applicable
- Linked alerts for the destination SKU

## Risk Logic

### Inventory

- `days_of_cover = on_hand / avg_daily_demand`
- projected stockout date = `TODAY + days_of_cover`
- alert when projected stockout happens before the next inbound ETA

### Transit

- vessel delay alert when `delay_days > 0`
- stale vessel position when last position update is older than 3 days
- missed ETA for non-vessel shipments that are still open after ETA

### Production

- production slip alert when `actual_completion > planned_completion`

### Severity

- `CRITICAL`: severe stockout gap or vessel delay of 7+ days
- `HIGH`: short stockout gap, low days of cover, or vessel delay of 3-6 days
- `MEDIUM`: early warning inventory or vessel delay of 1-2 days

## Quick Start

### PowerShell

```powershell
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
. .\.venv\Scripts\Activate.ps1
```

The app runs at `http://localhost:8501`.

## Project Structure

```text
SC_Visibility_Risk_Map/
|-- app.py
|-- requirements.txt
|-- data/
|   |-- inventory.csv
|   |-- locations.csv
|   |-- production_orders.csv
|   |-- shipments.csv
|   `-- vessels.csv
|-- logic/
|   |-- __init__.py
|   |-- data_loader.py
|   `-- risk_engine.py
`-- views/
    |-- __init__.py
    |-- alerts_view.py
    |-- location_detail.py
    |-- map_view.py
    `-- shipment_view.py
```

## Data Files

All demo content is loaded from CSV files in `data/`.

- `locations.csv`: plants, distribution centers, and ports with map coordinates
- `inventory.csv`: on-hand stock, daily demand, and safety stock by location and SKU
- `shipments.csv`: planned and in-transit shipments
- `vessels.csv`: vessel position and delay information
- `production_orders.csv`: planned and active plant production orders

This makes the MVP easy to adapt to a different geography or product portfolio without changing the core logic.

## Notes

- The app is intentionally demo-sized and file-based
- Risk calculations are deterministic and based on the snapshot date in `logic/risk_engine.py`
- The sample dataset is synthetic and intended for prototyping and stakeholder demos
