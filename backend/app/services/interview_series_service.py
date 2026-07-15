"""Service for stakeholder-specific interview topic series."""

import re
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.interview_series import InterviewSeries
from app.models.project import Project
from app.models.stakeholder_profile import StakeholderProfile


class InterviewSeriesService:
    """Owns topic-series lookup, validation, and creation."""

    def list_series(
        self, db: Session, project_id: str, stakeholder_profile_id: str
    ) -> List[InterviewSeries]:
        return (
            db.query(InterviewSeries)
            .filter(
                InterviewSeries.project_id == project_id,
                InterviewSeries.stakeholder_profile_id == stakeholder_profile_id,
            )
            .order_by(InterviewSeries.created_at.asc())
            .all()
        )

    def get_series(self, db: Session, series_id: str) -> InterviewSeries:
        series = db.query(InterviewSeries).filter(InterviewSeries.id == series_id).first()
        if not series:
            raise ValueError(f"Interview series {series_id} not found")
        return series

    def create_series(
        self,
        db: Session,
        project_id: str,
        stakeholder_profile_id: str,
        title: str,
        topic_key: Optional[str] = None,
    ) -> InterviewSeries:
        self.get_project_and_profile(db, project_id, stakeholder_profile_id)
        normalized_key = self.normalize_topic_key(topic_key or title)
        existing = (
            db.query(InterviewSeries)
            .filter(
                InterviewSeries.project_id == project_id,
                InterviewSeries.stakeholder_profile_id == stakeholder_profile_id,
                InterviewSeries.topic_key == normalized_key,
            )
            .first()
        )
        if existing:
            return existing

        series = InterviewSeries(
            id=f"series_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            stakeholder_profile_id=stakeholder_profile_id,
            title=title.strip() or "一般訪談主題",
            topic_key=normalized_key,
            status="active",
        )
        db.add(series)
        db.commit()
        db.refresh(series)
        return series

    def get_or_create_default_series(
        self, db: Session, project_id: str, stakeholder_profile_id: str
    ) -> InterviewSeries:
        existing = (
            db.query(InterviewSeries)
            .filter(
                InterviewSeries.project_id == project_id,
                InterviewSeries.stakeholder_profile_id == stakeholder_profile_id,
                InterviewSeries.status == "active",
                InterviewSeries.topic_key == "default",
            )
            .order_by(InterviewSeries.created_at.asc())
            .first()
        )
        if existing:
            return existing

        _, profile = self.get_project_and_profile(db, project_id, stakeholder_profile_id)
        return self.create_series(
            db,
            project_id=project_id,
            stakeholder_profile_id=stakeholder_profile_id,
            title=profile.role_title or "一般訪談主題",
            topic_key="default",
        )

    @staticmethod
    def get_project_and_profile(
        db: Session, project_id: str, stakeholder_profile_id: str
    ) -> tuple[Project, StakeholderProfile]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        profile = (
            db.query(StakeholderProfile)
            .filter(
                StakeholderProfile.id == stakeholder_profile_id,
                StakeholderProfile.project_id == project_id,
            )
            .first()
        )
        if not profile:
            raise ValueError(f"Stakeholder {stakeholder_profile_id} not found")
        return project, profile

    @staticmethod
    def normalize_topic_key(value: str) -> str:
        normalized = re.sub(r"\s+", "-", value.strip().lower())
        normalized = re.sub(r"[^\w\-\u4e00-\u9fff]", "", normalized)
        return normalized[:80] or "default"


interview_series_service = InterviewSeriesService()
