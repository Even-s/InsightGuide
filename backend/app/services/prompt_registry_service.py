"""Prompt Registry Service — centralized prompt management with DB-first, code-fallback."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

import random

from app.models.prompt_template import PromptTemplate, PromptVersion, PromptABTest, PromptABResult, PromptApprovalRequest, PromptAuditLog, PromptUsageLog

logger = logging.getLogger(__name__)


class PromptRegistryService:
    """Manages prompt templates and versions with fallback to code defaults."""

    def get_all_templates(self, db: Session, category: Optional[str] = None) -> List[PromptTemplate]:
        query = db.query(PromptTemplate).filter(PromptTemplate.is_active.is_(True))
        if category:
            query = query.filter(PromptTemplate.category == category)
        return query.order_by(PromptTemplate.category, PromptTemplate.name).all()

    def get_template_by_key(self, db: Session, key: str) -> Optional[PromptTemplate]:
        return db.query(PromptTemplate).filter(PromptTemplate.key == key).first()

    def get_active_version(self, db: Session, key: str) -> Optional[PromptVersion]:
        template = self.get_template_by_key(db, key)
        if not template:
            return None
        return (
            db.query(PromptVersion)
            .filter(PromptVersion.template_id == template.id, PromptVersion.status == "published")
            .first()
        )

    def get_versions(self, db: Session, key: str) -> List[PromptVersion]:
        template = self.get_template_by_key(db, key)
        if not template:
            return []
        return (
            db.query(PromptVersion)
            .filter(PromptVersion.template_id == template.id)
            .order_by(PromptVersion.version_number.desc())
            .all()
        )

    def render_prompt(self, db: Session, key: str, variables: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Render prompt with variables. Returns {system_prompt, user_prompt} or None if not found."""
        import time
        start = time.time()

        ab_test = self.get_active_ab_test(db, key)
        if ab_test:
            roll = random.randint(1, 100)
            if roll <= ab_test.traffic_percent_b:
                ab_variant, ab_version_id = "b", ab_test.variant_b_id
            else:
                ab_variant, ab_version_id = "a", ab_test.variant_a_id
            version = db.query(PromptVersion).filter(PromptVersion.id == ab_version_id).first()
        else:
            ab_variant, ab_test = None, None
            version = self.get_active_version(db, key)

        if not version:
            return None

        template = version.template
        required_vars = template.input_variables or []
        missing = [v for v in required_vars if v not in variables]
        if missing:
            logger.warning(f"Prompt '{key}' missing variables: {missing}")

        result = {}
        try:
            if version.system_prompt:
                try:
                    result["system_prompt"] = version.system_prompt.format(**variables)
                except KeyError:
                    result["system_prompt"] = version.system_prompt

            if version.user_prompt_template:
                try:
                    result["user_prompt"] = version.user_prompt_template.format(**variables)
                except KeyError:
                    result["user_prompt"] = version.user_prompt_template

            latency = int((time.time() - start) * 1000)
            self.log_usage(db, key, version_id=version.id, latency_ms=latency)
            if ab_test and ab_variant:
                self.record_ab_result(db, ab_test.id, ab_variant, version.id, latency_ms=latency)
        except Exception as e:
            latency = int((time.time() - start) * 1000)
            self.log_usage(db, key, version_id=version.id, latency_ms=latency, status="error", error_message=str(e))
            if ab_test and ab_variant:
                self.record_ab_result(db, ab_test.id, ab_variant, version.id, latency_ms=latency, status="error")
            raise

        return result

    def get_prompt(self, db: Session, key: str, variables: Dict[str, Any], fallback_system: Optional[str] = None, fallback_user: Optional[str] = None) -> Dict[str, str]:
        """High-level helper: DB-first, code-fallback. Used by AI services."""
        try:
            rendered = self.render_prompt(db, key, variables)
            if rendered:
                return rendered
        except Exception as e:
            logger.debug(f"Registry render failed for '{key}': {e}")

        result = {}
        if fallback_system:
            try:
                result["system_prompt"] = fallback_system.format(**variables)
            except KeyError:
                result["system_prompt"] = fallback_system
        if fallback_user:
            try:
                result["user_prompt"] = fallback_user.format(**variables)
            except KeyError:
                result["user_prompt"] = fallback_user
        return result

    def detect_drift(self, db: Session) -> List[Dict]:
        """Check registry health. Reports missing prompts (not yet seeded) and unseeded keys.
        NOTE: DB is source of truth. Content differences from seed are expected and NOT reported as drift.
        """
        from app.services.prompt_seed_data import PROMPT_SEEDS

        issues = []
        seeded_keys = {s["key"] for s in PROMPT_SEEDS}

        for seed in PROMPT_SEEDS:
            key = seed["key"]
            version = self.get_active_version(db, key)
            if not version:
                issues.append({"key": key, "type": "missing", "detail": "需要 seed — 尚無已發布版本"})

        # Check if registry has templates not in seed (manually added)
        all_templates = self.get_all_templates(db)
        for t in all_templates:
            if t.key not in seeded_keys:
                issues.append({"key": t.key, "type": "custom", "detail": "Dashboard 手動新增（無 seed 對應）"})

        return issues

    def export_all(self, db: Session) -> List[Dict]:
        """Export all templates + active versions as JSON-serializable dicts."""
        templates = self.get_all_templates(db)
        result = []
        for t in templates:
            active = next((v for v in t.versions if v.status == "published"), None)
            result.append({
                "key": t.key,
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "model": t.model,
                "risk_level": t.risk_level,
                "service_file": t.service_file,
                "service_function": t.service_function,
                "input_variables": t.input_variables,
                "output_format": t.output_format,
                "system_prompt": active.system_prompt if active else None,
                "user_prompt_template": active.user_prompt_template if active else None,
            })
        return result

    def import_all(self, db: Session, data: List[Dict]) -> Dict[str, int]:
        """Import templates from exported JSON. Creates or updates."""
        created = 0
        updated = 0
        for item in data:
            existing = self.get_template_by_key(db, item["key"])
            if not existing:
                self.seed_template(
                    db, key=item["key"], name=item["name"], category=item["category"],
                    system_prompt=item.get("system_prompt") or "",
                    user_prompt_template=item.get("user_prompt_template"),
                    description=item.get("description"), model=item.get("model"),
                    risk_level=item.get("risk_level", "medium"),
                    service_file=item.get("service_file"),
                    service_function=item.get("service_function"),
                    input_variables=item.get("input_variables"),
                    output_format=item.get("output_format"),
                )
                created += 1
            else:
                new_sp = item.get("system_prompt")
                new_upt = item.get("user_prompt_template")
                active = self.get_active_version(db, item["key"])
                if active and (active.system_prompt != new_sp or active.user_prompt_template != new_upt):
                    version = self.create_version(
                        db, item["key"],
                        system_prompt=new_sp,
                        user_prompt_template=new_upt,
                        notes="Imported from export",
                    )
                    self.publish_version(db, item["key"], version.id)
                    updated += 1
        return {"created": created, "updated": updated}

    def create_version(
        self,
        db: Session,
        key: str,
        system_prompt: Optional[str] = None,
        user_prompt_template: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> PromptVersion:
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        max_version = (
            db.query(PromptVersion.version_number)
            .filter(PromptVersion.template_id == template.id)
            .order_by(PromptVersion.version_number.desc())
            .first()
        )
        next_version = (max_version[0] + 1) if max_version else 1

        version = PromptVersion(
            id=f"pv_{uuid.uuid4().hex[:12]}",
            template_id=template.id,
            version_number=next_version,
            status="draft",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            notes=notes,
        )
        db.add(version)
        db.flush()
        self._emit_audit(db, template.id, "created_draft", version_id=version.id)
        db.commit()
        db.refresh(version)
        return version

    def publish_version(self, db: Session, key: str, version_id: str, _allow_archived: bool = False) -> PromptVersion:
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        version = db.query(PromptVersion).filter(
            PromptVersion.id == version_id,
            PromptVersion.template_id == template.id,
        ).first()
        if not version:
            raise ValueError(f"Version '{version_id}' not found")
        if version.status == "archived" and not _allow_archived:
            raise ValueError("Cannot publish an archived version directly — use rollback")

        # Unpublish current
        db.query(PromptVersion).filter(
            PromptVersion.template_id == template.id,
            PromptVersion.status == "published",
        ).update({"status": "archived", "updated_at": datetime.utcnow()})

        version.status = "published"
        version.published_at = datetime.utcnow()
        version.updated_at = datetime.utcnow()
        self._emit_audit(db, template.id, "published", version_id=version.id)
        db.commit()
        db.refresh(version)
        return version

    def rollback(self, db: Session, key: str) -> Optional[PromptVersion]:
        """Rollback to the most recent archived version."""
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        previous = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.template_id == template.id,
                PromptVersion.status == "archived",
            )
            .order_by(PromptVersion.version_number.desc())
            .first()
        )
        if not previous:
            return None

        self._emit_audit(db, template.id, "rolled_back", version_id=previous.id)
        return self.publish_version(db, key, previous.id, _allow_archived=True)

    def archive_version(self, db: Session, key: str, version_id: str) -> PromptVersion:
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        version = db.query(PromptVersion).filter(
            PromptVersion.id == version_id,
            PromptVersion.template_id == template.id,
        ).first()
        if not version:
            raise ValueError(f"Version '{version_id}' not found")

        version.status = "archived"
        version.updated_at = datetime.utcnow()
        self._emit_audit(db, template.id, "archived", version_id=version.id)
        db.commit()
        db.refresh(version)
        return version

    def seed_template(
        self,
        db: Session,
        key: str,
        name: str,
        category: str,
        system_prompt: str,
        user_prompt_template: Optional[str] = None,
        description: Optional[str] = None,
        model: Optional[str] = None,
        risk_level: str = "medium",
        service_file: Optional[str] = None,
        service_function: Optional[str] = None,
        input_variables: Optional[List[str]] = None,
        output_format: Optional[str] = None,
    ) -> PromptTemplate:
        """Create or update a template and publish its first version."""
        existing = self.get_template_by_key(db, key)
        if existing:
            return existing

        template = PromptTemplate(
            id=f"pt_{uuid.uuid4().hex[:12]}",
            key=key,
            name=name,
            description=description,
            category=category,
            model=model,
            risk_level=risk_level,
            service_file=service_file,
            service_function=service_function,
            input_variables=input_variables,
            output_format=output_format,
        )
        db.add(template)
        db.flush()

        version = PromptVersion(
            id=f"pv_{uuid.uuid4().hex[:12]}",
            template_id=template.id,
            version_number=1,
            status="published",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            published_at=datetime.utcnow(),
        )
        db.add(version)
        db.commit()
        db.refresh(template)
        return template


    # --- A/B Testing ---

    def get_active_ab_test(self, db: Session, key: str) -> Optional[PromptABTest]:
        template = self.get_template_by_key(db, key)
        if not template:
            return None
        return (
            db.query(PromptABTest)
            .filter(PromptABTest.template_id == template.id, PromptABTest.status == "active")
            .first()
        )

    def create_ab_test(
        self, db: Session, key: str, name: str, variant_a_id: str, variant_b_id: str, traffic_percent_b: int = 50
    ) -> PromptABTest:
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        existing = self.get_active_ab_test(db, key)
        if existing:
            raise ValueError(f"Template '{key}' already has an active A/B test")

        if traffic_percent_b < 0 or traffic_percent_b > 100:
            raise ValueError("traffic_percent_b must be 0-100")

        test = PromptABTest(
            id=f"ab_{uuid.uuid4().hex[:12]}",
            template_id=template.id,
            name=name,
            variant_a_id=variant_a_id,
            variant_b_id=variant_b_id,
            traffic_percent_b=traffic_percent_b,
        )
        db.add(test)
        self._emit_audit(db, template.id, "ab_test_started", details={"test_id": test.id, "name": name, "traffic_b": traffic_percent_b})
        db.commit()
        db.refresh(test)
        return test

    def stop_ab_test(self, db: Session, key: str, winner: Optional[str] = None) -> PromptABTest:
        test = self.get_active_ab_test(db, key)
        if not test:
            raise ValueError("No active A/B test found")

        test.status = "completed"
        test.ended_at = datetime.utcnow()
        test.winner = winner
        test.updated_at = datetime.utcnow()

        template = self.get_template_by_key(db, key)
        self._emit_audit(db, template.id, "ab_test_completed", details={"test_id": test.id, "winner": winner})

        if winner and template:
            winning_version_id = test.variant_a_id if winner == "a" else test.variant_b_id
            self.publish_version(db, key, winning_version_id)

        db.commit()
        db.refresh(test)
        return test

    def resolve_ab_variant(self, db: Session, key: str) -> Optional[PromptVersion]:
        """Resolve which version to use, considering active A/B test."""
        test = self.get_active_ab_test(db, key)
        if not test:
            return self.get_active_version(db, key)

        roll = random.randint(1, 100)
        if roll <= test.traffic_percent_b:
            variant = "b"
            version_id = test.variant_b_id
        else:
            variant = "a"
            version_id = test.variant_a_id

        version = db.query(PromptVersion).filter(PromptVersion.id == version_id).first()
        return version

    def record_ab_result(self, db: Session, test_id: str, variant: str, version_id: str, latency_ms: Optional[int] = None, token_count: Optional[int] = None, status: str = "success"):
        result = PromptABResult(
            id=f"ar_{uuid.uuid4().hex[:12]}",
            test_id=test_id,
            variant=variant,
            version_id=version_id,
            latency_ms=latency_ms,
            token_count=token_count,
            status=status,
        )
        db.add(result)
        db.commit()

    def get_ab_test_stats(self, db: Session, test_id: str) -> Dict:
        from sqlalchemy import func

        stats = {}
        for variant in ("a", "b"):
            row = (
                db.query(
                    func.count(PromptABResult.id).label("calls"),
                    func.avg(PromptABResult.latency_ms).label("avg_latency"),
                    func.sum(PromptABResult.token_count).label("total_tokens"),
                )
                .filter(PromptABResult.test_id == test_id, PromptABResult.variant == variant)
                .first()
            )
            error_count = (
                db.query(func.count(PromptABResult.id))
                .filter(PromptABResult.test_id == test_id, PromptABResult.variant == variant, PromptABResult.status == "error")
                .scalar()
            )
            stats[variant] = {
                "calls": row.calls or 0,
                "avgLatencyMs": round(row.avg_latency or 0, 1),
                "totalTokens": row.total_tokens or 0,
                "errorCount": error_count or 0,
                "errorRate": round((error_count or 0) / max(row.calls or 1, 1) * 100, 1),
            }
        return stats

    # --- Approval Workflow ---

    def requires_approval(self, db: Session, key: str) -> bool:
        """Check if a template requires approval to publish (high-risk)."""
        template = self.get_template_by_key(db, key)
        return template.risk_level == "high" if template else False

    def request_approval(self, db: Session, key: str, version_id: str, requester: Optional[str] = None) -> PromptApprovalRequest:
        template = self.get_template_by_key(db, key)
        if not template:
            raise ValueError(f"Template '{key}' not found")

        version = db.query(PromptVersion).filter(
            PromptVersion.id == version_id, PromptVersion.template_id == template.id
        ).first()
        if not version:
            raise ValueError(f"Version '{version_id}' not found")

        existing = (
            db.query(PromptApprovalRequest)
            .filter(
                PromptApprovalRequest.version_id == version_id,
                PromptApprovalRequest.status == "pending",
            )
            .first()
        )
        if existing:
            raise ValueError("An approval request is already pending for this version")

        request = PromptApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:12]}",
            template_id=template.id,
            version_id=version_id,
            requester=requester,
        )
        db.add(request)
        self._emit_audit(db, template.id, "approval_requested", version_id=version_id, actor=requester)
        db.commit()
        db.refresh(request)
        return request

    def approve(self, db: Session, request_id: str, reviewer: Optional[str] = None, comment: Optional[str] = None) -> PromptApprovalRequest:
        req = db.query(PromptApprovalRequest).filter(PromptApprovalRequest.id == request_id).first()
        if not req:
            raise ValueError("Approval request not found")
        if req.status != "pending":
            raise ValueError(f"Request is already {req.status}")

        req.status = "approved"
        req.reviewer = reviewer
        req.review_comment = comment
        req.reviewed_at = datetime.utcnow()

        template = db.query(PromptTemplate).filter(PromptTemplate.id == req.template_id).first()
        self._emit_audit(db, template.id, "approval_approved", version_id=req.version_id, actor=reviewer)

        # Auto-publish on approval
        self.publish_version(db, template.key, req.version_id)
        db.commit()
        db.refresh(req)
        return req

    def reject(self, db: Session, request_id: str, reviewer: Optional[str] = None, comment: Optional[str] = None) -> PromptApprovalRequest:
        req = db.query(PromptApprovalRequest).filter(PromptApprovalRequest.id == request_id).first()
        if not req:
            raise ValueError("Approval request not found")
        if req.status != "pending":
            raise ValueError(f"Request is already {req.status}")

        req.status = "rejected"
        req.reviewer = reviewer
        req.review_comment = comment
        req.reviewed_at = datetime.utcnow()

        template = db.query(PromptTemplate).filter(PromptTemplate.id == req.template_id).first()
        self._emit_audit(db, template.id, "approval_rejected", version_id=req.version_id, actor=reviewer, details={"comment": comment})
        db.commit()
        db.refresh(req)
        return req

    def get_pending_approvals(self, db: Session, key: Optional[str] = None) -> List[PromptApprovalRequest]:
        query = db.query(PromptApprovalRequest).filter(PromptApprovalRequest.status == "pending")
        if key:
            template = self.get_template_by_key(db, key)
            if template:
                query = query.filter(PromptApprovalRequest.template_id == template.id)
        return query.order_by(PromptApprovalRequest.requested_at.desc()).all()

    def _emit_audit(self, db: Session, template_id: str, action: str, version_id: Optional[str] = None, actor: Optional[str] = None, details: Optional[Dict] = None):
        log = PromptAuditLog(
            id=f"pa_{uuid.uuid4().hex[:12]}",
            template_id=template_id,
            version_id=version_id,
            action=action,
            actor=actor,
            details=details,
        )
        db.add(log)

    def log_usage(self, db: Session, template_key: str, version_id: Optional[str] = None, latency_ms: Optional[int] = None, token_count: Optional[int] = None, status: str = "success", error_message: Optional[str] = None):
        log = PromptUsageLog(
            id=f"pu_{uuid.uuid4().hex[:12]}",
            template_key=template_key,
            version_id=version_id,
            latency_ms=latency_ms,
            token_count=token_count,
            status=status,
            error_message=error_message,
        )
        db.add(log)
        db.commit()

    def get_audit_logs(self, db: Session, key: str, limit: int = 50) -> List[PromptAuditLog]:
        template = self.get_template_by_key(db, key)
        if not template:
            return []
        return (
            db.query(PromptAuditLog)
            .filter(PromptAuditLog.template_id == template.id)
            .order_by(PromptAuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_usage_stats(self, db: Session, key: str) -> Dict:
        from sqlalchemy import func
        results = (
            db.query(
                func.count(PromptUsageLog.id).label("total_calls"),
                func.avg(PromptUsageLog.latency_ms).label("avg_latency_ms"),
                func.sum(PromptUsageLog.token_count).label("total_tokens"),
            )
            .filter(PromptUsageLog.template_key == key)
            .first()
        )
        error_count = (
            db.query(func.count(PromptUsageLog.id))
            .filter(PromptUsageLog.template_key == key, PromptUsageLog.status == "error")
            .scalar()
        )
        return {
            "totalCalls": results.total_calls or 0,
            "avgLatencyMs": round(results.avg_latency_ms or 0, 1),
            "totalTokens": results.total_tokens or 0,
            "errorCount": error_count or 0,
        }


prompt_registry_service = PromptRegistryService()
