"""Evidence Matrix Service - cross-interview requirement consolidation."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.requirement_evidence_matrix import EvidenceMatrixEntry, RequirementEvidenceMatrix
from app.models.stakeholder_profile import StakeholderProfile

logger = logging.getLogger(__name__)


class EvidenceMatrixService:

    def get_or_create_matrix(self, db: Session, project_id: str) -> RequirementEvidenceMatrix:
        """Get existing matrix or create a new one."""
        matrix = (
            db.query(RequirementEvidenceMatrix)
            .filter(RequirementEvidenceMatrix.project_id == project_id)
            .first()
        )

        if not matrix:
            matrix = RequirementEvidenceMatrix(
                id=f"matrix_{uuid.uuid4().hex[:12]}",
                project_id=project_id,
                status="draft",
            )
            db.add(matrix)
            db.commit()
            db.refresh(matrix)

        return matrix

    def update_matrix(self, db: Session, project_id: str) -> RequirementEvidenceMatrix:
        """Incrementally update the evidence matrix from all completed Insight Memos."""
        matrix = self.get_or_create_matrix(db, project_id)
        matrix.status = "updating"
        db.flush()

        # Load all completed memos for this project
        memos = (
            db.query(InterviewInsightMemo)
            .filter(
                InterviewInsightMemo.project_id == project_id,
                InterviewInsightMemo.status == "completed",
            )
            .order_by(InterviewInsightMemo.interview_date)
            .all()
        )

        if not memos:
            matrix.status = "draft"
            matrix.memo_count = 0
            db.commit()
            return matrix

        # Collect all requirement candidates from all memos
        all_candidates = []
        for memo in memos:
            stakeholder = None
            if memo.stakeholder_profile_id:
                stakeholder = (
                    db.query(StakeholderProfile)
                    .filter(StakeholderProfile.id == memo.stakeholder_profile_id)
                    .first()
                )

            for candidate in memo.requirement_candidates or []:
                all_candidates.append(
                    {
                        "memo_id": memo.id,
                        "stakeholder_role": (
                            stakeholder.stakeholder_type if stakeholder else "unknown"
                        ),
                        "stakeholder_name": stakeholder.name if stakeholder else "未知",
                        "description": candidate.get("description", ""),
                        "source": candidate.get("source", "inferred"),
                        "confidence": candidate.get("confidence", "medium"),
                        "evidence_quote": candidate.get("evidence_quote", ""),
                        "needs_validation_from": candidate.get("needs_validation_from", []),
                    }
                )

        # Deduplicate and merge candidates into entries
        merged_entries = self._deduplicate_and_merge(all_candidates)

        # Clear existing entries and rebuild
        db.query(EvidenceMatrixEntry).filter(EvidenceMatrixEntry.matrix_id == matrix.id).delete()
        db.flush()

        for entry_data in merged_entries:
            entry = EvidenceMatrixEntry(
                id=f"entry_{uuid.uuid4().hex[:12]}",
                matrix_id=matrix.id,
                requirement_candidate=entry_data["requirement_candidate"],
                category=entry_data.get("category"),
                source_roles=entry_data["source_roles"],
                source_memo_ids=entry_data["source_memo_ids"],
                supporting_evidence=entry_data["supporting_evidence"],
                conflicts=entry_data.get("conflicts", []),
                validation_status=entry_data["validation_status"],
                missing_validation_from=entry_data.get("missing_validation_from", []),
                mention_count=entry_data["mention_count"],
                stakeholder_agreement_level=entry_data["stakeholder_agreement_level"],
            )
            db.add(entry)

        matrix.status = "ready"
        matrix.memo_count = len(memos)
        matrix.last_memo_id = memos[-1].id
        matrix.last_updated_at = datetime.utcnow()
        matrix.markdown_content = self._render_matrix_markdown(merged_entries)

        db.commit()
        db.refresh(matrix)

        # Update stakeholder plan based on evidence gaps
        try:
            from app.services.stakeholder_plan_service import stakeholder_plan_service

            stakeholder_plan_service._update_slot_statuses(db, project_id)
        except Exception as e:
            logger.warning(f"Failed to update plan from evidence matrix: {e}")

        return matrix

    def _deduplicate_and_merge(self, candidates: List[Dict]) -> List[Dict]:
        """Merge similar requirement candidates using simple text matching.

        For production, this would use AI semantic deduplication.
        Current approach: group by normalized description similarity.
        """
        if not candidates:
            return []

        # Try AI-based deduplication
        merged = self._ai_deduplicate(candidates)
        if merged:
            return merged

        # Fallback: simple grouping by exact description
        return self._simple_merge(candidates)

    def _ai_deduplicate(self, candidates: List[Dict]) -> Optional[List[Dict]]:
        """Use AI to semantically deduplicate and merge candidates."""
        if len(candidates) <= 2:
            return None

        try:
            from app.services.openai_service import openai_service

            candidate_list = "\n".join(
                f"{i+1}. [{c['stakeholder_role']}] {c['description']}"
                for i, c in enumerate(candidates[:30])
            )

            prompt = (
                "以下是從多場訪談中萃取的候選需求列表。請合併語意相同的需求，並產出去重後的結果。\n\n"
                f"{candidate_list}\n\n"
                "請以 JSON 陣列回傳，每個元素代表一個合併後的需求：\n"
                "[\n"
                "  {\n"
                '    "requirement_candidate": "合併後的需求描述",\n'
                '    "category": "functional|non_functional|business_process|integration|permission|data|ux",\n'
                '    "source_indices": [1, 3],\n'
                '    "conflicts": []\n'
                "  }\n"
                "]\n\n"
                "規則：\n"
                "- 語意相同或高度相似的合併為同一條\n"
                "- 保留 source_indices 標記來自哪些原始 candidates（1-based）\n"
                "- 如果不同角色有矛盾觀點，在 conflicts 中說明\n"
                "- 只回傳 JSON"
            )

            result = openai_service.chat_completion(
                messages=[
                    {"role": "system", "content": "你是需求分析師。合併相似需求。只回傳 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                model="gpt-5.4-mini",
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
                db=db,
                purpose="evidence_deduplication",
            )

            # The wrapper already parses JSON, but handle markdown code blocks if present
            if isinstance(result, str):
                content = result.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                merged_raw = json.loads(content)
            else:
                merged_raw = result

            # Build proper entries from AI merge result
            entries = []
            for item in merged_raw:
                indices = item.get("source_indices", [])
                source_candidates = [candidates[i - 1] for i in indices if 0 < i <= len(candidates)]
                if not source_candidates:
                    continue

                source_roles = list({c["stakeholder_role"] for c in source_candidates})
                source_memo_ids = list({c["memo_id"] for c in source_candidates})
                supporting_evidence = [
                    {
                        "memo_id": c["memo_id"],
                        "stakeholder_role": c["stakeholder_role"],
                        "stakeholder_name": c["stakeholder_name"],
                        "evidence_quote": c["evidence_quote"],
                        "source_type": c["source"],
                        "confidence": c["confidence"],
                    }
                    for c in source_candidates
                ]

                # Collect all missing_validation_from
                all_missing = set()
                for c in source_candidates:
                    all_missing.update(c.get("needs_validation_from", []))
                # Remove roles we already have evidence from
                all_missing -= set(source_roles)

                entries.append(
                    {
                        "requirement_candidate": item["requirement_candidate"],
                        "category": item.get("category"),
                        "source_roles": source_roles,
                        "source_memo_ids": source_memo_ids,
                        "supporting_evidence": supporting_evidence,
                        "conflicts": item.get("conflicts", []),
                        "validation_status": self._compute_validation_status(
                            source_roles, list(all_missing), item.get("conflicts", [])
                        ),
                        "missing_validation_from": list(all_missing),
                        "mention_count": len(source_candidates),
                        "stakeholder_agreement_level": self._compute_agreement_level(
                            source_roles, item.get("conflicts", [])
                        ),
                    }
                )

            return entries if entries else None

        except Exception as e:
            logger.warning(f"AI deduplication failed: {e}")
            return None

    def _simple_merge(self, candidates: List[Dict]) -> List[Dict]:
        """Fallback: treat each candidate as its own entry."""
        entries = []
        for c in candidates:
            entries.append(
                {
                    "requirement_candidate": c["description"],
                    "category": None,
                    "source_roles": [c["stakeholder_role"]],
                    "source_memo_ids": [c["memo_id"]],
                    "supporting_evidence": [
                        {
                            "memo_id": c["memo_id"],
                            "stakeholder_role": c["stakeholder_role"],
                            "stakeholder_name": c["stakeholder_name"],
                            "evidence_quote": c["evidence_quote"],
                            "source_type": c["source"],
                            "confidence": c["confidence"],
                        }
                    ],
                    "conflicts": [],
                    "validation_status": "candidate",
                    "missing_validation_from": c.get("needs_validation_from", []),
                    "mention_count": 1,
                    "stakeholder_agreement_level": "single_source",
                }
            )
        return entries

    def _compute_validation_status(
        self, source_roles: List[str], missing: List[str], conflicts: List
    ) -> str:
        if conflicts:
            return "conflicted"
        if len(source_roles) >= 2 and not missing:
            return "validated"
        if len(source_roles) >= 2:
            return "needs_more_evidence"
        return "candidate"

    def _compute_agreement_level(self, source_roles: List[str], conflicts: List) -> str:
        if conflicts:
            return "conflicted"
        if len(source_roles) >= 3:
            return "unanimous"
        if len(source_roles) >= 2:
            return "majority"
        return "single_source"

    def get_matrix_summary(self, db: Session, project_id: str) -> Dict[str, Any]:
        """Get matrix summary statistics."""
        matrix = (
            db.query(RequirementEvidenceMatrix)
            .filter(RequirementEvidenceMatrix.project_id == project_id)
            .first()
        )

        if not matrix:
            return {"total_candidates": 0, "status": "empty"}

        entries = (
            db.query(EvidenceMatrixEntry).filter(EvidenceMatrixEntry.matrix_id == matrix.id).all()
        )

        status_counts = {}
        all_roles = set()
        missing_roles = set()
        for entry in entries:
            s = entry.validation_status
            status_counts[s] = status_counts.get(s, 0) + 1
            all_roles.update(entry.source_roles or [])
            missing_roles.update(entry.missing_validation_from or [])

        return {
            "total_candidates": len(entries),
            "validated": status_counts.get("validated", 0),
            "conflicted": status_counts.get("conflicted", 0),
            "needs_more_evidence": status_counts.get("needs_more_evidence", 0),
            "candidate": status_counts.get("candidate", 0),
            "roles_heard_from": sorted(all_roles),
            "roles_missing": sorted(missing_roles - all_roles),
            "memo_count": matrix.memo_count,
            "status": matrix.status,
            "last_updated_at": (
                matrix.last_updated_at.isoformat() if matrix.last_updated_at else None
            ),
        }

    def update_entry(
        self, db: Session, entry_id: str, data: Dict[str, Any]
    ) -> Optional[EvidenceMatrixEntry]:
        """Manually update a matrix entry (e.g. mark as rejected)."""
        entry = db.query(EvidenceMatrixEntry).filter(EvidenceMatrixEntry.id == entry_id).first()
        if not entry:
            return None

        for key, value in data.items():
            if value is not None and hasattr(entry, key):
                setattr(entry, key, value)
        entry.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(entry)
        return entry

    def _render_matrix_markdown(self, entries: List[Dict]) -> str:
        """Render matrix as markdown table."""
        lines = ["# 需求證據矩陣", ""]
        lines.append("| # | 候選需求 | 來源角色 | 提及次數 | 狀態 | 缺少驗證 |")
        lines.append("|:---:|---------|---------|:---:|------|---------|")

        for i, entry in enumerate(entries, 1):
            roles = ", ".join(entry.get("source_roles", []))
            missing = ", ".join(entry.get("missing_validation_from", []))
            status_map = {
                "validated": "已驗證",
                "conflicted": "有衝突",
                "needs_more_evidence": "待補證",
                "candidate": "候選",
            }
            status = status_map.get(
                entry.get("validation_status", ""), entry.get("validation_status", "")
            )
            lines.append(
                f"| {i} | {entry['requirement_candidate'][:40]} | {roles} | {entry['mention_count']} | {status} | {missing} |"
            )

        return "\n".join(lines)


evidence_matrix_service = EvidenceMatrixService()
