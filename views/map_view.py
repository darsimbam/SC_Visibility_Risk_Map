"""Risk map view — click any location to see its detail panel."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from logic.risk_engine import SEVERITY_ORDER, TODAY
from views.location_detail import render_location_detail

# ── Visual constants ──────────────────────────────────────────────────────────

SEVERITY_COLOR = {
    "CRITICAL": "#d62728",
    "HIGH":     "#ff7f0e",
    "MEDIUM":   "#c9a800",
    "OK":       "#4e79a7",
}

# Marker size grows with risk severity
SEVERITY_SIZE = {"CRITICAL": 28, "HIGH": 22, "MEDIUM": 18, "OK": 14}

# Distinct Plotly Maki shapes — one per location type
TYPE_SYMBOL = {"plant": "square", "distributor": "circle", "port": "diamond"}

# Route colors by mode (plain mode) + red override when vessel is delayed
MODE_COLOR = {"ocean": "#4e79a7", "air": "#9467bd", "truck": "#59a14f"}

VESSEL_COLOR = {"on_schedule": "#2ca02c", "minor_delay": "#f7c948", "delayed": "#d62728"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _short_label(name: str) -> str:
    for s in [" Distribution Center", " Manufacturing Plant",
              " Skin Care Plant", " Personal Care Plant", " Production Facility"]:
        name = name.replace(s, "")
    return name.replace("Port of ", "").replace("Port Of ", "").strip()


def _location_risk(loc_id: str, alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return "OK"
    sub = alerts[alerts["location_id"] == loc_id]
    if sub.empty:
        return "OK"
    return sub.sort_values("severity", key=lambda s: s.map(SEVERITY_ORDER)).iloc[0]["severity"]


def _route_color(shp: pd.Series, delayed_vessels: set) -> str:
    if shp["status"] == "planned":
        return "#cccccc"
    vid = shp.get("vessel_id")
    if pd.notna(vid) and vid in delayed_vessels:
        return "#d62728"
    return MODE_COLOR.get(shp.get("transport_mode", "truck"), "#888888")


# ── Main render ───────────────────────────────────────────────────────────────

def render_map(data: dict, alerts: pd.DataFrame) -> None:
    locations = data["locations"]
    shipments = data["shipments"]
    vessels   = data["vessels"]

    # ── Summary banner ────────────────────────────────────────────────────────
    n_active  = len(shipments[shipments["status"] == "in_transit"])
    n_delayed = len(vessels[vessels["delay_days"] > 0])

    if not alerts.empty:
        counts = alerts["severity"].value_counts()
        parts  = [f"**{counts[s]} {s}**" for s in ["CRITICAL","HIGH","MEDIUM"] if counts.get(s,0) > 0]
        alert_text = " · ".join(parts) if parts else "No active alerts"
    else:
        alert_text = "No active alerts"

    st.info(
        f"📍 {len(locations)} locations · 🚢 {n_active} shipments in transit · "
        f"⚓ {len(vessels)} vessels ({n_delayed} delayed) · Alerts: {alert_text}"
    )

    # ── Filters ───────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 3, 2])
    with fc1:
        show_types = st.multiselect(
            "Location types", ["plant","distributor","port"],
            default=["plant","distributor","port"], key="map_types",
        )
    with fc2:
        route_filter = st.radio(
            "Routes", ["In transit only","All (incl. planned)","Hide"],
            index=0, horizontal=True, key="map_routes",
        )
    with fc3:
        risk_only = st.checkbox("At-risk locations only", value=False, key="map_risk_only")

    # ── Prepare data ──────────────────────────────────────────────────────────
    delayed_vessels = set(vessels.loc[vessels["delay_days"] > 0, "vessel_id"].dropna())

    filtered_locs = locations[locations["type"].isin(show_types)].copy()
    if risk_only:
        alert_locs = set(alerts["location_id"]) if not alerts.empty else set()
        filtered_locs = filtered_locs[
            (filtered_locs["type"] != "distributor") | filtered_locs["location_id"].isin(alert_locs)
        ]

    if route_filter == "In transit only":
        route_shp = shipments[shipments["status"] == "in_transit"]
    elif route_filter == "All (incl. planned)":
        route_shp = shipments[shipments["status"].isin(["in_transit","planned"])]
    else:
        route_shp = pd.DataFrame()

    loc_coord = locations.set_index("location_id")[["lat","lon"]]

    # ── Build figure ──────────────────────────────────────────────────────────
    fig = go.Figure()

    # Route lines (drawn first so markers sit on top)
    if not route_shp.empty:
        for _, shp in route_shp.iterrows():
            if shp["origin_id"] not in loc_coord.index or shp["destination_id"] not in loc_coord.index:
                continue
            o, d    = loc_coord.loc[shp["origin_id"]], loc_coord.loc[shp["destination_id"]]
            color   = _route_color(shp, delayed_vessels)
            width   = 2.5 if shp["transport_mode"] == "ocean" else 1.8
            delay_flag = " ⚠ DELAYED" if (pd.notna(shp.get("vessel_id")) and shp.get("vessel_id") in delayed_vessels) else ""
            eta_note   = f"Delayed — was {shp['original_eta'].date()}" if shp["eta"] != shp["original_eta"] else f"On schedule"

            fig.add_trace(go.Scattermapbox(
                lat=[o["lat"], d["lat"]], lon=[o["lon"], d["lon"]],
                mode="lines",
                line=dict(width=width, color=color),
                hovertext=(
                    f"<b>{shp['shipment_id']}{delay_flag}</b><br>"
                    f"{shp['sku_name']} · {shp['qty']:,} units<br>"
                    f"Mode: {shp['transport_mode'].capitalize()}<br>"
                    f"ETA: {shp['eta'].date()} · {eta_note}"
                ),
                hoverinfo="text", showlegend=False,
            ))

    # Location markers — one trace per type, using customdata for click events
    # Legend labels include emoji (renders in legend); map labels are plain text
    TYPE_LEGEND = {
        "plant":       "🏭  Plants",
        "distributor": "🏪  Distribution Centers",
        "port":        "⚓  Ports",
    }

    for loc_type in ["plant", "distributor", "port"]:
        subset = filtered_locs[filtered_locs["type"] == loc_type]
        if subset.empty:
            continue

        colors, sizes, labels, hovers, custom = [], [], [], [], []

        for _, loc in subset.iterrows():
            sev = _location_risk(loc["location_id"], alerts)
            colors.append(SEVERITY_COLOR.get(sev, SEVERITY_COLOR["OK"]))
            sizes.append(SEVERITY_SIZE.get(sev, 14))
            labels.append(_short_label(loc["name"]))   # plain name, no emoji
            custom.append(loc["location_id"])

            loc_alts = alerts[alerts["location_id"] == loc["location_id"]] if not alerts.empty else pd.DataFrame()
            alert_lines = (
                "<br>".join(f"  [{a['severity']}] {a['risk_type']}" for _, a in loc_alts.iterrows())
                if not loc_alts.empty else "  No active alerts"
            )
            hovers.append(
                f"<b>{loc['name']}</b><br>"
                f"{loc['type'].capitalize()} · {loc['country']}<br>"
                f"Risk: <b>{sev}</b><br>{alert_lines}<br>"
                f"<i>Click to see full details</i>"
            )

        fig.add_trace(go.Scattermapbox(
            lat=subset["lat"].tolist(),
            lon=subset["lon"].tolist(),
            mode="markers+text",
            marker=dict(
                size=sizes,
                color=colors,
                symbol=TYPE_SYMBOL[loc_type],  # square / circle / diamond
                opacity=1.0,
            ),
            text=labels,
            textposition="top center",
            textfont=dict(size=11, color="#1e293b"),
            customdata=custom,
            name=TYPE_LEGEND[loc_type],
            hovertext=hovers,
            hoverinfo="text",
        ))

    # Vessel markers
    if not vessels.empty:
        v_colors = [VESSEL_COLOR.get(s, "#888") for s in vessels["status"]]
        v_hovers, v_labels = [], []
        for _, v in vessels.iterrows():
            days_since = (TODAY - v["last_position_update"]).days
            stale      = f" ⚠ Position {days_since}d old" if days_since > 3 else " ✓ Live"
            delay_txt  = f"Delayed +{v['delay_days']}d" if v["delay_days"] > 0 else "On schedule"
            v_hovers.append(
                f"<b>{v['vessel_name']}</b><br>{delay_txt}<br>"
                f"ETA: {v['estimated_eta'].date()}{stale}"
            )
            v_labels.append(v["vessel_name"].split()[0])  # first word only

        fig.add_trace(go.Scattermapbox(
            lat=vessels["current_lat"].tolist(), lon=vessels["current_lon"].tolist(),
            mode="markers+text",
            marker=dict(size=16, color=v_colors, symbol="ferry", opacity=1.0),
            text=v_labels, textposition="top right",
            textfont=dict(size=10, color="#1e293b"),
            name="🚢  Vessels",
            hovertext=v_hovers, hoverinfo="text",
        ))

    # Auto-center on data
    all_lats = list(filtered_locs["lat"]) + list(vessels["current_lat"])
    all_lons = list(filtered_locs["lon"]) + list(vessels["current_lon"])
    c_lat = sum(all_lats) / len(all_lats) if all_lats else 35
    c_lon = sum(all_lons) / len(all_lons) if all_lons else 35

    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox=dict(center=dict(lat=c_lat, lon=c_lon), zoom=3.5),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        legend=dict(
            orientation="v",
            yanchor="top", y=0.99,
            xanchor="left", x=0.01,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#e2e8f0", borderwidth=1,
            font=dict(size=13),
        ),
    )

    # ── Two-column layout: map left, detail right ─────────────────────────────
    map_col, detail_col = st.columns([3, 2])

    with map_col:
        # Render the chart and capture click events
        event = st.plotly_chart(
            fig, use_container_width=True,
            on_select="rerun", key="risk_map_chart",
        )

        # Extract clicked location_id from customdata
        if event.selection.points:
            pt = event.selection.points[0]
            clicked_id = pt.get("customdata")
            if clicked_id:
                st.session_state["selected_location"] = clicked_id

        st.caption(
            "**Shapes:** ■ Plant · ● Distribution Center · ◆ Port · 🚢 Vessel  "
            "| **Size** = risk severity  "
            "| **Routes:** solid = ocean · dashed = air · dotted = truck · red = delayed"
        )

    with detail_col:
        selected = st.session_state.get("selected_location")

        if selected and selected in locations["location_id"].values:
            # Clear button
            if st.button("✕ Clear selection", key="clear_loc"):
                st.session_state.pop("selected_location", None)
                st.rerun()
            st.divider()
            render_location_detail(selected, data, alerts)
        else:
            st.markdown(
                """
                <div style="
                    height: 460px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    color: #94a3b8;
                    border: 2px dashed #cbd5e1;
                    border-radius: 12px;
                    text-align: center;
                    padding: 24px;
                ">
                    <div style="font-size: 2.5rem">📍</div>
                    <div style="font-size: 1.1rem; font-weight: 600; margin-top: 12px;">
                        Click any location on the map
                    </div>
                    <div style="font-size: 0.85rem; margin-top: 6px;">
                        Plants, Distribution Centers, and Ports<br>
                        will show inventory, production, or vessel details here.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
