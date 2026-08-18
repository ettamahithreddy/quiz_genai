import os
import re
import logging
import certifi
from pymongo import MongoClient, ASCENDING
from backend.config import Config

logger = logging.getLogger(__name__)

_mongo_client = None
_db_instance = None
_is_mock = False

def _sanitize_error(error_str: str) -> str:
    """Mask any embedded passwords or credentials in connection strings or error messages."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", str(error_str))

def get_db():
    """
    Returns the MongoDB database instance.
    Connects to MongoDB Atlas or configured MongoDB URI.
    """
    MONGO_URI = os.environ.get("MONGO_URI")
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    global _mongo_client, _db_instance, _is_mock

    if _db_instance is not None:
        return _db_instance

    mongo_uri = Config.MONGO_URI
    db_name = Config.DB_NAME or "quiz_generator"

    if not mongo_uri:
        logger.error("MongoDB configuration error: MONGO_URI environment variable is missing.")
        raise ValueError("MONGO_URI environment variable is not configured.")

    try:
        # Configure client connection options
        client_kwargs = {
            "serverSelectionTimeoutMS": 5000,
            "connectTimeoutMS": 5000,
            "socketTimeoutMS": 10000,
        }

        # Apply certifi CA bundle for Atlas (SRV or TLS/SSL connections)
        if "mongodb+srv" in mongo_uri or "ssl=true" in mongo_uri.lower() or "tls=true" in mongo_uri.lower():
            client_kwargs["tlsCAFile"] = certifi.where()

        _mongo_client = MongoClient(mongo_uri, **client_kwargs)

        # Ping operation to verify actual connection
        _mongo_client.admin.command("ping")
        _db_instance = _mongo_client[db_name]
        _is_mock = False

        if "mongodb+srv" in mongo_uri or "mongodb.net" in mongo_uri:
            logger.info("MongoDB Atlas connection successful (Database: %s)", db_name)
        else:
            logger.info("MongoDB connection successful (Database: %s)", db_name)

    except Exception as e:
        safe_err = _sanitize_error(str(e))
        logger.error("MongoDB connection failed: %s", safe_err)

        # If remote Atlas fails, check if local MongoDB is available as backup
        try:
            local_client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=1500)
            local_client.admin.command("ping")
            _mongo_client = local_client
            _db_instance = _mongo_client[db_name]
            _is_mock = False
            logger.info("Connected to local MongoDB instance (Database: %s).", db_name)
        except Exception:
            import mongomock
            logger.warning("MongoDB unavailable. Falling back to in-memory mongomock database.")
            _mongo_client = mongomock.MongoClient()
            _db_instance = _mongo_client[db_name]
            _is_mock = True

    # Setup indexes
    _setup_indexes(_db_instance)
    return _db_instance

def is_mock_db():
    return _is_mock

def _setup_indexes(db):
    try:
        # User email unique index
        db.users.create_index([("email", ASCENDING)], unique=True)
        # Material user_id index
        db.materials.create_index([("user_id", ASCENDING)])
        # Quizzes user_id index
        db.quizzes.create_index([("user_id", ASCENDING)])
        db.quizzes.create_index([("share_code", ASCENDING)])
        # Attempts user_id and quiz_id indexes
        db.attempts.create_index([("user_id", ASCENDING)])
        db.attempts.create_index([("quiz_id", ASCENDING)])
        # Progress user_id and topic compound index
        db.progress.create_index([("user_id", ASCENDING), ("topic", ASCENDING)], unique=True)
        # Flashcards user_id index
        db.flashcards.create_index([("user_id", ASCENDING)])
    except Exception as e:
        logger.debug("Index creation notice: %s", str(e))

