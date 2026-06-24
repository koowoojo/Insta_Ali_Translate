"""
브라우저 쿠키 JSON → Playwright storage_state 변환.

Playwright `python main.py --login`이 실패할 때, 일반 Chrome/Edge에서
로그인한 뒤 Cookie-Editor 확장 프로그램으로보낸 쿠키를 세션 파일로 변환한다.

지원 형식: Cookie-Editor JSON 배열 [{name, value, domain, ...}]
미지원: Hot Cleaner 암호화 백업 {version:2, data:"..."} — 확장에서 JSON Export 사용
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CookieImportError(ValueError):
    """쿠키 import 실패 시 사용자 안내 메시지 포함."""


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


def _reject_encrypted_hotcleaner(data: Any) -> None:
    """Hot Cleaner 암호화 백업 형식이면 명확한 안내와 함께 거부."""
    if isinstance(data, dict) and "data" in data and "version" in data:
        if isinstance(data.get("data"), str) and "name" not in data:
            raise CookieImportError(
                "암호화된 Cookie 백업 파일입니다 (Hot Cleaner 형식).\n"
                "Chrome에서 Cookie-Editor 확장 → aliexpress.com 페이지 → "
                "Export → **JSON(배열)** 형식으로 다시 저장하세요.\n"
                "예시: [{\"name\":\"...\", \"value\":\"...\", \"domain\":\".aliexpress.com\"}]"
            )


def parse_cookie_json(data: Any) -> list[dict[str, Any]]:
    """
    다양한 JSON 형식에서 Playwright cookies 리스트를 추출한다.

    지원 형식:
    - Cookie-Editor 배열: [{name, value, domain, ...}, ...]
    - Playwright storage_state: {cookies: [...], origins: [...]}
    - {cookies: [...]} 래퍼
    """
    _reject_encrypted_hotcleaner(data)

    if isinstance(data, list):
        cookies = [_to_playwright_cookie(item) for item in data if "name" in item and "value" in item]
        if not cookies:
            raise CookieImportError(
                "쿠키 배열이 비어 있거나 name/value 필드가 없습니다. "
                "aliexpress.com 페이지에서 Cookie-Editor로 Export 했는지 확인하세요."
            )
        return cookies

    if isinstance(data, dict):
        if "cookies" in data and isinstance(data["cookies"], list):
            cookies = data["cookies"]
            if cookies and "expirationDate" in cookies[0]:
                return [_to_playwright_cookie(c) for c in cookies]
            return list(cookies)
        raise CookieImportError(
            "지원하지 않는 JSON 구조입니다. Cookie-Editor 배열 또는 storage_state 형식이어야 합니다."
        )

    raise CookieImportError("JSON 루트는 배열 또는 객체여야 합니다.")


def import_cookies_file(source: Path, dest: Path) -> Path:
    """
    쿠키 JSON 파일을 읽어 Playwright storage_state로 저장한다.

    Args:
        source: Cookie-Editor 등에서보낸 .json 경로
        dest: 저장할 storage_state 경로 (예: assets/sessions/aliexpress_state.json)

    Returns:
        저장된 dest Path
    """
    if not source.exists():
        raise CookieImportError(f"파일을 찾을 수 없습니다: {source}")

    raw_text = source.read_text(encoding="utf-8-sig")
    data = json.loads(raw_text)
    cookies = parse_cookie_json(data)

    storage_state = {"cookies": cookies, "origins": []}
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(storage_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest
