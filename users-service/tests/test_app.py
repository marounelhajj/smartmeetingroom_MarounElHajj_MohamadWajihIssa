"""
Unit tests for Users Service.
Run with:
    pytest tests/test_app.py -v --cov=users-service/app.py --cov-report=html
"""
import os
import sys

# Make sure the parent folder (where app.py lives) is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import pytest
from werkzeug.security import generate_password_hash

from app import app, db, User


@pytest.fixture()
def client():
    """Create Flask test client with in-memory SQLite DB."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.test_client() as client:
        with app.app_context():
            db.create_all()

            # Seed one admin user
            admin = User(
                name="Admin",
                username="admin",
                password=generate_password_hash("admin123"),
                email="admin@test.com",
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()

        yield client

        with app.app_context():
            db.drop_all()


@pytest.fixture()
def admin_token(client):
    """Return JWT token for seeded admin user."""
    response = client.post(
        "/api/users/login",
        data=json.dumps({"username": "admin", "password": "admin123"}),
        content_type="application/json",
    )
    data = json.loads(response.data)
    return data["token"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "healthy"
    assert data["service"] == "users"


def test_register_success(client):
    payload = {
        "name": "John Doe",
        "username": "johndoe",
        "password": "secret123",
        "email": "john@example.com",
        "role": "regular_user",
    }
    resp = client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["user"]["username"] == "johndoe"


def test_register_missing_field(client):
    payload = {
        "name": "John Doe",
        "username": "johndoe",
        # missing password & email
    }
    resp = client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_register_invalid_email(client):
    payload = {
        "name": "John Doe",
        "username": "johndoe",
        "password": "secret123",
        "email": "bad-email",
    }
    resp = client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_register_weak_password(client):
    payload = {
        "name": "John Doe",
        "username": "johndoe",
        "password": "123",
        "email": "john@example.com",
    }
    resp = client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 400


def test_register_duplicate_username(client):
    payload = {
        "name": "User1",
        "username": "duplicate",
        "password": "secret123",
        "email": "u1@example.com",
    }
    client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )

    payload["email"] = "u2@example.com"
    resp = client.post(
        "/api/users/register",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert resp.status_code == 409


def test_login_success(client):
    # admin user comes from fixture
    resp = client.post(
        "/api/users/login",
        data=json.dumps({"username": "admin", "password": "admin123"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "token" in data


def test_login_fail(client):
    resp = client.post(
        "/api/users/login",
        data=json.dumps({"username": "unknown", "password": "nopass"}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_get_all_users_unauthorized(client):
    resp = client.get("/api/users")
    assert resp.status_code == 401


def test_get_all_users_as_admin(client, admin_token):
    resp = client.get(
        "/api/users", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert "users" in data
    assert data["count"] >= 1


def test_update_user_profile(client, admin_token):
    payload = {"name": "New Admin Name", "email": "newadmin@test.com"}
    resp = client.put(
        "/api/users/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["user"]["name"] == "New Admin Name"
    assert data["user"]["email"] == "newadmin@test.com"


def test_delete_user_prevent_self_delete(client, admin_token):
    resp = client.delete(
        "/api/users/admin", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 400


def test_invalid_token_rejected(client):
    resp = client.get(
        "/api/users", headers={"Authorization": "Bearer invalid_token"}
    )
    assert resp.status_code == 401
