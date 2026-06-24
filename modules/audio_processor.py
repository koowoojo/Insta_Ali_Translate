"""
영상 오디오 분리 및 OpenAI Whisper STT 모듈.

주요 기능:
- 자막 렌더링용 텍스트 청킹 (chunk_text_for_subtitles)
- MoviePy VideoFileClip으로 영상에서 오디오 추출 (extract_audio)
- OpenAI whisper-1 API로 음성→텍스트 변환 (transcribe)

설정은 utils.config.Settings에서 openai_api_key를 읽는다.
"""

from __future__ import annotations

import logging
from pathlib import Path

from moviepy import VideoFileClip
from openai import OpenAI

from utils.config import get_settings

# 모듈 전용 로거 — setup_logging() 호출 후 루트 핸들러에 전파된다.
logger = logging.getLogger(__name__)


def chunk_text_for_subtitles(text: str, chunk_size: int = 18) -> list[str]:
    """
    자막 표시용으로 긴 텍스트를 고정 길이 청크로 분할한다.

    줄바꿈은 공백으로 치환한 뒤 앞뒤 공백을 제거하고,
    chunk_size 문자 단위로 슬라이싱한다 (한글·영문 모두 1자=1칸).

    Args:
        text: 원본 전사/대본 텍스트
        chunk_size: 청크당 최대 문자 수 (기본 18 — Settings.subtitle_chunk_size와 동일)

    Returns:
        비어 있지 않은 청크 문자열 리스트 (입력이 빈 문자열이면 [])
    """
    normalized = text.replace("\n", " ").strip()
    if not normalized:
        return []
    return [
        normalized[i : i + chunk_size]
        for i in range(0, len(normalized), chunk_size)
    ]


def chunk_text_reels_style(text: str, max_chars: int = 12) -> list[str]:
    """
    인스타 릴스 스타일 짧은 구절 자막용 청킹.

    단어(공백) 단위로 묶되 max_chars를 넘지 않게 분할한다.
    공백 없는 긴 한글 구간은 max_chars 단위로 잘라낸다.

    Args:
        text: 대본 전문
        max_chars: 한 화면에 표시할 최대 글자 수 (기본 12)

    Returns:
        자막 청크 리스트
    """
    normalized = text.replace("\n", " ").strip()
    if not normalized:
        return []

    chunks: list[str] = []
    current = ""

    for word in normalized.split():
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(word) <= max_chars:
            current = word
        else:
            for i in range(0, len(word), max_chars):
                chunks.append(word[i : i + max_chars])
            current = ""

    if current:
        chunks.append(current)

    return chunks


def extract_audio(video_path: str, audio_path: str) -> str:
    """
    영상 파일에서 오디오 트랙만 추출해 별도 파일로 저장한다.

    Args:
        video_path: 입력 MP4 등 비디오 파일 경로
        audio_path: 출력 오디오 파일 경로 (부모 디렉터리 없으면 생성)

    Returns:
        저장된 audio_path 문자열

    Raises:
        ValueError: 영상에 오디오 트랙이 없을 때
    """
    logger.info("오디오 추출: %s", video_path)
    Path(audio_path).parent.mkdir(parents=True, exist_ok=True)

    clip = VideoFileClip(video_path)
    try:
        if clip.audio is None:
            raise ValueError("영상에 오디오 트랙이 없습니다.")
        clip.audio.write_audiofile(audio_path, logger=None)
    finally:
        clip.close()

    logger.info("오디오 저장 완료: %s", audio_path)
    return audio_path


def transcribe(audio_path: str) -> str:
    """
    OpenAI Whisper(whisper-1) API로 오디오 파일을 텍스트로 변환한다.

    Args:
        audio_path: WAV/MP3 등 Whisper가 지원하는 오디오 파일 경로

    Returns:
        전사된 텍스트 (앞뒤 공백 제거)
    """
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    logger.info("Whisper STT 시작: %s", audio_path)
    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )

    text = result.text.strip()
    logger.info("STT 완료 (%d자)", len(text))
    return text
