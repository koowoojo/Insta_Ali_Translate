"""
video_editor 모듈 단위 테스트.

compute_center_crop_box의 9:16 중앙 크롭 계산만 검증한다.
MoviePy 렌더·자막 합성 통합 테스트는 포함하지 않는다.
"""

from modules.video_editor import _subtitle_timings, compute_center_crop_box


def test_compute_center_crop_box_landscape():
    """1920x1080 가로 영상에서 9:16 중앙 크롭 박스를 계산한다."""
    x1, y1, x2, y2 = compute_center_crop_box(1920, 1080, target_w=9, target_h=16)

    crop_w = x2 - x1
    crop_h = y2 - y1

    # 세로 전체를 유지하고 좌우만 잘라 9:16 비율을 맞춘다.
    assert crop_h == 1080
    assert crop_w == int(1080 * 9 / 16)
    assert x1 == (1920 - crop_w) // 2
    assert y1 == 0
    assert abs(crop_w / crop_h - 9 / 16) < 0.01


def test_subtitle_timings_cover_full_duration():
    chunks = ["짧은", "조금더긴청크", "끝"]
    timings = _subtitle_timings(chunks, 30.0)
    assert len(timings) == 3
    total = sum(seg for _, seg in timings)
    assert abs(total - 30.0) < 0.01
