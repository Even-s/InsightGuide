"""
Unit tests for Hallucination Filter Service
Tests Whisper hallucination detection across all filter layers.
"""

import pytest

from app.services.hallucination_filter import HallucinationFilter, hallucination_filter


class TestHallucinationFilter:
    """Test suite for hallucination filter."""

    @pytest.fixture
    def fresh_filter(self):
        """Create a fresh filter instance for isolation."""
        return HallucinationFilter()

    def test_service_initialization(self):
        assert hallucination_filter is not None
        assert isinstance(hallucination_filter, HallucinationFilter)

    def test_empty_transcript(self, fresh_filter):
        result = fresh_filter.is_hallucination("")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "empty"
        assert result["confidence"] == 1.0

    def test_whitespace_only(self, fresh_filter):
        result = fresh_filter.is_hallucination("   ")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "empty"

    # --- Layer 1: Blacklist exact match ---

    def test_blacklist_chinese_hallucination(self, fresh_filter):
        result = fresh_filter.is_hallucination("謝謝觀看")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist"
        assert result["confidence"] == 1.0

    def test_blacklist_english_hallucination(self, fresh_filter):
        result = fresh_filter.is_hallucination("Thanks for watching")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist"

    def test_blacklist_test_word(self, fresh_filter):
        result = fresh_filter.is_hallucination("測試")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist"

    def test_blacklist_filler_word(self, fresh_filter):
        result = fresh_filter.is_hallucination("嗯")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist"

    # --- Layer 1.5: Partial match ---

    def test_partial_match_contains_hallucination(self, fresh_filter):
        result = fresh_filter.is_hallucination("然後訂閱我的頻道喔")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist_partial"
        assert result["confidence"] == 0.9

    def test_partial_match_amara(self, fresh_filter):
        result = fresh_filter.is_hallucination("Subtitles by Amara.org community")
        assert result["is_hallucination"] is True

    # --- Layer 2: Repetition patterns ---

    def test_repetition_haha(self, fresh_filter):
        result = fresh_filter.is_hallucination("哈哈哈哈")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "repetition"
        assert result["confidence"] == 0.95

    def test_repetition_single_char(self, fresh_filter):
        result = fresh_filter.is_hallucination("嗯嗯嗯嗯")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "repetition"

    def test_repetition_two_char(self, fresh_filter):
        result = fresh_filter.is_hallucination("哈哈哈哈哈哈")
        assert result["is_hallucination"] is True

    # --- Layer 3: Semantic blacklist patterns ---

    def test_semantic_subscribe_chinese(self, fresh_filter):
        result = fresh_filter.is_hallucination("請訂閱我的頻道")
        assert result["is_hallucination"] is True
        # Caught by partial match blacklist (earlier layer)
        assert result["filter_layer"] in ("blacklist_partial", "semantic")

    def test_semantic_subscribe_english(self, fresh_filter):
        result = fresh_filter.is_hallucination("please like and subscribe to my channel")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "semantic"

    def test_semantic_subtitle(self, fresh_filter):
        result = fresh_filter.is_hallucination("字幕翻譯製作")
        assert result["is_hallucination"] is True

    # --- Layer 4: Too short ---

    def test_too_short_two_chars(self, fresh_filter):
        result = fresh_filter.is_hallucination("好的")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "too_short"
        assert result["confidence"] == 0.8

    def test_too_short_one_char(self, fresh_filter):
        # Single non-blacklist char
        result = fresh_filter.is_hallucination("是")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "too_short"

    # --- Layer 5: High frequency ---

    def test_high_frequency_detection(self, fresh_filter):
        phrase = "重複的句子"
        # Track it enough times
        for _ in range(fresh_filter.frequency_threshold):
            fresh_filter.track_transcript(phrase)

        result = fresh_filter.is_hallucination(phrase)
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "high_frequency"

    def test_frequency_below_threshold(self, fresh_filter):
        phrase = "正常的句子不會重複太多次"
        fresh_filter.track_transcript(phrase)
        fresh_filter.track_transcript(phrase)

        result = fresh_filter.is_hallucination(phrase)
        assert result["is_hallucination"] is False

    def test_frequency_check_disabled(self, fresh_filter):
        phrase = "重複句子"
        for _ in range(10):
            fresh_filter.track_transcript(phrase)

        result = fresh_filter.is_hallucination(phrase, enable_frequency_check=False)
        assert result["is_hallucination"] is False

    # --- Normal text (should pass all filters) ---

    def test_normal_chinese_sentence(self, fresh_filter):
        result = fresh_filter.is_hallucination("今天我們要介紹機器學習的基本概念")
        assert result["is_hallucination"] is False
        assert result["filter_layer"] is None

    def test_normal_english_sentence(self, fresh_filter):
        result = fresh_filter.is_hallucination("Today we will discuss the project requirements")
        assert result["is_hallucination"] is False

    def test_normal_mixed_language(self, fresh_filter):
        result = fresh_filter.is_hallucination("這個 API 的 response time 很快")
        assert result["is_hallucination"] is False

    # --- Utility methods ---

    def test_track_transcript(self, fresh_filter):
        fresh_filter.track_transcript("hello")
        fresh_filter.track_transcript("hello")
        assert fresh_filter.transcript_frequency["hello"] == 2

    def test_reset_frequency_tracking(self, fresh_filter):
        fresh_filter.track_transcript("test")
        fresh_filter.reset_frequency_tracking()
        assert len(fresh_filter.transcript_frequency) == 0

    def test_add_to_blacklist(self, fresh_filter):
        fresh_filter.add_to_blacklist("custom hallucination")
        result = fresh_filter.is_hallucination("custom hallucination")
        assert result["is_hallucination"] is True
        assert result["filter_layer"] == "blacklist"

    def test_remove_from_blacklist(self, fresh_filter):
        fresh_filter.add_to_blacklist("temporary phrase")
        fresh_filter.remove_from_blacklist("temporary phrase")
        # Now it won't be in blacklist (but might fail on too_short)
        assert "temporary phrase" not in fresh_filter.hallucination_blacklist

    def test_get_stats(self, fresh_filter):
        fresh_filter.track_transcript("hello")
        stats = fresh_filter.get_stats()
        assert "blacklist_size" in stats
        assert "tracked_transcripts" in stats
        assert stats["tracked_transcripts"] == 1
        assert stats["blacklist_size"] > 0
