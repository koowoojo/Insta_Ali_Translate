"""
브라우저 쿠키 JSON → Playwright storage_state 변환.

Playwright `python main.py --login`이 실패할 때, 일반 Chrome/Edge에서
로그인한 뒤 Cookie-Editor 등으로보낸 쿠키를 세션 파일로 변환한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _normalize_same_site(value: Any) -> str:
    """Playwright가 허용하는 sameSite 값으로 정규화."""
    if not value:
        return "Lax"
    text = str(value).capitalize()
    if text in ("Strict", "Lax", "None"):
        return text
    return "Lax"


def _to_playwright_cookie(raw: dict[str, Any]) -> dict[str, Any]:
    """Cookie-Editor / EditThisCookie 형식 1건을 Playwright 쿠키 dict로 변환."""
    expires = raw.get("expirationDate", raw.get("expires", -1))
    if expires is None:
        expires = -1
    return {
        "name": raw["name"],
        "value": raw["value"],
        "domain": raw.get("domain", ".aliexpress.com"),
        "path": raw.get("path", "/"),
        "expires": float(expires),
        "httpOnly": bool(raw.get("httpOnly", False)),
        "secure": bool(raw.get("secure", False)),
        "sameSite": _normalize_same_site(raw.get("sameSite")),
    }


def parse_cookie_json(data: Any) -> list[dict[str, Any]]:
    """
    다양한 JSON 형식에서 Playwright cookies 리스트를 추출한다.

    지원 형식:
    - Cookie-Editor 배열: [{name, value, domain, ...}, ...]
    - Playwright storage_state: {cookies: [...], origins: [...]}
    - {cookies: [...]} 래퍼
    """
    if isinstance(data, list):
        return [_to_playwright_cookie(item) for item in data if "name" in item and "value" in item]

    if isinstance(data, dict):
        if "cookies" in data and isinstance(data["cookies"], list):
            cookies = data["cookies"]
            if cookies and "expirationDate" in cookies[0]:
                return [_to_playwright_cookie(c) for c in cookies]
            return list(cookies)
        raise ValueError("지원하지 않는 JSON 구조입니다. Cookie-Editor 배열 또는 storage_state 형식이어야 합니다.")

    raise ValueError("JSON 루트는 배열 또는 객체여야 합니다.")


def import_cookies_file(source: Path, dest: Path) -> Path:
    """
    쿠키 JSON 파일을 읽어 Playwright storage_state로 저장한다.

    Args:
        source: Cookie-Editor 등에서보낸 .json 경로
        dest: 저장할 storage_state 경로 (예: assets/sessions/aliexpress_state.json)

    Returns:
        저장된 dest Path
    """
    raw_text = source.read_text(encoding="utf-8-sig")
    data = json.loads(raw_text)
    cookies = parse_cookie_json(data)
    if not cookies:
        raise ValueError("변환할 쿠키가 없습니다.")

    storage_state = {"cookies": cookies, "origins": []}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(storage_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest
