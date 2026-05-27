"""
Team 6 — Incident Commander
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team6_incident_commander/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import json
from bedrock_helper import call_nova_lite, call_nova_pro
from sample_data import PROD_STACK_TRACE

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Incident Commander", layout="wide")
st.title("🚨 Incident Commander")
st.caption("Sigma DataTech AI Ops Platform — Team 6")
st.error("⏰ It's 2:47 AM. Pipeline failed. 15 minutes before CEO wakes up.")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

tab1, tab2, tab3 = st.tabs(["Round 1 — First Responder", "Round 2 — Devil's Advocate", "Round 3 — Investigation"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI First Responder")
    st.info("Nova Pro reads the stack trace and declares severity, root cause, and immediate fix.")

    st.markdown("### 📟 Production Stack Trace")
    st.code(PROD_STACK_TRACE, language="text")

    if st.button("🚨 Triage Incident", type="primary"):
        with st.spinner("Nova Pro triaging..."):

            # TODO: Write a system prompt making Nova Pro a senior SRE on-call
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as an experienced SRE doing incident triage.
Output must include: severity (P1/P2/P3), root_cause_hypothesis, immediate_fix,
time_to_resolve_estimate, and whether to wake the engineering team now."""

            # TODO: Pass the stack trace for triage
            user_message = f"""TODO: Pass the stack trace and ask for incident triage.
Stack trace:
{PROD_STACK_TRACE}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["triage"] = response

    if "triage" in st.session_state:
        st.markdown("### First Responder Report")
        st.error(st.session_state["triage"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Devil's Advocate")
    st.info("Nova Lite generates an alternative root cause that also fits the stack trace.")

    if "triage" not in st.session_state:
        st.warning("Run Round 1 first.")
    else:
        if st.button("🔄 Generate Alternative Hypothesis", type="primary"):
            with st.spinner("Nova Lite building alternative hypothesis..."):

                # TODO: Write a system prompt making Nova Lite a contrarian investigator
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should challenge the Round 1 hypothesis.
It must propose a different root cause that also explains the same stack trace.
It should explain why the Round 1 fix might not resolve the real problem."""

                # TODO: Pass triage and stack trace to Nova Lite
                user_message = f"""TODO: Ask Nova Lite to propose an alternative hypothesis.
Stack trace: {PROD_STACK_TRACE}
Round 1 diagnosis: {st.session_state['triage']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["alt_hypothesis"] = response

    if "alt_hypothesis" in st.session_state:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Hypothesis 1 (Round 1)**")
            st.error(st.session_state.get("triage", ""))
        with c2:
            st.markdown("**Hypothesis 2 (Round 2)**")
            st.warning(st.session_state["alt_hypothesis"])

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: DuckDB Investigation")
    st.info("Query the data to determine which hypothesis is correct — or find what both missed.")

    if "alt_hypothesis" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Your Investigation Queries")
        st.info("💡 Hint: The stack trace mentions TXN012. Start there. Check BOTH bronze and silver tables.")

        # TODO: Write DuckDB queries to investigate
        # Suggested queries to run:
        investigation_queries = {
            "Check TXN012 in bronze":    "TODO: Write query to check TXN012 in bronze_transactions",
            "Count TXN012 occurrences":  "TODO: Write query to count how many times TXN012 appears",
            "Check source data":         "TODO: Write query to check if duplicate exists in source",
        }

        for label, query in investigation_queries.items():
            st.markdown(f"**{label}**")
            st.code(query, language="sql")
            # TODO: Execute query and show result
            st.warning(f"TODO: Execute and display result of '{label}'")

        st.markdown("---")
        st.markdown("### Your Finding")
        finding = st.text_area(
            "What DuckDB revealed (the actual root cause):",
            placeholder="The data shows that TXN012 appears ___ times in bronze because ___. "
                        "This means the real root cause is ___, not what either AI hypothesis said.",
            height=120
        )

        severity = st.radio("Final severity:", ["P1 — Wake everyone now", "P2 — Fix by 6 AM", "P3 — Fix in morning standup"])

        ceo_summary = st.text_input(
            "One-line CEO summary (what happened, impact, ETA to fix):",
            placeholder="Pipeline failure at 2:47 AM due to ___. ___ transactions affected. Fix ETA: ___."
        )

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "Which hypothesis was wrong and why was it plausible?",
            height=80
        )

        if st.button("💾 Save Incident Report"):
            if finding.strip() and ceo_summary.strip():
                result = {
                    "finding": finding,
                    "severity": severity,
                    "ceo_summary": ceo_summary,
                    "ai_got_wrong": ai_wrong,
                    "team": "team6_incident_commander"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Incident report saved!")
            else:
                st.error("Fill in finding and CEO summary first.")
