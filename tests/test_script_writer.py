"""script_writer 모듈 단위 테스트 — 프롬프트 빌더 검증."""

from modules.script_writer import build_step1_prompt, build_step2_prompt


def test_build_step1_prompt_contains_text():
    p = build_step1_prompt("hello product")
    assert "hello product" in p


def test_build_step2_prompt_contains_summary():
    p = build_step2_prompt('{"hooks":["fast"]}', target_duration_sec=38.0)
    assert "fast" in p
    assert "38초" in p or "38" in p
