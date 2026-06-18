"""
Unit tests for Chinese text prefiltering in Answer Evaluation Engine.
Tests character bigram overlap scoring for Chinese text.
"""

import pytest
from app.services.answer_evaluation_engine import AnswerEvaluationEngine


class TestChineseOverlapScore:
    """Test character n-gram overlap scoring."""

    def setup_method(self):
        self.engine = AnswerEvaluationEngine()

    def test_identical_text_returns_one(self):
        score = self.engine._chinese_overlap_score("資料收集", "資料收集")
        assert score == 1.0

    def test_completely_different_returns_zero(self):
        score = self.engine._chinese_overlap_score("天氣很好", "程式設計")
        assert score == 0.0

    def test_partial_overlap(self):
        score = self.engine._chinese_overlap_score("資料收集很花時間", "資料收集")
        # "資料收集" has bigrams: 資料, 料收, 收集
        # "資料收集很花時間" has bigrams: 資料, 料收, 收集, 集很, 很花, 花時, 時間
        # overlap = 3/3 = 1.0
        assert score == 1.0

    def test_subset_match(self):
        score = self.engine._chinese_overlap_score("收集", "資料收集流程")
        # text bigrams: 收集
        # ref bigrams: 資料, 料收, 收集, 集流, 流程 → overlap=1/4
        assert 0.0 < score < 1.0

    def test_empty_text_returns_zero(self):
        score = self.engine._chinese_overlap_score("", "資料收集")
        assert score == 0.0

    def test_empty_reference_returns_zero(self):
        score = self.engine._chinese_overlap_score("資料收集", "")
        assert score == 0.0

    def test_both_empty_returns_zero(self):
        score = self.engine._chinese_overlap_score("", "")
        assert score == 0.0

    def test_single_char_text_returns_zero(self):
        # Single char can't form a bigram
        score = self.engine._chinese_overlap_score("資", "資料收集")
        assert score == 0.0

    def test_mixed_chinese_english(self):
        score = self.engine._chinese_overlap_score("API介面設計", "介面設計規範")
        # Should find overlap on 介面, 面設, 設計
        assert score > 0.0

    def test_trigram_overlap(self):
        score = self.engine._chinese_overlap_score("資料收集", "資料收集", n=3)
        assert score == 1.0


class TestPrefilterCandidatesWithChinese:
    """Test that prefilter works with Chinese text."""

    def setup_method(self):
        self.engine = AnswerEvaluationEngine()

    def _make_card_data(self, focus_text="", question_text="", keywords=None, elements=None):
        from unittest.mock import Mock
        card = Mock()
        card.focus_text = focus_text
        card.question_text = question_text
        card.coverage_rule = {
            "expectedKeywords": keywords or [],
            "mustMentionElements": elements or [],
        }
        return {"card": card, "state": Mock()}

    def test_keyword_substring_match_works_for_chinese(self):
        candidates = [
            self._make_card_data(keywords=["資料收集"]),
            self._make_card_data(keywords=["系統架構"]),
        ]
        result = self.engine._prefilter_candidates(
            "目前最花時間的是資料收集的部分", candidates, top_k=8
        )
        # keyword match uses `in` operator, should work
        assert len(result) >= 1

    def test_focus_text_bigram_match(self):
        candidates = [
            self._make_card_data(focus_text="資料收集流程"),
            self._make_card_data(focus_text="系統架構設計"),
        ]
        result = self.engine._prefilter_candidates(
            "我們的資料收集有很多問題", candidates, top_k=8
        )
        # Both returned since <= top_k, but first should score higher
        assert len(result) >= 1

    def test_returns_all_when_under_top_k(self):
        candidates = [
            self._make_card_data(focus_text="A"),
            self._make_card_data(focus_text="B"),
        ]
        result = self.engine._prefilter_candidates("隨便什麼", candidates, top_k=8)
        assert len(result) == 2

    def test_filters_to_top_k_when_over(self):
        candidates = [self._make_card_data(focus_text=f"卡片{i}") for i in range(12)]
        # Give one a strong keyword match
        candidates[5] = self._make_card_data(keywords=["重要關鍵字"])
        result = self.engine._prefilter_candidates("包含重要關鍵字的句子", candidates, top_k=4)
        assert len(result) <= 4
