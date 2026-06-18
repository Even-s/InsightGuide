"""BRD Readiness Service - evaluates whether a project is ready for BRD generation."""

import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.brd_readiness_report import BRDReadinessReport
from app.models.requirement_evidence_matrix import RequirementEvidenceMatrix, EvidenceMatrixEntry
from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.stakeholder_slot import StakeholderSlot
from app.models.stakeholder_profile import StakeholderProfile
from app.models.project import Project

logger = logging.getLogger(__name__)


class BRDReadinessService:

    def generate_report(self, db: Session, project_id: str) -> BRDReadinessReport:
        """Generate a BRD Readiness Report for a project."""
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Gather data
        matrix = db.query(RequirementEvidenceMatrix).filter(
            RequirementEvidenceMatrix.project_id == project_id
        ).first()

        entries = []
        if matrix:
            entries = db.query(EvidenceMatrixEntry).filter(
                EvidenceMatrixEntry.matrix_id == matrix.id
            ).all()

        memos = db.query(InterviewInsightMemo).filter(
            InterviewInsightMemo.project_id == project_id,
            InterviewInsightMemo.status == "completed",
        ).all()

        slots = db.query(StakeholderSlot).filter(
            StakeholderSlot.project_id == project_id
        ).all()

        profiles = db.query(StakeholderProfile).filter(
            StakeholderProfile.project_id == project_id,
            StakeholderProfile.status == "interviewed",
        ).all()

        # Evaluate
        stakeholder_coverage = self._evaluate_stakeholder_coverage(slots, profiles)
        section_readiness = self._evaluate_section_readiness(entries, memos)
        conflicts = self._gather_conflicts(entries)
        suggestions = self._build_suggestions(entries, slots, stakeholder_coverage)

        # Calculate score
        readiness_score = self._calculate_readiness_score(
            section_readiness, stakeholder_coverage, conflicts, entries
        )

        # Determine generation mode
        if readiness_score >= 0.75 and not conflicts:
            generation_mode = "full"
            is_ready = True
            recommendation = "可生成完整 BRD。所有必要章節都有足夠證據支撐。"
        elif readiness_score >= 0.45:
            generation_mode = "partial"
            is_ready = True
            recommendation = "可生成部分 BRD 草稿。部分章節證據不足，將標記為「待確認」。"
        else:
            generation_mode = "not_ready"
            is_ready = False
            recommendation = "建議補訪後再生成 BRD。目前證據不足以產出可靠文件。"

        # Build report
        validated_count = len([e for e in entries if e.validation_status == "validated"])

        report = BRDReadinessReport(
            id=f"ready_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            is_ready=is_ready,
            readiness_score=round(readiness_score, 3),
            generation_mode=generation_mode,
            recommendation=recommendation,
            ready_sections=section_readiness["ready"],
            insufficient_sections=section_readiness["insufficient"],
            unresolved_conflicts=conflicts,
            suggested_next_interviews=suggestions,
            stakeholder_coverage=stakeholder_coverage,
            total_memos=len(memos),
            total_stakeholders_interviewed=len(profiles),
            total_evidence_entries=len(entries),
            validated_requirements=validated_count,
            generated_at=datetime.utcnow(),
        )

        report.markdown_content = self._render_markdown(report)

        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    def get_latest_report(self, db: Session, project_id: str) -> Optional[BRDReadinessReport]:
        """Get the most recent readiness report for a project."""
        return db.query(BRDReadinessReport).filter(
            BRDReadinessReport.project_id == project_id
        ).order_by(BRDReadinessReport.generated_at.desc()).first()

    def can_generate_brd(self, db: Session, project_id: str) -> Dict[str, Any]:
        """Quick check: can we generate a BRD?"""
        report = self.get_latest_report(db, project_id)
        if not report:
            return {"can_generate": False, "mode": "not_ready", "reason": "尚未產生準備度報告"}

        return {
            "can_generate": report.is_ready,
            "mode": report.generation_mode,
            "reason": report.recommendation,
            "readiness_score": report.readiness_score,
        }

    def _evaluate_stakeholder_coverage(self, slots: List, profiles: List) -> Dict[str, Any]:
        """Evaluate stakeholder plan coverage."""
        required_slots = [s for s in slots if s.priority == "required"]
        completed_slots = [s for s in required_slots if s.status == "completed"]
        skipped_slots = [s for s in required_slots if s.status == "skipped"]
        missing_slots = [s for s in required_slots if s.status in ("unassigned", "partially_assigned", "assigned")]

        interviewed_roles = {p.stakeholder_type for p in profiles}

        return {
            "required_roles_total": len(required_slots),
            "required_roles_covered": len(completed_slots),
            "skipped_roles": [s.role_label for s in skipped_slots],
            "missing_roles": [s.role_label for s in missing_slots],
            "missing_role_categories": [s.role_category for s in missing_slots],
            "interviewed_roles": sorted(interviewed_roles),
            "coverage_percentage": round(
                len(completed_slots) / max(len(required_slots), 1) * 100, 1
            ),
        }

    def _evaluate_section_readiness(self, entries: List, memos: List) -> Dict[str, List]:
        """Evaluate which BRD sections have enough evidence."""
        ready = []
        insufficient = []

        # Derive sections from entry categories and memo content
        categories_with_evidence = {}
        for entry in entries:
            cat = entry.category or "general"
            if cat not in categories_with_evidence:
                categories_with_evidence[cat] = {"entries": 0, "validated": 0, "roles": set()}
            categories_with_evidence[cat]["entries"] += 1
            if entry.validation_status == "validated":
                categories_with_evidence[cat]["validated"] += 1
            for role in (entry.source_roles or []):
                categories_with_evidence[cat]["roles"].add(role)

        # Check pain points and process coverage from memos
        has_pain_points = any(m.pain_points for m in memos)
        has_process = any(m.process_descriptions for m in memos)
        has_constraints = any(m.constraints_and_assumptions for m in memos)

        if has_pain_points:
            ready.append({
                "section": "業務流程痛點",
                "evidence_count": sum(len(m.pain_points or []) for m in memos),
                "source_roles": sorted({
                    (m.stakeholder_summary or {}).get("role", "unknown")
                    for m in memos if m.pain_points
                }),
                "confidence": "high",
            })
        else:
            insufficient.append({
                "section": "業務流程痛點",
                "reason": "尚無訪談提及痛點",
                "missing_roles": [],
                "priority": "high",
            })

        if has_process:
            ready.append({
                "section": "現有流程描述",
                "evidence_count": sum(len(m.process_descriptions or []) for m in memos),
                "source_roles": sorted({
                    (m.stakeholder_summary or {}).get("role", "unknown")
                    for m in memos if m.process_descriptions
                }),
                "confidence": "medium",
            })

        if has_constraints:
            ready.append({
                "section": "限制與假設",
                "evidence_count": sum(len(m.constraints_and_assumptions or []) for m in memos),
                "source_roles": sorted({
                    (m.stakeholder_summary or {}).get("role", "unknown")
                    for m in memos if m.constraints_and_assumptions
                }),
                "confidence": "medium",
            })

        # Check categories from evidence matrix
        for cat, info in categories_with_evidence.items():
            section_name = {
                "functional": "功能性需求",
                "non_functional": "非功能性需求",
                "integration": "系統整合需求",
                "permission": "權限模型",
                "business_process": "業務流程需求",
                "data": "資料需求",
                "ux": "使用者體驗需求",
            }.get(cat, cat)

            if info["validated"] >= 2 or (info["entries"] >= 3 and len(info["roles"]) >= 2):
                ready.append({
                    "section": section_name,
                    "evidence_count": info["entries"],
                    "source_roles": sorted(info["roles"]),
                    "confidence": "high" if info["validated"] >= 2 else "medium",
                })
            elif info["entries"] > 0:
                insufficient.append({
                    "section": section_name,
                    "reason": f"僅 {len(info['roles'])} 個角色提供證據" if len(info["roles"]) < 2 else "驗證數不足",
                    "missing_roles": [],
                    "priority": "medium",
                })

        # Check for technical sections
        tech_roles_heard = any("engineering" in (e.source_roles or []) for e in entries)
        if not tech_roles_heard and entries:
            insufficient.append({
                "section": "技術限制與系統整合",
                "reason": "尚無工程/IT角色訪談",
                "missing_roles": ["engineering", "IT"],
                "priority": "high",
            })

        return {"ready": ready, "insufficient": insufficient}

    def _gather_conflicts(self, entries: List) -> List[Dict]:
        """Gather unresolved conflicts from matrix entries."""
        conflicts = []
        for entry in entries:
            if entry.validation_status == "conflicted" and entry.conflicts:
                for c in entry.conflicts:
                    conflicts.append({
                        "topic": entry.requirement_candidate[:60],
                        "conflicting_parties": c.get("conflicting_roles", []),
                        "details": c.get("description", ""),
                    })
        return conflicts

    def _build_suggestions(self, entries: List, slots: List, coverage: Dict) -> List[Dict]:
        """Build next interview suggestions."""
        suggestions = []

        # From missing roles in stakeholder plan
        for role_label in coverage.get("missing_roles", []):
            matching_cat = None
            for s in slots:
                if s.role_label == role_label:
                    matching_cat = s.role_category
                    break
            suggestions.append({
                "target_role": role_label,
                "role_category": matching_cat or "unknown",
                "objective": f"完成「{role_label}」角色的需求訪談",
                "urgency": "high",
                "key_questions": [],
            })

        # From missing_validation_from in entries
        role_demand: Dict[str, int] = {}
        for entry in entries:
            for role in (entry.missing_validation_from or []):
                role_demand[role] = role_demand.get(role, 0) + 1

        for role, count in sorted(role_demand.items(), key=lambda x: -x[1]):
            if not any(s.get("role_category") == role for s in suggestions):
                suggestions.append({
                    "target_role": role,
                    "role_category": role,
                    "objective": f"驗證 {count} 條候選需求的技術/業務可行性",
                    "urgency": "high" if count >= 3 else "medium",
                    "key_questions": [],
                })

        return suggestions[:5]

    def _calculate_readiness_score(
        self, section_readiness: Dict, coverage: Dict, conflicts: List, entries: List
    ) -> float:
        """Calculate overall readiness score (0.0 - 1.0)."""
        ready_count = len(section_readiness["ready"])
        insufficient_count = len(section_readiness["insufficient"])
        total_sections = ready_count + insufficient_count

        # Section coverage (40% weight)
        section_score = ready_count / max(total_sections, 1)

        # Stakeholder coverage (30% weight)
        stakeholder_score = coverage.get("coverage_percentage", 0) / 100

        # Evidence validation (20% weight)
        validated = len([e for e in entries if e.validation_status == "validated"])
        total_entries = len(entries)
        evidence_score = validated / max(total_entries, 1)

        # Conflict penalty (10% weight, inverted)
        conflict_penalty = min(len(conflicts) * 0.2, 1.0)
        conflict_score = 1.0 - conflict_penalty

        score = (
            section_score * 0.4 +
            stakeholder_score * 0.3 +
            evidence_score * 0.2 +
            conflict_score * 0.1
        )

        return max(0.0, min(1.0, score))

    def _render_markdown(self, report: BRDReadinessReport) -> str:
        """Render readiness report as markdown."""
        lines = []
        lines.append("# BRD 生成準備度報告")
        lines.append("")

        # Verdict
        emoji = "✅" if report.generation_mode == "full" else "⚠️" if report.generation_mode == "partial" else "❌"
        lines.append(f"## 結論 {emoji}")
        lines.append("")
        lines.append(report.recommendation or "")
        lines.append("")
        lines.append(f"**準備度分數**：{round((report.readiness_score or 0) * 100)}%")
        lines.append("")

        # Stats
        lines.append("## 統計")
        lines.append("")
        lines.append(f"| 項目 | 數量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 訪談場次 | {report.total_memos} |")
        lines.append(f"| 受訪者數 | {report.total_stakeholders_interviewed} |")
        lines.append(f"| 候選需求 | {report.total_evidence_entries} |")
        lines.append(f"| 已驗證需求 | {report.validated_requirements} |")
        lines.append("")

        # Ready sections
        if report.ready_sections:
            lines.append("## 已具備足夠證據的區塊")
            lines.append("")
            for s in report.ready_sections:
                roles = ", ".join(s.get("source_roles", []))
                lines.append(f"- **{s['section']}** — {s.get('evidence_count', 0)} 條證據 ({roles})")
            lines.append("")

        # Insufficient sections
        if report.insufficient_sections:
            lines.append("## 證據不足的區塊")
            lines.append("")
            for s in report.insufficient_sections:
                missing = ", ".join(s.get("missing_roles", []))
                reason = s.get("reason", "")
                lines.append(f"- **{s['section']}** — {reason}" + (f" (缺: {missing})" if missing else ""))
            lines.append("")

        # Conflicts
        if report.unresolved_conflicts:
            lines.append("## 未解決衝突")
            lines.append("")
            for c in report.unresolved_conflicts:
                parties = ", ".join(c.get("conflicting_parties", []))
                lines.append(f"- {c.get('topic', '')} ({parties})")
            lines.append("")

        # Suggestions
        if report.suggested_next_interviews:
            lines.append("## 建議下一輪訪談")
            lines.append("")
            lines.append("| 對象 | 目的 | 急迫性 |")
            lines.append("|------|------|--------|")
            for s in report.suggested_next_interviews:
                lines.append(f"| {s.get('target_role', '')} | {s.get('objective', '')} | {s.get('urgency', '')} |")
            lines.append("")

        return "\n".join(lines)


brd_readiness_service = BRDReadinessService()
