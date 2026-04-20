"""
Test suite for the CodeSentinel test application.
These tests run in the sandbox when Agent 4 (Auto-Fix) validates patches.
"""
import pytest
from app import app, init_db, get_db
import sqlite3
import os


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = ":memory:"
    with app.test_client() as c:
        with app.app_context():
            init_db()
        yield c


def test_welcome_page_renders(client):
    """Basic smoke test — welcome page should return 200."""
    resp = client.get("/welcome?name=CodeSentinel")
    assert resp.status_code == 200


def test_forgot_password_returns_token(client):
    """Forgot password endpoint returns a token."""
    resp = client.get("/forgot-password?email=test@example.com")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reset_token" in data
    assert len(data["reset_token"]) > 0


def test_register_user(client):
    """User registration stores a record."""
    resp = client.post("/auth/register", json={
        "username": "testuser",
        "password": "password123",
    })
    assert resp.status_code == 200


def test_search_users_returns_list(client):
    """User search returns a list."""
    resp = client.get("/users/search?q=nobody")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_order_list_returns_json(client):
    """Order endpoint returns JSON for any user ID."""
    resp = client.get("/users/1/orders")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "orders" in data


def test_create_order_valid_amount(client):
    """Create order with positive amount."""
    resp = client.post("/orders/create", json={
        "user_id": 1,
        "amount": 29.99,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["created"] is True
