"""
RetrieverAgent with robust fallback.

Primary: embed query -> vector search (VectorTool.search)
Fallback: local text search over data/chunks/*.json (case-insensitive substring match)

This keeps the system working even when the placeholder embedder is non-semantic.
"""
from typing import List, Dict, Any
import os
import json
import glob
import heapq
import re
import itertools

from src.agents.embedding_agent import EmbeddingAgent
from src.tools.vector_tool import VectorTool

DATA_DIR = os.environ.get("SECOND_BRAIN_DATA_DIR", "data/chunks")

class RetrieverAgent:
    def __init__(self, embedder: EmbeddingAgent = None, vector_tool: VectorTool = None):
        self.embedder = embedder or EmbeddingAgent()
        self.vector_tool = vector_tool or VectorTool()

    async def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        # 1) embed + vector search
        vecs = await self.embedder.embed_texts([query])
        qvec = vecs[0]
        hits = await self.vector_tool.search(qvec, top_k=top_k)

        # normalize if any hits
        normalized = []
        for h in hits:
            normalized.append({
                "text": h.get("text"),
                "source_id": h.get("source_id"),
                "chunk_index": h.get("chunk_index"),
                "page": h.get("page"),
                "chunk_id": h.get("chunk_id") or h.get("id") or None,
            })

        if normalized:
            return normalized

        # 2) Fallback: local substring search over persisted chunk files
        return self._local_text_search(query, top_k)

    def _local_text_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Very simple local search:
        - loads all JSON files under data/chunks/*.json
        - scores chunks by number of occurrences of query terms (case-insensitive)
        - returns top_k chunks with highest score

        Uses a tie-breaker counter to avoid heap comparison issues when scores tie.
        """
        if not os.path.exists(DATA_DIR):
            return []

        q = query.strip().lower()
        if not q:
            return []

        # simple tokenization: words and phrases fallback
        terms = re.findall(r"\w+", q)

        heap = []  # min-heap of (score, tie_breaker, chunk_dict) for top-k
        tie_counter = itertools.count()  # unique increasing integers as tie-breakers

        for path in glob.glob(os.path.join(DATA_DIR, "*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
            except Exception:
                continue

            for ch in chunks:
                text = (ch.get("text") or "").lower()
                if not text:
                    continue
                # score by occurrences of full query and individual terms (weighted)
                score = 0
                # full phrase match higher weight
                score += text.count(q) * 10
                for t in terms:
                    score += text.count(t)
                if score <= 0:
                    continue
                chunk_obj = {
                    "text": ch.get("text"),
                    "source_id": ch.get("meta", {}).get("source_id"),
                    "chunk_index": ch.get("meta", {}).get("chunk_index"),
                    "page": ch.get("meta", {}).get("page"),
                    "chunk_id": ch.get("id"),
                }
                tie = next(tie_counter)
                item = (score, tie, chunk_obj)
                if len(heap) < top_k:
                    heapq.heappush(heap, item)
                else:
                    # pushpop keeps the heap size fixed and maintains smallest at root
                    heapq.heappushpop(heap, item)

        if not heap:
            return []

        # Convert heap to sorted list by score descending then tie ascending
        largest = heapq.nlargest(len(heap), heap)
        # Extract chunk dicts in descending score order
        results = [t[2] for t in largest]
        return results
