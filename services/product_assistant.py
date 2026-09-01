"""Grounded InternSphere product assistant with persisted chat-ready retrieval."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

from services.internship_index import _dot, _embed, _terms

KNOWLEDGE_PATH = Path(os.getenv("PRODUCT_KNOWLEDGE_PATH", "data/product_knowledge.json"))
INDEX_PATH = Path("data/product_knowledge_index.json")


def _documents() -> list[dict]:
    raw = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        if index.get("fingerprint") == fingerprint:
            return index["documents"]
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    documents = json.loads(raw)
    for document in documents:
        document["embedding"] = _embed([document["content"]])[0]
    INDEX_PATH.write_text(json.dumps({"fingerprint": fingerprint, "documents": documents}), encoding="utf-8")
    return documents


def answer(question: str) -> tuple[str, list[str]]:
    """Return a concise answer only from the best product-knowledge document."""
    documents = _documents()
    query_vector = _embed([question])[0]
    question_terms = set(_terms(question))
    def score(doc: dict) -> float:
        document_terms = set(_terms(doc["title"] + " " + doc["content"]))
        lexical = len(question_terms & document_terms) / max(1, len(question_terms))
        semantic = max(0.0, _dot(query_vector, doc["embedding"]))
        return 0.7 * lexical + 0.3 * semantic
    ranked = sorted(((score(doc), doc) for doc in documents), reverse=True, key=lambda item: item[0])
    score, document = ranked[0]
    if score <= 0.05:
        return ("That information is not available in the InternSphere product knowledge base.", [])
    return (document["content"], [document["title"]])
