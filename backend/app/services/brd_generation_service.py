"""BRD and transcript generation service.

After an interview session ends, this service generates:
1. A BRD document based on structured evidence from card states
2. A full interview transcript organized by theme
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

TZ_TAIPEI = timezone(timedelta(hours=8))

import json
import uuid

from app.models.brd import BRDDraft, BRDStatus
from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.interview_theme import InterviewTheme
from app.models.question_card import QuestionCard
from app.models.utterance import Utterance
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

        card_states = db.query(InterviewCardState).filter(
            InterviewCardState.session_id == session_id
        ).all()
        state_by_card_id = {cs.question_card_id: cs for cs in card_states}

        # Load all utterances
        utterances = db.query(Utterance).filter(
            Utterance.session_id == session_id
        ).order_by(Utterance.created_at).all()

        # Build structured data
        brd_sections = self._build_brd_sections(themes, state_by_card_id, db)
        open_issues = self._build_open_issues(themes, state_by_card_id, db)
        transcript_md = self._build_transcript(utterances, themes)

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
        self, themes: List[InterviewTheme], state_by_card_id: Dict, db: Session
    ) -> List[Dict[str, Any]]:
        """Build BRD content sections from theme/card evidence."""
        brd_chapter_map: Dict[str, List[Dict]] = {}

        for theme in themes:
            cards = db.query(QuestionCard).filter(
                QuestionCard.interview_theme_id == theme.id
            ).order_by(QuestionCard.order_index).all()

            for card in cards:
                state = state_by_card_id.get(card.id)
                if not state:
                    continue

                for chapter in (card.brd_mapping or theme.brd_mapping or []):
                    brd_chapter_map.setdefault(chapter, [])

                    if state.status in ('sufficient', 'probably_sufficient', 'covered', 'probably_covered', 'manually_checked'):
                        brd_chapter_map[chapter].append({
                            "focusText": card.focus_text or card.question_text,
                            "status": state.status,
                            "evidence": state.evidence_transcript or "",
                            "confidence": float(state.confidence) if state.confidence else None,
                            "themeTitle": theme.title,
                        })
                    elif state.status in ('pending', 'at_risk') and card.importance == 'must':
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
        """Build list of unresolved must-ask items."""
        issues = []
        for theme in themes:
            cards = db.query(QuestionCard).filter(
                QuestionCard.interview_theme_id == theme.id,
                QuestionCard.importance == "must",
            ).all()

            for card in cards:
                state = state_by_card_id.get(card.id)
                if not state or state.status in ('pending', 'at_risk', 'skipped'):
                    issues.append({
                        "themeTitle": theme.title,
                        "focusText": card.focus_text or card.question_text,
                        "suggestedFollowup": card.suggested_followup,
                        "brdMapping": card.brd_mapping or theme.brd_mapping or [],
                    })

        return issues

    def _build_transcript(
        self, utterances: List[Utterance], themes: List[InterviewTheme]
    ) -> str:
        """Build formatted transcript markdown."""
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
        lines.append(f"| 訪談單元數 | {len(set(theme_map.get(u.section_id, '') for u in utterances))} |")
        lines.append("")
        lines.append("---")
        lines.append("")

        current_theme_title = None
        for utt in utterances:
            theme_title = theme_map.get(utt.section_id, "未分類")
            if theme_title != current_theme_title:
                current_theme_title = theme_title
                lines.append(f"## {current_theme_title}")
                lines.append("")

            speaker_label = "訪談者" if utt.speaker == "interviewer" else "受訪者"
            time_str = utt.created_at.replace(tzinfo=timezone.utc).astimezone(TZ_TAIPEI).strftime("%H:%M:%S") if utt.created_at else ""
            lines.append(f"**{speaker_label}** `{time_str}`")
            lines.append("")
            lines.append(f"> {utt.transcript}")
            lines.append("")

        return "\n".join(lines)

    def _rewrite_sections_with_ai(
        self, document: Optional[Document], sections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use GPT 5.4 mini to rewrite raw evidence into formal BRD paragraphs."""
        import json
        from app.services.openai_service import openai_service

        title = document.title if document else "需求文件"

        for section in sections:
            if not section["confirmedItems"]:
                continue

            for item in section["confirmedItems"]:
                evidence = item.get("evidence", "")
                if not evidence or len(evidence.strip()) < 10:
                    continue

                try:
                    response = openai_service.client.chat.completions.create(
                        model="gpt-5.4-mini",
                        messages=[
                            {"role": "system", "content": (
                                "你是專業的商業分析師，負責將訪談逐字稿改寫成正式的 BRD（Business Requirements Document）段落。\n\n"
                                "規則：\n"
                                "- 使用正式、清晰的書面語\n"
                                "- 保留所有具體資訊（數據、流程步驟、規則、角色名稱）\n"
                                "- 移除口語贅詞（呃、那個、就是說）\n"
                                "- 以條列或段落形式整理，方便閱讀\n"
                                "- 不得添加訪談中沒有提到的資訊\n"
                                "- 不得推測或補猜\n"
                                "- 直接輸出改寫後的內容，不要加前言或說明"
                            )},
                            {"role": "user", "content": (
                                f"文件：{title}\n"
                                f"BRD 章節：{section['chapter']}\n"
                                f"提問重點：{item['focusText']}\n\n"
                                f"訪談原始回答：\n{evidence[:3000]}\n\n"
                                f"請改寫成正式 BRD 段落。"
                            )},
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


brd_generation_service = BRDGenerationService()
