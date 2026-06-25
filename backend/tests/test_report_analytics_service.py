"""
Unit tests for Report Analytics Service
Tests report generation, coverage stats, and performance metrics.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from app.models.interview_session import InterviewSession
from app.models.utterance import Utterance
from app.services.report_analytics_service import ReportAnalyticsService, report_analytics_service


class TestReportAnalyticsService:
    """Test suite for report analytics service."""

    @pytest.fixture
    def mock_db(self):
        db = Mock()
        db.query = Mock(return_value=Mock())
        return db

    @pytest.fixture
    def sample_session(self):
        now = datetime.utcnow()
        session = InterviewSession(
            id="session-123",
            prep_session_id="prep-123",
            document_id="doc-123",
            user_id="user-123",
            status="ended",
            started_at=now - timedelta(minutes=30),
            ended_at=now,
            paused_duration_seconds=0,
            created_at=now - timedelta(minutes=35),
        )
        return session

    def test_service_initialization(self):
        assert report_analytics_service is not None
        assert isinstance(report_analytics_service, ReportAnalyticsService)

    def test_service_has_required_methods(self):
        assert hasattr(report_analytics_service, "generate_comprehensive_report")
        assert hasattr(report_analytics_service, "calculate_coverage_stats")
        assert hasattr(report_analytics_service, "generate_timeline")
        assert hasattr(report_analytics_service, "calculate_performance_metrics")
        assert hasattr(report_analytics_service, "generate_insights")

    # --- _count_chinese_characters ---

    def test_count_chinese_basic(self):
        assert report_analytics_service._count_chinese_characters("你好世界") == 4

    def test_count_chinese_mixed(self):
        count = report_analytics_service._count_chinese_characters("Hello 你好 World 世界")
        assert count == 4

    def test_count_chinese_empty(self):
        assert report_analytics_service._count_chinese_characters("") == 0
        assert report_analytics_service._count_chinese_characters(None) == 0

    def test_count_chinese_only_english(self):
        assert report_analytics_service._count_chinese_characters("Hello World") == 0

    def test_count_chinese_with_punctuation(self):
        count = report_analytics_service._count_chinese_characters("你好，世界！")
        assert count == 4

    def test_count_chinese_numbers_excluded(self):
        count = report_analytics_service._count_chinese_characters("123你好456")
        assert count == 2

    # --- calculate_performance_metrics ---

    @patch("app.services.report_analytics_service.interview_service")
    def test_performance_metrics_basic(self, mock_interview_svc, mock_db, sample_session):
        mock_interview_svc.calculate_active_duration.return_value = 1800

        utterances = [
            Utterance(
                id="u1",
                session_id="session-123",
                speaker="interviewee",
                transcript="今天介紹機器學習的基本概念和應用場景",
                created_at=datetime.utcnow(),
            ),
            Utterance(
                id="u2",
                session_id="session-123",
                speaker="interviewee",
                transcript="深度學習是機器學習的一個子領域",
                created_at=datetime.utcnow(),
            ),
        ]

        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = utterances
        mock_query.scalar.return_value = 3
        mock_db.query.return_value = mock_query

        metrics = report_analytics_service.calculate_performance_metrics(mock_db, sample_session)

        assert "total_duration_seconds" in metrics
        assert "total_utterances" in metrics
        assert metrics["total_utterances"] == 2
        assert metrics["total_characters"] > 0
        assert metrics["characters_per_minute"] > 0

    def test_performance_metrics_method_exists(self):
        """Verify performance metrics method signature."""
        assert callable(report_analytics_service.calculate_performance_metrics)

    # --- calculate_coverage_stats ---
    # These tests need complex DB mock chains; tested via integration tests instead.

    def test_coverage_stats_method_exists(self):
        """Verify coverage stats method signature."""
        assert callable(report_analytics_service.calculate_coverage_stats)

    def test_generate_timeline_method_exists(self):
        """Verify timeline method signature."""
        assert callable(report_analytics_service.generate_timeline)

    def test_analyze_topic_performance_method_exists(self):
        """Verify topic performance method signature."""
        assert callable(report_analytics_service.analyze_topic_performance)
