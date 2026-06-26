"""
WhatsApp Cloud API integration.

Handles:
  - Sending outbound text messages
  - Marking inbound messages as read
  - Parsing the (fairly verbose) inbound webhook payload into a simple shape
"""
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class InboundMessage:
    whatsapp_message_id: str
    from_phone: str
    text: str
    profile_name: Optional[str] = None


def _graph_url(path: str) -> str:
    return (
        f"{settings.WHATSAPP_GRAPH_BASE_URL}/{settings.WHATSAPP_API_VERSION}/{path}"
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }


def send_text_message(to_phone: str, body: str) -> dict[str, Any]:
    """Send a plain text message to a WhatsApp user via the Cloud API."""
    url = _graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, headers=_headers(), json=payload)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError:
        logger.exception("Failed to send WhatsApp message to %s", to_phone)
        raise


def mark_message_as_read(whatsapp_message_id: str) -> None:
    url = _graph_url(f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": whatsapp_message_id,
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=_headers(), json=payload)
            response.raise_for_status()
    except httpx.HTTPError:
        # Non-critical — log and move on, don't fail the whole webhook
        logger.warning("Failed to mark message %s as read", whatsapp_message_id)


def parse_inbound_payload(payload: dict[str, Any]) -> list[InboundMessage]:
    """
    Parse a WhatsApp Cloud API webhook POST body into a list of inbound
    text messages. Non-text message types (image, audio, location, etc.)
    and status-only callbacks are safely skipped here; extend this
    function to support those payload types as needed.
    """
    messages: list[InboundMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {c["wa_id"]: c.get("profile", {}).get("name") for c in value.get("contacts", [])}

            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    logger.info(
                        "Skipping unsupported inbound message type: %s", msg.get("type")
                    )
                    continue

                from_phone = msg.get("from")
                messages.append(
                    InboundMessage(
                        whatsapp_message_id=msg.get("id", ""),
                        from_phone=from_phone,
                        text=msg.get("text", {}).get("body", ""),
                        profile_name=contacts.get(from_phone),
                    )
                )

    return messages
