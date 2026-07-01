"""
AliExpress 상품 페이지 Playwright 스크래핑 모듈.

주요 기능:
- HTML/페이지 소스에서 MP4 비디오 URL 탐색 (find_mp4_url_in_html)
- Playwright Chromium으로 페이지 로드 후 MP4 다운로드 (scrape_video)
- httpx 스트리밍 다운로드 (_download_mp4)
- Headful 수동 로그인 후 storage_state 저장 (save_login_session)

설정은 utils.config.Settings에서 proxy_url, aliexpress_session_path 등을 읽는다.
실패 시 utils.exceptions.PipelineError / VideoNotFoundError를 발생시킨다.
"""

from __future__ import annotations

import argparse
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from playwright.sync_api import sync_playwright

from utils.config import get_settings
from utils.exceptions import PipelineError, VideoNotFoundError

# 모듈 전용 로거 — setup_logging() 호출 후 루트 핸들러에 전파된다.
logger = logging.getLogger(__name__)

# Linux Docker headless 봇 차단 완화용 데스크톱 Chrome UA
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# 페이지 소스 전역 탐색용 MP4 URL 정규식 (video 태그·video_url 키워드 매칭 실패 시 폴백)
MP4_PATTERN = re.compile(r"https?://[^\s\"'<>]+\.mp4", re.IGNORECASE)


