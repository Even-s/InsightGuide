"""Project-level BRD evidence-based generation service.

Used by: project-level BRD workflows.
Purpose: Generates BRD markdown from ready RoundAggregate-backed evidence.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.document import Document


class BRDGenerationService:

    def _rewrite_chapters_with_ai(
        self,
        document: Optional[Document],
        chapters: List[Dict[str, Any]],
        db: Optional[Session] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Use GPT 5.4 mini to rewrite raw evidence into formal BRD paragraphs."""
        import json

        from app.services.openai_service import openai_service

        title = document.title if document else "需求文件"

        system_prompt = (
            "你是專業的商業分析師，負責將訪談逐字稿改寫成正式的 BRD（Business Requirements Document）段落。\n\n"
            "規則：\n"
            "- 使用正式、清晰的書面語\n"
            "- 保留所有具體資訊（數據、流程步驟、規則、角色名稱）\n"
            "- 如果回答中有具體數字（金額、人數、時間、頻率），必須保留原始數字\n"
            "- 使用第三人稱（「利害關係人表示...」「目前流程為...」），不要用第一人稱\n"
            "- 移除口語贅詞（呃、那個、就是說）\n"
            "- 以條列或段落形式整理，方便閱讀\n"
            "- 不得添加訪談中沒有提到的資訊\n"
            "- 不得推測或補猜\n"
            "- 直接輸出改寫後的內容，不要加前言或說明"
        )

        for chapter in chapters:
            if not chapter["confirmedItems"]:
                continue

            for item in chapter["confirmedItems"]:
                evidence = item.get("evidence", "")
                if not evidence or len(evidence.strip()) < 10:
                    continue

                try:
                    user_prompt = (
                        f"文件：{title}\n"
                        f"BRD 章節：{chapter['chapter']}\n"
                        f"提問重點：{item['focusText']}\n\n"
                        f"訪談原始回答：\n{evidence[:3000]}\n\n"
                        f"請改寫成正式 BRD 段落。"
                    )

                    rewritten = openai_service.chat_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        model="gpt-5.4-mini",
                        temperature=0.3,
                        max_tokens=500,
                        db=db,
                        session_id=session_id,
                        document_id=document.id if document else None,
                        purpose="brd_rewrite",
                    )
                    if isinstance(rewritten, str) and rewritten.strip():
                        item["evidence"] = rewritten.strip()
                except Exception as e:
                    logger.warning(f"Failed to rewrite BRD chapter: {e}")

        return chapters

    def generate_project_brd(self, db: Session, project_id: str) -> Dict[str, Any]:
        """Generate BRD from project-level evidence (multi-interview).

        Uses requirement entries derived directly from ready RoundAggregate rows,
        instead of reading persisted Evidence Matrix snapshots, historical
        session memos or a single session's card states.
        """
        from app.models.project import Project
        from app.models.stakeholder_profile import StakeholderProfile
        from app.services.evidence_matrix_service import evidence_matrix_service

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        entries, memos = evidence_matrix_service.build_entries_from_round_aggregates(db, project_id)
        entries = [entry for entry in entries if entry.get("validation_status") != "rejected"]
        entries.sort(key=lambda entry: entry.get("mention_count", 0), reverse=True)
        if not memos:
            raise ValueError(
                "No ready RoundAggregate evidence found. Generate or rebuild round aggregates before generating BRD."
            )

        # Load stakeholders
        profiles = (
            db.query(StakeholderProfile)
            .filter(
                StakeholderProfile.project_id == project_id,
                StakeholderProfile.status == "interviewed",
            )
            .all()
        )

        # Build BRD chapters from evidence
        brd_chapters = self._build_project_brd_chapters(entries, memos, project)
        stakeholders_chapter = self._build_stakeholders_chapter(profiles)
        open_issues = self._build_project_open_issues(entries)

        # AI rewrite
        brd_chapters = self._rewrite_chapters_with_ai(None, brd_chapters)

        # Render markdown
        brd_md = self._render_project_brd_markdown(
            project, brd_chapters, stakeholders_chapter, open_issues
        )

        return {
            "projectId": project_id,
            "brd": {
                "markdown": brd_md,
                "chapters": brd_chapters,
                "openIssuesCount": len(open_issues),
            },
            "evidence": {
                "totalEntries": len(entries),
                "validatedEntries": len(
                    [e for e in entries if e.get("validation_status") == "validated"]
                ),
                "memoCount": len(memos),
                "stakeholderCount": len(profiles),
            },
        }

    def _build_project_brd_chapters(
        self, entries: List, memos: List, project
    ) -> List[Dict[str, Any]]:
        """Build BRD content chapters from RoundAggregate-derived entries and memos."""
        chapter_map: Dict[str, List[Dict]] = {}

        # From RoundAggregate-derived entries (validated + needs_more_evidence)
        for entry in entries:
            category = entry.get("category") or "general"
            chapter = {
                "functional": "功能性需求",
                "non_functional": "非功能性需求",
                "business_process": "業務流程需求",
                "integration": "系統整合需求",
                "permission": "權限需求",
                "data": "資料需求",
                "ux": "使用者體驗需求",
            }.get(category, "其他需求")

            chapter_map.setdefault(chapter, [])

            evidence_text = ""
            for ev in (entry.get("supporting_evidence") or [])[:3]:
                if ev.get("evidence_quote"):
                    evidence_text += f"[{ev.get('stakeholder_name', '')}] {ev['evidence_quote']}\n"

            chapter_map[chapter].append(
                {
                    "focusText": entry.get("requirement_candidate", ""),
                    "status": entry.get("validation_status"),
                    "evidence": evidence_text.strip(),
                    "confidence": None,
                    "themeTitle": "",
                    "sourceRoles": entry.get("source_roles") or [],
                    "mentionCount": entry.get("mention_count", 0),
                }
            )

        # From memos: pain points → 業務痛點 chapter
        all_pain_points = []
        for memo in memos:
            for pp in memo.pain_points or []:
                all_pain_points.append(pp)

        if all_pain_points:
            chapter_map.setdefault("業務痛點", [])
            for pp in all_pain_points[:10]:
                chapter_map["業務痛點"].append(
                    {
                        "focusText": pp.get("description", ""),
                        "status": "sufficient",
                        "evidence": pp.get("evidence_quote", ""),
                        "confidence": None,
                        "themeTitle": "",
                        "sourceRoles": pp.get("affected_roles", []),
                        "mentionCount": 1,
                    }
                )

        # From memos: constraints
        all_constraints = []
        for memo in memos:
            for ca in memo.constraints_and_assumptions or []:
                all_constraints.append(ca)

        if all_constraints:
            chapter_map.setdefault("限制與假設", [])
            for ca in all_constraints[:10]:
                chapter_map["限制與假設"].append(
                    {
                        "focusText": ca.get("content", ""),
                        "status": "sufficient",
                        "evidence": ca.get("evidence_quote", ""),
                        "confidence": None,
                        "themeTitle": "",
                        "sourceRoles": [],
                        "mentionCount": 1,
                    }
                )

        chapters = []
        for chapter, items in chapter_map.items():
            confirmed = [i for i in items if i["status"] not in ("missing", "rejected")]
            missing = [i for i in items if i["status"] == "missing"]
            chapters.append(
                {
                    "chapter": chapter,
                    "confirmedItems": confirmed,
                    "missingItems": missing,
                    "isComplete": len(missing) == 0 and len(confirmed) > 0,
                }
            )

        return chapters

    def _build_stakeholders_chapter(self, profiles: List) -> str:
        """Build stakeholders markdown chapter."""
        if not profiles:
            return ""
        lines = ["## 利害關係人", ""]
        lines.append("| 姓名 | 角色 | 部門 | 決策權 |")
        lines.append("|------|------|------|--------|")
        for p in profiles:
            power_map = {
                "decision_maker": "決策者",
                "influencer": "影響者",
                "user": "使用者",
                "operator": "操作者",
                "subject_matter_expert": "領域專家",
            }
            power = power_map.get(p.decision_power, p.decision_power or "—")
            lines.append(
                f"| {p.name} | {p.role_title or p.stakeholder_type} | {p.department or '—'} | {power} |"
            )
        lines.append("")
        return "\n".join(lines)

    def _build_project_open_issues(self, entries: List) -> List[Dict[str, Any]]:
        """Build open issues from RoundAggregate-derived entries that need more evidence."""
        issues = []
        for entry in entries:
            if entry.get("validation_status") in ("needs_more_evidence", "conflicted"):
                issues.append(
                    {
                        "focusText": entry.get("requirement_candidate", ""),
                        "status": entry.get("validation_status"),
                        "missingRoles": entry.get("missing_validation_from") or [],
                        "conflicts": entry.get("conflicts") or [],
                    }
                )
        return issues

    def _render_project_brd_markdown(
        self, project, chapters: List[Dict], stakeholders_chapter: str, open_issues: List[Dict]
    ) -> str:
        """Render project-level BRD as markdown."""
        from datetime import timedelta, timezone

        now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")

        lines = []
        lines.append(f"# {project.title}")
        lines.append("")
        lines.append(f"**Business Requirements Document** | 草稿 | {now}")
        lines.append("")

        # Project scope
        brd_scope = project.brd_scope or {}
        if brd_scope.get("key_objectives"):
            lines.append("## 專案目標")
            lines.append("")
            for obj in brd_scope["key_objectives"]:
                lines.append(f"- {obj}")
            lines.append("")

        if brd_scope.get("business_domain"):
            lines.append(f"**業務領域**：{brd_scope['business_domain']}")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Stakeholders
        if stakeholders_chapter:
            lines.append(stakeholders_chapter)
            lines.append("---")
            lines.append("")

        # Main content
        for chapter in chapters:
            chapter_title = chapter["chapter"]
            lines.append(f"## {chapter_title}")
            lines.append("")
            if chapter["confirmedItems"]:
                for item in chapter["confirmedItems"]:
                    lines.append(f"### {item['focusText']}")
                    lines.append("")
                    if item.get("sourceRoles"):
                        lines.append(f"*來源：{', '.join(item['sourceRoles'])}*")
                        lines.append("")
                    if item["evidence"]:
                        lines.append(item["evidence"])
                    lines.append("")
            lines.append("")

        # Open issues
        if open_issues:
            lines.append("---")
            lines.append("")
            lines.append("## 待確認事項")
            lines.append("")
            lines.append("| # | 候選需求 | 狀態 | 缺少角色 |")
            lines.append("|:---:|---------|------|---------|")
            for idx, issue in enumerate(open_issues, 1):
                missing = ", ".join(issue.get("missingRoles", [])[:3]) or "—"
                status = "衝突" if issue["status"] == "conflicted" else "待補證"
                lines.append(f"| {idx} | {issue['focusText'][:40]} | {status} | {missing} |")
            lines.append("")

        return "\n".join(lines)


brd_generation_service = BRDGenerationService()
