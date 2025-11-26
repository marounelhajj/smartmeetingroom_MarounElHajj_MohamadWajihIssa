"""
Unit tests for Bookings Service.
"""

import datetime
import json
import jwt
import pytest

from app import app, db, Booking


@pytest.fixture
def client():
    """Configure test client with in-memory DB."""
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()


def _token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


@pytest.fixture
def user_token():
    return _token(1, "alice", "regular_user")


@pytest.fixture
def admin_token():
    return _token(99, "admin", "admin")


def _future_range(hours_from_now: int = 1, duration_hours: int = 1):
    start = datetime.datetime.utcnow() + datetime.timedelta(hours=hours_from_now)
    end = start + datetime.timedelta(hours=duration_hours)
    return start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["service"] == "bookings"


def test_create_booking_success(client, user_token):
    start, end = _future_range(2, 1)
    resp = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 10, "start_time": start, "end_time": end, "room_name": "A"},
    )
    assert resp.status_code == 201
    payload = json.loads(resp.data)
    assert payload["booking"]["room_id"] == 10
    assert payload["booking"]["status"] == "booked"


def test_prevent_overlap(client, user_token):
    start, end = _future_range(3, 1)
    # First booking
    client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 22, "start_time": start, "end_time": end},
    )

    # Conflicting booking
    resp = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 22, "start_time": start, "end_time": end},
    )
    assert resp.status_code == 409


def test_list_scopes(client, user_token, admin_token):
    start, end = _future_range(4, 1)
    other_start, other_end = _future_range(6, 1)
    # Create two bookings under different users
    client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 1, "start_time": start, "end_time": end},
    )
    admin_book = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"room_id": 2, "start_time": other_start, "end_time": other_end},
    )
    admin_book_id = json.loads(admin_book.data)["booking"]["id"]

    # Regular user sees only own
    resp_user = client.get(
        "/api/bookings", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert resp_user.status_code == 200
    assert json.loads(resp_user.data)["count"] == 1

    # Admin sees all
    resp_admin = client.get(
        "/api/bookings", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp_admin.status_code == 200
    assert json.loads(resp_admin.data)["count"] == 2

    # Admin can see history for user 99
    history = client.get(
        "/api/bookings/history/99", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert history.status_code == 200
    assert json.loads(history.data)["bookings"][0]["id"] == admin_book_id


def test_update_booking(client, user_token):
    start, end = _future_range(8, 1)
    resp = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 5, "start_time": start, "end_time": end},
    )
    booking_id = json.loads(resp.data)["booking"]["id"]

    new_start, new_end = _future_range(10, 2)
    update_resp = client.put(
        f"/api/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"start_time": new_start, "end_time": new_end, "room_id": 6},
    )
    assert update_resp.status_code == 200
    data = json.loads(update_resp.data)
    assert data["booking"]["room_id"] == 6
    assert data["booking"]["start_time"].startswith(new_start[:16])


def test_cancel_booking(client, user_token):
    start, end = _future_range(12, 1)
    resp = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 7, "start_time": start, "end_time": end},
    )
    booking_id = json.loads(resp.data)["booking"]["id"]

    cancel_resp = client.delete(
        f"/api/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert cancel_resp.status_code == 200
    data = json.loads(cancel_resp.data)
    assert data["booking"]["status"] == "cancelled"


def test_check_availability(client, user_token):
    start, end = _future_range(15, 1)
    client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 50, "start_time": start, "end_time": end},
    )

    resp = client.get(
        f"/api/bookings/check?room_id=50&start_time={start}&end_time={end}"
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["available"] is False


def test_forbid_updating_other_users_booking(client, user_token, admin_token):
    start, end = _future_range(18, 1)
    resp = client.post(
        "/api/bookings",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 12, "start_time": start, "end_time": end},
    )
    booking_id = json.loads(resp.data)["booking"]["id"]

    stranger_token = _token(2, "bob", "regular_user")
    update_resp = client.put(
        f"/api/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
        json={"room_id": 99},
    )
    assert update_resp.status_code == 403

    # Admin can update it
    admin_resp = client.put(
        f"/api/bookings/{booking_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"room_id": 99},
    )
    assert admin_resp.status_code == 200
