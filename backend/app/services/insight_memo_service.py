"""Insight Memo Service - generates structured interview insight documents."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.final_utterance import FinalUtterance
from app.models.interview_insight_memo import InterviewInsightMemo
from app.models.interview_session import InterviewSession
from app.models.question_answer import QuestionAnswer
from app.models.question_instance import QuestionInstance
from app.models.stakeholder_profile import StakeholderProfile

logger = logging.getLogger(__name__)


class InsightMemoService:

    def generate_memo(self, db: Session, session_id: str) -> InterviewInsightMemo:
        """Generate an Interview Insight Memo from a completed interview session."""
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Delete existing memo if regenerating
        existing = (
            db.query(InterviewInsightMemo)
            .filter(InterviewInsightMemo.session_id == session_id)
            .first()
        )
        if existing:
            db.delete(existing)
            db.flush()

        # Gather source data
        stakeholder = None
        if session.stakeholder_profile_id:
            stakeholder = (
                db.query(StakeholderProfile)
                .filter(StakeholderProfile.id == session.stakeholder_profile_id)
                .first()
            )

        qa_records = self._load_qa_records(db, session_id)
        transcript_text = self._load_transcript_text(db, session_id)

        # Calculate duration
        duration_minutes = None
        if session.started_at and session.ended_at:
            delta = session.ended_at - session.started_at
            duration_minutes = int(delta.total_seconds() / 60)

        # Generate insights using AI
        insights = self._ai_analyze_interview(
            stakeholder=stakeholder,
            qa_records=qa_records,
            transcript_text=transcript_text,
            session=session,
        )

        # Build stakeholder summary
        stakeholder_summary = None
        if stakeholder:
            stakeholder_summary = {
                "name": stakeholder.name,
                "role": stakeholder.role_title or stakeholder.stakeholder_type,
                "department": stakeholder.department,
                "expertise": stakeholder.expertise_tags or [],
                "boundaries": stakeholder.knowledge_boundaries or [],
            }

        memo = InterviewInsightMemo(
            id=f"memo_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            project_id=session.project_id,
            stakeholder_profile_id=session.stakeholder_profile_id,
            interview_date=session.started_at or session.created_at,
            interview_duration_minutes=duration_minutes,
            topics_covered=insights.get("topics_covered", []),
            stakeholder_summary=stakeholder_summary,
            qa_summaries=insights.get("qa_summaries", []),
            pain_points=insights.get("pain_points", []),
            requirement_candidates=insights.get("requirement_candidates", []),
            constraints_and_assumptions=insights.get("constraints_and_assumptions", []),
            process_descriptions=insights.get("process_descriptions", []),
            unresolved_questions=insights.get("unresolved_questions", []),
            next_interview_suggestions=insights.get("next_interview_suggestions", []),
            source_distinction=insights.get("source_distinction"),
            status="completed",
            generated_at=datetime.utcnow(),
        )

        # Render markdown
        memo.markdown_content = self._render_memo_markdown(memo)

        db.add(memo)
        db.commit()
        db.refresh(memo)

        # Post-processing: update stakeholder plan if project exists
        if session.project_id:
            try:
                from app.services.stakeholder_plan_service import stakeholder_plan_service

                stakeholder_plan_service.update_plan_after_interview(
                    db, session.project_id, memo.id
                )
            except Exception as e:
                logger.warning(f"Failed to update stakeholder plan: {e}")

        return memo

    def get_memo(self, db: Session, session_id: str) -> Optional[InterviewInsightMemo]:
        return (
            db.query(InterviewInsightMemo)
            .filter(InterviewInsightMemo.session_id == session_id)
            .first()
        )

    def get_memos_for_project(self, db: Session, project_id: str) -> List[InterviewInsightMemo]:
        return (
            db.query(InterviewInsightMemo)
            .filter(
                InterviewInsightMemo.project_id == project_id,
                InterviewInsightMemo.status == "completed",
            )
            .order_by(InterviewInsightMemo.interview_date.desc())
            .all()
        )

    def _load_qa_records(self, db: Session, session_id: str) -> List[Dict[str, Any]]:
        """Load Q/A records from QuestionInstance + QuestionAnswer."""
        questions = (
            db.query(QuestionInstance)
            .filter(QuestionInstance.session_id == session_id)
            .order_by(QuestionInstance.sequence_index)
            .all()
        )

        records = []
        for q in questions:
            answer = (
                db.query(QuestionAnswer).filter(QuestionAnswer.question_instance_id == q.id).first()
            )

            records.append(
                {
                    "question": q.asked_text,
                    "question_type": q.question_type,
                    "answer_summary": answer.answer_summary if answer else None,
                    "answer_status": answer.answer_status if answer else "not_answered",
                    "evidence_quotes": answer.evidence_quotes if answer else [],
                    "confidence": answer.confidence if answer else None,
                }
            )

        return records

    def _load_transcript_text(self, db: Session, session_id: str) -> str:
        """Load transcript as plain text for AI analysis."""
        utterances = (
            db.query(FinalUtterance)
            .filter(FinalUtterance.session_id == session_id)
            .order_by(FinalUtterance.sequence_index)
            .limit(200)
            .all()
        )

        if not utterances:
            from app.models.live_utterance import LiveUtterance

            utterances = (
                db.query(LiveUtterance)
                .filter(
                    LiveUtterance.session_id == session_id,
                    LiveUtterance.is_partial == False,
                )
                .order_by(LiveUtterance.created_at)
                .limit(200)
                .all()
            )

        lines = []
        for u in utterances:
            speaker = getattr(u, "speaker_display_name", None) or getattr(u, "speaker", "unknown")
            lines.append(f"[{speaker}] {u.transcript}")

        return "\n".join(lines)

    def _ai_analyze_interview(
        self,
        stakeholder: Optional[StakeholderProfile],
        qa_records: List[Dict],
        transcript_text: str,
        session: InterviewSession,
    ) -> Dict[str, Any]:
        """Use AI to analyze interview and extract structured insights."""
        try:
            from app.services.openai_service import openai_service

            stakeholder_info = ""
            if stakeholder:
                stakeholder_info = (
                    f"受訪者：{stakeholder.name}（{stakeholder.role_title or stakeholder.stakeholder_type}）\n"
                    f"專長：{', '.join(stakeholder.expertise_tags or [])}\n"
                    f"不熟悉：{', '.join(stakeholder.knowledge_boundaries or [])}\n"
                )

            qa_text = ""
            for i, r in enumerate(qa_records[:20], 1):
                status_label = {
                    "answered": "已回答",
                    "partially_answered": "部分回答",
                    "not_answered": "未回答",
                }.get(r["answer_status"], r["answer_status"])
                qa_text += f"Q{i}. {r['question']} [{status_label}]\n"
                if r["answer_summary"]:
                    qa_text += f"   摘要：{r['answer_summary']}\n"

            # Truncate transcript for token limits
            transcript_excerpt = transcript_text[:6000] if transcript_text else "(無逐字稿)"

            prompt = (
                "你是專業的商業分析師。請分析以下訪談內容，產生結構化的訪談洞察紀錄。\n\n"
                f"{stakeholder_info}\n"
                f"## Q/A 摘要\n{qa_text}\n\n"
                f"## 逐字稿摘錄\n{transcript_excerpt}\n\n"
                "請以 JSON 格式產出：\n"
                "{\n"
                '  "topics_covered": ["涵蓋的主題"],\n'
                '  "qa_summaries": [{"question": "...", "answer_summary": "...", "answer_status": "answered|partial|unanswered", "confidence": 0.8}],\n'
                '  "pain_points": [{"description": "...", "evidence_quote": "原文", "affected_roles": ["角色"], "severity": "high|medium|low"}],\n'
                '  "requirement_candidates": [{"description": "...", "source": "explicit|inferred|unverified", "confidence": "high|medium|low", "evidence_quote": "...", "needs_validation_from": ["角色"], "brd_ready": false}],\n'
                '  "constraints_and_assumptions": [{"type": "assumption|constraint|limitation", "content": "...", "source": "explicit|inferred", "evidence_quote": "..."}],\n'
                '  "process_descriptions": [{"process_name": "...", "steps": ["..."], "pain_points": ["..."], "source_quote": "..."}],\n'
                '  "unresolved_questions": [{"question": "...", "suggested_stakeholder_type": "engineering|product|...", "priority": "high|medium|low", "reason": "..."}],\n'
                '  "next_interview_suggestions": [{"target_role": "...", "objective": "...", "key_questions": ["..."]}],\n'
                '  "source_distinction": {"explicit_statements": 數量, "inferences": 數量, "unverified": 數量}\n'
                "}\n\n"
                "重要規則：\n"
                "- pain_points: 只列明確提到的痛點，附上原文依據\n"
                "- requirement_candidates: 標記 source 區分「受訪者明確說的(explicit)」vs「推論(inferred)」vs「需驗證(unverified)」\n"
                "- unresolved_questions: 列出受訪者無法或未回答的重要問題，建議應該問誰\n"
                "- 只回傳 JSON，不要其他文字"
            )

            result = openai_service.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "你是專業商業分析師，擅長從訪談中萃取可寫入 BRD 的結構化洞察。嚴格區分「受訪者明確說的」和「你推論的」。如果某個欄位沒有足夠證據，回傳空陣列，不要為了填滿欄位而推測。只回傳 JSON。",
                    },
                    {"role": "user", "content": prompt},
                ],
                model="gpt-5.4-mini",
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"},
                session_id=session.id,
                purpose="insight_memo_analysis",
            )

            # The wrapper already parses JSON, but handle markdown code blocks if present
            if isinstance(result, str):
                content = result.strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                return json.loads(content)

            return result

        except Exception as e:
            logger.error(f"AI insight analysis failed: {e}")
            return self._fallback_insights(qa_records)

    def _fallback_insights(self, qa_records: List[Dict]) -> Dict[str, Any]:
        """Generate minimal insights without AI."""
        qa_summaries = [
            {
                "question": r["question"],
                "answer_summary": r["answer_summary"] or "",
                "answer_status": r["answer_status"],
                "confidence": r["confidence"],
            }
            for r in qa_records
        ]

        return {
            "topics_covered": [],
            "qa_summaries": qa_summaries,
            "pain_points": [],
            "requirement_candidates": [],
            "constraints_and_assumptions": [],
            "process_descriptions": [],
            "unresolved_questions": [],
            "next_interview_suggestions": [],
            "source_distinction": {"explicit_statements": 0, "inferences": 0, "unverified": 0},
        }

    def _render_memo_markdown(self, memo: InterviewInsightMemo) -> str:
        """Render the memo as markdown."""
        lines = []
        lines.append("# 訪談洞察紀錄")
        lines.append("")

        # Section 1
        lines.append("## 1. 訪談基本資訊")
        lines.append("")
        if memo.stakeholder_summary:
            s = memo.stakeholder_summary
            lines.append(f"- 受訪者：{s.get('name', '未知')}")
            lines.append(f"- 角色：{s.get('role', '未知')}")
            if s.get("department"):
                lines.append(f"- 部門：{s['department']}")
            if s.get("expertise"):
                lines.append(f"- 熟悉領域：{', '.join(s['expertise'])}")
            if s.get("boundaries"):
                lines.append(f"- 不熟悉領域：{', '.join(s['boundaries'])}")
        if memo.interview_date:
            lines.append(f"- 訪談日期：{memo.interview_date.strftime('%Y-%m-%d')}")
        if memo.interview_duration_minutes:
            lines.append(f"- 訪談時長：{memo.interview_duration_minutes} 分鐘")
        if memo.topics_covered:
            lines.append(f"- 涵蓋主題：{', '.join(memo.topics_covered)}")
        lines.append("")

        # Section 2: Q/A
        if memo.qa_summaries:
            lines.append("## 2. 每題回答整理")
            lines.append("")
            for i, qa in enumerate(memo.qa_summaries, 1):
                lines.append(f"### Q{i}. {qa.get('question', '')}")
                lines.append("")
                if qa.get("answer_summary"):
                    lines.append(f"**回答摘要**：{qa['answer_summary']}")
                    lines.append("")
                status_map = {"answered": "已回答", "partial": "部分回答", "unanswered": "未回答"}
                lines.append(
                    f"**狀態**：{status_map.get(qa.get('answer_status', ''), qa.get('answer_status', ''))}"
                )
                lines.append("")

        # Section 3: Pain points
        if memo.pain_points:
            lines.append("## 3. 主要痛點")
            lines.append("")
            lines.append("| 痛點 | 原文依據 | 影響對象 | 嚴重程度 |")
            lines.append("|------|---------|---------|---------|")
            for p in memo.pain_points:
                affected = ", ".join(p.get("affected_roles", []))
                quote = p.get("evidence_quote", "")[:40]
                lines.append(
                    f"| {p.get('description', '')} | {quote} | {affected} | {p.get('severity', '')} |"
                )
            lines.append("")

        # Section 4: Requirement candidates
        if memo.requirement_candidates:
            lines.append("## 4. 需求線索")
            lines.append("")
            lines.append("| 需求線索 | 來源 | 信心 | 需驗證角色 |")
            lines.append("|---------|------|------|----------|")
            for r in memo.requirement_candidates:
                validation = ", ".join(r.get("needs_validation_from", []))
                lines.append(
                    f"| {r.get('description', '')} | {r.get('source', '')} | {r.get('confidence', '')} | {validation} |"
                )
            lines.append("")

        # Section 5: Constraints
        if memo.constraints_and_assumptions:
            lines.append("## 5. 限制與假設")
            lines.append("")
            for c in memo.constraints_and_assumptions:
                type_label = {"assumption": "假設", "constraint": "限制", "limitation": "限制"}.get(
                    c.get("type", ""), c.get("type", "")
                )
                lines.append(f"- **[{type_label}]** {c.get('content', '')} ({c.get('source', '')})")
            lines.append("")

        # Section 6: Process descriptions
        if memo.process_descriptions:
            lines.append("## 6. 流程描述")
            lines.append("")
            for p in memo.process_descriptions:
                lines.append(f"### {p.get('process_name', '流程')}")
                for step in p.get("steps", []):
                    lines.append(f"1. {step}")
                if p.get("pain_points"):
                    lines.append(f"\n痛點：{', '.join(p['pain_points'])}")
                lines.append("")

        # Section 7: Unresolved questions
        if memo.unresolved_questions:
            lines.append("## 7. 未解問題")
            lines.append("")
            lines.append("| 問題 | 建議訪談對象 | 優先級 |")
            lines.append("|------|------------|--------|")
            for q in memo.unresolved_questions:
                lines.append(
                    f"| {q.get('question', '')} | {q.get('suggested_stakeholder_type', '')} | {q.get('priority', '')} |"
                )
            lines.append("")

        # Section 8: Next suggestions
        if memo.next_interview_suggestions:
            lines.append("## 8. 建議下一步")
            lines.append("")
            for s in memo.next_interview_suggestions:
                lines.append(f"- **{s.get('target_role', '')}**：{s.get('objective', '')}")
                for q in s.get("key_questions", []):
                    lines.append(f"  - {q}")
            lines.append("")

        # Source distinction
        if memo.source_distinction:
            sd = memo.source_distinction
            lines.append("---")
            lines.append("")
            lines.append(
                f"*來源統計：明確陳述 {sd.get('explicit_statements', 0)} 項 / "
                f"推論 {sd.get('inferences', 0)} 項 / "
                f"待驗證 {sd.get('unverified', 0)} 項*"
            )

        return "\n".join(lines)


insight_memo_service = InsightMemoService()
