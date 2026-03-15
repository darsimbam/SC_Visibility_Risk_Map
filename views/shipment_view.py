"""Shipment detail view — drill into individual shipments and linked alerts."""

import pandas as pd
import streamlit as st

from logic.risk_engine import TODAY

STATUS_COLOR = {
    "in_transit": "#2ca02c",
    "planned":    "#1f77b4",
    "delivered":  "#888888",
}


def render_shipments(data: dict, alerts: pd.DataFrame) -> None:
    shipments = data["shipments"]
    vessels   = data["vessels"]
    locations = data["locations"]

    if shipments.empty:
        st.info("No shipment data available.")
        return

    loc_lookup    = locations.set_index("location_id")["name"].to_dict()
    vessel_lookup = vessels.set_index("vessel_id") if not vessels.empty else pd.DataFrame()

    # --- Selector ---
    shp_options = {}
    for _, row in shipments.sort_values("status").iterrows():
        delay_flag = ""
        if pd.notna(row.get("vessel_id")) and not vessels.empty:
            v_match = vessels[vessels["vessel_id"] == row["vessel_id"]]
            if not v_match.empty and v_match.iloc[0]["delay_days"] > 0:
                delay_flag = " ⚠"
        label = (
            f"{row['shipment_id']}{delay_flag}  |  "
            f"{row['sku_name']}  |  "
            f"{loc_lookup.get(row['origin_id'], row['origin_id'])} → "
            f"{loc_lookup.get(row['destination_id'], row['destination_id'])}  |  "
            f"{row['status'].replace('_',' ').upper()}"
        )
        shp_options[label] = row["shipment_id"]

    selected = st.selectbox("Select shipment", list(shp_options.keys()), key="shp_select")
    shp_id   = shp_options[selected]
    shp      = shipments[shipments["shipment_id"] == shp_id].iloc[0]

    st.divider()

    # --- Status pill ---
    status_color = STATUS_COLOR.get(shp["status"], "#888")
    delay_days   = (shp["eta"] - shp["original_eta"]).days
    delay_label  = f"  ⚠ +{delay_days} days" if delay_days > 0 else "  ✓ On schedule"

    st.markdown(
        f"""<div style="display:flex;gap:16px;align-items:center;margin-bottom:12px;">
        <span style="background:{status_color};color:#fff;padding:3px 12px;
            border-radius:12px;font-weight:bold;font-size:0.9rem;">
            {shp['status'].replace('_',' ').upper()}
        </span>
        <span style="font-size:0.95rem;">{delay_label}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # --- Detail columns ---
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("**Cargo**")
        st.write(f"SKU: `{shp['sku']}`")
        st.write(f"Product: {shp['sku_name']}")
        st.write(f"Quantity: {shp['qty']:,} units")
        st.write(f"Mode: {shp['transport_mode'].capitalize()}")

    with col_b:
        st.markdown("**Route**")
        st.write(f"From: {loc_lookup.get(shp['origin_id'], shp['origin_id'])}")
        st.write(f"To:   {loc_lookup.get(shp['destination_id'], shp['destination_id'])}")
        st.write(f"Departed: {shp['departure_date'].date()}")

    with col_c:
        st.markdown("**Timeline**")
        st.write(f"Original ETA: {shp['original_eta'].date()}")
        if delay_days > 0:
            st.write(f"Current ETA:  {shp['eta'].date()} ⚠ (+{delay_days} days)")
        else:
            st.write(f"Current ETA:  {shp['eta'].date()} ✓")
        if pd.notna(shp["actual_arrival"]):
            st.write(f"Arrived: {shp['actual_arrival'].date()}")
        else:
            days_to_eta = (shp["eta"] - TODAY).days
            if days_to_eta >= 0:
                st.write(f"Arrives in: **{days_to_eta} day(s)**")
            else:
                st.write(f"Overdue by: **{-days_to_eta} day(s)**")

    st.divider()

    # --- Vessel block ---
    v_id = shp.get("vessel_id")
    if pd.notna(v_id) and not vessel_lookup.empty and v_id in vessel_lookup.index:
        v = vessel_lookup.loc[v_id]
        days_since = (TODAY - v["last_position_update"]).days
        stale_warn = f" ⚠ Position data {days_since} days old" if days_since > 3 else " ✓ Live position"

        if v["delay_days"] > 0:
            st.warning(
                f"**Vessel: {v['vessel_name']}** — "
                f"Delayed **+{v['delay_days']} days** · "
                f"New ETA: {v['estimated_eta'].date()}{stale_warn}"
            )
        else:
            st.success(
                f"**Vessel: {v['vessel_name']}** — "
                f"On schedule · ETA: {v['estimated_eta'].date()}{stale_warn}"
            )

        vc1, vc2 = st.columns(2)
        vc1.write(f"Current position: {v['current_lat']:.1f}°N, {v['current_lon']:.1f}°E")
        vc1.write(f"Last update: {v['last_position_update'].date()}")
        vc2.write(f"Scheduled ETA: {v['scheduled_eta'].date()}")
        vc2.write(f"Estimated ETA: {v['estimated_eta'].date()}")
    else:
        st.caption(f"Transport mode: {shp['transport_mode'].capitalize()} (no vessel tracking)")

    # --- Linked alerts ---
    st.divider()
    st.markdown("**Alerts at destination for this SKU**")
    if not alerts.empty:
        linked = alerts[
            (alerts["location_id"] == shp["destination_id"])
            & (alerts["sku"] == shp["sku"])
        ]
        if not linked.empty:
            for _, a in linked.iterrows():
                dot = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(a["severity"], "⚪")
                st.warning(
                    f"{dot} **{a['severity']} — {a['risk_type']}**  \n"
                    f"{a['message']}  \n"
                    f"**Action:** {a['recommended_action']}"
                )
        else:
            st.success("No active risk alerts at this destination for this SKU.")
    else:
        st.success("No active alerts.")

    # --- Notes ---
    if pd.notna(shp.get("notes")) and str(shp["notes"]).strip():
        st.divider()
        st.caption(f"Notes: {shp['notes']}")
