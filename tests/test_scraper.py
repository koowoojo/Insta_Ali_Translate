"""
scraper 모듈 단위 테스트.

HTML fixture 기반 MP4 URL 추출(find_mp4_url_in_html)만 검증한다.
Playwright·네트워크 연동 테스트는 포함하지 않는다.
"""

import re

from modules.scraper import find_mp4_url_in_html

SAMPLE_HTML = """
<html><body>
<video src="https://cdn.example.com/video.mp4"></video>
</body></html>
"""


def test_find_mp4_in_video_tag():
    """<video src="..."> 태그에서 MP4 URL을 추출한다."""
    url = find_mp4_url_in_html(SAMPLE_HTML)
    assert url == "https://cdn.example.com/video.mp4"


def test_find_mp4_in_page_source():
    """페이지 소스 JSON/JS 변수 내 video_url 필드에서 MP4를 찾는다."""
    html = 'var x = {"video_url":"https://cdn.example.com/promo.mp4"}'
    url = find_mp4_url_in_html(html)
    assert url == "https://cdn.example.com/promo.mp4"


def test_find_mp4_returns_none():
    """MP4 URL이 없으면 None을 반환한다."""
    assert find_mp4_url_in_html("<html></html>") is None
