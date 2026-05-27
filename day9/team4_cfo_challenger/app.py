"""
Team 4 — CFO Challenger
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team4_cfo_challenger/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import pandas as pd
import json
from bedrock_helper import call_nova_lite, call_nova_pro

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="CFO Challenger", layout="wide")
st.title("💼 CFO Challenger")
st.caption("Sigma DataTech AI Ops Platform — Team 4")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

@st.cache_data
def load_gold_metrics():
    merchant = conn.execute("SELECT * FROM gold_merchant_performance ORDER BY total_revenue DESC").df()
    daily    = conn.execute("SELECT * FROM gold_daily_summary ORDER BY report_date").df()
    return merchant, daily

merchant_df, daily_df = load_gold_metrics()

tab1, tab2, tab3 = st.tabs(["Round 1 — CEO Briefing", "Round 2 — CFO Challenge", "Round 3 — Fact Check"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI CEO Briefing")
    st.info("Nova Pro generates a 5-bullet Monday morning revenue briefing from Gold metrics.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Merchant Performance**")
        st.dataframe(merchant_df, use_container_width=True)
    with col2:
        st.markdown("**Daily Summary**")
        st.dataframe(daily_df, use_container_width=True)

    if st.button("📊 Generate CEO Briefing", type="primary"):
        with st.spinner("Nova Pro writing Monday briefing..."):

            # TODO: Write a system prompt for a business intelligence writer
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a BI analyst writing a concise CEO briefing.
Output: exactly 5 bullet points with specific numbers from the data.
Each bullet should include a trend or comparison (not just raw numbers)."""

            # TODO: Pass Gold metrics and ask for a 5-bullet briefing
            user_message = f"""TODO: Ask Nova Pro to generate the CEO briefing.
Merchant data: {merchant_df.to_json(orient='records')}
Daily data: {daily_df.to_json(orient='records')}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["briefing"] = response

    if "briefing" in st.session_state:
        st.markdown("### Monday Morning Briefing")
        st.info(st.session_state["briefing"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: CFO Challenge")
    st.info("Nova Lite plays a skeptical CFO and challenges 3 specific claims. Each challenge demands: 'Show me the data.'")

    if "briefing" not in st.session_state:
        st.warning("Generate Round 1 first.")
    else:
        if st.button("💬 Run CFO Challenge", type="primary"):
            with st.spinner("Nova Lite channelling the CFO..."):

                # TODO: Write a system prompt making Nova Lite a skeptical CFO
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should act as a tough CFO who has been burned by wrong reports before.
It should challenge exactly 3 claims from the briefing.
For each challenge: state the claim, state the concern, ask the specific data question."""

                # TODO: Pass the briefing to Nova Lite and ask for CFO challenges
                user_message = f"""TODO: Pass the CEO briefing and ask Nova Lite to challenge 3 claims.
Briefing: {st.session_state['briefing']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["challenges"] = response

    if "challenges" in st.session_state:
        st.markdown("### CFO's 3 Challenges")
        st.warning(st.session_state["challenges"])

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Fact Check")
    st.info("Run DuckDB queries to verify or refute each CFO challenge. Mark each: VERIFIED / WRONG / MISLEADING.")

    if "challenges" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Run Your Verification Queries")

        # TODO: For each of the 3 CFO challenges, write a DuckDB query that proves or disproves it
        st.code("""# TODO: Write 3 DuckDB queries — one per CFO challenge
# Hint for the trap: check how many data points the 'trend' claim is based on
# Example:
# conn.execute("SELECT COUNT(*) FROM gold_daily_summary").fetchone()
# conn.execute("SELECT report_date, total_revenue FROM gold_daily_summary ORDER BY report_date").df()
""", language="python")

        st.markdown("### Verdict Table")
        # TODO: Build a table with 3 rows (one per claim) and columns: Claim | CFO Concern | Your Query Result | Verdict
        st.warning("TODO: Build verdict table — 3 claims × 4 columns (Claim, Challenge, Query Result, VERIFIED/WRONG/MISLEADING)")

        st.markdown("### The Confidently Wrong Claim")
        # TODO: Identify which claim is statistically invalid and explain why
        wrong_claim = st.text_area(
            "Which claim is misleading and why?",
            placeholder="Claim ___ says '___'. This is misleading because it's based on only ___ data points, which is not enough to ___",
            height=100
        )

        trust_score = st.slider("Your AI trust score for business insights (0-100%)", 0, 100, 60)
        trust_reason = st.text_input("One-line justification for your trust score:")

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "The claim that sounds most convincing but is statistically invalid:",
            height=80
        )

        if st.button("💾 Save Fact Check"):
            if wrong_claim.strip():
                result = {
                    "wrong_claim": wrong_claim,
                    "trust_score": trust_score,
                    "trust_reason": trust_reason,
                    "ai_got_wrong": ai_wrong,
                    "team": "team4_cfo_challenger"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Fact check saved!")
            else:
                st.error("Fill in the wrong claim field first.")
