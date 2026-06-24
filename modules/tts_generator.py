"""
OpenAI TTS로 한국어 더빙 오디오 생성.

주요 기능:
- build_tts_request: OpenAI speech API 요청 파라미터 dict 구성
- generate_speech: TTS 생성 + (선택) 목표 영상 길이에 맞춘 속도 조절
"""

from __future__ import annotations

import logging
from pathlib import Path

from moviepy import AudioFileClip
from openai import OpenAI

from utils.config import get_settings
from utils.exceptions import PipelineError

logger = logging.getLogger(__name__)

MIN_CHARS_PER_SECOND = 5.0


def build_tts_request(text: str, model: str, voice: str, speed: float = 1.0) -> dict:
    """OpenAI TTS API 호출 파라미터 dict."""
    return {
        "model": model,
        "voice": voice,
        "input": text.strip(),
        "response_format": "mp3",
        "speed": speed,
    }


def _validate_audio_duration(output_path: str, text: str) -> float:
    """생성된 MP3가 비정상적으로 짧지 않은지 검증."""
    with AudioFileClip(output_path) as clip:
        duration = clip.duration

    char_count = len(text.replace(" ", "").replace("\n", ""))
    min_expected = char_count / (MIN_CHARS_PER_SECOND * 2.5)

    if duration < max(3.0, min_expected):
        raise PipelineError(
            "tts",
            f"TTS 오디오가 비정상적으로 짧습니다 ({duration:.1f}초, "
            f"대본 {char_count}자, 최소 예상 {min_expected:.1f}초)",
        )

    logger.info("TTS 길이 검증 통과: %.1f초", duration)
    return duration


def _synthesize(client: OpenAI, request: dict, output_path: str) -> None:
    """API 호출 후 MP3 저장."""
    response = client.audio.speech.create(**request)
    response.write_to_file(output_path)


def generate_speech(
    text: str,
    output_path: str,
    target_duration_sec: float | None = None,
) -> str:
    """
    OpenAI TTS로 더빙 MP3를 생성한다.

    target_duration_sec가 주어지면 1차 생성 후 길이를 보고 speed를 조절해
    영상 길이에 최대한 맞춘 뒤 저장한다 (미세 조정은 video_editor에서 처리).

    Args:
        text: 더빙 대본
        output_path: 출력 MP3 경로
        target_duration_sec: 목표 영상 길이(초), None이면 speed 1.0만 사용
    """
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    speed = 1.0
    request = build_tts_request(
        text, settings.openai_tts_model, settings.openai_tts_voice, speed=speed
    )
    logger.info(
        "OpenAI TTS 요청 (%d자, model=%s, voice=%s, speed=%.2f)",
        len(text),
        request["model"],
        request["voice"],
        speed,
    )
    _synthesize(client, request, output_path)
    _validate_audio_duration(output_path, text)

    if target_duration_sec is not None:
        with AudioFileClip(output_path) as clip:
            current = clip.duration

        if current > target_duration_sec * 1.05:
            speed = min(1.15, current / target_duration_sec)
            logger.info("TTS 재생성 (빠르게): speed=%.2f", speed)
            request = build_tts_request(
                text, settings.openai_tts_model, settings.openai_tts_voice, speed=speed
            )
            _synthesize(client, request, output_path)
        elif current < target_duration_sec * 0.92:
            speed = max(0.82, current / target_duration_sec)
            logger.info("TTS 재생성 (느리게): speed=%.2f", speed)
            request = build_tts_request(
                text, settings.openai_tts_model, settings.openai_tts_voice, speed=speed
            )
            _synthesize(client, request, output_path)

        with AudioFileClip(output_path) as clip:
            logger.info("TTS 목표 대비: %.1f초 / 목표 %.1f초", clip.duration, target_duration_sec)

    logger.info("더빙 저장: %s", output_path)
    return output_path
