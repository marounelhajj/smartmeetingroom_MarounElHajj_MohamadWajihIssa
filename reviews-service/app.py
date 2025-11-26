"""
Reviews Service - Smart Meeting Room System
Author: Assistant

Responsibilities:
- Allow users to submit, update, delete reviews for rooms
- Provide moderation workflows (flag/unflag/hide)
- Enforce authentication and basic RBAC
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from typing import Optional
import datetime
import logging
import time
import os
import jwt
from logging.handlers import RotatingFileHandler

# ----------------------------------------------------------------------
# App configuration
# ----------------------------------------------------------------------
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///reviews.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "change-this-secret-key-in-production"
)

db = SQLAlchemy(app)

# ----------------------------------------------------------------------
# Auditing & rate limiting
# ----------------------------------------------------------------------

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
_rate_buckets: dict = {}


def _init_logging():
    """Configure rotating file logging for auditing."""
    os.makedirs("logs", exist_ok=True)
    handler = RotatingFileHandler("logs/reviews.log", maxBytes=500_000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(handler)


_init_logging()

# ----------------------------------------------------------------------
# Caching (simple in-memory with TTL)
# ----------------------------------------------------------------------

REVIEWS_CACHE_TTL = int(os.getenv("REVIEWS_CACHE_TTL", "60"))
_room_reviews_cache: dict = {}


def _cache_get(cache: dict, key):
    entry = cache.get(key)
    if not entry:
        return None
    expires, value = entry
    if time.time() > expires:
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict, key, value):
    cache[key] = (time.time() + REVIEWS_CACHE_TTL, value)


def _invalidate_room_cache(room_id: int):
    _room_reviews_cache.pop(room_id, None)


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


class Review(db.Model):
    """Database model for reviews."""

    __tablename__ = "reviews"
    __table_args__ = (
        db.Index("ix_reviews_room_created", "room_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)
    room_id = db.Column(db.Integer, nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.String(1000), nullable=True)
    is_flagged = db.Column(db.Boolean, default=False)
    hidden = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    def to_dict(self) -> dict:
        """Serialize review for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "room_id": self.room_id,
            "rating": self.rating,
            "comment": self.comment,
            "is_flagged": self.is_flagged,
            "hidden": self.hidden,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def sanitize(text: Optional[str]) -> Optional[str]:
    """Basic sanitization to minimize injection surface."""
    if text is None:
        return None
    bad = ["<", ">", '"', "'", ";", "--", "/*", "*/"]
    clean = str(text)
    for b in bad:
        clean = clean.replace(b, "")
    return clean.strip()


def decode_token(auth_header: str) -> dict:
    """Decode JWT using shared secret."""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = auth_header
    return jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])


def _try_decode_for_logging() -> dict:
    """Decode JWT for logging if available."""
    header = request.headers.get("Authorization")
    if not header:
        return {}
    try:
        return decode_token(header)
    except Exception:  # noqa: BLE001
        return {}


