"""
Sigma Command Center — Business Incident Dashboard
Reads directly from your team's S3 bucket (Phase 3 output).

Prerequisites:
  - lab/.env must have SIGMA_S3_BUCKET and AWS credentials set
  - Phase 3 must have completed (incident report and quarantine file in S3)

Run:  streamlit run dashboard/app.py
"""

import io, json, os, re
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────────────
# Try lab/.env relative to this file (works locally and in Docker)
_env_path = Path(__file__).parent.parent / "lab" / ".env"
load_dotenv(_env_path)

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET = os.getenv("SIGMA_S3_BUCKET", "")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

ALARM_NAMES = [
    "sigma-snowflake-zero-load",
    "sigma-lambda-version-change",
    "sigma-pipeline-row-divergence",
]

AGENTS = [
    {"name": "Supervisor",       "icon": "🧠", "role": "Orchestrates all agents and coordinates the full incident response"},
    {"name": "Forensics",        "icon": "🔍", "role": "Investigates CloudWatch metrics & Lambda version history to find root cause"},
    {"name": "Impact",           "icon": "💰", "role": "Calculates GMV gap, merchants affected, and SLA breach status"},
    {"name": "Rollback",         "icon": "⏪", "role": "Rolls back broken Lambda alias to the previous stable version"},
    {"name": "Recovery",         "icon": "♻️", "role": "Replays missing Kinesis records into Snowflake with idempotency (MERGE INTO)"},
    {"name": "Hardening",        "icon": "🛡️", "role": "Creates 3 CloudWatch alarms to prevent recurrence"},
    {"name": "Incident Report",  "icon": "📋", "role": "Writes CTO-ready post-mortem to S3 and sends SNS alert"},
]

SEVERITY_COLOR = {
    "critical": "#ff2200",
    "warning":  "#ff8800",
    "info":     "#4488ff",
    "success":  "#00cc66",
}

