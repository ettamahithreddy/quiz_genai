import math
import logging
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
from backend.config import Config
from backend.services.embedding_service import get_embeddings_batch, get_embedding, calculate_cosine_similarity

logger = logging.getLogger(__name__)

def create_chunks_from_pages(
    pages: List[Dict[str, Any]],
    material_id: Optional[ObjectId] = None,
    user_id: Optional[ObjectId] = None,
    chunk_size: int = Config.CHUNK_SIZE,
    chunk_overlap: int = Config.CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    """
    Split page texts into overlapping chunks, maintaining page number tracking.
    """
    all_chunks = []
    chunk_index = 0

    for page_data in pages:
        page_num = page_data.get("page_number", 1)
        text = page_data.get("text", "").strip()
        if not text:
            continue

        # If page text is smaller than chunk_size, create a single chunk for this page
        if len(text) <= chunk_size:
            chunk_obj = {
                "chunk_id": f"{material_id}_{chunk_index}" if material_id else f"chunk_{chunk_index}",
                "chunk_index": chunk_index,
                "material_id": material_id,
                "user_id": user_id,
                "page_number": page_num,
                "chunk_text": text,
                "char_count": len(text)
            }
            all_chunks.append(chunk_obj)
            chunk_index += 1
            continue

        # Sliding window chunking with sentence/paragraph boundary preference
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # If not at the very end of page, try to break on a sentence (. / ! / ?) or paragraph boundary
            if end < text_len:
                boundary = -1
                search_sub = text[max(start, end - 80):end]
                for sep in ["\n\n", ".\n", ". ", "? ", "! "]:
                    pos = search_sub.rfind(sep)
                    if pos != -1:
                        boundary = max(start, end - 80) + pos + len(sep)
                        break
                
                if boundary != -1 and boundary > start + 80:
                    end = boundary

            chunk_text = text[start:end].strip()
            if len(chunk_text) >= 30:  # Include meaningful text chunks
                chunk_obj = {
                    "chunk_id": f"{material_id}_{chunk_index}" if material_id else f"chunk_{chunk_index}",
                    "chunk_index": chunk_index,
                    "material_id": material_id,
                    "user_id": user_id,
                    "page_number": page_num,
                    "chunk_text": chunk_text,
                    "char_count": len(chunk_text)
                }
                all_chunks.append(chunk_obj)
                chunk_index += 1

            if end >= text_len:
                break
            start = end - chunk_overlap

    # Batch compute embeddings for all chunks
    if all_chunks:
        texts_to_embed = [c["chunk_text"] for c in all_chunks]
        embeddings = get_embeddings_batch(texts_to_embed)
        for i, emb in enumerate(embeddings):
            all_chunks[i]["embedding"] = emb

    return all_chunks

def retrieve_relevant_context(
    chunks: List[Dict[str, Any]],
    topic: Optional[str] = None,
    top_k: int = 15,
    min_similarity: float = 0.10
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Retrieves the most relevant chunks using semantic cosine similarity & keyword relevance.
    If chunks are few (e.g. an uploaded article), preserves all chunks ranked by topic relevance.
    Returns: (list_of_selected_chunks, has_enough_topic_content)
    """
    if not chunks:
        return [], False

    topic_clean = topic.strip() if topic else ""

    if not topic_clean:
        if len(chunks) <= top_k:
            return chunks, True
        step = max(1, len(chunks) // top_k)
        selected = [chunks[i] for i in range(0, len(chunks), step)][:top_k]
        return selected, True

    # Topic is provided -> perform hybrid semantic + keyword scoring
    query_emb = get_embedding(topic_clean)
    topic_keywords = set(re_tokenize(topic_clean))

    scored_chunks = []
    for chunk in chunks:
        chunk_text = chunk.get("chunk_text", "")
        chunk_emb = chunk.get("embedding")
        
        if not chunk_emb:
            chunk_emb = get_embedding(chunk_text)
            chunk["embedding"] = chunk_emb

        sem_sim = calculate_cosine_similarity(query_emb, chunk_emb)
        chunk_words = set(re_tokenize(chunk_text))
        kw_overlap = len(topic_keywords.intersection(chunk_words)) / max(1, len(topic_keywords))
        phrase_bonus = 0.35 if topic_clean.lower() in chunk_text.lower() else 0.0

        hybrid_score = (0.60 * sem_sim) + (0.25 * kw_overlap) + (0.15 * phrase_bonus)

        scored_chunks.append({
            "chunk": chunk,
            "score": hybrid_score,
            "semantic_similarity": sem_sim,
            "keyword_overlap": kw_overlap
        })

    # Sort descending by relevance score
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    # If the document is small (<= top_k chunks), return all document chunks sorted by relevance
    if len(chunks) <= top_k:
        return [item["chunk"] for item in scored_chunks], True

    # Otherwise filter by minimal threshold
    relevant_chunks = [
        item["chunk"] for item in scored_chunks 
        if item["score"] >= min_similarity or item["keyword_overlap"] > 0
    ]

    if not relevant_chunks and scored_chunks:
        relevant_chunks = [scored_chunks[0]["chunk"]]

    selected_top_k = relevant_chunks[:top_k]
    has_sufficient = len(selected_top_k) >= 1

    return selected_top_k, has_sufficient

def estimate_question_capacity(chunks: List[Dict[str, Any]]) -> int:
    """
    Estimates the maximum number of reliable questions that can be generated
    from the supplied chunks without redundancy.
    A standard paragraph of 300+ characters supports multiple questions across MCQ, True/False, and Short Answer.
    """
    if not chunks:
        return 0
    
    total_chars = sum(len(c.get("chunk_text", "")) for c in chunks)
    if total_chars < 100:
        return 1
    elif total_chars < 200:
        return 3
    elif total_chars < 400:
        return 8
    elif total_chars < 800:
        return 20
    else:
        return max(30, math.floor(total_chars / 50))

def re_tokenize(text: str) -> List[str]:
    """Helper to extract clean lowercase alphanumeric tokens."""
    import re
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", text) if len(w) > 2]
