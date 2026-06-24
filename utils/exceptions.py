"""
파이프라인 공통 예외 정의.

각 처리 단계(scraping, tts, video 등)에서 발생하는 오류를
PipelineError 계층으로 통일해 로깅·알림·재시도 정책을 일관되게 적용한다.
"""


class PipelineError(Exception):
    """파이프라인 단계별 오류의 기본 예외."""

    def __init__(self, step: str, message: str) -> None:
        # step: 실패한 파이프라인 단계 식별자 (예: "scraping", "tts")
        self.step = step
        # message: 사용자·운영자에게 표시할 상세 오류 메시지
        self.message = message
        super().__init__(f"[{step}] {message}")


class VideoNotFoundError(PipelineError):
    """AliExpress 페이지에서 MP4 영상 URL을 찾지 못했을 때 발생."""

    def __init__(self, message: str = "페이지에서 MP4 비디오를 찾을 수 없습니다.") -> None:
        super().__init__("scraping", message)
