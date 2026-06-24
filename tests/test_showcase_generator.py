"""showcase_generator 모듈 단위 테스트 — Opal 스타일 HTML 생성 검증."""

from pathlib import Path

from utils.showcase_generator import generate_showcase


def test_generate_showcase_creates_html(tmp_path):
    """generate_showcase가 필수 UI 요소를 포함한 showcase.html을 생성하는지 확인."""
    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    (job_dir / "script.txt").write_text("한국어 대본 테스트", encoding="utf-8")
    (job_dir / "final_shorts.mp4").write_bytes(b"fake-mp4")
    (job_dir / "dubbing.mp3").write_bytes(b"fake-mp3")

    out = generate_showcase(
        job_id="job-1",
        job_dir=job_dir,
        product_url="https://www.aliexpress.com/item/123.html",
        base_url="http://localhost:8080",
    )

    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "한국어 대본 테스트" in html
    assert "final_shorts.mp4" in html
    assert "dubbing.mp3" in html
    assert "AI Generated" in html
    assert "Ready to Post" in html
    assert "#121212" in html
