"""HTTP client for the Task Manager backend, with X-API-Key injection."""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 10.0


class ApiError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(f"API {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


def _base_url() -> str:
    return os.getenv("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "X-API-Key": os.getenv("API_KEY", "dev-secret-123"),
        "Content-Type": "application/json",
    }


async def _request(method: str, path: str, **kwargs: Any) -> Any:
    url = f"{_base_url()}{path}"
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.request(method, url, headers=_headers(), **kwargs)
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise ApiError(resp.status_code, str(detail))
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


async def api_get(path: str, params: Optional[dict[str, Any]] = None) -> Any:
    return await _request("GET", path, params=params)


async def api_post(path: str, json_body: Any) -> Any:
    return await _request("POST", path, json=json_body)


async def api_put(path: str, json_body: Any) -> Any:
    return await _request("PUT", path, json=json_body)


async def api_delete(path: str) -> Any:
    return await _request("DELETE", path)
