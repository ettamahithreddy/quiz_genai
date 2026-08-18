import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from bson import ObjectId

from backend.config import Config
from backend.utils.db import get_db
from backend.utils.auth import auth_required
from backend.utils.validators import validate_file_upload
from backend.services.pdf_service import extract_text_from_pdf, extract_text_from_plain_text
from backend.services.rag_service import create_chunks_from_pages

logger = logging.getLogger(__name__)
materials_bp = Blueprint("materials", __name__, url_prefix="/api/materials")

# Ensure upload directory exists
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

@materials_bp.route("/upload", methods=["POST"])
@auth_required
def upload_material():
    """
    Upload study material: PDF file or pasted text notes.
    Extracts text, splits into RAG chunks, computes embeddings, and stores in MongoDB.
    """
    user_id = request.user_id
    db = get_db()
    
    # Check if multipart file upload
    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file."}), 400

        # Read file length to validate size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        is_valid, err_msg = validate_file_upload(file.filename, file_size)
        if not is_valid:
            return jsonify({"error": err_msg}), 400

        filename = secure_filename(file.filename)
        # Unique disk filename
        timestamp_prefix = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_filename = f"{user_id}_{timestamp_prefix}_{filename}"
        saved_path = os.path.join(Config.UPLOAD_FOLDER, saved_filename)
        
        file.save(saved_path)

        try:
            # Extract text page-by-page
            if filename.lower().endswith(".pdf"):
                extraction = extract_text_from_pdf(saved_path)
                file_type = "pdf"
            else:
                with open(saved_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                extraction = extract_text_from_plain_text(content, title=filename)
                file_type = "text"

        except Exception as e:
            logger.error("Text extraction failed: %s", str(e))
            if os.path.exists(saved_path):
                os.remove(saved_path)
            return jsonify({"error": "Failed to parse study material.", "detail": str(e)}), 422

    else:
        # JSON pasted text payload
        data = request.get_json(silent=True) or {}
        text_content = data.get("text", "").strip()
        title = data.get("title", "").strip() or "Pasted Notes"

        if not text_content:
            return jsonify({"error": "Please provide study text or upload a PDF file."}), 400

        filename = f"{title}.txt"
        file_size = len(text_content.encode("utf-8"))
        saved_path = None
        file_type = "text"
        extraction = extract_text_from_plain_text(text_content, title=title)

    # Insert material record
    material_doc = {
        "user_id": user_id,
        "file_name": filename,
        "file_type": file_type,
        "file_size": file_size,
        "page_count": extraction.get("total_pages", 1),
        "total_words": extraction.get("total_words", 0),
        "total_characters": extraction.get("total_characters", 0),
        "raw_text": extraction.get("full_text", "")[:10000],  # preview snippet
        "file_path": saved_path,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = db.materials.insert_one(material_doc)
    material_id = result.inserted_id

    # Create and embed chunks
    chunks = create_chunks_from_pages(
        pages=extraction.get("pages", []),
        material_id=material_id,
        user_id=user_id
    )

    # Save chunks in material or separate chunks field
    db.materials.update_one(
        {"_id": material_id},
        {"$set": {"chunks": chunks, "chunk_count": len(chunks)}}
    )

    return jsonify({
        "message": "Study material processed successfully.",
        "material": {
            "id": str(material_id),
            "file_name": filename,
            "file_type": file_type,
            "file_size": file_size,
            "page_count": extraction.get("total_pages", 1),
            "total_words": extraction.get("total_words", 0),
            "chunk_count": len(chunks)
        }
    }), 201

@materials_bp.route("", methods=["GET"])
@auth_required
def list_materials():
    """List all study materials for authenticated user with quiz stats."""
    user_id = request.user_id
    db = get_db()

    cursor = db.materials.find({"user_id": user_id}).sort("created_at", -1)
    materials_list = []

    for mat in cursor:
        mat_id = mat["_id"]
        # Count quizzes generated from this material
        quiz_count = db.quizzes.count_documents({"material_id": mat_id, "user_id": user_id})
        
        materials_list.append({
            "id": str(mat_id),
            "file_name": mat.get("file_name", "Untitled"),
            "file_type": mat.get("file_type", "pdf"),
            "file_size": mat.get("file_size", 0),
            "page_count": mat.get("page_count", 1),
            "total_words": mat.get("total_words", 0),
            "chunk_count": mat.get("chunk_count", len(mat.get("chunks", []))),
            "quizzes_generated": quiz_count,
            "created_at": mat.get("created_at").isoformat() if mat.get("created_at") else None
        })

    return jsonify({"materials": materials_list}), 200

@materials_bp.route("/<material_id>", methods=["GET"])
@auth_required
def get_material_detail(material_id: str):
    """Retrieve single study material detail."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(material_id)
    except Exception:
        return jsonify({"error": "Invalid material ID."}), 400

    mat = db.materials.find_one({"_id": oid, "user_id": user_id})
    if not mat:
        return jsonify({"error": "Material not found or access denied."}), 404

    chunks_preview = []
    for c in mat.get("chunks", [])[:15]:
        chunks_preview.append({
            "chunk_id": c.get("chunk_id"),
            "page_number": c.get("page_number", 1),
            "chunk_text": c.get("chunk_text", ""),
            "char_count": c.get("char_count", 0)
        })

    return jsonify({
        "material": {
            "id": str(mat["_id"]),
            "file_name": mat.get("file_name"),
            "file_type": mat.get("file_type"),
            "file_size": mat.get("file_size", 0),
            "page_count": mat.get("page_count", 1),
            "total_words": mat.get("total_words", 0),
            "chunk_count": len(mat.get("chunks", [])),
            "chunks_preview": chunks_preview,
            "created_at": mat.get("created_at").isoformat() if mat.get("created_at") else None
        }
    }), 200

@materials_bp.route("/<material_id>", methods=["DELETE"])
@auth_required
def delete_material(material_id: str):
    """Delete study material and clean up files."""
    user_id = request.user_id
    db = get_db()

    try:
        oid = ObjectId(material_id)
    except Exception:
        return jsonify({"error": "Invalid material ID."}), 400

    mat = db.materials.find_one({"_id": oid, "user_id": user_id})
    if not mat:
        return jsonify({"error": "Material not found or access denied."}), 404

    # Remove file on disk if exists
    file_path = mat.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning("Could not delete file from disk: %s", str(e))

    db.materials.delete_one({"_id": oid, "user_id": user_id})
    return jsonify({"message": "Material deleted successfully."}), 200
