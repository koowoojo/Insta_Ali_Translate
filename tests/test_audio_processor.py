"""
audio_processor 모듈 단위 테스트.

자막용 텍스트 청킹(chunk_text_for_subtitles)만 검증한다.
MoviePy·OpenAI Whisper 연동 테스트는 포함하지 않는다.
"""

from modules.audio_processor import chunk_text_for_subtitles, chunk_text_reels_style


def test_chunk_text_for_subtitles():
    """한글 텍스트를 지정 크기로 균등 분할한다."""
    text = "가나다라마바사아자차카타파하"
    chunks = chunk_text_for_subtitles(text, chunk_size=4)
    assert chunks == ["가나다라", "마바사아", "자차카타", "파하"]


def test_chunk_text_reels_style_short_phrases():
    """릴스 스타일: 짧은 구절 단위로 분할한다."""
    chunks = chunk_text_reels_style("지금 이거 모르면 손해예요 정말 대박", max_chars=12)
    assert all(len(c) <= 12 for c in chunks)
    assert "".join(chunks).replace(" ", "") == "지금이거모르면손해예요정말대박"
