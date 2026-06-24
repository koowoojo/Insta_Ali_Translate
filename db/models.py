"""
SQLite Job·JobLog SQLAlchemy 모델.

설계 스펙(`docs/superpowers/specs/2026-06-22-insta-ali-pipeline-design.md` §4.3)의
jobs / job_logs 테이블 정의와 1:1로 대응한다. FastAPI·RQ 워커가 작업 상태·로그를
영구 저장하는 데 사용한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

if TYPE_CHECKING:
    # 순환 import 방지용 타입 힌트 전용 import
    pass


class Base(DeclarativeBase):
    """모든 DB 모델의 SQLAlchemy 2.x DeclarativeBase."""


class Job(Base):
    """
    AliExpress 숏폼 생성 파이프라인 작업 1건.

    id는 UUID 문자열이며, status는 pending|running|completed|failed 등을 저장한다.
    """

    __tablename__ = "jobs"

    # --- 기본 식별·입력 ---
    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # --- 실행 상태 ---
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    current_step: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- 산출물·메타 ---
    script_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # --- 타임스탬프 (SQLite CURRENT_TIMESTAMP) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # --- 관계: 작업별 단계 로그 ---
    logs: Mapped[list["JobLog"]] = relationship(
        "JobLog",
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobLog(Base):
    """
    Job 실행 중 단계별 로그 1건.

    step에는 scraping|transcribing|scripting|tts|editing 등 파이프라인 단계명이 들어간다.
    """

    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("jobs.id"),
        nullable=False,
    )
    step: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
    )

    # --- 관계: 소속 Job ---
    job: Mapped["Job"] = relationship("Job", back_populates="logs")
