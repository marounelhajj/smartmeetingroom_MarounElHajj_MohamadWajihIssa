"""
Unit tests for Rooms Service.
"""
import os
import sys

# Make sure the parent folder (where app.py lives) is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import json
import pytest

from app import app, db, Room


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client
        with app.app_context():
            db.drop_all()


# A fake token payload for tests (no real JWT decoding needed here).
VALID_ADMIN_HEADER = {"Authorization": "Bearer test_admin_token"}
VALID_USER_HEADER = {"Authorization": "Bearer test_user_token"}


def monkey_decode_token(token):
    """Small helper so we bypass real JWT for unit tests."""
    if "admin" in token:
        return {"user_id": 1, "role": "admin"}
    return {"user_id": 2, "role": "regular_user"}


# Patch decode_token in module during tests
@pytest.fixture(autouse=True)
def patch_jwt(monkeypatch):
    from app import decode_token

    monkeypatch.setattr("app.decode_token", monkey_decode_token)
    yield
    monkeypatch.setattr("app.decode_token", decode_token)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_add_room_requires_auth(client):
    payload = {
        "name": "Room A",
        "capacity": 10,
        "equipment": "projector",
        "location": "AUB",
    }
    resp = client.post(
        "/api/rooms",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_add_room_as_admin(client):
    payload = {
        "name": "Room A",
        "capacity": 10,
        "equipment": "projector",
        "location": "AUB",
    }
    resp = client.post(
        "/api/rooms",
        headers=VALID_ADMIN_HEADER,
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["room"]["name"] == "Room A"


def test_list_rooms_filter(client):
    # Seed a few rooms
    with app.app_context():
        r1 = Room(
            name="BigRoom",
            capacity=20,
            equipment="projector,whiteboard",
            location="Beirut",
        )
        r2 = Room(
            name="SmallRoom",
            capacity=4,
            equipment="tv",
            location="Tripoli",
        )
        db.session.add_all([r1, r2])
        db.session.commit()

    resp = client.get("/api/rooms?min_capacity=5")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    # Only BigRoom should match
    assert data["count"] == 1


def test_update_room(client):
    with app.app_context():
        room = Room(
            name="RoomX",
            capacity=5,
            equipment="tv",
            location="AUB",
        )
        db.session.add(room)
        db.session.commit()
        room_id = room.id

    payload = {"capacity": 8}
    resp = client.put(
        f"/api/rooms/{room_id}",
        headers=VALID_ADMIN_HEADER,
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["room"]["capacity"] == 8


def test_delete_room(client):
    with app.app_context():
        room = Room(
            name="TempRoom",
            capacity=3,
            equipment="",
            location="AUB",
        )
        db.session.add(room)
        db.session.commit()
        room_id = room.id

    resp = client.delete(
        f"/api/rooms/{room_id}",
        headers=VALID_ADMIN_HEADER,
    )
    assert resp.status_code == 200
