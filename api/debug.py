from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error


def github_test_call(token, trainer_repo):
    """Make one real, authenticated call to GitHub and report exactly what happened.
    This is the check that was missing — it's what actually tells us whether the
    token/repo combo works, instead of just confirming the env vars are *set*."""
    if not token:
        return {"attempted": False, "reason": "GITHUB_TOKEN is not set"}

    url = f'https://api.github.com/repos/{trainer_repo}'
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'token {token}')
    req.add_header('User-Agent', 'sigma-dashboard')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            return {
                "attempted": True,
                "status": resp.status,
                "ok": True,
                "repo_full_name": body.get('full_name'),
                "forks_count_reported_by_github": body.get('forks_count'),
                "rate_limit_remaining": resp.headers.get('X-RateLimit-Remaining'),
            }
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode('utf-8'))
        except Exception:
            err_body = {}
        return {
            "attempted": True,
            "status": e.code,
            "ok": False,
            "github_message": err_body.get('message'),
            "hint": (
                "401 = the token is invalid, expired, or was revoked — generate a new "
                "Personal Access Token (classic, 'repo' or 'public_repo' scope) under the "
                "askanilkumar account and update GITHUB_TOKEN in Vercel."
                if e.code == 401 else
                "403 = usually a rate limit or the token lacks access to this repo."
                if e.code == 403 else
                "404 = the token can authenticate but this repo/owner is wrong or private to it."
                if e.code == 404 else None
            ),
        }
    except Exception as e:
        return {"attempted": True, "ok": False, "error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.environ.get('GITHUB_TOKEN', '')
        trainer_repo = os.environ.get('TRAINER_REPO', 'NOT SET')

        import csv
        csv_path = os.path.join(os.path.dirname(__file__), 'students.csv')
        csv_exists = os.path.exists(csv_path)
        csv_rows = []
        if csv_exists:
            with open(csv_path, newline='', encoding='utf-8') as f:
                csv_rows = list(csv.DictReader(f))

        data = {
            "GITHUB_TOKEN_set": bool(token),
            "GITHUB_TOKEN_length": len(token),
            "TRAINER_REPO": trainer_repo,
            "csv_path": csv_path,
            "csv_exists": csv_exists,
            "csv_row_count": len(csv_rows),
            "csv_first_3_rows": csv_rows[:3],
            "github_live_test": github_test_call(token, trainer_repo) if trainer_repo != 'NOT SET' else {"attempted": False, "reason": "TRAINER_REPO not set"},
        }
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
