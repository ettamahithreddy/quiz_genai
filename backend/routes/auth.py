from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from bson import ObjectId
from backend.utils.db import get_db
from backend.utils.auth import hash_password, verify_password, create_user_token, auth_required
from backend.utils.validators import validate_registration, validate_login

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    
    is_valid, error_msg = validate_registration(data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    name = data["name"].strip()
    email = data["email"].strip().lower()
    password = data["password"]
    role = data.get("role", "student").lower()
    if role not in ("student", "teacher", "admin"):
        role = "student"

    db = get_db()

    # Check if user already exists
    existing = db.users.find_one({"email": email})
    if existing:
        return jsonify({"error": "An account with this email address already exists."}), 409

    now = datetime.now(timezone.utc)
    hashed_pwd = hash_password(password)

    user_doc = {
        "name": name,
        "email": email,
        "password_hash": hashed_pwd,
        "role": role,
        "created_at": now,
        "updated_at": now
    }

    result = db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_user_token(user_id=user_id, email=email, role=role)

    return jsonify({
        "message": "Registration successful.",
        "token": token,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "role": role
        }
    }), 201

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate existing user and return JWT."""
    data = request.get_json(silent=True) or {}

    is_valid, error_msg = validate_login(data)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    email = data["email"].strip().lower()
    password = data["password"]

    db = get_db()
    user = db.users.find_one({"email": email})

    if not user or not verify_password(password, user.get("password_hash", "")):
        return jsonify({"error": "Invalid email or password."}), 401

    user_id = str(user["_id"])
    role = user.get("role", "student")
    token = create_user_token(user_id=user_id, email=email, role=role)

    return jsonify({
        "message": "Login successful.",
        "token": token,
        "user": {
            "id": user_id,
            "name": user.get("name"),
            "email": user.get("email"),
            "role": role
        }
    }), 200

@auth_bp.route("/me", methods=["GET"])
@auth_required
def get_current_user_profile():
    """Fetch profile of currently authenticated user."""
    user = request.user
    return jsonify({
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name"),
            "email": user.get("email"),
            "role": user.get("role", "student"),
            "created_at": user.get("created_at").isoformat() if user.get("created_at") else None
        }
    }), 200

@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Acknowledge logout."""
    return jsonify({"message": "Logout successful."}), 200
