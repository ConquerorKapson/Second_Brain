"""
IngestAgent - chunking & file processing (fixed merge logic)

Responsibilities:
 - normalize content (text / pdf)
 - chunk text into sentence-aware chunks
 - ensure each chunk <= chunk_size_chars (char-based)
 - avoid overly aggressive post-merge that creates giant chunks
"""
import re
import uuid
from typing import List, Dict, Optional
from src.utils.file_parsers import parse_pdf_bytes, parse_text_bytes, detect_file_type_from_bytes

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

class IngestAgent:
    def __init__(self, chunk_size_chars: int = 800, min_chunk_chars: int = 200):
        """
        chunk_size_chars - approximate max characters per chunk (not tokens)
        min_chunk_chars - try not to emit very small chunks
        """
        self.chunk_size_chars = chunk_size_chars
        self.min_chunk_chars = min_chunk_chars

    def _split_into_sentences(self, text: str) -> List[str]:
        sentences = _SENTENCE_SPLIT_RE.split(text.strip())
        return [s.strip() for s in sentences if s and s.strip()]

    def _split_long_text(self, text: str) -> List[str]:
        """
        If a single sentence or piece is longer than chunk_size_chars,
        split it into multiple pieces by simple character slices at word boundaries.
        """
        if len(text) <= self.chunk_size_chars:
            return [text]
        parts = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + self.chunk_size_chars, n)
            # Try to backtrack to last space for nicer split
            if end < n:
                last_space = text.rfind(" ", start, end)
                if last_space > start:
                    end = last_space
            part = text[start:end].strip()
            if part:
                parts.append(part)
            start = end
        return parts

    def _aggregate_sentences_to_chunks(self, sentences: List[str], source_id: str, page: Optional[int] = None) -> List[Dict]:
        chunks = []
        buffer = []
        buffer_len = 0
        idx = 0

        for sent in sentences:
            s_len = len(sent)
            # If sentence itself is very long, split it
            if s_len > self.chunk_size_chars:
                # flush current buffer first
                if buffer:
                    text = " ".join(buffer).strip()
                    if text:
                        chunks.append({
                            "id": f"{source_id}::chunk::{idx}::{uuid.uuid4().hex[:8]}",
                            "text": text,
                            "meta": {"source_id": source_id, "chunk_index": idx, "page": page, "char_len": len(text)}
                        })
                        idx += 1
                    buffer = []
                    buffer_len = 0
                # split the long sentence into parts and add each as its own chunk
                parts = self._split_long_text(sent)
                for part in parts:
                    chunks.append({
                        "id": f"{source_id}::chunk::{idx}::{uuid.uuid4().hex[:8]}",
                        "text": part,
                        "meta": {"source_id": source_id, "chunk_index": idx, "page": page, "char_len": len(part)}
                    })
                    idx += 1
                continue

            # normal flow: try to append sentence to buffer
            if buffer_len + s_len + 1 <= self.chunk_size_chars:
                buffer.append(sent)
                buffer_len += s_len + 1
            else:
                # emit buffer as chunk
                text = " ".join(buffer).strip()
                if text:
                    chunks.append({
                        "id": f"{source_id}::chunk::{idx}::{uuid.uuid4().hex[:8]}",
                        "text": text,
                        "meta": {"source_id": source_id, "chunk_index": idx, "page": page, "char_len": len(text)}
                    })
                    idx += 1
                # start new buffer with current sentence
                buffer = [sent]
                buffer_len = s_len + 1

        # emit last buffer
        if buffer:
            text = " ".join(buffer).strip()
            if text:
                chunks.append({
                    "id": f"{source_id}::chunk::{idx}::{uuid.uuid4().hex[:8]}",
                    "text": text,
                    "meta": {"source_id": source_id, "chunk_index": idx, "page": page, "char_len": len(text)}
                })

        # Post-process: merge *very small* chunks only if merged size <= chunk_size_chars
        merged: List[Dict] = []
        for c in chunks:
            if merged:
                prev = merged[-1]
                prev_len = prev["meta"]["char_len"]
                c_len = c["meta"]["char_len"]
                # merge only if prev is small AND merged result will not exceed chunk_size_chars
                if prev_len < self.min_chunk_chars and (prev_len + 1 + c_len) <= self.chunk_size_chars:
                    prev["text"] = (prev["text"] + " " + c["text"]).strip()
                    prev["meta"]["char_len"] = len(prev["text"])
                    # keep prev["meta"]["chunk_index"] as-is (we don't renumber)
                    continue
            # otherwise append as new chunk
            merged.append(c)

        return merged

    async def process_text(self, text: str, source_id: Optional[str] = None) -> List[Dict]:
        if source_id is None:
            source_id = f"txt-{uuid.uuid4().hex[:8]}"
        sentences = self._split_into_sentences(text)
        if not sentences:
            return [{
                "id": f"{source_id}::chunk::0::{uuid.uuid4().hex[:8]}",
                "text": text,
                "meta": {"source_id": source_id, "chunk_index": 0, "page": None, "char_len": len(text)}
            }]
        chunks = self._aggregate_sentences_to_chunks(sentences, source_id=source_id, page=None)
        return chunks

    async def process_file_bytes(self, file_bytes: bytes, filename: str = "") -> List[Dict]:
        ftype = detect_file_type_from_bytes(file_bytes, filename)
        source_id = filename or f"file-{uuid.uuid4().hex[:8]}"
        result_chunks = []
        if ftype == "pdf":
            pages = parse_pdf_bytes(file_bytes)
            for p_idx, page_text in enumerate(pages):
                if not page_text or not page_text.strip():
                    continue
                sentences = self._split_into_sentences(page_text)
                page_chunks = self._aggregate_sentences_to_chunks(sentences, source_id=source_id, page=p_idx)
                result_chunks.extend(page_chunks)
        else:
            texts = parse_text_bytes(file_bytes)
            for t in texts:
                chunks = await self.process_text(t, source_id=source_id)
                result_chunks.extend(chunks)
        return result_chunks
