"""
Day 12 Validator — The Sigma Intelligence Platform
Checks all required outputs exist and judgment questions are answered.

Usage: python tests/validate_day12.py
"""

import boto3, glob, json, os, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT       = Path(__file__).parent.parent
LAB_DIR    = ROOT / "lab"
OUTPUT_DIR = LAB_DIR / "agent_outputs"
CHAOS_LOG  = LAB_DIR / "chaos_log.md"

load_dotenv(LAB_DIR / ".env")

passed = 0
failed = 0
warns  = 0

def ok(msg):
    global passed; passed += 1
    print(f"  OK  {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  MISSING  {msg}")

def warn(msg):
    global warns; warns += 1
    print(f"  WARN  {msg}")

print()
print("=" * 55)
print("DAY 12 VALIDATOR — SIGMA INTELLIGENCE PLATFORM")
print("=" * 55)

# ── chaos_log.md ──────────────────────────────────────────────────────────────
print("\nPHASE 2 — CHAOS LOG:")
if CHAOS_LOG.exists():
    size    = CHAOS_LOG.stat().st_size
    content = CHAOS_LOG.read_text(encoding="utf-8")
    filled_fields = content.count("Your answer:") - content.count("Your answer:\n\n")
    if size > 3000:
        ok(f"chaos_log.md  ({size:,} bytes — filled in)")
    else:
        fail(f"chaos_log.md  ({size:,} bytes — template not filled in, needs > 3KB)")
    if "___" in content:
        warn("chaos_log.md — blank fields still present (replace ___ with answers)")
else:
    fail("chaos_log.md  MISSING")

# ── Lambda tools deployed ─────────────────────────────────────────────────────
print("\nPHASE 1 — LAMBDA TOOLS:")
region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
lam    = boto3.client("lambda", region_name=region)
tools  = [
    "sigma-tool-check-cloudwatch",
    "sigma-tool-get-kinesis-records",
    "sigma-tool-query-snowflake",
    "sigma-tool-rollback-lambda",
    "sigma-tool-create-alarm",
    "sigma-tool-quarantine-rows",
    "sigma-tool-load-snowflake",
    "sigma-tool-write-report",
    "sigma-tool-send-alert",
    "sigma-mcp-server",
]
for fn in tools:
    try:
        lam.get_function(FunctionName=fn)
        ok(fn)
    except Exception:
        fail(fn)

# ── Agent outputs ─────────────────────────────────────────────────────────────
print("\nPHASE 3 — AGENT OUTPUTS:")
bucket = os.getenv("SIGMA_S3_BUCKET", "")
if bucket:
    s3 = boto3.client("s3", region_name=region)
    for prefix, label in [
        ("reports/", "Incident report (S3 reports/)"),
        ("quarantine/", "Quarantine file (S3 quarantine/)"),
    ]:
        try:
            resp  = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            objs  = resp.get("Contents", [])
            today = [o for o in objs if "20260604" in o["Key"] or
                     o["LastModified"].strftime("%Y-%m-%d") == "2026-06-04"]
            if today:
                latest = sorted(today, key=lambda x: x["LastModified"], reverse=True)[0]
                ok(f"{label}  ({latest['Key']})")
            else:
                fail(f"{label}  (none found for today — run pipeline_trigger.py)")
        except Exception as e:
            fail(f"{label}  (S3 error: {e})")
else:
    warn("SIGMA_S3_BUCKET not set — skipping S3 output checks")

# ── CloudWatch alarms created ─────────────────────────────────────────────────
print("\nPHASE 3 — CLOUDWATCH ALARMS:")
cw = boto3.client("cloudwatch", region_name=region)
expected_alarms = [
    "sigma-snowflake-zero-load",
    "sigma-lambda-version-change",
    "sigma-pipeline-row-divergence",
]
for alarm_name in expected_alarms:
    try:
        resp   = cw.describe_alarms(AlarmNames=[alarm_name])
        alarms = resp.get("MetricAlarms", [])
        if alarms:
            state = alarms[0].get("StateValue", "?")
            ok(f"{alarm_name}  (state: {state})")
        else:
            fail(f"{alarm_name}  (not found — Hardening Agent did not create it)")
    except Exception as e:
        fail(f"{alarm_name}  (error: {e})")

# ── Forensics extension ───────────────────────────────────────────────────────
print("\nPHASE 3 — FORENSICS EXTENSION:")
cw_tool = LAB_DIR / "tools" / "check_cloudwatch.py"
if cw_tool.exists():
    content = cw_tool.read_text(encoding="utf-8")
    # Check for evidence of student extension — new detection beyond the base 4
    base_metrics = ["Errors", "DataFreshness", "WriteProvisionedThroughputExceeded",
                    "list_versions_by_function"]
    new_code = any(
        kw in content for kw in [
            "Throttled", "zero-byte", "suspended", "Duration",
            "Iterator", "GetRecords.IteratorAgeMilliseconds"
        ]
    )
    if new_code:
        ok("check_cloudwatch.py — extension detected")
    else:
        fail("check_cloudwatch.py — no extension found (add Option A, B, or C from Phase 3)")
else:
    fail("check_cloudwatch.py — file missing")

# ── Judgment answers ──────────────────────────────────────────────────────────
print("\nJUDGMENT QUESTIONS:")
if CHAOS_LOG.exists():
    content = CHAOS_LOG.read_text(encoding="utf-8")
    questions = [
        ("Forensics Agent", "Forensics Agent:"),
        ("Recovery Agent",  "Recovery Agent:"),
        ("Hardening Agent", "Hardening Agent:"),
    ]
    for label, marker in questions:
        if marker in content:
            idx   = content.index(marker) + len(marker)
            after = content[idx:idx+500]
            answer_start = after.find("Your answer:")
            if answer_start >= 0:
                answer = after[answer_start+12:answer_start+200].strip()
                if answer and len(answer) > 20 and "___" not in answer:
                    ok(f"{label:40} answered")
                else:
                    fail(f"{label:40} NOT ANSWERED")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 55)
total = passed + failed
if failed == 0 and warns == 0:
    print(f"  STATUS: ALL DONE — {passed}/{total} checks passed")
    print()
    print("  Push to your team fork:")
    print("    git add .")
    print('    git commit -m "Day 12 complete — self-healing agentic pipeline"')
    print("    git push")
elif failed == 0:
    print(f"  STATUS: COMPLETE WITH WARNINGS — {passed}/{total} passed, {warns} warnings")
    print("  Fix the warnings above before pushing.")
else:
    print(f"  STATUS: INCOMPLETE — {failed} item(s) missing")
    print(f"  Passed: {passed}/{total}")
    print("  Fix the missing items and re-run this validator.")
print("=" * 55)
print()

sys.exit(0 if failed == 0 else 1)
