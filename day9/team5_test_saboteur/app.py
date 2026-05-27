"""
Team 5 — Test Saboteur
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team5_test_saboteur/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import json
import subprocess
import tempfile
from bedrock_helper import call_nova_lite, call_nova_pro
from sample_data import TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY, MERCHANTS

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Test Saboteur", layout="wide")
st.title("🧨 Test Saboteur")
st.caption("Sigma DataTech AI Ops Platform — Team 5")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

# The pipeline functions being tested
PIPELINE_SOURCE = """
from collections import defaultdict

def transform_bronze_to_silver(transactions, merchants):
    merchant_map = {m["merchant_id"]: m for m in merchants}
    seen_ids = set()
    silver = []
    for txn in transactions:
        if txn["transaction_id"] is None:
            continue
        if txn["amount"] < 0:
            continue
        if txn["transaction_id"] in seen_ids:
            continue
        seen_ids.add(txn["transaction_id"])
        m = merchant_map.get(txn["merchant_id"], {})
        silver.append({**txn,
            "merchant_name": m.get("merchant_name"),
            "category": m.get("category"),
            "quality_flag": "CLEAN" if txn["merchant_id"] in merchant_map else "UNMATCHED"
        })
    return silver

def compute_merchant_performance(silver_rows):
    agg = defaultdict(lambda: {"rev": 0.0, "total": 0, "failed": 0})
    for row in silver_rows:
        mid = row["merchant_id"]
        agg[mid]["total"] += 1
        if row["status"] == "COMPLETED": agg[mid]["rev"] += row["amount"]
        if row["status"] == "FAILED":    agg[mid]["failed"] += 1
    return [{"merchant_id": k, "total_revenue": v["rev"],
             "txn_count": v["total"],
             "failure_rate_pct": round(v["failed"]/v["total"]*100, 2)}
            for k, v in agg.items()]
"""

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Test Generator", "Round 2 — AI Test Critic", "Round 3 — Your Audit"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Test Generator")
    st.info("Nova Pro generates 8-10 pytest tests for the Silver pipeline functions.")

    with st.expander("Pipeline source being tested"):
        st.code(PIPELINE_SOURCE, language="python")

    if st.button("🧪 Generate Test Suite", type="primary"):
        with st.spinner("Nova Pro writing pytest suite..."):

            # TODO: Write a system prompt for a test engineer
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a senior QA engineer.
Output: a complete pytest file with 8-10 tests.
Tests should cover: null filtering, deduplication, negative amount filtering,
merchant enrichment, edge cases (empty list, all dirty, all duplicates)."""

            # TODO: Ask Nova Pro to generate the test suite
            user_message = f"""TODO: Ask Nova Pro to generate pytest tests for these functions.
Pipeline code:
{PIPELINE_SOURCE}

Sample data available: TRANSACTIONS_CLEAN ({len(TRANSACTIONS_CLEAN)} rows),
TRANSACTIONS_DIRTY ({len(TRANSACTIONS_DIRTY)} rows), MERCHANTS ({len(MERCHANTS)} entries)"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["test_suite"] = response

    if "test_suite" in st.session_state:
        st.markdown("### Generated Test Suite")
        st.code(st.session_state["test_suite"], language="python")

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Test Critic")
    st.info("Nova Lite reviews each test and scores it: STRONG / WEAK / USELESS. Find the saboteur.")

    if "test_suite" not in st.session_state:
        st.warning("Generate the test suite first.")
    else:
        if st.button("🔎 Critique Tests", type="primary"):
            with st.spinner("Nova Lite auditing the test suite..."):

                # TODO: Write a system prompt for a test critic
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should act as a security-minded QA lead.
For each test function, output: test_name, score (STRONG/WEAK/USELESS), reason.
Pay special attention to: tests that could pass even when the function is broken,
tests with logical flaws in the assertion, tests that test the wrong thing."""

                # TODO: Ask Nova Lite to critique each test
                user_message = f"""TODO: Ask Nova Lite to critique every test in the suite.
Test suite:
{st.session_state['test_suite']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["critique"] = response

    if "critique" in st.session_state:
        st.markdown("### Test Critique")
        st.markdown(st.session_state["critique"])

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Your Audit — Find the Saboteur")
    st.info("Find the test that always passes even when the pipeline is broken. Prove it.")

    if "critique" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Run the Tests")
        if st.button("▶️ Run Test Suite"):
            with st.spinner("Running pytest..."):
                # TODO: Save the generated test suite to a temp file and run pytest
                # Hint: use subprocess.run(["python", "-m", "pytest", test_file, "-v"])
                st.warning("TODO: Save test suite to a temp file and run pytest via subprocess. Show pass/fail output.")

        st.markdown("---")
        st.markdown("### Identify the Saboteur")
        saboteur_name = st.text_input(
            "Name of the saboteur test (function name):",
            placeholder="test_..."
        )

        st.markdown("### Prove It — Counter-Example")
        st.info("Write input data that should FAIL the pipeline logic, but PASSES the saboteur test.")

        saboteur_proof = st.text_area(
            "Your counter-example (Python code):",
            placeholder="""# Example structure:
# broken_data = [...]  # data that SHOULD be rejected
# result = transform_bronze_to_silver(broken_data, MERCHANTS)
# # The saboteur test passes, but result contains wrong data
# assert ...  # show what the saboteur wrongly accepts""",
            height=150
        )

        st.markdown("### Fixed Test")
        fixed_test = st.text_area(
            "Your corrected version of the saboteur test:",
            placeholder="def test_...()\n    # Fixed version that actually catches the bug",
            height=120
        )

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "Did the AI critic catch the saboteur in Round 2?",
            placeholder="The AI critic rated ___ as STRONG/WEAK but missed that it would always pass because ___",
            height=80
        )

        if st.button("💾 Save Audit"):
            if saboteur_name.strip():
                result = {
                    "saboteur_test": saboteur_name,
                    "counter_example": saboteur_proof,
                    "fixed_test": fixed_test,
                    "ai_got_wrong": ai_wrong,
                    "team": "team5_test_saboteur"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Audit saved!")
            else:
                st.error("Name the saboteur test first.")
