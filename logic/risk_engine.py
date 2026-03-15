"""
Risk calculation engine.

Rules:
- Inventory risk : days_of_cover = on_hand / avg_daily_demand
                   Alert when stockout_date is earlier than next inbound ETA
- Transit risk   : vessel delayed, stale position, or missed ETA
- Production risk: actual_completion later than planned_completion
"""

from datetime import timedelta
import pandas as pd

# Simulated "today" matches the demo data snapshot
TODAY = pd.Timestamp("2026-03-15")

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def days_of_cover(on_hand: float, avg_daily_demand: float) -> float:
    if avg_daily_demand <= 0:
        return float("inf")
    return on_hand / avg_daily_demand


def projected_stockout_date(on_hand: float, avg_daily_demand: float) -> pd.Timestamp | None:
    doc = days_of_cover(on_hand, avg_daily_demand)
    if doc == float("inf"):
        return None
    return TODAY + timedelta(days=doc)


def get_next_inbound(location_id: str, sku: str, shipments: pd.DataFrame):
    """Return (eta, shipment_id, status) for the earliest pending inbound."""
    not_arrived = shipments["actual_arrival"].isna()

    # Prefer confirmed in-transit over planned
    for status in ("in_transit", "planned"):
        mask = (
            (shipments["destination_id"] == location_id)
            & (shipments["sku"] == sku)
            & (shipments["status"] == status)
            & not_arrived
        )
        subset = shipments[mask]
        if not subset.empty:
            idx = subset["eta"].idxmin()
            row = subset.loc[idx]
            return row["eta"], row["shipment_id"], status

    return None, None, None


def worst_severity(*severities: str) -> str:
    """Return the most severe (lowest order number) from a list."""
    return min(severities, key=lambda s: SEVERITY_ORDER.get(s, 99))


# ---------------------------------------------------------------------------
# Inventory alerts
# ---------------------------------------------------------------------------

