"""
Unit tests for Reviews Service.
"""

import datetime
import json
import jwt
import pytest

from app import app, db, Review


@pytest.fixture
def client():
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
def moderator_token():
    return _token(10, "mod", "moderator")


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert json.loads(resp.data)["service"] == "reviews"


def test_create_review(client, user_token):
    resp = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 1, "rating": 5, "comment": "Great room!"},
    )
    assert resp.status_code == 201
    payload = json.loads(resp.data)
    assert payload["review"]["rating"] == 5
    assert payload["review"]["room_id"] == 1


def test_invalid_rating(client, user_token):
    resp = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 1, "rating": 8},
    )
    assert resp.status_code == 400


def test_reviews_for_room_and_average(client, user_token):
    # two reviews for room 2
    client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 2, "rating": 4, "comment": "Nice"},
    )
    client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 2, "rating": 2, "comment": "Ok"},
    )

    resp = client.get("/api/reviews/room/2")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["count"] == 2
    assert data["average_rating"] == 3


def test_update_and_delete_review_permissions(client, user_token, moderator_token):
    resp = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 3, "rating": 3, "comment": "Average"},
    )
    review_id = json.loads(resp.data)["review"]["id"]

    # Owner updates
    update = client.put(
        f"/api/reviews/{review_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"rating": 4},
    )
    assert update.status_code == 200

    # Stranger cannot delete
    stranger_token = _token(2, "bob", "regular_user")
    delete = client.delete(
        f"/api/reviews/{review_id}",
        headers={"Authorization": f"Bearer {stranger_token}"},
    )
    assert delete.status_code == 403

    # Moderator can delete
    mod_delete = client.delete(
        f"/api/reviews/{review_id}",
        headers={"Authorization": f"Bearer {moderator_token}"},
    )
    assert mod_delete.status_code == 200


def test_flag_and_moderation(client, user_token, moderator_token):
    resp = client.post(
        "/api/reviews",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"room_id": 4, "rating": 1, "comment": "Bad"},
    )
    review_id = json.loads(resp.data)["review"]["id"]

    # Any user can flag
    flag_resp = client.patch(
        f"/api/reviews/{review_id}/flag",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"flag": True},
    )
    assert flag_resp.status_code == 200
    assert json.loads(flag_resp.data)["review"]["is_flagged"] is True

    # Moderator clears flag and hides
    mod_resp = client.patch(
        f"/api/reviews/{review_id}/moderate",
        headers={"Authorization": f"Bearer {moderator_token}"},
        json={"hidden": True, "clear_flag": True},
    )
    assert mod_resp.status_code == 200
    moderated = json.loads(mod_resp.data)["review"]
    assert moderated["is_flagged"] is False
    assert moderated["hidden"] is True
