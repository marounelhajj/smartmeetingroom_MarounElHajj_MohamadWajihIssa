"""
Users Service - Smart Meeting Room System
Author: Maroun El Hajj

This microservice manages:
- user accounts
- authentication (JWT tokens)
- basic RBAC (admin, regular_user, facility_manager, moderator, auditor, service_account)
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from typing import Optional
import datetime
import os
import jwt
import re

# ----------------------------------------------------------------------
# Flask & DB configuration
# ----------------------------------------------------------------------
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///users.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "change-this-secret-key-in-production"
)

db = SQLAlchemy(app)

# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


class User(db.Model):
    """SQLAlchemy model for users."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    role = db.Column(
        db.String(30),
        nullable=False,
        default="regular_user",
    )
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self) -> dict:
        """Serialize user without password."""
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat(),
        }


# ----------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------


def validate_email(email: str) -> bool:
    """Return True if email has valid format."""
    pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return bool(re.match(pattern, email or ""))


def validate_username(username: str) -> bool:
    """Allow letters, numbers and underscore; length 3..50."""
    pattern = r"^[A-Za-z0-9_]{3,50}$"
    return bool(re.match(pattern, username or ""))


def sanitize(text: Optional[str]) -> Optional[str]:
    """Very small sanitizer against obvious injection patterns."""
    if text is None:
        return None
    bad = ["<", ">", '"', "'", ";", "--", "/*", "*/"]
    result = str(text)
    for b in bad:
        result = result.replace(b, "")
    return result.strip()


def create_token(user: User) -> str:
    """Create JWT token with 24h expiration."""
    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(raw_token: str):
    """Decode token or raise jwt exceptions."""
    return jwt.decode(raw_token, app.config["SECRET_KEY"], algorithms=["HS256"])


# ----------------------------------------------------------------------
# Decorators for authentication/authorization
# ----------------------------------------------------------------------


def token_required(fn):
    """Decorator to enforce presence of valid JWT in Authorization header."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        # Expect "Bearer <token>"
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        try:
            data = decode_token(token)
            current_user = User.query.get(data["user_id"])
            if not current_user:
                return jsonify({"error": "User not found"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return fn(current_user, *args, **kwargs)

    return wrapper


def admin_required(fn):
    """Decorator: only admins allowed."""

    @wraps(fn)
    def wrapper(current_user: User, *args, **kwargs):
        if current_user.role != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return fn(current_user, *args, **kwargs)

    return wrapper


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------


@app.route("/health", methods=["GET"])
def health():
    """Simple health check."""
    return jsonify({"status": "healthy", "service": "users"}), 200


@app.route("/api/users/register", methods=["POST"])
def register():
    """
    Register new user.

    JSON body:
    {
        "name": "...",
        "username": "...",
        "password": "...",
        "email": "...",
        "role": "admin|regular_user|facility_manager|moderator|auditor|service_account" (optional)
    }
    """
    data = request.get_json() or {}

    # Required fields
    for field in ["name", "username", "password", "email"]:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    name = sanitize(data["name"])
    username = sanitize(data["username"])
    email = sanitize(data["email"])
    password = data["password"]
    role = sanitize(data.get("role", "regular_user"))

    valid_roles = [
        "admin",
        "regular_user",
        "facility_manager",
        "moderator",
        "auditor",
        "service_account",
    ]

    if not validate_username(username or ""):
        return jsonify(
            {
                "error": "Username must be 3-50 chars long and contain only letters, "
                "numbers, and underscore"
            }
        ), 400

    if not validate_email(email or ""):
        return jsonify({"error": "Invalid email format"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if role not in valid_roles:
        return jsonify(
            {"error": f"Invalid role. Allowed roles: {', '.join(valid_roles)}"}
        ), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 409

    try:
        hashed = generate_password_hash(password)
        new_user = User(
            name=name,
            username=username,
            password=hashed,
            email=email,
            role=role,
        )
        db.session.add(new_user)
        db.session.commit()

        return (
            jsonify({"message": "User registered successfully", "user": new_user.to_dict()}),
            201,
        )
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Registration failed: {exc}"}), 500


@app.route("/api/users/login", methods=["POST"])
def login():
    """
    Login endpoint.

    JSON body:
    {
        "username": "...",
        "password": "..."
    }
    """
    data = request.get_json() or {}
    username = sanitize(data.get("username"))
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_token(user)

    return (
        jsonify(
            {
                "message": "Login successful",
                "token": token,
                "user": user.to_dict(),
            }
        ),
        200,
    )


@app.route("/api/users", methods=["GET"])
@token_required
def get_all_users(current_user: User):
    """
    Get all users.

    - admins and auditors can read all users
    """
    if current_user.role not in ["admin", "auditor"]:
        return jsonify({"error": "Insufficient permissions"}), 403

    users = User.query.all()
    return (
        jsonify(
            {
                "users": [u.to_dict() for u in users],
                "count": len(users),
            }
        ),
        200,
    )


@app.route("/api/users/<string:username>", methods=["GET"])
@token_required
def get_user(current_user: User, username: str):
    """
    Get user by username.

    - user can see himself
    - admin and auditor can see everyone
    """
    username = sanitize(username)

    if current_user.username != username and current_user.role not in [
        "admin",
        "auditor",
    ]:
        return jsonify({"error": "Insufficient permissions"}), 403

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user.to_dict()}), 200


@app.route("/api/users/<string:username>", methods=["PUT"])
@token_required
def update_user(current_user: User, username: str):
    """
    Update user details.

    JSON body (any subset):
    {
        "name": "...",
        "email": "...",
        "password": "...",
        "role": "..."   # role change only allowed for admins
    }
    """
    username = sanitize(username)

    if current_user.username != username and current_user.role != "admin":
        return jsonify({"error": "Insufficient permissions"}), 403

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    # Name
    if "name" in data and data["name"]:
        user.name = sanitize(data["name"])

    # Email
    if "email" in data and data["email"]:
        email = sanitize(data["email"])
        if not validate_email(email or ""):
            return jsonify({"error": "Invalid email format"}), 400

        other = User.query.filter_by(email=email).first()
        if other and other.id != user.id:
            return jsonify({"error": "Email already in use"}), 409
        user.email = email

    # Password
    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            return jsonify(
                {"error": "Password must be at least 6 characters"},
            ), 400
        user.password = generate_password_hash(data["password"])

    # Role
    if "role" in data:
        if current_user.role != "admin":
            return jsonify({"error": "Only admins can change roles"}), 403
        new_role = sanitize(data["role"])
        valid_roles = [
            "admin",
            "regular_user",
            "facility_manager",
            "moderator",
            "auditor",
            "service_account",
        ]
        if new_role not in valid_roles:
            return jsonify(
                {"error": f"Invalid role. Allowed: {', '.join(valid_roles)}"},
            ), 400
        user.role = new_role

    try:
        db.session.commit()
        return jsonify({"message": "User updated", "user": user.to_dict()}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Update failed: {exc}"}), 500


@app.route("/api/users/<string:username>", methods=["DELETE"])
@token_required
@admin_required
def delete_user(current_user: User, username: str):
    """
    Delete user (admin only).

    - admin cannot delete himself (safety)
    """
    username = sanitize(username)
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.id == current_user.id:
        return jsonify({"error": "Admin cannot delete own account"}), 400

    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": f"User {username} deleted"}), 200
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        return jsonify({"error": f"Delete failed: {exc}"}), 500


# ----------------------------------------------------------------------
# CLI entrypoint
# ----------------------------------------------------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5001, debug=True)
