"""Alerts view — filterable risk alert cards with summary metrics."""

import pandas as pd
import streamlit as st

SEVERITY_BADGE = {
    "CRITICAL": "🔴 CRITICAL",
    "HIGH":     "🟠 HIGH",
    "MEDIUM":   "🟡 MEDIUM",
    "LOW":      "🟢 LOW",
}

SEVERITY_BG = {
    "CRITICAL": "#fff0f0",
    "HIGH":     "#fff5eb",
    "MEDIUM":   "#fffce8",
    "LOW":      "#f0fff0",
}

SEVERITY_BORDER = {
    "CRITICAL": "#d62728",
    "HIGH":     "#ff7f0e",
    "MEDIUM":   "#c9a800",
    "LOW":      "#2ca02c",
}

RISK_TYPE_LABEL = {
    "STOCKOUT_BEFORE_REPLENISHMENT": "Projected Stockout",
    "LOW_INVENTORY":                 "Low Inventory",
    "NO_REPLENISHMENT_PLANNED":      "No Replenishment",
    "VESSEL_DELAY":                  "Vessel Delay",
    "VESSEL_DELAY + STALE_POSITION": "Vessel Delay + Stale Position",
    "MISSED_ETA":                    "Missed ETA",
    "PRODUCTION_SLIP":               "Production Slip",
}


def render_alerts(alerts: pd.DataFrame, data: dict) -> None:
    if alerts.empty:
        st.success("No active alerts. All supply chain signals are within thresholds.")
        return

    loc_lookup = data["locations"].set_index("location_id")["name"].to_dict()

    # --- Filters ---
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sev_opts = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        sev_filter = st.multiselect(
            "Severity", sev_opts,
            default=[s for s in sev_opts if s in alerts["severity"].values],
            key="al_sev",
        )
    with fc2:
        type_opts = sorted(alerts["risk_type"].unique())
        type_filter = st.multiselect(
            "Risk type", type_opts, default=type_opts, key="al_type"
        )
    with fc3:
        group_by = st.radio(
            "Group by", ["Severity", "Location", "None"],
            horizontal=True, key="al_group"
        )

    filtered = alerts[
        alerts["severity"].isin(sev_filter) & alerts["risk_type"].isin(type_filter)
    ]

    if filtered.empty:
        st.info("No alerts match the current filters.")
        return

    st.caption(f"Showing **{len(filtered)}** of {len(alerts)} alerts")

    def _card(row: pd.Series) -> None:
        sev  = row["severity"]
        bg   = SEVERITY_BG.get(sev, "#fff")
        bdr  = SEVERITY_BORDER.get(sev, "#ccc")
        badge = SEVERITY_BADGE.get(sev, sev)
        loc_name = loc_lookup.get(row["location_id"], row["location_id"])
        risk_label = RISK_TYPE_LABEL.get(row["risk_type"], row["risk_type"])

        with st.container():
            st.markdown(
                f"""<div style="
                    background:{bg};
                    border-left:5px solid {bdr};
                    border-radius:6px;
                    padding:10px 14px;
                    margin-bottom:10px;
                ">
                <div style="font-size:0.85rem;color:#555;margin-bottom:4px;">
                    {badge} &nbsp;·&nbsp; {risk_label} &nbsp;·&nbsp;
                    <b>{row['sku']}</b> — {row['sku_name']} &nbsp;·&nbsp; {loc_name}
                </div>
                <div style="font-size:0.95rem;">{row['message']}</div>
                </div>""",
                unsafe_allow_html=True,
            )
            with st.expander("Root cause & recommended action"):
                c1, c2 = st.columns(2)
                c1.markdown(f"**Root cause**  \n{row['root_cause']}")
                c2.markdown(f"**Recommended action**  \n{row['recommended_action']}")
                detail_parts = []
                if pd.notna(row.get("days_of_cover")):
                    detail_parts.append(f"Days of cover: **{row['days_of_cover']}**")
                if pd.notna(row.get("stockout_date")):
                    detail_parts.append(f"Projected stockout: **{row['stockout_date'].date()}**")
                if pd.notna(row.get("next_replenishment_eta")):
                    detail_parts.append(f"Next replenishment ETA: **{row['next_replenishment_eta'].date()}**")
                if detail_parts:
                    st.caption(" · ".join(detail_parts))

    # --- Render by grouping ---
    if group_by == "Severity":
        for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            group = filtered[filtered["severity"] == sev]
            if group.empty:
                continue
            st.markdown(f"#### {SEVERITY_BADGE[sev]} ({len(group)})")
            for _, row in group.iterrows():
                _card(row)

    elif group_by == "Location":
        for loc_id in filtered["location_id"].unique():
            group = filtered[filtered["location_id"] == loc_id]
            loc_name = loc_lookup.get(loc_id, loc_id)
            worst = group.sort_values(
                "severity", key=lambda s: s.map({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3})
            ).iloc[0]["severity"]
            badge = SEVERITY_BADGE.get(worst, worst)
            st.markdown(f"#### {loc_name} — {badge} ({len(group)} alert{'s' if len(group)>1 else ''})")
            for _, row in group.iterrows():
                _card(row)

    else:
        for _, row in filtered.iterrows():
            _card(row)

    # --- Export table ---
    st.divider()
    with st.expander("Export as table"):
        display = filtered[[
            "severity", "sku", "sku_name", "location_id", "risk_type",
            "days_of_cover", "stockout_date", "next_replenishment_eta", "message",
        ]].copy()
        display["location_id"] = display["location_id"].map(loc_lookup)
        display["severity"] = display["severity"].map(SEVERITY_BADGE)
        display.columns = [c.replace("_", " ").title() for c in display.columns]
        st.dataframe(display, use_container_width=True, hide_index=True)
