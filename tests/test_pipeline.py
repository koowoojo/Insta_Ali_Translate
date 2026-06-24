"""worker.pipeline 경로 헬퍼 및 오케스트레이션 단위 테스트."""

from worker.pipeline import job_asset_dir


def test_job_asset_dir():
    """job_id별 assets/jobs/{id} 경로가 올바르게 구성되는지 검증."""
    p = job_asset_dir("abc-123")
    assert str(p).replace("\\", "/").endswith("assets/jobs/abc-123")
