"""
RootAgent skeleton for ADK.

Implements high-level orchestration:
 - receives requests (ingest/query)
 - dispatches to sub-agents or tools
 - composes final responses

Replace placeholder logic with ADK BaseAgent usage and proper async calls.
"""
"""
RootAgent: orchestrates ingestion and persistence for now.

Eventually this will call embedding agent & vector upserts.
"""
"""
RootAgent: Ingestion + Embeddings + Vector Upsert
"""
import os
import json
from typing import Dict, Any, List
from src.agents.ingest_agent import IngestAgent
from src.agents.embedding_agent import EmbeddingAgent
from src.agents.retriever_agent import RetrieverAgent
from src.agents.rag_agent import RAGAgent
from src.tools.vector_tool import VectorTool

DATA_DIR = os.environ.get("SECOND_BRAIN_DATA_DIR", "data/chunks")

class RootAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.ingest_agent = IngestAgent()
        self.embedder = EmbeddingAgent()
        self.vector_tool = VectorTool()
        self.retriever = RetrieverAgent(embedder=self.embedder, vector_tool=self.vector_tool)
        self.rag = RAGAgent()
        os.makedirs(DATA_DIR, exist_ok=True)

    async def handle_ingest(self, *, content: str = None, file_bytes: bytes = None, filename: str = "") -> Dict[str, Any]:
        # Step 1: chunking
        if file_bytes:
            chunks = await self.ingest_agent.process_file_bytes(file_bytes, filename=filename)
        else:
            chunks = await self.ingest_agent.process_text(content)

        if not chunks:
            return {"status": "error", "ingested_chunks": 0}

        source_id = chunks[0]["meta"]["source_id"]

        # Step 2: embeddings
        texts = [c["text"] for c in chunks]
        vectors = await self.embedder.embed_texts(texts)

        # Step 3: upsert into Weaviate
        for c, vec in zip(chunks, vectors):
            await self.vector_tool.upsert(
                id=c["id"],
                vector=vec,
                metadata=c["meta"],
                text=c["text"],
            )

        # Step 4: persist chunks locally
        out_path = os.path.join(DATA_DIR, f"{source_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        return {"status": "ok", "ingested_chunks": len(chunks), "source_id": source_id}

    async def handle_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Orchestrate retrieval + RAG.
        Returns: {"answer": "...", "sources": [...]}
        """
        # 1) retrieve
        hits = await self.retriever.retrieve(query, top_k=top_k)

        # 2) generate answer via RAG agent
        result = self.rag.generate_answer(query, hits)

        return result