def auth_required(fn):
    """Require JWT."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization")
        if not header:
            return jsonify({"error": "Authorization header missing"}), 401
        try:
            payload = decode_token(header)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return fn(payload, *args, **kwargs)

    return wrapper


def _prune_bucket(bucket, now: float):
    """Remove timestamps outside window."""
    return [ts for ts in bucket if now - ts <= RATE_LIMIT_WINDOW]


@app.before_request
def enforce_rate_limit():
    """Simple sliding-window rate limiter per IP + endpoint."""
    if request.endpoint == "health" or request.endpoint == "reviews_for_room":
        return
    now = time.time()
    key = f"{request.remote_addr}:{request.endpoint}"
    bucket = _rate_buckets.get(key, [])
    bucket = _prune_bucket(bucket, now)
    if len(bucket) >= RATE_LIMIT_REQUESTS:
        return jsonify({"error": "Rate limit exceeded"}), 429
    bucket.append(now)
    _rate_buckets[key] = bucket


@app.after_request
def audit_log(response):
    """Log request/response pairs for auditing."""
    payload = _try_decode_for_logging()
    app.logger.info(
        "user_id=%s role=%s method=%s path=%s status=%s",
        payload.get("user_id"),
        payload.get("role"),
        request.method,
        request.path,
        response.status_code,
    )
    return response


def moderator_or_admin(role: str) -> bool:
    """Return True if role can moderate reviews."""
    return role in ["admin", "moderator"]


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "reviews"}), 200


@app.route("/api/reviews", methods=["GET"])
@auth_required
def list_reviews(payload: dict):
    """
    List reviews.

    - moderators/admins see all
    - others see only non-hidden reviews
    """
    if moderator_or_admin(payload.get("role", "")):
        reviews = Review.query.order_by(Review.created_at.desc()).all()
    else:
        reviews = (
            Review.query.filter_by(hidden=False)
            .order_by(Review.created_at.desc())
            .all()
        )
    return jsonify({"reviews": [r.to_dict() for r in reviews], "count": len(reviews)}), 200


@app.route("/api/reviews/room/<int:room_id>", methods=["GET"])
def reviews_for_room(room_id: int):
    """Public endpoint to view reviews for a room (hidden reviews are excluded)."""
    cached = _cache_get(_room_reviews_cache, room_id)
    if cached is not None:
        return jsonify(cached), 200

    reviews = (
        Review.query.filter_by(room_id=room_id, hidden=False)
        .order_by(Review.created_at.desc())
        .all()
    )
    if reviews:
        avg_rating = sum([r.rating for r in reviews]) / len(reviews)
    else:
        avg_rating = 0
    payload = {
        "room_id": room_id,
        "reviews": [r.to_dict() for r in reviews],
        "count": len(reviews),
        "average_rating": round(avg_rating, 2),
    }
    _cache_set(_room_reviews_cache, room_id, payload)
    return jsonify(payload), 200


def _validate_review_payload(data: dict) -> Optional[str]:
    """Return error message if invalid, else None."""
    if "rating" not in data:
        return "rating is required"
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        return "rating must be an integer 1-5"
    if rating < 1 or rating > 5:
        return "rating must be between 1 and 5"

    if data.get("comment") and len(str(data.get("comment"))) > 1000:
        return "comment too long (max 1000 characters)"
    if "room_id" in data:
        try:
            int(data.get("room_id"))
        except (TypeError, ValueError):
            return "room_id must be an integer"
    return None


@app.route("/api/reviews", methods=["POST"])
@auth_required
def create_review(payload: dict):
    """
    Submit a review.

    JSON body:
    {
        "room_id": 1,
        "rating": 4,
        "comment": "Great room!"
    }
    """
    data = request.get_json() or {}
    for field in ["room_id", "rating"]:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    err = _validate_review_payload(data)
    if err:
        return jsonify({"error": err}), 400

    review = Review(
        user_id=payload.get("user_id"),
        username=payload.get("username", "unknown"),
        room_id=int(data["room_id"]),
        rating=int(data["rating"]),
        comment=sanitize(data.get("comment")),
    )
    try:
        db.session.add(review)
        db.session.commit()
        _invalidate_room_cache(review.room_id)
        return jsonify({"message": "Review submitted", "review": review.to_dict()}), 201
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Failed to submit review: {exc}"}), 500


def _ensure_permission(payload: dict, review: Review) -> Optional[tuple]:
    """Check if user can manage a review."""
    role = payload.get("role")
    if moderator_or_admin(role) or review.user_id == payload.get("user_id"):
        return None
    return jsonify({"error": "Insufficient permissions"}), 403


@app.route("/api/reviews/<int:review_id>", methods=["PUT"])
@auth_required
def update_review(payload: dict, review_id: int):
    """Update rating/comment for a review."""
    review = Review.query.get(review_id)
    if not review:
        return jsonify({"error": "Review not found"}), 404

    perm = _ensure_permission(payload, review)
    if perm:
        return perm

    data = request.get_json() or {}
    err = _validate_review_payload({**data, "room_id": review.room_id, "rating": data.get("rating", review.rating)})
    if err:
        return jsonify({"error": err}), 400

    if "rating" in data:
        review.rating = int(data["rating"])
    if "comment" in data:
        review.comment = sanitize(data.get("comment"))

    try:
        db.session.commit()
        _invalidate_room_cache(review.room_id)
        return jsonify({"message": "Review updated", "review": review.to_dict()}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Failed to update review: {exc}"}), 500


@app.route("/api/reviews/<int:review_id>", methods=["DELETE"])
@auth_required
def delete_review(payload: dict, review_id: int):
    """Delete a review (moderator/admin or owner)."""
    review = Review.query.get(review_id)
    if not review:
        return jsonify({"error": "Review not found"}), 404

    perm = _ensure_permission(payload, review)
    if perm:
        return perm

    try:
        db.session.delete(review)
        db.session.commit()
        _invalidate_room_cache(review.room_id)
        return jsonify({"message": "Review deleted"}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Failed to delete review: {exc}"}), 500


@app.route("/api/reviews/<int:review_id>/flag", methods=["PATCH"])
@auth_required
def flag_review(payload: dict, review_id: int):
    """
    Flag or unflag a review.

    Any authenticated user can flag; only moderators/admins can clear flags.
    JSON body: {"flag": true|false}
    """
    review = Review.query.get(review_id)
    if not review:
        return jsonify({"error": "Review not found"}), 404

    data = request.get_json() or {}
    desired_flag = bool(data.get("flag", True))

    if not desired_flag and not moderator_or_admin(payload.get("role", "")):
        return jsonify({"error": "Only moderators/admins can clear flags"}), 403

    review.is_flagged = desired_flag
    review.hidden = review.hidden or desired_flag

    try:
        db.session.commit()
        _invalidate_room_cache(review.room_id)
        return jsonify({"message": "Flag updated", "review": review.to_dict()}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Failed to update flag: {exc}"}), 500


@app.route("/api/reviews/<int:review_id>/moderate", methods=["PATCH"])
@auth_required
def moderate_review(payload: dict, review_id: int):
    """
    Moderator/admin actions.

    JSON body:
    {
        "hidden": true|false,
        "clear_flag": true|false
    }
    """
    if not moderator_or_admin(payload.get("role", "")):
        return jsonify({"error": "Moderator or admin required"}), 403

    review = Review.query.get(review_id)
    if not review:
        return jsonify({"error": "Review not found"}), 404

    data = request.get_json() or {}
    if "hidden" in data:
        review.hidden = bool(data["hidden"])
    if data.get("clear_flag"):
        review.is_flagged = False

    try:
        db.session.commit()
        _invalidate_room_cache(review.room_id)
        return jsonify({"message": "Review moderated", "review": review.to_dict()}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Failed to moderate review: {exc}"}), 500


# ----------------------------------------------------------------------
# Entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5004, debug=True)
