"""
Unit tests for BRD PDF Export Service
Tests PDF generation functionality using ReportLab.
"""

from datetime import datetime
from io import BytesIO

import pytest

from app.models.brd import BRDDraft, BRDStatus, Requirement, RequirementPriority, RequirementType
from app.services.brd_pdf_export_service import brd_pdf_export_service


class TestBRDPDFExportService:
    """Test suite for BRD PDF export service."""

    @pytest.fixture
    def sample_brd(self):
        """Create a sample BRD draft for testing."""
        brd = BRDDraft(
            id="test-brd-123",
            interview_session_id="session-456",
            user_id="user-789",
            status=BRDStatus.COMPLETED,
            title="E-Commerce Platform Modernization",
            executive_summary="This project aims to modernize our e-commerce platform to improve user experience and increase conversion rates.",
            project_overview="The current platform is 5 years old and needs modernization to support new features and mobile experiences.",
            business_objectives=[
                "Increase conversion rate by 20%",
                "Reduce page load time by 50%",
                "Support mobile-first design",
            ],
            success_criteria=[
                "95% customer satisfaction score",
                "Page load time under 2 seconds",
                "Mobile traffic increases by 30%",
            ],
            stakeholders=[
                {"role": "Product Owner", "name": "Jane Smith"},
                {"role": "Tech Lead", "name": "John Doe"},
            ],
            assumptions=[
                "Budget approved for Q3",
                "Team available for 3 months",
                "Third-party API access confirmed",
            ],
            constraints=[
                "Must maintain backward compatibility",
                "Limited to current tech stack",
                "Go-live deadline: Dec 31",
            ],
            risks=[
                {
                    "description": "Third-party API downtime",
                    "mitigation": "Implement fallback mechanism and caching",
                }
            ],
            generated_at=datetime(2026, 6, 10, 10, 0, 0),
            generation_duration_seconds=45,
        )
        return brd

    @pytest.fixture
    def sample_requirements(self):
        """Create sample requirements for testing."""
        return [
            Requirement(
                id="req-1",
                brd_draft_id="test-brd-123",
                title="User Authentication System",
                description="Implement secure user authentication with OAuth2",
                type=RequirementType.FUNCTIONAL,
                priority=RequirementPriority.MUST_HAVE,
                user_story="As a user, I want to log in securely so that my data is protected",
                acceptance_criteria=[
                    "Users can log in with email/password",
                    "OAuth2 providers supported (Google, Facebook)",
                    "Session timeout after 30 minutes",
                ],
            ),
            Requirement(
                id="req-2",
                brd_draft_id="test-brd-123",
                title="Shopping Cart Management",
                description="Users can add, remove, and update items in cart",
                type=RequirementType.FUNCTIONAL,
                priority=RequirementPriority.MUST_HAVE,
                user_story="As a shopper, I want to manage my cart easily so that I can adjust my order",
                acceptance_criteria=["Add items to cart", "Update quantities", "Remove items"],
            ),
            Requirement(
                id="req-3",
                brd_draft_id="test-brd-123",
                title="Performance Optimization",
                description="System should load pages in under 2 seconds",
                type=RequirementType.NON_FUNCTIONAL,
                priority=RequirementPriority.SHOULD_HAVE,
                acceptance_criteria=[
                    "95th percentile load time under 2s",
                    "CDN configured for static assets",
                ],
            ),
        ]

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert brd_pdf_export_service is not None
        assert hasattr(brd_pdf_export_service, "generate_pdf")
        assert hasattr(brd_pdf_export_service, "styles")

    def test_generate_pdf_returns_bytesio(self, sample_brd):
        """Test that PDF generation returns a BytesIO object."""
        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        assert result.tell() == 0  # Should be at start of buffer

        # Check that buffer contains data
        content = result.read()
        assert len(content) > 0
        assert content.startswith(b"%PDF")  # PDF magic number

    def test_generate_pdf_with_requirements(self, sample_brd, sample_requirements):
        """Test PDF generation with requirements."""
        sample_brd.requirements = sample_requirements

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

        # Verify it's a valid PDF
        assert content.startswith(b"%PDF")

    def test_generate_pdf_with_minimal_data(self):
        """Test PDF generation with minimal required data."""
        minimal_brd = BRDDraft(
            id="minimal-brd",
            interview_session_id="session-min",
            user_id="user-min",
            status=BRDStatus.COMPLETED,
            title="Minimal BRD",
            requirements=[],
        )

        result = brd_pdf_export_service.generate_pdf(minimal_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0
        assert content.startswith(b"%PDF")

    def test_generate_pdf_all_sections(self, sample_brd, sample_requirements):
        """Test that all BRD sections are included when data is present."""
        sample_brd.requirements = sample_requirements

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        # Verify PDF was created
        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 5000  # Should be substantial with all sections

    def test_pdf_with_special_characters(self, sample_brd):
        """Test PDF generation with special characters in text."""
        sample_brd.title = "BRD with Special Chars: <>&\"'"
        sample_brd.executive_summary = 'Summary with special chars: <tag> & "quote"'

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

    def test_pdf_with_long_text(self, sample_brd):
        """Test PDF generation with very long text that spans multiple pages."""
        # Create very long executive summary
        long_text = "This is a very long executive summary. " * 500
        sample_brd.executive_summary = long_text

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 5000  # PDF compression makes it smaller than raw text

    def test_pdf_with_many_requirements(self, sample_brd):
        """Test PDF generation with many requirements."""
        # Create 50 requirements
        requirements = []
        for i in range(50):
            req = Requirement(
                id=f"req-{i}",
                brd_draft_id=sample_brd.id,
                title=f"Requirement {i}",
                description=f"Description for requirement {i}",
                type=RequirementType.FUNCTIONAL,
                priority=RequirementPriority.SHOULD_HAVE,
            )
            requirements.append(req)

        sample_brd.requirements = requirements

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 10000  # PDF with many requirements should be substantial

    def test_pdf_with_empty_lists(self, sample_brd):
        """Test PDF generation with empty lists."""
        sample_brd.business_objectives = []
        sample_brd.success_criteria = []
        sample_brd.stakeholders = []
        sample_brd.assumptions = []
        sample_brd.constraints = []
        sample_brd.risks = []
        sample_brd.requirements = []

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

    def test_pdf_with_none_values(self):
        """Test PDF generation with None values for optional fields."""
        brd = BRDDraft(
            id="none-brd",
            interview_session_id="session-none",
            user_id="user-none",
            status=BRDStatus.COMPLETED,
            title=None,
            executive_summary=None,
            project_overview=None,
            generated_at=None,
            requirements=[],
        )

        result = brd_pdf_export_service.generate_pdf(brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

    def test_requirement_priority_colors(self, sample_brd, sample_requirements):
        """Test that different priority requirements are handled."""
        # Set different priorities
        sample_requirements[0].priority = RequirementPriority.MUST_HAVE
        sample_requirements[1].priority = RequirementPriority.SHOULD_HAVE
        sample_requirements[2].priority = RequirementPriority.NICE_TO_HAVE

        sample_brd.requirements = sample_requirements

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

    def test_requirement_types(self, sample_brd):
        """Test that all requirement types are handled."""
        requirements = []
        types = [
            RequirementType.FUNCTIONAL,
            RequirementType.NON_FUNCTIONAL,
            RequirementType.BUSINESS,
            RequirementType.USER,
            RequirementType.TECHNICAL,
        ]

        for i, req_type in enumerate(types):
            req = Requirement(
                id=f"req-type-{i}",
                brd_draft_id=sample_brd.id,
                title=f"{req_type.value} Requirement",
                description=f"Description for {req_type.value}",
                type=req_type,
                priority=RequirementPriority.MUST_HAVE,
            )
            requirements.append(req)

        sample_brd.requirements = requirements

        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert isinstance(result, BytesIO)
        content = result.read()
        assert len(content) > 0

    def test_pdf_buffer_is_seekable(self, sample_brd):
        """Test that the returned buffer is seekable for streaming."""
        result = brd_pdf_export_service.generate_pdf(sample_brd)

        assert result.seekable()
        assert result.tell() == 0

        # Read some data
        result.read(100)
        assert result.tell() == 100

        # Seek back to start
        result.seek(0)
        assert result.tell() == 0

    def test_custom_styles_exist(self):
        """Test that custom paragraph styles are defined."""
        styles = brd_pdf_export_service.styles

        assert "CustomTitle" in styles
        assert "CustomHeading1" in styles
        assert "CustomHeading2" in styles
        assert "CustomBody" in styles
        assert "CustomBullet" in styles
