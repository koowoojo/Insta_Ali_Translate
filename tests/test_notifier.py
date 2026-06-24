"""notifier 모듈 단위 테스트 — 실패 메시지 포맷 검증."""


def test_format_failure_message():
    """format_failure_message가 job_id·에러 등 핵심 필드를 포함하는지 확인."""
    from utils.notifier import format_failure_message

    msg = format_failure_message("j1", "http://x", "scraping", "timeout")
    assert "j1" in msg and "timeout" in msg
