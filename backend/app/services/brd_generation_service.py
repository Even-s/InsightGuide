"""BRD and transcript generation service.

After an interview session ends, this service generates:
1. A BRD document based on structured evidence from card states
2. A full interview transcript organized by theme

Phase 1: Updated to read from final_utterances when available, with fallback to utterances.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

TZ_TAIPEI = timezone(timedelta(hours=8))

import json
import uuid

logger = logging.getLogger(__name__)

from app.models.brd import BRDDraft, BRDStatus
from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.interview_theme import InterviewTheme
from app.models.question_card import QuestionCard
from app.models.utterance import Utterance
from app.models.final_utterance import FinalUtterance
from app.models.card_coverage_evaluation import CardCoverageEvaluation
from app.models.document import Document

class BRDGenerationService:

    def generate_outputs(self, db: Session, session_id: str) -> Dict[str, Any]:
        """Generate BRD and transcript for a completed interview session.

        If a cached BRDDraft exists for this session, return it directly.
        Otherwise generate, persist to BRDDraft, then return.
        """
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Check for cached BRD
        existing_brd = db.query(BRDDraft).filter(
            BRDDraft.interview_session_id == session_id,
            BRDDraft.status == BRDStatus.COMPLETED,
        ).first()

        if existing_brd and existing_brd.markdown_content:
            return json.loads(existing_brd.markdown_content)

        document = db.query(Document).filter(Document.id == session.document_id).first()

        # Load themes with cards and their states
        themes = db.query(InterviewTheme).filter(
            InterviewTheme.document_id == session.document_id,
            InterviewTheme.is_enabled == True,
        ).order_by(InterviewTheme.order_index).all()

        # Phase 2: Prefer final card coverage evaluations if available
        final_evaluations = db.query(CardCoverageEvaluation).filter(
            CardCoverageEvaluation.session_id == session_id,
            CardCoverageEvaluation.basis_type == "final",
        ).order_by(CardCoverageEvaluation.evaluation_seq.desc()).all()

        # Group by card_id and take the latest evaluation_seq for each card
        final_eval_by_card_id = {}
        for eval_rec in final_evaluations:
            if eval_rec.card_id not in final_eval_by_card_id:
                final_eval_by_card_id[eval_rec.card_id] = eval_rec

        # Fallback to InterviewCardState for backwards compatibility
        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).all()
        state_by_card_id = {cs.question_card_id: cs for cs in card_states}

        # Phase 1: Load utterances - prefer final_utterances if available, fallback to old utterances
        final_utterances = db.query(FinalUtterance).filter(
            FinalUtterance.session_id == session_id
        ).order_by(FinalUtterance.sequence_index).all()

        if final_utterances:
            utterances = final_utterances
            logger.info(f"Using {len(final_utterances)} final utterances for BRD generation")
        else:
            # Fallback: try live_utterances, then old utterances
            from app.models.live_utterance import LiveUtterance
            live_utts = db.query(LiveUtterance).filter(
                LiveUtterance.session_id == session_id,
                LiveUtterance.is_partial == False,
            ).order_by(LiveUtterance.created_at).all()
            if live_utts:
                utterances = live_utts
                logger.info(f"Using {len(live_utts)} live utterances for BRD generation (no final yet)")
            else:
                old_utterances = db.query(Utterance).filter(
                    Utterance.session_id == session_id
                ).order_by(Utterance.created_at).all()
                utterances = old_utterances
                logger.info(f"Using {len(old_utterances)} old utterances for BRD generation (backwards compat)")
                if not old_utterances:
                    logger.warning(f"No utterances found for session {session_id}")

        # Build structured data
        brd_sections = self._build_brd_sections(themes, state_by_card_id, final_eval_by_card_id, db)
        open_issues = self._build_open_issues(themes, state_by_card_id, db)
        transcript_md = self._build_transcript(utterances, themes)

        # Phase 4: Build Q/A report
        qa_md, question_count = self._build_qa_report(db, session_id)

        # Use GPT to rewrite raw evidence into formal BRD paragraphs
        brd_sections = self._rewrite_sections_with_ai(document, brd_sections)

        brd_md = self._render_brd_markdown(document, brd_sections, open_issues)

        result = {
            "sessionId": session_id,
            "brd": {
                "markdown": brd_md,
                "sections": brd_sections,
                "openIssuesCount": len(open_issues),
            },
            "transcript": {
                "markdown": transcript_md,
                "utteranceCount": len(utterances),
            },
            "qa": {
                "markdown": qa_md,
                "questionCount": question_count,
            },
        }

        # Persist to BRDDraft
        if existing_brd:
            existing_brd.markdown_content = json.dumps(result, ensure_ascii=False)
            existing_brd.status = BRDStatus.COMPLETED
            existing_brd.generated_at = datetime.utcnow()
        else:
            brd_draft = BRDDraft(
                id=f"brd_{uuid.uuid4().hex[:12]}",
                interview_session_id=session_id,
                user_id=session.user_id,
                status=BRDStatus.COMPLETED,
                title=document.title if document else "BRD",
                markdown_content=json.dumps(result, ensure_ascii=False),
                generated_at=datetime.utcnow(),
            )
            db.add(brd_draft)
        db.commit()

        return result

    def _build_brd_sections(
        self, themes: List[InterviewTheme], state_by_card_id: Dict, final_eval_by_card_id: Dict, db: Session
    ) -> List[Dict[str, Any]]:
        """Build BRD content sections from theme/card evidence."""
        brd_chapter_map: Dict[str, List[Dict]] = {}

        for theme in themes:
            cards = db.query(QuestionCard).filter(
                QuestionCard.interview_theme_id == theme.id
            ).order_by(QuestionCard.order_index).all()

            for card in cards:
                # Phase 2: Use final evaluation if available, otherwise fall back to InterviewCardState
                final_eval = final_eval_by_card_id.get(card.id)
                state = state_by_card_id.get(card.id)

                if final_eval:
                    # Use final evaluation (basis_type='final')
                    status = final_eval.state
                    confidence = float(final_eval.confidence) if final_eval.confidence else None
                    # TODO: Phase 3 will extract evidence quotes from final_eval.evidence
                    evidence_text = state.evidence_transcript if state else ""
                elif state:
                    # Fall back to old InterviewCardState for backwards compatibility
                    status = state.status
                    confidence = float(state.confidence) if state.confidence else None
                    evidence_text = state.evidence_transcript or ""
                else:
                    # No evaluation found, skip this card
                    continue

                for chapter in (card.brd_mapping or theme.brd_mapping or []):
                    brd_chapter_map.setdefault(chapter, [])

                    if status in ('sufficient', 'probably_sufficient', 'covered', 'probably_covered', 'manually_checked'):
                        brd_chapter_map[chapter].append({
                            "focusText": card.focus_text or card.question_text,
                            "status": status,
                            "evidence": evidence_text,
                            "confidence": confidence,
                            "themeTitle": theme.title,
                        })
                    elif status in ('pending', 'at_risk') and card.importance == 'must':
                        brd_chapter_map[chapter].append({
                            "focusText": card.focus_text or card.question_text,
                            "status": "missing",
                            "evidence": "",
                            "confidence": None,
                            "themeTitle": theme.title,
                        })

        sections = []
        for chapter, items in brd_chapter_map.items():
            confirmed = [i for i in items if i["status"] != "missing"]
            missing = [i for i in items if i["status"] == "missing"]
            sections.append({
                "chapter": chapter,
                "confirmedItems": confirmed,
                "missingItems": missing,
                "isComplete": len(missing) == 0 and len(confirmed) > 0,
            })

        return sections

    def _build_open_issues(
        self, themes: List[InterviewTheme], state_by_card_id: Dict, db: Session
    ) -> List[Dict[str, Any]]:
        """Build list of unresolved must-ask items.

        Cards marked not_applicable_for_role or needs_different_stakeholder
        are NOT counted as open issues — they need a different interviewee.
        """
        issues = []
        role_deferred = []
        for theme in themes:
            cards = db.query(QuestionCard).filter(
                QuestionCard.interview_theme_id == theme.id,
                QuestionCard.importance == "must",
            ).all()

            for card in cards:
                state = state_by_card_id.get(card.id)
                if state and state.status in ('not_applicable_for_role', 'needs_different_stakeholder'):
                    role_deferred.append({
                        "themeTitle": theme.title,
                        "focusText": card.focus_text or card.question_text,
                        "targetRoles": card.target_roles or [],
                        "brdMapping": card.brd_mapping or theme.brd_mapping or [],
                    })
                    continue
                if not state or state.status in ('pending', 'at_risk', 'skipped'):
                    issues.append({
                        "themeTitle": theme.title,
                        "focusText": card.focus_text or card.question_text,
                        "suggestedFollowup": card.suggested_followup,
                        "brdMapping": card.brd_mapping or theme.brd_mapping or [],
                    })

        return issues

    def _build_transcript(
        self, utterances, themes: List[InterviewTheme]
    ) -> str:
        """Build formatted transcript markdown.

        Handles both FinalUtterance and Utterance objects for backwards compatibility.
        """
        if not utterances:
            return "# 訪談逐字稿\n\n（本次訪談無轉錄內容）\n"

        theme_map = {t.id: t.title for t in themes}
        now = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")
        total_duration = ""
        if utterances[0].created_at and utterances[-1].created_at:
            delta = utterances[-1].created_at - utterances[0].created_at
            minutes = int(delta.total_seconds() // 60)
            total_duration = f"{minutes} 分鐘"

        lines = []
        lines.append("# 訪談逐字稿")
        lines.append("")
        lines.append(f"| 項目 | 內容 |")
        lines.append(f"|------|------|")
        lines.append(f"| 訪談日期 | {now} |")
        lines.append(f"| 總發言數 | {len(utterances)} 句 |")
        if total_duration:
            lines.append(f"| 訪談時長 | {total_duration} |")

        # For FinalUtterance, use theme_id; for Utterance, use section_id
        theme_ids = set()
        for u in utterances:
            if hasattr(u, 'theme_id') and u.theme_id:
                theme_ids.add(u.theme_id)
            elif hasattr(u, 'section_id') and u.section_id:
                theme_ids.add(u.section_id)
        lines.append(f"| 訪談單元數 | {len(theme_ids)} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        current_theme_title = None
        for utt in utterances:
            # Handle both FinalUtterance (theme_id) and Utterance (section_id)
            theme_id = getattr(utt, 'theme_id', None) or getattr(utt, 'section_id', None)
            theme_title = theme_map.get(theme_id, "未分類")

            if theme_title != current_theme_title:
                current_theme_title = theme_title
                lines.append(f"## {current_theme_title}")
                lines.append("")

            # For FinalUtterance, prefer speaker_display_name; otherwise parse speaker
            if hasattr(utt, 'speaker_display_name') and utt.speaker_display_name:
                speaker_label = utt.speaker_display_name
            else:
                raw = getattr(utt, 'speaker_label', None) or getattr(utt, 'speaker', None) or "?"
                if raw.startswith("speaker_"):
                    try:
                        speaker_label = f"Speaker {int(raw.split('_')[1]) + 1}"
                    except (IndexError, ValueError):
                        speaker_label = raw
                else:
                    speaker_label = f"Speaker ({raw})"

            time_str = utt.created_at.replace(tzinfo=timezone.utc).astimezone(TZ_TAIPEI).strftime("%H:%M:%S") if utt.created_at else ""
            lines.append(f"**{speaker_label}** `{time_str}`")
            lines.append("")
            lines.append(f"> {utt.transcript}")
            lines.append("")

        return "\n".join(lines)

    def _build_qa_report(self, db: Session, session_id: str) -> tuple[str, int]:
        """Build Q/A report markdown.

        Returns:
            Tuple of (markdown_string, question_count)
        """
        from app.models.question_instance import QuestionInstance
        from app.models.question_answer import QuestionAnswer

        questions = db.query(QuestionInstance).filter(
            QuestionInstance.session_id == session_id
        ).order_by(QuestionInstance.sequence_index).all()

        if not questions:
            return "## 每題回答整理\n\n（本次訪談無偵測到問答結構）\n", 0

        lines = []
        lines.append("# 每題回答整理")
        lines.append("")
        lines.append("本節整理訪談中實際被問出的問題與受訪者的回答。")
        lines.append("")
        lines.append("---")
        lines.append("")

        for idx, question in enumerate(questions, 1):
            # Load answer
            answer = db.query(QuestionAnswer).filter(
                QuestionAnswer.question_instance_id == question.id
            ).first()

            # Question header
            q_type_label = {
                'main_question': '主要問題',
                'follow_up': '追問',
                'clarification': '釐清',
            }.get(question.question_type, '')

            lines.append(f"### Q{idx}. {question.asked_text}")
            if q_type_label:
                lines.append(f"*{q_type_label}*")
            lines.append("")

            if not answer:
                lines.append("**回答狀態**")
                lines.append("未回答")
                lines.append("")
                continue

            # Answer summary
            if answer.answer_summary:
                lines.append("**回答摘要**")
                lines.append("")
                lines.append(answer.answer_summary)
                lines.append("")

            # Evidence quotes
            if answer.evidence_quotes and len(answer.evidence_quotes) > 0:
                lines.append("**原文依據**")
                lines.append("")
                for quote_obj in answer.evidence_quotes[:3]:
                    quote = quote_obj.get('quote', '') if isinstance(quote_obj, dict) else str(quote_obj)
                    if quote:
                        lines.append(f"> {quote}")
                lines.append("")

            # Answer status
            status_label = {
                'answered': '已回答',
                'partially_answered': '部分回答',
                'not_answered': '未回答',
                'unclear': '不清楚',
            }.get(answer.answer_status, '未知')

            lines.append(f"**回答狀態**")
            lines.append(status_label)
            lines.append("")
            lines.append("---")
            lines.append("")

        return "\n".join(lines), len(questions)

    def _rewrite_sections_with_ai(
        self, document: Optional[Document], sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use GPT 5.4 mini to rewrite raw evidence into formal BRD paragraphs."""
        import json
        from app.services.openai_service import openai_service
        from app.db.session import SessionLocal
        from app.services.prompt_registry_service import prompt_registry_service

        title = document.title if document else "需求文件"

        # Try to load prompt from registry with fallback
        system_prompt = (
            "你是專業的商業分析師，負責將訪談逐字稿改寫成正式的 BRD（Business Requirements Document）段落。\n\n"
            "規則：\n"
            "- 使用正式、清晰的書面語\n"
            "- 保留所有具體資訊（數據、流程步驟、規則、角色名稱）\n"
            "- 移除口語贅詞（呃、那個、就是說）\n"
            "- 以條列或段落形式整理，方便閱讀\n"
            "- 不得添加訪談中沒有提到的資訊\n"
            "- 不得推測或補猜\n"
            "- 直接輸出改寫後的內容，不要加前言或說明"
        )

        for section in sections:
            if not section["confirmedItems"]:
                continue

            for item in section["confirmedItems"]:
                evidence = item.get("evidence", "")
                if not evidence or len(evidence.strip()) < 10:
                    continue

                try:
                    # Try DB first, fallback to hardcoded
                    db = SessionLocal()
                    try:
                        rendered = prompt_registry_service.render_prompt(
                            db,
                            "rewrite_brd_section",
                            {
                                "document_title": title,
                                "chapter": section['chapter'],
                                "focus_text": item['focusText'],
                                "evidence": evidence[:3000],
                            }
                        )
                        if rendered and "system_prompt" in rendered:
                            system_prompt_to_use = rendered["system_prompt"]
                            user_prompt = rendered.get("user_prompt", (
                                f"文件：{title}\n"
                                f"BRD 章節：{section['chapter']}\n"
                                f"提問重點：{item['focusText']}\n\n"
                                f"訪談原始回答：\n{evidence[:3000]}\n\n"
                                f"請改寫成正式 BRD 段落。"
                            ))
                        else:
                            system_prompt_to_use = system_prompt
                            user_prompt = (
                                f"文件：{title}\n"
                                f"BRD 章節：{section['chapter']}\n"
                                f"提問重點：{item['focusText']}\n\n"
                                f"訪談原始回答：\n{evidence[:3000]}\n\n"
                                f"請改寫成正式 BRD 段落。"
                            )
                    finally:
                        db.close()

                    response = openai_service.client.chat.completions.create(
                        model="gpt-5.4-mini",
                        messages=[
                            {"role": "system", "content": system_prompt_to_use},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.3,
                        max_completion_tokens=500,
                    )
                    rewritten = response.choices[0].message.content.strip()
                    if rewritten:
                        item["evidence"] = rewritten
                except Exception as e:
                    logger.warning(f"Failed to rewrite BRD section: {e}")

        return sections

    def _render_brd_markdown(
        self, document: Optional[Document], sections: List[Dict], open_issues: List[Dict]
    ) -> str:
        """Render the BRD as a clean, professional markdown document."""
        title = document.title if document else "需求文件"
        now = datetime.now(TZ_TAIPEI).strftime("%Y-%m-%d")

        lines = []

        # Title block
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"**Business Requirements Document** ｜ 草稿 ｜ {now}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Main content — each BRD chapter
        for section in sections:
            chapter = section["chapter"]
            lines.append(f"## {chapter}")
            lines.append("")

            if section["confirmedItems"]:
                for item in section["confirmedItems"]:
                    lines.append(f"### {item['focusText']}")
                    lines.append("")
                    if item["evidence"]:
                        lines.append(item["evidence"])
                    lines.append("")
            else:
                # No confirmed content — leave blank space for future fill
                lines.append("")

            lines.append("")

        # Open Issues — compact table at the end
        if open_issues:
            lines.append("---")
            lines.append("")
            lines.append("## 待確認事項")
            lines.append("")
            lines.append("| # | 章節 | 待確認項目 | 建議追問 |")
            lines.append("|:---:|------|------|------|")
            for idx, issue in enumerate(open_issues, 1):
                brd = ", ".join(issue["brdMapping"][:2]) or "—"
                followup = (issue["suggestedFollowup"] or "—")[:50]
                lines.append(f"| {idx} | {brd} | {issue['focusText']} | {followup} |")
            lines.append("")

        return "\n".join(lines)


    def generate_project_brd(self, db: Session, project_id: str) -> Dict[str, Any]:
        """Generate BRD from project-level evidence (multi-interview).

        Uses Evidence Matrix validated entries + all Insight Memos
        instead of a single session's card states.
        """
        from app.models.project import Project
        from app.models.requirement_evidence_matrix import RequirementEvidenceMatrix, EvidenceMatrixEntry
        from app.models.interview_insight_memo import InterviewInsightMemo
        from app.models.stakeholder_profile import StakeholderProfile

        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Load evidence matrix entries
        matrix = db.query(RequirementEvidenceMatrix).filter(
            RequirementEvidenceMatrix.project_id == project_id
        ).first()

        entries = []
        if matrix:
            entries = db.query(EvidenceMatrixEntry).filter(
                EvidenceMatrixEntry.matrix_id == matrix.id,
                EvidenceMatrixEntry.validation_status != "rejected",
            ).order_by(EvidenceMatrixEntry.mention_count.desc()).all()

        # Load all insight memos
        memos = db.query(InterviewInsightMemo).filter(
            InterviewInsightMemo.project_id == project_id,
            InterviewInsightMemo.status == "completed",
        ).all()

        # Load stakeholders
        profiles = db.query(StakeholderProfile).filter(
            StakeholderProfile.project_id == project_id,
            StakeholderProfile.status == "interviewed",
        ).all()

        # Build BRD sections from evidence
        brd_sections = self._build_project_brd_sections(entries, memos, project)
        stakeholders_section = self._build_stakeholders_section(profiles)
        open_issues = self._build_project_open_issues(entries)

        # AI rewrite
        brd_sections = self._rewrite_sections_with_ai(None, brd_sections)

        # Render markdown
        brd_md = self._render_project_brd_markdown(project, brd_sections, stakeholders_section, open_issues)

        return {
            "projectId": project_id,
            "brd": {
                "markdown": brd_md,
                "sections": brd_sections,
                "openIssuesCount": len(open_issues),
            },
            "evidence": {
                "totalEntries": len(entries),
                "validatedEntries": len([e for e in entries if e.validation_status == "validated"]),
                "memoCount": len(memos),
                "stakeholderCount": len(profiles),
            },
        }

    def _build_project_brd_sections(
        self, entries: List, memos: List, project
    ) -> List[Dict[str, Any]]:
        """Build BRD content sections from evidence matrix entries and memos."""
        chapter_map: Dict[str, List[Dict]] = {}

        # From evidence matrix entries (validated + needs_more_evidence)
        for entry in entries:
            category = entry.category or "general"
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
            for ev in (entry.supporting_evidence or [])[:3]:
                if ev.get("evidence_quote"):
                    evidence_text += f"[{ev.get('stakeholder_name', '')}] {ev['evidence_quote']}\n"

            chapter_map[chapter].append({
                "focusText": entry.requirement_candidate,
                "status": entry.validation_status,
                "evidence": evidence_text.strip(),
                "confidence": None,
                "themeTitle": "",
                "sourceRoles": entry.source_roles or [],
                "mentionCount": entry.mention_count,
            })

        # From memos: pain points → 業務痛點 chapter
        all_pain_points = []
        for memo in memos:
            for pp in (memo.pain_points or []):
                all_pain_points.append(pp)

        if all_pain_points:
            chapter_map.setdefault("業務痛點", [])
            for pp in all_pain_points[:10]:
                chapter_map["業務痛點"].append({
                    "focusText": pp.get("description", ""),
                    "status": "sufficient",
                    "evidence": pp.get("evidence_quote", ""),
                    "confidence": None,
                    "themeTitle": "",
                    "sourceRoles": pp.get("affected_roles", []),
                    "mentionCount": 1,
                })

        # From memos: constraints
        all_constraints = []
        for memo in memos:
            for ca in (memo.constraints_and_assumptions or []):
                all_constraints.append(ca)

        if all_constraints:
            chapter_map.setdefault("限制與假設", [])
            for ca in all_constraints[:10]:
                chapter_map["限制與假設"].append({
                    "focusText": ca.get("content", ""),
                    "status": "sufficient",
                    "evidence": ca.get("evidence_quote", ""),
                    "confidence": None,
                    "themeTitle": "",
                    "sourceRoles": [],
                    "mentionCount": 1,
                })

        sections = []
        for chapter, items in chapter_map.items():
            confirmed = [i for i in items if i["status"] not in ("missing", "rejected")]
            missing = [i for i in items if i["status"] == "missing"]
            sections.append({
                "chapter": chapter,
                "confirmedItems": confirmed,
                "missingItems": missing,
                "isComplete": len(missing) == 0 and len(confirmed) > 0,
            })

        return sections

    def _build_stakeholders_section(self, profiles: List) -> str:
        """Build stakeholders markdown section."""
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
            lines.append(f"| {p.name} | {p.role_title or p.stakeholder_type} | {p.department or '—'} | {power} |")
        lines.append("")
        return "\n".join(lines)

    def _build_project_open_issues(self, entries: List) -> List[Dict[str, Any]]:
        """Build open issues from evidence matrix entries that need more evidence."""
        issues = []
        for entry in entries:
            if entry.validation_status in ("needs_more_evidence", "conflicted"):
                issues.append({
                    "focusText": entry.requirement_candidate,
                    "status": entry.validation_status,
                    "missingRoles": entry.missing_validation_from or [],
                    "conflicts": entry.conflicts or [],
                })
        return issues

    def _render_project_brd_markdown(
        self, project, sections: List[Dict], stakeholders_section: str, open_issues: List[Dict]
    ) -> str:
        """Render project-level BRD as markdown."""
        from datetime import timezone, timedelta
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
        if stakeholders_section:
            lines.append(stakeholders_section)
            lines.append("---")
            lines.append("")

        # Main content
        for section in sections:
            chapter = section["chapter"]
            lines.append(f"## {chapter}")
            lines.append("")
            if section["confirmedItems"]:
                for item in section["confirmedItems"]:
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
