from http.server import BaseHTTPRequestHandler
import json
import os
import csv
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

# For days that have a "master" tier, list the core files required for "complete"
# and the extra files required for "master". Other days have no master tier.
MASTER_TIER = {
    7: {
        "core": [
            "pipeline_brain/generated_pipeline.py",
            "pipeline_brain/sigma_dag.py",
            "pipeline_brain/hardened_pipeline.py",
        ],
        "extra": [
            "pipeline_brain/schema_drift_report.json",
            "pipeline_brain/code_review.json",
        ],
    },
    8: {
        "core": [
            "devops_brain/code_review_report.json",
            "devops_brain/doc_report.json",
            "devops_brain/testing_report.json",
            "devops_brain/ci_slo_report.json",
        ],
        "extra": [
            "devops_brain/observability_report.json",
        ],
    },
}

EXPECTED_FILES = {
    6: {
        "review_report.json": "SQL Review",
        "nl2sql_audit.json": "NL2SQL",
        "sigma_dbt/models/staging/stg_transactions.sql": "dbt",
    },
    7: {
        "pipeline_brain/generated_pipeline.py": "Pipeline",
        "pipeline_brain/sigma_dag.py": "DAG",
        "pipeline_brain/hardened_pipeline.py": "Hardened",
        "pipeline_brain/schema_drift_report.json": "SchemaDrift",
        "pipeline_brain/code_review.json": "Review",
    },
    8: {
        "devops_brain/code_review_report.json":   "Review",
        "devops_brain/doc_report.json":           "Docs",
        "devops_brain/testing_report.json":       "Tests",
        "devops_brain/ci_slo_report.json":        "CI/SLO",
        "devops_brain/observability_report.json": "Observe",
    },
}


def load_students():
    """Load github_username -> real_name mapping from students.csv."""
    mapping = {}
    csv_path = os.path.join(os.path.dirname(__file__), 'students.csv')
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                username = row.get('github_username', '').strip()
                name = row.get('real_name', '').strip()
                if username:
                    mapping[username] = name if name else username
    except FileNotFoundError:
        pass  # gracefully return empty mapping; caller falls back to github username
    return mapping


def github_get(url, token):
    """Make an authenticated GET request to the GitHub API. Returns (status_code, body_dict_or_None)."""
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {token}')
    req.add_header('User-Agent', 'sigma-dashboard')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def get_all_forks(owner, repo, token):
    """Fetch all forks with pagination."""
    forks = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{owner}/{repo}/forks?per_page=100&page={page}'
        status, body = github_get(url, token)
        if status != 200 or not body:
            break
        if not body:
            break
        forks.extend(body)
        if len(body) < 100:
            break
        page += 1
    return forks


def get_fork_file_tree(fork_owner, fork_repo, token):
    """Fetch all file paths in the fork's default branch in one API call.
    Returns a set of lowercase paths, or None if the call failed."""
    url = f'https://api.github.com/repos/{fork_owner}/{fork_repo}/git/trees/HEAD?recursive=1'
    status, body = github_get(url, token)
    if status != 200 or not body or 'tree' not in body:
        return None
    return {item['path'].lower() for item in body['tree'] if item.get('type') == 'blob'}


def compute_status(files_found, day_num=None):
    """Convert a dict of {filename: bool} to a status string."""
    if not files_found:
        return "missing"
    values = list(files_found.values())
    if not any(values):
        return "missing"

    # Check master tier first (all 5 files present)
    if day_num in MASTER_TIER:
        tier = MASTER_TIER[day_num]
        core_done  = all(files_found.get(f, False) for f in tier["core"])
        extra_done = all(files_found.get(f, False) for f in tier["extra"])
        if core_done and extra_done:
            return "master"
        if core_done:
            return "complete"
        if any(values):
            return "partial"
        return "missing"

    if all(values):
        return "complete"
    return "partial"


def ist_now():
    """Return current time as a formatted IST string."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return now.strftime('%Y-%m-%d %H:%M IST')


def build_response():
    """Core logic: hit GitHub API and return the dashboard data dict."""
    token = os.environ.get('GITHUB_TOKEN', '')
    trainer_repo = os.environ.get('TRAINER_REPO', 'Anilmidna/sigma-genai-de')

    if not token:
        return {
            "error": "GITHUB_TOKEN environment variable is not set.",
            "days": [],
            "students": [],
            "refreshed_at": ist_now(),
        }

    parts = trainer_repo.split('/')
    if len(parts) != 2:
        return {
            "error": f"TRAINER_REPO must be in 'owner/repo' format, got: {trainer_repo}",
            "days": [],
            "students": [],
            "refreshed_at": ist_now(),
        }

    owner, repo = parts[0], parts[1]
    name_map = load_students()
    days = sorted(EXPECTED_FILES.keys())

    forks = get_all_forks(owner, repo, token)

    # Build a set of known github usernames (case-insensitive lookup)
    known_usernames_lower = {u.lower(): u for u in name_map.keys()}

    students_data = []
    for fork in forks:
        fork_owner = fork.get('owner', {}).get('login', '')
        fork_repo = fork.get('name', '')
        if not fork_owner or not fork_repo:
            continue

        # Map to real name (case-insensitive match against students.csv)
        canonical = known_usernames_lower.get(fork_owner.lower(), fork_owner)
        real_name = name_map.get(canonical, fork_owner)

        # One API call gets ALL files in the fork — replaces N*files individual calls
        tree = get_fork_file_tree(fork_owner, fork_repo, token)

        student_entry = {
            "github": fork_owner,
            "real_name": real_name,
        }

        for day_num in days:
            file_specs = EXPECTED_FILES[day_num]
            files_found = {}
            for rel_path, label in file_specs.items():
                full_path = f'day{day_num}/lab/{rel_path}'.lower()
                if tree is None:
                    exists = False
                else:
                    exists = full_path in tree
                files_found[rel_path] = exists

            student_entry[f'day{day_num}'] = {
                "status": compute_status(files_found, day_num),
                "files": files_found,
            }

        students_data.append(student_entry)

    # Sort: complete first, then partial, then missing; ties broken by name
    rank = {"master": 0, "complete": 1, "partial": 2, "missing": 3}

    def sort_key(s):
        total_complete = sum(
            1 for d in days
            if s.get(f'day{d}', {}).get('status') == 'complete'
        )
        worst = max(
            rank.get(s.get(f'day{d}', {}).get('status', 'missing'), 2)
            for d in days
        ) if days else 2
        return (worst, -total_complete, s.get('real_name', '').lower())

    students_data.sort(key=sort_key)

    return {
        "days": days,
        "students": students_data,
        "refreshed_at": ist_now(),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        data = build_response()
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default stderr logging in Vercel
