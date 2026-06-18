"""Prompt Template and Version models for the Prompt Registry."""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, JSON, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.db.session import Base


class PromptTemplate(Base):
    """A registered prompt template with metadata."""

    __tablename__ = "prompt_templates"

    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False, index=True)
    model = Column(String, nullable=True)
    risk_level = Column(String, nullable=False, default="medium")
    service_file = Column(String, nullable=True)
    service_function = Column(String, nullable=True)
    input_variables = Column(JSON, nullable=True)
    output_format = Column(String, nullable=True)
    response_schema = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("PromptVersion", back_populates="template", cascade="all, delete-orphan", order_by="PromptVersion.version_number.desc()")


class PromptVersion(Base):
    """A specific version of a prompt template."""

    __tablename__ = "prompt_versions"

    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("prompt_templates.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="draft", index=True)  # draft | published | archived

    system_prompt = Column(Text, nullable=True)
    user_prompt_template = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    template = relationship("PromptTemplate", back_populates="versions")


class PromptABTest(Base):
    """An A/B test between two prompt versions."""

    __tablename__ = "prompt_ab_tests"

    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("prompt_templates.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active")  # active | paused | completed
    variant_a_id = Column(String, ForeignKey("prompt_versions.id"), nullable=False)
    variant_b_id = Column(String, ForeignKey("prompt_versions.id"), nullable=False)
    traffic_percent_b = Column(Integer, nullable=False, default=50)  # 0-100, percent going to B
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    winner = Column(String, nullable=True)  # a | b | null
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class PromptABResult(Base):
    """Individual call result within an A/B test."""

    __tablename__ = "prompt_ab_results"

    id = Column(String, primary_key=True)
    test_id = Column(String, ForeignKey("prompt_ab_tests.id"), nullable=False, index=True)
    variant = Column(String, nullable=False)  # a | b
    version_id = Column(String, ForeignKey("prompt_versions.id"), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="success")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromptApprovalRequest(Base):
    """Approval request for publishing a high-risk prompt version."""

    __tablename__ = "prompt_approval_requests"

    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("prompt_templates.id"), nullable=False, index=True)
    version_id = Column(String, ForeignKey("prompt_versions.id"), nullable=False)
    requester = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # pending | approved | rejected
    reviewer = Column(String, nullable=True)
    review_comment = Column(Text, nullable=True)
    requested_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class PromptAuditLog(Base):
    """Tracks all publish/rollback/archive actions on prompt templates."""

    __tablename__ = "prompt_audit_logs"

    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("prompt_templates.id"), nullable=False, index=True)
    version_id = Column(String, ForeignKey("prompt_versions.id"), nullable=True)
    action = Column(String, nullable=False)  # published | rolled_back | archived | created_draft
    actor = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PromptUsageLog(Base):
    """Tracks each prompt render/call for observability."""

    __tablename__ = "prompt_usage_logs"

    id = Column(String, primary_key=True)
    template_key = Column(String, nullable=False, index=True)
    version_id = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    token_count = Column(Integer, nullable=True)
    status = Column(String, nullable=False, default="success")  # success | error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
