"""
Claude 다단계 프롬프팅으로 한국어 세일즈 대본 생성 모듈.

주요 기능:
- Step 1: STT 원문에서 hooks/features/target_audience JSON 요약 (analyze_product)
- Step 2: 요약 기반 40초 이내 쇼츠용 세일즈 대본 작성 (write_sales_script)
- generate_script: Anthropic SDK + get_settings()로 2단계 파이프라인 실행

설정은 utils.config.Settings에서 anthropic_api_key, claude_model을 읽는다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from utils.config import get_settings

# 모듈 전용 로거 — setup_logging() 호출 후 루트 핸들러에 전파된다.
logger = logging.getLogger(__name__)


def build_step1_prompt(raw_text: str) -> str:
    """
    Step 1용 프롬프트: STT 원문을 제품 분석 JSON으로 요약하도록 지시한다.

    Args:
        raw_text: Whisper 등으로 전사된 상품 홍보 원문

    Returns:
        Claude API user 메시지용 프롬프트 문자열
    """
    return f"""다음은 상품 홍보 영상의 음성 인식 원문입니다.
핵심 소구점(hooks), 제품 특징(features), 타겟(target_audience)을 JSON으로 요약하세요.
키만 hooks, features, target_audience를 사용하세요.
JSON만 출력하세요. 마크다운 코드 블록이나 설명 문장은 넣지 마세요.

원문:
{raw_text}
"""


def build_step2_prompt(summary_json: str, target_duration_sec: float = 38.0) -> str:
    """
    Step 2용 프롬프트: 제품 요약 JSON을 바탕으로 세일즈 대본 작성을 지시한다.

    Args:
        summary_json: Step 1 분석 결과 JSON 문자열
        target_duration_sec: 원본 영상 길이에 맞춘 목표 낭독 시간(초)

    Returns:
        Claude API user 메시지용 프롬프트 문자열
    """
    min_chars = int(target_duration_sec * 7.2)
    max_chars = int(target_duration_sec * 8.8)
    return f"""아래 제품 요약을 바탕으로 인스타그램 릴스/틱톡용 한국어 세일즈 대본을 작성하세요.
- 첫 2초 안에 시선을 사로잡는 강력한 후킹 멘트
- 자연스러운 한국어 홈쇼핑 MC 톤, 말하듯 짧은 호흡
- **반드시** 낭독 시 {target_duration_sec:.1f}초 전체를 채울 것 ({min_chars}~{max_chars}자) — 절대 짧게 끝내지 말 것
- 원본 영상 길이에 맞춰 처음부터 끝까지 말이 이어지게 작성
- 문장 6~8개 이상, 제품 특징·혜택·행동 유도(구매/저장)까지 포함
- 대본 텍스트만 출력 (설명·괄호·제목·타임스탬프 없음)

요약:
{summary_json}
"""


def _parse_json_response(text: str) -> dict:
    """Claude 응답에서 JSON 객체를 추출한다 (```json 래퍼 허용)."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return json.loads(cleaned)


def analyze_product(client: anthropic.Anthropic, raw_text: str, model: str) -> dict:
    """
    Claude Step 1: 원문에서 hooks/features/target_audience JSON을 추출한다.

    Args:
        client: Anthropic SDK 클라이언트
        raw_text: STT 원문
        model: Claude 모델 식별자 (예: claude-3-5-sonnet-20241022)

    Returns:
        파싱된 제품 요약 dict (hooks, features, target_audience 키)

    Raises:
        json.JSONDecodeError: 모델 응답이 유효한 JSON이 아닐 때
    """
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": build_step1_prompt(raw_text)}],
    )
    content = msg.content[0].text
    return _parse_json_response(content)


def write_sales_script(
    client: anthropic.Anthropic,
    summary: dict,
    model: str,
    target_duration_sec: float = 38.0,
) -> str:
    """
    Claude Step 2: 제품 요약을 바탕으로 한국어 세일즈 대본을 생성한다.

    Args:
        client: Anthropic SDK 클라이언트
        summary: Step 1 analyze_product 결과 dict
        model: Claude 모델 식별자

    Returns:
        앞뒤 공백이 제거된 최종 대본 문자열
    """
    msg = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": build_step2_prompt(
                    json.dumps(summary, ensure_ascii=False),
                    target_duration_sec=target_duration_sec,
                ),
            }
        ],
    )
    return msg.content[0].text.strip()


def generate_script(
    raw_text: str,
    job_dir: str | None = None,
    target_duration_sec: float = 38.0,
) -> str:
    """
    2단계 Claude 파이프라인으로 한국어 세일즈 대본을 생성한다.

    job_dir가 주어지면 Step 1 JSON 요약을 script_step1.json으로 저장한다.

    Args:
        raw_text: STT 원문 텍스트
        job_dir: 작업별 산출물 디렉터리 (선택, 예: assets/jobs/{job_id})
        target_duration_sec: 원본 영상 길이에 맞춘 목표 낭독 시간(초)

    Returns:
        최종 세일즈 대본 문자열
    """
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    logger.info("Step1: 제품 분석")
    summary = analyze_product(client, raw_text, settings.claude_model)

    if job_dir:
        step1_path = Path(job_dir) / "script_step1.json"
        step1_path.parent.mkdir(parents=True, exist_ok=True)
        step1_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    logger.info("Step2: 세일즈 대본 작성 (목표 %.0f초)", target_duration_sec)
    return write_sales_script(
        client, summary, settings.claude_model, target_duration_sec
    )
