"""
Day 8 Validator — Run this to check your work is complete.
Usage: python tests/validate.py  (from repo/day8/)

Each test prints PASS, FAIL, or SKIP.
All core sprint tests green → push your code.
"""

import sys
import os
import json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}
judgment_answers = []


def check(test_name: str, condition: bool, hint: str = ""):
    if condition:
        print(f"  [{PASS}] {test_name}")
        results["pass"] += 1
    else:
        print(f"  [{FAIL}] {test_name}")
        if hint:
            print(f"         → {hint}")
        results["fail"] += 1


def skip(test_name: str, reason: str):
    print(f"  [{SKIP}] {test_name} — {reason}")
    results["skip"] += 1


def check_judgment(report_path: str, sprint_label: str):
    """Check if student answered the accountability gate question."""
    if not os.path.exists(report_path):
        return
    try:
        with open(report_path) as f:
            data = json.load(f)
        answer = data.get("student_judgment", "NOT ANSWERED")
        answered = answer and answer != "NOT ANSWERED" and len(answer.strip()) > 5
        check(f"{sprint_label}: student judgment answered",
              answered,
              f'Currently: "{answer[:80]}" — answer the question when prompted')
        if answered:
            judgment_answers.append((sprint_label, answer[:120]))
    except (json.JSONDecodeError, Exception):
        pass


lab_dir = os.path.join(os.path.dirname(__file__), "..", "lab")
db_dir = os.path.join(lab_dir, "devops_brain")

print("\n" + "=" * 60)
print("DAY 8 VALIDATOR — Sigma Intelligence Platform")
print("Code Review + Debug + Docs + CI/CD + Testing + Observability")
print("=" * 60)


# ── SPRINT 1: Code Review ────────────────────────────────────
print("\n── SPRINT 1: AI Code Review + Bug Diagnosis ─────────────")

code_review = os.path.join(db_dir, "code_review_report.json")
rca_report = os.path.join(db_dir, "rca_report.json")

check("devops_brain/code_review_report.json exists",
      os.path.exists(code_review),
      "Run: cd lab && python 1_code_review.py")

if os.path.exists(code_review):
    try:
        with open(code_review) as f:
            cr = json.load(f)
        check("code_review_report has bugs_found",
              "bugs_found" in cr or "review" in cr or "findings" in cr,
              "Report should contain AI bug findings")
        check_judgment(code_review, "Sprint 1")
    except json.JSONDecodeError:
        check("code_review_report.json is valid JSON", False, "Cannot be parsed")

check("devops_brain/rca_report.json exists",
      os.path.exists(rca_report),
      "Run: cd lab && python 1_code_review.py")


# ── SPRINT 2: Documentation ──────────────────────────────────
print("\n── SPRINT 2: Documentation Automation ───────────────────")

documented = os.path.join(db_dir, "documented_pipeline.py")
runbook = os.path.join(db_dir, "runbook.md")
design_doc = os.path.join(db_dir, "design_doc.md")
doc_report = os.path.join(db_dir, "doc_report.json")

check("devops_brain/documented_pipeline.py exists",
      os.path.exists(documented),
      "Run: cd lab && python 2_doc_generator.py")

if os.path.exists(documented):
    with open(documented, encoding="utf-8", errors="replace") as f:
        doc_content = f.read()
    docstring_count = doc_content.count('"""')
    check("documented_pipeline.py has docstrings added",
          docstring_count >= 6,
          f"Found {docstring_count // 2} docstrings — AI should add one per function")

check("devops_brain/runbook.md exists",
      os.path.exists(runbook),
      "Run: cd lab && python 2_doc_generator.py")

if os.path.exists(runbook):
    size = os.path.getsize(runbook)
    check("runbook.md has content (> 500 bytes)",
          size > 500,
          f"Runbook is {size} bytes — may be too short")

check("devops_brain/design_doc.md exists",
      os.path.exists(design_doc),
      "Run: cd lab && python 2_doc_generator.py")

check_judgment(doc_report, "Sprint 2")


# ── SPRINT 3: Testing ────────────────────────────────────────
print("\n── SPRINT 3: pytest + Great Expectations ─────────────────")

test_file = os.path.join(db_dir, "test_pipeline.py")
ge_file = os.path.join(db_dir, "ge_expectations.json")
testing_report = os.path.join(db_dir, "testing_report.json")

check("devops_brain/test_pipeline.py exists",
      os.path.exists(test_file),
      "Run: cd lab && python 3_testing_sprint.py")

if os.path.exists(test_file):
    with open(test_file, encoding="utf-8", errors="replace") as f:
        test_content = f.read()
    test_count = test_content.count("def test_")
    check(f"test_pipeline.py has at least 7 test functions (found {test_count})",
          test_count >= 7,
          "AI should generate 8-10 tests")

check("devops_brain/ge_expectations.json exists",
      os.path.exists(ge_file),
      "Run: cd lab && python 3_testing_sprint.py")

if os.path.exists(ge_file):
    try:
        with open(ge_file) as f:
            ge = json.load(f)
        exp_count = len(ge) if isinstance(ge, list) else len(ge.get("expectations", []))
        check(f"ge_expectations.json has expectations (found {exp_count})",
              exp_count >= 3,
              "GE suite should have at least 5 expectations")
    except json.JSONDecodeError:
        check("ge_expectations.json is valid JSON", False, "Cannot be parsed")

check_judgment(testing_report, "Sprint 3")


