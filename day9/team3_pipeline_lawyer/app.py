"""
Team 3 — Pipeline Lawyer
Sigma AI Ops Platform | Day 9 Case Study

Run: streamlit run app.py   (from repo/day9/team3_pipeline_lawyer/)
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
import json
from bedrock_helper import call_nova_lite, call_nova_pro
from sample_data import PIPELINE_V1_CODE, PIPELINE_V2_CODE

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(page_title="Pipeline Lawyer", layout="wide")
st.title("⚖️ Pipeline Lawyer")
st.caption("Sigma DataTech AI Ops Platform — Team 3")

@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

tab1, tab2, tab3 = st.tabs(["Round 1 — PRO-Merge Brief", "Round 2 — AGAINST-Merge Brief", "Round 3 — Your Verdict"])

# ─────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Round 1: AI Prosecutor — PRO-Merge Brief")
    st.info("Nova Pro reads both pipeline versions and argues FOR merging the change.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pipeline v1 (original — has idempotency bug)**")
        st.code(PIPELINE_V1_CODE, language="python")
    with col2:
        st.markdown("**Pipeline v2 (PR — proposed fix)**")
        st.code(PIPELINE_V2_CODE, language="python")

    if st.button("📋 Generate PRO-Merge Brief", type="primary"):
        with st.spinner("Nova Pro building the case FOR merging..."):

            # TODO: Write a system prompt making Nova Pro act as a lawyer arguing FOR the merge
            system_prompt = """TODO: Write a system prompt here.
Hint: Nova Pro should act as a senior engineer presenting a code review approval.
It should list specific improvements in v2 over v1, with line references."""

            # TODO: Ask Nova Pro to compare v1 and v2 and argue for merging
            user_message = f"""TODO: Ask Nova Pro to write a PRO-merge brief.
Pipeline v1:\n{PIPELINE_V1_CODE}\n\nPipeline v2:\n{PIPELINE_V2_CODE}"""

            response = call_nova_pro(system_prompt, user_message)
            st.session_state["pro_brief"] = response

    if "pro_brief" in st.session_state:
        st.markdown("### PRO-Merge Brief")
        st.success(st.session_state["pro_brief"])

# ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Round 2: AI Defense — AGAINST-Merge Brief")
    st.info("Nova Lite reads the same code and finds risks, edge cases, and potential failures.")

    if "pro_brief" not in st.session_state:
        st.warning("Generate Round 1 first.")
    else:
        if st.button("📋 Generate AGAINST-Merge Brief", type="primary"):
            with st.spinner("Nova Lite building the case AGAINST merging..."):

                # TODO: Write a system prompt making Nova Lite a skeptical tech lead
                system_prompt = """TODO: Write a system prompt here.
Hint: Nova Lite should act as a skeptical senior engineer who is risk-averse.
It should find edge cases, hidden assumptions, and scenarios where v2 could fail."""

                # TODO: Ask Nova Lite to argue against the merge
                user_message = f"""TODO: Ask Nova Lite to write an AGAINST-merge brief.
Pipeline v1:\n{PIPELINE_V1_CODE}\n\nPipeline v2:\n{PIPELINE_V2_CODE}"""

                response = call_nova_lite(system_prompt, user_message)
                st.session_state["against_brief"] = response

    if "against_brief" in st.session_state:
        st.markdown("### AGAINST-Merge Brief")
        st.error(st.session_state["against_brief"])

        st.markdown("---")
        st.markdown("### Side by Side Comparison")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**✅ PRO (Round 1)**")
            st.markdown(st.session_state.get("pro_brief", ""))
        with c2:
            st.markdown("**❌ AGAINST (Round 2)**")
            st.markdown(st.session_state.get("against_brief", ""))

# ─────────────────────────────────────────────────────────────
with tab3:
    st.subheader("Round 3: Your Verdict")
    st.info("You are the tech lead. Approve, reject, or request changes. Justify with a reproduction.")

    if "against_brief" not in st.session_state:
        st.warning("Complete Rounds 1 and 2 first.")
    else:
        verdict = st.radio(
            "Your decision:",
            ["APPROVE — merge as is", "REJECT — do not merge", "REQUEST CHANGES — merge after fix"],
            index=2
        )

        st.markdown("### Reproduce the Bug (if you found it)")
        st.info("Hint: What happens if you call load_silver() twice in the same Python session?")

        # TODO: Write a short Python snippet that demonstrates the bug
        st.code("""# TODO: Write 5 lines of Python that prove your verdict.
# Call load_silver() (or the equivalent transform) twice and show what happens.
# Example structure:
# result1 = transform_bronze_to_silver(data, merchants)
# result2 = transform_bronze_to_silver(data, merchants)  # what's different?
# print(len(result1), len(result2))
""", language="python")

        st.markdown("### Your Exact Change Request")
        change_request = st.text_area(
            "If REJECT or REQUEST CHANGES — write exactly what the developer must fix (one sentence):",
            placeholder="The seen_ids set must be _____ so that _____",
            height=80
        )

        st.markdown("### 🎯 What AI Got Wrong")
        ai_wrong = st.text_area(
            "Which brief was weaker and why?",
            placeholder="The PRO/AGAINST brief missed ___ because AI cannot reason about ___",
            height=80
        )

        if st.button("💾 Save Verdict"):
            if change_request.strip() and ai_wrong.strip():
                result = {
                    "verdict": verdict,
                    "change_request": change_request,
                    "ai_got_wrong": ai_wrong,
                    "team": "team3_pipeline_lawyer"
                }
                with open("verdict.json", "w") as f:
                    json.dump(result, f, indent=2)
                st.success("Verdict saved!")
            else:
                st.error("Fill in both fields before saving.")