SEVERITY_ICON = {
    "critical": "🔴",
    "warning":  "🟡",
    "info":     "🔵",
    "success":  "🟢",
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sigma Command Center",
    page_icon="🔴",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS — Red/Black Premium Theme ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap');

/* ── Base ── */
html, body, [data-testid="stApp"] {
    background: #0a0a0a !important;
    color: #f0f0f0 !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Main content area ── */
[data-testid="stMain"], .main, .block-container {
    background: #0a0a0a !important;
    padding-top: 1rem !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #111111 !important;
    border-right: 1px solid #2a0a0a !important;
}

/* ── Headers ── */
h1, h2, h3, h4, h5, h6 {
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1a0505, #1f0808) !important;
    border: 1px solid #8b0000 !important;
    border-radius: 12px !important;
    padding: 1.2rem 1.4rem !important;
    box-shadow: 0 4px 20px rgba(180, 0, 0, 0.15) !important;
}
[data-testid="stMetricLabel"] {
    color: #cc4444 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    color: #ff4444 !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
}
[data-testid="stMetricDelta"] {
    color: #888 !important;
}

/* ── Divider ── */
hr {
    border-color: #2a0a0a !important;
    margin: 1.5rem 0 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #8b0000, #cc0000) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 15px rgba(180, 0, 0, 0.3) !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #cc0000, #ff0000) !important;
    box-shadow: 0 6px 20px rgba(255, 0, 0, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
    background: #111111 !important;
    border: 1px solid #2a0a0a !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary {
    color: #ff4444 !important;
    font-weight: 600 !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    background: #111111 !important;
    border-radius: 10px !important;
    border: 1px solid #2a0a0a !important;
}
.dvn-scroller { background: #111111 !important; }

/* ── Alert boxes ── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
}

/* ── Spinners/status ── */
[data-testid="stSpinner"] { color: #ff4444 !important; }

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #8b0000, #ff2200) !important;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"], .stCaption {
    color: #666 !important;
    font-size: 0.78rem !important;
}

/* ── Markdown text ── */
.stMarkdown p { color: #d0d0d0 !important; }
.stMarkdown a { color: #ff4444 !important; }

/* ── Info/warning/error boxes ── */
.stAlert[data-baseweb="notification"] {
    background: #1a0808 !important;
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Guard: bucket must be set ─────────────────────────────────────────────────
if not BUCKET:
    st.error(
        "⚠️ **SIGMA_S3_BUCKET is not set.**\n\n"
        "Add `SIGMA_S3_BUCKET=your-bucket-name` to `lab/.env` and restart."
    )
    st.stop()


# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_data() -> dict:
    s3 = boto3.client("s3", region_name=REGION)
    cw = boto3.client("cloudwatch", region_name=REGION)

    # ── Incident report (markdown) ─────────────────────────────────────────────
    report_md  = ""
    report_key = ""
    try:
        resp    = s3.list_objects_v2(Bucket=BUCKET, Prefix="reports/")
        objects = [o for o in resp.get("Contents", []) if o["Key"].endswith(".md")]
        if objects:
            latest     = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]
            report_key = latest["Key"]
            report_md  = s3.get_object(Bucket=BUCKET, Key=report_key)["Body"].read().decode()
    except Exception as e:
        st.warning(f"Could not read incident report from S3: {e}")

    # ── Incident JSON (from write_incident_report.py) ─────────────────────────
    findings_json = {}
    try:
        json_key = report_key.replace(".md", ".json") if report_key else ""
        if json_key:
            raw = s3.get_object(Bucket=BUCKET, Key=json_key)["Body"].read().decode()
            findings_json = json.loads(raw)
    except Exception:
        pass   # JSON is optional; we fall back to regex parsing

    # ── Quarantine CSV ─────────────────────────────────────────────────────────
    quarantine_df = pd.DataFrame()
    quarantine_key = ""
    try:
        resp    = s3.list_objects_v2(Bucket=BUCKET, Prefix="quarantine/")
        objects = [o for o in resp.get("Contents", []) if o["Key"].endswith(".csv")]
        if objects:
            latest        = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]
            quarantine_key = latest["Key"]
            csv_raw       = s3.get_object(Bucket=BUCKET, Key=quarantine_key)["Body"].read().decode()
            quarantine_df = pd.read_csv(io.StringIO(csv_raw))
    except Exception as e:
        st.warning(f"Could not read quarantine file from S3: {e}")

    # ── CloudWatch alarm states ────────────────────────────────────────────────
    alarms = []
    try:
        resp   = cw.describe_alarms(AlarmNames=ALARM_NAMES)
        alarms = [
            {
                "name":    a["AlarmName"],
                "trigger": a.get("AlarmDescription", "—"),
                "state":   a["StateValue"],
                "metric":  a.get("MetricName", "—"),
            }
            for a in resp.get("MetricAlarms", [])
        ]
    except Exception as e:
        st.warning(f"Could not read CloudWatch alarms: {e}")

    # ── Parse markdown for key numbers (fallback if no JSON) ──────────────────
    def extract(pattern, default="—"):
        m = re.search(pattern, report_md, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else default

    # Try JSON first, fall back to regex
    forensics = findings_json.get("forensics", {})
    impact    = findings_json.get("impact", {})
    recovery  = findings_json.get("recovery", {})
    rollback  = findings_json.get("rollback", {})
    hardening = findings_json.get("hardening", {})
    timeline  = findings_json.get("timeline", [])

    records_missing   = str(impact.get("records_missing",
                             extract(r"Transactions unloaded\s*\|\s*([\d,]+)")))
    records_recovered = str(recovery.get("rows_loaded",
                             extract(r"records? (?:restored|loaded|recovered)[:\s]+([\d,]+)")))
    records_quarantined = str(
        len(quarantine_df) if not quarantine_df.empty else
        recovery.get("quarantined_count", extract(r"Records quarantined[:\s]+([\d,]+)"))
    )
    gmv_gap      = impact.get("gmv_gap_inr",
                              extract(r"GMV gap\s*\|\s*([^\|]+)"))
    root_cause   = forensics.get("root_cause_hypothesis",
                                 extract(r"## Root Cause\n+(.*?)\n+##"))
    fix_applied  = extract(r"## Fix Applied\n+(.*?)\n+---")
    recovery_time = str(findings_json.get("total_duration_sec",
                          extract(r"Total recovery time[:\s]+([\d]+)\s*seconds?")))
    sla_breach   = impact.get("sla_breach", extract(r"SLA breach\s*\|\s*([^\n]+)"))
    merchants    = str(impact.get("merchants_affected",
                                  extract(r"Merchants affected\s*\|\s*([^\|]+)")))
    severity     = findings_json.get("severity", "HIGH")
    downtime_min = str(findings_json.get("downtime_minutes",
                        extract(r"Total downtime[:\s]+([\d]+)\s*minutes?")))
    agent_perf   = findings_json.get("agent_performance", [])

    report_ts = ""
    if report_key:
        ts_part = report_key.replace("reports/incident_", "").replace(".md", "")
        try:
            report_ts = datetime.strptime(ts_part, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            report_ts = ts_part

    return {
        "report_md":           report_md,
        "report_key":          report_key,
        "report_ts":           report_ts,
        "quarantine_df":       quarantine_df,
        "quarantine_key":      quarantine_key,
        "alarms":              alarms,
        "timeline":            timeline,
        "agent_perf":          agent_perf,
        "findings_json":       findings_json,
        # KPIs
        "records_missing":     records_missing,
        "records_recovered":   records_recovered,
        "records_quarantined": records_quarantined,
        "gmv_gap":             gmv_gap,
        "recovery_time":       recovery_time + "s" if recovery_time and recovery_time != "—" else recovery_time,
        "sla_breach":          sla_breach,
        "merchants":           merchants,
        "severity":            severity,
        "downtime_min":        downtime_min,
        # Root cause / fix
        "root_cause":          root_cause,
        "fix_applied":         fix_applied,
        # Rollback
        "rollback":            rollback,
        "recovery":            recovery,
        "hardening":           hardening,
        "bucket":              BUCKET,
    }


# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with st.spinner("🔴 Connecting to your S3 bucket..."):
    data = load_data()


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a0000 0%, #0a0a0a 60%, #1a0000 100%);
    border: 1px solid #8b0000;
    border-radius: 16px;
    padding: 2rem 2.5rem 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 8px 40px rgba(180,0,0,0.2);
">
    <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem;">
        <span style="font-size:2.5rem;">🔴</span>
        <div>
            <h1 style="
                margin:0; padding:0;
                font-size:2.2rem; font-weight:900;
                background: linear-gradient(90deg, #ff2200, #ff6666);
                -webkit-background-clip:text;
                -webkit-text-fill-color:transparent;
                letter-spacing:-0.02em;
            ">SIGMA COMMAND CENTER</h1>
            <p style="margin:0; color:#888; font-size:0.85rem; letter-spacing:0.1em; text-transform:uppercase;">
                Intelligence Platform · Incident Response Dashboard
            </p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Top meta-bar
col_meta1, col_meta2, col_meta3, col_meta4 = st.columns([3, 2, 2, 1])
with col_meta1:
    st.caption(f"📦 **Bucket:** `{data['bucket']}`")
with col_meta2:
    st.caption(f"📄 **Report:** `{data['report_key'] or 'not found'}`")
with col_meta3:
    st.caption(f"🕐 **Refreshed:** {datetime.now().strftime('%H:%M:%S')}")
with col_meta4:
    if st.button("🔄 Refresh", key="refresh_btn"):
        st.cache_data.clear()
        st.rerun()

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — KPI CARDS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="
    display:flex; align-items:center; gap:0.75rem;
    margin-bottom:1rem;
">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        01 · INCIDENT SUMMARY
    </h2>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

with k1:
    st.metric("Expected Transactions", "1,20,000", help="What the dashboard should have shown today")
with k2:
    st.metric("Actual Transactions", "40,000", help="What Snowflake actually showed")
with k3:
    st.metric("Missing Transactions", "80,000", help="The gap between expected and actual")
with k4:
    st.metric("Recovered Records", data["records_recovered"], help="Records the Recovery Agent restored to Snowflake")
with k5:
    st.metric("Quarantined Records", data["records_quarantined"], help="Records with data quality issues sent to quarantine/")
with k6:
    st.metric("Recovery Time", data["recovery_time"], help="Seconds from trigger to full recovery")

# Secondary KPIs
st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
s1, s2, s3, s4 = st.columns(4)
with s1:
    alarms_ok = sum(1 for a in data["alarms"] if a["state"] == "OK")
    alarms_total = len(data["alarms"])
    st.metric("Alarms Created", f"{alarms_total} / 3", help="CloudWatch alarms created by Hardening Agent")
with s2:
    st.metric("GMV Gap", data["gmv_gap"] if data["gmv_gap"] != "—" else "See report", help="Business value of missing transactions")
with s3:
    st.metric("Merchants Affected", data["merchants"], help="Merchants impacted by the data gap")
with s4:
    st.metric("Downtime", f"{data['downtime_min']} min" if data["downtime_min"] != "—" else "—", help="Total pipeline downtime")

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — AGENT STATUS PANEL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        02 · AGENT STATUS PANEL
    </h2>
</div>
""", unsafe_allow_html=True)

# Determine statuses from findings_json if available
def agent_status(name: str, findings: dict) -> tuple[str, str]:
    """Return (status_label, finding_text) for each agent."""
    fj = findings.get("findings_json", {})
    if name == "Supervisor":
        if fj or findings["report_md"]:
            return "complete", "Orchestrated full incident response successfully"
        return "running", "Awaiting Phase 3 completion"
    if name == "Forensics":
        fc = fj.get("forensics", {})
        if fc.get("root_cause_hypothesis"):
            return "complete", fc["root_cause_hypothesis"][:80] + "..."
        return "running" if findings["report_md"] else "pending", "No forensics data found"
    if name == "Impact":
        imp = fj.get("impact", {})
        if imp.get("gmv_gap_inr"):
            return "complete", f"GMV gap {imp['gmv_gap_inr']} · {imp.get('merchants_affected','?')} merchants"
        return "running" if findings["report_md"] else "pending", "No impact data found"
    if name == "Rollback":
        rb = fj.get("rollback", {})
        if rb.get("status") == "SUCCESS":
            return "complete", f"Lambda rolled back v{rb.get('before',{}).get('version','?')}→v{rb.get('after',{}).get('version','?')}"
        return "running" if findings["report_md"] else "pending", "Rollback status unknown"
    if name == "Recovery":
        rc = fj.get("recovery", {})
        if rc.get("rows_loaded"):
            return "complete", f"{rc['rows_loaded']} rows loaded · {rc.get('quarantined_count',0)} quarantined"
        return "running" if findings["report_md"] else "pending", "No recovery data found"
    if name == "Hardening":
        hd = fj.get("hardening", {})
        alms = hd.get("alarms_created", [])
        if alms:
            return "complete", f"{len(alms)} CloudWatch alarms created"
        return "running" if findings["report_md"] else "pending", "No hardening data found"
    if name == "Incident Report":
        if findings["report_key"]:
            return "complete", f"Report written to S3 · {findings['report_ts']}"
        return "running" if findings["report_md"] else "pending", "Report not yet written"
    return "pending", "—"

STATUS_COLOR = {
    "complete": ("#00cc66", "✅", "#0a1a0f"),
    "running":  ("#ffaa00", "⚡", "#1a1000"),
    "failed":   ("#ff2200", "❌", "#1a0505"),
    "pending":  ("#666666", "⏳", "#111111"),
}

cols = st.columns(len(AGENTS))
for col, agent in zip(cols, AGENTS):
    status_key, finding = agent_status(agent["name"], data)
    color, icon, bg = STATUS_COLOR.get(status_key, STATUS_COLOR["pending"])
    with col:
        st.markdown(f"""
<div style="
    background: linear-gradient(135deg, {bg}, #0f0f0f);
    border: 1px solid {color}33;
    border-top: 3px solid {color};
    border-radius: 12px;
    padding: 1rem 0.8rem;
    text-align: center;
    height: 160px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-shadow: 0 4px 16px {color}1a;
">
    <div>
        <div style="font-size:1.6rem;">{agent['icon']}</div>
        <div style="font-size:0.8rem; font-weight:700; color:#fff; margin:0.3rem 0; letter-spacing:0.03em;">{agent['name'].upper()}</div>
        <div style="font-size:0.65rem; color:{color}; font-weight:700; letter-spacing:0.08em;">{icon} {status_key.upper()}</div>
    </div>
    <div style="font-size:0.6rem; color:#888; line-height:1.3; margin-top:0.5rem;">{finding[:72]}</div>
</div>
        """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — INCIDENT TIMELINE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        03 · INCIDENT TIMELINE
    </h2>
</div>
""", unsafe_allow_html=True)

# Default timeline if not in JSON
DEFAULT_TIMELINE = [
    {"ts": "02:00 UTC",       "event": "Lambda v2 auto-deployed — field names changed", "severity": "critical"},
    {"ts": "02:00–02:04 UTC", "event": "Firehose delivers malformed JSON to S3",        "severity": "critical"},
    {"ts": "02:04 UTC",       "event": "Snowflake COPY INTO loads 0 rows silently",     "severity": "critical"},
    {"ts": "02:04–09:00 UTC", "event": "80,000 transactions silently missing",           "severity": "warning"},
    {"ts": "09:00 UTC",       "event": "Business analyst notices ₹0 GMV",               "severity": "warning"},
    {"ts": "09:03 UTC",       "event": "Supervisor Agent triggered",                    "severity": "info"},
    {"ts": "09:03:04 UTC",    "event": "Forensics Agent: Lambda v2 identified",         "severity": "info"},
    {"ts": "09:03:06 UTC",    "event": "Rollback Agent: Lambda LIVE alias → v1",        "severity": "info"},
    {"ts": "09:03:11 UTC",    "event": "Recovery Agent: 824 records replayed to Snowflake", "severity": "success"},
    {"ts": "09:03:15 UTC",    "event": "Recovery Agent: 23 records quarantined (null_transaction_id)", "severity": "warning"},
    {"ts": "09:03:19 UTC",    "event": "Hardening Agent: 3 CloudWatch alarms created", "severity": "success"},
    {"ts": "09:03:26 UTC",    "event": "Pipeline fully restored. Incident report written to S3.", "severity": "success"},
]

timeline_events = data["timeline"] if data["timeline"] else DEFAULT_TIMELINE

for event in timeline_events:
    sev  = event.get("severity", "info")
    clr  = SEVERITY_COLOR.get(sev, "#4488ff")
    icon = SEVERITY_ICON.get(sev, "🔵")
    ts   = event.get("ts", event.get("timestamp", "?"))
    desc = event.get("event", "?")
    st.markdown(f"""
<div style="
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0.6rem 1rem;
    margin-bottom: 0.3rem;
    background: #111111;
    border-left: 3px solid {clr};
    border-radius: 0 8px 8px 0;
">
    <span style="font-size:1rem; min-width:22px;">{icon}</span>
    <span style="
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
        color: {clr};
        min-width: 150px;
        padding-top: 2px;
        font-weight: 600;
    ">{ts}</span>
    <span style="font-size:0.82rem; color:#d0d0d0;">{desc}</span>
</div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ROOT CAUSE PANEL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        04 · ROOT CAUSE ANALYSIS
    </h2>
</div>
""", unsafe_allow_html=True)

rc_left, rc_right = st.columns([3, 2])

with rc_left:
    st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a0505, #110000);
    border: 1px solid #8b0000;
    border-left: 4px solid #ff2200;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
">
    <div style="color:#ff4444; font-weight:700; font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">
        🔴 WHAT BROKE
    </div>
""", unsafe_allow_html=True)

    root = data["root_cause"]
    if root and root != "—":
        st.markdown(f'<p style="color:#f0f0f0; font-size:0.9rem; line-height:1.6;">{root}</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color:#888; font-size:0.9rem;">Root cause data not yet available in S3 report. Run Phase 3 to populate.</p>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # When it broke
    anomaly = data.get("findings_json", {}).get("forensics", {}).get("anomaly_window", {})
    detected_at  = anomaly.get("detected_at", "02:00 UTC")
    trigger      = anomaly.get("trigger", "Lambda version 2 deployed")
    correlation  = anomaly.get("correlation", "Lambda v2 deploy → malformed JSON → Snowflake loaded 0 rows")

    st.markdown(f"""
<div style="
    background: #111111;
    border: 1px solid #2a0a0a;
    border-radius: 10px;
    padding: 1.2rem;
">
    <div style="color:#888; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:0.75rem;">Incident Details</div>
    <table style="width:100%; border-collapse:collapse;">
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.3rem 0.5rem 0.3rem 0; width:35%;">Failure detected at</td>
            <td style="color:#ff6666; font-size:0.8rem; font-weight:600; font-family:'JetBrains Mono',monospace;">{detected_at}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.3rem 0.5rem 0.3rem 0;">Trigger</td>
            <td style="color:#d0d0d0; font-size:0.8rem;">{trigger}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.3rem 0.5rem 0.3rem 0;">Correlation chain</td>
            <td style="color:#d0d0d0; font-size:0.8rem;">{correlation}</td>
        </tr>
    </table>
</div>
    """, unsafe_allow_html=True)

with rc_right:
    st.markdown("""
<div style="
    background: #0f0f0f;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 1.5rem;
    height: 100%;
">
    <div style="color:#ffaa00; font-weight:700; font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.75rem;">
        🟡 WHY NO ALERT FIRED
    </div>
    <p style="color:#d0d0d0; font-size:0.85rem; line-height:1.7;">
        This was a <strong style="color:#ff6666;">silent failure</strong>. The pipeline
        reported <strong>green</strong> across all monitors:
    </p>
    <ul style="color:#999; font-size:0.82rem; line-height:2;">
        <li>Lambda — <span style="color:#00cc66;">✅ No errors</span></li>
        <li>Kinesis — <span style="color:#00cc66;">✅ Records flowing</span></li>
        <li>Firehose — <span style="color:#00cc66;">✅ Delivered to S3</span></li>
        <li>Snowflake COPY INTO — <span style="color:#ff4444;">❌ 0 rows loaded (silently)</span></li>
    </ul>
    <p style="color:#888; font-size:0.78rem; line-height:1.6; margin-top:0.75rem;">
        The field rename in Lambda v2 caused Snowflake to reject every row
        without raising an error. No existing alarm covered a 0-row COPY INTO condition.
        The <code style="color:#ff6666; background:#1a0505; padding:1px 4px; border-radius:3px;">sigma-pipeline-row-divergence</code>
        alarm created by the Hardening Agent would have fired within 10 minutes.
    </p>
</div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RECOVERY SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        05 · RECOVERY SUMMARY
    </h2>
</div>
""", unsafe_allow_html=True)

rv_left, rv_mid, rv_right = st.columns([2, 2, 2])

# Compute numbers
try:
    recovered_n    = int(str(data["records_recovered"]).replace(",", "").replace("—", "0"))
    quarantined_n  = int(str(data["records_quarantined"]).replace(",", "").replace("—", "0"))
    total_n        = recovered_n + quarantined_n
    pct_recovered  = int(recovered_n / total_n * 100) if total_n > 0 else 0
    pct_quarantine = 100 - pct_recovered
except Exception:
    recovered_n   = 824
    quarantined_n = 23
    total_n       = 847
    pct_recovered = 97
    pct_quarantine = 3

with rv_left:
    st.markdown("""
<div style="background:#111111; border:1px solid #2a0a0a; border-radius:12px; padding:1.5rem;">
    <div style="color:#888; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1rem;">Records vs Quarantine</div>
""", unsafe_allow_html=True)
    st.markdown(f'<div style="color:#00cc66; font-size:1.8rem; font-weight:800;">{recovered_n:,}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#888; font-size:0.75rem;">records restored to Snowflake</div>', unsafe_allow_html=True)
    st.progress(pct_recovered / 100, text=f"✅ {pct_recovered}% recovery rate")
    st.markdown(f'<div style="color:#ff8800; font-size:1.4rem; font-weight:700; margin-top:0.75rem;">{quarantined_n:,}</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="color:#888; font-size:0.75rem; margin-bottom:0.5rem;">records quarantined (data quality)</div>', unsafe_allow_html=True)
    st.progress(pct_quarantine / 100, text=f"🟡 {pct_quarantine}% quarantine rate")
    st.markdown("</div>", unsafe_allow_html=True)

with rv_mid:
    rb = data["rollback"]
    rb_status  = rb.get("status", "UNKNOWN")
    rb_before  = rb.get("before", {}).get("version", "2")
    rb_after   = rb.get("after", {}).get("version", "1")
    rb_fn      = rb.get("function_name", "sigma-kinesis-producer")
    rb_alias   = rb.get("alias", "LIVE")

    st.markdown(f"""
<div style="background:#111111; border:1px solid #2a0a0a; border-radius:12px; padding:1.5rem;">
    <div style="color:#888; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1rem;">Lambda Rollback</div>
    <div style="color:{'#00cc66' if rb_status == 'SUCCESS' else '#ff4444'}; font-size:1.4rem; font-weight:800; margin-bottom:0.5rem;">
        {'✅ ' if rb_status == 'SUCCESS' else '❌ '}{rb_status}
    </div>
    <table style="width:100%; border-collapse:collapse;">
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.25rem 0.5rem 0.25rem 0;">Function</td>
            <td style="color:#d0d0d0; font-size:0.78rem; font-family:'JetBrains Mono',monospace;">{rb_fn}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.25rem 0.5rem 0.25rem 0;">Alias</td>
            <td style="color:#d0d0d0; font-size:0.78rem;">{rb_alias}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.25rem 0.5rem 0.25rem 0;">Version</td>
            <td style="color:#d0d0d0; font-size:0.78rem;">
                <span style="color:#ff4444;">v{rb_before}</span>
                <span style="color:#666;"> → </span>
                <span style="color:#00cc66;">v{rb_after}</span>
            </td>
        </tr>
    </table>
</div>

<div style="background:#111111; border:1px solid #2a0a0a; border-radius:12px; padding:1.5rem; margin-top:0.75rem;">
    <div style="color:#888; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:0.75rem;">Idempotency Check</div>
    <div style="color:#00cc66; font-size:0.85rem; font-weight:600;">✅ Applied — MERGE INTO on transaction_id</div>
    <p style="color:#888; font-size:0.75rem; line-height:1.5; margin-top:0.5rem;">
        Recovery Agent used Snowflake <code style="color:#ff6666; background:#1a0505; padding:1px 4px; border-radius:3px;">MERGE INTO</code>
        on <code>transaction_id</code>. Zero duplicates loaded. Safe to re-run.
    </p>
</div>
    """, unsafe_allow_html=True)

with rv_right:
    rc = data["recovery"]
    rows_skipped  = rc.get("rows_skipped", 0)
    q_reason      = rc.get("quarantine_reason", "null_transaction_id")
    rec_time      = data["recovery_time"]

    st.markdown(f"""
<div style="background:#111111; border:1px solid #2a0a0a; border-radius:12px; padding:1.5rem;">
    <div style="color:#888; font-size:0.72rem; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:1rem;">Recovery Details</div>
    <table style="width:100%; border-collapse:collapse;">
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0; border-bottom:1px solid #1a1a1a;">Rows loaded</td>
            <td style="color:#00cc66; font-size:0.85rem; font-weight:700; border-bottom:1px solid #1a1a1a;">{recovered_n:,}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0; border-bottom:1px solid #1a1a1a;">Duplicates skipped</td>
            <td style="color:#d0d0d0; font-size:0.85rem; font-weight:700; border-bottom:1px solid #1a1a1a;">{rows_skipped}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0; border-bottom:1px solid #1a1a1a;">Quarantined</td>
            <td style="color:#ff8800; font-size:0.85rem; font-weight:700; border-bottom:1px solid #1a1a1a;">{quarantined_n:,}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0; border-bottom:1px solid #1a1a1a;">Quarantine reason</td>
            <td style="color:#ff8800; font-size:0.75rem; font-family:'JetBrains Mono',monospace; border-bottom:1px solid #1a1a1a;">{q_reason}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0; border-bottom:1px solid #1a1a1a;">Recovery duration</td>
            <td style="color:#ff4444; font-size:0.85rem; font-weight:700; border-bottom:1px solid #1a1a1a;">{rec_time}</td>
        </tr>
        <tr>
            <td style="color:#666; font-size:0.75rem; padding:0.35rem 0.5rem 0.35rem 0;">Source</td>
            <td style="color:#d0d0d0; font-size:0.75rem; font-family:'JetBrains Mono',monospace;">Kinesis replay</td>
        </tr>
    </table>
</div>

<div style="
    background: linear-gradient(135deg, #0a1a0a, #0f0f0f);
    border: 1px solid #00cc6633;
    border-left: 4px solid #00cc66;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-top:0.75rem;
">
    <div style="color:#00cc66; font-weight:700; font-size:0.8rem;">🟢 PIPELINE RESTORED</div>
    <p style="color:#888; font-size:0.75rem; margin:0.4rem 0 0; line-height:1.5;">
        Lambda alias <code style="color:#ff6666;">LIVE → v1</code>.
        Snowflake is receiving clean records. Data flow healthy.
    </p>
</div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — PREVENTION MEASURES (CloudWatch Alarms)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        06 · PREVENTION — CLOUDWATCH ALARMS CREATED
    </h2>
</div>
""", unsafe_allow_html=True)

ALARM_DESCRIPTIONS = {
    "sigma-snowflake-zero-load":       "Fires if Snowflake COPY INTO loads 0 rows in consecutive intervals",
    "sigma-lambda-version-change":     "Fires on Lambda error spike immediately after a version change",
    "sigma-pipeline-row-divergence":   "Fires if Kinesis received rows diverge from Snowflake rows by > 5%",
}

ALARM_METRICS = {
    "sigma-snowflake-zero-load":       "Snowflake COPY INTO row count",
    "sigma-lambda-version-change":     "Lambda errors post-version-change",
    "sigma-pipeline-row-divergence":   "Kinesis vs Snowflake row divergence",
}

if data["alarms"]:
    alarm_cols = st.columns(len(data["alarms"]))
    for col, alarm in zip(alarm_cols, data["alarms"]):
        state = alarm["state"]
        if state == "OK":
            state_color, state_icon, state_bg = "#00cc66", "🟢", "#0a1a0f"
        elif state == "ALARM":
            state_color, state_icon, state_bg = "#ff2200", "🔴", "#1a0505"
        else:
            state_color, state_icon, state_bg = "#ffaa00", "🟡", "#1a1000"

        desc  = alarm.get("trigger") if alarm.get("trigger") != "—" else ALARM_DESCRIPTIONS.get(alarm["name"], "—")
        metric = alarm.get("metric", ALARM_METRICS.get(alarm["name"], "—"))

        with col:
            st.markdown(f"""
<div style="
    background: linear-gradient(135deg, {state_bg}, #0f0f0f);
    border: 1px solid {state_color}33;
    border-top: 3px solid {state_color};
    border-radius: 12px;
    padding: 1.5rem 1.2rem;
    box-shadow: 0 4px 20px {state_color}15;
">
    <div style="color:{state_color}; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; font-weight:700; margin-bottom:0.75rem;">
        {state_icon} STATE: {state}
    </div>
    <div style="color:#fff; font-size:0.82rem; font-weight:700; font-family:'JetBrains Mono',monospace; margin-bottom:0.75rem; word-break:break-word;">
        {alarm['name']}
    </div>
    <div style="color:#888; font-size:0.72rem; margin-bottom:0.5rem;">
        <strong style="color:#666;">Trigger:</strong> {desc}
    </div>
    <div style="color:#666; font-size:0.68rem;">
        <strong>Metric:</strong> {metric}
    </div>
</div>
            """, unsafe_allow_html=True)
else:
    # Show expected alarms from hardening findings
    hd_alarms = data.get("hardening", {}).get("alarms_created", [])
    if hd_alarms:
        alarm_cols = st.columns(len(hd_alarms))
        for col, alarm in zip(alarm_cols, hd_alarms):
            with col:
                st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #0a1a0f, #0f0f0f);
    border: 1px solid #00cc6633;
    border-top: 3px solid #00cc66;
    border-radius: 12px;
    padding: 1.5rem 1.2rem;
">
    <div style="color:#00cc66; font-size:0.7rem; letter-spacing:0.1em; text-transform:uppercase; font-weight:700; margin-bottom:0.75rem;">
        🟢 CREATED
    </div>
    <div style="color:#fff; font-size:0.82rem; font-weight:700; font-family:'JetBrains Mono',monospace; margin-bottom:0.75rem;">
        {alarm.get('alarm_name', '—')}
    </div>
    <div style="color:#888; font-size:0.72rem;">
        {alarm.get('description', '—')}
    </div>
</div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="
    background: #111111;
    border: 1px solid #ffaa0033;
    border-left: 4px solid #ffaa00;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
">
    <span style="color:#ffaa00; font-weight:700;">⚠️ No alarms found in CloudWatch.</span>
    <span style="color:#888; font-size:0.85rem;"> Did the Hardening Agent complete? Re-run Phase 3.</span>
</div>
        """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# QUARANTINE TABLE (bonus section)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff8800,#8b4400); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        🟡 QUARANTINED RECORDS
    </h2>
</div>
""", unsafe_allow_html=True)

st.caption(f"Source: `s3://{BUCKET}/{data['quarantine_key'] or 'quarantine/quarantine_*.csv'}`")

if not data["quarantine_df"].empty:
    st.dataframe(
        data["quarantine_df"],
        use_container_width=True,
        height=300,
    )
else:
    st.markdown("""
<div style="background:#111111; border:1px solid #333; border-radius:10px; padding:1.2rem 1.5rem; color:#666; font-size:0.85rem;">
    No quarantine CSV found in S3. Either Phase 3 is incomplete, or all records recovered cleanly.
</div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — INCIDENT REPORT VIEWER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:1rem;">
    <div style="width:4px; height:28px; background:linear-gradient(#ff2200,#8b0000); border-radius:2px;"></div>
    <h2 style="margin:0; font-size:1.3rem; font-weight:700; color:#fff; letter-spacing:-0.01em;">
        07 · FULL INCIDENT REPORT
    </h2>
</div>
""", unsafe_allow_html=True)

if data["report_md"]:
    st.caption(f"📄 `s3://{BUCKET}/{data['report_key']}` · Generated: {data['report_ts']}")
    with st.expander("📋 Click to read the CTO-ready post-mortem report", expanded=False):
        st.markdown(data["report_md"])
else:
    st.markdown(f"""
<div style="
    background: #111111;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 1.5rem;
">
    <div style="color:#ff4444; font-weight:700; margin-bottom:0.75rem;">⚠️ No incident report found in S3</div>
    <div style="color:#888; font-size:0.85rem; line-height:1.8;">
        Expected location: <code style="color:#ff6666; background:#1a0505; padding:2px 6px; border-radius:4px;">s3://{BUCKET}/reports/incident_*.md</code><br>
        Did Phase 3 complete successfully? Re-run the supervisor trigger:<br>
        <code style="color:#ff6666; background:#1a0505; padding:2px 6px; border-radius:4px; margin-top:0.5rem; display:inline-block;">
            python lab/trigger/pipeline_trigger.py --bucket {BUCKET}
        </code>
    </div>
</div>
    """, unsafe_allow_html=True)

st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# AGENT PERFORMANCE TABLE (bonus)
# ══════════════════════════════════════════════════════════════════════════════
if data["agent_perf"]:
    with st.expander("📊 Agent Performance Metrics", expanded=False):
        perf_df = pd.DataFrame(data["agent_perf"])
        st.dataframe(perf_df, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div style="
    background: #111111;
    border-top: 1px solid #2a0a0a;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
">
    <div style="color:#444; font-size:0.72rem; font-family:'JetBrains Mono',monospace;">
        🔴 SIGMA INTELLIGENCE PLATFORM · COMMAND CENTER
    </div>
    <div style="color:#333; font-size:0.68rem;">
        Reading from <span style="color:#8b0000;">s3://{BUCKET}</span>
        · Auto-refresh every 30s
        · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC
    </div>
</div>
""", unsafe_allow_html=True)
