from flask import Blueprint, request, jsonify
from datetime import datetime, timezone
from backend.utils.db import get_db
from backend.utils.auth import auth_required

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api")

@dashboard_bp.route("/dashboard", methods=["GET"])
@auth_required
def get_dashboard_summary():
    """
    Returns aggregated student metrics, recent attempts, weak topics, and chart data.
    """
    user_id = request.user_id
    db = get_db()

    # 1. User's Completed Quiz Attempts (sorted chronologically for progression)
    attempts_chronological = list(
        db.attempts.find({"user_id": user_id}).sort([("completed_at", 1), ("submitted_at", 1)])
    )
    total_quizzes_count = len(attempts_chronological)
    total_attempts = total_quizzes_count

    # 3. Aggregations across completed quizzes
    total_questions_answered = sum(int(a.get("total_questions", 0)) for a in attempts_chronological)
    total_correct = sum(
        int(a.get("correct_answers") if a.get("correct_answers") is not None else a.get("correct", 0))
        for a in attempts_chronological
    )
    
    accuracies = []
    for a in attempts_chronological:
        acc = a.get("accuracy")
        if acc is not None:
            try:
                accuracies.append(float(acc))
            except (ValueError, TypeError):
                pass
        else:
            tot = a.get("total_questions", 0)
            if tot > 0:
                corr = a.get("correct_answers") if a.get("correct_answers") is not None else a.get("correct", 0)
                accuracies.append((float(corr) / float(tot)) * 100.0)

    # Average score = sum of all completed quiz accuracies / number of completed quizzes
    if accuracies:
        avg_score_raw = sum(accuracies) / len(accuracies)
        average_score = round(avg_score_raw, 2)
        best_score = round(max(accuracies), 2)
    else:
        average_score = 0
        best_score = 0

    # 4. Recent Quizzes (last 5)
    recent_quizzes = []
    recent_cursor = db.quizzes.find({"user_id": user_id}).sort("created_at", -1).limit(5)
    for q in recent_cursor:
        recent_quizzes.append({
            "id": str(q["_id"]),
            "title": q.get("title", "Untitled Quiz"),
            "topic": q.get("topic", "General"),
            "difficulty": q.get("difficulty", "mixed"),
            "question_count": len(q.get("questions", [])),
            "share_code": q.get("share_code"),
            "created_at": q.get("created_at").isoformat() if q.get("created_at") else None
        })

    # 5. Weak Topics from progress collection (accuracy < 75%)
    progress_cursor = db.progress.find({"user_id": user_id}).sort("accuracy", 1)
    topic_progress = []
    weak_topics = []

    for p in progress_cursor:
        item = {
            "topic": p.get("topic", "General"),
            "questions_answered": p.get("questions_answered", 0),
            "correct_answers": p.get("correct_answers", 0),
            "accuracy": p.get("accuracy", 0),
            "last_practiced": p.get("last_practiced").isoformat() if p.get("last_practiced") else None
        }
        topic_progress.append(item)
        if item["accuracy"] < 75 and item["questions_answered"] >= 3:
            weak_topics.append(item)

    # If no weak topics identified yet but some topics exist, suggest the lowest accuracy topic
    if not weak_topics and topic_progress:
        weak_topics.append(topic_progress[0])

    # 6. Score Progression for Chart (Chronological order: Quiz 1, Quiz 2, Quiz 3...)
    score_history_labels = []
    score_history_data = []
    progression_list = []

    for idx, att in enumerate(attempts_chronological):
        acc = att.get("accuracy")
        if acc is None:
            tot = att.get("total_questions", 0)
            corr = att.get("correct_answers") if att.get("correct_answers") is not None else att.get("correct", 0)
            acc = (float(corr) / float(tot)) * 100.0 if tot > 0 else 0.0
        acc_val = round(float(acc), 2)
        label = f"Quiz {idx + 1}"
        score_history_labels.append(label)
        score_history_data.append(acc_val)
        progression_list.append({
            "attempt": idx + 1,
            "quiz_label": label,
            "accuracy": acc_val
        })

    return jsonify({
        "metrics": {
            "total_quizzes": total_quizzes_count,
            "total_attempts": total_attempts,
            "total_questions_answered": total_questions_answered,
            "total_correct": total_correct,
            "average_score": average_score,
            "best_score": best_score
        },
        "recent_quizzes": recent_quizzes,
        "weak_topics": weak_topics,
        "topic_progress": topic_progress,
        "chart_data": {
            "labels": score_history_labels,
            "scores": score_history_data,
            "progression": progression_list
        }
    }), 200

@dashboard_bp.route("/progress", methods=["GET"])
@auth_required
def get_user_progress():
    """Retrieve full topic-by-topic mastery stats."""
    user_id = request.user_id
    db = get_db()

    cursor = db.progress.find({"user_id": user_id}).sort("accuracy", 1)
    progress_list = []
    for p in cursor:
        progress_list.append({
            "id": str(p["_id"]),
            "topic": p.get("topic"),
            "questions_answered": p.get("questions_answered", 0),
            "correct_answers": p.get("correct_answers", 0),
            "accuracy": p.get("accuracy", 0),
            "last_practiced": p.get("last_practiced").isoformat() if p.get("last_practiced") else None
        })

    return jsonify({"progress": progress_list}), 200

@dashboard_bp.route("/analytics", methods=["GET"])
@auth_required
def get_analytics():
    """Detailed performance breakdowns."""
    user_id = request.user_id
    db = get_db()

    attempts = list(db.attempts.find({"user_id": user_id}))
    
    # Question type distribution
    type_stats = {"mcq": {"total": 0, "correct": 0}, "true_false": {"total": 0, "correct": 0}, "short_answer": {"total": 0, "correct": 0}}
    for att in attempts:
        for ans in att.get("answers", []):
            q_type = ans.get("type", "mcq")
            if q_type in type_stats:
                type_stats[q_type]["total"] += 1
                if ans.get("is_correct"):
                    type_stats[q_type]["correct"] += 1

    return jsonify({
        "type_breakdown": type_stats,
        "total_attempts": len(attempts)
    }), 200
