"""Streamlit dashboard for the synthetic Growth & Operations Command Center."""

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.calculate_kpis import run_pipeline
from src.classify_risks import classify_risks
from src.generate_executive_summary import generate_summary

st.set_page_config(
    page_title="Growth & Operations Command Center",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Growth & Operations Command Center")
st.caption(
    "Synthetic, public-safe portfolio implementation for project governance, "
    "KPI visibility, risk escalation, and executive reporting."
)

outputs = run_pipeline(PROJECT_ROOT)
risk_register = classify_risks(PROJECT_ROOT)
summary = outputs["summary"]
projects = outputs["projects"]
enriched_kpis = outputs["enriched_kpis"]
blockers = outputs["blockers"]
decisions = outputs["decisions"]


def get_metric(name: str):
    value = summary.loc[summary["metric"] == name, "value"]
    return value.iloc[0] if not value.empty else 0


col1, col2, col3, col4 = st.columns(4)
col1.metric("Projects Tracked", int(get_metric("Projects tracked")))
col2.metric("Projects On Track", int(get_metric("Projects on track")))
col3.metric("Open Blockers", int(get_metric("Open blockers")))
col4.metric("KPI Target Attainment", f"{get_metric('KPI target attainment rate')}%")

st.divider()

left, right = st.columns(2)

with left:
    status_counts = (
        projects["status"].value_counts().rename_axis("status").reset_index(name="projects")
    )
    fig_status = px.bar(
        status_counts,
        x="status",
        y="projects",
        title="Project Status Distribution",
        text="projects",
    )
    fig_status.update_layout(showlegend=False, xaxis_title="", yaxis_title="Projects")
    st.plotly_chart(fig_status, use_container_width=True)

with right:
    progress = projects.sort_values("progress_pct", ascending=True)
    fig_progress = px.bar(
        progress,
        x="progress_pct",
        y="project_name",
        orientation="h",
        title="Project Progress",
        text="progress_pct",
    )
    fig_progress.update_layout(xaxis_title="Progress %", yaxis_title="")
    st.plotly_chart(fig_progress, use_container_width=True)

left, right = st.columns(2)

with left:
    fig_kpi = px.bar(
        enriched_kpis.sort_values("attainment_pct"),
        x="attainment_pct",
        y="metric_name",
        orientation="h",
        color="target_met",
        title="KPI Attainment",
        labels={"target_met": "Target Met"},
    )
    fig_kpi.add_vline(x=100, line_dash="dash")
    fig_kpi.update_layout(xaxis_title="Attainment %", yaxis_title="")
    st.plotly_chart(fig_kpi, use_container_width=True)

with right:
    health_counts = (
        risk_register["health"].value_counts().rename_axis("health").reset_index(name="projects")
    )
    fig_health = px.pie(
        health_counts,
        names="health",
        values="projects",
        hole=0.55,
        title="Portfolio Health",
    )
    st.plotly_chart(fig_health, use_container_width=True)

st.subheader("🚧 Open Blockers")
open_blockers = blockers[blockers["status"].isin(["Open", "Escalated"])][
    [
        "blocker_id",
        "project_id",
        "blocker_title",
        "severity",
        "owner",
        "status",
        "target_resolution_date",
        "escalation_required",
    ]
]
st.dataframe(open_blockers, use_container_width=True, hide_index=True)

st.subheader("🧾 Pending Decisions")
pending_decisions = decisions[decisions["status"] == "Pending"][
    [
        "decision_id",
        "project_id",
        "decision_title",
        "decision_owner",
        "follow_up_action",
    ]
]
st.dataframe(pending_decisions, use_container_width=True, hide_index=True)

st.subheader("🧠 Executive Summary")
st.markdown(generate_summary(PROJECT_ROOT))

st.info(
    "All records and metrics in this dashboard are synthetic and created solely "
    "for public portfolio demonstration."
)
