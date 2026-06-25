"""AI usage and cost accounting helpers."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ai_usage_event import AIUsageEvent

logger = logging.getLogger(__name__)

MILLION = Decimal("1000000")
ZERO = Decimal("0")


@dataclass(frozen=True)
class TokenPricing:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal


@dataclass(frozen=True)
class AudioPricing:
    per_second: Decimal


MODEL_TOKEN_PRICES: Dict[str, TokenPricing] = {
    "gpt-5.5": TokenPricing(Decimal("5.00"), Decimal("0.50"), Decimal("30.00")),
    "gpt-5.4": TokenPricing(Decimal("2.50"), Decimal("0.25"), Decimal("15.00")),
    "gpt-5.4-mini": TokenPricing(Decimal("0.75"), Decimal("0.075"), Decimal("4.50")),
    "gpt-5": TokenPricing(Decimal("1.25"), Decimal("0.125"), Decimal("10.00")),
    "gpt-5-mini": TokenPricing(Decimal("0.25"), Decimal("0.025"), Decimal("2.00")),
    "gpt-5-nano": TokenPricing(Decimal("0.05"), Decimal("0.005"), Decimal("0.40")),
    "gpt-4.1": TokenPricing(Decimal("2.00"), Decimal("0.50"), Decimal("8.00")),
    "gpt-4.1-mini": TokenPricing(Decimal("0.40"), Decimal("0.10"), Decimal("1.60")),
    "gpt-4.1-nano": TokenPricing(Decimal("0.10"), Decimal("0.025"), Decimal("0.40")),
    "gpt-4o": TokenPricing(Decimal("2.50"), Decimal("1.25"), Decimal("10.00")),
    "gpt-4o-mini": TokenPricing(Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
}

MODEL_AUDIO_PRICES: Dict[str, AudioPricing] = {
    "gpt-realtime-whisper": AudioPricing(Decimal("0.00028")),
    "gpt-realtime-translate": AudioPricing(Decimal("0.00057")),
}


class BillingService:
    """Record AI usage events and summarize interview session costs."""

    def _normalize_model(self, model: str) -> str:
        model = (model or "").strip()
        if model in MODEL_TOKEN_PRICES or model in MODEL_AUDIO_PRICES:
            return model

        # Snapshot models keep the same base price, e.g. gpt-5.5-2026-04-23.
        for known_model in sorted(MODEL_TOKEN_PRICES, key=len, reverse=True):
            if model.startswith(f"{known_model}-"):
                return known_model
        for known_model in sorted(MODEL_AUDIO_PRICES, key=len, reverse=True):
            if model.startswith(f"{known_model}-"):
                return known_model
        return model

    def _usage_value(self, usage: Any, key: str, default: int = 0) -> int:
        if usage is None:
            return default
        if isinstance(usage, dict):
            value = usage.get(key, default)
        else:
            value = getattr(usage, key, default)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return default

    def _cached_input_tokens(self, usage: Any) -> int:
        details = None
        if isinstance(usage, dict):
            details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details")
        elif usage is not None:
            details = getattr(usage, "prompt_tokens_details", None) or getattr(
                usage, "input_tokens_details", None
            )
        return self._usage_value(details, "cached_tokens", 0)

    def calculate_token_cost(
        self,
        model: str,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> tuple[Decimal, Dict[str, Any]]:
        normalized_model = self._normalize_model(model)
        pricing = MODEL_TOKEN_PRICES.get(normalized_model)
        if not pricing:
            return ZERO, {
                "type": "text_tokens",
                "model": model,
                "pricedModel": normalized_model,
                "missingPrice": True,
            }

        cached_tokens = min(max(cached_input_tokens, 0), max(input_tokens, 0))
        billable_input_tokens = max(input_tokens - cached_tokens, 0)
        cost = (
            Decimal(billable_input_tokens) * pricing.input_per_million / MILLION
            + Decimal(cached_tokens) * pricing.cached_input_per_million / MILLION
            + Decimal(max(output_tokens, 0)) * pricing.output_per_million / MILLION
        )
        return self._round_money(cost), {
            "type": "text_tokens",
            "model": model,
            "pricedModel": normalized_model,
            "inputPerMillion": str(pricing.input_per_million),
            "cachedInputPerMillion": str(pricing.cached_input_per_million),
            "outputPerMillion": str(pricing.output_per_million),
        }

    def _round_money(self, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    def record_deck_chat_completion(
        self,
        document_id: Optional[str],
        operation: str,
        model: str,
        response: Any,
        source_id: Optional[str] = None,
    ) -> None:
        if not document_id:
            return

        usage = getattr(response, "usage", None)
        input_tokens = self._usage_value(usage, "prompt_tokens")
        output_tokens = self._usage_value(usage, "completion_tokens")
        total_tokens = self._usage_value(usage, "total_tokens", input_tokens + output_tokens)
        cached_input_tokens = self._cached_input_tokens(usage)
        cost, pricing = self.calculate_token_cost(
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
        )

        self.record_usage_event(
            session_id=None,
            document_id=document_id,
            operation=operation,
            model=model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            pricing=pricing,
            source_id=source_id,
            idempotent=True,
        )

    def record_usage_event(
        self,
        session_id: Optional[str],
        operation: str,
        model: str,
        document_id: Optional[str] = None,
        input_tokens: int = 0,
        cached_input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        audio_seconds: Decimal = ZERO,
        cost_usd: Decimal = ZERO,
        pricing: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
        idempotent: bool = False,
    ) -> None:
        if not session_id and not document_id:
            return

        db = SessionLocal()
        try:
            if idempotent and source_id:
                query = db.query(AIUsageEvent).filter(
                    AIUsageEvent.operation == operation,
                    AIUsageEvent.source_id == source_id,
                )
                if session_id:
                    query = query.filter(AIUsageEvent.interview_session_id == session_id)
                if document_id:
                    query = query.filter(AIUsageEvent.document_id == document_id)
                existing = query.first()
                if existing:
                    return

            event = AIUsageEvent(
                id=f"aiusage_{uuid.uuid4().hex[:12]}",
                interview_session_id=session_id,
                document_id=document_id,
                operation=operation,
                source_id=source_id,
                model=model,
                input_tokens=max(input_tokens, 0),
                cached_input_tokens=max(cached_input_tokens, 0),
                output_tokens=max(output_tokens, 0),
                total_tokens=max(total_tokens, 0),
                audio_seconds=audio_seconds,
                cost_usd=cost_usd,
                pricing=pricing,
                created_at=datetime.utcnow(),
            )
            db.add(event)
            db.commit()
            logger.info(
                "Recorded AI usage event id=%s session=%s document=%s operation=%s model=%s total_tokens=%s cost_usd=%s",
                event.id,
                session_id,
                document_id,
                operation,
                model,
                event.total_tokens,
                event.cost_usd,
            )
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Failed to record AI usage event session=%s document=%s operation=%s: %s",
                session_id,
                document_id,
                operation,
                exc,
                exc_info=True,
            )
        finally:
            db.close()

    def summarize_sessions(self, db: Session, session_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        ids = [session_id for session_id in session_ids if session_id]
        if not ids:
            return {}

        rows = db.query(
            AIUsageEvent.interview_session_id,
            func.coalesce(func.sum(AIUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.cached_input_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.audio_seconds), 0),
            func.coalesce(func.sum(AIUsageEvent.cost_usd), 0),
        ).filter(
            AIUsageEvent.interview_session_id.in_(ids)
        ).group_by(AIUsageEvent.interview_session_id).all()

        return {
            row[0]: self._summary_dict(
                input_tokens=row[1],
                cached_input_tokens=row[2],
                output_tokens=row[3],
                total_tokens=row[4],
                realtime_seconds=row[5],
                total_cost_usd=row[6],
            )
            for row in rows
        }

    def summarize_documents(self, db: Session, document_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        ids = [doc_id for doc_id in document_ids if doc_id]
        if not ids:
            return {}

        rows = db.query(
            AIUsageEvent.document_id,
            func.coalesce(func.sum(AIUsageEvent.input_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.cached_input_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.output_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.total_tokens), 0),
            func.coalesce(func.sum(AIUsageEvent.audio_seconds), 0),
            func.coalesce(func.sum(AIUsageEvent.cost_usd), 0),
        ).filter(
            AIUsageEvent.document_id.in_(ids)
        ).group_by(AIUsageEvent.document_id).all()

        return {
            row[0]: self._summary_dict(
                input_tokens=row[1],
                cached_input_tokens=row[2],
                output_tokens=row[3],
                total_tokens=row[4],
                realtime_seconds=row[5],
                total_cost_usd=row[6],
            )
            for row in rows
        }

    def summarize_session(self, db: Session, session_id: str) -> Dict[str, Any]:
        return self.summarize_sessions(db, [session_id]).get(session_id, self.empty_summary())

    def empty_summary(self) -> Dict[str, Any]:
        return self._summary_dict(0, 0, 0, 0, ZERO, ZERO)

    def _summary_dict(
        self,
        input_tokens: Any,
        cached_input_tokens: Any,
        output_tokens: Any,
        total_tokens: Any,
        realtime_seconds: Any,
        total_cost_usd: Any,
    ) -> Dict[str, Any]:
        total_cost = self._round_money(Decimal(str(total_cost_usd or 0)))
        return {
            "inputTokens": int(input_tokens or 0),
            "cachedInputTokens": int(cached_input_tokens or 0),
            "outputTokens": int(output_tokens or 0),
            "totalTokens": int(total_tokens or 0),
            "realtimeSeconds": float(realtime_seconds or 0),
            "totalCostUsd": float(total_cost),
        }


billing_service = BillingService()
