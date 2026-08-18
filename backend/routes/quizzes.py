import os
import random
import string
import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from bson import ObjectId

from backend.config import Config
from backend.utils.db import get_db
from backend.utils.auth import auth_required
from backend.utils.validators import validate_quiz_params, validate_file_upload
from backend.services.pdf_service import extract_text_from_pdf, extract_text_from_plain_text
from backend.services.rag_service import create_chunks_from_pages, retrieve_relevant_context, estimate_question_capacity
from backend.services.topic_service import normalize_topic
from backend.services.ai_service import generate_questions_with_ai, generate_topic_quiz_with_ai
from backend.services.quiz_service import (
    validate_and_sanitize_questions,
    evaluate_quiz_submission,
    update_user_topic_progress
)

logger = logging.getLogger(__name__)
quizzes_bp = Blueprint("quizzes", __name__, url_prefix="/api/quizzes")

def generate_unique_share_code(topic: str = "QUIZ") -> str:
    """Generate a clean share code like ML2026 or PY8492."""
    prefix = "".join(filter(str.isalnum, topic.upper()))[:4] or "QUIZ"
    digits = "".join(random.choices(string.digits, k=4))
    return f"{prefix}{digits}"

@quizzes_bp.route("/generate", methods=["POST"])
@auth_required
def generate_quiz():
    """
    Main Quiz Generation Endpoint.
    Supports:
    - SCENARIO A: Uploaded PDF / File / Pasted Text (Strict RAG mode)
    - SCENARIO B: Topic-Only mode (Dedicated topic generation pipeline with relevance validation & replacements)
    """
    user_id = request.user_id
    db = get_db()

    # Determine if multipart (file upload) or JSON
    if request.content_type and "multipart/form-data" in request.content_type:
        raw_data = request.form.to_dict()
        file = request.files.get("file")
    else:
        raw_data = request.get_json(silent=True) or {}
        file = None

    # Parse and validate settings
    num_q_raw = raw_data.get("num_questions") if raw_data.get("num_questions") is not None else raw_data.get("number_of_questions")
    try:
        num_questions = int(num_q_raw) if num_q_raw is not None and str(num_q_raw).strip() != "" else 10
    except (ValueError, TypeError):
        num_questions = -1
    difficulty = raw_data.get("difficulty", "medium").lower()
    question_types = raw_data.get("question_types", ["mcq"])
    if isinstance(question_types, str):
        if "[" in question_types:
            import json
            try:
                question_types = json.loads(question_types)
            except Exception:
                question_types = [t.strip() for t in question_types.split(",")]
        else:
            question_types = [t.strip() for t in question_types.split(",") if t.strip()]

    is_valid, err_msg = validate_quiz_params({
        "num_questions": num_questions,
        "difficulty": difficulty,
        "question_types": question_types
    })
    if not is_valid:
        return jsonify({"error": err_msg}), 400

    topic = raw_data.get("topic", "").strip()
    material_id_str = raw_data.get("material_id", "").strip()
    pasted_text = (raw_data.get("text") or raw_data.get("content") or raw_data.get("notes") or raw_data.get("article") or "").strip()
    force_count = str(raw_data.get("force_count", "false")).lower() in ("true", "1")

    context_chunks = []
    material_title = "Study Material"
    target_material_id = None

    # Determine Scenario:
    is_rag_mode = bool(material_id_str or file or pasted_text)

    if not is_rag_mode and not topic:
        return jsonify({"error": "Please provide an input method: Upload PDF, Enter Topic, or Paste Notes."}), 400

    # =========================================================================
    # SCENARIO B: DEDICATED TOPIC-ONLY GENERATION
    # =========================================================================
    if not is_rag_mode and topic:
        norm_topic = normalize_topic(topic)
        ai_response = generate_topic_quiz_with_ai(
            topic=norm_topic,
            num_questions=num_questions,
            difficulty=difficulty,
            question_types=question_types
        )
        validated_questions = ai_response.get("questions", [])

        if not validated_questions:
            return jsonify({
                "error": f"Could not generate questions for topic '{norm_topic}'.",
                "detail": "Please refine the topic name."
            }), 422

        quiz_title = f"{norm_topic} Quiz"
        share_code = generate_unique_share_code(norm_topic)

        quiz_doc = {
            "user_id": user_id,
            "material_id": None,
            "title": quiz_title,
            "topic": norm_topic,
            "difficulty": difficulty,
            "question_types": question_types,
            "question_count": len(validated_questions),
            "questions": validated_questions,
            "share_code": share_code,
            "is_published": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = db.quizzes.insert_one(quiz_doc)
        quiz_id = str(result.inserted_id)

        db.quiz_shares.insert_one({
            "share_code": share_code,
            "quiz_id": result.inserted_id,
            "created_by": user_id,
            "access_count": 0,
            "created_at": datetime.now(timezone.utc)
        })

        return jsonify({
            "success": True,
            "message": "Quiz generated successfully.",
            "quiz": {
                "id": quiz_id,
                "title": quiz_title,
                "topic": norm_topic,
                "difficulty": difficulty,
                "question_count": len(validated_questions),
                "share_code": share_code,
                "questions": validated_questions,
                "created_at": quiz_doc["created_at"].isoformat()
            }
        }), 201

    # =========================================================================
    # SCENARIO A: STRICT RAG DOCUMENT / ARTICLE MODE
    # =========================================================================
    # --- Mode 1: From Existing Material ID ---
    if material_id_str:
        try:
            m_oid = ObjectId(material_id_str)
            material_doc = db.materials.find_one({"_id": m_oid, "user_id": user_id})
            if not material_doc:
                return jsonify({"error": "Selected study material not found or access denied."}), 404
            
            target_material_id = m_oid
            material_title = material_doc.get("file_name", "Study Material")
            all_chunks = material_doc.get("chunks", [])
            
            context_chunks, _ = retrieve_relevant_context(
                chunks=all_chunks,
                topic=topic,
                top_k=max(15, num_questions * 2)
            )
        except Exception as e:
            return jsonify({"error": f"Invalid material lookup: {str(e)}"}), 400

    # --- Mode 2: Direct File Upload ---
    elif file:
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        v_ok, v_err = validate_file_upload(file.filename, file_size)
        if not v_ok:
            return jsonify({"error": v_err}), 400

        from werkzeug.utils import secure_filename
        filename = secure_filename(file.filename)
        saved_filename = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        saved_path = os.path.join(Config.UPLOAD_FOLDER, saved_filename)
        file.save(saved_path)

        if filename.lower().endswith(".pdf"):
            extraction = extract_text_from_pdf(saved_path)
            f_type = "pdf"
        else:
            with open(saved_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            extraction = extract_text_from_plain_text(content, title=filename)
            f_type = "text"

        mat_doc = {
            "user_id": user_id,
            "file_name": filename,
            "file_type": f_type,
            "file_size": file_size,
            "page_count": extraction.get("total_pages", 1),
            "total_words": extraction.get("total_words", 0),
            "total_characters": extraction.get("total_characters", 0),
            "raw_text": extraction.get("full_text", "")[:10000],
            "file_path": saved_path,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        res = db.materials.insert_one(mat_doc)
        target_material_id = res.inserted_id
        material_title = filename

        all_chunks = create_chunks_from_pages(
            pages=extraction.get("pages", []),
            material_id=target_material_id,
            user_id=user_id
        )
        db.materials.update_one({"_id": target_material_id}, {"$set": {"chunks": all_chunks, "chunk_count": len(all_chunks)}})

        context_chunks, _ = retrieve_relevant_context(
            chunks=all_chunks,
            topic=topic,
            top_k=max(20, num_questions * 2)
        )

    # --- Mode 3: Direct Pasted Notes/Article Text ---
    elif pasted_text:
        extraction = extract_text_from_plain_text(pasted_text, title=topic or "Pasted Notes")
        filename = f"{topic or 'Pasted Notes'}.txt"
        
        mat_doc = {
            "user_id": user_id,
            "file_name": filename,
            "file_type": "text",
            "file_size": len(pasted_text.encode("utf-8")),
            "page_count": extraction.get("total_pages", 1),
            "total_words": extraction.get("total_words", 0),
            "total_characters": extraction.get("total_characters", 0),
            "raw_text": pasted_text[:10000],
            "file_path": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        res = db.materials.insert_one(mat_doc)
        target_material_id = res.inserted_id
        material_title = filename

        all_chunks = create_chunks_from_pages(
            pages=extraction.get("pages", []),
            material_id=target_material_id,
            user_id=user_id
        )
        db.materials.update_one({"_id": target_material_id}, {"$set": {"chunks": all_chunks, "chunk_count": len(all_chunks)}})

        context_chunks, _ = retrieve_relevant_context(
            chunks=all_chunks,
            topic=topic,
            top_k=max(20, num_questions * 2)
        )

    retrieved_context_len = sum(len(c.get("chunk_text", "")) for c in context_chunks)

    logger.info("[DEBUG] Article characters: %d", len(pasted_text) if pasted_text else (extraction.get("total_characters", 0) if 'extraction' in locals() else 0))
    logger.info("[DEBUG] Chunks: %d", len(all_chunks) if 'all_chunks' in locals() else len(context_chunks))
    logger.info("[DEBUG] Retrieved chunks: %d", len(context_chunks))
    logger.info("[DEBUG] Retrieved context length: %d", retrieved_context_len)

    # Capacity Check & Genuinely Insufficient Source Handling
    total_chars = retrieved_context_len
    if total_chars < 120 and num_questions > 20 and not force_count:
        return jsonify({
            "insufficient_content": True,
            "requested_questions": num_questions,
            "max_reliable_questions": 1,
            "message": "The supplied material is too short to generate this many source-grounded questions."
        }), 200

    # Call RAG AI generation service
    ai_response = generate_questions_with_ai(
        context_chunks=context_chunks,
        num_questions=num_questions,
        difficulty=difficulty,
        question_types=question_types,
        topic=topic,
        material_title=material_title
    )

    raw_questions = ai_response.get("questions", [])
    
    # Strictly validate, deduplicate, and ground questions
    validated_questions = validate_and_sanitize_questions(raw_questions, context_chunks)

    if not validated_questions:
        return jsonify({
            "error": "Could not generate grounded questions from the supplied content.",
            "detail": "The context was insufficient or lacked clear factual statements."
        }), 422

    logger.info("[DEBUG] Final questions: %d", len(validated_questions))

    # Save Quiz to MongoDB
    final_topic = topic if topic else material_title
    quiz_title = f"{final_topic} Quiz"
    share_code = generate_unique_share_code(final_topic)

    quiz_doc = {
        "user_id": user_id,
        "material_id": target_material_id,
        "title": quiz_title,
        "topic": final_topic,
        "difficulty": difficulty,
        "question_types": question_types,
        "question_count": len(validated_questions),
        "questions": validated_questions,
        "share_code": share_code,
        "is_published": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = db.quizzes.insert_one(quiz_doc)
    quiz_id = str(result.inserted_id)

    db.quiz_shares.insert_one({
        "share_code": share_code,
        "quiz_id": result.inserted_id,
        "created_by": user_id,
        "access_count": 0,
        "created_at": datetime.now(timezone.utc)
    })

    return jsonify({
        "success": True,
        "message": "Quiz generated successfully.",
        "quiz": {
            "id": quiz_id,
            "title": quiz_title,
            "topic": final_topic,
            "difficulty": difficulty,
            "question_count": len(validated_questions),
            "share_code": share_code,
            "questions": validated_questions,
            "created_at": quiz_doc["created_at"].isoformat()
        }
    }), 201

@quizzes_bp.route("", methods=["GET"])
@auth_required
def list_quizzes():
    """List all quizzes created by the authenticated user with recent attempt stats."""
    user_id = request.user_id
    db = get_db()

    cursor = db.quizzes.find({"user_id": user_id}).sort("created_at", -1)
    quizzes_list = []

    for q in cursor:
        qid = q["_id"]
        latest_attempt = db.attempts.find_one(
            {"quiz_id": qid, "user_id": user_id},
            sort=[("completed_at", -1)]
        )
        quizzes_list.append({
            "id": str(qid),
            "title": q.get("title", "Untitled Quiz"),
            "topic": q.get("topic", "General"),
            "difficulty": q.get("difficulty", "medium"),
            "question_count": q.get("question_count", len(q.get("questions", []))),
            "share_code": q.get("share_code"),
            "is_published": q.get("is_published", False),
            "latest_score": latest_attempt.get("score") if latest_attempt else None,
            "latest_accuracy": latest_attempt.get("accuracy") if latest_attempt else None,
            "created_at": q.get("created_at").isoformat() if q.get("created_at") else None
        })

    return jsonify({"quizzes": quizzes_list}), 200

@quizzes_bp.route("/<quiz_id>", methods=["GET"])
@auth_required
def get_quiz_detail(quiz_id: str):
    """Retrieve quiz details and questions for taking the quiz."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(quiz_id)
    except Exception:
        return jsonify({"error": "Invalid quiz ID."}), 400

    quiz = db.quizzes.find_one({"_id": oid})
    if not quiz:
        return jsonify({"error": "Quiz not found."}), 404

    if quiz.get("user_id") != user_id and not quiz.get("is_published", False):
        return jsonify({"error": "Access denied to this private quiz."}), 403

    clean_questions = []
    for q in quiz.get("questions", []):
        clean_questions.append({
            "id": q["id"],
            "type": q.get("type", "mcq"),
            "question": q.get("question"),
            "options": q.get("options", []),
            "difficulty": q.get("difficulty", "Medium")
        })

    return jsonify({
        "quiz": {
            "id": str(quiz["_id"]),
            "title": quiz.get("title"),
            "topic": quiz.get("topic"),
            "difficulty": quiz.get("difficulty"),
            "question_count": len(quiz.get("questions", [])),
            "questions": clean_questions,
            "share_code": quiz.get("share_code"),
            "created_at": quiz.get("created_at").isoformat() if quiz.get("created_at") else None
        }
    }), 200

@quizzes_bp.route("/<quiz_id>/submit", methods=["POST"])
@auth_required
def submit_quiz_attempt(quiz_id: str):
    """Submit answers for evaluation, calculate scores, accuracy, and update progress."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(quiz_id)
    except Exception:
        return jsonify({"error": "Invalid quiz ID."}), 400

    quiz = db.quizzes.find_one({"_id": oid})
    if not quiz:
        return jsonify({"error": "Quiz not found."}), 404

    data = request.get_json(silent=True) or {}
    submitted_answers = data.get("answers", [])
    time_taken_seconds = int(data.get("time_taken", 0))

    eval_result = evaluate_quiz_submission(
        quiz=quiz,
        submitted_answers=submitted_answers,
        time_taken_seconds=time_taken_seconds
    )

    user_doc = db.users.find_one({"_id": user_id})
    user_email = user_doc.get("email") if user_doc else None

    completed_time = eval_result.get("completed_at", datetime.now(timezone.utc))

    attempt_doc = {
        "user_id": user_id,
        "user_email": user_email,
        "quiz_id": oid,
        "quiz_title": quiz.get("title"),
        "topic": quiz.get("topic", "General"),
        "score": eval_result["score"],
        "correct": eval_result["correct"],
        "correct_answers": eval_result.get("correct_answers", eval_result["correct"]),
        "incorrect": eval_result["incorrect"],
        "total_questions": eval_result["total_questions"],
        "accuracy": eval_result["accuracy"],
        "time_taken": time_taken_seconds,
        "answers": eval_result["detailed_review"],
        "completed_at": completed_time,
        "submitted_at": completed_time
    }

    res = db.attempts.insert_one(attempt_doc)
    attempt_id = str(res.inserted_id)

    update_user_topic_progress(
        db=db,
        user_id=user_id,
        topic=quiz.get("topic", "General"),
        correct=eval_result["correct"],
        total=eval_result["total_questions"]
    )

    return jsonify({
        "message": "Quiz submitted and evaluated successfully.",
        "attempt_id": attempt_id,
        "result": {
            "score": eval_result["score"],
            "correct": eval_result["correct"],
            "incorrect": eval_result["incorrect"],
            "total_questions": eval_result["total_questions"],
            "accuracy": eval_result["accuracy"],
            "time_taken": time_taken_seconds,
            "detailed_review": eval_result["detailed_review"],
            "completed_at": eval_result["completed_at"].isoformat()
        }
    }), 200

@quizzes_bp.route("/attempts/<attempt_id>", methods=["GET"])
@auth_required
def get_attempt_result(attempt_id: str):
    """Retrieve detailed results of an attempt with citations."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(attempt_id)
    except Exception:
        return jsonify({"error": "Invalid attempt ID."}), 400

    attempt = db.attempts.find_one({"_id": oid, "user_id": user_id})
    if not attempt:
        return jsonify({"error": "Attempt not found or access denied."}), 404

    return jsonify({
        "attempt": {
            "id": str(attempt["_id"]),
            "quiz_id": str(attempt["quiz_id"]),
            "quiz_title": attempt.get("quiz_title"),
            "topic": attempt.get("topic"),
            "score": attempt.get("score"),
            "correct": attempt.get("correct"),
            "incorrect": attempt.get("incorrect"),
            "total_questions": attempt.get("total_questions"),
            "accuracy": attempt.get("accuracy"),
            "time_taken": attempt.get("time_taken", 0),
            "detailed_review": attempt.get("answers", []),
            "completed_at": attempt.get("completed_at").isoformat() if attempt.get("completed_at") else None
        }
    }), 200

@quizzes_bp.route("/share/<share_code>", methods=["GET"])
@auth_required
def get_quiz_by_share_code(share_code: str):
    """Find a shared quiz using Quiz Code."""
    code_clean = share_code.strip().upper()
    db = get_db()

    quiz = db.quizzes.find_one({"share_code": code_clean})
    if not quiz:
        return jsonify({"error": f"No quiz found with share code: {code_clean}"}), 404

    db.quiz_shares.update_one({"share_code": code_clean}, {"$inc": {"access_count": 1}})

    return jsonify({
        "quiz": {
            "id": str(quiz["_id"]),
            "title": quiz.get("title"),
            "topic": quiz.get("topic"),
            "difficulty": quiz.get("difficulty"),
            "question_count": len(quiz.get("questions", [])),
            "share_code": quiz.get("share_code")
        }
    }), 200

@quizzes_bp.route("/<quiz_id>", methods=["DELETE"])
@auth_required
def delete_quiz(quiz_id: str):
    """Delete a quiz and its attempts."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(quiz_id)
    except Exception:
        return jsonify({"error": "Invalid quiz ID."}), 400

    res = db.quizzes.delete_one({"_id": oid, "user_id": user_id})
    if res.deleted_count == 0:
        return jsonify({"error": "Quiz not found or access denied."}), 404

    db.attempts.delete_many({"quiz_id": oid, "user_id": user_id})
    return jsonify({"message": "Quiz deleted successfully."}), 200
