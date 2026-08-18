import logging
import numpy as np
from typing import List, Union

logger = logging.getLogger(__name__)

_model_instance = None
_model_failed = False

def get_sentence_transformer_model():
    """Lazily load sentence-transformers all-MiniLM-L6-v2 model."""
    global _model_instance, _model_failed
    if _model_instance is not None:
        return _model_instance
    if _model_failed:
        return None

    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers all-MiniLM-L6-v2 model...")
        _model_instance = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("SentenceTransformer model loaded successfully.")
        return _model_instance
    except Exception as e:
        logger.warning("Could not load sentence-transformers: %s. Using TF-IDF/Hashing fallback.", str(e))
        _model_failed = True
        return None

def compute_fallback_embedding(text: str, dim: int = 384) -> List[float]:
    """
    Deterministic TF-IDF & character n-gram projection fallback embedding.
    Produces unit-normalized 384-dimensional dense vectors.
    """
    words = text.lower().split()
    if not words:
        return [0.0] * dim

    vec = np.zeros(dim, dtype=np.float32)
    for w in words:
        # Word hash
        h = hash(w) % dim
        vec[h] += 1.0
        # Substring bi-grams
        for i in range(len(w) - 1):
            sub_h = hash(w[i:i+2]) % dim
            vec[sub_h] += 0.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def get_embedding(text: str) -> List[float]:
    """Generate dense vector embedding for single text string."""
    if not text or not text.strip():
        return [0.0] * 384

    model = get_sentence_transformer_model()
    if model is not None:
        try:
            emb = model.encode(text.strip(), convert_to_numpy=True)
            return emb.tolist()
        except Exception as e:
            logger.error("Error generating sentence-transformers embedding: %s", str(e))
            return compute_fallback_embedding(text)
    else:
        return compute_fallback_embedding(text)

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Batch generate vector embeddings."""
    if not texts:
        return []

    model = get_sentence_transformer_model()
    if model is not None:
        try:
            embs = model.encode([t.strip() for t in texts], batch_size=32, convert_to_numpy=True)
            return [e.tolist() for e in embs]
        except Exception as e:
            logger.error("Batch embedding error: %s", str(e))
            return [compute_fallback_embedding(t) for t in texts]
    else:
        return [compute_fallback_embedding(t) for t in texts]

def calculate_cosine_similarity(vec_a: Union[List[float], np.ndarray], vec_b: Union[List[float], np.ndarray]) -> float:
    """Calculate cosine similarity between two vectors (-1.0 to 1.0)."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))
