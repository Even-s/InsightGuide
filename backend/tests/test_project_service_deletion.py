"""Regression tests for project deletion with active theme references."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models.interview_session import InterviewSession
from app.models.project import Project
from app.services.project_service import ProjectService


def _project_and_session():
    project = Project(
        id="proj_delete",
        user_id="user_default",
        title="Project to delete",
        mode="formal",
    )
    session = InterviewSession(
        id="session_delete",
        prep_session_id="doc_delete",
        document_id="doc_delete",
        user_id="user_default",
        project_id=project.id,
        status="idle",
        current_theme_id="theme_delete",
        created_at=datetime.utcnow(),
    )
    return project, session


def _delete_db(project, sessions):
    db = MagicMock()
    project_query = MagicMock()
    project_query.filter.return_value.first.return_value = project
    sessions_query = MagicMock()
    sessions_query.filter.return_value.all.return_value = sessions
    db.query.side_effect = [project_query, sessions_query]
    return db


def test_delete_project_clears_current_theme_before_deleting_project():
    project, session = _project_and_session()
    db = _delete_db(project, [session])

    deleted = ProjectService().delete_project(db, project.id)

    assert deleted is True
    assert session.current_theme_id is None
    db.flush.assert_called_once_with()
    db.delete.assert_called_once_with(project)
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
    method_names = [method_call[0] for method_call in db.method_calls]
    assert method_names.index("flush") < method_names.index("delete")


def test_delete_project_rolls_back_if_reference_cleanup_fails():
    project, session = _project_and_session()
    db = _delete_db(project, [session])
    db.flush.side_effect = RuntimeError("flush failed")

    with pytest.raises(RuntimeError, match="flush failed"):
        ProjectService().delete_project(db, project.id)

    assert session.current_theme_id is None
    db.delete.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once_with()


def test_delete_project_returns_false_when_project_does_not_exist():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    assert ProjectService().delete_project(db, "proj_missing") is False

    db.flush.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()
