"""
Security utilities:
  - Symmetric encryption (Fernet) for sensitive fields at rest
  - WhatsApp webhook HMAC-SHA256 signature verification
  - Simple API-key dependency to protect admin/dashboard-facing endpoints
"""
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet
from fastapi import Header, HTTPException, status

from app.config import settings


@lru_cache
def _fernet() -> Fernet:
    """
    Build a Fernet cipher from FIELD_ENCRYPTION_KEY.

    FIELD_ENCRYPTION_KEY must be a urlsafe-base64-encoded 32-byte key.
    Generate one with:
        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "FIELD_ENCRYPTION_KEY is not set. Generate one with "
            "`python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"` and set it in your .env file."
        )
    return Fernet(key.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string for storage. Returns a urlsafe base64 token."""
    if plaintext is None:
        return plaintext
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a value previously produced by encrypt_value()."""
    if token is None:
        return token
    return _fernet().decrypt(token.encode()).decode()


def verify_whatsapp_signature(payload_body: bytes, signature_header: str | None) -> bool:
    """
    Verify the `X-Hub-Signature-256` header Meta sends with every webhook
    POST, computed as HMAC-SHA256 of the raw request body using the
    WhatsApp App Secret.
    """
    if not settings.WHATSAPP_APP_SECRET:
        # In local/dev environments without an app secret configured, skip
        # verification rather than hard-failing every request.
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        key=settings.WHATSAPP_APP_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header.split("sha256=", 1)[1]
    return hmac.compare_digest(expected_signature, received_signature)


def require_admin_api_key(x_admin_api_key: str = Header(default="")) -> None:
    """
    FastAPI dependency that protects admin/dashboard-facing endpoints
    (document upload, reindex, conversations, analytics) with a static
    API key shared with the Streamlit dashboard via environment variables.
    """
    if not hmac.compare_digest(x_admin_api_key, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Api-Key header.",
        )
