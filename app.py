"""
Supply Chain Visibility & Risk Dashboard
Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="SC Risk Dashboard",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

from logic.data_loader import load_all
from logic.risk_engine import run_risk_engine, TODAY
from views.map_view import render_map
from views.alerts_view import render_alerts
from views.shipment_view import render_shipments


@st.cache_data(ttl=60)
def get_data():
    return load_all()


@st.cache_data(ttl=60)
def get_alerts(_data):
    return run_risk_engine(_data)


def _kpi_card(col, label: str, value, bg: str, fg: str = "#fff") -> None:
    col.markdown(
        f"""<div style="background:{bg};border-radius:10px;padding:16px 20px;text-align:center;">
            <div style="font-size:0.75rem;font-weight:600;color:{fg};opacity:0.85;
                        text-transform:uppercase;letter-spacing:0.05em">{label}</div>
            <div style="font-size:2rem;font-weight:800;color:{fg};line-height:1.1">{value}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def _sidebar(data: dict, alerts: pd.DataFrame) -> None:
    st.sidebar.markdown(
        "<div style='font-size:1.15rem;font-weight:800;color:#2563EB'>SC Risk Dashboard</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"Snapshot: **{TODAY.date()}**")
    st.sidebar.divider()

    # Alert summary
    st.sidebar.markdown("**Alert Summary**")
    if alerts.empty:
        st.sidebar.success("All clear — no active alerts")
    else:
        counts = alerts["severity"].value_counts()
        for sev, emoji, color in [
            ("CRITICAL", "🔴", "#d62728"),
            ("HIGH",     "🟠", "#ff7f0e"),
            ("MEDIUM",   "🟡", "#c9a800"),
        ]:
            n = counts.get(sev, 0)
            if n:
                st.sidebar.markdown(
                    f"<div style='display:flex;justify-content:space-between;"
                    f"padding:4px 0'><span>{emoji} {sev.capitalize()}</span>"
                    f"<span style='font-weight:700;color:{color}'>{n}</span></div>",
                    unsafe_allow_html=True,
                )

    st.sidebar.divider()

    # Network snapshot
    locs = data["locations"]
    shps = data["shipments"]
    vess = data["vessels"]
    n_delayed = len(vess[vess["delay_days"] > 0])

    st.sidebar.markdown("**Network**")
    rows = [
        ("🏭 Plants",               len(locs[locs["type"] == "plant"])),
        ("🏪 Distribution Centers", len(locs[locs["type"] == "distributor"])),
        ("⚓ Ports",                len(locs[locs["type"] == "port"])),
        ("🚢 Shipments in transit", len(shps[shps["status"] == "in_transit"])),
        ("📡 Vessels tracked",      len(vess)),
    ]
    for label, val in rows:
        st.sidebar.markdown(
            f"<div style='display:flex;justify-content:space-between;padding:3px 0'>"
            f"<span>{label}</span><span style='font-weight:700'>{val}</span></div>",
            unsafe_allow_html=True,
        )
    if n_delayed:
        st.sidebar.warning(f"⚠ {n_delayed} vessel(s) delayed")

    st.sidebar.divider()
    st.sidebar.caption(
        "Days of cover = on_hand ÷ avg_daily_demand.  "
        "Alert fires when stockout date < next inbound ETA."
    )


def main():
    data   = get_data()
    alerts = get_alerts(data)

    _sidebar(data, alerts)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='margin-bottom:2px'>Supply Chain Visibility & Risk</h1>"
        "<p style='color:#64748b;margin-top:0'>Europe → Gulf beauty & personal care network</p>",
        unsafe_allow_html=True,
    )

    # ── KPI row ───────────────────────────────────────────────────────────────
    locs = data["locations"]
    shps = data["shipments"]
    vess = data["vessels"]
    counts = alerts["severity"].value_counts() if not alerts.empty else {}

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    _kpi_card(k1, "Critical", counts.get("CRITICAL", 0), "#d62728")
    _kpi_card(k2, "High",     counts.get("HIGH",     0), "#ff7f0e")
    _kpi_card(k3, "Medium",   counts.get("MEDIUM",   0), "#c9a800")
    _kpi_card(k4, "In Transit", len(shps[shps["status"] == "in_transit"]), "#2563EB")
    _kpi_card(k5, "Vessels Delayed", len(vess[vess["delay_days"] > 0]),
              "#7c3aed" if len(vess[vess["delay_days"] > 0]) > 0 else "#4e79a7")
    _kpi_card(k6, "Locations", len(locs), "#0f766e")

    st.write("")  # breathing room

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_map, tab_alerts, tab_shipments = st.tabs(
        ["🗺  Risk Map", "🚨  Alerts", "📦  Shipment Detail"]
    )

    with tab_map:
        render_map(data, alerts)

    with tab_alerts:
        render_alerts(alerts, data)

    with tab_shipments:
        render_shipments(data, alerts)


if __name__ == "__main__":
    main()
