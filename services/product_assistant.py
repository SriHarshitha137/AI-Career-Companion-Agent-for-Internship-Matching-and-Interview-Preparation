"""Grounded InternSphere product assistant with persisted chat-ready RAG retrieval."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from services.internship_index import _dot, _embed, _terms

KNOWLEDGE_PATH = Path(os.getenv("PRODUCT_KNOWLEDGE_PATH", "data/product_knowledge.json"))
INDEX_PATH = Path("data/product_knowledge_index.json")
DEFAULT_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-flash-latest"]


def _documents() -> list[dict]:
    raw = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    try:
        if INDEX_PATH.exists():
            index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if index.get("fingerprint") == fingerprint:
                return index["documents"]
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    documents = json.loads(raw)
    texts = [f"{doc['title']}\n{doc['content']}" for doc in documents]
    embeddings = _embed(texts)
    for document, vector in zip(documents, embeddings):
        document["embedding"] = vector
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps({"fingerprint": fingerprint, "documents": documents}, ensure_ascii=False), encoding="utf-8")
    return documents


def _find_previous_question(history: list[dict[str, Any]]) -> str | None:
    """Find the previous user question before the latest one."""
    user_questions = [msg["content"] for msg in history if msg.get("role") == "user"]
    if len(user_questions) >= 2:
        return user_questions[-2]
    return None


def answer(question: str, history: list[dict[str, Any]] | None = None) -> tuple[str, list[str]]:
    """Generate a grounded response using RAG, session context memory, and scope awareness."""
    history = history or []

    # Check for direct conversational memory queries like "What was my previous question?"
    q_norm = question.strip().lower()
    if any(phrase in q_norm for phrase in [
        "what was my previous question",
        "what was my last question",
        "what did i ask previously",
        "what did i ask before",
        "repeat my previous question",
    ]):
        prev = _find_previous_question(history)
        if prev:
            return (f'Your previous question was "{prev}"', ["Session Context"])
        else:
            return ("You have not asked any previous questions in this chat session yet.", ["Session Context"])

    # Perform RAG retrieval from the product knowledge base
    documents = _documents()
    query_vector = _embed([question])[0]
    question_terms = set(_terms(question))

    def score(doc: dict) -> float:
        document_terms = set(_terms(doc["title"] + " " + doc["content"]))
        lexical = len(question_terms & document_terms) / max(1, len(question_terms))
        semantic = max(0.0, _dot(query_vector, doc["embedding"]))
        return 0.65 * lexical + 0.35 * semantic

    ranked = sorted(((score(doc), doc) for doc in documents), reverse=True, key=lambda item: item[0])
    top_docs = [doc for s, doc in ranked if s > 0.05][:3]
    top_score = ranked[0][0] if ranked else 0.0

    context_str = "\n\n".join([f"Topic: {d['title']}\nContent: {d['content']}" for d in top_docs])
    sources = [d["title"] for d in top_docs]

    # Format recent history for context
    history_snippets = []
    for msg in history[-6:]:  # Last 3 turns
        role = "User" if msg.get("role") == "user" else "Assistant"
        history_snippets.append(f"{role}: {msg.get('content')}")
    history_str = "\n".join(history_snippets)

    # Use Gemini for grounded generation with scope handling
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("paste_your_"):
        if top_docs:
            return (top_docs[0]["content"], sources[:1])
        return ("InternSphere AI generation is currently offline. Please configure GEMINI_API_KEY.", [])

    prompt = f"""You are the InternSphere AI Assistant, an expert on the InternSphere AI-Powered Internship Matching & Career Assistant platform.

VERIFIED INTERNSPHERE KNOWLEDGE CONTEXT:
{context_str if context_str else "No direct InternSphere documentation matched."}

RECENT CONVERSATION HISTORY:
{history_str if history_str else "No prior messages."}

CURRENT USER QUESTION:
{question}

INSTRUCTIONS:
1. SCOPE CHECK:
   - If the question is outside the scope of InternSphere (such as general world trivia, recipes, poetry, sports scores, math puzzles, programming tutorials unrelated to the platform):
     You MUST respond strictly in this format:
     "This question is outside the scope of the InternSphere AI Assistant.

For general information:
[Provide a concise, accurate 1-2 sentence answer to their question]

I can also help you with InternSphere features such as internship matching, resume parsing, skill-gap analysis, cover letters, applications, and the AI assistant."

2. RELEVANT QUESTIONS (InternSphere platform, internship matching, resume parsing, skill gaps, profile, cover letters, applications, RAG):
   - Provide a helpful, clear, professional, concise response grounded strictly in the verified knowledge context.
   - If the user asks about previous topics or refers to earlier messages in the active session, use the recent conversation history to answer contextually.
   - Do not hallucinate features not present in the context.
   - Keep answers well-formatted with bullet points if helpful.
"""

    try:
        from google import genai
        configured_model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        models = [configured_model] + [m for m in FALLBACK_MODELS if m != configured_model]
        client = genai.Client(api_key=api_key)

        for model in models:
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                ans = (response.text or "").strip()
                if ans:
                    # If it was an irrelevant question, sources are empty or general
                    if "outside the scope of the InternSphere AI Assistant" in ans:
                        return (ans, [])
                    return (ans, sources if sources else ["InternSphere Platform"])
            except Exception:
                continue

    except Exception:
        pass

    # Fallback to direct knowledge match if Gemini call encounters an error
    if top_docs:
        return (top_docs[0]["content"], sources[:1])
    return ("I can help you with InternSphere features including resume parsing, internship matching, skill gap analysis, cover letters, and application tracking. How can I assist you?", [])
