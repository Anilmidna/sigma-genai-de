"""
Day 7 Validator — Run this to check your work is complete.
Usage: python tests/validate_day7.py  (from repo/day7/)

Each test prints PASS, FAIL, or SKIP.
All core module tests green → push your code.
"""

import sys
import os
import json

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── COLOUR CODES ──────────────────────────────────────────────
PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}


def check(test_name: str, condition: bool, hint: str = ""):
    if condition:
        print(f"  [{PASS}] {test_name}")
        results["pass"] += 1
    else:
        print(f"  [{FAIL}] {test_name}")
        if hint:
            print(f"         Hint: {hint}")
        results["fail"] += 1


def skip(test_name: str, reason: str):
    print(f"  [{SKIP}] {test_name} — {reason}")
    results["skip"] += 1


# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("DAY 7 VALIDATOR — Sigma Intelligence Platform")
print("Pipeline Brain: Spec-to-Ship in 45 Minutes")
print("=" * 60)

# Paths — validator runs from repo/day7/
lab_dir = os.path.join(os.path.dirname(__file__), "..", "lab")
pb_dir  = os.path.join(lab_dir, "pipeline_brain")


# ── MODULE 0: Team Spec ───────────────────────────────────────
print("\n── MODULE 0: Team Spec Writing ──────────────────────────")

my_spec = os.path.join(lab_dir, "my_pipeline_spec.txt")
spec_scenarios = os.path.join(lab_dir, "0_team_spec_scenarios.md")

check("0_team_spec_scenarios.md exists",
      os.path.exists(spec_scenarios),
      "File should be at lab/0_team_spec_scenarios.md")

if not os.path.exists(my_spec):
    skip("my_pipeline_spec.txt",
         "Team task — fill in your scenario from 0_team_spec_scenarios.md and save as lab/my_pipeline_spec.txt")
else:
    spec_size = os.path.getsize(my_spec)
    check("my_pipeline_spec.txt has content (> 100 bytes)",
          spec_size > 100,
          f"File is {spec_size} bytes — fill in all 6 sections of the spec template")


# ── MODULE 1: Spec-to-Pipeline ────────────────────────────────
print("\n── MODULE 1: Spec to PySpark Pipeline ───────────────────")

m1_script = os.path.join(lab_dir, "1_spec_to_pipeline.py")
gen_pipeline = os.path.join(pb_dir, "generated_pipeline.py")
gen_report   = os.path.join(pb_dir, "generation_report.json")

check("1_spec_to_pipeline.py exists",
      os.path.exists(m1_script),
      "File should be at lab/1_spec_to_pipeline.py")

check("pipeline_brain/generated_pipeline.py exists",
      os.path.exists(gen_pipeline),
      "Run: cd lab && python 1_spec_to_pipeline.py")

if os.path.exists(gen_pipeline):
    file_size = os.path.getsize(gen_pipeline)
    check("generated_pipeline.py is substantial (> 500 bytes)",
          file_size > 500,
          f"File exists but is {file_size} bytes — may have failed silently. Re-run Module 1.")

    with open(gen_pipeline, "r", encoding="utf-8", errors="replace") as f:
        pipeline_content = f.read()

    check("generated_pipeline.py contains PySpark code",
          any(kw in pipeline_content for kw in ["def ", "SparkSession", "PySpark", "pyspark"]),
          "Should contain at least one function definition or SparkSession reference")

check("pipeline_brain/generation_report.json exists",
      os.path.exists(gen_report),
      "Report should be saved when Module 1 runs")

if os.path.exists(gen_report):
    try:
        with open(gen_report) as f:
            rpt = json.load(f)
        check("generation_report.json is valid JSON with 'generated_at'",
              "generated_at" in rpt,
              "Report should have a generated_at timestamp")
        check("generation_report.json has model info",
              "model" in rpt,
              "Report should record which model was used")
    except json.JSONDecodeError:
        check("generation_report.json is valid JSON", False,
              "File exists but cannot be parsed — check for truncation")


# ── MODULE 2: DAG Generator ───────────────────────────────────
print("\n── MODULE 2: Airflow DAG Generator ──────────────────────")

m2_script  = os.path.join(lab_dir, "2_dag_generator.py")
sigma_dag  = os.path.join(pb_dir, "sigma_dag.py")
dag_report = os.path.join(pb_dir, "dag_report.json")

check("2_dag_generator.py exists",
      os.path.exists(m2_script),
      "File should be at lab/2_dag_generator.py")

