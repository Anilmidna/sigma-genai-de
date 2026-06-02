"""
Sigma Command Center — Business Incident Dashboard
Reads directly from your team's S3 bucket (Phase 3 output).

Prerequisites:
  - lab/.env must have SIGMA_S3_BUCKET and AWS credentials set
  - Phase 3 must have completed (incident report and quarantine file in S3)

Run:  streamlit run app.py
"""

import io, json, os, re
from datetime import datetime
from pathlib import Path

import boto3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / "lab" / ".env")

# ── Config ────────────────────────────────────────────────────────────────────
BUCKET = os.getenv("SIGMA_S3_BUCKET", "")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

SEVERITY_COLOR = {
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
)

# ── Guard: bucket must be set ─────────────────────────────────────────────────
if not BUCKET:
    st.error("SIGMA_S3_BUCKET is not set. Check lab/.env")
    st.stop()

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_data() -> dict:
    s3  = boto3.client("s3", region_name=REGION)
    cw  = boto3.client("cloudwatch", region_name=REGION)

    # ── Incident report ───────────────────────────────────────────────────────
    report_md   = ""
    report_key  = ""
    try:
        resp    = s3.list_objects_v2(Bucket=BUCKET, Prefix="reports/")
        objects = resp.get("Contents", [])
        if objects:
            latest     = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]
            report_key = latest["Key"]
            report_md  = s3.get_object(Bucket=BUCKET, Key=report_key)["Body"].read().decode()
    except Exception as e:
        st.warning(f"Could not read incident report from S3: {e}")

    # ── Quarantine CSV ────────────────────────────────────────────────────────
    quarantine_df = pd.DataFrame()
    try:
        resp    = s3.list_objects_v2(Bucket=BUCKET, Prefix="quarantine/")
        objects = resp.get("Contents", [])
        if objects:
            latest  = sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]
            csv_raw = s3.get_object(Bucket=BUCKET, Key=latest["Key"])["Body"].read().decode()
            quarantine_df = pd.read_csv(io.StringIO(csv_raw))
    except Exception as e:
        st.warning(f"Could not read quarantine file from S3: {e}")

    # ── CloudWatch alarm states ───────────────────────────────────────────────
    alarms = []
    try:
        alarm_names = [
            "sigma-snowflake-zero-load",
            "sigma-lambda-version-change",
            "sigma-pipeline-row-divergence",
        ]
        resp   = cw.describe_alarms(AlarmNames=alarm_names)
        alarms = [
            {
                "name":    a["AlarmName"],
                "trigger": a.get("AlarmDescription", "—"),
                "state":   a["StateValue"],
            }
            for a in resp.get("MetricAlarms", [])
        ]
    except Exception as e:
        st.warning(f"Could not read CloudWatch alarms: {e}")

    # ── Parse incident report for key numbers ─────────────────────────────────
    def extract(pattern, default="—"):
        m = re.search(pattern, report_md, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else default

    records_lost    = extract(r"Records (?:lost|missing)[:\s]+([\d,]+)")
    recovered       = extract(r"records? (?:restored|loaded|recovered)[:\s]+([\d,]+)")
    root_cause      = extract(r"## Root Cause\n+(.*?)\n+##")
    fix_applied     = extract(r"## Fix Applied\n+(.*?)\n+##")
    report_time     = report_key.split("_")[-1].replace(".md", "") if report_key else "—"

    return {
        "report_md":      report_md,
        "report_key":     report_key,
        "records_lost":   records_lost,
        "recovered":      recovered,
        "quarantined":    str(len(quarantine_df)) if not quarantine_df.empty else "—",
        "root_cause":     root_cause,
        "fix_applied":    fix_applied,
        "report_time":    report_time,
        "alarms":         alarms,
        "quarantine_df":  quarantine_df,
        "bucket":         BUCKET,
    }


# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner("Reading from your S3 bucket..."):
    data = load_data()

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔴 Sigma Command Center")
st.caption(
    f"Bucket: **{data['bucket']}** · "
    f"Report: **{data['report_key'] or 'not found'}** · "
    f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}"
)
if st.button("🔄 Refresh"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

# ── KPI Cards ─────────────────────────────────────────────────────────────────
st.subheader("Incident Summary")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Records Lost",     data["records_lost"])
with c2:
    st.metric("Records Recovered", data["recovered"])
with c3:
    st.metric("Records Quarantined", data["quarantined"])
with c4:
    alarms_ok = sum(1 for a in data["alarms"] if a["state"] == "OK")
    st.metric("Alarms Created", f"{alarms_ok} / {len(data['alarms'])}")

st.markdown("---")

# ── Root Cause + Fix ──────────────────────────────────────────────────────────
left, right = st.columns(2)

with left:
    st.subheader("Root Cause")
    if data["root_cause"] != "—":
        st.error(data["root_cause"])
    else:
        st.warning("Root cause not found in report — check S3")

with right:
    st.subheader("Fix Applied")
    if data["fix_applied"] != "—":
        st.success(data["fix_applied"])
    else:
        st.warning("Fix details not found in report — check S3")

st.markdown("---")

# ── Prevention Measures ───────────────────────────────────────────────────────
st.subheader("Prevention — CloudWatch Alarms Created")
if data["alarms"]:
    cols = st.columns(len(data["alarms"]))
    for col, alarm in zip(cols, data["alarms"]):
        with col:
            state = alarm["state"]
            icon  = "🟢" if state == "OK" else ("🔴" if state == "ALARM" else "🟡")
            st.markdown(f"**{icon} {alarm['name']}**")
            st.caption(f"State: {state}")
            if alarm["trigger"] != "—":
                st.caption(alarm["trigger"])
else:
    st.warning("No alarms found — did the Hardening Agent complete?")

st.markdown("---")

# ── Quarantine Table ──────────────────────────────────────────────────────────
st.subheader(f"Quarantined Records ({data['quarantined']})")
if not data["quarantine_df"].empty:
    st.dataframe(data["quarantine_df"], use_container_width=True)
else:
    st.info("No quarantine file found in S3")

st.markdown("---")

# ── Incident Report ───────────────────────────────────────────────────────────
st.subheader("Full Incident Report")
if data["report_md"]:
    with st.expander("Click to read the CTO-ready post-mortem", expanded=True):
        st.markdown(data["report_md"])
else:
    st.warning(
        "No incident report found in S3. "
        f"Expected: s3://{BUCKET}/reports/incident_*.md\n\n"
        "Did Phase 3 complete successfully? Re-run:\n"
        "`python lab/trigger/pipeline_trigger.py --bucket " + BUCKET + "`"
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"Sigma Intelligence Platform · "
    f"Reading from s3://{BUCKET} · "
    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
