"""
CodeSentinel Test Repository
-------------------------------
This is the source code you push to YOUR GitHub account to test CodeSentinel.
It intentionally contains real vulnerability patterns that each agent detects.

Push instructions:
  git init codesentinel-test-app
  cd codesentinel-test-app
  # copy these files in
  git add .
  git commit -m "Initial commit"
  git remote add origin https://github.com/YOUR_USERNAME/codesentinel-test-app.git
  git push -u origin main

Then connect this repo to CodeSentinel and open a pull request to trigger a scan.
"""

# ── app.py — Main Flask application with real vulnerability patterns ──────────
APP_PY = '''
from flask import Flask, request, jsonify, render_template_string
import sqlite3
import os
import pickle
import hashlib
import random
import yaml
import subprocess

app = Flask(__name__)

# VULNERABILITY: Hardcoded JWT secret (will be caught by Agent 1 + Secret Scanner)
SECRET_KEY = "mysupersecretkey123"
app.config["SECRET_KEY"] = SECRET_KEY

# VULNERABILITY: Debug mode enabled (Agent 1 - STATIC-CONFIG-001)
app.config["DEBUG"] = True

DATABASE = "users.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

# VULNERABILITY: SQL Injection (Agent 1 - BANDIT-B608 + Agent 3 business logic)
@app.route("/users/search")
def search_users():
    query = request.args.get("q", "")
    conn = get_db()
    cursor = conn.cursor()
    # VULN: direct string interpolation in SQL
    sql = f"SELECT * FROM users WHERE username = \'{query}\'"
    cursor.execute(sql)
    results = cursor.fetchall()
    return jsonify(results)

# VULNERABILITY: OS Command Injection (Agent 1 - BANDIT-B602)
@app.route("/ping")
def ping():
    host = request.args.get("host", "localhost")
    # VULN: user input directly in shell command
    result = subprocess.check_output(f"ping -c 1 {host}", shell=True)
    return result

# VULNERABILITY: Insecure deserialization (Agent 1 - BANDIT-B301)
@app.route("/load-session", methods=["POST"])
def load_session():
    session_data = request.get_data()
    # VULN: unpickling arbitrary user data
    user_session = pickle.loads(session_data)
    return jsonify({"user": str(user_session)})

# VULNERABILITY: yaml.load without Loader (Agent 1 - BANDIT-B506)
@app.route("/load-config", methods=["POST"])
def load_config():
    config_data = request.get_data(as_text=True)
    # VULN: yaml.load() without Loader allows code execution
    config = yaml.load(config_data)
    return jsonify(config)

# VULNERABILITY: Weak hash algorithm (Agent 1 - BANDIT-B303)
@app.route("/hash-password", methods=["POST"])
def hash_password_endpoint():
    password = request.json.get("password", "")
    # VULN: MD5 is a broken hash algorithm for passwords
    hashed = hashlib.md5(password.encode()).hexdigest()
    return jsonify({"hash": hashed})

# VULNERABILITY: Non-cryptographic random for token generation (Agent 1)
@app.route("/generate-token")
def generate_token():
    # VULN: random.random() is not cryptographically secure
    token = str(random.random())[2:]
    return jsonify({"token": token})

# VULNERABILITY: Server-Side Template Injection (Agent 1 - STATIC-SSTI-001)
@app.route("/greet")
def greet():
    name = request.args.get("name", "World")
    # VULN: user input directly in template string
    template = f"<h1>Hello, {name}!</h1>"
    return render_template_string(template)

# VULNERABILITY: Missing authentication on admin endpoint (Agent 3 business logic)
@app.route("/admin/users", methods=["DELETE"])
def delete_all_users():
    # VULN: No authentication check before destructive operation
    conn = get_db()
    conn.execute("DELETE FROM users")
    conn.commit()
    return jsonify({"deleted": True})

# VULNERABILITY: IDOR - no ownership check (Agent 3)
@app.route("/user/<int:user_id>/profile")
def get_user_profile(user_id):
    # VULN: Returns any user's data without checking if requester owns it
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    return jsonify({"user": user})

# VULNERABILITY: TLS verification disabled (Agent 1 - STATIC-TLS-001)
import requests as req_lib
def fetch_external_data(url):
    # VULN: SSL verification disabled
    response = req_lib.get(url, verify=False)
    return response.json()

if __name__ == "__main__":
    app.run(debug=True)
'''

