from functools import wraps
from flask import request, jsonify
import bcrypt
from flask_jwt_extended import create_access_token, decode_token
from bson import ObjectId
from backend.utils.db import get_db

def hash_password(password: str) -> str:
    """Hash password with bcrypt salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_user_token(user_id: str, email: str, role: str = "student") -> str:
    """Create JWT access token storing user_id and email in claims."""
    additional_claims = {
        "email": email,
        "role": role
    }
    return create_access_token(identity=str(user_id), additional_claims=additional_claims)

def get_auth_token_from_header() -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return ""

def auth_required(f):
    """
    Decorator to protect routes, validating JWT token
    and attaching authenticated user object to request context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_auth_token_from_header()
        if not token:
            return jsonify({"error": "Authentication required. Missing token."}), 401
        
        try:
            decoded = decode_token(token)
            user_id = decoded.get("sub")
            if not user_id:
                return jsonify({"error": "Invalid token identity."}), 401
            
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return jsonify({"error": "User not found or token expired."}), 401
            
            # Store authenticated user inside request
            request.user = user
            request.user_id = ObjectId(user_id)
            request.user_role = user.get("role", "student")

        except Exception as e:
            return jsonify({"error": "Invalid or expired token.", "detail": str(e)}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """Decorator to enforce teacher/admin role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_auth_token_from_header()
        if not token:
            return jsonify({"error": "Authentication required."}), 401
        try:
            decoded = decode_token(token)
            user_id = decoded.get("sub")
            db = get_db()
            user = db.users.find_one({"_id": ObjectId(user_id)})
            if not user or user.get("role") not in ("teacher", "admin"):
                return jsonify({"error": "Teacher role required to access this resource."}), 403
            request.user = user
            request.user_id = ObjectId(user_id)
            request.user_role = user.get("role")
        except Exception:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function
