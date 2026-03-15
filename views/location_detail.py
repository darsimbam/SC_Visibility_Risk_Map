"""Location detail panel — rendered in the right column when a map point is clicked."""

from datetime import timedelta

import pandas as pd
import streamlit as st

from logic.risk_engine import SEVERITY_ORDER, TODAY

SEVERITY_COLOR = {
    "CRITICAL": "#d62728",
    "HIGH":     "#ff7f0e",
    "MEDIUM":   "#c9a800",
    "OK":       "#2ca02c",
}

TYPE_ICON = {"plant": "🏭", "distributor": "🏪", "port": "⚓"}


def _worst_severity(loc_id: str, alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return "OK"
    sub = alerts[alerts["location_id"] == loc_id]
    if sub.empty:
        return "OK"
    return sub.sort_values("severity", key=lambda s: s.map(SEVERITY_ORDER)).iloc[0]["severity"]


def _doc_bar_color(doc: float) -> str:
    if doc < 3:
        return "#d62728"
    if doc < 7:
        return "#ff7f0e"
    if doc < 14:
        return "#f7c948"
    return "#2ca02c"


def render_location_detail(loc_id: str, data: dict, alerts: pd.DataFrame) -> None:
    locations    = data["locations"]
    inventory    = data["inventory"]
    prod_orders  = data["production_orders"]
    shipments    = data["shipments"]
    vessels      = data["vessels"]

    loc_row = locations[locations["location_id"] == loc_id]
    if loc_row.empty:
        st.info("Location data not found.")
        return
    loc = loc_row.iloc[0]

    # ── Header ────────────────────────────────────────────────────────────────
    icon    = TYPE_ICON.get(loc["type"], "📍")
    sev     = _worst_severity(loc_id, alerts)
    sev_col = SEVERITY_COLOR.get(sev, SEVERITY_COLOR["OK"])

    st.markdown(
        f"<h3 style='margin-bottom:2px'>{icon} {loc['name']}</h3>"
        f"<span style='color:#64748b;font-size:0.85rem'>"
        f"{loc['type'].capitalize()} · {loc['country']} · {loc['region']}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<span style='background:{sev_col};color:#fff;padding:3px 12px;"
        f"border-radius:12px;font-size:0.8rem;font-weight:700'>"
        f"{'⚠ ' if sev != 'OK' else '✓ '}{sev} RISK</span>",
        unsafe_allow_html=True,
    )
    st.write("")  # spacing

    loc_alerts = alerts[alerts["location_id"] == loc_id] if not alerts.empty else pd.DataFrame()

    # ── DISTRIBUTOR ───────────────────────────────────────────────────────────
    if loc["type"] == "distributor":
        inv = inventory[
            (inventory["location_id"] == loc_id) & (inventory["avg_daily_demand"] > 0)
        ].copy()

        if not inv.empty:
            st.markdown("**Inventory Status**")
            for _, row in inv.iterrows():
                doc     = row["on_hand"] / row["avg_daily_demand"]
                so_date = TODAY + timedelta(days=doc)
                bar_col = _doc_bar_color(doc)

                # Next inbound
                inbound_shp = shipments[
                    (shipments["destination_id"] == loc_id)
                    & (shipments["sku"] == row["sku"])
                    & shipments["actual_arrival"].isna()
                ].sort_values("eta")
                next_eta = inbound_shp.iloc[0]["eta"].date() if not inbound_shp.empty else "—"

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(
                        f"<b>{row['sku']}</b> — {row['sku_name']}",
                        unsafe_allow_html=True,
                    )
                    c2.markdown(
                        f"<span style='color:{bar_col};font-weight:700'>{doc:.1f}d</span>",
                        unsafe_allow_html=True,
                    )
                    st.progress(min(doc / 30, 1.0), text=f"{row['on_hand']:,} units on hand")
                    st.caption(
                        f"Demand: {row['avg_daily_demand']} /day · "
                        f"Stockout ~{so_date.date()} · "
                        f"Next replenishment: {next_eta}"
                    )

        # Inbound shipments
        inbound = shipments[
            (shipments["destination_id"] == loc_id)
            & (shipments["status"].isin(["in_transit", "planned"]))
            & shipments["actual_arrival"].isna()
        ].sort_values("eta")

        if not inbound.empty:
            st.markdown("**Inbound Shipments**")
            for _, shp in inbound.iterrows():
                delay = (shp["eta"] - shp["original_eta"]).days
                flag  = f" ⚠ +{delay}d" if delay > 0 else " ✓"
                st.markdown(
                    f"- **{shp['shipment_id']}** · {shp['sku_name']} · "
                    f"{shp['qty']:,} units · {shp['transport_mode']} · "
                    f"ETA {shp['eta'].date()}{flag}"
                )

    # ── PLANT ─────────────────────────────────────────────────────────────────
    elif loc["type"] == "plant":
        pos = prod_orders[prod_orders["plant_id"] == loc_id]

        if not pos.empty:
            st.markdown("**Production Orders**")
            for _, po in pos.iterrows():
                slip = (po["actual_completion"] - po["planned_completion"]).days
                pct  = (po["actual_qty"] / po["planned_qty"] * 100) if po["planned_qty"] > 0 else 0
                status_col = "#d62728" if slip > 7 else "#ff7f0e" if slip > 0 else "#2ca02c"
                slip_txt   = f"⚠ +{slip}d slip" if slip > 0 else "✓ On schedule"

                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(f"**{po['order_id']}** — {po['sku_name']}")
                    c2.markdown(
                        f"<span style='color:{status_col};font-weight:700'>{slip_txt}</span>",
                        unsafe_allow_html=True,
                    )
                    if po["status"] != "planned":
                        st.progress(min(pct / 100, 1.0), text=f"{pct:.0f}% complete")
                    st.caption(
                        f"{po['planned_qty']:,} units planned · "
                        f"Complete by {po['actual_completion'].date()} · "
                        f"Status: {po['status'].replace('_',' ').title()}"
                    )

        # Outbound shipments from plant
        outbound = shipments[
            (shipments["origin_id"] == loc_id)
            & (shipments["status"].isin(["in_transit", "planned"]))
        ].sort_values("eta")
        if not outbound.empty:
            st.markdown("**Outbound Shipments**")
            for _, shp in outbound.iterrows():
                st.markdown(
                    f"- **{shp['shipment_id']}** · {shp['sku_name']} · "
                    f"{shp['qty']:,} units → {shp['destination_id']} · "
                    f"ETA {shp['eta'].date()} · {shp['transport_mode']}"
                )

    # ── PORT ──────────────────────────────────────────────────────────────────
    elif loc["type"] == "port":
        # Vessels heading to this port
        port_vessels = vessels[
            (vessels["destination_port_id"] == loc_id) | (vessels["origin_port_id"] == loc_id)
        ]
        if not port_vessels.empty:
            st.markdown("**Vessels**")
            for _, v in port_vessels.iterrows():
                direction = "→ arriving" if v["destination_port_id"] == loc_id else "departed ←"
                delay_txt = f"⚠ +{v['delay_days']}d" if v["delay_days"] > 0 else "✓ On schedule"
                days_since = (TODAY - v["last_position_update"]).days
                stale = f" · position {days_since}d old" if days_since > 3 else ""
                st.markdown(
                    f"- **{v['vessel_name']}** {direction} · "
                    f"{delay_txt} · ETA {v['estimated_eta'].date()}{stale}"
                )

        # Active shipments through this port
        port_shp = shipments[
            (shipments["origin_id"] == loc_id) | (shipments["destination_id"] == loc_id)
        ]
        active_port_shp = port_shp[port_shp["status"].isin(["in_transit", "planned"])]
        if not active_port_shp.empty:
            st.markdown("**Active Shipments**")
            for _, shp in active_port_shp.iterrows():
                direction = "→ OUT" if shp["origin_id"] == loc_id else "← IN"
                st.markdown(
                    f"- **{shp['shipment_id']}** {direction} · {shp['sku_name']} · "
                    f"{shp['qty']:,} units · ETA {shp['eta'].date()}"
                )

    # ── Alerts (all types) ─────────────────────────────────────────────────────
    if not loc_alerts.empty:
        st.divider()
        st.markdown("**Active Alerts**")
        for _, a in loc_alerts.iterrows():
            dot = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(a["severity"], "⚪")
            with st.expander(f"{dot} {a['severity']} — {a['risk_type']}"):
                st.write(a["message"])
                st.caption(f"**Action:** {a['recommended_action']}")
