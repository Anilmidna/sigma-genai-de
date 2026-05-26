from http.server import BaseHTTPRequestHandler
import json
import os


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.environ.get('GITHUB_TOKEN', '')
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
            "TRAINER_REPO": os.environ.get('TRAINER_REPO', 'NOT SET'),
            "csv_path": csv_path,
            "csv_exists": csv_exists,
            "csv_row_count": len(csv_rows),
            "csv_first_3_rows": csv_rows[:3],
        }
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
