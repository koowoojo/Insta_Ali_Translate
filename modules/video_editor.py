"""
MoviePy 기반 9:16 숏폼 영상 합성 모듈.

주요 기능:
- compute_center_crop_box: 원본 해상도에서 9:16 중앙 크롭 영역 계산
- _sync_video_to_target: 원본 영상 길이 기준 루프/컷 (영상 길이가 마스터)
- fit_audio_to_target: 더빙 오디오를 영상 길이에 맞춤 (속도 조절·무음 패딩)
- _build_reels_subtitle_clips: 인스타 릴스 스타일 자막 (흰 글씨 + 반투명 배경)
- compose_shorts: 크롭·리사이즈·동기화·자막·렌더까지 일괄 처리
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
from moviepy import (
    AudioArrayClip,
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)

from modules.audio_processor import chunk_text_reels_style
from utils.config import get_settings

logger = logging.getLogger(__name__)

TARGET_W, TARGET_H = 1080, 1920


def compute_center_crop_box(
    w: int,
    h: int,
    target_w: int = 9,
    target_h: int = 16,
) -> tuple[int, int, int, int]:
    """원본 프레임에서 9:16 중앙 크롭 박스 (x1, y1, x2, y2)를 반환한다."""
    target_ratio = target_w / target_h
    current_ratio = w / h

    if current_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x1 = (w - new_w) // 2
        return x1, 0, x1 + new_w, h

    new_h = int(w / target_ratio)
    y1 = (h - new_h) // 2
    return 0, y1, w, y1 + new_h


def _sync_video_to_target(video: VideoFileClip, target_duration: float) -> VideoFileClip:
    """
    원본 영상 길이(target_duration)에 맞춘다. 오디오가 아닌 **영상이 기준**.

    - 영상 ≥ 목표: 목표 시점에서 컷
    - 영상 < 목표: 루프 후 목표 길이까지 연장
    """
    if video.duration >= target_duration:
        return video.subclipped(0, target_duration)

    loops = math.ceil(target_duration / video.duration)
    looped = concatenate_videoclips([video] * loops)
    return looped.subclipped(0, target_duration)


def fit_audio_to_target(audio: AudioFileClip, target_duration: float) -> AudioFileClip:
    """
    더빙 오디오를 target_duration(초)에 맞춘다.

    1. 약간 길면 속도 업 (최대 1.15배)
    2. 약간 짧으면 속도 다운 (최소 0.82배)
    3. 그래도 짧으면 끝에 무음 패딩
    """
    tolerance = 0.25
    clip = audio

    if clip.duration > target_duration + tolerance:
        factor = clip.duration / target_duration
        factor = min(factor, 1.15)
        clip = clip.with_speed_scaled(factor)
        logger.info("오디오 속도 업: x%.2f → %.1f초", factor, clip.duration)

    if clip.duration < target_duration - tolerance:
        factor = clip.duration / target_duration
        factor = max(factor, 0.82)
        clip = clip.with_speed_scaled(factor)
        logger.info("오디오 속도 다운: x%.2f → %.1f초", factor, clip.duration)

    if clip.duration < target_duration - 0.05:
        pad_sec = target_duration - clip.duration
        n_samples = int(pad_sec * clip.fps)
        silence = np.zeros((n_samples, 2))
        silence_clip = AudioArrayClip(silence, fps=clip.fps)
        clip = concatenate_audioclips([clip, silence_clip])
        logger.info("오디오 무음 패딩: +%.1f초 → %.1f초", pad_sec, clip.duration)

    if clip.duration > target_duration + 0.05:
        clip = clip.subclipped(0, target_duration)

    return clip


def _subtitle_timings(chunks: list[str], total_duration: float) -> list[tuple[float, float]]:
    """글자 수 비례로 각 자막 청크의 (시작, 길이) 초를 계산한다."""
    weights = [max(len(c.replace(" ", "")), 1) for c in chunks]
    total_weight = sum(weights)
    timings: list[tuple[float, float]] = []
    cursor = 0.0

    for weight in weights:
        seg = total_duration * weight / total_weight
        timings.append((cursor, seg))
        cursor += seg

    return timings


def _make_reels_subtitle_elements(
    chunk: str,
    start: float,
    duration: float,
) -> list:
    """릴스 스타일 자막 요소(배경 박스 + 텍스트)를 반환한다."""
    settings = get_settings()
    text_width = TARGET_W - settings.subtitle_margin_x * 2

    txt = TextClip(
        text=chunk,
        font=settings.subtitle_font_path,
        font_size=settings.subtitle_font_size,
        color="white",
        stroke_color="black",
        stroke_width=2,
        method="caption",
        size=(text_width, None),
        text_align="center",
    )

    pad_x, pad_y = 32, 18
    bg_w = min(int(txt.w) + pad_x * 2, TARGET_W - 64)
    bg_h = int(txt.h) + pad_y * 2
    y_center = int(TARGET_H * settings.subtitle_position_y_ratio)

    bg = (
        ColorClip(size=(bg_w, bg_h), color=(20, 20, 20))
        .with_opacity(0.78)
        .with_duration(duration)
        .with_start(start)
        .with_position(("center", y_center - pad_y))
    )

    text_clip = (
        txt.with_duration(duration)
        .with_start(start)
        .with_position(("center", y_center))
    )

    return [bg, text_clip]


def _build_reels_subtitle_clips(script: str, duration: float) -> list:
    """릴스 스타일 짧은 구절 자막 클립 리스트를 생성한다."""
    settings = get_settings()
    chunks = chunk_text_reels_style(script, settings.subtitle_chunk_size)
    if not chunks:
        return []

    timings = _subtitle_timings(chunks, duration)
    clips: list = []

    for chunk, (start, seg) in zip(chunks, timings):
        clips.extend(_make_reels_subtitle_elements(chunk, start, seg))

    return clips


def compose_shorts(
    video_path: str,
    audio_path: str,
    script: str,
    output_path: str,
    target_duration_sec: float | None = None,
) -> str:
    """
    원본 영상과 더빙·대본으로 9:16 숏폼 MP4를 렌더한다.

    **영상 길이가 마스터** — target_duration_sec(기본: 원본 길이)에 맞춰
    영상·오디오·자막을 동기화한다.

    Args:
        video_path: 입력 원본 MP4
        audio_path: 더빙 MP3/WAV
        script: 자막 대본
        output_path: 출력 MP4 경로
        target_duration_sec: 최종 영상 길이(초). None이면 원본 영상 길이 사용
    """
    logger.info("영상 합성 시작: video=%s audio=%s", video_path, audio_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    video = VideoFileClip(video_path).without_audio()
    audio = AudioFileClip(audio_path)
    final: VideoFileClip | CompositeVideoClip | None = None
    fitted_audio: AudioFileClip | None = None

    try:
        target = target_duration_sec if target_duration_sec is not None else video.duration
        target = min(target, settings.max_shorts_duration)
        logger.info("목표 영상 길이: %.2f초 (원본 %.2f초)", target, video.duration)

        x1, y1, x2, y2 = compute_center_crop_box(video.w, video.h)
        video = video.cropped(x1=x1, y1=y1, x2=x2, y2=y2).resized((TARGET_W, TARGET_H))
        video = _sync_video_to_target(video, target)

        fitted_audio = fit_audio_to_target(audio, target)
        video = video.with_audio(fitted_audio)

        subs = _build_reels_subtitle_clips(script, target)
        final = CompositeVideoClip([video, *subs], size=(TARGET_W, TARGET_H)) if subs else video

        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
    finally:
        video.close()
        audio.close()
        if fitted_audio is not None and fitted_audio is not audio:
            fitted_audio.close()
        if final is not None and final is not video:
            final.close()

    logger.info("렌더 완료: %.1f초 → %s", target, output_path)
    return output_path
