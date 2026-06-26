"""
LLM response generation via GPT-4o.

This version supports MOCK_MODE so the project can run without
an OpenAI API key.
"""

import json
from dataclasses import dataclass

from app.config import settings
from app.services.embedding_service import get_openai_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ==========================
# Enable mock mode
# ==========================
MOCK_MODE = True

SYSTEM_PROMPT = """You are a helpful, friendly customer support assistant for a company,
communicating with customers over WhatsApp.

Rules:
- Answer ONLY using the information given in the Knowledge Base.
- If the answer is not in the context, say you don't know.
- Return ONLY valid JSON.

Format:
{
  "answer": "<text>",
  "confidence": <0-1>
}
"""


@dataclass
class LLMResult:
    answer: str
    confidence: float
    raw_response: str


def _build_context_block(chunks: list[str]) -> str:
    if not chunks:
        return "(no relevant knowledge base content was found)"
    numbered = [f"[{i+1}] {c}" for i, c in enumerate(chunks)]
    return "\n\n".join(numbered)


def generate_answer(
    user_query: str,
    context_chunks: list[str],
    conversation_history: list[dict],
) -> LLMResult:
    """
    Generate an answer using the retrieved context.
    """

    # =====================================================
    # MOCK MODE (No OpenAI required)
    # =====================================================
    if MOCK_MODE:

        if context_chunks:
            context = "\n\n".join(context_chunks[:2])

            return LLMResult(
                answer=f"""[MOCK AI RESPONSE]

Question:
{user_query}

Based on the uploaded knowledge base:

{context}
""",
                confidence=0.95,
                raw_response="mock",
            )

        return LLMResult(
            answer="No relevant information was found in the uploaded documents.",
            confidence=0.2,
            raw_response="mock",
        )

    # =====================================================
    # REAL OPENAI MODE
    # =====================================================

    client = get_openai_client()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for turn in conversation_history:
        messages.append(
            {
                "role": turn["role"],
                "content": turn["content"],
            }
        )

    context_block = _build_context_block(context_chunks)

    user_content = (
        f"Knowledge base context:\n{context_block}\n\n"
        f"Customer question: {user_query}"
    )

    messages.append(
        {
            "role": "user",
            "content": user_content,
        }
    )

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=settings.LLM_TEMPERATURE,
        max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
        response_format={"type": "json_object"},
    )

    raw_content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(raw_content)

        answer = str(parsed.get("answer", "")).strip()

        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))

    except Exception:
        logger.warning("Failed to parse LLM JSON response.")

        answer = raw_content.strip()
        confidence = 0.3

    if not answer:
        answer = (
            "I'm sorry, I couldn't find a confident answer."
        )
        confidence = 0.0

    return LLMResult(
        answer=answer,
        confidence=confidence,
        raw_response=raw_content,
    )