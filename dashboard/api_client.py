"""
Thin HTTP client used by every dashboard page to talk to the FastAPI
backend. Centralizes the base URL, admin API key header, and basic
error handling so individual pages stay focused on presentation.
"""
import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")
REQUEST_TIMEOUT = 30


def _headers() -> dict:
    return {"X-Admin-Api-Key": ADMIN_API_KEY}


def api_get(path: str, params: dict | None = None):
    try:
        response = requests.get(
            f"{BACKEND_URL}{path}", headers=_headers(), params=params, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Failed to reach backend at `{BACKEND_URL}{path}`: {exc}")
        return None


def api_post(path: str, json: dict | None = None, files: dict | None = None):
    try:
        response = requests.post(
            f"{BACKEND_URL}{path}",
            headers=_headers(),
            json=json,
            files=files,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as exc:
        st.error(f"Request to `{BACKEND_URL}{path}` failed: {exc}")
        return None
