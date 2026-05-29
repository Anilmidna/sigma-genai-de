"""
Data Therapist — Streamlit Application
AI-Powered Data Quality Simulator for Sigma DataTech
"""

import sys
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Adjust paths to make sure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db.duckdb_manager import DuckDBManager
from utils.synthetic_data_generator import generate_dirty_data
from llm.diagnosis_engine import diagnose_dataset
from llm.remediation_engine import prescribe_remediation
from utils.validators import calculate_downstream_metrics, generate_comparison_report

# Page Config
st.set_page_config(
    page_title="Data Therapist — AI Data Quality Ops",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark/Futuristic theme elements, custom card animations, and badges)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&display=swap');

/* Apply modern typography */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}
h1, h2, h3, .title-text {
    font-family: 'Outfit', sans-serif;
    font-weight: 800;
    letter-spacing: -0.5px;
}

/* Glassmorphism Card Style */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.25);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    margin-bottom: 20px;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.glass-card:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.18);
}

/* Glassmorphic Metrics */
.metric-box {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 10px;
    padding: 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    text-align: center;
}

/* Pulse animation for High Severity */
@keyframes pulse {
    0% { border-color: rgba(239, 68, 68, 0.4); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2); }
    70% { border-color: rgba(239, 68, 68, 0.7); box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
    100% { border-color: rgba(239, 68, 68, 0.4); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}
.pulsing-alert-card {
    background: rgba(239, 68, 68, 0.08);
    border: 1px solid rgba(239, 68, 68, 0.4);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
    animation: pulse 2.5s infinite;
}

/* Badges styling */
.badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-right: 6px;
}
.badge-high {
    background-color: rgba(239, 68, 68, 0.18);
    color: rgb(248, 113, 113);
    border: 1px solid rgba(239, 68, 68, 0.4);
}
.badge-medium {
    background-color: rgba(245, 158, 11, 0.18);
    color: rgb(251, 191, 36);
    border: 1px solid rgba(245, 158, 11, 0.4);
}
.badge-low {
    background-color: rgba(16, 185, 129, 0.18);
    color: rgb(52, 211, 153);
    border: 1px solid rgba(16, 185, 129, 0.4);
}

.success-card {
    background: rgba(16, 185, 129, 0.08);
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}

