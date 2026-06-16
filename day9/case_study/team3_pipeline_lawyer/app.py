import sys, os, json, textwrap
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "shared"))

import streamlit as st
import duckdb
from bedrock_helper import call_nova_lite, call_nova_pro

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "shared", "sigma_platform.duckdb")
VERDICT_PATH = os.path.join(os.path.dirname(__file__), "verdict.json")

st.set_page_config(
    page_title="Pipeline Lawyer — Sigma AI Ops",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Dark gradient background */
.stApp {
    background: linear-gradient(135deg, #0d0d1a 0%, #111827 50%, #0d1117 100%);
    color: #e2e8f0;
}

/* Header banner */
.hero-banner {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 4px 32px rgba(0,0,0,0.4);
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
}
.hero-sub {
    color: #94a3b8;
    font-size: 1rem;
    margin-top: 0.4rem;
}
.badge {
    display: inline-block;
    padding: 0.2rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-right: 0.4rem;
    margin-top: 0.6rem;
}
.badge-blue   { background: rgba(96,165,250,0.15); color: #60a5fa; border: 1px solid rgba(96,165,250,0.3); }
.badge-purple { background: rgba(167,139,250,0.15); color: #a78bfa; border: 1px solid rgba(167,139,250,0.3); }
.badge-pink   { background: rgba(244,114,182,0.15); color: #f472b6; border: 1px solid rgba(244,114,182,0.3); }

/* Round cards */
.round-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
}
.round-number {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 0.9rem;
}
.round-pro  { background: rgba(34,197,94,0.2);  color: #22c55e; border: 2px solid #22c55e; }
.round-con  { background: rgba(239,68,68,0.2);  color: #ef4444; border: 2px solid #ef4444; }
.round-judge { background: rgba(250,204,21,0.2); color: #facc15; border: 2px solid #facc15; }

/* Brief boxes */
.brief-box {
    background: #1e293b;
    border-radius: 12px;
    padding: 1.5rem;
    border: 1px solid #334155;
    height: 100%;
    line-height: 1.7;
}
.brief-box-pro  { border-left: 4px solid #22c55e; }
.brief-box-con  { border-left: 4px solid #ef4444; }

/* Code diff */
.code-panel {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1.2rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    line-height: 1.6;
    overflow-x: auto;
}
.diff-add { color: #3fb950; }
.diff-del { color: #f85149; }
.diff-neu { color: #8b949e; }

/* Verdict section */
.verdict-box {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #facc15;
    border-radius: 14px;
    padding: 1.5rem 2rem;
    box-shadow: 0 0 24px rgba(250,204,21,0.08);
}

/* Bug reproduction */
.trap-box {
    background: #1a0a00;
    border: 1px solid #f97316;
    border-left: 4px solid #f97316;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
    color: #fed7aa;
    line-height: 1.8;
}

/* Buttons */
.stButton>button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.6rem 1.5rem;
    font-weight: 600;
    font-size: 0.9rem;
    transition: all 0.2s;
    width: 100%;
}
.stButton>button:hover {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    box-shadow: 0 4px 16px rgba(99,102,241,0.4);
    transform: translateY(-1px);
}

/* Selectbox / radio */
div[data-testid="stSelectbox"] label,
div[data-testid="stRadio"] label { color: #cbd5e1; font-weight: 500; }

/* Section divider */
.section-divider {
    border: none;
    border-top: 1px solid #1e293b;
    margin: 2rem 0;
}

/* Metric tiles */
.metric-tile {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    text-align: center;
}
.metric-val { font-size: 1.6rem; font-weight: 700; }
.metric-lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem; }

/* Spinner override */
.stSpinner > div { border-top-color: #6366f1 !important; }
</style>
""", unsafe_allow_html=True)


# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-banner">
  <p class="hero-title">⚖️ Pipeline Lawyer</p>
  <p class="hero-sub">Sigma DataTech AI Ops Platform &nbsp;|&nbsp; Day 9 &nbsp;|&nbsp; Team 3</p>
  <span class="badge badge-blue">Nova Pro — Prosecutor</span>
  <span class="badge badge-purple">Nova Lite — Defense</span>
  <span class="badge badge-pink">Human Judge</span>
</div>
""", unsafe_allow_html=True)

# ── Load pipeline code from DB ────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return duckdb.connect(DB_PATH, read_only=True)

conn = get_conn()

@st.cache_data
def load_pipeline_code():
    v1 = conn.execute("SELECT code FROM pipeline_versions WHERE version='v1'").fetchone()[0]
    v2 = conn.execute("SELECT code FROM pipeline_versions WHERE version='v2'").fetchone()[0]
    return v1.strip(), v2.strip()

v1_code, v2_code = load_pipeline_code()

# ── CASE INTRO ─────────────────────────────────────────────────────────────────
with st.expander("📋 Case Brief — Read Before Judging", expanded=False):
    st.markdown("""
    **Background:** A junior Data Engineer submitted PR #42 to fix the **Silver layer idempotency bug**.
    The original pipeline (`v1`) crashes with a `ConstraintException` when duplicate transaction IDs are loaded.
    The fix (`v2`) appears to solve this by tracking seen IDs.

    **Tech Lead's Concern:** *"The tests pass. The fix looks clean. But something feels wrong."*

    **Your job:** Read both AI arguments, then deliver your verdict.
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Pipeline v1 — Original (Buggy)**")
        st.code(v1_code, language="python")
    with col2:
        st.markdown("**Pipeline v2 — PR Fix**")
        st.code(v2_code, language="python")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# ROUND 1 — AI PROSECUTOR (PRO-MERGE) — Nova Pro
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="round-header">
  <div class="round-number round-pro">1</div>
  <div>
    <span style="font-size:1.15rem;font-weight:700;color:#22c55e;">Round 1 — AI Prosecutor</span>
    <span style="color:#64748b;font-size:0.85rem;margin-left:0.5rem;">(Nova Pro • PRO-MERGE)</span>
  </div>
</div>
""", unsafe_allow_html=True)

if "pro_brief" not in st.session_state:
    st.session_state.pro_brief = None

if st.button("🟢 Generate PRO-MERGE Argument", key="btn_pro"):
    with st.spinner("Nova Pro is reviewing the PR and building the prosecution brief..."):
        system_pro = textwrap.dedent("""
            You are a senior data engineering expert acting as legal counsel arguing FOR merging a Pull Request.
            Your job is to write a persuasive, professional legal brief that:
            1. Clearly identifies every bug or limitation in the original code (v1)
            2. Explains precisely how the new code (v2) fixes each issue
            3. Lists all engineering improvements and their business impact
            4. Concludes with a strong recommendation to MERGE
            Be specific, reference line-level code details, and write in a confident legal brief style.
            Format your response with clear sections: OPENING, THE CASE FOR v2, ENGINEERING IMPROVEMENTS, VERDICT.
        """)
        user_pro = textwrap.dedent(f"""
            Review the following two pipeline versions and argue FOR merging v2:

            === PIPELINE v1 (Current - Buggy) ===
            {v1_code}

            === PIPELINE v2 (PR Fix) ===
            {v2_code}

            Write a compelling legal brief arguing FOR merging this Pull Request.
        """)
        st.session_state.pro_brief = call_nova_pro(system_pro, user_pro, max_tokens=1500)

if st.session_state.pro_brief:
    st.markdown(f"""
    <div class="brief-box brief-box-pro">
    <strong style="color:#22c55e;">🟢 PROSECUTION BRIEF — Arguments FOR Merging PR #42</strong><br/><br/>
    {st.session_state.pro_brief.replace(chr(10), '<br/>')}
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROUND 2 — AI DEFENSE (AGAINST-MERGE) — Nova Lite
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="round-header">
  <div class="round-number round-con">2</div>
  <div>
    <span style="font-size:1.15rem;font-weight:700;color:#ef4444;">Round 2 — AI Defense</span>
    <span style="color:#64748b;font-size:0.85rem;margin-left:0.5rem;">(Nova Lite • AGAINST-MERGE)</span>
  </div>
</div>
""", unsafe_allow_html=True)

if "con_brief" not in st.session_state:
    st.session_state.con_brief = None

if st.button("🔴 Generate AGAINST-MERGE Argument", key="btn_con"):
    with st.spinner("Nova Lite is scanning for risks and building the defense brief..."):
        system_con = textwrap.dedent("""
            You are a skeptical senior data engineering expert acting as defense counsel arguing AGAINST merging a Pull Request.
            Your job is to write a rigorous legal brief that:
            1. Identifies all hidden risks, edge cases, and failure modes in the new code (v2)
            2. Explains scenarios where v2 silently fails or produces incorrect results
            3. Highlights what happens when the function is called more than once in the same session
            4. Points out the module-level global state problem if you see it
            5. Concludes with a strong recommendation to REJECT or REQUEST CHANGES
            Be specific, reference actual code lines, and write in a formal legal brief style.
            Format: OPENING, RISKS & EDGE CASES, SILENT FAILURE ANALYSIS, VERDICT.
        """)
        user_con = textwrap.dedent(f"""
            Review the following two pipeline versions and argue AGAINST merging v2:

            === PIPELINE v1 (Current) ===
            {v1_code}

            === PIPELINE v2 (PR Fix - Under Review) ===
            {v2_code}

            Write a compelling legal brief arguing AGAINST merging this Pull Request.
            Pay special attention to what happens if load_silver() is called more than once.
        """)
        st.session_state.con_brief = call_nova_lite(system_con, user_con, max_tokens=1000)

if st.session_state.con_brief:
    st.markdown(f"""
    <div class="brief-box brief-box-con">
    <strong style="color:#ef4444;">🔴 DEFENSE BRIEF — Arguments AGAINST Merging PR #42</strong><br/><br/>
    {st.session_state.con_brief.replace(chr(10), '<br/>')}
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDE-BY-SIDE VIEW (if both briefs are ready)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pro_brief and st.session_state.con_brief:
    st.markdown("### 📄 Side-by-Side View — Both Legal Briefs")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(f"""
        <div class="brief-box brief-box-pro" style="min-height:300px;">
        <strong style="color:#22c55e;">🟢 PROSECUTION (Nova Pro)</strong><br/><br/>
        {st.session_state.pro_brief.replace(chr(10), '<br/>')}
        </div>
        """, unsafe_allow_html=True)
    with col_r:
        st.markdown(f"""
        <div class="brief-box brief-box-con" style="min-height:300px;">
        <strong style="color:#ef4444;">🔴 DEFENSE (Nova Lite)</strong><br/><br/>
        {st.session_state.con_brief.replace(chr(10), '<br/>')}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROUND 3 — THE TRAP + YOUR VERDICT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="round-header">
  <div class="round-number round-judge">3</div>
  <div>
    <span style="font-size:1.15rem;font-weight:700;color:#facc15;">Round 3 — Your Verdict</span>
    <span style="color:#64748b;font-size:0.85rem;margin-left:0.5rem;">(You are the Judge)</span>
  </div>
</div>
""", unsafe_allow_html=True)

# The Trap Explainer
st.markdown("#### 🪤 The Hidden Trap — Reproduce in 5 Lines")
st.markdown("""
<div class="trap-box">
<span style="color:#f97316;font-weight:600;"># The bug in v2 — module-level global is NEVER reset between runs</span><br/>
<br/>
seen_ids = set()  <span style="color:#64748b;"># ← lives at module level, persists across calls</span><br/>
<br/>
load_silver(batch_1)  <span style="color:#64748b;"># ✅ Run 1: 14 rows written to Silver</span><br/>
load_silver(batch_1)  <span style="color:#64748b;"># ❌ Run 2: 0 rows written! seen_ids still full</span><br/>
load_silver(batch_2)  <span style="color:#64748b;"># ❌ Run 3: 0 rows written! all IDs already "seen"</span><br/>
<br/>
<span style="color:#f97316;font-weight:600;"># Silent failure — no error raised, pipeline reports "success"</span><br/>
<span style="color:#fbbf24;">print(silver_count)   # → 14  (expected: 42, if called 3 times with 14 rows each)</span>
</div>
""", unsafe_allow_html=True)

st.markdown("<br/>", unsafe_allow_html=True)

# DuckDB Proof
with st.expander("🔍 DuckDB Query — Prove The Bug", expanded=False):
    st.markdown("Run this to see the current Silver row count. On second pipeline run, it stays at 14:")
    st.code("""
-- Check Silver row count (should grow after each pipeline run)
SELECT COUNT(*) AS silver_rows FROM silver_transactions;

-- After 2nd run with v2, count stays the same — proof of silent failure
SELECT version, length(code) AS code_length FROM pipeline_versions;
    """, language="sql")

    if st.button("▶ Run DuckDB Query", key="btn_duckdb"):
        result = conn.execute("SELECT COUNT(*) AS silver_rows FROM pipeline_versions").fetchdf()
        silver_count = conn.execute("SELECT COUNT(*) AS cnt FROM silver_transactions").fetchone()[0]
        st.metric("Silver Rows", silver_count, help="This stays at 14 even after a 2nd pipeline run with v2")

st.markdown("<br/>", unsafe_allow_html=True)

# The Correct Fix
with st.expander("✅ The Correct Fix", expanded=False):
    st.markdown("**Option A — Move `seen_ids` inside the function (simplest fix):**")
    st.code("""
def load_silver(rows):
    seen_ids = set()   # ✅ reset on every call — local scope, not global
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        if row["transaction_id"] in seen_ids:
            continue
        seen_ids.add(row["transaction_id"])
        con.execute(
            "INSERT OR IGNORE INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )
    """, language="python")

    st.markdown("**Option B — Use database-level deduplication (production-grade):**")
    st.code("""
-- Use INSERT OR IGNORE (SQLite) or INSERT ... ON CONFLICT DO NOTHING (DuckDB)
con.execute(
    "INSERT OR IGNORE INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
    [row["transaction_id"], ...]
)
# No in-memory tracking needed — DB enforces the PRIMARY KEY constraint
    """, language="python")

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── Verdict Form ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="verdict-box">
<strong style="color:#facc15;font-size:1.1rem;">⚖️ Your Verdict — PR #42</strong>
</div>
""", unsafe_allow_html=True)
st.markdown("<br/>", unsafe_allow_html=True)

col_v1, col_v2 = st.columns([1, 2])
with col_v1:
    verdict_choice = st.radio(
        "Decision",
        ["✅ APPROVE", "❌ REJECT", "🔄 REQUEST CHANGES"],
        index=1,
        key="verdict_radio"
    )

with col_v2:
    verdict_reason = st.text_area(
        "One sentence — what exactly needs to change?",
        placeholder="e.g. The seen_ids global variable must be moved inside load_silver() to prevent silent data loss on repeated pipeline runs.",
        height=100,
        key="verdict_text"
    )

col_s1, col_s2, col_s3 = st.columns([1, 1, 2])
with col_s1:
    if st.button("💾 Save Verdict to verdict.json", key="btn_save"):
        if not verdict_reason.strip():
            st.error("Please write your one-sentence justification before saving.")
        else:
            verdict_data = {
                "team": "Team 3 — Pipeline Lawyer",
                "pr": "PR #42 — Silver Load Idempotency Fix",
                "verdict": verdict_choice.replace("✅ ", "").replace("❌ ", "").replace("🔄 ", ""),
                "reason": verdict_reason.strip(),
                "bug_found": True,
                "bug_description": "seen_ids is a module-level global — on second call to load_silver() in same session, all IDs are already in seen_ids, so 0 rows are written. Silent failure — no exception raised.",
                "correct_fix": "Move seen_ids = set() inside the load_silver() function body so it resets on every call. Better: use INSERT OR IGNORE / INSERT ... ON CONFLICT DO NOTHING at DB level.",
                "what_ai_got_wrong": "Nova Pro (PRO-merge) focused on the fix for the original bug and may have missed the global state issue. Nova Lite was prompted to specifically look for repeated-call failures.",
                "models_used": {
                    "round_1": "amazon.nova-pro-v1:0",
                    "round_2": "amazon.nova-lite-v1:0"
                }
            }
            with open(VERDICT_PATH, "w") as f:
                json.dump(verdict_data, f, indent=2)
            st.success(f"✅ Verdict saved to verdict.json")
            st.json(verdict_data)

with col_s2:
    # Load existing verdict if it exists
    if os.path.exists(VERDICT_PATH):
        if st.button("📂 Load Saved Verdict", key="btn_load"):
            with open(VERDICT_PATH) as f:
                saved = json.load(f)
            st.json(saved)

st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)

# ── What AI Got Wrong ─────────────────────────────────────────────────────────
st.markdown("### 🤖 What AI Got Wrong")
col_w1, col_w2 = st.columns(2)
with col_w1:
    st.markdown("""
    <div class="metric-tile" style="border-left:4px solid #22c55e;">
    <div class="metric-val" style="color:#22c55e;">Nova Pro</div>
    <div class="metric-lbl">Round 1 • Prosecutor</div>
    <br/>
    <div style="color:#94a3b8;font-size:0.85rem;text-align:left;">
    ⚠️ Likely argued that v2 is a clean, correct fix.<br/>
    It correctly identified the crash in v1 (duplicate PK violation).<br/>
    But it may have <strong style="color:#fbbf24;">missed the global state bug</strong> in v2
    — especially if it only reviewed the code statically without simulating a second call.
    </div>
    </div>
    """, unsafe_allow_html=True)
with col_w2:
    st.markdown("""
    <div class="metric-tile" style="border-left:4px solid #ef4444;">
    <div class="metric-val" style="color:#ef4444;">Nova Lite</div>
    <div class="metric-lbl">Round 2 • Defense</div>
    <br/>
    <div style="color:#94a3b8;font-size:0.85rem;text-align:left;">
    ✅ Was specifically prompted to look for repeated-call failures.<br/>
    More likely to catch the <code>seen_ids</code> global variable problem.<br/>
    But may have been <strong style="color:#fbbf24;">less nuanced</strong> — potentially flagging
    non-issues or missing the exact silent-failure mechanism.
    </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br/><br/>", unsafe_allow_html=True)
st.caption("Sigma DataTech AI Ops Platform · Day 9 · Team 3 — Pipeline Lawyer · Built with AWS Bedrock + DuckDB + Streamlit")
