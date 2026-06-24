"""
tts_generator 모듈 단위 테스트.

build_tts_request 파라미터 구조만 검증한다.
OpenAI HTTP 연동(generate_speech) 테스트는 포함하지 않는다.
"""

from modules.tts_generator import build_tts_request


def test_build_tts_request():
    """TTS API 요청 본문에 input·model·voice가 올바르게 설정된다."""
    payload = build_tts_request("안녕하세요", "tts-1-hd", "nova", speed=0.95)
    assert payload["input"] == "안녕하세요"
    assert payload["model"] == "tts-1-hd"
    assert payload["voice"] == "nova"
    assert payload["speed"] == 0.95
    assert payload["response_format"] == "mp3"
