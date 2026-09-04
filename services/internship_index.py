"""Small persisted vector store for the internship knowledge base.

The default embedding is deterministic feature hashing, so the project runs locally
without a second API key or database service.  Set EMBEDDING_PROVIDER=gemini to use
Gemini embeddings when a compatible Gemini key/model is configured.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Any

DATASET_PATH = Path(os.getenv("INTERNSHIP_DATASET_PATH", "data/internships.json"))
INDEX_PATH = Path(os.getenv("INTERNSHIP_INDEX_PATH", "data/internship_vector_index.json"))
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
VECTOR_DIMENSIONS = int(os.getenv("VECTOR_DIMENSIONS", "384"))
CHUNK_SIZE = int(os.getenv("INTERNSHIP_CHUNK_SIZE", "850"))


class InternshipIndexError(Exception):
    """Raised for invalid datasets, index files, or embedding-provider failures."""


def _terms(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#.]{2,}", text.lower())


def _local_embedding(text: str) -> list[float]:
    """Hash words and adjacent word pairs into a normalized, stable vector."""
    vector = [0.0] * VECTOR_DIMENSIONS
    terms = _terms(text)
    features = terms + [f"{left}_{right}" for left, right in zip(terms, terms[1:])]
    for feature in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % VECTOR_DIMENSIONS
        vector[bucket] += 1.0 if digest[4] % 2 else -1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


def _embed(texts: list[str]) -> list[list[float]]:
    if EMBEDDING_PROVIDER == "local":
        return [_local_embedding(text) for text in texts]
    if EMBEDDING_PROVIDER != "gemini":
        raise InternshipIndexError("EMBEDDING_PROVIDER must be 'local' or 'gemini'.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise InternshipIndexError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini.")
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.embed_content(model=EMBEDDING_MODEL, contents=texts)
        return [list(item.values) for item in response.embeddings]
    except Exception as exc:
        raise InternshipIndexError("Could not generate Gemini embeddings.") from exc


def _internship_text(record: dict[str, Any]) -> str:
    def value(key: str) -> str:
        raw = record.get(key)
        return ", ".join(str(item) for item in raw) if isinstance(raw, list) else str(raw or "Not provided")

    return "\n".join(
        f"{label}: {value(key)}"
        for label, key in (
            ("Internship title", "title"), ("Company", "company"), ("Description", "description"),
            ("Required skills", "required_skills"), ("Preferred skills", "preferred_skills"),
            ("Eligibility", "eligibility"), ("Location", "location"), ("Duration", "duration"),
        )
    )


def _chunk(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text]
    words, chunks, start = text.split(), [], 0
    while start < len(words):
        piece = words[start : start + CHUNK_SIZE // 5]
        chunks.append(" ".join(piece))
        start += max(1, len(piece) - 25)
    return chunks


def _dataset() -> list[dict[str, Any]]:
    try:
        records = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InternshipIndexError("Could not read the internship dataset.") from exc
    if not isinstance(records, list) or not records:
        raise InternshipIndexError("The internship dataset must be a non-empty JSON array.")
    required = {"internship_id", "title", "company", "description"}
    if any(not isinstance(item, dict) or not required.issubset(item) for item in records):
        raise InternshipIndexError("Every internship must include internship_id, title, company, and description.")
    return records


def _fingerprint(records: list[dict[str, Any]]) -> str:
    encoded = json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ingest(force: bool = False) -> dict[str, int | bool]:
    records = _dataset()
    fingerprint = _fingerprint(records)
    if not force and INDEX_PATH.exists():
        try:
            existing = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if existing.get("fingerprint") == fingerprint and existing.get("provider") == EMBEDDING_PROVIDER:
                return {"indexed": False, "internships": len(records), "chunks": len(existing.get("chunks", []))}
        except (OSError, json.JSONDecodeError):
            pass

    chunks: list[dict[str, Any]] = []
    for record in records:
        for number, content in enumerate(_chunk(_internship_text(record))):
            chunks.append({"content": content, "metadata": {"internship_id": record["internship_id"], "chunk_number": number}, "record": record})
    vectors = _embed([chunk["content"] for chunk in chunks])
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps({"fingerprint": fingerprint, "provider": EMBEDDING_PROVIDER, "chunks": chunks}, ensure_ascii=False), encoding="utf-8")
    return {"indexed": True, "internships": len(records), "chunks": len(chunks)}


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def search(query: str, top_k: int) -> list[dict[str, Any]]:
    if not query.strip():
        raise InternshipIndexError("Candidate data did not contain enough information to search internships.")
    ingest()
    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        chunks = index["chunks"]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise InternshipIndexError("Could not load the internship vector index.") from exc
    query_vector = _embed([query])[0]
    ranked = sorted(((_dot(query_vector, item["embedding"]), item) for item in chunks), reverse=True, key=lambda row: row[0])
    best: dict[str, dict[str, Any]] = {}
    for score, item in ranked:
        internship_id = item["metadata"]["internship_id"]
        if internship_id not in best:
            best[internship_id] = {"semantic_score": max(0.0, score), "record": item["record"], "context": item["content"]}
        if len(best) >= top_k:
            break
    return list(best.values())


def get_internship(internship_id: str) -> dict[str, Any] | None:
    """Look up the source record without treating user input as a search query."""
    return next((record for record in _dataset() if record["internship_id"] == internship_id), None)
