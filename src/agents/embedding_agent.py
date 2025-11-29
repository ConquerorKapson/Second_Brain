"""
EmbeddingAgent skeleton.

Responsibilities:
 - call embedding model (via ADK model tool or provider)
 - support batch embeddings and text normalization
"""
"""
EmbeddingAgent - temporary simple embedder
For now: deterministic pseudo-embedding using hashing.
Later in Block 6, we replace this with ADK model embeddings.
"""
import hashlib
import numpy as np
from typing import List

class EmbeddingAgent:
    def __init__(self, dim: int = 128):
        self.dim = dim

    def _hash_to_vector(self, text: str) -> List[float]:
        # deterministic hash → vector
        h = hashlib.md5(text.encode("utf-8")).hexdigest()
        # convert hex to numbers
        nums = [int(h[i:i+2], 16) / 255 for i in range(0, len(h), 2)]
        # pad/repeat to reach dimension
        vec = (nums * ((self.dim // len(nums)) + 1))[: self.dim]
        return vec

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]

