"""Evidence Matrix Service - cross-interview requirement consolidation."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.requirement_evidence_matrix import RequirementEvidenceMatrix
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

    def build_entries_from_round_aggregates(
        self, db: Session, project_id: str
    ) -> tuple[List[Dict], List[Any]]:
        """Build canonical requirement entries from ready RoundAggregate rows.

        RoundAggregate is the only upstream source for project-level evidence.
        The Evidence Matrix metadata row is not a requirement source read by
        BRD or readiness generation.
        """
        from app.services.interview_round_aggregate_service import interview_round_aggregate_service

        memos = interview_round_aggregate_service.latest_memos_for_project(db, project_id)
        candidates = self._collect_requirement_candidates_from_memos(db, memos)
        if not candidates:
            return [], memos
        return self._deduplicate_and_merge(candidates), memos

    def summarize_entries(
        self, entries: List[Dict], memos: List[Any], status: str = "derived"
    ) -> Dict[str, Any]:
        """Summarize RoundAggregate-derived evidence matrix entries."""
        status_counts: Dict[str, int] = {}
        all_roles = set()
        missing_roles = set()
        for entry in entries:
            validation_status = self._entry_get(entry, "validation_status", "candidate")
            status_counts[validation_status] = status_counts.get(validation_status, 0) + 1
            all_roles.update(self._entry_get(entry, "source_roles", []) or [])
            missing_roles.update(self._entry_get(entry, "missing_validation_from", []) or [])

        latest_generated_at = None
        for memo in memos:
            generated_at = getattr(memo, "generated_at", None)
            if generated_at and (latest_generated_at is None or generated_at > latest_generated_at):
                latest_generated_at = generated_at

        return {
            "total_candidates": len(entries),
            "validated": status_counts.get("validated", 0),
            "conflicted": status_counts.get("conflicted", 0),
            "needs_more_evidence": status_counts.get("needs_more_evidence", 0),
            "candidate": status_counts.get("candidate", 0),
            "roles_heard_from": sorted(all_roles),
            "roles_missing": sorted(missing_roles - all_roles),
            "memo_count": len(memos),
            "status": status if memos else "empty",
            "last_updated_at": latest_generated_at.isoformat() if latest_generated_at else None,
        }

    @staticmethod
    def _entry_get(entry: Any, key: str, default: Any = None) -> Any:
        if isinstance(entry, dict):
            return entry.get(key, default)
        return getattr(entry, key, default)

    def _collect_requirement_candidates_from_memos(
        self, db: Session, memos: List[Any]
    ) -> List[Dict]:
        """Collect requirement candidates from cumulative round memos."""
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
        return all_candidates

    def update_matrix(self, db: Session, project_id: str) -> RequirementEvidenceMatrix:
        """Refresh derived matrix metadata from one canonical cumulative memo per round.

        Requirement rows are deliberately not persisted. RoundAggregate remains
        the only source read by BRD, Readiness, and Evidence Matrix responses.
        """
        matrix = self.get_or_create_matrix(db, project_id)
        matrix.status = "updating"
        db.flush()

        merged_entries, memos = self.build_entries_from_round_aggregates(db, project_id)
        matrix._derived_entries = merged_entries
        matrix._source_memos = memos

        if not memos:
            matrix.status = "draft"
            matrix.memo_count = 0
            matrix.last_memo_id = None
            matrix.last_updated_at = datetime.utcnow()
            matrix.markdown_content = self._render_matrix_markdown([])
            db.commit()
            return matrix

        matrix.status = "ready"
        matrix.memo_count = len(memos)
        matrix.last_memo_id = memos[-1].id
        matrix.last_updated_at = datetime.utcnow()
        matrix.markdown_content = self._render_matrix_markdown(merged_entries)

        db.commit()
        db.refresh(matrix)
        matrix._derived_entries = merged_entries
        matrix._source_memos = memos

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
                "- 合併判斷依據：描述的是同一個功能/流程/限制，即使用詞不同\n"
                "- 不合併：相似但針對不同使用者或不同情境的需求\n"
                "- 保留 source_indices 標記來自哪些原始 candidates（1-based）\n"
                "- 如果不同角色有矛盾觀點，在 conflicts 中說明\n"
                "- 只回傳 JSON"
            )

            result = openai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "你是專案需求整合分析師。你的任務是對比來自不同利害關係人的需求描述，判斷哪些語意相同（合併），哪些有衝突（標記），哪些獨立。合併時保留最完整的描述。只回傳 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-5.4-mini",
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"},
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
        """Get RoundAggregate-derived matrix summary statistics."""
        entries, memos = self.build_entries_from_round_aggregates(db, project_id)
        return self.summarize_entries(entries, memos)

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
