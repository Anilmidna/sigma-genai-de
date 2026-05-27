"""
Team 2 — Data Therapist
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team2_data_therapist/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import pandas as pd
import json
from bedrock_helper import call_nova_lite, call_nova_pro

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Data Therapist", layout="wide")
st.title("🩺 Data Therapist")
st.caption("Sigma DataTech AI Ops Platform — Team 2")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

@st.cache_data
def load_dirty():
    return conn.execute(
        "SELECT * FROM bronze_transactions WHERE "
        "transaction_id IS NULL OR amount < 0 OR amount = 0 OR "
        "transaction_date > '2025-01-01'"
    ).df()

@st.cache_data
def load_all():
    return conn.execute("SELECT * FROM bronze_transactions").df()

dirty_df = load_dirty()
all_df   = load_all()

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Diagnosis", "Round 2 — AI Prescription", "Round 3 — Treatment Plan"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Diagnosis")
    st.info("Nova Pro diagnoses each quality issue: what's wrong, why it happened, and confidence score.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**All Transactions**")
        st.dataframe(all_df, use_container_width=True, height=250)
    with col2:
        st.markdown("**Flagged Dirty Rows**")
        st.dataframe(dirty_df, use_container_width=True, height=250)

    st.metric("Total rows", len(all_df))
    st.metric("Dirty rows detected", len(dirty_df))

    if st.button("🩺 Run Diagnosis", type="primary"):
        with st.spinner("Nova Pro diagnosing data quality issues..."):

            # TODO: Write a system prompt making Nova Pro a data quality specialist
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a senior data quality engineer.
For each dirty row, it should output: issue_type, root_cause_hypothesis, confidence (0-100%), severity."""

            # TODO: Pass dirty rows to Nova Pro
            user_message = f"""TODO: Pass dirty rows and ask for diagnosis.
Dirty rows: {dirty_df.to_json(orient='records')}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["diagnosis"] = response

    if "diagnosis" in st.session_state:
        st.markdown("### Diagnosis Report")
        st.markdown(st.session_state["diagnosis"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Prescription")
    st.info("Nova Lite prescribes a specific fix for each issue — AND warns about side effects.")

    if "diagnosis" not in st.session_state:
        st.warning("Run Round 1 first.")
    else:
        if st.button("💊 Generate Prescriptions", type="primary"):
            with st.spinner("Nova Lite writing prescriptions..."):

                # TODO: Write a system prompt for a prescription generator
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should prescribe a specific Python/SQL fix for each diagnosed issue.
Crucially: it must also output a 'side_effect_warning' for each fix —
what could go wrong if this fix is applied without checking downstream impact."""

                # TODO: Pass diagnosis to Nova Lite
                user_message = f"""TODO: Pass diagnosis and ask for prescriptions with side-effect warnings.
Diagnosis: {st.session_state['diagnosis']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["prescription"] = response

    if "prescription" in st.session_state:
        st.markdown("### Prescriptions + Side Effect Warnings")
        st.markdown(st.session_state["prescription"])

        st.warning("⚠️ TODO: Highlight the fix that has the most dangerous side effect. "
                   "Hint: check what happens to Silver row count after applying each fix.")

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Treatment Plan")
    st.info("Approve, reject, or flag each fix. Run approved fixes and show before/after row counts.")

    if "prescription" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Before Treatment")
        before_bronze = conn.execute("SELECT COUNT(*) FROM bronze_transactions").fetchone()[0]
        before_silver = conn.execute("SELECT COUNT(*) FROM silver_transactions").fetchone()[0]
        col1, col2 = st.columns(2)
        col1.metric("Bronze rows", before_bronze)
        col2.metric("Silver rows (clean)", before_silver)

        st.markdown("### Your Treatment Decisions")
        # TODO: For each prescribed fix, show a selectbox: APPLY / REJECT / INVESTIGATE
        # Then show what the row counts would be after applying approved fixes
        st.warning("TODO: Build a decision interface for each fix (APPLY / REJECT / INVESTIGATE).")

        st.markdown("### After Treatment (Simulated)")
        # TODO: Simulate the effect of approved fixes using DuckDB queries
        # Show projected Silver row count after treatment
        st.warning("TODO: Query DuckDB to show projected impact of your approved fixes.")

        st.markdown("---")
        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "Describe the fix that causes more damage than it heals:",
            placeholder="The prescription for ___ looked correct but would break ___ because ___",
            height=100
        )
        if st.button("💾 Save Treatment Plan"):
            if ai_wrong.strip():
                result = {
                    "ai_got_wrong": ai_wrong,
                    "before_silver": before_silver,
                    "team": "team2_data_therapist"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Saved to verdict.json!")
            else:
                st.error("Fill in 'What AI Got Wrong' first.")
