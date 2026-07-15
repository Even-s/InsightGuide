"""Global test isolation for external background systems."""

from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def isolate_celery_broker(monkeypatch):
    """Never enqueue application tasks into a developer's live Redis broker."""
    from app.workers.document_analysis_worker import analyze_document

    monkeypatch.setattr(analyze_document, "delay", Mock(name="isolated_celery_delay"))
