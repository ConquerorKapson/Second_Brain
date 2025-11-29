"""
RAGAgent (simple composer)

Responsibilities:
- Accept query + retrieved chunks
- Compose a prompt for a model and return an answer + sources
- For now: a lightweight, deterministic composer (no external LLM).
  Replace `generate_answer` with a real LLM call when ready.
"""

from typing import List, Dict, Any

class RAGAgent:
    def __init__(self, max_context_chars: int = 2000):
        self.max_context_chars = max_context_chars

    def _build_context(self, query: str, hits: List[Dict[str, Any]]) -> str:
        """
        Simple aggregator: concatenate top hits up to max_context_chars.
        """
        ctx_parts = []
        total = 0
        for h in hits:
            t = h.get("text", "")
            if not t:
                continue
            if total + len(t) > self.max_context_chars:
                # truncate if necessary
                remaining = self.max_context_chars - total
                if remaining <= 0:
                    break
                t = t[:remaining]
            ctx_parts.append(f"Source ({h.get('source_id')}:{h.get('chunk_index')}): {t}")
            total += len(t)
        return "\n\n".join(ctx_parts)

    def generate_answer(self, query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Placeholder answer generator. It creates a short summary by simple heuristics.
        Replace this function with a real LLM call (via ADK model tool / Vertex / OpenAI) later.
        Returns: {"answer": str, "sources": [...]}
        """
        context = self._build_context(query, hits)
        if not context:
            answer = "I couldn't find relevant information in your memory."
        else:
            # Very simple "summary": take the first 1-2 sentences of the concatenated context
            # This is intentionally naive — swap out for LLM later.
            excerpt = context.split(".")
            first = excerpt[0].strip()
            second = ""
            if len(excerpt) > 1:
                second = excerpt[1].strip()
            answer = f"{first}. {second}".strip()

        # Build sources array
        sources = []
        for h in hits:
            sources.append({
                "chunk_id": h.get("chunk_id"),
                "source_id": h.get("source_id"),
                "chunk_index": h.get("chunk_index"),
                "page": h.get("page"),
            })

        return {"answer": answer, "sources": sources}
