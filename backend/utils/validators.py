import re
from typing import Tuple, List, Optional
from backend.config import Config

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate_registration(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate user registration inputs."""
    if not data:
        return False, "Request body cannot be empty."

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")

    if not name:
        return False, "Name is required."
    if len(name) < 2 or len(name) > 100:
        return False, "Name must be between 2 and 100 characters."

    if not email or not EMAIL_REGEX.match(email):
        return False, "A valid email address is required."

    if not password:
        return False, "Password is required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    if confirm_password and password != confirm_password:
        return False, "Passwords do not match."

    return True, None

def validate_login(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate user login inputs."""
    if not data:
        return False, "Request body cannot be empty."

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email:
        return False, "Email is required."
    if not password:
        return False, "Password is required."

    return True, None

def validate_file_upload(filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
    """Validate uploaded file size and extension."""
    if not filename:
        return False, "No file uploaded."

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in Config.ALLOWED_EXTENSIONS:
        return False, f"Invalid file format. Allowed formats: {', '.join(Config.ALLOWED_EXTENSIONS).upper()}"

    if file_size > Config.MAX_CONTENT_LENGTH:
        return False, f"File size exceeds the 20 MB limit (File is {round(file_size / (1024 * 1024), 2)} MB)."

    return True, None

def validate_quiz_params(data: dict) -> Tuple[bool, Optional[str]]:
    """Validate quiz generation request parameters."""
    num_questions = data.get("num_questions", 10)
    try:
        num_questions = int(num_questions)
        if num_questions < 1 or num_questions > 100:
            return False, "Number of questions must be between 1 and 100."
    except (ValueError, TypeError):
        return False, "Invalid number of questions."

    difficulty = data.get("difficulty", "medium").lower()
    if difficulty not in ("easy", "medium", "difficult", "hard", "mixed"):
        return False, "Difficulty must be one of: easy, medium, difficult, mixed."

    question_types = data.get("question_types", ["mcq"])
    if not isinstance(question_types, list) or len(question_types) == 0:
        return False, "At least one question type must be selected (mcq, true_false, short_answer)."

    valid_types = {"mcq", "true_false", "short_answer"}
    for qt in question_types:
        if qt not in valid_types:
            return False, f"Unsupported question type: {qt}"

    return True, None
