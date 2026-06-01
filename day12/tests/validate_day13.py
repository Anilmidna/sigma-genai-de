"""
Day 13 Validator — checks all required output files exist and
judgment questions are answered.

Usage: python tests/validate_day13.py
"""

import os, sys, json, glob

LAB_DIR    = os.path.join(os.path.dirname(__file__), "..", "lab")
OUTPUT_DIR = os.path.join(LAB_DIR, "agent_outputs")

def find_files(pattern):
    """Find files matching a glob pattern."""
    return glob.glob(os.path.join(OUTPUT_DIR, pattern))

def check_judgment(json_path):
    """Returns True if student answered the judgment question."""
    try:
        with open(json_path) as f:
            data = json.load(f)
        answer = data.get("student_judgment", "NOT ANSWERED")
        return bool(answer) and answer.strip() != "NOT ANSWERED"
    except Exception:
        return False

print("\n" + "="*55)
print("DAY 13 VALIDATOR — THE SIGMA INTELLIGENCE PLATFORM")
print("="*55)

passed = 0
failed = 0

# ── Phase 1: chaos_log.md ─────────────────────────────────────────────────────
print("\nPHASE 2 — CHAOS LOG:")
chaos_log = os.path.join(LAB_DIR, "chaos_log_template.md")
if os.path.exists(chaos_log):
    size = os.path.getsize(chaos_log)
    # Check if it looks filled in (size > 2KB means they added content)
    if size > 2000:
        print(f"  ✓ chaos_log_template.md        ({size:,} bytes — looks filled in)")
        passed += 1
    else:
        print(f"  ⚠ chaos_log_template.md        ({size:,} bytes — template not filled in)")
        failed += 1
else:
    print(f"  ✗ chaos_log_template.md        MISSING")
    failed += 1

# ── Phase 3: Agent output files ───────────────────────────────────────────────
print("\nPHASE 3 — AGENT OUTPUTS:")

checks = [
    ("schema_drift_incident_*.json", "Schema Evolution Agent", "schema_drift"),
    ("pii_scan_*.json",              "PII Detection Agent",    "pii"),
    ("quality_report_*.json",        "Ingestion Quality Agent","quality"),
    ("quarantine_*.csv",             "Quarantine file",        None),
]

judgment_files = []

for pattern, label, jtype in checks:
    matches = find_files(pattern)
    if matches:
        latest = sorted(matches)[-1]
        size   = os.path.getsize(latest)
        fname  = os.path.basename(latest)
        print(f"  ✓ {fname:45} ({size:,} bytes)")
        passed += 1
        if jtype:
            judgment_files.append((latest, label))
    else:
        print(f"  ✗ {pattern:45} MISSING — run the agent")
        failed += 1

# ── Judgment questions ─────────────────────────────────────────────────────────
print("\nJUDGMENT ANSWERS (accountability check):")
for jpath, label in judgment_files:
    answered = check_judgment(jpath)
    mark     = "✓" if answered else "⚠"
    status   = "answered" if answered else "NOT ANSWERED"
    print(f"  {mark} {label:40} {status}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*55)
total = passed + failed
if failed == 0:
    print(f"  STATUS: ✅ ALL DONE — {passed}/{total} checks passed")
    print("  Push to your fork:")
    print("    git add .")
    print('    git commit -m "Day 13 complete"')
    print("    git push")
else:
    print(f"  STATUS: ✗ INCOMPLETE — {failed} item(s) missing")
    print(f"  Passed: {passed}/{total}")
    print("  Fix the missing items and re-run this validator.")
print("="*55 + "\n")

sys.exit(0 if failed == 0 else 1)
