import os
import secrets

from fastapi import Header, HTTPException, status

API_KEY_HEADER = "X-API-Key"


def _expected_key() -> str:
    return os.getenv("API_KEY", "dev-secret-123")


def require_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    expected = _expected_key()
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )
