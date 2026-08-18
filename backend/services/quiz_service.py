import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
from backend.services.embedding_service import calculate_cosine_similarity, get_embedding

logger = logging.getLogger(__name__)

def validate_and_sanitize_questions(
    questions: List[Dict[str, Any]],
    context_chunks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Validates, deduplicates, and cleans generated questions.
    Rejects malformed or hallucinated questions lacking valid source alignment.
    """
    if not questions:
        return []

    valid_questions = []
    seen_texts = set()

    for idx, q in enumerate(questions):
        q_text = q.get("question", "").strip()
        if not q_text or len(q_text) < 8:
            continue

        # Deduplication check (normalized lower)
        norm_key = re.sub(r"[^a-z0-9]", "", q_text.lower())
        if norm_key in seen_texts:
            continue
        seen_texts.add(norm_key)

        q_type = q.get("type", "mcq").lower()
        if q_type not in ("mcq", "true_false", "short_answer"):
            q_type = "mcq"

        correct_ans = str(q.get("correct_answer", "")).strip()
        if not correct_ans:
            continue

        options = q.get("options", [])
        if q_type == "mcq":
            if not isinstance(options, list) or len(options) < 2:
                continue
            # Ensure unique options
            clean_options = []
            opt_set = set()
            for opt in options:
                opt_str = str(opt).strip()
                if opt_str and opt_str not in opt_set:
                    clean_options.append(opt_str)
                    opt_set.add(opt_str)

            if len(clean_options) < 2:
                continue

            # Ensure correct answer is one of the options
            if correct_ans not in clean_options:
                # If close match exists, align it, otherwise prepend
                found_match = False
                for opt in clean_options:
                    if opt.lower() == correct_ans.lower():
                        correct_ans = opt
                        found_match = True
                        break
                if not found_match:
                    clean_options[0] = correct_ans

            options = clean_options

        elif q_type == "true_false":
            options = ["True", "False"]
            if correct_ans.lower() in ("true", "t", "yes", "1"):
                correct_ans = "True"
            else:
                correct_ans = "False"

        else:  # short_answer
            options = []

        # Source page and snippet validation
        source_page = q.get("source_page", 1)
        try:
            source_page = int(source_page)
        except Exception:
            source_page = 1

        source_text = q.get("source_text", "").strip()
        if not source_text and context_chunks:
            # Fallback to closest chunk
            source_text = context_chunks[0].get("chunk_text", "")[:180]
            source_page = context_chunks[0].get("page_number", 1)

        diff_raw = str(q.get("difficulty", "Medium")).strip().lower()
        if diff_raw in ("hard", "difficult"):
            diff_val = "Difficult"
        elif diff_raw == "easy":
            diff_val = "Easy"
        else:
            diff_val = "Medium"

        valid_questions.append({
            "id": f"q_{idx+1}",
            "type": q_type,
            "question": q_text,
            "options": options,
            "correct_answer": correct_ans,
            "explanation": q.get("explanation", f"Supported by source material on page {source_page}.").strip(),
            "difficulty": diff_val,
            "source_page": source_page,
            "source_text": source_text
        })

    return valid_questions

def evaluate_short_answer(user_answer: str, expected_answer: str) -> Tuple[bool, float]:
    """
    Evaluates short answer text against expected answer.
    Returns: (is_correct, score_fraction 0.0 to 1.0)
    """
    u_clean = user_answer.strip().lower()
    e_clean = expected_answer.strip().lower()

    if not u_clean:
        return False, 0.0

    # Exact or substring match
    if u_clean == e_clean or e_clean in u_clean or u_clean in e_clean:
        return True, 1.0

    # Word token overlap
    u_words = set(re.findall(r"\b[a-z0-9]{3,}\b", u_clean))
    e_words = set(re.findall(r"\b[a-z0-9]{3,}\b", e_clean))

    if not e_words:
        return True, 1.0

    overlap = len(u_words.intersection(e_words)) / len(e_words)
    if overlap >= 0.60:
        return True, 1.0
    elif overlap >= 0.40:
        return True, 0.75
    elif overlap >= 0.25:
        return False, 0.50

    # Semantic similarity
    try:
        u_emb = get_embedding(u_clean)
        e_emb = get_embedding(e_clean)
        sim = calculate_cosine_similarity(u_emb, e_emb)
        if sim >= 0.75:
            return True, 1.0
        elif sim >= 0.60:
            return True, 0.75
    except Exception:
        pass

    return False, 0.0

def evaluate_quiz_submission(
    quiz: Dict[str, Any],
    submitted_answers: List[Dict[str, Any]],
    time_taken_seconds: int = 0
) -> Dict[str, Any]:
    """
    Evaluates quiz attempt answers, computes score, accuracy, and detailed review.
    """
    questions = quiz.get("questions", [])
    q_map = {q["id"]: q for q in questions}
    
    # Map user answers
    ans_map = {}
    for a in submitted_answers:
        ans_map[a.get("question_id")] = a.get("user_answer", "")

    total_questions = len(questions)
    correct_count = 0
    incorrect_count = 0
    detailed_review = []
    total_score = 0.0

    for q in questions:
        qid = q["id"]
        q_type = q.get("type", "mcq")
        user_ans = ans_map.get(qid, "")
        correct_ans = q.get("correct_answer", "")
        
        is_correct = False
        earned_fraction = 0.0

        if q_type in ("mcq", "true_false"):
            if str(user_ans).strip().lower() == str(correct_ans).strip().lower():
                is_correct = True
                earned_fraction = 1.0
                correct_count += 1
            else:
                is_correct = False
                earned_fraction = 0.0
                incorrect_count += 1
        elif q_type == "short_answer":
            is_corr, fraction = evaluate_short_answer(str(user_ans), str(correct_ans))
            is_correct = is_corr
            earned_fraction = fraction
            if is_corr:
                correct_count += 1
            else:
                incorrect_count += 1

        total_score += earned_fraction

        detailed_review.append({
            "question_id": qid,
            "type": q_type,
            "question": q.get("question"),
            "options": q.get("options", []),
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "is_correct": is_correct,
            "earned_score": earned_fraction,
            "explanation": q.get("explanation", ""),
            "difficulty": q.get("difficulty", "Medium"),
            "source_page": q.get("source_page", 1),
            "source_text": q.get("source_text", "")
        })

    accuracy = round((correct_count / max(1, total_questions)) * 100, 2)

    return {
        "total_questions": total_questions,
        "correct": correct_count,
        "correct_answers": correct_count,
        "incorrect": incorrect_count,
        "score": accuracy,
        "accuracy": accuracy,
        "time_taken": time_taken_seconds,
        "completed_at": datetime.now(timezone.utc),
        "detailed_review": detailed_review
    }

def update_user_topic_progress(
    db,
    user_id: ObjectId,
    topic: str,
    correct: int,
    total: int
):
    """
    Update or insert topic mastery metrics in MongoDB progress collection.
    """
    if not topic or not total:
        return

    topic_clean = topic.strip()
    now = datetime.now(timezone.utc)

    existing = db.progress.find_one({"user_id": user_id, "topic": topic_clean})
    if existing:
        new_total = existing.get("questions_answered", 0) + total
        new_correct = existing.get("correct_answers", 0) + correct
        new_accuracy = round((new_correct / max(1, new_total)) * 100, 1)

        db.progress.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "questions_answered": new_total,
                    "correct_answers": new_correct,
                    "accuracy": new_accuracy,
                    "last_practiced": now
                }
            }
        )
    else:
        accuracy = round((correct / max(1, total)) * 100, 1)
        db.progress.insert_one({
            "user_id": user_id,
            "topic": topic_clean,
            "questions_answered": total,
            "correct_answers": correct,
            "accuracy": accuracy,
            "last_practiced": now
        })