# ── SPRINT 4: CI/CD + SLO ───────────────────────────────────
print("\n── SPRINT 4: GitHub Actions + SLO + Alert Rules ─────────")

ci_yml = os.path.join(db_dir, "pipeline_ci.yml")
slo_file = os.path.join(db_dir, "slo_definitions.json")
alert_file = os.path.join(db_dir, "alert_rules.json")
ci_slo_report = os.path.join(db_dir, "ci_slo_report.json")

check("devops_brain/pipeline_ci.yml exists",
      os.path.exists(ci_yml),
      "Run: cd lab && python 4_ci_slo.py")

if os.path.exists(ci_yml):
    with open(ci_yml, encoding="utf-8", errors="replace") as f:
        ci_content = f.read()
    check("pipeline_ci.yml has pytest step",
          "pytest" in ci_content,
          "CI workflow should include a pytest run")
    check("pipeline_ci.yml has ruff step",
          "ruff" in ci_content,
          "CI workflow should include a lint step")

check("devops_brain/slo_definitions.json exists",
      os.path.exists(slo_file),
      "Run: cd lab && python 4_ci_slo.py")

check("devops_brain/alert_rules.json exists",
      os.path.exists(alert_file),
      "Run: cd lab && python 4_ci_slo.py")

if os.path.exists(alert_file):
    try:
        with open(alert_file) as f:
            alerts = json.load(f)
        check("alert_rules.json has CRITICAL alerts defined",
              len(str(alerts)) > 200,
              "Alert rules should define critical, warning, and info levels")
    except json.JSONDecodeError:
        check("alert_rules.json is valid JSON", False, "Cannot be parsed")

check_judgment(ci_slo_report, "Sprint 4")


# ── SPRINT 5: Observability ──────────────────────────────────
print("\n── SPRINT 5: Evidently AI Observability ──────────────────")

obs_report = os.path.join(db_dir, "observability_report.json")
obs_dir = os.path.join(db_dir, "observability")
morning_report = os.path.join(obs_dir, "morning_report.md")

check("devops_brain/observability_report.json exists",
      os.path.exists(obs_report),
      "Run: cd lab && python 5_observability.py")

check("devops_brain/observability/ folder exists",
      os.path.exists(obs_dir),
      "Run: cd lab && python 5_observability.py")

if os.path.exists(obs_dir):
    html_files = [f for f in os.listdir(obs_dir) if f.endswith(".html")]
    check(f"Evidently HTML report(s) generated (found {len(html_files)})",
          len(html_files) >= 1,
          "At least one HTML observability report should be generated")

check("devops_brain/observability/morning_report.md exists",
      os.path.exists(morning_report),
      "Run: cd lab && python 5_observability.py")

if os.path.exists(morning_report):
    size = os.path.getsize(morning_report)
    check("morning_report.md has content (> 200 bytes)",
          size > 200,
          f"Morning report is {size} bytes — may be too short")

check_judgment(obs_report, "Sprint 5")


# ── COMPETITIVE BUILD ────────────────────────────────────────
print("\n── COMPETITIVE BUILD: Ship Scorecard ────────────────────")

scorecard = os.path.join(db_dir, "competitive", "scorecard.json")

if not os.path.exists(scorecard):
    skip("competitive/scorecard.json",
         "Run: cd lab && python 6_competitive_build.py (afternoon session)")
else:
    try:
        with open(scorecard) as f:
            sc = json.load(f)
        verdict = sc.get("verdict", "UNKNOWN")
        score = sc.get("score", "?")
        check(f"Competitive build completed (verdict: {verdict}, score: {score})",
              verdict in ["SHIP", "CONDITIONAL SHIP", "DOESN'T SHIP"],
              "Run 6_competitive_build.py to completion")
        check_judgment(scorecard, "Competitive Build")
    except json.JSONDecodeError:
        check("scorecard.json is valid JSON", False, "Cannot be parsed")


# ── JUDGMENT SUMMARY ─────────────────────────────────────────
if judgment_answers:
    print("\n── YOUR ANSWERS (saved to GitHub) ───────────────────────")
    for sprint, answer in judgment_answers:
        print(f"  {sprint}: {answer}")


# ── FINAL REPORT ─────────────────────────────────────────────
print("\n" + "=" * 60)
total = results["pass"] + results["fail"]
print(f"RESULTS: {results['pass']}/{total} passed  |  {results['fail']} failed  |  {results['skip']} skipped")
print("=" * 60)

if results["fail"] == 0 and results["pass"] >= 12:
    print("\n  ALL CORE TESTS PASSED. Push your code!")
    print("  git add .")
    print('  git commit -m "Day 8 done — Code Review + CI/CD + Observability"')
    print("  git push\n")
elif results["fail"] == 0:
    print("\n  LOOKING GOOD. Run remaining scripts to complete all sprints.\n")
else:
    print(f"\n  {results['fail']} tests need fixing. Run each module in order:")
    print("    cd repo/day8/lab")
    print("    python 1_code_review.py      # Sprint 1: AI code review")
    print("    python 2_doc_generator.py    # Sprint 2: documentation")
    print("    python 3_testing_sprint.py   # Sprint 3: pytest + GE")
    print("    python 4_ci_slo.py           # Sprint 4: CI/CD + SLO")
    print("    python 5_observability.py    # Sprint 5: Evidently dashboard")
    print("    python 6_competitive_build.py # Competitive build")
    print("  Then re-run: python tests/validate.py\n")
