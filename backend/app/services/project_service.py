"""Project service."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession
from app.models.project import Project
from app.models.stakeholder_profile import StakeholderProfile

logger = logging.getLogger(__name__)


class ProjectService:

    def create_project(
        self, db: Session, user_id: str, title: str, description: Optional[str] = None
    ) -> Project:
        # Summarize description into a concise one-liner via AI
        summary = self._summarize_description(title, description)

        project = Project(
            id=f"proj_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            title=title,
            description=summary,
            status="active",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # Auto-generate initial stakeholder plan from project description
        try:
            from app.services.stakeholder_plan_service import stakeholder_plan_service

            stakeholder_plan_service.generate_initial_plan(db, project.id)
        except Exception as e:
            logger.warning(f"Failed to generate initial stakeholder plan for {project.id}: {e}")

        return project

    def _summarize_description(self, title: str, description: Optional[str]) -> Optional[str]:
        """Use AI to condense a verbose description into one clear sentence."""
        if not description or len(description) < 60:
            return description

        try:
            from app.services.openai_service import openai_service

            result = openai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "你是專案管理助理。將使用者的專案描述濃縮為一句簡潔的中文，說明這個專案要做什麼、為誰做。不要加引號，不要重複專案名稱，只回傳那一句話。",
                    },
                    {"role": "user", "content": f"專案名稱：{title}\n原始描述：{description}"},
                ],
                model="gpt-5.4-mini",
                temperature=0.2,
                max_tokens=100,
                purpose="project_description_summary",
            )
            if isinstance(result, str) and result.strip():
                return result.strip()
        except Exception as e:
            logger.warning(f"Failed to summarize project description: {e}")

        return description

    def get_project(self, db: Session, project_id: str) -> Optional[Project]:
        return db.query(Project).filter(Project.id == project_id).first()

    def list_projects(self, db: Session, user_id: str) -> List[Project]:
        return (
            db.query(Project)
            .filter(Project.user_id == user_id)
            .order_by(Project.created_at.desc())
            .all()
        )

    def update_project(
        self, db: Session, project_id: str, data: Dict[str, Any]
    ) -> Optional[Project]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None
        for key, value in data.items():
            if value is not None and hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(project)
        return project

    def delete_project(self, db: Session, project_id: str) -> bool:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return False
        db.delete(project)
        db.commit()
        return True

    def get_dashboard(self, db: Session, project_id: str) -> Dict[str, Any]:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {}

        sessions = (
            db.query(InterviewSession).filter(InterviewSession.project_id == project_id).all()
        )

        profiles = (
            db.query(StakeholderProfile).filter(StakeholderProfile.project_id == project_id).all()
        )

        completed_sessions = [s for s in sessions if s.status == "ended"]
        interviewed_profiles = [p for p in profiles if p.status == "interviewed"]

        from app.services.stakeholder_plan_service import stakeholder_plan_service

        plan_status = stakeholder_plan_service.get_plan_status(db, project_id)

        return {
            "project": project,
            "stakeholder_plan": plan_status,
            "interview_progress": {
                "total_sessions": len(sessions),
                "completed_sessions": len(completed_sessions),
                "total_profiles": len(profiles),
                "interviewed_profiles": len(interviewed_profiles),
            },
            "next_action": plan_status.get("next_recommended_action"),
        }


project_service = ProjectService()
