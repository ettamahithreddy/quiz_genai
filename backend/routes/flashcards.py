import logging
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from bson import ObjectId

from backend.utils.db import get_db
from backend.utils.auth import auth_required
from backend.services.rag_service import retrieve_relevant_context, create_chunks_from_pages
from backend.services.pdf_service import extract_text_from_plain_text
from backend.services.topic_service import normalize_topic
from backend.services.ai_service import generate_flashcards_with_ai, generate_topic_flashcards_with_ai

logger = logging.getLogger(__name__)
flashcards_bp = Blueprint("flashcards", __name__, url_prefix="/api/flashcards")

@flashcards_bp.route("/generate", methods=["POST"])
@auth_required
def generate_flashcards():
    """
    Generate study flashcards from uploaded material (RAG) or topic (Scenario B).
    """
    user_id = request.user_id
    db = get_db()
    data = request.get_json(silent=True) or {}

    logger.info("[FLASHCARD] Request received")
    logger.info("[FLASHCARD] User authenticated")

    material_id_str = data.get("material_id", "").strip()
    topic = data.get("topic", "").strip()
    num_cards = int(data.get("num_cards", 10))
    pasted_text = data.get("text", "").strip()

    context_chunks = []
    target_mat_id = None
    material_title = "Study Flashcards"
    norm_topic = normalize_topic(topic) if topic else ""

    if topic:
        logger.info("[FLASHCARD] Topic: %s", norm_topic)

    logger.info("[FLASHCARD] Generating...")

    # MODE A: From Uploaded Material ID
    if material_id_str:
        try:
            m_oid = ObjectId(material_id_str)
            material_doc = db.materials.find_one({"_id": m_oid, "user_id": user_id})
            if not material_doc:
                return jsonify({"error": "Material not found or access denied."}), 404
            target_mat_id = m_oid
            material_title = material_doc.get("file_name", "Material")
            chunks = material_doc.get("chunks", [])
            context_chunks, _ = retrieve_relevant_context(chunks, topic=topic, top_k=12)
            
            result = generate_flashcards_with_ai(
                context_chunks=context_chunks,
                num_cards=num_cards,
                topic=topic,
                material_title=material_title
            )
            cards = result.get("flashcards", [])
        except Exception as e:
            return jsonify({"error": f"Invalid material lookup: {str(e)}"}), 400

    # MODE A: From Pasted Text
    elif pasted_text:
        extraction = extract_text_from_plain_text(pasted_text, title=topic or "Pasted Notes")
        chunks = create_chunks_from_pages(extraction.get("pages", []), user_id=user_id)
        context_chunks, _ = retrieve_relevant_context(chunks, topic=topic, top_k=12)
        material_title = topic or "Pasted Notes"
        
        result = generate_flashcards_with_ai(
            context_chunks=context_chunks,
            num_cards=num_cards,
            topic=topic,
            material_title=material_title
        )
        cards = result.get("flashcards", [])

    # MODE B: Topic Only Mode
    elif topic:
        material_title = norm_topic
        result = generate_topic_flashcards_with_ai(
            topic=norm_topic,
            num_cards=num_cards
        )
        cards = result.get("flashcards", [])

    else:
        return jsonify({"error": "Please provide a material ID, topic, or study text."}), 400

    logger.info("[FLASHCARD] Validation completed")

    if not cards:
        return jsonify({"error": "Could not generate flashcards from provided topic/material."}), 422

    deck_title = f"{norm_topic or material_title} Flashcards"
    deck_doc = {
        "user_id": user_id,
        "material_id": target_mat_id,
        "title": deck_title,
        "topic": norm_topic or material_title,
        "card_count": len(cards),
        "cards": cards,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    res = db.flashcards.insert_one(deck_doc)
    deck_id = str(res.inserted_id)

    logger.info("[FLASHCARD] Saved to MongoDB (ID: %s)", deck_id)

    return jsonify({
        "success": True,
        "message": "Flashcards created successfully.",
        "deck": {
            "id": deck_id,
            "title": deck_doc["title"],
            "topic": deck_doc["topic"],
            "card_count": len(cards),
            "cards": cards,
            "created_at": deck_doc["created_at"].isoformat()
        },
        "flashcards": cards
    }), 201

@flashcards_bp.route("", methods=["GET"])
@auth_required
def list_flashcard_decks():
    """List all flashcard decks for the authenticated user."""
    user_id = request.user_id
    db = get_db()

    cursor = db.flashcards.find({"user_id": user_id}).sort("created_at", -1)
    decks = []
    for d in cursor:
        cards = d.get("cards", [])
        mastered_count = sum(1 for c in cards if c.get("mastered", False))
        decks.append({
            "id": str(d["_id"]),
            "title": d.get("title", "Untitled Deck"),
            "topic": d.get("topic", "General"),
            "card_count": len(cards),
            "mastered_count": mastered_count,
            "created_at": d.get("created_at").isoformat() if d.get("created_at") else None
        })

    return jsonify({
        "success": True,
        "decks": decks
    }), 200

@flashcards_bp.route("/<deck_id>", methods=["GET"])
@auth_required
def get_flashcard_deck(deck_id: str):
    """Retrieve single flashcard deck for authenticated user."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(deck_id)
    except Exception:
        return jsonify({"error": "Invalid deck ID."}), 400

    deck = db.flashcards.find_one({"_id": oid, "user_id": user_id})
    if not deck:
        return jsonify({"error": "Deck not found."}), 404

    cards = deck.get("cards", [])
    return jsonify({
        "success": True,
        "deck": {
            "id": str(deck["_id"]),
            "title": deck.get("title"),
            "topic": deck.get("topic"),
            "card_count": len(cards),
            "cards": cards,
            "created_at": deck.get("created_at").isoformat() if deck.get("created_at") else None
        },
        "flashcards": cards
    }), 200

@flashcards_bp.route("/<deck_id>/cards/<card_id>", methods=["PUT"])
@auth_required
def update_card_mastery(deck_id: str, card_id: str):
    """Update mastery status and difficulty rating of a card."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(deck_id)
    except Exception:
        return jsonify({"error": "Invalid deck ID."}), 400

    deck = db.flashcards.find_one({"_id": oid, "user_id": user_id})
    if not deck:
        return jsonify({"error": "Deck not found."}), 404

    data = request.get_json(silent=True) or {}
    mastered = data.get("mastered", False)
    difficulty_rating = data.get("difficulty_rating", "normal")

    cards = deck.get("cards", [])
    updated = False
    for c in cards:
        if c.get("id") == card_id:
            c["mastered"] = bool(mastered)
            c["difficulty_rating"] = difficulty_rating
            updated = True
            break

    if not updated:
        return jsonify({"error": "Card not found in deck."}), 404

    db.flashcards.update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"cards": cards, "updated_at": datetime.now(timezone.utc)}}
    )

    return jsonify({"success": True, "message": "Card updated successfully."}), 200

@flashcards_bp.route("/<deck_id>", methods=["DELETE"])
@auth_required
def delete_flashcard_deck(deck_id: str):
    """Delete a flashcard deck."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(deck_id)
    except Exception:
        return jsonify({"error": "Invalid deck ID."}), 400

    res = db.flashcards.delete_one({"_id": oid, "user_id": user_id})
    if res.deleted_count == 0:
        return jsonify({"error": "Deck not found."}), 404

    return jsonify({"success": True, "message": "Deck deleted successfully."}), 200
