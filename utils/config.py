"""
환경변수 기반 애플리케이션 설정.

pydantic-settings로 .env / 환경변수를 읽어 Settings 인스턴스를 구성한다.
필수 API 키 2종(OpenAI, Anthropic)은 기본값 없이 주입해야 하며, 나머지는
.env.example 및 설계 문서에 정의된 기본값을 사용한다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Insta_Ali 파이프라인 전역 설정."""

    # .env 파일 및 환경변수 로드 규칙 (알 수 없는 키는 무시)
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 필수 API 키 (기본값 없음) ---
    openai_api_key: str
    anthropic_api_key: str

    # --- OpenAI TTS (Whisper와 동일 API 키) ---
    openai_tts_model: str = "tts-1-hd"
    openai_tts_voice: str = "nova"

    # --- 숏폼 최대 길이(초) — 원본 영상·대본·TTS 상한 ---
    max_shorts_duration: float = 40.0

    # --- 인프라·저장소 ---
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///db/jobs.db"
    max_concurrent_jobs: int = 2

    # --- AliExpress 스크래핑 ---
    proxy_url: str = ""
    aliexpress_session_path: str = "assets/sessions/aliexpress_state.json"

    # --- Telegram 알림 (선택) ---
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # --- 자막 렌더링 (인스타 릴스 스타일) ---
    subtitle_font_path: str = "C:/Windows/Fonts/malgunbd.ttf"
    subtitle_font_size: int = 62
    subtitle_chunk_size: int = 12
    subtitle_margin_x: int = 56
    subtitle_position_y_ratio: float = 0.72

    # --- AI 모델 식별자 ---
    claude_model: str = "claude-sonnet-4-6"


@lru_cache
def get_settings() -> Settings:
    """캐시된 Settings 싱글톤을 반환한다. FastAPI/RQ 워커에서 재사용."""
    return Settings()