# ── requirements.txt — with deliberately vulnerable packages ─────────────────
REQUIREMENTS_TXT = '''
Flask==2.0.1
requests==2.27.0
PyYAML==5.3.1
Werkzeug==2.0.1
Jinja2==2.11.3
SQLAlchemy==1.4.15
cryptography==3.3.1
paramiko==2.7.2
Pillow==8.1.0
'''
# NOTE: The versions above are intentionally old and contain real CVEs:
# - Flask 2.0.1: CVE-2023-30861 (session cookie not secure by default)
# - requests 2.27.0: CVE-2023-32681 (Proxy-Authorization leak)
# - PyYAML 5.3.1: CVE-2020-14343 (full schema yaml.load() RCE)
# - Werkzeug 2.0.1: CVE-2023-46136 (DoS via multipart)
# - Jinja2 2.11.3: CVE-2020-28493 (ReDoS in urlize)
# - paramiko 2.7.2: CVE-2022-24302 (race condition private key)
# - Pillow 8.1.0: CVE-2021-25289 (buffer overflow)
# These are real OSV.dev entries — Agent 2 will find them via live API.

# ── test_app.py — pytest tests for the sandbox to run ────────────────────────
TEST_APP_PY = '''
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_search_users_basic(client):
    resp = client.get("/users/search?q=alice")
    assert resp.status_code in (200, 500)  # may fail if no DB

def test_generate_token(client):
    resp = client.get("/generate-token")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "token" in data

def test_greet(client):
    resp = client.get("/greet?name=World")
    assert resp.status_code == 200
'''

# ── README.md ─────────────────────────────────────────────────────────────────
README_MD = '''
# CodeSentinel Test Application

This repository intentionally contains security vulnerabilities for testing
the CodeSentinel security scanning platform.

## DO NOT use this code in production.

## Vulnerabilities Present:
- SQL Injection (agent_type: static, rule: BANDIT-B608)
- OS Command Injection (agent_type: static, rule: BANDIT-B602)
- Insecure Deserialization (agent_type: static, rule: BANDIT-B301)
- Unsafe YAML Loading (agent_type: static, rule: BANDIT-B506)
- Weak MD5 Password Hashing (agent_type: static, rule: BANDIT-B303)
- Non-cryptographic Random (agent_type: static, rule: STATIC-CRYPTO-002)
- Server-Side Template Injection (agent_type: static)
- Hardcoded Secret Key (agent_type: secret)
- Missing Authentication on Admin Endpoint (agent_type: business_logic)
- IDOR - Missing Ownership Check (agent_type: business_logic)
- TLS Verification Disabled (agent_type: static)
- Multiple known CVEs in requirements.txt (agent_type: dependency)

## How to Use with CodeSentinel:
1. Push this repo to your GitHub account
2. Install the CodeSentinel GitHub App
3. Connect this repository in the CodeSentinel dashboard
4. Create a pull request from any branch to main
5. Watch the 5-agent pipeline run on your scan dashboard
'''

if __name__ == "__main__":
    import os
    os.makedirs("codesentinel-test-app", exist_ok=True)
    with open("codesentinel-test-app/app.py", "w") as f:
        f.write(APP_PY.strip())
    with open("codesentinel-test-app/requirements.txt", "w") as f:
        f.write(REQUIREMENTS_TXT.strip())
    with open("codesentinel-test-app/test_app.py", "w") as f:
        f.write(TEST_APP_PY.strip())
    with open("codesentinel-test-app/README.md", "w") as f:
        f.write(README_MD.strip())
    print("Test repository files generated in ./codesentinel-test-app/")
    print("Push to your GitHub account and connect to CodeSentinel.")
