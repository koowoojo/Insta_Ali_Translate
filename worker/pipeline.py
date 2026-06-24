"""
5단계 동기 파이프라인 오케스트레이션.

AliExpress URL부터 최종 9:16 숏폼 MP4까지 scraper → audio_processor →
script_writer → tts_generator → video_editor 순서로 실행한다.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from moviepy import VideoFileClip

from modules import audio_processor, scraper, script_writer, tts_generator, video_editor
from utils.config import get_settings

# 파이프라인 단계별 진행 로그용 모듈 로거
logger = logging.getLogger(__name__)


def job_asset_dir(job_id: str) -> Path:
    """
    작업별 산출물 디렉터리 경로를 반환한다.

    Args:
        job_id: UUID 또는 호출자가 지정한 작업 식별자

    Returns:
        assets/jobs/{job_id} 형태의 Path
    """
    return Path("assets") / "jobs" / job_id


def run_pipeline(url: str, job_id: str | None = None) -> dict:
    """
    단일 URL에 대해 전체 동기 파이프라인을 실행한다.

    단계:
    1. scrape_video — 원본 MP4 다운로드
    2. extract_audio + transcribe — WAV 추출 및 Whisper 전사
    3. generate_script — Claude 숏폼 대본 생성
    4. generate_speech — OpenAI TTS
    5. compose_shorts — 9:16 합성·자막·루프 동기화

    Args:
        url: AliExpress 상품 페이지 URL
        job_id: 기존 작업 ID 재사용 시 지정; None이면 uuid4() 생성

    Returns:
        job_id, script, output_path 키를 가진 결과 dict
    """
    settings = get_settings()
    job_id = job_id or str(uuid.uuid4())
    base = job_asset_dir(job_id)
    base.mkdir(parents=True, exist_ok=True)

    raw = str(base / "raw_video.mp4")
    wav = str(base / "extracted_audio.wav")
    dub = str(base / "dubbing.mp3")
    final = str(base / "final_shorts.mp4")

    logger.info("[%s] scraping", job_id)
    scraper.scrape_video(url, raw)

    with VideoFileClip(raw) as raw_clip:
        raw_duration = raw_clip.duration
        target_duration = min(raw_duration, settings.max_shorts_duration)
    logger.info(
        "[%s] 원본 영상 %.1f초 → 목표 대본 %.1f초",
        job_id,
        raw_duration,
        target_duration,
    )

    logger.info("[%s] transcribing", job_id)
    audio_processor.extract_audio(raw, wav)
    text = audio_processor.transcribe(wav)

    logger.info("[%s] scripting", job_id)
    script = script_writer.generate_script(
        text,
        job_dir=str(base),
        target_duration_sec=target_duration,
    )
    (base / "script.txt").write_text(script, encoding="utf-8")

    logger.info("[%s] tts", job_id)
    tts_generator.generate_speech(script, dub, target_duration_sec=target_duration)

    logger.info("[%s] editing", job_id)
    video_editor.compose_shorts(
        raw, dub, script, final, target_duration_sec=target_duration
    )

    return {"job_id": job_id, "script": script, "output_path": final}
