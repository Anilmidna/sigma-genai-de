"""
Team 8 — Synthetic Data Judge
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team8_synthetic_data_judge/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import pandas as pd
import json
from bedrock_helper import call_nova_lite, call_nova_pro

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Synthetic Data Judge", layout="wide")
st.title("🧬 Synthetic Data Judge")
st.caption("Sigma DataTech AI Ops Platform — Team 8")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

@st.cache_data
def load_data():
    real = conn.execute("SELECT * FROM silver_transactions ORDER BY transaction_date").df()
    synth = conn.execute("SELECT * FROM synthetic_transactions ORDER BY transaction_date").df()
    return real, synth

real_df, synth_df = load_data()

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Statistician", "Round 2 — AI Domain Expert", "Round 3 — Your Judgement"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Statistician")
    st.info("Nova Pro compares statistical properties of real vs synthetic data and assigns a realism score.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Real Transactions (Silver)**")
        st.dataframe(real_df, use_container_width=True, height=250)
        st.markdown(f"Count: {len(real_df)} | Avg amount: ₹{real_df['amount'].mean():.0f}")
    with col2:
        st.markdown("**Synthetic Transactions**")
        st.dataframe(synth_df, use_container_width=True, height=250)
        st.markdown(f"Count: {len(synth_df)} | Avg amount: ₹{synth_df['amount'].mean():.0f}")

    if st.button("📊 Run Statistical Comparison", type="primary"):
        with st.spinner("Nova Pro running statistical analysis..."):

            # TODO: Write a system prompt for a statistical analyst
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a statistician comparing two datasets.
It should compare: mean, std, min/max, null rates, cardinality, value distributions.
Output a realism_score (0-100) with specific statistical justification for the score."""

            # Compute basic stats to pass to Nova Pro
            real_stats = {
                "count": len(real_df),
                "amount_mean": round(real_df["amount"].mean(), 2),
                "amount_std": round(real_df["amount"].std(), 2),
                "amount_min": real_df["amount"].min(),
                "amount_max": real_df["amount"].max(),
                "status_counts": real_df["status"].value_counts().to_dict(),
                "payment_method_counts": real_df["payment_method"].value_counts().to_dict(),
            }
            synth_stats = {
                "count": len(synth_df),
                "amount_mean": round(synth_df["amount"].mean(), 2),
                "amount_std": round(synth_df["amount"].std(), 2),
                "amount_min": synth_df["amount"].min(),
                "amount_max": synth_df["amount"].max(),
                "status_counts": synth_df["status"].value_counts().to_dict(),
                "payment_method_counts": synth_df["payment_method"].value_counts().to_dict(),
            }

            # TODO: Ask Nova Pro to compare and score
            user_message = f"""TODO: Ask Nova Pro to compare these stats and give a realism score.
Real data stats: {json.dumps(real_stats)}
Synthetic data stats: {json.dumps(synth_stats)}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["stats_report"] = response

    if "stats_report" in st.session_state:
        st.markdown("### Statistical Report")
        st.markdown(st.session_state["stats_report"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Domain Expert")
    st.info("Nova Lite reviews the synthetic data from a business rules perspective — not statistics.")

    if "stats_report" not in st.session_state:
        st.warning("Run Round 1 first.")
    else:
        if st.button("🔍 Run Domain Expert Review", type="primary"):
            with st.spinner("Nova Lite checking business rules..."):

                # TODO: Write a system prompt for a payments domain expert
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should act as a payments domain expert who knows Indian fintech rules.
It should find transactions that are statistically plausible but domain-impossible.
Examples to look for: payment limits, valid status values, valid merchant IDs, date sanity."""

                # TODO: Ask Nova Lite to find domain impossibilities
                user_message = f"""TODO: Ask Nova Lite to find domain-impossible records in the synthetic data.
Synthetic transactions: {synth_df.to_json(orient='records')}
Real merchants: {conn.execute('SELECT merchant_id, merchant_name FROM merchants').df().to_json(orient='records')}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["domain_review"] = response

    if "domain_review" in st.session_state:
        st.markdown("### Domain Expert Findings")
        st.warning(st.session_state["domain_review"])

        st.info("💡 Note: The statistical realism score from Round 1 will be high. "
                "The domain issues are invisible to statistics.")

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Your Judgement")
    st.info("Validate domain expert findings with DuckDB queries. Classify each issue and give final verdict.")

    if "domain_review" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Validate With DuckDB")
        st.code("""# TODO: Write DuckDB queries to prove each domain impossibility
# Example queries:
# conn.execute("SELECT * FROM synthetic_transactions WHERE payment_method='UPI' AND amount > 100000").df()
# conn.execute("SELECT * FROM synthetic_transactions WHERE status NOT IN ('COMPLETED','FAILED','PENDING')").df()
# conn.execute("SELECT s.* FROM synthetic_transactions s LEFT JOIN merchants m ON s.merchant_id=m.merchant_id WHERE m.merchant_id IS NULL").df()
# conn.execute("SELECT * FROM synthetic_transactions WHERE transaction_date > '2025-01-01'").df()
""", language="python")

        # TODO: Run and display each query result
        st.warning("TODO: Execute the queries above and show results.")

        st.markdown("### Issue Classification")
        # TODO: For each domain issue found, classify CRITICAL / MINOR / FALSE ALARM
        st.warning("TODO: Build a table of issues × classification (CRITICAL/MINOR/FALSE ALARM)")

        st.markdown("### Final Verdict")
        verdict = st.radio(
            "Is this synthetic data safe to use for testing?",
            ["✅ SAFE — issues are minor, acceptable for testing",
             "⚠️ CONDITIONALLY SAFE — fix these specific issues first",
             "❌ NOT SAFE — would cause tests to give false passes"]
        )
        confidence = st.slider("Confidence in your verdict (%)", 0, 100, 70)

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "How did statistics miss what domain knowledge caught?",
            placeholder="The statistical realism score was ___% because ___. "
                        "But statistics couldn't detect ___ because ___.",
            height=100
        )

        if st.button("💾 Save Judgement"):
            if ai_wrong.strip():
                result = {
                    "verdict": verdict,
                    "confidence": confidence,
                    "ai_got_wrong": ai_wrong,
                    "team": "team8_synthetic_data_judge"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Judgement saved!")
            else:
                st.error("Fill in 'What AI Got Wrong' first.")