.sidebar-title {
    font-family: 'Outfit', sans-serif;
    font-weight: 700;
    color: #a78bfa;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    # Create DB and seed dirty transactions
    st.session_state.db_manager = DuckDBManager()
    df_bronze = generate_dirty_data(n_records=220)
    st.session_state.db_manager.init_database(df_bronze)
    
    # Pre-configure default treatment decisions
    st.session_state.decisions = {
        "duplicates": "APPLY",
        "null_ids": "APPLY",
        "null_merchants": "APPLY",
        "null_customers": "APPLY",
        "malformed_timestamps": "APPLY",
        "future_timestamps": "APPLY",
        "merchant_spellings": "APPLY",
        "negative_amounts": "APPLY", # Initially applied (the trap is active!)
        "outliers": "APPLY"
    }
    
    # Save default decisions to DB
    for issue_id, decision in st.session_state.decisions.items():
        title = issue_id.replace("_", " ").title()
        st.session_state.db_manager.save_decision(issue_id, title, decision)
        
    # Execute pipeline initially
    st.session_state.db_manager.execute_remediation_pipeline(
        st.session_state.db_manager.get_decisions(), 
        use_naive_refund_fix=True
    )

db_manager = st.session_state.db_manager

# SIDEBAR PANEL
with st.sidebar:
    st.markdown("<h2 class='sidebar-title'>🩺 Data Therapist</h2>", unsafe_allow_html=True)
    st.caption("Sigma DataTech AI Remediation Console")
    
    # Navigation Radio
    navigation = st.radio(
        "Workflow Stage:",
        [
            "🏠 Home Dashboard",
            "📊 Bronze Data Explorer",
            "🔍 Round 1: AI Diagnosis",
            "⚡ Round 2: AI Prescription",
            "🩺 Round 3: Treatment Plan",
            "🛡️ Downstream Validation",
            "🚨 What AI Got Wrong"
        ]
    )
    
    st.divider()
    
    # AI Engine Settings
    st.markdown("### ⚙️ LLM Integration")
    use_bedrock = st.toggle("Live AWS Bedrock Mode", value=False, help="Toggle to make live calls to Bedrock us-east-1. Default is pre-seeded Mock mode.")
    
    if use_bedrock:
        st.success("AWS Bedrock mode active!")
        st.info("Uses Nova Pro for diagnosis and Nova Lite for prescription.")
    else:
        st.info("Demo Mode: Running via pre-seeded high-fidelity LLM outputs.")
        
    st.divider()
    st.markdown("### 📊 Pipeline State")
    bronze_cnt = db_manager.get_row_count("bronze_transactions")
    silver_cnt = db_manager.get_row_count("silver_transactions")
    survival_pct = round(silver_cnt / bronze_cnt * 100, 1) if bronze_cnt else 0
    
    st.metric("Bronze Rows", f"{bronze_cnt}")
    st.metric("Silver Rows", f"{silver_cnt}", f"Survival: {survival_pct}%")
    
    if st.button("Reset Simulator"):
        st.session_state.clear()
        st.rerun()

# ----------------- HOME PAGE -----------------
if navigation == "🏠 Home Dashboard":
    st.markdown("# 🩺 Data Therapist")
    st.markdown("### *Simulating Enterprise AI-powered Data Quality Remediation*")
    
    st.markdown("""
    Welcome to the **Data Therapist** simulator. This platform demonstrates how modern data engineering pipelines 
    can leverage generative AI models to observe, diagnose, and remediate bad data moving from raw ingestion (**Bronze**) 
    to clean analytics tables (**Silver**).
    
    Sigma DataTech receives thousands of transactions every minute from three distinct source systems. Often, this data contains duplicates, 
    missing values, formatting anomalies, and spelling inconsistencies. Typically, data engineers spend hours writing custom validation rules 
    and manual cleaning queries every morning.
    """)
    
    # Key Pillars
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class='glass-card' style='height: 280px;'>
            <h4>🔍 Observability</h4>
            <p>Scan incoming Bronze streams dynamically and pinpoint exactly what is broken, where it originated, and why it occurred using <b>Nova Pro</b>.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class='glass-card' style='height: 280px;'>
            <h4>⚡ Auto-Remediation</h4>
            <p>Automatically generate exact SQL and Pandas repair code alongside safety impact assessments using cheap, high-speed <b>Nova Lite</b> models.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class='glass-card' style='height: 280px;'>
            <h4>🛡️ Human-in-the-Loop</h4>
            <p>Provide ultimate control to data teams, letting engineers approve, reject, or isolate AI fixes before code execution or table promotion.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("## 📊 Current Pipeline Health")
    
    # Stat metrics row
    bronze_metrics = db_manager.get_anomaly_metrics("bronze_transactions")
    silver_metrics = db_manager.get_anomaly_metrics("silver_transactions")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Raw Ingested Records", bronze_cnt)
    with c2:
        st.metric("Detected Anomalies (Bronze)", bronze_metrics.get("total_anomalies", 0), delta="Unhealthy", delta_color="inverse")
    with c3:
        st.metric("Remaining Anomalies (Silver)", silver_metrics.get("total_anomalies", 0), delta="Healthy" if silver_metrics.get("total_anomalies", 0) == 0 else "Anomalous")
    with c4:
        st.metric("Silver Survival Rate", f"{survival_pct}%")
        
    st.markdown("""
    ### 🚨 The Core Dilemma: The Silent Business Logic Failure
    Even when an AI agent achieves **0 structural anomalies** in your data quality metrics, it can still **completely corrupt your business metrics downstream**.
    
    In this app, you will experience **Round 1 (Diagnosis)**, **Round 2 (Prescription)**, and **Round 3 (Treatment)**. 
    You will witness how a naive AI-prescribed fix that resolves all structural warnings actually breaks financial aggregations. 
    Then, you'll see why human oversight and net business validations are crucial.
    """)

# ----------------- BRONZE DATA EXPLORER -----------------
elif navigation == "📊 Bronze Data Explorer":
    st.markdown("# 📊 Bronze Layer Data Explorer")
    st.markdown("Explore the raw, dirty transactional logs injected from Source Systems A, B, and C.")
    
    df_b = db_manager.get_table_as_df("bronze_transactions")
    b_metrics = db_manager.get_anomaly_metrics("bronze_transactions")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown("### Data Profiling Summary")
        st.markdown("Here is the anomaly profile of the Bronze table:")
        
        # Profile Table
        profile_data = {
            "Anomaly Type": [
                "Duplicate Transaction IDs",
                "Null Transaction IDs",
                "Null Merchant Names",
                "Missing Customer IDs",
                "Malformed/Future Dates",
                "Inconsistent Merchant Names",
                "Negative Amounts (Refunds)"
            ],
            "Impacted Rows": [
                f"{b_metrics.get('duplicate_ids', 0)} rows",
                f"{b_metrics.get('null_ids', 0)} rows",
                f"{b_metrics.get('null_merchants', 0)} rows",
                f"{b_metrics.get('null_customers', 0)} rows",
                f"{b_metrics.get('bad_timestamps', 0)} rows",
                f"{b_metrics.get('inconsistent_merchants', 0)} rows",
                f"{b_metrics.get('negative_amounts', 0)} rows"
            ],
            "Severity": ["HIGH 🔴", "HIGH 🔴", "MEDIUM 🟡", "MEDIUM 🟡", "HIGH 🔴", "MEDIUM 🟡", "HIGH 🔴"]
        }
        st.table(pd.DataFrame(profile_data))
        
    with col2:
        st.markdown("### Ingestion Source & Distribution Analysis")
        # Visualizing using Plotly
        fig_source = px.histogram(
            df_b, 
            x="source_system", 
            color="source_system", 
            title="Transactions count by Source System",
            color_discrete_sequence=px.colors.qualitative.Dark24
        )
        st.plotly_chart(fig_source, use_container_width=True)
        
    # Table Grid
    st.markdown("### Raw Bronze Transactions (First 100 rows)")
    st.dataframe(df_b.head(100), use_container_width=True)

# ----------------- AI DIAGNOSIS (ROUND 1) -----------------
elif navigation == "🔍 Round 1: AI Diagnosis":
    st.markdown("# 🔍 Round 1: AI-Powered Diagnosis")
    st.markdown("### Nova Pro analyzes raw table footprints to hypothesize root causes and estimate business impacts.")
    
    df_b = db_manager.get_table_as_df("bronze_transactions")
    
    # Progress or diagnostic button
    if st.button("Trigger AI System Audit Scan", type="primary"):
        with st.spinner("AI Scanner is running deep-analysis with Nova Pro..."):
            st.session_state.diagnoses = diagnose_dataset(df_b, use_bedrock=use_bedrock)
            st.success("Audit complete! Report generated successfully.")
            
    if "diagnoses" not in st.session_state:
        st.session_state.diagnoses = diagnose_dataset(df_b, use_bedrock=False)
        
    diagnoses = st.session_state.diagnoses
    
    st.markdown(f"**Nova Pro detected {len(diagnoses)} critical issues in Bronze layer:**")
    
    # Display in cards
    for issue in diagnoses:
        sev = issue.get("severity", "MEDIUM")
        badge_cls = "badge-high" if sev == "HIGH" else "badge-medium" if sev == "MEDIUM" else "badge-low"
        
        st.markdown(f"""
        <div class="glass-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #a78bfa;">{issue.get('title')}</h3>
                <div>
                    <span class="badge {badge_cls}">{sev} SEVERITY</span>
                    <span class="badge" style="background-color: rgba(255,255,255,0.08); color: #cbd5e1;">Confidence: {issue.get('confidence')}</span>
                </div>
            </div>
            <p style="margin: 10px 0; color: #e2e8f0; font-size: 0.95rem;"><b>Description:</b> {issue.get('description')}</p>
            <div style="margin-top: 15px; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 6px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px;">🔬 Root Cause Hypothesis:</span>
                <p style="margin: 4px 0 0 0; color: #a7f3d0; font-size: 0.9rem;">{issue.get('root_cause')}</p>
            </div>
            <div style="margin-top: 10px; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 6px;">
                <span style="color: #cbd5e1; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px;">💸 Business Impact:</span>
                <p style="margin: 4px 0 0 0; color: #fca5a5; font-size: 0.9rem;">{issue.get('business_impact')}</p>
            </div>
            <div style="margin-top: 10px; color: #94a3b8; font-size: 0.85rem;">
                <b>Impacted Rows Estimate:</b> {issue.get('affected_rows')}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ----------------- AI PRESCRIPTION (ROUND 2) -----------------
elif navigation == "⚡ Round 2: AI Prescription":
    st.markdown("# ⚡ Round 2: AI-Powered Prescription")
    st.markdown("### Nova Lite writes SQL transformations, provides logic explanations, and assesses down-stream risks.")
    
    if "diagnoses" not in st.session_state:
        df_b = db_manager.get_table_as_df("bronze_transactions")
        st.session_state.diagnoses = diagnose_dataset(df_b, use_bedrock=False)
        
    issue_list = [i.get("title") for i in st.session_state.diagnoses]
    selected_title = st.selectbox("Select Detected Quality Issue to Inspect Remediation:", issue_list)
    
    # Retrieve the issue ID
    selected_issue = next(i for i in st.session_state.diagnoses if i.get("title") == selected_title)
    issue_id = selected_issue.get("id")
    
    with st.spinner(f"Prescribing fix for {selected_title}..."):
        prescription = prescribe_remediation(issue_id, use_bedrock=use_bedrock)
        
    st.markdown(f"## 🩺 Recipe: {selected_title}")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("### 📝 Suggested Remedy & Logic")
        st.write(prescription.get("recommended_fix"))
        
        st.markdown("### 🔬 Execution Explanation")
        st.write(prescription.get("explanation"))
        
        st.markdown("### ⚠️ Side-Effect Warnings")
        st.warning(prescription.get("side_effect_warning"))
        
        st.markdown("### 🚨 Downstream Metric Risks")
        st.error(prescription.get("downstream_risk"))
        
    with col2:
        st.markdown("### 💻 Executable DuckDB SQL Transformation")
        st.code(prescription.get("sql_fix"), language="sql")
        
        st.markdown("### 🐍 Equivalent Python (Pandas) cleansing logic")
        st.code(prescription.get("pandas_fix"), language="python")
        
        st.metric("Nova Lite Prescription Confidence", prescription.get("confidence_level", "90%"))
        
        # Alert if the prescription is the dangerous absolute value fix
        if issue_id == "negative_amounts":
            st.markdown("""
            <div class="pulsing-alert-card">
                <h4 style="margin: 0 0 5px 0; color: #f87171;">⚠️ POTENTIAL DESIGN TRAP DETECTED</h4>
                <p style="margin:0; font-size: 0.85rem; color: #cbd5e1;">
                    This recommendation converts refunds into positive purchase values. While it satisfies structural validation 
                    checks (removes all negative amount issues), it will result in doubled revenue calculations downstream. 
                    Monitor validations closely!
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.success("Safe structural cleansing prescription.")

# ----------------- TREATMENT PLAN (ROUND 3) -----------------
elif navigation == "🩺 Round 3: Treatment Plan":
    st.markdown("# 🩺 Round 3: Active Treatment Plan & Human Governance")
    st.markdown("### Humans-in-the-loop review, approve, reject, or flag AI prescriptions before they run.")
    
    if "diagnoses" not in st.session_state:
        df_b = db_manager.get_table_as_df("bronze_transactions")
        st.session_state.diagnoses = diagnose_dataset(df_b, use_bedrock=False)
        
    st.markdown("""
    Review each AI-suggested prescription below. Select whether to **APPLY** the fix, **REJECT** it, 
    or flag it as **NEEDS INVESTIGATION** (which prevents automatic promotion).
    """)
    
    # Display each issue with governance selectors
    decisions = db_manager.get_decisions()
    
    # We render this inside a nice form or block
    updated_decisions = {}
    
    for idx, issue in enumerate(st.session_state.diagnoses):
        issue_id = issue.get("id")
        title = issue.get("title")
        severity = issue.get("severity", "MEDIUM")
        
        # Get active stored decision or default to APPLY
        current_decision = decisions.get(issue_id, {}).get("decision", "APPLY")
        
        with st.expander(f"Issue {idx+1}: {title} (Severity: {severity})", expanded=(issue_id == "negative_amounts")):
            st.markdown(f"**Issue Description:** {issue.get('description')}")
            
            # Fetch prescription details
            prescription = prescribe_remediation(issue_id, use_bedrock=False)
            st.code(prescription.get("sql_fix"), language="sql")
            
            # Governance Radio
            choice = st.radio(
                f"Action for '{title}':",
                ["APPLY FIX", "REJECT FIX", "NEEDS INVESTIGATION"],
                index=0 if current_decision == "APPLY" else 1 if current_decision == "REJECT" else 2,
                key=f"choice_{issue_id}"
            )
            
            decision_val = "APPLY" if "APPLY" in choice else "REJECT" if "REJECT" in choice else "INVESTIGATE"
            updated_decisions[issue_id] = decision_val
            
            # Save selection immediately
            db_manager.save_decision(issue_id, title, decision_val, prescription.get("sql_fix"))
            
    st.divider()
    
    # Pipeline execution toggle
    st.markdown("### ⚙️ Execute Remediation & Promote to Silver")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        When you run the pipeline, the treatment manager will read the human decisions.
        - **Approved Fixes:** Will execute dynamically in DuckDB to populate the `silver_transactions` table.
        - **Rejected Fixes:** Will skip correction, meaning the raw anomalies will persist in Silver.
        - **Investigation Flags:** The records will be isolated, allowing deep forensics.
        """)
        
        # Toggle safe alternative for refunds
        use_naive_refund = st.checkbox(
            "Use AI-Recommended absolute value fix for Negative Amounts", 
            value=st.session_state.get("use_naive_refund", True),
            help="If checked, applies ABS(). If unchecked, uses the Human-Governed safe fix (preserving signs)."
        )
        st.session_state.use_naive_refund = use_naive_refund
        
    with col2:
        if st.button("🚀 Run Remediation Pipeline", type="primary", use_container_width=True):
            with st.spinner("Executing dynamic DuckDB SQL scripts..."):
                active_decisions = db_manager.get_decisions()
                sqls = db_manager.execute_remediation_pipeline(active_decisions, use_naive_refund_fix=use_naive_refund)
                st.success("Pipeline executed successfully!")
                
                # Show executed SQL block
                with st.expander("Show Executed SQL Lineage Log"):
                    for key, sql in sqls:
                        st.markdown(f"**Applied issue ID: {key}**")
                        st.code(sql, language="sql")
                        st.divider()
                        
                st.rerun()

# ----------------- DOWNSTREAM VALIDATION -----------------
elif navigation == "🛡️ Downstream Validation":
    st.markdown("# 🛡️ Downstream Validation & Observability Dashboard")
    st.markdown("### Validate downstream financial metrics and compare Bronze Raw vs. Silver Promoted.")
    
    # Calculate comparison reports
    reports = generate_comparison_report(db_manager)
    
    # Retrieve current active state of the database
    # Which state are we rendering right now?
    active_silver_metrics = calculate_downstream_metrics(db_manager, "silver_transactions")
    
    st.markdown("## 📊 Downstream Financial Comparison")
    st.markdown("""
    This screen simulates downstream business metrics. Notice what happens when you compare **Bronze Raw**, 
    **Silver with Naive AI Fixes** (which applies the AI-suggested absolute value trap), and **Silver with Human-Governed Safe Fixes** (which preserves negatives).
    """)
    
    # Cards comparing net revenue and refunds
    col1, col2, col3 = st.columns(3)
    with col1:
        bronze_val = reports.get("bronze", {})
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid #f87171;">
            <h5 style="margin: 0; color: #94a3b8;">1. BRONZE RAW DATA</h5>
            <h2 style="margin: 10px 0 5px 0; color: #f87171;">${bronze_val.get('net_revenue', 0.0):,}</h2>
            <p style="margin: 0; font-size: 0.85rem; color: #cbd5e1;"><b>Net Revenue</b> (Dirty, duplicates included)</p>
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="font-size: 0.85rem; color: #cbd5e1;">
                <b>Refunds Count:</b> {bronze_val.get('refunds_count', 0)}<br>
                <b>Refunds Amount:</b> ${bronze_val.get('refunds_amount', 0.0):,}<br>
                <b>Total Transactions:</b> {bronze_val.get('total_rows', 0)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        naive_val = reports.get("naive_silver", {})
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid #fb7185; background: rgba(244,63,94,0.06);">
            <h5 style="margin: 0; color: #e2e8f0;">2. SILVER (NAIVE AI REMEDIATION)</h5>
            <h2 style="margin: 10px 0 5px 0; color: #fb7185;">${naive_val.get('net_revenue', 0.0):,}</h2>
            <p style="margin: 0; font-size: 0.85rem; color: #fca5a5;"><b>Net Revenue</b> (⚠️ INFLATED REVENUE DETECTED!)</p>
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="font-size: 0.85rem; color: #fca5a5;">
                <b>Refunds Count:</b> {naive_val.get('refunds_count', 0)} (🚨 Vanished!)<br>
                <b>Refunds Amount:</b> ${naive_val.get('refunds_amount', 0.0):,} (🚨 Sign inverted!)<br>
                <b>Total Transactions:</b> {naive_val.get('total_rows', 0)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        correct_val = reports.get("correct_silver", {})
        st.markdown(f"""
        <div class="glass-card" style="border-left: 5px solid #34d399; background: rgba(52,211,153,0.06);">
            <h5 style="margin: 0; color: #e2e8f0;">3. SILVER (HUMAN-GOVERNED SAFE)</h5>
            <h2 style="margin: 10px 0 5px 0; color: #34d399;">${correct_val.get('net_revenue', 0.0):,}</h2>
            <p style="margin: 0; font-size: 0.85rem; color: #a7f3d0;"><b>Net Revenue</b> (🛡️ Correct Net Figures)</p>
            <hr style="margin: 10px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="font-size: 0.85rem; color: #a7f3d0;">
                <b>Refunds Count:</b> {correct_val.get('refunds_count', 0)} (Preserved)<br>
                <b>Refunds Amount:</b> ${correct_val.get('refunds_amount', 0.0):,} (Accurate)<br>
                <b>Total Transactions:</b> {correct_val.get('total_rows', 0)}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    # Chart comparison
    st.markdown("### 📈 Net Revenue & Refund Variance Chart")
    
    categories = ["Bronze (Dirty Raw)", "Silver (Naive AI Fix - Trap)", "Silver (Human-Governed - Correct)"]
    revenues = [bronze_val.get("net_revenue", 0), naive_val.get("net_revenue", 0), correct_val.get("net_revenue", 0)]
    refund_counts = [bronze_val.get("refunds_count", 0), naive_val.get("refunds_count", 0), correct_val.get("refunds_count", 0)]
    
    fig = go.Figure()
    # Revenue Bar Chart
    fig.add_trace(go.Bar(
        x=categories,
        y=revenues,
        name="Calculated Net Revenue ($)",
        marker_color=["#f87171", "#fb7185", "#34d399"],
        text=[f"${v:,.2f}" for v in revenues],
        textposition="auto"
    ))
    # Refund Count line chart (dual axis)
    fig.add_trace(go.Scatter(
        x=categories,
        y=refund_counts,
        name="Refund Count",
        yaxis="y2",
        line=dict(color="#6366f1", width=3, dash="dash"),
        marker=dict(size=10, color="#6366f1")
    ))
    
    fig.update_layout(
        title="Downstream Metrics Deviation Analysis",
        xaxis=dict(title="Pipeline Stage"),
        yaxis=dict(title="Net Revenue ($)", titlefont=dict(color="#34d399"), tickfont=dict(color="#34d399")),
        yaxis2=dict(
            title="Refund Count", 
            titlefont=dict(color="#6366f1"), 
            tickfont=dict(color="#6366f1"),
            overlaying="y",
            side="right"
        ),
        legend=dict(x=0.01, y=0.99),
        template="plotly_dark",
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed Table comparison
    st.markdown("### 📊 Side-by-Side Aggregation Ledger")
    ledger_data = {
        "Metric": ["Total Record Count", "Calculated Net Revenue", "Refund Transaction Count", "Refund Dollar Amount", "Gross Purchases Count", "High Value Fraud Alerts"],
        "Bronze (Raw)": [
            f"{bronze_val.get('total_rows')}",
            f"${bronze_val.get('net_revenue'):,}",
            f"{bronze_val.get('refunds_count')}",
            f"${bronze_val.get('refunds_amount'):,}",
            f"{bronze_val.get('purchase_count')}",
            f"{bronze_val.get('high_value_alerts')}"
        ],
        "Silver (Naive AI Fix - Trap Active)": [
            f"{naive_val.get('total_rows')}",
            f"${naive_val.get('net_revenue'):,}",
            f"{naive_val.get('refunds_count')}",
            f"${naive_val.get('refunds_amount'):,}",
            f"{naive_val.get('purchase_count')}",
            f"{naive_val.get('high_value_alerts')}"
        ],
        "Silver (Human-Governed - Correct)": [
            f"{correct_val.get('total_rows')}",
            f"${correct_val.get('net_revenue'):,}",
            f"{correct_val.get('refunds_count')}",
            f"${correct_val.get('refunds_amount'):,}",
            f"{correct_val.get('purchase_count')}",
            f"{correct_val.get('high_value_alerts')}"
        ]
    }
    st.table(pd.DataFrame(ledger_data))

# ----------------- WHAT AI GOT WRONG -----------------
elif navigation == "🚨 What AI Got Wrong":
    st.markdown("# 🚨 What AI Got Wrong: Exposing the Absolute Value Trap")
    st.markdown("### The crucial case study for Human-in-the-Loop AI Governance.")
    
    st.markdown("""
    ### 🔬 Case Study: The Negative Amount sign inversion
    The central theme of the **Data Therapist** project is that **optimizing data quality metrics in isolation can lead to logical business catastrophes**.
    
    When our AI diagnosis module scanned the Bronze table, it correctly noted:
    * *"Anomalous negative figures in transaction_amount (-$120.00)"*
    
    Optimizing for clean data validation, the AI prescription engine (**Nova Lite**) immediately generated the following logic:
    > *"Currency amounts must be non-negative. Convert negative values to positive using the mathematical ABS() function to resolve the format violation."*
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="pulsing-alert-card" style="height: 480px;">
            <h4 style="margin: 0 0 10px 0; color: #f87171;">❌ Naive AI Prescription (ABS)</h4>
            <p><b>What it did:</b> Applied absolute math to all negative transactions in the table.</p>
            <pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; color: #fca5a5;">
UPDATE silver_transactions
SET transaction_amount = abs(transaction_amount)
WHERE transaction_amount &lt; 0;
            </pre>
            <p><b>Why it seemed correct:</b>
                <ul>
                    <li>Anomalous negative amounts drop to <b>0</b>.</li>
                    <li>The structural validation check returns <b>100% HEALTHY</b>.</li>
                    <li>No database schema constraints are broken.</li>
                </ul>
            </p>
            <p style="color: #fca5a5;"><b>The Disaster:</b> Downstream dashboard revenue doubled, and refund trackers collapsed to zero, leaving corporate accounting severely out of sync.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="success-card" style="height: 480px;">
            <h4 style="margin: 0 0 10px 0; color: #34d399;">✅ Human-Governed Safe Fix</h4>
            <p><b>What it does:</b> Preserves the negative amount representing the cash outflow, but standardizes the transaction_type categorization.</p>
            <pre style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; color: #a7f3d0;">
UPDATE silver_transactions
SET transaction_type = CASE 
    WHEN transaction_type NOT IN ('REFUND', 'CHARGEBACK') THEN 'REFUND' 
    ELSE transaction_type 
END
WHERE transaction_amount &lt; 0;
            </pre>
            <p><b>Why it is correct:</b>
                <ul>
                    <li>Preserves the negative mathematical sign.</li>
                    <li>Accurately reports cash flowing back to customers.</li>
                    <li>Maintains net income totals correctly.</li>
                </ul>
            </p>
            <p style="color: #a7f3d0;"><b>The Success:</b> Standard accounting integrity is maintained. Corporate ledgers show true net figures ($95k instead of the artificial $150k).</p>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("""
    ### 🧠 Key Lessons for AI Systems Design
    
    1. **Data Quality is not just Column-level validation:** A column can pass all validation checks (e.g., non-negative, standard format, not-null) while corrupting system logic.
    2. **AI lacks contextual domain awareness:** Large language models are fantastic at syntax and format cleanup, but they lack the corporate domain context to know that a negative number represents a refund rather than a database glitch.
    3. **Observability must look Downstream:** Data monitoring shouldn't stop at the Silver loading layer. It must audit high-level business indicators (like Total Net Revenue vs. Refund Rates) to detect anomalous swings.
    4. **Governance requires human-in-the-loop oversight:** Human supervisors must review automatically generated SQL scripts before they are committed, preventing major business corruption.
    
    ---
    
    ### 🩺 How to Fix it in this App:
    1. Go to the **Round 3: Treatment Plan** tab in the sidebar.
    2. Under **Issue 8: Negative Transaction Amounts**, review the choices.
    3. Scroll down and **UNCHECK** *"Use AI-Recommended absolute value fix for Negative Amounts"*. This activates the **Human-Governed Safe Fix**.
    4. Click **🚀 Run Remediation Pipeline** again.
    5. Navigate to the **Downstream Validation** tab to see standard Net Revenue and Refund counts return to normal, healthy metrics!
    """)
    
    # Interactive test trigger
    st.info("💡 Try deactivating the naive fix in Round 3 and watch the downstream ledger return to safety!")
