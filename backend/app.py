import os
import sys
import logging
from pathlib import Path
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.config import Config
from backend.utils.db import get_db, is_mock_db
from backend.routes.auth import auth_bp
from backend.routes.materials import materials_bp
from backend.routes.quizzes import quizzes_bp
from backend.routes.dashboard import dashboard_bp
from backend.routes.flashcards import flashcards_bp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("quizgen_ai")

def create_app():
    frontend_dir = BASE_DIR / "frontend"
    app = Flask(
        __name__,
        static_folder=str(frontend_dir),
        static_url_path=""
    )
    app.config.from_object(Config)

    # Enable CORS
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    # Initialize JWT Manager
    jwt = JWTManager(app)

    @jwt.unauthorized_loader
    def custom_unauthorized_response(err):
        return jsonify({"error": "Authentication token is missing or invalid.", "detail": str(err)}), 401

    @jwt.expired_token_loader
    def custom_expired_token_response(jwt_header, jwt_payload):
        return jsonify({"error": "Token has expired. Please log in again."}), 401

    # Register API Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(quizzes_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(flashcards_bp)

    # Health Check endpoint
    @app.route("/api/health", methods=["GET"])
    def health_check():
        db = get_db()
        return jsonify({
            "status": "ok",
            "app": "QuizGen AI",
            "version": "1.0.0",
            "database": "mock_in_memory" if is_mock_db() else "mongodb_connected"
        }), 200

    # Serve Frontend Pages
    @app.route("/")
    def serve_index():
        return send_from_directory(str(frontend_dir), "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        target = frontend_dir / path
        if target.is_file():
            return send_from_directory(str(frontend_dir), path)
        elif (frontend_dir / f"{path}.html").is_file():
            return send_from_directory(str(frontend_dir), f"{path}.html")
        return send_from_directory(str(frontend_dir), "index.html")

    # Global Error Handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request.", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "API endpoint not found."}), 404
        return send_from_directory(str(frontend_dir), "index.html")

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return jsonify({"error": "File size exceeds the 20 MB limit."}), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.error("Internal Server Error: %s", str(e))
        return jsonify({"error": "An internal server error occurred. Please try again."}), 500

    return app

app = create_app()

if __name__ == "__main__":
    logger.info("Starting QuizGen AI server on port %d...", Config.PORT)
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
