"""
Team 9 — Runbook Guardian
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team9_runbook_guardian/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import json
from bedrock_helper import call_nova_lite, call_nova_pro
from sample_data import PIPELINE_V2_CODE

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Runbook Guardian", layout="wide")
st.title("📖 Runbook Guardian")
st.caption("Sigma DataTech AI Ops Platform — Team 9")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

tab1, tab2, tab3 = st.tabs(["Round 1 — AI Runbook Writer", "Round 2 — Junior Engineer", "Round 3 — Gap Analysis"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Runbook Writer")
    st.info("Nova Pro reads the Silver pipeline code and generates a complete operational runbook.")

    with st.expander("Pipeline code being documented"):
        st.code(PIPELINE_V2_CODE, language="python")

    if st.button("📝 Generate Runbook", type="primary"):
        with st.spinner("Nova Pro writing runbook..."):

            # TODO: Write a system prompt for a runbook author
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a senior DE writing an operational runbook for on-call engineers.
The runbook should cover: setup/prerequisites, normal operation steps,
how to validate success, known failure modes, recovery steps, escalation path.
Target audience: a junior engineer reading this at 3 AM for the first time."""

            # TODO: Ask Nova Pro to generate the runbook from the pipeline code
            user_message = f"""TODO: Ask Nova Pro to generate the runbook.
Pipeline code:
{PIPELINE_V2_CODE}

Context: This pipeline loads Bronze transactions into Silver layer in DuckDB.
It runs nightly at 2 AM. If it fails, __ transactions are not processed until next run."""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["runbook"] = response

    if "runbook" in st.session_state:
        st.markdown("### Generated Runbook")
        st.markdown(st.session_state["runbook"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: Junior Engineer Simulator")
    st.info("Nova Lite plays a confused junior engineer reading the runbook for the first time. Asks 5 questions.")

    if "runbook" not in st.session_state:
        st.warning("Generate Round 1 first.")
    else:
        if st.button("🙋 Simulate Junior Engineer", type="primary"):
            with st.spinner("Nova Lite playing junior engineer..."):

                # TODO: Write a system prompt making Nova Lite a nervous junior engineer
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should play a junior engineer who just got paged at 3 AM.
They are reading this runbook for the first time and are confused.
They must ask EXACTLY 5 questions — the questions a real new hire would ask.
At least one question should reveal a genuine gap in the runbook or the pipeline itself."""

                # TODO: Ask Nova Lite to read the runbook and ask 5 questions
                user_message = f"""TODO: Ask Nova Lite to read this runbook as a junior engineer and ask 5 questions.
Runbook:
{st.session_state['runbook']}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["questions"] = response

    if "questions" in st.session_state:
        st.markdown("### Junior Engineer's 5 Questions")
        st.warning(st.session_state["questions"])

        st.markdown("---")
        st.markdown("### 🔍 Which question reveals a real gap?")
        st.info("One of these questions will reveal something the runbook can't answer "
                "because the pipeline itself doesn't handle it. Find it.")

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Gap Analysis")
    st.info("Classify each question. Fix the runbook. Find the question that exposed a pipeline gap.")

    if "questions" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        st.markdown("### Question Classification")
        # TODO: For each of the 5 questions, show a selectbox:
        # RUNBOOK GAP / GOOD QUESTION (real pipeline issue) / UNNECESSARY
        st.warning("TODO: Build a selectbox for each of the 5 questions — classify each one.")

        st.markdown("---")
        st.markdown("### The Real Pipeline Gap")
        real_gap = st.text_area(
            "Which question revealed a gap in the PIPELINE (not just the docs)?",
            placeholder="Question ___ asked '___'. This reveals that if ___ happens, "
                        "the pipeline has no way to ___ because the code doesn't ___. "
                        "This means: [business consequence].",
            height=120
        )

        st.markdown("### Updated Runbook Snippet")
        st.info("Fix the most critical gap. Show before and after.")
        updated_section = st.text_area(
            "Updated runbook section (the gap you fixed):",
            placeholder="## Failure Recovery\n\nIf the Silver insert fails partway through:\n1. ...",
            height=150
        )

        st.markdown("### Code Fix Proposal")
        code_fix = st.text_area(
            "What code change would make the runbook easier to write?",
            placeholder="# Add a transaction wrapper so partial failures are rolled back:\n"
                        "# with duckdb.connect(...) as con:\n#     con.begin()\n#     ...\n#     con.commit()",
            height=120
        )

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "What critical scenario did the runbook miss entirely?",
            placeholder="The runbook covers ___ but completely misses ___. "
                        "This would be a problem in production because ___.",
            height=80
        )

        if st.button("💾 Save Gap Analysis"):
            if real_gap.strip():
                result = {
                    "real_gap": real_gap,
                    "updated_runbook_section": updated_section,
                    "code_fix": code_fix,
                    "ai_got_wrong": ai_wrong,
                    "team": "team9_runbook_guardian"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Gap analysis saved!")
            else:
                st.error("Describe the real pipeline gap first.")
