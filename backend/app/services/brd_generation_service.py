"""BRD and transcript generation service.

After an interview session ends, this service generates:
1. A BRD document based on structured evidence from card states
2. A full interview transcript organized by theme
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.interview_session import InterviewSession, InterviewCardState
from app.models.interview_theme import InterviewTheme
from app.models.question_card import QuestionCard
from app.models.utterance import Utterance
from app.models.document import Document

class BRDGenerationService:

    def generate_outputs(self, db: Session, session_id: str) -> Dict[str, Any]:
        """Generate BRD and transcript for a completed interview session."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")

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
        brd_md = self._render_brd_markdown(document, brd_sections, open_issues)

        return {
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
            return "# 訪談逐字稿\n\n（無轉錄內容）\n"

        theme_map = {t.id: t.title for t in themes}
        lines = ["# 訪談逐字稿\n"]
        current_theme_title = None

        for utt in utterances:
            theme_title = theme_map.get(utt.section_id, "未分類")
            if theme_title != current_theme_title:
                current_theme_title = theme_title
                lines.append(f"\n## {current_theme_title}\n")

            speaker_label = "訪談者" if utt.speaker == "interviewer" else "受訪者"
            time_str = utt.created_at.strftime("%H:%M:%S") if utt.created_at else ""
            lines.append(f"**{speaker_label}** [{time_str}]：{utt.transcript}\n")

        return "\n".join(lines)

    def _render_brd_markdown(
        self, document: Optional[Document], sections: List[Dict], open_issues: List[Dict]
    ) -> str:
        """Render the BRD as markdown."""
        title = document.title if document else "BRD 草稿"
        lines = [f"# {title} — BRD 草稿\n"]
        lines.append("> 本文件由訪談系統依實際訪談 evidence 自動產出。標示「待補」之段落表示訪談中未取得足夠資訊，不得由 AI 自行補猜。\n")

        for section in sections:
            lines.append(f"\n## {section['chapter']}\n")

            if section["confirmedItems"]:
                for item in section["confirmedItems"]:
                    lines.append(f"### {item['focusText']}\n")
                    if item["evidence"]:
                        lines.append(f"> 來源：{item['themeTitle']}\n")
                        lines.append(f"{item['evidence']}\n")
                    else:
                        lines.append("（已確認，但未留存詳細 evidence）\n")

            if section["missingItems"]:
                lines.append("\n### 待補資訊\n")
                for item in section["missingItems"]:
                    lines.append(f"- **{item['focusText']}**（來源：{item['themeTitle']}）\n")

        if open_issues:
            lines.append("\n---\n\n## Open Issues / 待確認事項\n")
            lines.append("| # | 訪談單元 | 待確認事項 | 建議追問 | 對應 BRD 章節 |\n")
            lines.append("|---|---|---|---|---|\n")
            for idx, issue in enumerate(open_issues, 1):
                brd = ", ".join(issue["brdMapping"][:3])
                followup = (issue["suggestedFollowup"] or "")[:40]
                lines.append(f"| {idx} | {issue['themeTitle']} | {issue['focusText']} | {followup} | {brd} |\n")

        return "\n".join(lines)


brd_generation_service = BRDGenerationService()