check("pipeline_brain/sigma_dag.py exists",
      os.path.exists(sigma_dag),
      "Run: cd lab && python 2_dag_generator.py")

if os.path.exists(sigma_dag):
    dag_size = os.path.getsize(sigma_dag)
    check("sigma_dag.py is substantial (> 200 bytes)",
          dag_size > 200,
          f"File is {dag_size} bytes — may be empty or failed. Re-run Module 2.")

    with open(sigma_dag, "r", encoding="utf-8", errors="replace") as f:
        dag_content = f.read()

    check("sigma_dag.py contains DAG definition",
          "dag" in dag_content.lower() or "DAG" in dag_content,
          "Should contain Airflow DAG keyword")

check("pipeline_brain/dag_report.json exists",
      os.path.exists(dag_report),
      "Report should be saved when Module 2 runs")

if os.path.exists(dag_report):
    try:
        with open(dag_report) as f:
            drpt = json.load(f)
        check("dag_report.json is valid JSON with 'generated_at'",
              "generated_at" in drpt,
              "Report should have a generated_at timestamp")
        check("dag_report.json has tasks_found count",
              "tasks_found" in drpt,
              "Report should record how many tasks were found in the generated DAG")
        check("dag_report.json has has_dependencies field",
              "has_dependencies" in drpt,
              "Report should indicate whether >> dependencies were found")
    except json.JSONDecodeError:
        check("dag_report.json is valid JSON", False,
              "File exists but cannot be parsed")


# ── MODULE 3: Pipeline Hardening ─────────────────────────────
print("\n── MODULE 3: Pipeline Hardening ─────────────────────────")

m3_script       = os.path.join(lab_dir, "3_pipeline_hardening.py")
hardened        = os.path.join(pb_dir, "hardened_pipeline.py")
hardening_report = os.path.join(pb_dir, "hardening_report.json")

check("3_pipeline_hardening.py exists",
      os.path.exists(m3_script),
      "File should be at lab/3_pipeline_hardening.py")

check("pipeline_brain/hardened_pipeline.py exists",
      os.path.exists(hardened),
      "Run: cd lab && python 3_pipeline_hardening.py")

if os.path.exists(hardened):
    hardened_size = os.path.getsize(hardened)
    check("hardened_pipeline.py is substantial (> 500 bytes)",
          hardened_size > 500,
          f"File is {hardened_size} bytes — may be empty. Re-run Module 3.")

check("pipeline_brain/hardening_report.json exists",
      os.path.exists(hardening_report),
      "Report should be saved when Module 3 runs")

if os.path.exists(hardening_report):
    try:
        with open(hardening_report) as f:
            hrpt = json.load(f)
        check("hardening_report.json is valid JSON",
              True)
        check("hardening_report.json has 'improvements_added' key",
              "improvements_added" in hrpt,
              "Report should list what was added by hardening")
        check("improvements_added list has at least 1 item",
              isinstance(hrpt.get("improvements_added"), list)
              and len(hrpt.get("improvements_added", [])) >= 1,
              "At least one improvement should have been detected")
        check("hardening_report.json has model_used field",
              "model_used" in hrpt,
              "Report should record which model was used (should be Nova Pro)")

        if "model_used" in hrpt:
            check("Module 3 used Nova Pro (heavier reasoning task)",
                  "pro" in hrpt["model_used"].lower(),
                  f"Expected nova-pro-v1:0, got: {hrpt.get('model_used')}")

    except json.JSONDecodeError:
        check("hardening_report.json is valid JSON", False,
              "File exists but cannot be parsed")


# ── MODULE 5: Code Review ─────────────────────────────────────
print("\n── MODULE 5: Code Review Agent ──────────────────────────")

m5_script    = os.path.join(lab_dir, "5_code_review.py")
review_json  = os.path.join(pb_dir, "code_review.json")

check("5_code_review.py exists",
      os.path.exists(m5_script),
      "File should be at lab/5_code_review.py")

check("pipeline_brain/code_review.json exists",
      os.path.exists(review_json),
      "Run: cd lab && python 5_code_review.py")

if os.path.exists(review_json):
    try:
        with open(review_json) as f:
            crpt = json.load(f)
        check("code_review.json is valid JSON with 'summary' key",
              "summary" in crpt,
              "Review JSON should have a summary section")
        check("code_review.json summary has merge_recommendation",
              "merge_recommendation" in crpt.get("summary", {}),
              "Summary should have merge_recommendation (APPROVE/REJECT/APPROVE_WITH_CHANGES)")
    except json.JSONDecodeError:
        check("code_review.json is valid JSON", False,
              "File exists but cannot be parsed — check for truncation")

