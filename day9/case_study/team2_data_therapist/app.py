"""
Data Therapist — Main Streamlit App
Sigma DataTech AI-Powered Data Quality Remediation Simulator

3-Round Workflow:
  Round 1 — AI Diagnosis (Nova Pro)
  Round 2 — AI Prescription (Nova Lite)
  Round 3 — Human Treatment Plan + Silver Creation

The trap: "Fix negative amounts" looks correct but corrupts refund accounting downstream.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Local imports
from utils.synthetic_data_generator import generate_bronze_dataset
from db.duckdb_manager import (
    init_bronze,
    get_bronze_stats,
    get_bronze_df,
    create_silver_from_approved_fixes,
    get_silver_stats,
    get_silver_df,
    get_connection,
)
from llm.diagnosis_engine import run_diagnosis
from llm.remediation_engine import run_prescriptions

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Data Therapist | Sigma DataTech",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Dark gradient background */
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #0d1530 50%, #0a1628 100%);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1530 0%, #0a0e1a 100%);
        border-right: 1px solid rgba(99, 102, 241, 0.2);
    }

    /* Main header */
    .main-header {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.1) 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 16px;
        padding: 28px 36px;
        margin-bottom: 28px;
        text-align: center;
        backdrop-filter: blur(10px);
    }

    .main-header h1 {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #818cf8, #c084fc, #60a5fa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -1px;
    }

    .main-header p {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-top: 8px;
    }

    /* Metric cards */
    .metric-card {
        background: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.6);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
    }

    .metric-card .value {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -1px;
    }

    .metric-card .label {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 4px;
    }

    /* Section headers */
    .section-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #e2e8f0;
        margin: 24px 0 16px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }

    /* Issue card */
    .issue-card {
        background: rgba(15, 23, 42, 0.9);
        border-left: 4px solid #ef4444;
        border-radius: 0 12px 12px 0;
        padding: 18px 22px;
        margin-bottom: 14px;
        transition: all 0.2s ease;
    }

    .issue-card.medium {
        border-left-color: #f59e0b;
    }

    .issue-card.low {
        border-left-color: #10b981;
    }

    .issue-card:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }

    /* Severity badges */
    .badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .badge-high { background: rgba(239,68,68,0.2); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
    .badge-medium { background: rgba(245,158,11,0.2); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); }
    .badge-low { background: rgba(16,185,129,0.2); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
    .badge-danger { background: rgba(220,38,38,0.3); color: #fca5a5; border: 1px solid rgba(220,38,38,0.6); }
    .badge-safe { background: rgba(16,185,129,0.2); color: #6ee7b7; border: 1px solid rgba(16,185,129,0.4); }

    /* Treatment plan decision card */
    .decision-card {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }

    /* Code blocks */
    code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
    }

    /* Warning box */
    .warning-box {
        background: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-radius: 10px;
        padding: 16px 20px;
        margin: 12px 0;
    }

    .danger-box {
        background: rgba(220, 38, 38, 0.12);
        border: 2px solid rgba(220, 38, 38, 0.5);
        border-radius: 12px;
        padding: 20px 24px;
        margin: 16px 0;
        animation: pulse-border 2s ease-in-out infinite;
    }

    @keyframes pulse-border {
        0%, 100% { border-color: rgba(220, 38, 38, 0.5); }
        50% { border-color: rgba(220, 38, 38, 0.9); }
    }

    /* Silver success box */
    .silver-box {
        background: linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1));
        border: 1px solid rgba(99,102,241,0.4);
        border-radius: 14px;
        padding: 24px;
        margin: 16px 0;
    }

    /* Timeline steps */
    .step-indicator {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(99,102,241,0.15);
        border: 1px solid rgba(99,102,241,0.3);
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #818cf8;
    }

    /* Audit trail */
    .audit-row-apply {
        border-left: 3px solid #10b981;
        padding: 8px 12px;
        margin: 6px 0;
        background: rgba(16,185,129,0.05);
        border-radius: 0 6px 6px 0;
    }

    .audit-row-reject {
        border-left: 3px solid #ef4444;
        padding: 8px 12px;
        margin: 6px 0;
        background: rgba(239,68,68,0.05);
        border-radius: 0 6px 6px 0;
    }

    .audit-row-investigate {
        border-left: 3px solid #f59e0b;
        padding: 8px 12px;
        margin: 6px 0;
        background: rgba(245,158,11,0.05);
        border-radius: 0 6px 6px 0;
    }

    /* Stale Streamlit elements fix */
    .stSelectbox label, .stRadio label {
        color: #94a3b8 !important;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(99,102,241,0.2);
        border-radius: 10px;
        padding: 14px 18px;
    }

    /* Sidebar nav */
    .sidebar-nav-item {
        padding: 10px 16px;
        border-radius: 8px;
        cursor: pointer;
        color: #94a3b8;
        transition: all 0.2s;
        margin-bottom: 4px;
    }
    .sidebar-nav-item:hover, .sidebar-nav-item.active {
        background: rgba(99,102,241,0.15);
        color: #818cf8;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state helpers ─────────────────────────────────────────────────────
def init_session_state():
    defaults = {
        "bronze_loaded": False,
        "bronze_df": None,
        "bronze_stats": {},
        "diagnoses": [],
        "prescriptions": {},
        "decisions": {},
        "silver_df": None,
        "sql_log": [],
        "row_stats": {},
        "silver_stats": {},
        "silver_created": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session_state()

# ── Sidebar Navigation ────────────────────────────────────────────────────────
PAGES = {
    "🏠 Home": "home",
    "🥉 Bronze Data": "bronze",
    "🤖 AI Diagnosis": "diagnosis",
    "💊 AI Prescription": "prescription",
    "📋 Treatment Plan": "treatment",
    "🥈 Silver Validation": "silver",
    "⚠️ What AI Got Wrong": "wrong",
}

with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 16px 0 24px 0;'>
        <span style='font-size: 2.5rem;'>🩺</span>
        <h2 style='color: #818cf8; margin: 8px 0 4px 0; font-size: 1.2rem; font-weight: 700;'>Data Therapist</h2>
        <p style='color: #475569; font-size: 0.78rem; margin: 0;'>Sigma DataTech AI Ops</p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    page = st.radio("Navigation", list(PAGES.keys()), label_visibility="collapsed")
    active_page = PAGES[page]

    st.divider()

    # Quick status panel
    if st.session_state.bronze_loaded:
        stats = st.session_state.bronze_stats
        st.markdown("**📊 Quick Stats**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Bronze Rows", stats.get("total_rows", 0))
            st.metric("Duplicates", stats.get("duplicate_ids", 0))
        with col2:
            st.metric("Nulls", stats.get("null_transaction_id", 0) + stats.get("null_merchant", 0))
            st.metric("Bad TS", stats.get("bad_timestamps", 0))

    if st.session_state.silver_created:
        st.markdown("**🥈 Silver Layer**")
        st.metric("Silver Rows", len(st.session_state.silver_df) if st.session_state.silver_df is not None else 0)

    st.divider()

    # Data control
    if st.button("🔄 Reset & Reload Bronze Data", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        init_session_state()
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: HOME
# ─────────────────────────────────────────────────────────────────────────────
if active_page == "home":
    st.markdown("""
    <div class='main-header'>
        <h1>🩺 Data Therapist</h1>
        <p>AI-Powered Data Quality Remediation Simulator — Sigma DataTech</p>
    </div>
    """, unsafe_allow_html=True)

    # Architecture overview
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class='metric-card'>
            <div class='value' style='color: #cd7f32;'>🥉</div>
            <div style='color: #94a3b8; font-size: 1.1rem; font-weight: 600; margin-top: 8px;'>Bronze Layer</div>
            <div class='label'>Raw dirty transactions from 3 source systems</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class='metric-card'>
            <div class='value' style='color: #818cf8;'>🤖</div>
            <div style='color: #94a3b8; font-size: 1.1rem; font-weight: 600; margin-top: 8px;'>AI Analysis</div>
            <div class='label'>Nova Pro diagnoses · Nova Lite prescribes</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("""
        <div class='metric-card'>
            <div class='value' style='color: #94a3b8;'>🥈</div>
            <div style='color: #94a3b8; font-size: 1.1rem; font-weight: 600; margin-top: 8px;'>Silver Layer</div>
            <div class='label'>Human-approved clean transactions</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Workflow steps
    st.markdown("### 🔄 Three-Round Workflow")
    steps = [
        ("1", "AI Diagnosis", "Nova Pro scans Bronze data and diagnoses each quality issue with root cause analysis and confidence scores.", "🔍", "#6366f1"),
        ("2", "AI Prescription", "Nova Lite prescribes SQL/Python fixes for every issue — including mandatory side-effect warnings.", "💊", "#8b5cf6"),
        ("3", "Treatment Plan", "You decide: APPLY FIX / REJECT FIX / NEEDS INVESTIGATION. Only approved fixes reach Silver.", "📋", "#0ea5e9"),
        ("4", "Silver Validation", "DuckDB materializes the Silver table. Downstream metrics reveal which AI fix caused hidden damage.", "🥈", "#10b981"),
        ("5", "What AI Got Wrong", "The reveal: one fix looked correct but corrupted refund accounting. Human oversight caught it.", "⚠️", "#ef4444"),
    ]

    for num, title, desc, icon, color in steps:
        st.markdown(f"""
        <div style='display: flex; gap: 20px; align-items: flex-start; margin-bottom: 16px;
                    background: rgba(15,23,42,0.8); border-radius: 12px; padding: 18px 22px;
                    border: 1px solid rgba(99,102,241,0.15);'>
            <div style='background: {color}22; border: 2px solid {color}; border-radius: 50%;
                        width: 40px; height: 40px; display: flex; align-items: center;
                        justify-content: center; font-size: 1.2rem; font-weight: 800;
                        color: {color}; flex-shrink: 0;'>{num}</div>
            <div>
                <div style='font-weight: 700; color: #e2e8f0; font-size: 1rem;'>{icon} {title}</div>
                <div style='color: #64748b; font-size: 0.875rem; margin-top: 4px;'>{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Key learning
    st.markdown("""
    <div class='danger-box'>
        <div style='font-size: 1.1rem; font-weight: 700; color: #f87171; margin-bottom: 8px;'>
            🎯 The Central Learning Objective
        </div>
        <div style='color: #fca5a5; font-size: 0.95rem; line-height: 1.6;'>
            <strong>One AI-prescribed fix will look obviously correct but break something downstream.</strong><br>
            The "Convert negative amounts to positive" fix reduces negative value counts (metrics improve!) 
            but it also flips legitimate REFUND transactions to positive values — doubling revenue and 
            destroying refund accounting. You won't see the damage until you query the Silver table.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("👈 Start with **🥉 Bronze Data** in the sidebar to load and inspect the dirty dataset.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: BRONZE DATA
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "bronze":
    st.markdown("## 🥉 Bronze Layer — Raw Dirty Transactions")
    st.markdown("*Sigma DataTech receives raw transactions from 3 source systems (SYS_A, SYS_B, SYS_C). This is the unfiltered, unvalidated Bronze layer.*")

    if not st.session_state.bronze_loaded:
        st.markdown("""
        <div style='background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.3);
                    border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0;'>
            <div style='font-size: 2rem;'>🔄</div>
            <div style='color: #94a3b8; margin-top: 8px;'>Bronze data not yet loaded.</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⚡ Generate & Load Bronze Data", type="primary", use_container_width=True):
            with st.spinner("🔬 Generating synthetic dirty transaction dataset..."):
                df = generate_bronze_dataset()
                count = init_bronze(df)
                stats = get_bronze_stats()
                st.session_state.bronze_df = df
                st.session_state.bronze_stats = stats
                st.session_state.bronze_loaded = True
            st.success(f"✅ Loaded {count} Bronze rows with injected quality issues!")
            st.rerun()
    else:
        df = st.session_state.bronze_df
        stats = st.session_state.bronze_stats

        # Top metrics
        st.markdown("### 📊 Bronze Layer Health Dashboard")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        metrics = [
            (c1, stats.get("total_rows", 0), "Total Rows", "#818cf8"),
            (c2, stats.get("duplicate_ids", 0), "Duplicate IDs", "#ef4444"),
            (c3, stats.get("null_merchant", 0), "Null Merchants", "#f59e0b"),
            (c4, stats.get("negative_amounts", 0), "Negative Amounts", "#ef4444"),
            (c5, stats.get("bad_timestamps", 0), "Bad Timestamps", "#ef4444"),
            (c6, stats.get("invalid_types", 0), "Invalid Types", "#f59e0b"),
        ]
        for col, val, label, color in metrics:
            with col:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='value' style='color: {color};'>{val}</div>
                    <div class='label'>{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Quality issue breakdown chart
        col_chart, col_table = st.columns([1, 1])

        with col_chart:
            st.markdown("#### 📈 Quality Issue Breakdown")
            issues_data = {
                "Issue": ["Null TXN IDs", "Null Customers", "Null Merchants", "Duplicates",
                          "Negative Amounts", "Bad Timestamps", "Invalid Types", "Outliers",
                          "Whitespace", "Invalid Source"],
                "Count": [
                    stats.get("null_transaction_id", 0), stats.get("null_customer_id", 0),
                    stats.get("null_merchant", 0), stats.get("duplicate_ids", 0),
                    stats.get("negative_amounts", 0), stats.get("bad_timestamps", 0),
                    stats.get("invalid_types", 0), stats.get("outlier_amounts", 0),
                    stats.get("whitespace_merchants", 0), stats.get("invalid_source_systems", 0),
                ],
                "Severity": ["HIGH", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "HIGH",
                             "MEDIUM", "HIGH", "LOW", "MEDIUM"],
            }
            df_chart = pd.DataFrame(issues_data)
            color_map = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}
            df_chart["color"] = df_chart["Severity"].map(color_map)

            fig = px.bar(
                df_chart, x="Count", y="Issue", orientation="h",
                color="Severity",
                color_discrete_map=color_map,
                template="plotly_dark",
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#94a3b8"),
                margin=dict(l=0, r=10, t=10, b=10),
                height=350,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            fig.update_xaxes(gridcolor="rgba(99,102,241,0.1)")
            fig.update_yaxes(gridcolor="rgba(99,102,241,0.1)")
            st.plotly_chart(fig, use_container_width=True)

        with col_table:
            st.markdown("#### 💳 Transaction Amount Distribution")
            # Filter out extreme outliers for visualization
            df_viz = df[df["transaction_amount"].between(-10000, 10000)]
            fig2 = px.histogram(
                df_viz, x="transaction_amount", nbins=40,
                template="plotly_dark",
                color_discrete_sequence=["#818cf8"],
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#94a3b8"),
                margin=dict(l=0, r=10, t=10, b=10),
                height=350,
                xaxis_title="Amount (₹)",
                yaxis_title="Count",
            )
            fig2.update_xaxes(gridcolor="rgba(99,102,241,0.1)")
            fig2.update_yaxes(gridcolor="rgba(99,102,241,0.1)")
            st.plotly_chart(fig2, use_container_width=True)

        # Raw data table
        st.markdown("#### 📋 Raw Bronze Table")

        # Highlight problematic rows
        def highlight_issues(row):
            styles = [""] * len(row)
            if pd.isna(row.get("transaction_id")):
                styles = ["background-color: rgba(239,68,68,0.15)"] * len(row)
            elif pd.isna(row.get("merchant_name")):
                styles = ["background-color: rgba(245,158,11,0.1)"] * len(row)
            elif row.get("transaction_amount", 0) < 0:
                styles = ["background-color: rgba(239,68,68,0.08)"] * len(row)
            return styles

        # Show styled dataframe
        search_col, filter_col = st.columns([2, 1])
        with filter_col:
            show_issues_only = st.checkbox("Show issues only", value=False)

        if show_issues_only:
            mask = (
                df["transaction_id"].isna() |
                df["merchant_name"].isna() |
                df["customer_id"].isna() |
                (df["transaction_amount"] < 0) |
                df["transaction_timestamp"].isin(["not-a-date", "0000-00-00 00:00:00", "2024-13-45 00:00:00"]) |
                ~df["transaction_type"].isin(["PURCHASE", "REFUND", "CHARGEBACK", "TRANSFER"])
            )
            display_df = df[mask]
        else:
            display_df = df

        st.dataframe(
            display_df,
            use_container_width=True,
            height=400,
            column_config={
                "transaction_amount": st.column_config.NumberColumn("Amount (₹)", format="₹%.2f"),
                "transaction_timestamp": st.column_config.TextColumn("Timestamp"),
            }
        )

        st.caption(f"Showing {len(display_df)} of {len(df)} rows")

        # Source system breakdown
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🔌 Source System Distribution")
            sys_counts = df["source_system"].value_counts().reset_index()
            sys_counts.columns = ["source_system", "count"]
            fig3 = px.pie(sys_counts, values="count", names="source_system",
                          template="plotly_dark", hole=0.4,
                          color_discrete_sequence=["#818cf8", "#60a5fa", "#c084fc", "#34d399", "#f87171"])
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"), height=280)
            st.plotly_chart(fig3, use_container_width=True)

        with col2:
            st.markdown("#### 🏷️ Transaction Type Distribution")
            type_counts = df["transaction_type"].value_counts().reset_index()
            type_counts.columns = ["type", "count"]
            fig4 = px.pie(type_counts, values="count", names="type",
                          template="plotly_dark", hole=0.4,
                          color_discrete_sequence=["#818cf8", "#60a5fa", "#c084fc", "#34d399", "#f87171"])
            fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color="#94a3b8"), height=280)
            st.plotly_chart(fig4, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: AI DIAGNOSIS (Round 1 — Nova Pro)
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "diagnosis":
    st.markdown("## 🤖 Round 1 — AI Diagnosis")
    st.markdown("*Amazon Nova Pro scans the Bronze layer and diagnoses each data quality issue with root cause analysis, confidence scoring, and business impact assessment.*")

    if not st.session_state.bronze_loaded:
        st.warning("⚠️ Please load Bronze data first (navigate to **🥉 Bronze Data**).")
    else:
        if not st.session_state.diagnoses:
            st.markdown("""
            <div style='background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.3);
                        border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0;'>
                <div style='font-size: 2rem;'>🔍</div>
                <div style='color: #94a3b8; margin-top: 8px;'>Nova Pro has not run yet.</div>
                <div style='color: #64748b; font-size: 0.85rem;'>Click below to start AI-powered diagnosis.</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔍 Run Nova Pro Diagnosis", type="primary", use_container_width=True):
                with st.spinner("🧠 Nova Pro is analyzing your Bronze data... (this may take 30-60 seconds)"):
                    stats = st.session_state.bronze_stats
                    diagnoses = run_diagnosis(stats)
                    st.session_state.diagnoses = diagnoses
                st.success(f"✅ Diagnosed {len(diagnoses)} data quality issues!")
                st.rerun()
        else:
            diagnoses = st.session_state.diagnoses

            # Summary metrics
            high_count = sum(1 for d in diagnoses if d.get("severity") == "HIGH")
            med_count = sum(1 for d in diagnoses if d.get("severity") == "MEDIUM")
            low_count = sum(1 for d in diagnoses if d.get("severity") == "LOW")
            avg_conf = sum(d.get("confidence_score", 0) for d in diagnoses) / len(diagnoses) if diagnoses else 0
            total_affected = sum(d.get("affected_rows_estimate", 0) for d in diagnoses)

            c1, c2, c3, c4, c5 = st.columns(5)
            for col, val, label, color in [
                (c1, len(diagnoses), "Total Issues", "#818cf8"),
                (c2, high_count, "HIGH Severity", "#ef4444"),
                (c3, med_count, "MEDIUM Severity", "#f59e0b"),
                (c4, low_count, "LOW Severity", "#10b981"),
                (c5, f"{avg_conf:.0f}%", "Avg Confidence", "#60a5fa"),
            ]:
                with col:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <div class='value' style='color: {color};'>{val}</div>
                        <div class='label'>{label}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Confidence heatmap
            st.markdown("#### 🎯 Issue Confidence & Severity Overview")
            df_diag = pd.DataFrame([{
                "Issue": d.get("issue_title", ""),
                "Severity": d.get("severity", ""),
                "Confidence": d.get("confidence_score", 0),
                "Affected Rows": d.get("affected_rows_estimate", 0),
            } for d in diagnoses])

            color_map = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#10b981"}
            fig = px.scatter(
                df_diag, x="Confidence", y="Affected Rows",
                color="Severity", size="Affected Rows",
                hover_data=["Issue"],
                color_discrete_map=color_map,
                template="plotly_dark",
                size_max=30,
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#94a3b8"),
                height=280,
                margin=dict(l=0, r=10, t=10, b=10),
            )
            fig.update_xaxes(gridcolor="rgba(99,102,241,0.1)", title="AI Confidence (%)")
            fig.update_yaxes(gridcolor="rgba(99,102,241,0.1)", title="Estimated Affected Rows")
            st.plotly_chart(fig, use_container_width=True)

            # Diagnosis cards
            st.markdown("#### 🏥 Detailed Diagnoses")

            severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
            sorted_diagnoses = sorted(diagnoses, key=lambda x: severity_order.get(x.get("severity", "LOW"), 3))

            for diag in sorted_diagnoses:
                severity = diag.get("severity", "LOW")
                sev_class = severity.lower()
                badge_class = f"badge-{sev_class}"
                conf = diag.get("confidence_score", 0)
                conf_color = "#10b981" if conf >= 85 else "#f59e0b" if conf >= 70 else "#ef4444"

                with st.expander(
                    f"{'🔴' if severity == 'HIGH' else '🟡' if severity == 'MEDIUM' else '🟢'} "
                    f"{diag.get('issue_id', '')} — {diag.get('issue_title', '')}  |  Confidence: {conf}%",
                    expanded=(severity == "HIGH")
                ):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**📝 Description:** {diag.get('issue_description', '')}")
                        st.markdown(f"**🔍 Root Cause:** {diag.get('root_cause_hypothesis', '')}")
                        st.markdown(f"**💼 Business Impact:** {diag.get('business_impact', '')}")

                    with col2:
                        st.markdown(f"**Severity:** <span class='badge {badge_class}'>{severity}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Confidence:** <span style='color: {conf_color}; font-weight: 700; font-size: 1.3rem;'>{conf}%</span>", unsafe_allow_html=True)
                        st.markdown(f"**Affected Rows:** `~{diag.get('affected_rows_estimate', 0)}`")
                        st.markdown(f"**Fix Key:** `{diag.get('fix_key', 'N/A')}`")

            if st.button("🔄 Re-run Diagnosis", use_container_width=True):
                st.session_state.diagnoses = []
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: AI PRESCRIPTION (Round 2 — Nova Lite)
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "prescription":
    st.markdown("## 💊 Round 2 — AI Prescription")
    st.markdown("*Amazon Nova Lite prescribes SQL and Python fixes for each diagnosed issue — including mandatory side-effect warnings and downstream risk assessments.*")

    if not st.session_state.diagnoses:
        st.warning("⚠️ Please run AI Diagnosis first (navigate to **🤖 AI Diagnosis**).")
    else:
        if not st.session_state.prescriptions:
            st.markdown("""
            <div style='background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.3);
                        border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0;'>
                <div style='font-size: 2rem;'>💊</div>
                <div style='color: #94a3b8; margin-top: 8px;'>Nova Lite has not run yet.</div>
                <div style='color: #64748b; font-size: 0.85rem;'>Click below to generate remediation prescriptions.</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("💊 Run Nova Lite Prescription", type="primary", use_container_width=True):
                with st.spinner("🧬 Nova Lite is generating remediation prescriptions..."):
                    prescriptions = run_prescriptions(st.session_state.diagnoses)
                    st.session_state.prescriptions = prescriptions
                st.success(f"✅ Generated {len(prescriptions)} prescriptions!")
                st.rerun()
        else:
            prescriptions = st.session_state.prescriptions
            diagnoses = st.session_state.diagnoses

            # Dangerous fix callout
            dangerous = [p for p in prescriptions.values() if p.get("is_dangerous")]
            if dangerous:
                st.markdown("""
                <div class='danger-box'>
                    <div style='font-size: 1.1rem; font-weight: 700; color: #f87171; margin-bottom: 8px;'>
                        🚨 WARNING: AI Has Prescribed At Least One Dangerous Fix
                    </div>
                    <div style='color: #fca5a5;'>
                        Nova Lite has identified a fix that <strong>appears correct</strong> but will <strong>corrupt downstream business logic</strong>.
                        Review all prescriptions carefully before approving. This is why human oversight exists.
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # Summary
            safe_count = sum(1 for p in prescriptions.values() if not p.get("is_dangerous"))
            dangerous_count = len(dangerous)
            avg_conf = sum(p.get("confidence_level", 0) for p in prescriptions.values()) / len(prescriptions) if prescriptions else 0

            c1, c2, c3, c4 = st.columns(4)
            for col, val, label, color in [
                (c1, len(prescriptions), "Total Prescriptions", "#818cf8"),
                (c2, safe_count, "Safe Fixes", "#10b981"),
                (c3, dangerous_count, "Dangerous Fixes", "#ef4444"),
                (c4, f"{avg_conf:.0f}%", "Avg Confidence", "#60a5fa"),
            ]:
                with col:
                    st.markdown(f"""
                    <div class='metric-card'>
                        <div class='value' style='color: {color};'>{val}</div>
                        <div class='label'>{label}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Prescription cards
            st.markdown("#### 💊 Detailed Prescriptions")

            # Show dangerous fix first
            diag_map = {d["issue_id"]: d for d in diagnoses}

            for issue_id, p in sorted(prescriptions.items(), key=lambda x: (not x[1].get("is_dangerous"), x[0])):
                diag = diag_map.get(issue_id, {})
                is_dangerous = p.get("is_dangerous", False)
                conf = p.get("confidence_level", 0)

                badge = "🚨 DANGEROUS" if is_dangerous else "✅ SAFE"
                badge_color = "#ef4444" if is_dangerous else "#10b981"

                with st.expander(
                    f"{'🚨' if is_dangerous else '✅'} {issue_id} — {diag.get('issue_title', 'Unknown Issue')}  |  Confidence: {conf}%",
                    expanded=is_dangerous
                ):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**🎯 Recommended Fix:**")
                        st.info(p.get("recommended_fix", ""))

                        st.markdown(f"**📝 Explanation:**")
                        st.markdown(p.get("explanation", ""))

                        st.markdown("**🗄️ SQL Fix:**")
                        st.code(p.get("sql_fix", ""), language="sql")

                        st.markdown("**🐍 Python/Pandas Fix:**")
                        st.code(p.get("python_fix", ""), language="python")

                    with col2:
                        st.markdown(f"**Risk Level:** <span style='color: {badge_color}; font-weight: 700;'>{badge}</span>", unsafe_allow_html=True)
                        st.markdown(f"**AI Confidence:** <span style='color: {'#10b981' if conf >= 85 else '#f59e0b' if conf >= 70 else '#ef4444'}; font-weight: 700; font-size: 1.2rem;'>{conf}%</span>", unsafe_allow_html=True)

                        st.markdown("**⚠️ Side Effect Warning:**")
                        if is_dangerous:
                            st.markdown(f"""
                            <div class='danger-box' style='margin: 0;'>
                                <div style='color: #fca5a5; font-size: 0.88rem;'>{p.get('side_effect_warning', '')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class='warning-box'>
                                <div style='color: #fbbf24; font-size: 0.88rem;'>{p.get('side_effect_warning', '')}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown(f"**🔽 Downstream Risk:**")
                        st.markdown(f"<span style='color: #94a3b8; font-size: 0.875rem;'>{p.get('downstream_risk', '')}</span>", unsafe_allow_html=True)

                        if is_dangerous and p.get("danger_reason"):
                            st.markdown(f"""
                            <div style='margin-top: 12px; background: rgba(220,38,38,0.1);
                                        border: 1px solid rgba(220,38,38,0.4); border-radius: 8px;
                                        padding: 12px;'>
                                <div style='color: #f87171; font-weight: 700; font-size: 0.8rem;'>WHY IT'S DANGEROUS:</div>
                                <div style='color: #fca5a5; font-size: 0.82rem; margin-top: 4px;'>{p.get('danger_reason', '')}</div>
                            </div>
                            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: TREATMENT PLAN (Round 3)
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "treatment":
    st.markdown("## 📋 Round 3 — Your Treatment Plan")
    st.markdown("*For each diagnosed issue, decide: **APPLY FIX** / **REJECT FIX** / **NEEDS INVESTIGATION**. Only approved fixes will be applied to the Silver layer.*")

    if not st.session_state.prescriptions:
        st.warning("⚠️ Please run AI Prescription first (navigate to **💊 AI Prescription**).")
    else:
        diagnoses = st.session_state.diagnoses
        prescriptions = st.session_state.prescriptions

        st.info(
            "💡 **Data Governance Principle:** You are the human in the loop. "
            "AI can diagnose and recommend — but only you can approve changes to production data. "
            "Review the side-effect warnings carefully. The dangerous fix will look tempting."
        )

        decisions = {}
        diag_map = {d["issue_id"]: d for d in diagnoses}

        st.markdown("#### 🩺 Issue Review Queue")

        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_diagnoses = sorted(diagnoses, key=lambda x: severity_order.get(x.get("severity", "LOW"), 3))

        for diag in sorted_diagnoses:
            issue_id = diag.get("issue_id", "")
            presc = prescriptions.get(issue_id, {})
            severity = diag.get("severity", "LOW")
            is_dangerous = presc.get("is_dangerous", False)

            sev_color = "#ef4444" if severity == "HIGH" else "#f59e0b" if severity == "MEDIUM" else "#10b981"
            sev_icon = "🔴" if severity == "HIGH" else "🟡" if severity == "MEDIUM" else "🟢"
            danger_label = " 🚨 AI FLAGGED DANGEROUS" if is_dangerous else ""

            # Header — only static/safe values in HTML (no user-data that contains quotes)
            st.markdown(
                f"<div style='background: rgba(15,23,42,0.9); border: 1px solid {sev_color}33; "
                f"border-left: 4px solid {sev_color}; border-radius: 0 12px 12px 0; "
                f"padding: 12px 20px; margin-bottom: 4px;'>"
                f"<span style='font-weight:700; color:#e2e8f0;'>{sev_icon} {issue_id}</span> "
                f"<span style='color:#94a3b8;'>— {diag.get('issue_title', '')}</span> "
                f"<span style='margin-left:10px; font-size:0.72rem; color:{sev_color}; font-weight:600;'>[{severity}]</span>"
                f"<span style='margin-left:8px; font-size:0.72rem; color:#f87171; font-weight:700;'>{danger_label}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Dynamic text — always use native st.caption (safe from HTML injection)
            desc = diag.get("issue_description", "")[:160] + "..."
            fix_preview = presc.get("recommended_fix", "")[:120] + "..."
            st.caption(f"📋 {desc}")
            st.caption(f"🔧 Proposed fix: *{fix_preview}*")

            # Warning for dangerous fix — native st.error (never renders stray HTML)
            if is_dangerous:
                st.error(
                    f"🚨 **HUMAN OVERSIGHT REQUIRED:** {presc.get('danger_reason', '')}",
                    icon="🚨",
                )

            default_choice = "REJECT FIX" if is_dangerous else "APPLY FIX"
            decision = st.radio(
                f"Decision for {issue_id}:",
                ["APPLY FIX", "REJECT FIX", "NEEDS INVESTIGATION"],
                index=["APPLY FIX", "REJECT FIX", "NEEDS INVESTIGATION"].index(
                    st.session_state.decisions.get(issue_id, default_choice)
                ),
                horizontal=True,
                key=f"decision_{issue_id}",
            )
            decisions[issue_id] = decision
            st.divider()

        # Summary of decisions
        st.markdown("### 📊 Treatment Plan Summary")

        apply_count = sum(1 for d in decisions.values() if d == "APPLY FIX")
        reject_count = sum(1 for d in decisions.values() if d == "REJECT FIX")
        investigate_count = sum(1 for d in decisions.values() if d == "NEEDS INVESTIGATION")

        c1, c2, c3 = st.columns(3)
        for col, val, label, color, icon in [
            (c1, apply_count, "Fixes to Apply", "#10b981", "✅"),
            (c2, reject_count, "Fixes Rejected", "#ef4444", "❌"),
            (c3, investigate_count, "Needs Investigation", "#f59e0b", "🔍"),
        ]:
            with col:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='value' style='color: {color};'>{icon} {val}</div>
                    <div class='label'>{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Audit trail — fully native markdown, no HTML tags
        st.markdown("#### 📜 Audit Trail Preview")
        audit_icons = {"APPLY FIX": "✅", "REJECT FIX": "❌", "NEEDS INVESTIGATION": "🔍"}
        for issue_id, decision in decisions.items():
            diag = diag_map.get(issue_id, {})
            presc = prescriptions.get(issue_id, {})
            icon = audit_icons[decision]
            danger_note = "  ⚠️ *Dangerous fix — correctly rejected*" if decision == "REJECT FIX" and presc.get("is_dangerous") else ""
            st.markdown(f"{icon} **{issue_id}** — {diag.get('issue_title', '')} → `{decision}`{danger_note}")

        st.markdown("<br>", unsafe_allow_html=True)

        # Apply treatment
        if st.button("⚡ Apply Treatment Plan & Create Silver Layer", type="primary", use_container_width=True):
            st.session_state.decisions = decisions

            approved_fixes = []
            for issue_id, decision in decisions.items():
                if decision == "APPLY FIX":
                    diag = diag_map.get(issue_id, {})
                    fix_key = diag.get("fix_key", "")
                    if fix_key:
                        approved_fixes.append(fix_key)

            df_bronze = st.session_state.bronze_df

            with st.spinner(f"⚙️ Applying {len(approved_fixes)} approved fixes to Bronze data..."):
                silver_df, sql_log, row_stats = create_silver_from_approved_fixes(approved_fixes, df_bronze)
                silver_stats = get_silver_stats(silver_df)

            st.session_state.silver_df = silver_df
            st.session_state.sql_log = sql_log
            st.session_state.row_stats = row_stats
            st.session_state.silver_stats = silver_stats
            st.session_state.silver_created = True

            st.success(f"✅ Silver layer created! {row_stats['bronze_original']} → {row_stats['silver_rows']} rows ({row_stats['bronze_original'] - row_stats['silver_rows']} removed)")
            st.balloons()
            st.info("👈 Navigate to **🥈 Silver Validation** to see downstream impact.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: SILVER VALIDATION
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "silver":
    st.markdown("## 🥈 Silver Validation — Downstream Impact Analysis")
    st.markdown("*The Silver layer has been materialized from your approved fixes. Let's examine the downstream metrics.*")

    if not st.session_state.silver_created:
        st.warning("⚠️ Please complete the Treatment Plan first (navigate to **📋 Treatment Plan**).")
    else:
        silver_df = st.session_state.silver_df
        bronze_df = st.session_state.bronze_df
        row_stats = st.session_state.row_stats
        sql_log = st.session_state.sql_log
        silver_stats = st.session_state.silver_stats
        decisions = st.session_state.decisions

        # Row count comparison
        st.markdown("### 📊 Bronze → Silver Row Count Comparison")
        bronze_rows = row_stats.get("bronze_original", 0)
        silver_rows = row_stats.get("silver_rows", 0)
        survival_pct = (silver_rows / bronze_rows * 100) if bronze_rows > 0 else 0

        c1, c2, c3, c4 = st.columns(4)
        for col, val, label, color in [
            (c1, bronze_rows, "Bronze Rows", "#cd7f32"),
            (c2, silver_rows, "Silver Rows", "#94a3b8"),
            (c3, bronze_rows - silver_rows, "Rows Removed", "#ef4444"),
            (c4, f"{survival_pct:.1f}%", "Survival Rate", "#10b981"),
        ]:
            with col:
                st.markdown(f"""
                <div class='metric-card'>
                    <div class='value' style='color: {color};'>{val}</div>
                    <div class='label'>{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # SQL execution log
        st.markdown("### ⚙️ Applied SQL Transformations")
        for log_entry in sql_log:
            status_color = "#10b981" if "✅" in log_entry.get("status", "") else "#ef4444"
            with st.expander(f"{log_entry.get('status', '')} — {log_entry.get('description', '')}", expanded=False):
                st.code(log_entry.get("sql", ""), language="sql")

        st.markdown("<br>", unsafe_allow_html=True)

        # Downstream analytics comparison
        st.markdown("### 💹 Downstream Business Metrics — Before vs After")

        # Bronze stats
        bronze_completed = bronze_df[bronze_df["status"] == "COMPLETED"]
        bronze_refunds = bronze_df[bronze_df["transaction_type"] == "REFUND"]
        bronze_revenue = bronze_completed["transaction_amount"].sum()
        bronze_refund_count = len(bronze_refunds)
        bronze_neg = (bronze_df["transaction_amount"] < 0).sum()

        # Silver stats
        silver_completed = silver_df[silver_df["status"] == "COMPLETED"] if not silver_df.empty else pd.DataFrame()
        silver_refunds = silver_df[silver_df["transaction_type"] == "REFUND"] if not silver_df.empty else pd.DataFrame()
        silver_revenue = silver_completed["transaction_amount"].sum() if not silver_completed.empty else 0
        silver_refund_count = len(silver_refunds)
        silver_neg = (silver_df["transaction_amount"] < 0).sum() if not silver_df.empty else 0

        # Check if the dangerous fix was applied
        dangerous_fix_applied = decisions.get("DX003", "") == "APPLY FIX"

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🥉 Bronze (Before)")
            metrics_bronze = [
                ("Total Revenue (COMPLETED)", f"₹{bronze_revenue:,.2f}", "#94a3b8"),
                ("Refund Transactions", str(bronze_refund_count), "#94a3b8"),
                ("Negative Amounts", str(bronze_neg), "#94a3b8"),
                ("Total Rows", str(len(bronze_df)), "#94a3b8"),
            ]
            for label, val, color in metrics_bronze:
                st.markdown(f"""
                <div style='display: flex; justify-content: space-between; padding: 10px 16px;
                            background: rgba(15,23,42,0.6); border-radius: 8px; margin-bottom: 6px;
                            border: 1px solid rgba(99,102,241,0.1);'>
                    <span style='color: #64748b;'>{label}</span>
                    <span style='color: {color}; font-weight: 600; font-family: JetBrains Mono, monospace;'>{val}</span>
                </div>
                """, unsafe_allow_html=True)

        with col2:
            st.markdown("#### 🥈 Silver (After)")
            # Flag if revenue jumped suspiciously
            rev_change_pct = ((silver_revenue - bronze_revenue) / abs(bronze_revenue) * 100) if bronze_revenue != 0 else 0
            rev_color = "#ef4444" if dangerous_fix_applied and abs(rev_change_pct) > 10 else "#10b981"
            ref_color = "#ef4444" if dangerous_fix_applied and silver_refund_count != bronze_refund_count else "#10b981"

            metrics_silver = [
                ("Total Revenue (COMPLETED)", f"₹{silver_revenue:,.2f}", rev_color),
                ("Refund Transactions", str(silver_refund_count), ref_color),
                ("Negative Amounts", str(silver_neg), "#10b981"),
                ("Total Rows", str(len(silver_df)), "#10b981"),
            ]
            for label, val, color in metrics_silver:
                change = ""
                if label == "Total Revenue (COMPLETED)" and dangerous_fix_applied:
                    change = f" ({'+'if rev_change_pct > 0 else ''}{rev_change_pct:.1f}%)"
                st.markdown(f"""
                <div style='display: flex; justify-content: space-between; padding: 10px 16px;
                            background: rgba(15,23,42,0.6); border-radius: 8px; margin-bottom: 6px;
                            border: 1px solid rgba(99,102,241,0.15);'>
                    <span style='color: #64748b;'>{label}</span>
                    <span style='color: {color}; font-weight: 600; font-family: JetBrains Mono, monospace;'>{val}{change}</span>
                </div>
                """, unsafe_allow_html=True)

        if dangerous_fix_applied:
            st.markdown("""
            <div class='danger-box'>
                <div style='font-size: 1.1rem; font-weight: 700; color: #f87171;'>
                    🚨 DOWNSTREAM CORRUPTION DETECTED!
                </div>
                <div style='color: #fca5a5; margin-top: 8px;'>
                    The "Convert Negative Amounts to Positive" fix was applied. Revenue has been artificially inflated
                    because REFUND transactions (which were correctly negative) have been converted to positive values.
                    The Finance dashboard now shows incorrect GMV. <strong>This is why the fix should be REJECTED.</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Merchant revenue chart
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### 🏪 Merchant Revenue — Silver Layer")

        if not silver_df.empty and "merchant_name" in silver_df.columns:
            merch_rev = (
                silver_completed.groupby("merchant_name")["transaction_amount"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            merch_rev.columns = ["Merchant", "Revenue"]

            fig = px.bar(merch_rev, x="Merchant", y="Revenue",
                         template="plotly_dark",
                         color_discrete_sequence=["#818cf8"])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#94a3b8"),
                height=300,
                margin=dict(l=0, r=10, t=10, b=10),
            )
            fig.update_xaxes(gridcolor="rgba(99,102,241,0.1)")
            fig.update_yaxes(gridcolor="rgba(99,102,241,0.1)", title="Revenue (₹)")
            st.plotly_chart(fig, use_container_width=True)

        # Silver data table
        st.markdown("### 📋 Silver Transactions Table")
        st.dataframe(silver_df, use_container_width=True, height=350)
        st.caption(f"✅ {len(silver_df)} clean rows in Silver | {row_stats.get('bronze_original', 0) - len(silver_df)} rows removed from Bronze")

        # Rejected fixes documentation
        rejected = {iid: d for iid, d in decisions.items() if d == "REJECT FIX"}
        if rejected:
            st.markdown("### ❌ Rejected Fixes — Documented for Audit")
            diag_map = {d["issue_id"]: d for d in st.session_state.diagnoses}
            presc_map = st.session_state.prescriptions

            for iid, _ in rejected.items():
                diag = diag_map.get(iid, {})
                presc = presc_map.get(iid, {})
                st.markdown(f"""
                <div class='audit-row-reject'>
                    <strong style='color: #f87171;'>❌ {iid} — {diag.get("issue_title", "")}</strong>
                    <div style='color: #64748b; font-size: 0.85rem; margin-top: 4px;'>
                        Rejected Fix: {presc.get("recommended_fix", "")[:100]}...
                    </div>
                    <div style='color: #475569; font-size: 0.8rem; margin-top: 2px;'>
                        Reason: {presc.get("side_effect_warning", "")[:150]}
                    </div>
                </div>
                """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: WHAT AI GOT WRONG
# ─────────────────────────────────────────────────────────────────────────────
elif active_page == "wrong":
    st.markdown("## ⚠️ What AI Got Wrong — The Dangerous Prescription")

    st.markdown("""
    <div class='danger-box'>
        <div style='font-size: 1.3rem; font-weight: 800; color: #f87171; margin-bottom: 12px;'>
            🚨 The Fix That Looked Right But Wasn't
        </div>
        <div style='color: #fca5a5; font-size: 1rem; line-height: 1.7;'>
            <strong>DX003 — Convert Negative Amounts to Positive</strong><br>
            Nova Lite recommended converting all negative transaction amounts to their absolute positive values using <code>ABS()</code>.
            On the surface, this looked like a clean, simple, low-risk data quality fix. The metrics improved. Validation checks passed.
            But it silently destroyed refund accounting downstream.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # The story
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🤖 What AI Saw")
        st.markdown("""
        <div style='background: rgba(15,23,42,0.9); border: 1px solid rgba(99,102,241,0.2);
                    border-radius: 12px; padding: 20px;'>
            <div style='color: #94a3b8; line-height: 1.7;'>
                <p>📊 <strong style='color: #e2e8f0;'>Before fix:</strong></p>
                <ul style='color: #64748b;'>
                    <li>6 records with negative amounts</li>
                    <li>Validation fails: "negative amounts detected"</li>
                    <li>Finance dashboard shows red</li>
                    <li>Data quality score: 71%</li>
                </ul>
                <p>📊 <strong style='color: #e2e8f0;'>After ABS() fix:</strong></p>
                <ul style='color: #10b981;'>
                    <li>✅ 0 records with negative amounts</li>
                    <li>✅ Validation passes</li>
                    <li>✅ Dashboard shows green</li>
                    <li>✅ Data quality score: 94%</li>
                </ul>
                <p style='color: #6ee7b7; font-style: italic;'>"Fix applied successfully. All metrics improved."</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("### 🧑‍💼 What Actually Happened")
        st.markdown("""
        <div style='background: rgba(220,38,38,0.08); border: 2px solid rgba(220,38,38,0.4);
                    border-radius: 12px; padding: 20px;'>
            <div style='color: #fca5a5; line-height: 1.7;'>
                <p>🔴 <strong style='color: #f87171;'>Hidden damage downstream:</strong></p>
                <ul>
                    <li>REFUND transactions (e.g., -₹500) → became +₹500 PURCHASES</li>
                    <li>Revenue aggregates <strong>inflated by ~15-20%</strong></li>
                    <li>Finance dashboard showed <strong>incorrect GMV</strong></li>
                    <li>Chargeback risk model lost negative signal entirely</li>
                    <li>Monthly refund report showed <strong>₹0 refunds</strong></li>
                </ul>
                <p style='color: #f87171; font-style: italic;'>"Everything looks healthy. But the finance team's numbers are wrong."</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Why it happened
    st.markdown("### 🧠 Why AI Got It Wrong")

    reasons = [
        ("🤖 AI Only Sees Patterns, Not Business Logic", "Nova Lite was trained to minimize data quality violations. A negative amount is a violation in most contexts — so ABS() is a statistically correct fix. But it had no knowledge of Sigma DataTech's business rule: 'negative amounts = refunds'. This business rule lives in human heads, not in the data."),
        ("📈 Metrics Looked Better, Not Deeper", "The prescription was evaluated on surface-level quality metrics: null counts, range violations, validation passes. All improved. The AI had no mechanism to check second-order effects — what happens to refund accounting, revenue aggregates, or fraud signals downstream."),
        ("⚡ Speed vs. Safety Trade-off", "Nova Lite is optimized for fast, cheap inference. It generates fixes that are syntactically correct and statistically sound. But enterprise data governance requires understanding of business invariants that take years to accumulate in a team's institutional knowledge."),
        ("🔍 No Downstream Simulation", "A production-grade AI data quality system would simulate the fix in a staging environment and run downstream validation checks before recommending a fix. Nova Lite prescribed the fix without running it — like a doctor recommending surgery without checking for allergies."),
    ]

    for title, desc in reasons:
        st.markdown(f"""
        <div style='background: rgba(15,23,42,0.8); border: 1px solid rgba(99,102,241,0.15);
                    border-left: 3px solid #818cf8; border-radius: 0 10px 10px 0;
                    padding: 16px 20px; margin-bottom: 12px;'>
            <div style='font-weight: 700; color: #e2e8f0; margin-bottom: 6px;'>{title}</div>
            <div style='color: #64748b; font-size: 0.88rem; line-height: 1.6;'>{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # The correct fix
    st.markdown("### ✅ What The Correct Fix Would Have Been")
    st.code("""
-- ✅ CORRECT: Only convert negatives that are NOT legitimate refunds
-- Step 1: Fix non-refund negatives (data entry errors)
UPDATE bronze_transactions
SET transaction_amount = ABS(transaction_amount)
WHERE transaction_amount < 0
  AND transaction_type != 'REFUND';

-- Step 2: Leave refund negatives as-is (they are business-valid)
-- REFUND amounts remain negative to correctly offset revenue

-- Step 3: Verify downstream impact
SELECT
    transaction_type,
    SUM(transaction_amount) as total_amount,
    COUNT(*) as count
FROM bronze_transactions
GROUP BY transaction_type;
""", language="sql")

    st.markdown("<br>", unsafe_allow_html=True)

    # Key takeaways
    st.markdown("### 💡 Key Takeaways — Human-in-the-Loop AI")

    takeaways = [
        ("🛡️", "AI is a tool, not a decision-maker", "Nova Lite generated a prescription. A human (you) decided whether to apply it. That distinction is the entire point of human-in-the-loop AI governance."),
        ("⚠️", "Side-effect warnings are not decorative", "The prescription explicitly warned: 'This fix will ALSO convert legitimate REFUND transactions to positive values.' The warning was correct. A human who reads it carefully will reject the fix."),
        ("🔍", "Downstream validation is non-negotiable", "The damage was only visible after querying the Silver table for refund counts and revenue. Production pipelines must run downstream checks before promoting data between layers."),
        ("📚", "Business context beats statistical optimization", "The AI optimized for 'fewer negative values'. The right metric was 'correct revenue + correct refund accounting'. Business invariants must be encoded explicitly, not assumed."),
        ("🤝", "AI + Human = Safer Data", "Neither AI alone (missed the refund impact) nor human alone (would spend 3 hours doing manual checks) is optimal. The combination — AI diagnosis + human approval + AI prescription + human veto — is the enterprise standard."),
    ]

    for icon, title, desc in takeaways:
        st.markdown(f"""
        <div style='display: flex; gap: 16px; background: rgba(15,23,42,0.8);
                    border: 1px solid rgba(99,102,241,0.15); border-radius: 12px;
                    padding: 16px 20px; margin-bottom: 10px;'>
            <div style='font-size: 1.5rem; flex-shrink: 0;'>{icon}</div>
            <div>
                <div style='font-weight: 700; color: #e2e8f0; margin-bottom: 4px;'>{title}</div>
                <div style='color: #64748b; font-size: 0.875rem; line-height: 1.6;'>{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # What healthy data looks like
    st.markdown("### 🌿 What 'Healthy Data' Looks Like for Sigma DataTech")
    st.markdown("""
    <div class='silver-box'>
        <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 16px;'>
            <div>
                <div style='color: #10b981; font-weight: 700; margin-bottom: 8px;'>✅ Silver Layer Standards</div>
                <ul style='color: #94a3b8; font-size: 0.875rem; line-height: 1.8; padding-left: 20px;'>
                    <li>All transaction_ids are non-null and unique</li>
                    <li>All amounts have correct sign for their type (REFUND = negative, PURCHASE = positive)</li>
                    <li>All timestamps are valid and within 90-day window</li>
                    <li>All merchant_names are trimmed and non-null</li>
                    <li>All transaction_types are in approved taxonomy</li>
                    <li>All source_system codes are registered</li>
                    <li>Refund-to-purchase ratio is within historical bounds (< 15%)</li>
                    <li>Revenue delta from Bronze-to-Silver is within ±5%</li>
                </ul>
            </div>
            <div>
                <div style='color: #818cf8; font-weight: 700; margin-bottom: 8px;'>📊 Target Metrics</div>
                <ul style='color: #94a3b8; font-size: 0.875rem; line-height: 1.8; padding-left: 20px;'>
                    <li>Data survival rate: > 90%</li>
                    <li>Null rate in Silver: < 2%</li>
                    <li>Duplicate rate in Silver: 0%</li>
                    <li>Revenue variance Bronze→Silver: ±5%</li>
                    <li>Refund count preserved from Bronze</li>
                    <li>All merchant GMV traceable to a registered merchant</li>
                    <li>Daily pipeline run time: < 10 minutes</li>
                    <li>AI confidence threshold for auto-apply: ≥ 90%</li>
                </ul>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Final pitch slide
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15));
                border: 1px solid rgba(99,102,241,0.4); border-radius: 16px;
                padding: 32px; text-align: center;'>
        <div style='font-size: 1.5rem; font-weight: 800; color: #e2e8f0; margin-bottom: 16px;'>
            🩺 Data Therapist — Demo Summary
        </div>
        <div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 20px;'>
            <div style='background: rgba(15,23,42,0.6); border-radius: 10px; padding: 16px;'>
                <div style='font-size: 1.5rem; font-weight: 800; color: #818cf8;'>10</div>
                <div style='color: #64748b; font-size: 0.8rem;'>Issues Diagnosed</div>
            </div>
            <div style='background: rgba(15,23,42,0.6); border-radius: 10px; padding: 16px;'>
                <div style='font-size: 1.5rem; font-weight: 800; color: #10b981;'>1</div>
                <div style='color: #64748b; font-size: 0.8rem;'>Dangerous Fix Caught</div>
            </div>
            <div style='background: rgba(15,23,42,0.6); border-radius: 10px; padding: 16px;'>
                <div style='font-size: 1.5rem; font-weight: 800; color: #f59e0b;'>3 hrs</div>
                <div style='color: #64748b; font-size: 0.8rem;'>Daily Time Saved</div>
            </div>
            <div style='background: rgba(15,23,42,0.6); border-radius: 10px; padding: 16px;'>
                <div style='font-size: 1.5rem; font-weight: 800; color: #60a5fa;'>Nova Pro+Lite</div>
                <div style='color: #64748b; font-size: 0.8rem;'>AI Models Used</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
