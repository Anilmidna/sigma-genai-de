"""
Submission Checker — Run this to see who completed today's lab.
Usage: python check_submissions.py <day_number>
Example: python check_submissions.py 6

Requires: gh CLI authenticated (gh auth login)
"""

import subprocess
import json
import sys
from datetime import datetime

TRAINER_REPO = "Anilmidna/sigma-genai-de"

# Expected output files per day (add new days as you go)
EXPECTED_FILES = {
    6: {
        "review_report.json": "Module 1: 1_sql_review.py",
        "nl2sql_audit.json": "Module 2: 2_nl2sql_pipeline.py",
        "sigma_dbt/models/staging/stg_transactions.sql": "Module 3: 3_dbt_generator.py",
    },
    7: {
        "pipeline_brain/generated_pipeline.py": "Module 1: 1_spec_to_pipeline.py",
        "pipeline_brain/sigma_dag.py": "Module 2: 2_dag_generator.py",
        "pipeline_brain/hardened_pipeline.py": "Module 3: 3_pipeline_hardening.py",
        "pipeline_brain/code_review.json": "Module 5: 5_code_review.py",
    },
    8: {
        "devops_brain/code_review_report.json": "Review",
        "devops_brain/doc_report.json": "Docs",
        "devops_brain/testing_report.json": "Tests",
        "devops_brain/ci_slo_report.json": "CI/SLO",
        "devops_brain/observability_report.json": "Observe",
        "devops_brain/competitive/scorecard.json": "CompBuild",
    },
    9: {
        "output/soda_lab_success.json": "Soda",
        "output/competitive_scorecard.json": "CompBuild",
        "output/llm_observability_success.json": "LLM-Obs",
        "output/openmetadatalab.json": "OpenMeta",
    },
}

DAY_LAB_FOLDER = {
    9: "labs",
}



def run_gh(args):
    """Run a gh CLI command and return parsed JSON."""
    result = subprocess.run(
        ["gh", "api"] + args,
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return result.stdout.strip()


def get_forks():
    """Get all forks of the trainer repo."""
    forks = run_gh([f"repos/{TRAINER_REPO}/forks", "--paginate", "--jq", "."])
    if not forks:
        print("ERROR: Could not fetch forks. Run: gh auth login")
        sys.exit(1)
    # Handle paginated response (list of lists)
    if isinstance(forks, list) and forks and isinstance(forks[0], list):
        flat = []
        for page in forks:
            flat.extend(page)
        return flat
    return forks if isinstance(forks, list) else []


def check_file_exists(owner, repo_name, filepath):
    """Check if a file exists in a student's fork."""
    result = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo_name}/contents/{filepath}"],
        capture_output=True, text=True
    )
    return result.returncode == 0


def check_submissions(day_num):
    """Check all students' submissions for a given day."""
    if day_num not in EXPECTED_FILES or not EXPECTED_FILES[day_num]:
        print(f"ERROR: No expected files defined for Day {day_num}")
        print(f"Update EXPECTED_FILES dict in this script.")
        sys.exit(1)

    expected = EXPECTED_FILES[day_num]
    lab_folder = DAY_LAB_FOLDER.get(day_num, "lab")
    lab_prefix = f"day{day_num}/{lab_folder}/"

    print(f"\nDAY {day_num} SUBMISSIONS (checked {datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print("─" * 70)

    forks = get_forks()
    if not forks:
        print("No forks found.")
        return

    submitted = 0
    complete = 0
    total = len(forks)

    for fork in forks:
        owner = fork["owner"]["login"]
        repo_name = fork["name"]
        pushed_at = fork.get("pushed_at", "")[:10]

        # Check each expected file
        file_results = {}
        for filename, label in expected.items():
            full_path = lab_prefix + filename
            exists = check_file_exists(owner, repo_name, full_path)
            file_results[filename] = exists

        # Determine status
        found_count = sum(1 for v in file_results.values() if v)
        total_files = len(expected)

        if found_count == 0:
            status = "\033[91m✗\033[0m"
            detail = "not submitted"
        elif found_count == total_files:
            status = "\033[92m✓\033[0m"
            detail = " | ".join(f"{k.split('/')[-1]} ✓" for k in expected.keys())
            complete += 1
            submitted += 1
        else:
            status = "\033[93m~\033[0m"
            parts = []
            for k in expected.keys():
                short = k.split("/")[-1]
                mark = "✓" if file_results[k] else "✗"
                parts.append(f"{short} {mark}")
            detail = " | ".join(parts)
            submitted += 1

        print(f"  {status} {owner:<20} — {detail}")

    print("─" * 70)
    print(f"  TOTAL: {total} | SUBMITTED: {submitted} | COMPLETE: {complete} | MISSING: {total - submitted}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_submissions.py <day_number>")
        print("Example: python check_submissions.py 6")
        sys.exit(1)

    day = int(sys.argv[1])
    check_submissions(day)
