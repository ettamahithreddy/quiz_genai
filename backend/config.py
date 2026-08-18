import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Config:
    # Server
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "quizgen_jwt_secret_dev_2026_x89a_secure")
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24 * 7  # 7 days in seconds

    # Database
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/quiz_generator")
    DB_NAME = os.getenv("DB_NAME", "quiz_generator")

    # Uploads
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 20 * 1024 * 1024))  # 20 MB
    ALLOWED_EXTENSIONS = {"pdf", "txt", "md"}

    # AI API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("AI_API_KEY", "")

    # RAG Settings
    CHUNK_SIZE = 600       # Target chunk size in characters
    CHUNK_OVERLAP = 120    # Overlap between consecutive chunks
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
