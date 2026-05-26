"""
Day 6 Validator — Run this to check your work is complete.
Usage: python tests/validate_day6.py  (from repo/day6/)

Each test prints PASS or FAIL. All core tests green → push your code.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lab"))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}


def check(test_name, condition, hint=""):
    if condition:
        print(f"  [{PASS}] {test_name}")
        results["pass"] += 1
    else:
        print(f"  [{FAIL}] {test_name}")
        if hint:
            print(f"         Hint: {hint}")
        results["fail"] += 1


def skip(test_name, reason):
    print(f"  [{SKIP}] {test_name} — {reason}")
    results["skip"] += 1


# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("DAY 6 VALIDATOR — Sigma Intelligence Platform")
print("=" * 60)

lab_dir = os.path.join(os.path.dirname(__file__), "..", "lab")


# ── MODULE 1: SQL Review ──────────────────────────────────────
print("\n── MODULE 1: SQL Review ──────────────────────────────")

sql_review_path = os.path.join(lab_dir, "1_sql_review.py")
review_report_path = os.path.join(lab_dir, "review_report.json")

check("1_sql_review.py exists", os.path.exists(sql_review_path),
      "File should be in lab/ folder")

check("review_report.json was generated",
      os.path.exists(review_report_path),
      "Run: python sql_review.py (it saves review_report.json)")

if os.path.exists(review_report_path):
    try:
        with open(review_report_path) as f:
            report = json.load(f)

        check("Report is valid JSON with 'queries' key",
              "queries" in report,
              "review_report.json should have a 'queries' key")

        check("Report reviewed 3 queries",
              len(report.get("queries", {})) == 3,
              "batch_review() should review all 3 broken queries")

        total_issues = sum(q.get("issues_found", 0) for q in report.get("queries", {}).values())
        check("Found issues in broken SQL (total > 0)",
              total_issues > 0,
              "AI should find bugs — if 0 issues, check your prompt")

        check("Report has timestamp",
              "reviewed_at" in report,
              "Add datetime to your report")

    except json.JSONDecodeError:
        check("review_report.json is valid JSON", False,
              "File exists but isn't valid JSON — check output")


# ── MODULE 2: NL2SQL Pipeline ─────────────────────────────────
print("\n── MODULE 2: NL2SQL Pipeline ────────────────────────")

nl2sql_path = os.path.join(lab_dir, "2_nl2sql_pipeline.py")
audit_path = os.path.join(lab_dir, "nl2sql_audit.json")

check("2_nl2sql_pipeline.py exists", os.path.exists(nl2sql_path),
      "File should be in lab/ folder")

check("nl2sql_audit.json was generated",
      os.path.exists(audit_path),
      "Run: python 2_nl2sql_pipeline.py (it saves nl2sql_audit.json)")

if os.path.exists(audit_path):
    try:
        with open(audit_path) as f:
            audit = json.load(f)

        check("Audit log is a list",
              isinstance(audit, list),
              "nl2sql_audit.json should be a JSON array")

        check("Audit log has 5 entries (one per question)",
              len(audit) >= 5,
              "Pipeline should process all 5 test questions")

        statuses = [e.get("status") for e in audit]
        check("At least one query succeeded",
              "SUCCESS" in statuses,
              "At least 1 of 5 should succeed (even without Snowflake, SQL generation counts)")

    except json.JSONDecodeError:
        check("nl2sql_audit.json is valid JSON", False,
              "File exists but isn't valid JSON")

# Validator logic check (import and test without Bedrock)
print("\n── MODULE 2: Validator Logic ─────────────────────────")
try:
    import importlib
    _mod = importlib.import_module("2_nl2sql_pipeline")
    validate_sql = _mod.validate_sql

    check("validate_sql rejects DROP TABLE",
          validate_sql("DROP TABLE fact_transactions")[0] == False,
          "Should block dangerous keywords")

    check("validate_sql rejects DELETE",
          validate_sql("DELETE FROM fact_transactions")[0] == False,
          "Should block DELETE statements")

    check("validate_sql accepts valid SELECT",
          validate_sql("SELECT COUNT(*) FROM FACT_TRANSACTIONS")[0] == True,
          "Should allow safe SELECT on known tables")

    check("validate_sql rejects None input",
          validate_sql(None)[0] == False,
          "Should handle None gracefully")

    check("validate_sql rejects unknown tables",
          validate_sql("SELECT * FROM random_unknown_table")[0] == False,
          "Should reject queries not referencing our tables")

except ImportError as e:
    skip("Validator logic tests", f"Import error: {e}")
except Exception as e:
    skip("Validator logic tests", f"Error: {str(e)[:80]}")


# ── MODULE 3: dbt Generator ──────────────────────────────────
print("\n── MODULE 3: dbt Generator ──────────────────────────")

dbt_path = os.path.join(lab_dir, "3_dbt_generator.py")
dbt_output = os.path.join(lab_dir, "sigma_dbt")

check("3_dbt_generator.py exists", os.path.exists(dbt_path),
      "File should be in lab/ folder")

check("sigma_dbt/ directory was created",
      os.path.isdir(dbt_output),
      "Run: python 3_dbt_generator.py (it creates sigma_dbt/)")

if os.path.isdir(dbt_output):
    staging_dir = os.path.join(dbt_output, "models", "staging")
    marts_dir = os.path.join(dbt_output, "models", "marts")

    check("sigma_dbt/models/staging/ exists",
          os.path.isdir(staging_dir),
          "Directory structure should include models/staging/")

    check("sigma_dbt/models/marts/ exists",
          os.path.isdir(marts_dir),
          "Directory structure should include models/marts/")

    stg_file = os.path.join(staging_dir, "stg_transactions.sql")
    mart_file = os.path.join(marts_dir, "mart_merchant_performance.sql")

    check("stg_transactions.sql was generated",
          os.path.exists(stg_file) and os.path.getsize(stg_file) > 50,
          "Staging model SQL should be generated")

    check("mart_merchant_performance.sql was generated",
          os.path.exists(mart_file) and os.path.getsize(mart_file) > 50,
          "Mart model SQL should be generated")

    schema_files = [
        os.path.join(staging_dir, "schema.yml"),
        os.path.join(marts_dir, "schema.yml"),
    ]
    schemas_exist = sum(1 for f in schema_files if os.path.exists(f))
    check(f"schema.yml files generated ({schemas_exist}/2)",
          schemas_exist == 2,
          "Both staging and marts should have schema.yml")


# ── MODULE 5: Run dbt Project ────────────────────────────────
print("\n── MODULE 5: Run dbt Project ────────────────────────")

dbt_target = os.path.join(lab_dir, "sigma_dbt", "target")
run_results_path = os.path.join(dbt_target, "run_results.json")
manifest_path = os.path.join(dbt_target, "manifest.json")

check("sigma_dbt/target/ exists (dbt was run)",
      os.path.isdir(dbt_target),
      "Run: cd sigma_dbt && dbt run")

check("run_results.json exists (dbt run completed)",
      os.path.exists(run_results_path),
      "Run: dbt run inside sigma_dbt/")

if os.path.exists(run_results_path):
    try:
        with open(run_results_path) as f:
            run_results = json.load(f)

        results_list = run_results.get("results", [])
        success_count = sum(1 for r in results_list if r.get("status") in ("success", "pass"))
        fail_count = sum(1 for r in results_list if r.get("status") == "fail")

        check(f"At least 2 models ran successfully",
              success_count >= 2,
              "dbt run should show stg_transactions and mart_merchant_performance as OK")

        check("dbt test was run (results include tests)",
              len(results_list) > 2,
              "Run: dbt test (or dbt build) inside sigma_dbt/")

        check("At least 1 test failed (deliberate bad data test)",
              fail_count >= 1,
              "One test should fail — that is expected. If 0 failures, check your marts/schema.yml")

    except json.JSONDecodeError:
        check("run_results.json is valid JSON", False,
              "File exists but isn't valid JSON")


# ── STRETCH: SQL Review Agent ─────────────────────────────────
print("\n── STRETCH: SQL Review Agent (bonus) ────────────────")

batch_report_path = os.path.join(lab_dir, "batch_report.json")
my_query_path = os.path.join(lab_dir, "queries", "my_query.sql")

if not os.path.exists(batch_report_path):
    skip("batch_report.json generated",
         "Run: python stretch_goal_sql_review.py queries/")
else:
    try:
        with open(batch_report_path) as f:
            batch = json.load(f)

        check("batch_report.json is valid JSON",
              True)

        check("Batch report reviewed 4+ files (3 given + your custom query)",
              batch.get("files_reviewed", 0) >= 4,
              "Create queries/my_query.sql with intentional bugs, then re-run")

        check("Your custom query exists (queries/my_query.sql)",
              os.path.exists(my_query_path),
              "Write your own broken SQL with 2+ intentional bugs")

    except json.JSONDecodeError:
        check("batch_report.json is valid JSON", False,
              "File exists but isn't valid JSON")


# ── FINAL REPORT ──────────────────────────────────────────────
print("\n" + "=" * 60)
total = results["pass"] + results["fail"]
print(f"RESULTS: {results['pass']}/{total} passed | {results['fail']} failed | {results['skip']} skipped")
print("=" * 60)

if results["fail"] == 0 and results["pass"] >= 6:
    print("\n  ALL CORE TESTS PASSED. Push your code!")
    print("  git add . && git commit -m \"Day 6 done\" && git push\n")
elif results["fail"] == 0:
    print("\n  LOOKING GOOD. Run the scripts to generate output files.")
    print("  Then re-run this validator.\n")
else:
    print(f"\n  {results['fail']} tests need fixing. Run each module:")
    print("    python 1_sql_review.py")
    print("    python 2_nl2sql_pipeline.py")
    print("    python 3_dbt_generator.py")
    print("  Then re-run: python tests/validate_day6.py\n")
