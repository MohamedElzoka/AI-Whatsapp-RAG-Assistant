from openai import OpenAI
from app.config import settings
import hashlib
import random

MOCK_MODE = True

_client = None


def get_openai_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def embed_text(text: str):
    return embed_texts([text])[0]


def embed_texts(texts: list[str]):
    if not texts:
        return []

    # ===== MOCK MODE =====
    if MOCK_MODE:
        vectors = []

        for text in texts:
            # نفس النص -> نفس الـ seed
            seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
            rng = random.Random(seed)

            vector = [
                rng.uniform(-1, 1)
                for _ in range(settings.EMBEDDING_DIMENSIONS)
            ]

            vectors.append(vector)

        return vectors

    # ===== OPENAI MODE =====
    client = get_openai_client()

    response = client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
    )

    return [item.embedding for item in response.data]