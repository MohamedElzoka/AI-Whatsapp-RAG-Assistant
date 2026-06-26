"""
Redis-backed conversation memory.

We keep a short rolling window of recent turns per WhatsApp user (keyed by
phone number) so the LLM can answer contextual follow-up questions
("and how long does that take?") without re-fetching the full Postgres
history on every message. PostgreSQL remains the durable source of truth;
Redis is purely a fast, TTL-bound cache.
"""
import json
from typing import List, TypedDict

import redis

from app.config import settings


class ChatTurn(TypedDict):
    role: str  # "user" | "assistant"
    content: str


_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _memory_key(phone: str) -> str:
    return f"conv:memory:{phone}"


def get_recent_turns(phone: str) -> List[ChatTurn]:
    """Return the cached conversation turns for a user, oldest first."""
    client = get_redis()
    raw_items = client.lrange(_memory_key(phone), 0, -1)
    return [json.loads(item) for item in raw_items]


def append_turn(phone: str, role: str, content: str) -> None:
    """Append a single turn and trim/refresh TTL on the rolling window."""
    client = get_redis()
    key = _memory_key(phone)
    turn: ChatTurn = {"role": role, "content": content}
    client.rpush(key, json.dumps(turn))
    client.ltrim(key, -settings.REDIS_MEMORY_MAX_TURNS, -1)
    client.expire(key, settings.REDIS_MEMORY_TTL_SECONDS)


def clear_memory(phone: str) -> None:
    get_redis().delete(_memory_key(phone))
