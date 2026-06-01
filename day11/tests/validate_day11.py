"""
Day 11 Validator — checks that all required output files exist.
Run this after completing all labs: python tests/validate_day11.py
"""

import os, sys, json

LAB_DIR    = os.path.join(os.path.dirname(__file__), "..", "lab")
OUTPUT_DIR = os.path.join(LAB_DIR, "agent_outputs")
DATA_DIR   = os.path.join(LAB_DIR, "data")

REQUIRED_FILES = {
    # sample_data.py outputs
    os.path.join(DATA_DIR, "transactions_raw.csv"):     "sample_data.py",
    os.path.join(DATA_DIR, "customers_raw.csv"):        "sample_data.py",
    # Lab 1 outputs
    os.path.join(OUTPUT_DIR, "supervisor_result.json"): "1_multi_agent_pipeline.py",
    os.path.join(OUTPUT_DIR, "swarm_result.json"):      "1_multi_agent_pipeline.py",
    os.path.join(OUTPUT_DIR, "pipeline_result.json"):   "1_multi_agent_pipeline.py",
    # Lab 2 outputs
    os.path.join(OUTPUT_DIR, "quality_report.json"):    "2_ingestion_quality_agent.py",
    os.path.join(OUTPUT_DIR, "ge_expectations.json"):   "2_ingestion_quality_agent.py",
    os.path.join(OUTPUT_DIR, "clean_output.csv"):       "2_ingestion_quality_agent.py",
    os.path.join(OUTPUT_DIR, "quarantine.csv"):         "2_ingestion_quality_agent.py",
    # Lab 3 outputs
    os.path.join(OUTPUT_DIR, "pii_scan_report.json"):   "3_pii_sensitivity_agent.py",
    os.path.join(OUTPUT_DIR, "sensitivity_report.json"):"3_pii_sensitivity_agent.py",
}

STRETCH_FILES = {
    os.path.join(OUTPUT_DIR, "self_heal_incident_report.json"): "4_stretch_goal_self_heal_loop.py",
}

def check_judgment(json_path: str) -> bool:
    """Returns True if the student answered the judgment question."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        answer = data.get("student_judgment", "NOT ANSWERED")
        return bool(answer) and answer != "NOT ANSWERED"
    except Exception:
        return False

PRE_WORK_FILE = os.path.join(LAB_DIR, "manual_first_annotated.csv")

print("\n" + "="*55)
print("DAY 11 VALIDATOR")
print("="*55)

passed = 0
failed = 0

print("\nPRE-WORK:")
if os.path.exists(PRE_WORK_FILE):
    import csv as _csv
    with open(PRE_WORK_FILE, newline="") as f:
        rows = list(_csv.DictReader(f))
    annotations = sum(1 for r in rows if r.get("issue_found", "").strip())
    print(f"  ✓ {'manual_first_annotated.csv':40} ({annotations} rows annotated)")
else:
    print(f"  ✗ {'manual_first_annotated.csv':40} MISSING — complete pre-work and push")
    failed += 1

print("\nCORE MODULES (Labs 1–3):")
for filepath, source in REQUIRED_FILES.items():
    fname = os.path.basename(filepath)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"  ✓ {fname:40} ({size:,} bytes)")
        passed += 1
    else:
        print(f"  ✗ {fname:40} MISSING — run {source}")
        failed += 1

print("\nJUDGMENT ANSWERS (accountability check):")
judgment_files = [
    os.path.join(OUTPUT_DIR, "pipeline_result.json"),
    os.path.join(OUTPUT_DIR, "quality_report.json"),
    os.path.join(OUTPUT_DIR, "sensitivity_report.json"),
]
for jf in judgment_files:
    fname = os.path.basename(jf)
    if os.path.exists(jf):
        answered = check_judgment(jf)
        mark = "✓" if answered else "⚠"
        label = "answered" if answered else "NOT ANSWERED"
        print(f"  {mark} {fname:40} judgment: {label}")

print("\nSTRETCH GOAL (Lab 4):")
stretch_found = 0
for filepath, source in STRETCH_FILES.items():
    fname = os.path.basename(filepath)
    if os.path.exists(filepath):
        print(f"  👑 {fname:40} COMPLETE")
        stretch_found += 1
    else:
        print(f"  ○  {fname:40} not done (run {source})")

print("\n" + "="*55)
if failed == 0:
    if stretch_found == len(STRETCH_FILES):
        print("  STATUS: 👑 ALL DONE — STRETCH GOAL COMPLETE")
    else:
        print("  STATUS: ✅ CORE COMPLETE — push to your fork")
    print(f"  Core: {passed}/{len(REQUIRED_FILES)} files present")
else:
    print(f"  STATUS: ✗ INCOMPLETE — {failed} file(s) missing")
    print(f"  Core: {passed}/{len(REQUIRED_FILES)} files present")
print("="*55 + "\n")

sys.exit(0 if failed == 0 else 1)
