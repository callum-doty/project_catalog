# app/utils/vector_utils.py
import numpy as np
from typing import List, Union

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
        
    # Convert to numpy arrays if they aren't already
    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)
    
    # Calculate cosine similarity
    dot_product = np.dot(vec1_array, vec2_array)
    norm_a = np.linalg.norm(vec1_array)
    norm_b = np.linalg.norm(vec2_array)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    return dot_product / (norm_a * norm_b)

def rank_by_similarity(query_embedding: List[float], 
                       document_embeddings: List[Union[List[float], None]],
                       document_ids: List[int],
                       threshold: float = 0.7) -> List[tuple]:
    """Rank documents by similarity to query embedding"""
    if not query_embedding:
        return []
    
    similarities = []
    for i, doc_embedding in enumerate(document_embeddings):
        if doc_embedding:
            similarity = cosine_similarity(query_embedding, doc_embedding)
            if similarity >= threshold:
                similarities.append((document_ids[i], similarity))
    
    # Sort by similarity (highest first)
    return sorted(similarities, key=lambda x: x[1], reverse=True)