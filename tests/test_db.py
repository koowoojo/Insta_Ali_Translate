"""SQLite Job 모델 단위 테스트."""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Job


def test_create_job():
    """인메모리 SQLite에 Job 1건을 생성·저장할 수 있는지 확인."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    job = Job(id=str(uuid.uuid4()), url="https://example.com", status="pending")
    db.add(job)
    db.commit()
    assert db.query(Job).count() == 1
