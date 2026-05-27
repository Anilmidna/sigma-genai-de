"""
Team 1 — Fraud Hunter
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team1_fraud_hunter/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import pandas as pd
import json
from bedrock_helper import call_nova_lite, call_nova_pro

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Fraud Hunter", layout="wide")
st.title("🔍 Fraud Hunter")
st.caption("Sigma DataTech AI Ops Platform — Team 1")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

# ── Load data ─────────────────────────────────────────────────
@st.cache_data
def load_transactions():
    return conn.execute(
        "SELECT * FROM bronze_transactions ORDER BY transaction_date"
    ).df()

df = load_transactions()

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Prosecutor", "Round 2 — AI Defense Lawyer", "Round 3 — Your Verdict"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Prosecutor")
    st.info("Nova Pro reviews all transactions and flags suspicious ones with severity and reason.")

    with st.expander("📋 Raw Transactions (what AI will review)", expanded=True):
        st.dataframe(df, use_container_width=True)

    if st.button("🔍 Run AI Fraud Analysis", type="primary"):
        with st.spinner("Nova Pro analysing transactions..."):

            # TODO: Build a system prompt that makes Nova Pro act as a fraud analyst
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a senior fraud analyst for a fintech company.
It should return structured output: list of flagged transactions with
severity (CRITICAL/HIGH/MEDIUM), reason, and confidence score."""

            # TODO: Build a user message with the transaction data
            user_message = f"""TODO: Pass the transaction data to Nova Pro here.
Transactions: {df.to_json(orient='records')}
Ask it to flag suspicious transactions."""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["round1_response"] = response

    if "round1_response" in st.session_state:
        st.markdown("### AI Findings")
        st.markdown(st.session_state["round1_response"])

        # TODO: Parse the AI response and display flagged transactions in a table
        # Hint: Ask AI to return JSON. Then parse with json.loads() and show as st.dataframe()
        st.warning("TODO: Parse the AI response and show flagged transactions as a structured table.")

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Defense Lawyer")
    st.info("Nova Lite argues why each flagged transaction might be legitimate.")

    if "round1_response" not in st.session_state:
        st.warning("Run Round 1 first.")
    else:
        if st.button("⚖️ Run Defense Analysis", type="primary"):
            with st.spinner("Nova Lite building defense arguments..."):

                # TODO: Write a system prompt that makes Nova Lite act as a defense lawyer
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should challenge each flag from Round 1.
For each flagged transaction, it should give 1-2 sentences arguing it could be legitimate."""

                # TODO: Pass the Round 1 findings to Nova Lite
                user_message = f"""TODO: Pass Round 1 findings here and ask Nova Lite to challenge them.
Round 1 findings: {st.session_state['round1_response']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["round2_response"] = response

    if "round2_response" in st.session_state:
        st.markdown("### Defense Arguments")
        st.markdown(st.session_state["round2_response"])

        st.markdown("---")
        st.markdown("### 🤔 The Contradiction")
        st.info("Find one transaction where the prosecutor and defense lawyer completely contradict each other. This is your key insight for the pitch.")
        # TODO: Display the most contradictory case side by side
        st.warning("TODO: Show the strongest contradiction between Round 1 and Round 2 side by side.")

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Your Verdict")
    st.info("You are the fraud team lead. Set your threshold and make the call for each transaction.")

    if "round2_response" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        col1, col2 = st.columns([2, 1])

        with col2:
            st.markdown("### Your Threshold")
            fp_threshold = st.slider(
                "Max acceptable false positives (%)",
                min_value=0, max_value=50, value=10,
                help="At 10%: if 100 flags, 10 can be legitimate customers wrongly blocked"
            )
            st.metric("Acceptable false positives", f"{fp_threshold}%")

            # TODO: Calculate how many legitimate customers get blocked at this threshold
            # using a DuckDB query
            st.warning("TODO: Query DuckDB to calculate how many legit customers are blocked.")

        with col1:
            st.markdown("### Transaction Verdicts")
            # TODO: Show each flagged transaction and let user select FRAUD / LEGITIMATE / INVESTIGATE
            # Use st.radio or st.selectbox per transaction
            st.warning("TODO: Build verdict selector for each flagged transaction.")

        st.markdown("---")
        st.markdown("### 📊 Impact Summary")

        # TODO: After verdicts are set, show:
        # - Total transactions reviewed
        # - Flagged as FRAUD
        # - Flagged as LEGITIMATE (false positives)
        # - Revenue protected vs revenue at risk
        st.warning("TODO: Show impact summary metrics using st.metric()")

        st.markdown("---")
        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "Describe one specific case where the AI was confidently wrong:",
            placeholder="Example: AI flagged TXN___ as CRITICAL fraud because ___, but it was actually ___ because ___",
            height=100
        )
        if st.button("💾 Save Verdict"):
            if ai_wrong.strip():
                verdict = {
                    "fp_threshold": fp_threshold,
                    "ai_got_wrong": ai_wrong,
                    "team": "team1_fraud_hunter"
                }
                with open("verdict.json", "w") as f:
                    json.dump(verdict, f, indent=2)
                st.success("Verdict saved to verdict.json — include in your GitHub push!")
            else:
                st.error("Fill in 'What AI Got Wrong' before saving.")
