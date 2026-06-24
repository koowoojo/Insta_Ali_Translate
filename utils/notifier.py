"""
텔레그램 실패 알림 유틸리티.

파이프라인 작업이 failed 상태가 되면 운영자에게 Telegram Bot API로
실패 요약 메시지를 전송한다. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID가
비어 있으면 전송을 건너뛰고 경고 로그만 남긴다.
"""

import logging

import requests

from utils.config import get_settings

# 모듈 전용 로거 (setup_logging() 호출 후 루트 핸들러에 연결됨)
logger = logging.getLogger(__name__)

# Telegram Bot API sendMessage 엔드포인트 베이스 URL
_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


def format_failure_message(job_id: str, url: str, step: str, error: str) -> str:
    """
    파이프라인 실패 알림용 텍스트 메시지를 설계 스펙 형식으로 포맷한다.

    Args:
        job_id: DB Job 식별자
        url: 처리 대상 AliExpress 상품 URL
        step: 실패한 파이프라인 단계 (예: scraping, tts)
        error: 오류 상세 문자열

    Returns:
        Telegram sendMessage text 필드에 넣을 멀티라인 문자열
    """
    return (
        "[Insta_Ali] 작업 실패\n"
        f"Job: {job_id}\n"
        f"URL: {url}\n"
        f"단계: {step}\n"
        f"에러: {error}"
    )


def send_telegram_failure(job_id: str, url: str, step: str, error: str) -> None:
    """
    파이프라인 실패 시 Telegram Bot API로 알림을 전송한다.

    TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 비어 있으면 API 호출 없이
    경고 로그만 남기고 즉시 반환한다.

    Args:
        job_id: DB Job 식별자
        url: 처리 대상 AliExpress 상품 URL
        step: 실패한 파이프라인 단계
        error: 오류 상세 문자열
    """
    settings = get_settings()
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()

    if not token or not chat_id:
        logger.warning(
            "Telegram 알림 스킵: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 미설정"
        )
        return

    message = format_failure_message(job_id, url, step, error)
    api_url = _TELEGRAM_API_BASE.format(token=token)

    try:
        response = requests.post(
            api_url,
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        response.raise_for_status()
        logger.info("Telegram 실패 알림 전송 완료 (job_id=%s, step=%s)", job_id, step)
    except requests.RequestException as exc:
        logger.error(
            "Telegram 알림 전송 실패 (job_id=%s): %s",
            job_id,
            exc,
        )