def calculate_inventory_alerts(inventory: pd.DataFrame, shipments: pd.DataFrame) -> list[dict]:
    alerts = []

    for _, row in inventory.iterrows():
        if row["avg_daily_demand"] <= 0:
            continue  # Plants / production buffers — skip

        doc = days_of_cover(row["on_hand"], row["avg_daily_demand"])
        so_date = projected_stockout_date(row["on_hand"], row["avg_daily_demand"])
        next_eta, shp_id, shp_status = get_next_inbound(
            row["location_id"], row["sku"], shipments
        )

        # Determine base severity from days of cover
        if doc < 3:
            severity = "CRITICAL"
        elif doc < 7:
            severity = "HIGH"
        elif doc < 14:
            severity = "MEDIUM"
        else:
            continue  # Healthy — no alert

        if next_eta is not None and so_date is not None:
            gap_days = (next_eta - so_date).days
            if gap_days > 0:
                # Replenishment arrives AFTER stockout
                severity = "CRITICAL" if gap_days >= 5 else "HIGH"
                risk_type = "STOCKOUT_BEFORE_REPLENISHMENT"
                status_label = "planned" if shp_status == "planned" else "in transit"
                message = (
                    f"Stock of {row['sku_name']} runs out {so_date.date()} "
                    f"({doc:.1f} days of cover). "
                    f"Next replenishment ({shp_id}, {status_label}) arrives "
                    f"{next_eta.date()} — {gap_days}-day gap."
                )
                root_cause = (
                    "High demand rate combined with delayed or long-lead-time inbound supply"
                )
                action = (
                    f"Expedite {shp_id} or arrange emergency stock. "
                    "Consider air freight or regional transfer."
                )
            else:
                # Replenishment arrives before or on stockout — low stock warning
                risk_type = "LOW_INVENTORY"
                message = (
                    f"{doc:.1f} days of cover for {row['sku_name']}. "
                    f"Replenishment ({shp_id}) ETA {next_eta.date()} — tight but before stockout."
                )
                root_cause = "Stock approaching minimum threshold"
                action = "Monitor closely. Confirm shipment is on track."
        else:
            risk_type = "NO_REPLENISHMENT_PLANNED"
            if next_eta is None:
                severity = worst_severity(severity, "HIGH")
            message = (
                f"Only {doc:.1f} days of cover for {row['sku_name']}. "
                + ("No inbound shipment scheduled." if next_eta is None else "")
            )
            root_cause = "Low stock with no confirmed inbound supply"
            action = "Arrange replenishment immediately."

        alerts.append(
            {
                "alert_id": f"INV-{row['location_id']}-{row['sku']}",
                "severity": severity,
                "sku": row["sku"],
                "sku_name": row["sku_name"],
                "location_id": row["location_id"],
                "risk_type": risk_type,
                "message": message,
                "root_cause": root_cause,
                "recommended_action": action,
                "stockout_date": so_date,
                "days_of_cover": round(doc, 1),
                "next_replenishment_eta": next_eta,
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Transit alerts
# ---------------------------------------------------------------------------

def calculate_transit_alerts(shipments: pd.DataFrame, vessels: pd.DataFrame) -> list[dict]:
    alerts = []

    # Vessel delays
    for _, v in vessels.iterrows():
        if v["delay_days"] <= 0:
            continue

        days_since_update = (TODAY - v["last_position_update"]).days
        stale_position = days_since_update > 3

        severity = "CRITICAL" if v["delay_days"] >= 7 else "HIGH" if v["delay_days"] >= 3 else "MEDIUM"

        affected = shipments[
            shipments["vessel_id"].notna() & (shipments["vessel_id"] == v["vessel_id"])
        ]

        for _, shp in affected.iterrows():
            stale_note = (
                f" Position data is {days_since_update} days old — vessel location unconfirmed."
                if stale_position
                else ""
            )
            message = (
                f"Vessel {v['vessel_name']} carrying {shp['sku_name']} ({shp['shipment_id']}) "
                f"is {v['delay_days']} days late. "
                f"New estimated arrival: {v['estimated_eta'].date()}."
                + stale_note
            )
            risk_type = "VESSEL_DELAY"
            if stale_position:
                risk_type += " + STALE_POSITION"

            alerts.append(
                {
                    "alert_id": f"TRN-{shp['shipment_id']}",
                    "severity": severity,
                    "sku": shp["sku"],
                    "sku_name": shp["sku_name"],
                    "location_id": shp["destination_id"],
                    "risk_type": risk_type,
                    "message": message,
                    "root_cause": (
                        f"Vessel {v['vessel_name']} delayed "
                        f"(weather, port congestion, or routing change)"
                    ),
                    "recommended_action": (
                        "Update downstream ETAs. Assess stockout risk at destination. "
                        "Consider air freight for critical SKUs."
                    ),
                    "stockout_date": None,
                    "days_of_cover": None,
                    "next_replenishment_eta": v["estimated_eta"],
                }
            )

    # Overdue non-vessel shipments (truck/rail past ETA with no arrival)
    truck_overdue = shipments[
        (shipments["status"] == "in_transit")
        & shipments["vessel_id"].isna()
        & shipments["actual_arrival"].isna()
        & (shipments["eta"] < TODAY)
    ]
    for _, shp in truck_overdue.iterrows():
        days_late = (TODAY - shp["eta"]).days
        severity = "HIGH" if days_late >= 2 else "MEDIUM"
        alerts.append(
            {
                "alert_id": f"TRN-LATE-{shp['shipment_id']}",
                "severity": severity,
                "sku": shp["sku"],
                "sku_name": shp["sku_name"],
                "location_id": shp["destination_id"],
                "risk_type": "MISSED_ETA",
                "message": (
                    f"Shipment {shp['shipment_id']} of {shp['sku_name']} is "
                    f"{days_late} day(s) past ETA with no arrival confirmed."
                ),
                "root_cause": "Shipment overdue — no status update received from carrier",
                "recommended_action": (
                    "Contact carrier for live status. "
                    "Prepare contingency stock if delivery cannot be confirmed."
                ),
                "stockout_date": None,
                "days_of_cover": None,
                "next_replenishment_eta": None,
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Production alerts
# ---------------------------------------------------------------------------

def calculate_production_alerts(production_orders: pd.DataFrame) -> list[dict]:
    alerts = []

    for _, po in production_orders.iterrows():
        if po["status"] in ("completed", "planned"):
            continue

        slip_days = (po["actual_completion"] - po["planned_completion"]).days
        if slip_days <= 0:
            continue

        completion_pct = (
            (po["actual_qty"] / po["planned_qty"] * 100) if po["planned_qty"] > 0 else 0
        )
        severity = "HIGH" if slip_days >= 7 else "MEDIUM"

        alerts.append(
            {
                "alert_id": f"PRD-{po['order_id']}",
                "severity": severity,
                "sku": po["sku"],
                "sku_name": po["sku_name"],
                "location_id": po["plant_id"],
                "risk_type": "PRODUCTION_SLIP",
                "message": (
                    f"Order {po['order_id']} for {po['sku_name']} slipped {slip_days} days. "
                    f"New completion: {po['actual_completion'].date()} "
                    f"(was {po['planned_completion'].date()}). "
                    f"{completion_pct:.0f}% complete "
                    f"({po['actual_qty']:,}/{po['planned_qty']:,} units)."
                ),
                "root_cause": po.get("notes", "Production delay"),
                "recommended_action": (
                    "Expedite production. Reallocate available stock to priority distributors. "
                    "Notify logistics to adjust outbound shipment schedules."
                ),
                "stockout_date": None,
                "days_of_cover": None,
                "next_replenishment_eta": po["actual_completion"],
            }
        )

    return alerts


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_risk_engine(data: dict) -> pd.DataFrame:
    """Run all risk checks and return a sorted alerts DataFrame."""
    inv_alerts = calculate_inventory_alerts(data["inventory"], data["shipments"])
    trn_alerts = calculate_transit_alerts(data["shipments"], data["vessels"])
    prd_alerts = calculate_production_alerts(data["production_orders"])

    all_alerts = inv_alerts + trn_alerts + prd_alerts

    if not all_alerts:
        return pd.DataFrame(
            columns=[
                "alert_id", "severity", "sku", "sku_name", "location_id",
                "risk_type", "message", "root_cause", "recommended_action",
                "stockout_date", "days_of_cover", "next_replenishment_eta",
            ]
        )

    df = pd.DataFrame(all_alerts)
    df["_order"] = df["severity"].map(SEVERITY_ORDER)
    df = df.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    return df
