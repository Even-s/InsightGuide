"""Prep session API clean-break contract tests."""

import inspect

from app.main import app
from app.api.routes import prep_sessions
from app.api.routes import session_outputs
from app.schemas.prep_session import PrepSessionWithDocument


def _route_response_model(path: str, method: str):
    for route in prep_sessions.router.routes:
        if route.path == path and method in getattr(route, "methods", set()):
            return getattr(route, "response_model", None)
    raise AssertionError(f"Route {method} {path} not found")


def test_prep_sessions_router_does_not_expose_legacy_repair_endpoint():
    """Clean v2 no longer supports old prep-session repair endpoints."""
    paths = {route.path for route in prep_sessions.router.routes}

    assert "/fix-stuck-sessions" not in paths


def test_list_prep_sessions_filters_by_document_id_not_deck_id():
    """Prep-session list query contract should use documentId only."""
    signature = inspect.signature(prep_sessions.list_prep_sessions)
    document_id_param = signature.parameters["document_id"]

    assert document_id_param.default.alias == "documentId"
    assert document_id_param.default.alias != "deckId"


def test_single_prep_session_endpoints_return_document_contract():
    """Create/get/update must return document metadata, not a partial legacy shape."""
    assert _route_response_model("/", "POST") is PrepSessionWithDocument
    assert _route_response_model("/{prep_session_id}", "GET") is PrepSessionWithDocument
    assert _route_response_model("/{prep_session_id}", "PATCH") is PrepSessionWithDocument


def test_clean_break_api_does_not_mount_session_reports_router():
    tags = {tag for route in app.routes for tag in getattr(route, "tags", [])}

    assert "session-reports" not in tags


def test_clean_break_api_does_not_mount_session_brd_router():
    """Session-scoped BRD drafts were replaced by project-level BRD generation."""
    paths = {route.path for route in app.routes}
    tags = {tag for route in app.routes for tag in getattr(route, "tags", [])}

    assert "brd" not in tags
    assert not any(path.startswith("/api/brd") for path in paths)


def test_interview_session_outputs_do_not_expose_legacy_report_endpoints():
    """Session output routes must not reintroduce per-session report/analytics APIs."""
    paths = {route.path for route in session_outputs.router.routes}

    assert "/{session_id}/report" not in paths
    assert "/{session_id}/analytics" not in paths
    assert "/{session_id}/outputs/generate" not in paths