def find_mp4_url_in_html(html: str, base_url: str = "") -> str | None:
    """
    HTML 문자열에서 MP4 비디오 URL을 우선순위대로 탐색한다.

    탐색 순서:
    1. <video ... src="..."> 태그의 src 속성 (상대 URL은 base_url과 결합)
    2. video_url 키워드 뒤의 .mp4 경로 (JSON/JS 변수 등)
    3. 페이지 전체에서 MP4_PATTERN에 매칭되는 첫 URL

    Args:
        html: Playwright page.content() 등으로 얻은 HTML/소스 문자열
        base_url: 상대 경로 src를 절대 URL로 만들 때 사용할 기준 URL

    Returns:
        발견된 MP4 URL 문자열, 없으면 None
    """
    # 1) <video src="..."> 우선 매칭
    video_tag_match = re.search(
        r'<video[^>]+src=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if video_tag_match:
        resolved = urljoin(base_url, video_tag_match.group(1))
        logger.debug("video 태그에서 MP4 URL 발견: %s", resolved)
        return resolved

    # 2) video_url: "....mp4" 또는 video_url = '....mp4' 형태
    video_url_field_match = re.search(
        r'video_url["\']?\s*[:=]\s*["\']([^"\']+\.mp4)',
        html,
        re.IGNORECASE,
    )
    if video_url_field_match:
        found = video_url_field_match.group(1)
        logger.debug("video_url 필드에서 MP4 URL 발견: %s", found)
        return found

    # 3) 임의의 .mp4 HTTP(S) URL (마지막 폴백)
    generic_match = MP4_PATTERN.search(html)
    if generic_match:
        found = generic_match.group(0)
        logger.debug("전역 MP4 패턴 매칭: %s", found)
        return found

    logger.debug("HTML에서 MP4 URL을 찾지 못함 (base_url=%s)", base_url or "(없음)")
    return None


def _download_mp4(url: str, dest: Path, proxy_url: str = "") -> Path:
    """
    httpx 스트리밍으로 MP4 파일을 로컬 경로에 저장한다.

    Args:
        url: 다운로드할 MP4 절대 URL
        dest: 저장할 파일 경로 (부모 디렉터리는 자동 생성)
        proxy_url: httpx 프록시 서버 URL (비어 있으면 프록시 미사용)

    Returns:
        저장 완료된 dest Path

    Raises:
        httpx.HTTPStatusError: HTTP 4xx/5xx 응답 시
        httpx.RequestError: 네트워크 오류 시
    """
    # 출력 디렉터리가 없으면 미리 생성
    dest.parent.mkdir(parents=True, exist_ok=True)

    # proxy_url이 설정된 경우에만 httpx Client에 프록시 전달 (httpx 0.28+는 proxy 단수 인자)
    client_kwargs: dict = {"timeout": 120.0, "follow_redirects": True}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url
    logger.info("MP4 다운로드 시작: %s -> %s", url, dest)

    with httpx.Client(**client_kwargs) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with dest.open("wb") as file_handle:
                for chunk in response.iter_bytes():
                    file_handle.write(chunk)

    logger.info("MP4 저장 완료: %s", dest)
    return dest


def scrape_video(url: str, output_path: str, max_retries: int = 3) -> str:
    """
    AliExpress 상품 URL에서 MP4를 추출해 output_path에 저장한다.

    Playwright로 페이지를 로드한 뒤 find_mp4_url_in_html로 URL을 찾고,
    _download_mp4로 파일을 받는다. CAPTCHA·일시 오류 등은 지수 백오프로 재시도한다.

    Args:
        url: AliExpress 상품 페이지 URL
        output_path: 저장할 로컬 MP4 파일 경로
        max_retries: 최대 재시도 횟수 (기본 3)

    Returns:
        저장된 파일의 절대/상대 경로 문자열

    Raises:
        VideoNotFoundError: 페이지에 MP4 URL이 없을 때 (재시도 소진 전에도 발생 가능)
        PipelineError: max_retries 초과 후 마지막 오류를 wrapping하여 발생
    """
    settings = get_settings()
    dest = Path(output_path)
    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("스크래핑 시도 %d/%d: %s", attempt, max_retries, url)

            with sync_playwright() as playwright:
                # headless Chromium 기동 — proxy_url 설정 시 launch proxy 적용
                launch_kwargs: dict = {"headless": True}
                if settings.proxy_url:
                    launch_kwargs["proxy"] = {"server": settings.proxy_url}
                    logger.debug("Playwright 프록시 사용: %s", settings.proxy_url)

                browser = playwright.chromium.launch(**launch_kwargs)

                # 저장된 AliExpress 로그인 세션이 있으면 storage_state 로드
                context_kwargs: dict = {
                    "locale": "ko-KR",
                    "user_agent": _DEFAULT_USER_AGENT,
                }
                session_path = Path(settings.aliexpress_session_path)
                if session_path.exists() and session_path.stat().st_size > 50:
                    context_kwargs["storage_state"] = str(session_path)
                    logger.debug("세션 storage_state 로드: %s", session_path)

                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                # AliExpress 상품 영상 URL은 JS 렌더 후 주입되므로 domcontentloaded + 추가 대기
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(10_000)
                html = page.content()
                mp4_url = find_mp4_url_in_html(html, base_url=url)
                browser.close()

            if not mp4_url:
                raise VideoNotFoundError()

            saved = _download_mp4(mp4_url, dest, settings.proxy_url)
            return str(saved)

        except Exception as exc:
            last_err = exc
            logger.warning("스크래핑 실패 (시도 %d): %s", attempt, exc)
            if attempt < max_retries:
                # 지수 백오프: 2^attempt 초 (2, 4, 8 ...)
                backoff_seconds = 2**attempt
                logger.info("%d초 후 재시도...", backoff_seconds)
                time.sleep(backoff_seconds)

    # 모든 재시도 실패 — 파이프라인 scraping 단계 오류로 통일
    raise PipelineError("scraping", str(last_err))


def _launch_headful_browser(playwright):
    """
    설치된 Chrome 채널을 우선 사용하고, 없으면 Playwright Chromium으로 폴백한다.

    AliExpress는 내장 Chromium보다 실제 Chrome/Edge 로그인 성공률이 높다.
    """
    launch_kwargs = {"headless": False}
    for channel in ("chrome", "msedge", None):
        try:
            if channel:
                logger.info("브라우저 채널 시도: %s", channel)
                return playwright.chromium.launch(channel=channel, **launch_kwargs)
            logger.info("브라우저 채널 폴백: playwright chromium")
            return playwright.chromium.launch(**launch_kwargs)
        except Exception as exc:
            logger.warning("채널 %s 기동 실패: %s", channel or "chromium", exc)
    raise PipelineError("scraping", "Headful 브라우저를 기동할 수 없습니다. Chrome 또는 Edge를 설치하세요.")


def save_login_session() -> None:
    """
    Headful 브라우저로 AliExpress에 수동 로그인 후 storage_state를 저장한다.

    사용자가 터미널에서 Enter를 누를 때까지 대기한 뒤,
    settings.aliexpress_session_path 경로에 JSON 세션 파일을 기록한다.
    이후 scrape_video 호출 시 해당 세션을 재사용한다.

    로그인이 안 되면 utils.session_import 로 Chrome 쿠키를 가져오거나,
    공개 상품 페이지는 세션 없이도 scrape_video 가 동작할 수 있다.
    """
    settings = get_settings()
    session_path = Path(settings.aliexpress_session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Headful 브라우저로 AliExpress 로그인 세션 저장 시작")
    with sync_playwright() as playwright:
        browser = _launch_headful_browser(playwright)
        context = browser.new_context(locale="ko-KR")
        page = context.new_page()
        page.goto("https://ko.aliexpress.com/", wait_until="domcontentloaded", timeout=60000)
        print(
            "\n[안내] 열린 브라우저에서 AliExpress 로그인을 완료한 뒤 이 터미널로 돌아와 Enter를 누르세요.\n"
            "로그인이 계속 실패하면 README의 '쿠키 가져오기' 방법을 사용하세요.\n"
        )
        input("AliExpress 로그인 후 Enter를 누르세요...")
        context.storage_state(path=str(session_path))
        browser.close()

    logger.info("세션 저장 완료: %s", session_path)


def capture_session_from_cdp(cdp_url: str = "http://127.0.0.1:9222") -> Path:
    """
    디버그 모드 Chrome(CDP)에 연결해 현재 쿠키를 storage_state로 저장한다.

    Hot Cleaner 암호화 쿠키 export 없이, 사용자가 이미 로그인한 Chrome 탭의
    세션을 그대로 가져올 때 사용한다.

    사전 준비:
        chrome.exe --remote-debugging-port=9222
    AliExpress 로그인 후 이 함수를 호출한다.

    Args:
        cdp_url: Chrome remote debugging URL (기본 9222)

    Returns:
        저장된 storage_state Path
    """
    settings = get_settings()
    session_path = Path(settings.aliexpress_session_path)
    session_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("CDP 연결 시도: %s", cdp_url)
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp(cdp_url)
        except Exception as exc:
            raise PipelineError(
                "scraping",
                f"Chrome CDP 연결 실패 ({cdp_url}). "
                "먼저 Chrome을 --remote-debugging-port=9222 로 실행하세요. "
                f"원인: {exc}",
            ) from exc

        if not browser.contexts:
            browser.close()
            raise PipelineError(
                "scraping",
                "Chrome에 열린 컨텍스트가 없습니다. AliExpress 탭을 연 뒤 다시 시도하세요.",
            )

        context = browser.contexts[0]
        ali_tab = next(
            (p for p in context.pages if "aliexpress" in p.url.lower()),
            context.pages[0] if context.pages else None,
        )
        if ali_tab is None:
            browser.close()
            raise PipelineError("scraping", "Chrome에 열린 탭이 없습니다.")

        logger.info("세션 캡처 대상 탭: %s", ali_tab.url)
        context.storage_state(path=str(session_path))
        browser.close()

    logger.info("CDP 세션 저장 완료: %s", session_path)
    return session_path


if __name__ == "__main__":
    from utils.logging_setup import setup_logging

    setup_logging()
    cli_parser = argparse.ArgumentParser(description="AliExpress MP4 스크래퍼 CLI")
    cli_parser.add_argument(
        "--login",
        action="store_true",
        help="Headful 브라우저로 로그인 후 storage_state 저장",
    )
    cli_parser.add_argument("--url", help="스크래핑할 AliExpress 상품 URL")
    cli_parser.add_argument(
        "--output",
        default="assets/raw_video.mp4",
        help="다운로드 MP4 저장 경로 (기본: assets/raw_video.mp4)",
    )
    cli_args = cli_parser.parse_args()

    if cli_args.login:
        save_login_session()
    elif cli_args.url:
        result_path = scrape_video(cli_args.url, cli_args.output)
        logger.info("스크래핑 완료: %s", result_path)
    else:
        cli_parser.print_help()
