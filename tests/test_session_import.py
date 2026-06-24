"""session_import 유틸 단위 테스트."""

import json
from pathlib import Path

from utils.session_import import import_cookies_file, parse_cookie_json


def test_parse_cookie_editor_array():
    data = [
        {
            "domain": ".aliexpress.com",
            "name": "aep_usuc_f",
            "value": "test",
            "path": "/",
            "expirationDate": 1893456000,
            "httpOnly": False,
            "secure": False,
            "sameSite": "lax",
        }
    ]
    cookies = parse_cookie_json(data)
    assert len(cookies) == 1
    assert cookies[0]["name"] == "aep_usuc_f"
    assert cookies[0]["sameSite"] == "Lax"


def test_import_cookies_file(tmp_path: Path):
    src = tmp_path / "cookies.json"
    src.write_text(
        json.dumps([{"name": "x", "value": "y", "domain": ".aliexpress.com"}]),
        encoding="utf-8",
    )
    dest = tmp_path / "state.json"
    out = import_cookies_file(src, dest)
    assert out.exists()
    state = json.loads(out.read_text(encoding="utf-8"))
    assert state["cookies"][0]["name"] == "x"
