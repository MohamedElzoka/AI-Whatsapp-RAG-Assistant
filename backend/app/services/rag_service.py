"""
RAG orchestration: the core "ask a question, get a grounded answer"
pipeline used by the WhatsApp webhook handler.

Flow (matches the design doc's RAG Workflow section):
  1. Receive customer question
  2. Generate embedding
  3. Search top-k similar chunks in Qdrant
  4. Build prompt using retrieved context + recent conversation memory
  5. Generate response with GPT-4o
  6. Decide on human escalation
"""
import time
from dataclasses import dataclass, field

from app.config import settings
from app.redis_client import append_turn, get_recent_turns
from app.services import escalation_service
from app.services.embedding_service import embed_text
from app.services.llm_service import generate_answer
from app.utils.logger import get_logger
from app.vectorstore import search as vector_search

logger = get_logger(__name__)


@dataclass
class RAGResult:
    answer: str
    confidence: float
    top_similarity_score: float | None
    sources: list[dict] = field(default_factory=list)
    should_escalate: bool = False
    escalation_reason: str | None = None
    llm_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0


def answer_question(user_phone: str, question: str) -> RAGResult:
    # --- 1 & 2: embed the question ---
    query_vector = embed_text(question)

    # --- 3: retrieve top-k similar chunks ---
    t0 = time.perf_counter()
    matches = vector_search(query_vector, top_k=settings.RAG_TOP_K)
    print("=" * 60)
    print("MATCHES:", matches)
    print("=" * 60)
    retrieval_latency_ms = (time.perf_counter() - t0) * 1000

    top_score = matches[0]["score"] if matches else None
    relevant_matches = [m for m in matches if m["score"] >= settings.SIMILARITY_THRESHOLD]
    print("SIMILARITY_THRESHOLD =", settings.SIMILARITY_THRESHOLD)
    print("RELEVANT MATCHES =", relevant_matches)
    context_chunks = [m["text"] for m in relevant_matches]

    # --- 4: pull recent conversation memory from Redis ---
    history = get_recent_turns(user_phone)

    # --- 5: generate grounded response ---
    t1 = time.perf_counter()
    llm_result = generate_answer(
        user_query=question,
        context_chunks=context_chunks,
        conversation_history=history,
    )
    llm_latency_ms = (time.perf_counter() - t1) * 1000

    # --- 6: escalation decision ---
    decision = escalation_service.evaluate_escalation(
        top_similarity_score=top_score if relevant_matches else None,
        llm_confidence=llm_result.confidence,
    )

    # Update rolling memory with this turn regardless of escalation outcome
    append_turn(user_phone, "user", question)
    append_turn(user_phone, "assistant", llm_result.answer)

    return RAGResult(
        answer=llm_result.answer,
        confidence=llm_result.confidence,
        top_similarity_score=top_score,
        sources=[
            {"filename": m["filename"], "score": m["score"], "document_id": m["document_id"]}
            for m in relevant_matches
        ],
        should_escalate=decision.should_escalate,
        escalation_reason=decision.reason,
        llm_latency_ms=llm_latency_ms,
        retrieval_latency_ms=retrieval_latency_ms,
    )
