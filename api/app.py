from flask import Flask, jsonify
from flask_cors import CORS
from submissions import build_response, ist_now

app = Flask(__name__)
CORS(app)

@app.route('/api/submissions')
def submissions():
    return jsonify(build_response())

@app.route('/api/debug')
def debug():
    import os, csv
    token = os.environ.get('GITHUB_TOKEN', '')
    csv_path = os.path.join(os.path.dirname(__file__), 'students.csv')
    csv_exists = os.path.exists(csv_path)
    csv_rows = []
    if csv_exists:
        with open(csv_path, newline='', encoding='utf-8') as f:
            csv_rows = list(csv.DictReader(f))
    return jsonify({
        "GITHUB_TOKEN_set": bool(token),
        "GITHUB_TOKEN_length": len(token),
        "TRAINER_REPO": os.environ.get('TRAINER_REPO', 'Anilmidna/sigma-genai-de'),
        "csv_exists": csv_exists,
        "csv_row_count": len(csv_rows),
    })

@app.route('/')
def index():
    with open(os.path.join(os.path.dirname(__file__), '../dashboard/index.html')) as f:
        return f.read(), 200, {'Content-Type': 'text/html'}

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