# Student review artefacts — SKIP (not required) if absent
fixed_pipeline   = os.path.join(pb_dir, "fixed_pipeline.py")
review_notes     = os.path.join(pb_dir, "my_review_notes.txt")

if not os.path.exists(fixed_pipeline):
    skip("pipeline_brain/fixed_pipeline.py",
         "Student task — fix 2 FAIL items in generated_pipeline.py, save as fixed_pipeline.py")
else:
    fixed_size = os.path.getsize(fixed_pipeline)
    check("fixed_pipeline.py has content (> 200 bytes)",
          fixed_size > 200,
          f"File is {fixed_size} bytes — may be empty")

if not os.path.exists(review_notes):
    skip("pipeline_brain/my_review_notes.txt",
         "Student task — document your changes from code review")
else:
    notes_size = os.path.getsize(review_notes)
    check("my_review_notes.txt has content (> 20 bytes)",
          notes_size > 20,
          f"File is {notes_size} bytes — should contain your review notes")


# ── STRETCH: Schema Drift ─────────────────────────────────────
print("\n── STRETCH: Schema Drift (bonus — skip if not run) ──────")

drift_report  = os.path.join(pb_dir, "schema_drift_report.json")
drift_handler = os.path.join(pb_dir, "schema_evolution_handler.py")

if not os.path.exists(drift_report):
    skip("pipeline_brain/schema_drift_report.json",
         "Run: python 4_stretch_goal_schema_drift.py")
else:
    try:
        with open(drift_report) as f:
            drft = json.load(f)
        check("schema_drift_report.json is valid JSON",
              True)
        check("schema_drift_report.json has new_columns_detected",
              "new_columns_detected" in drft,
              "Should list which columns were detected as new")
        check("schema_drift_report.json detected 2 new columns",
              len(drft.get("new_columns_detected", [])) >= 2,
              "payment_gateway and discount_amount should be detected")
    except json.JSONDecodeError:
        check("schema_drift_report.json is valid JSON", False,
              "File exists but cannot be parsed")

if not os.path.exists(drift_handler):
    skip("pipeline_brain/schema_evolution_handler.py",
         "Run: python 4_stretch_goal_schema_drift.py")
else:
    handler_size = os.path.getsize(drift_handler)
    check("schema_evolution_handler.py exists and has content",
          handler_size > 200,
          f"Handler is {handler_size} bytes — may be empty")


# ── FINAL REPORT ──────────────────────────────────────────────
print("\n" + "=" * 60)
total = results["pass"] + results["fail"]
print(f"RESULTS: {results['pass']}/{total} passed  |  {results['fail']} failed  |  {results['skip']} skipped")
print("=" * 60)

# Core = Modules 1-3 (not stretch)
core_fail = results["fail"]

if core_fail == 0 and results["pass"] >= 8:
    print("\n  ALL CORE TESTS PASSED. Push your code!")
    print("  git add .")
    print("  git commit -m \"Day 7 done\"")
    print("  git push")
    print()
    print("  Files committed:")
    print("    pipeline_brain/generated_pipeline.py   — your AI-generated pipeline")
    print("    pipeline_brain/generation_report.json  — model metadata")
    print("    pipeline_brain/sigma_dag.py             — AI-generated Airflow DAG")
    print("    pipeline_brain/dag_report.json          — DAG metadata")
    print("    pipeline_brain/hardened_pipeline.py     — production-hardened pipeline")
    print("    pipeline_brain/hardening_report.json    — hardening metadata")
    print("    pipeline_brain/code_review.json         — 12-point review results")
    print("    pipeline_brain/fixed_pipeline.py        — your fixed version (if done)")
    print("    pipeline_brain/my_review_notes.txt      — your review notes (if done)")
    print("    lab/my_pipeline_spec.txt                — your team's spec (if written)\n")
elif core_fail == 0:
    print("\n  LOOKING GOOD. Run the scripts to generate output files.")
    print("  Then re-run this validator.\n")
else:
    print(f"\n  {core_fail} tests need fixing. Run each module in order:")
    print("    cd repo/day7/lab")
    print("    python 1_spec_to_pipeline.py    # creates pipeline_brain/generated_pipeline.py")
    print("    python 2_dag_generator.py       # creates pipeline_brain/sigma_dag.py")
    print("    python 3_pipeline_hardening.py  # creates pipeline_brain/hardened_pipeline.py")
    print("    python 5_code_review.py         # creates pipeline_brain/code_review.json")
    print("  Then re-run: python tests/validate_day7.py\n")
