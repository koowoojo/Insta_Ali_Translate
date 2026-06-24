"""Settings 기본값 검증 테스트."""

from utils.config import Settings


def test_settings_defaults():
    """설계 기본값이 모델에 정의되어 있는지 확인한다."""
    assert Settings.model_fields["subtitle_chunk_size"].default == 12
    assert Settings.model_fields["subtitle_font_size"].default == 62
    assert "malgunbd" in str(Settings.model_fields["subtitle_font_path"].default).lower()

    s = Settings(
        openai_api_key="test-openai",
        anthropic_api_key="test-anthropic",
    )
    assert s.max_concurrent_jobs == 2
    assert s.openai_tts_model == "tts-1-hd"
    assert s.openai_tts_voice == "nova"
