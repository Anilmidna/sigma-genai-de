"""
Team 7 — Schema Archaeologist
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team7_schema_archaeologist/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import json
from bedrock_helper import call_nova_lite, call_nova_pro
from sample_data import SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, MIGRATION_V1_TO_V2, MIGRATION_V2_TO_V3

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Schema Archaeologist", layout="wide")
st.title("🏺 Schema Archaeologist")
st.caption("Sigma DataTech AI Ops Platform — Team 7")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

@st.cache_data
def load_schema_data():
    v1 = conn.execute("SELECT * FROM txn_v1 LIMIT 5").df()
    v2 = conn.execute("SELECT * FROM txn_v2 LIMIT 5").df()
    v3 = conn.execute("SELECT * FROM txn_v3 LIMIT 5").df()
    return v1, v2, v3

v1_df, v2_df, v3_df = load_schema_data()

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Historian", "Round 2 — AI Risk Auditor", "Round 3 — Your Finding"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Historian")
    st.info("Nova Pro compares the 3 schema versions and writes the business story behind each change.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Schema v1**")
        st.code(SCHEMA_V1, language="sql")
        st.dataframe(v1_df, use_container_width=True)
    with col2:
        st.markdown("**Schema v2**")
        st.code(SCHEMA_V2, language="sql")
        st.dataframe(v2_df, use_container_width=True)
    with col3:
        st.markdown("**Schema v3**")
        st.code(SCHEMA_V3, language="sql")
        st.dataframe(v3_df, use_container_width=True)

    if st.button("📜 Generate Business History", type="primary"):
        with st.spinner("Nova Pro reconstructing schema history..."):

            # TODO: Write a system prompt making Nova Pro a data archaeologist
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a data historian who can infer business decisions from schema changes.
For each schema version change, it should explain: what changed, what business event likely caused it,
and what teams were probably involved (product, legal, analytics, etc.)."""

            # TODO: Ask Nova Pro to tell the business story
            user_message = f"""TODO: Ask Nova Pro to write the business story behind each schema change.
Schema v1: {SCHEMA_V1}
Schema v2: {SCHEMA_V2}
Schema v3: {SCHEMA_V3}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["history"] = response

    if "history" in st.session_state:
        st.markdown("### Schema History")
        st.markdown(st.session_state["history"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Risk Auditor")
    st.info("Nova Lite reviews the migration SQL and assigns risk scores (LOW/MEDIUM/HIGH/CRITICAL).")

    if "history" not in st.session_state:
        st.warning("Generate Round 1 first.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Migration v1 → v2**")
            st.code(MIGRATION_V1_TO_V2, language="sql")
        with col2:
            st.markdown("**Migration v2 → v3**")
            st.code(MIGRATION_V2_TO_V3, language="sql")

        if st.button("⚠️ Run Risk Audit", type="primary"):
            with st.spinner("Nova Lite auditing migration risk..."):

                # TODO: Write a system prompt for a database migration risk auditor
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should act as a cautious DBA reviewing migration scripts.
For each migration step, assign: risk_level (LOW/MEDIUM/HIGH/CRITICAL),
specific_concern, and what would break if the concern materialises."""

                # TODO: Pass migration scripts to Nova Lite
                user_message = f"""TODO: Ask Nova Lite to audit both migrations for risk.
Migration v1→v2: {MIGRATION_V1_TO_V2}
Migration v2→v3: {MIGRATION_V2_TO_V3}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["risk_audit"] = response

    if "risk_audit" in st.session_state:
        st.markdown("### Risk Audit Results")
        st.warning(st.session_state["risk_audit"])

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Your Archaeological Finding")
    st.info("Find the migration step that silently breaks a downstream query — no error, wrong results.")

    if "risk_audit" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Your Investigation")
        st.info("💡 Hint: Write a query that would be commonly used by the analytics team. "
                "Run it against txn_v2, then run the same query against txn_v3. Compare results.")

        # TODO: Write the query that silently breaks after v2→v3 migration
        st.code("""# TODO: Write the query that breaks silently after v2→v3 migration
# Hint: think about what column was removed and what business questions depend on it
# Example: a payment method filter that returns correct results on v2 but wrong on v3
#
# conn.execute("SELECT ... FROM txn_v2 WHERE ...").df()  # correct result
# conn.execute("SELECT ... FROM txn_v3 WHERE ...").df()  # silent failure
""", language="python")

        st.markdown("### Evidence of Silent Failure")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**v2 query result (correct)**")
            # TODO: Run and display v2 query result
            st.warning("TODO: Show v2 query result")
        with c2:
            st.markdown("**v3 query result (wrong — no error)**")
            # TODO: Run and display v3 query result
            st.warning("TODO: Show v3 query result — should look correct but be wrong")

        dangerous_step = st.text_area(
            "Which migration step is actually CRITICAL (not what AI rated it)?",
            placeholder="The step '___' drops column ___. The risk audit rated it ___, but it's actually CRITICAL because "
                        "any query filtering by ___ will silently return ___ instead of an error.",
            height=100
        )

        safer_migration = st.text_area(
            "Your safer migration proposal:",
            placeholder="Instead of dropping ___, we should ___ so that downstream queries ___",
            height=80
        )

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "What risk did the AI miss or underrate?",
            height=80
        )

        if st.button("💾 Save Finding"):
            if dangerous_step.strip():
                result = {
                    "dangerous_step": dangerous_step,
                    "safer_migration": safer_migration,
                    "ai_got_wrong": ai_wrong,
                    "team": "team7_schema_archaeologist"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Finding saved!")
            else:
                st.error("Describe the dangerous step first.")
