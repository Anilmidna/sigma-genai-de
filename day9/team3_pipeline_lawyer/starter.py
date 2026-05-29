import sys
import os
import json
import streamlit as st
import duckdb

# Add shared folder to path to import helpers
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))
from bedrock_helper import call_nova_lite, call_nova_pro

# Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")

st.set_page_config(
    page_title="Pipeline Lawyer — AI Ops Trial",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium Styling
st.markdown("""
<style>
    .report-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FF4B4B, #FF8F8F);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .card {
        background-color: #1E1E1E;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #333333;
        margin-bottom: 1rem;
    }
    .prosecutor-card {
        border-left: 5px solid #4CAF50;
        background: rgba(76, 175, 80, 0.05);
    }
    .defense-card {
        border-left: 5px solid #F44336;
        background: rgba(244, 67, 54, 0.05);
    }
    .card-title {
        font-weight: 700;
        font-size: 1.3rem;
        margin-bottom: 0.8rem;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="report-title">⚖️ Pipeline Lawyer</div>', unsafe_allow_html=True)
st.markdown("##### *Sigma DataTech AI Ops Platform — Day 9 Team Project*")
st.markdown("---")

# Pipeline v1 & v2 Source Code
PIPELINE_V1_CODE = '''def load_silver(rows):
    """Load rows into Silver table."""
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        con.execute(
            "INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )'''

PIPELINE_V2_CODE = '''seen_ids = set()  # Global state variable

def load_silver(rows):
    """Load rows into Silver table — idempotent via seen_ids check."""
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        if row["transaction_id"] in seen_ids:
            continue                          # skip duplicate
        seen_ids.add(row["transaction_id"])
        con.execute(
            "INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )'''

# Side-by-Side Code Viewer
col1, col2 = st.columns(2)
with col1:
    st.subheader("🔴 Pipeline v1 (Original)")
    st.caption("Crashes on duplicate transaction IDs due to raw INSERT constraint violations.")
    st.code(PIPELINE_V1_CODE, language="python")

with col2:
    st.subheader("🟡 Pipeline v2 (Junior DE's Proposed PR)")
    st.caption("Attempts to make the load idempotent by filtering duplicates via a global set.")
    st.code(PIPELINE_V2_CODE, language="python")

st.markdown("---")

# Initialize Session State
if "prosecutor_brief" not in st.session_state:
    st.session_state.prosecutor_brief = ""
if "defense_brief" not in st.session_state:
    st.session_state.defense_brief = ""

# Trial Controller
st.subheader("🏛️ Start the Legal Trial")
st.markdown("Deploy our AI lawyers. **Nova Pro** will act as the Prosecutor arguing **FOR** the merge. **Nova Lite** will act as the Defense arguing **AGAINST** the merge, attempting to find any hidden vulnerabilities or traps in the junior's PR.")

if st.button("⚖️ Run AI Arguments & Analyze Code", type="primary"):
    with st.spinner("AI Prosecutor (Nova Pro) is preparing arguments FOR the PR..."):
        pros_system = (
            "You are a Senior Staff Data Engineer. Write a technical code review explaining the positive aspects of the v2 changes, "
            "focusing on how in-memory tracking attempts to handle duplicate items within a single run."
        )
        pros_user = f"Compare this pipeline code:\n\n=== v1 ===\n{PIPELINE_V1_CODE}\n\n=== v2 ===\n{PIPELINE_V2_CODE}"
        st.session_state.prosecutor_brief = call_nova_pro(pros_system, pros_user)
        
    with st.spinner("SRE (Nova Lite) is preparing arguments AGAINST the PR..."):
        def_system = (
            "You are a Principal Reliability Engineer. Write a technical code review explaining the persistence "
            "characteristics of module-level global variables (like seen_ids = set()) in long-running Python process sessions. "
            "Explain how this causes subsequent executions to skip processing items, and recommend a database-native stateless alternative."
        )
        def_user = f"Analyze the v2 code and find the persistence flaw:\n\n{PIPELINE_V2_CODE}"
        st.session_state.defense_brief = call_nova_lite(def_system, def_user)

# Display Side-by-Side Legal Briefs
if st.session_state.prosecutor_brief and st.session_state.defense_brief:
    col_brief_1, col_brief_2 = st.columns(2)
    
    with col_brief_1:
        st.markdown("""
        <div class="card prosecutor-card">
            <div class="card-title">🏛️ Round 1: AI Prosecutor (PRO-Merge)</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(st.session_state.prosecutor_brief)
        
    with col_brief_2:
        st.markdown("""
        <div class="card defense-card">
            <div class="card-title">🛡️ Round 2: AI Defense (AGAINST-Merge)</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown(st.session_state.defense_brief)

    st.markdown("---")

    # The Live Bug Lab
    st.subheader("🪤 The Live Bug Lab: Reproduce the Trap")
    st.markdown("Below, we simulate the production environment of **v2** live. We execute the pipeline twice inside the same running process session using the junior DE's logic. Watch what happens to the database when a subsequent batch runs!")
    
    # 5-line Live Simulation Demo
    sim_col1, sim_col2 = st.columns([2, 1])
    with sim_col1:
        st.markdown("**Live Python Simulation Code executed:**")
        sim_code = """# Simulate a fresh, in-memory DuckDB connection
conn_sim = duckdb.connect(":memory:")
conn_sim.execute("CREATE TABLE silver (transaction_id VARCHAR, amount DOUBLE)")

seen_ids = set() # Global module-level state

def load_silver_v2_sim(rows):
    for row in rows:
        if row["transaction_id"] in seen_ids:
            continue
        seen_ids.add(row["transaction_id"])
        conn_sim.execute("INSERT INTO silver VALUES (?, ?)", [row["transaction_id"], row["amount"]])

# RUN 1: Process first batch
load_silver_v2_sim([{"transaction_id": "TXN_001", "amount": 100.0}])

# RUN 2: Database is refreshed/cleaned or new transaction batch is processed
conn_sim.execute("DELETE FROM silver") # Clear DB (simulate retry / clean state)
load_silver_v2_sim([{"transaction_id": "TXN_001", "amount": 100.0}]) # Rerun
"""
        st.code(sim_code, language="python")
        
    with sim_col2:
        st.markdown("**Execution Results:**")
        
        # Run the actual simulation code live!
        conn_sim = duckdb.connect(":memory:")
        conn_sim.execute("CREATE TABLE silver (transaction_id VARCHAR, amount DOUBLE)")
        
        seen_ids_sim = set()
        
        def load_silver_v2_sim(rows):
            for row in rows:
                if row["transaction_id"] in seen_ids_sim:
                    continue
                seen_ids_sim.add(row["transaction_id"])
                conn_sim.execute("INSERT INTO silver VALUES (?, ?)", [row["transaction_id"], row["amount"]])
                
        # Run 1
        load_silver_v2_sim([{"transaction_id": "TXN_001", "amount": 100.0}])
        r1_count = conn_sim.execute("SELECT COUNT(*) FROM silver").fetchone()[0]
        
        # Run 2
        conn_sim.execute("DELETE FROM silver")
        load_silver_v2_sim([{"transaction_id": "TXN_001", "amount": 100.0}])
        r2_count = conn_sim.execute("SELECT COUNT(*) FROM silver").fetchone()[0]
        
        st.metric(label="Run 1 Rows Stored", value=r1_count, delta="Clean Batch Success")
        st.metric(label="Run 2 Rows Stored (Rerun/Retry)", value=r2_count, delta="-100% Data Loss!", delta_color="inverse")
        
        st.error(f"⚠️ PROOF OF THE TRAP: In Run 2, exactly {r2_count} rows were inserted into the database! The in-memory global state hijacked the database write, causing silent data loss!")

    # The Correct Fix
    st.subheader("💡 The Correct, Robust Fix")
    st.markdown("To make our pipeline truly idempotent without using unsafe global state, we should let the database enforce the data contract natively using `INSERT OR IGNORE` (or a `WHERE NOT EXISTS` check) without maintaining state in-memory:")
    
    correct_fix_code = """def load_silver(rows):
    \"\"\"Load rows safely into Silver table — idempotent via native database constraints.\"\"\"
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        # 1. Database level resolution: Skip if primary key already exists
        con.execute(
            \"\"\"INSERT OR IGNORE INTO silver_transactions 
               VALUES (?, ?, ?, ?, ?)\"\"\",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )"""
    st.code(correct_fix_code, language="python")

    st.markdown("**Live Python Simulation of the Correct Fix:**")
    
    fix_sim_col1, fix_sim_col2 = st.columns([2, 1])
    with fix_sim_col1:
        st.markdown("**Stateless Simulation Code executed:**")
        fix_sim_code = """# Simulate a fresh, in-memory DuckDB connection
conn_fix = duckdb.connect(":memory:")
conn_fix.execute("CREATE TABLE silver_fix (transaction_id VARCHAR PRIMARY KEY, amount DOUBLE)")

def load_silver_fix_sim(rows):
    for row in rows:
        # Database-level resolution: skip if primary key already exists
        conn_fix.execute(
            "INSERT OR IGNORE INTO silver_fix VALUES (?, ?)", 
            [row["transaction_id"], row["amount"]]
        )

# RUN 1: Process first batch
load_silver_fix_sim([{"transaction_id": "TXN_001", "amount": 100.0}])

# RUN 2: Database is cleared (rerun / clean retry)
conn_fix.execute("DELETE FROM silver_fix")
load_silver_fix_sim([{"transaction_id": "TXN_001", "amount": 100.0}]) # Rerun
"""
        st.code(fix_sim_code, language="python")
        
    with fix_sim_col2:
        st.markdown("**Stateless Fix Results:**")
        
        # Execute the fix simulation code live!
        conn_fix = duckdb.connect(":memory:")
        conn_fix.execute("CREATE TABLE silver_fix (transaction_id VARCHAR PRIMARY KEY, amount DOUBLE)")
        
        def load_silver_fix_sim(rows):
            for row in rows:
                conn_fix.execute(
                    "INSERT OR IGNORE INTO silver_fix VALUES (?, ?)", 
                    [row["transaction_id"], row["amount"]]
                )
                
        # Run 1
        load_silver_fix_sim([{"transaction_id": "TXN_001", "amount": 100.0}])
        f1_count = conn_fix.execute("SELECT COUNT(*) FROM silver_fix").fetchone()[0]
        
        # Run 2
        conn_fix.execute("DELETE FROM silver_fix")
        load_silver_fix_sim([{"transaction_id": "TXN_001", "amount": 100.0}])
        f2_count = conn_fix.execute("SELECT COUNT(*) FROM silver_fix").fetchone()[0]
        
        st.metric(label="Run 1 Rows Stored (Fix)", value=f1_count, delta="Clean Batch Success")
        st.metric(label="Run 2 Rows Stored (Fix Rerun)", value=f2_count, delta="100% Correct recovery!", delta_color="normal")
        
        st.success(f"✅ STATELESS SUCCESS: In Run 2, exactly {f2_count} row(s) were successfully loaded! Because we let the database handle constraints natively, reruns work perfectly without any data loss!")

    st.markdown("---")

    # Round 3: The Judge's Verdict
    st.subheader("👨‍⚖️ Round 3: The Judge's Verdict")
    st.markdown("Based on the arguments presented by the AI Prosecutor and AI Defense, record your final verdict for the Tech Lead.")
    
    verdict = st.radio("Final Decision", ["REJECT ❌ (Highly Recommended)", "REQUEST CHANGES ⚠️", "APPROVE PROPOSED PR  (Risk of Data Loss)"])
    
    justification = st.text_area(
        "Veritable Justification (What would you tell the developer to fix?):",
        value="REJECT: The v2 fix uses a module-level global set `seen_ids` which persists in memory across runs, causing silent data loss on subsequent executions in the same process session. Implement `INSERT OR IGNORE` natively instead."
    )
    
    if st.button("🔨 Submit Final Verdict to Tech Lead"):
        # Save results to output for day completion
        output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        verdict_dict = {
            "verdict": verdict,
            "justification": justification,
            "trap_found": "seen_ids_global_state" in justification.lower() or "global" in justification.lower() or "reject" in verdict.lower(),
            "prosecutor_brief": st.session_state.prosecutor_brief,
            "defense_brief": st.session_state.defense_brief,
        }
        
        # Save a success JSON file
        success_path = os.path.join(output_dir, "pipeline_lawyer_success.json")
        with open(success_path, "w", encoding="utf-8") as f:
            json.dump(verdict_dict, f, indent=2, ensure_ascii=False)
            
        st.success(f"🎉 Verdict successfully submitted and saved to `labs/output/pipeline_lawyer_success.json`!")
        st.balloons()
