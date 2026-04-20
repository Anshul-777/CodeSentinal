"""
CodeSentinel Test Application
===============================
This Flask app intentionally contains real vulnerability patterns.
Push to your GitHub account and connect to CodeSentinel to test all 5 agents.

DO NOT deploy this in production.
"""
from flask import Flask, request, jsonify, render_template_string, session
import sqlite3
import os
import pickle
import hashlib
import random
import subprocess

app = Flask(__name__)

# VULNERABILITY 1: Hardcoded secret key [Agent 1 — STATIC-SECRET, SECRET-jwt_secret]
SECRET_KEY = "mysupersecretkey123"
app.config["SECRET_KEY"] = SECRET_KEY

# VULNERABILITY 2: Debug mode left enabled [Agent 1 — STATIC-CONFIG-001]
app.config["DEBUG"] = True

DATABASE = os.path.join(os.path.dirname(__file__), "users.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()


# VULNERABILITY 3: SQL Injection [Agent 1 — BANDIT-B608, Agent 3 — business logic]
@app.route("/users/search")
def search_users():
    """Search users by username — SQL injection possible."""
    query = request.args.get("q", "")
    conn = get_db()
    # VULN: user input directly interpolated into SQL string
    sql = f"SELECT id, username, email FROM users WHERE username = '{query}'"
    cursor = conn.cursor()
    cursor.execute(sql)
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(results)


# VULNERABILITY 4: OS Command Injection [Agent 1 — BANDIT-B602]
@app.route("/diagnostics/ping")
def ping():
    """Ping a host — command injection via shell=True."""
    host = request.args.get("host", "127.0.0.1")
    # VULN: user input passed to shell command without sanitization
    result = subprocess.check_output(f"ping -c 1 {host}", shell=True, text=True)
    return jsonify({"output": result})


# VULNERABILITY 5: Insecure Deserialization [Agent 1 — BANDIT-B301]
@app.route("/session/restore", methods=["POST"])
def restore_session():
    """Restore a user session from serialized data."""
    session_bytes = request.get_data()
    # VULN: pickle.loads on untrusted user input — arbitrary code execution
    user_data = pickle.loads(session_bytes)
    return jsonify({"restored": str(user_data)})


# VULNERABILITY 6: Weak hash algorithm for passwords [Agent 1 — BANDIT-B303]
@app.route("/auth/register", methods=["POST"])
def register():
    """Register a user — MD5 password hashing."""
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    # VULN: MD5 is broken for password hashing — use bcrypt/argon2
    hashed = hashlib.md5(password.encode()).hexdigest()
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        return jsonify({"registered": True})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username taken"}), 400
    finally:
        conn.close()


# VULNERABILITY 7: Non-cryptographic random for token [Agent 1 — STATIC-CRYPTO-002]
@app.route("/auth/forgot-password")
def forgot_password():
    """Generate password reset token — non-cryptographic random."""
    email = request.args.get("email", "")
    # VULN: random.random() is predictable — use secrets.token_urlsafe()
    reset_token = str(random.random())[2:18]
    return jsonify({"reset_token": reset_token, "email": email})


# VULNERABILITY 8: Server-Side Template Injection [Agent 1 — STATIC-SSTI-001]
@app.route("/welcome")
def welcome():
    """Welcome page — SSTI via render_template_string with user input."""
    name = request.args.get("name", "World")
    # VULN: user input in template string — allows {{config}} leakage or RCE
    template = f"<h1>Welcome, {name}!</h1><p>Our secure platform awaits you.</p>"
    return render_template_string(template)


# VULNERABILITY 9: Missing authentication on admin endpoint [Agent 3 — business logic]
@app.route("/admin/users", methods=["DELETE"])
def delete_all_users():
    """Destroy all users — no authentication check."""
    # VULN: Destructive admin operation with zero auth enforcement
    conn = get_db()
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    return jsonify({"deleted": True, "message": "All users removed"})


# VULNERABILITY 10: IDOR — Missing ownership check [Agent 3 — business logic]  
@app.route("/users/<int:user_id>/orders")
def get_user_orders(user_id: int):
    """Get orders for a user — no ownership verification."""
    # VULN: Any authenticated user can read any other user's orders
    # Missing: check that request.user.id == user_id
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE user_id = ?", (user_id,))
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({"orders": orders, "user_id": user_id})


# VULNERABILITY 11: Negative price / financial logic error [Agent 3 — business logic]
@app.route("/orders/create", methods=["POST"])
def create_order():
    """Create an order — no validation of amount."""
    data = request.get_json()
    amount = data.get("amount", 0)
    user_id = data.get("user_id", 1)
    # VULN: negative amount allows store credit manipulation / financial fraud
    # Missing: if amount <= 0: return error
    conn = get_db()
    conn.execute("INSERT INTO orders (user_id, amount, status) VALUES (?, ?, 'pending')",
                 (user_id, amount))
    conn.commit()
    conn.close()
    return jsonify({"created": True, "amount": amount})


# VULNERABILITY 12: TLS verification disabled [Agent 1 — STATIC-TLS-001]
def fetch_payment_gateway(url: str) -> dict:
    """Fetch from payment gateway — SSL verification disabled."""
    import requests
    # VULN: verify=False disables TLS certificate validation — MITM attacks possible
    response = requests.get(url, verify=False, timeout=10)
    return response.json()


# VULNERABILITY 13: Debug endpoint exposing stack traces [Agent 3 — business logic]
@app.route("/debug/exception")
def trigger_exception():
    """Debug route — exposes full stack trace in response."""
    try:
        # Intentional error to trigger debug output
        result = 1 / 0
    except ZeroDivisionError as e:
        import traceback
        # VULN: exposing full stack trace with internal paths to clients
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc(),
            "config": str(app.config),  # CRITICAL: exposes SECRET_KEY
        }), 500


if __name__ == "__main__":
    init_db()
    # VULN: debug=True and host=0.0.0.0 exposes Werkzeug debugger to the network
    app.run(debug=True, host="0.0.0.0", port=5000)
