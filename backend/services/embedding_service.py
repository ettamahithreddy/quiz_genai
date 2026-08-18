import os
import logging
import numpy as np
from typing import List, Union
from google import genai

logger = logging.getLogger(__name__)

def compute_fallback_embedding(text: str, dim: int = 768) -> List[float]:
    words = text.lower().split()
    if not words:
        return [0.0] * dim

    vec = np.zeros(dim, dtype=np.float32)
    for w in words:
        h = hash(w) % dim
        vec[h] += 1.0
        for i in range(len(w) - 1):
            sub_h = hash(w[i:i+2]) % dim
            vec[sub_h] += 0.5

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()

def get_embedding(text: str) -> List[float]:
    if not text or not text.strip():
        return [0.0] * 768

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.embed_content(
            model='text-embedding-004',
            contents=text.strip()
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error("API embedding error: %s", str(e))
        return compute_fallback_embedding(text)

def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.embed_content(
            model='text-embedding-004',
            contents=[t.strip() for t in texts]
        )
        return [emb.values for emb in response.embeddings]
    except Exception as e:
        logger.error("Batch API embedding error: %s", str(e))
        return [compute_fallback_embedding(t) for t in texts]

def calculate_cosine_similarity(vec_a: Union[List[float], np.ndarray], vec_b: Union[List[float], np.ndarray]) -> float:
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))