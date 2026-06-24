"""
Unit tests for Billing Service
Tests cost calculation, model normalization, and usage tracking.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from app.services.billing_service import (
    billing_service, BillingService,
    MODEL_TOKEN_PRICES, MODEL_AUDIO_PRICES, ZERO, MILLION
)


class TestBillingService:
    """Test suite for billing service."""

    def test_service_initialization(self):
        assert billing_service is not None
        assert isinstance(billing_service, BillingService)

    # --- _normalize_model ---

    def test_normalize_known_model(self):
        assert billing_service._normalize_model("gpt-5.4-mini") == "gpt-5.4-mini"
        assert billing_service._normalize_model("gpt-4o") == "gpt-4o"

    def test_normalize_snapshot_model(self):
        assert billing_service._normalize_model("gpt-5.4-mini-2026-04-23") == "gpt-5.4-mini"
        assert billing_service._normalize_model("gpt-4o-2024-08-06") == "gpt-4o"

    def test_normalize_unknown_model(self):
        result = billing_service._normalize_model("unknown-model")
        assert result == "unknown-model"

    def test_normalize_empty(self):
        assert billing_service._normalize_model("") == ""
        assert billing_service._normalize_model(None) == ""

    def test_normalize_audio_model(self):
        assert billing_service._normalize_model("gpt-realtime-whisper") == "gpt-realtime-whisper"

    # --- _usage_value ---

    def test_usage_value_from_dict(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50}
        assert billing_service._usage_value(usage, "prompt_tokens") == 100
        assert billing_service._usage_value(usage, "completion_tokens") == 50

    def test_usage_value_from_object(self):
        usage = Mock()
        usage.prompt_tokens = 200
        assert billing_service._usage_value(usage, "prompt_tokens") == 200

    def test_usage_value_missing_key(self):
        usage = {"prompt_tokens": 100}
        assert billing_service._usage_value(usage, "missing_key") == 0
        assert billing_service._usage_value(usage, "missing_key", 42) == 42

    def test_usage_value_none(self):
        assert billing_service._usage_value(None, "any_key") == 0
        assert billing_service._usage_value(None, "any_key", 5) == 5

    def test_usage_value_none_value(self):
        usage = {"prompt_tokens": None}
        assert billing_service._usage_value(usage, "prompt_tokens") == 0

    # --- _cached_input_tokens ---

    def test_cached_tokens_from_dict(self):
        usage = {"prompt_tokens_details": {"cached_tokens": 50}}
        assert billing_service._cached_input_tokens(usage) == 50

    def test_cached_tokens_from_object(self):
        usage = Mock()
        usage.prompt_tokens_details = Mock()
        usage.prompt_tokens_details.cached_tokens = 30
        assert billing_service._cached_input_tokens(usage) == 30

    def test_cached_tokens_none(self):
        assert billing_service._cached_input_tokens(None) == 0

    def test_cached_tokens_no_details(self):
        usage = {"prompt_tokens": 100}
        assert billing_service._cached_input_tokens(usage) == 0

    # --- calculate_token_cost ---

    def test_token_cost_known_model(self):
        cost, pricing = billing_service.calculate_token_cost(
            model="gpt-5.4-mini",
            input_tokens=1000,
            cached_input_tokens=0,
            output_tokens=500
        )
        assert cost > ZERO
        assert pricing["type"] == "text_tokens"
        assert pricing["pricedModel"] == "gpt-5.4-mini"
        assert "missingPrice" not in pricing

    def test_token_cost_unknown_model(self):
        cost, pricing = billing_service.calculate_token_cost(
            model="unknown-model",
            input_tokens=1000,
            cached_input_tokens=0,
            output_tokens=500
        )
        assert cost == ZERO
        assert pricing["missingPrice"] is True

    def test_token_cost_with_cache(self):
        cost_no_cache, _ = billing_service.calculate_token_cost(
            model="gpt-5.4-mini",
            input_tokens=1000,
            cached_input_tokens=0,
            output_tokens=100
        )
        cost_with_cache, _ = billing_service.calculate_token_cost(
            model="gpt-5.4-mini",
            input_tokens=1000,
            cached_input_tokens=500,
            output_tokens=100
        )
        # Cached tokens are cheaper
        assert cost_with_cache < cost_no_cache

    def test_token_cost_zero_tokens(self):
        cost, _ = billing_service.calculate_token_cost(
            model="gpt-5.4-mini",
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=0
        )
        assert cost == ZERO

    def test_token_cost_negative_tokens_handled(self):
        cost, _ = billing_service.calculate_token_cost(
            model="gpt-5.4-mini",
            input_tokens=-100,
            cached_input_tokens=0,
            output_tokens=-50
        )
        assert cost >= ZERO

    # --- calculate_audio_cost ---




    def test_round_money(self):
        result = billing_service._round_money(Decimal("0.1234567"))
        assert result == Decimal("0.123457")

    def test_round_money_exact(self):
        result = billing_service._round_money(Decimal("1.000000"))
        assert result == Decimal("1.000000")

    # --- record_chat_completion ---

    def test_empty_summary(self):
        summary = billing_service.empty_summary()
        assert isinstance(summary, dict)
        assert "totalCostUsd" in summary
        assert summary["totalCostUsd"] == 0.0

    # --- Model pricing data ---

    def test_model_prices_exist(self):
        assert len(MODEL_TOKEN_PRICES) > 0
        assert "gpt-5.4-mini" in MODEL_TOKEN_PRICES
        assert "gpt-4o" in MODEL_TOKEN_PRICES

    def test_audio_prices_exist(self):
        assert len(MODEL_AUDIO_PRICES) > 0
        assert "gpt-realtime-whisper" in MODEL_AUDIO_PRICES

    def test_pricing_structure(self):
        pricing = MODEL_TOKEN_PRICES["gpt-5.4-mini"]
        assert pricing.input_per_million > 0
        assert pricing.cached_input_per_million > 0
        assert pricing.output_per_million > 0
        # Cached should be cheaper than regular
        assert pricing.cached_input_per_million < pricing.input_per_million
