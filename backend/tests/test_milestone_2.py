"""Integration tests for Milestone 2: AI Slide Analysis."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.openai_service import openai_service
from app.services.topic_card_service import topic_card_service
from app.schemas.topic_card import CoverageRule, MustMentionFact


class TestOpenAIService:
    """Test OpenAI service integration."""

    def test_analysis_prompt_building(self):
        """Test that analysis prompts are built correctly."""
        prompt = openai_service._build_analysis_prompt(
            slide_number=1,
            extracted_text="測試內容",
            speaker_notes="備註",
            deck_context="簡報背景"
        )

        assert "第 1 頁" in prompt
        assert "測試內容" in prompt
        assert "備註" in prompt
        assert "簡報背景" in prompt
        assert "Topic Cards" in prompt

    def test_analysis_schema_structure(self):
        """Test that the analysis schema is properly structured."""
        schema = openai_service._get_analysis_schema()

        # Verify top-level structure
        assert schema["type"] == "object"
        assert "slideSummary" in schema["properties"]
        assert "topicCards" in schema["properties"]

        # Verify topic card structure
        card_schema = schema["properties"]["topicCards"]["items"]
        assert "title" in card_schema["properties"]
        assert "coverageRule" in card_schema["properties"]

        # Verify coverage rule structure
        coverage_rule = card_schema["properties"]["coverageRule"]
        assert "semanticAnchors" in coverage_rule["properties"]
        assert "expectedKeywords" in coverage_rule["properties"]
        assert "mustMentionFacts" in coverage_rule["properties"]
        assert "thresholds" in coverage_rule["properties"]

    def test_slide_analysis_model_is_configurable(self):
        """Test that slide analysis and metadata generation share the configured model."""
        service = openai_service
        original_client = service.client
        original_model = service.analysis_model
        mock_client = MagicMock()

        analysis_response = Mock()
        analysis_response.choices = [Mock(message=Mock(content="""{
            "slideSummary": "測試摘要",
            "topicCards": []
        }"""))]
        metadata_response = Mock()
        metadata_response.choices = [Mock(message=Mock(content="""{
            "description": "測試描述",
            "importance": "must"
        }"""))]
        mock_client.chat.completions.create.side_effect = [
            analysis_response,
            metadata_response,
        ]

        try:
            service.client = mock_client
            service.analysis_model = "gpt-5.5"

            service.analyze_slide(
                slide_number=1,
                slide_image_url="https://example.com/image.png",
                extracted_text="測試內容",
            )
            service.generate_card_metadata("請生成卡片 metadata")

            used_models = [
                call.kwargs["model"]
                for call in mock_client.chat.completions.create.call_args_list
            ]
            assert used_models == ["gpt-5.5", "gpt-5.5"]
        finally:
            service.client = original_client
            service.analysis_model = original_model

    @patch('app.services.openai_service.OpenAI')
    def test_analyze_slide_success(self, mock_openai):
        """Test successful slide analysis."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="""{
            "slideSummary": "測試摘要",
            "topicCards": [{
                "title": "測試主題",
                "description": "測試描述",
                "importance": "must",
                "topicType": "problem",
                "coverageRule": {
                    "semanticAnchors": ["核心概念"],
                    "expectedKeywords": ["關鍵字"],
                    "mustMentionFacts": [],
                    "negativeSignals": [],
                    "thresholds": {"probablyCovered": 0.62, "covered": 0.78},
                    "scoringWeights": {
                        "semanticSimilarity": 0.55,
                        "keywordCoverage": 0.25,
                        "factCoverage": 0.20
                    }
                },
                "suggestedScript": "建議講稿",
                "estimatedSeconds": 30,
                "orderIndex": 0
            }]
        }"""))]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create a new service instance with mocked client
        service = openai_service
        service.client = mock_client

        result = service.analyze_slide(
            slide_number=1,
            slide_image_url="https://example.com/image.png",
            extracted_text="測試內容"
        )

        assert "slideSummary" in result
        assert "topicCards" in result
        assert len(result["topicCards"]) == 1
        assert result["topicCards"][0]["title"] == "測試主題"

    @patch('app.services.openai_service.OpenAI')
    def test_generate_embeddings(self, mock_openai):
        """Test embedding generation."""
        # Mock OpenAI embeddings response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1, 0.2, 0.3]),
            Mock(embedding=[0.4, 0.5, 0.6])
        ]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client

        service = openai_service
        service.client = mock_client

        texts = ["文本1", "文本2"]
        embeddings = service.generate_embeddings(texts)

        assert len(embeddings) == 2
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]


class TestTopicCardService:
    """Test topic card service."""

    def test_normalize_coverage_rule_limits_visible_points_and_keeps_details(self):
        """Extra talking points should fold into at most three visible parent facts."""
        rule = {
            "semanticAnchors": ["交易量", "振幅", "漲幅", "跌幅", "市場熱度"],
            "expectedKeywords": [],
            "mustMentionFacts": [
                {"text": "前五大排行", "required": True, "aliases": ["Top 5"]},
                {"text": "成交量集中", "required": True, "aliases": []},
            ],
            "negativeSignals": [],
        }

        normalized = topic_card_service.normalize_coverage_rule_for_important_points(rule)
        facts = normalized["mustMentionFacts"]
        visible_points = [fact["text"] for fact in facts]
        aliases = [
            alias
            for fact in facts
            for alias in fact.get("aliases", [])
        ]
        subpoints = [
            subpoint
            for fact in facts
            for subpoint in fact.get("subpoints", [])
        ]

        assert len(facts) == 3
        assert visible_points == ["交易量", "振幅", "漲幅"]
        assert "跌幅" in subpoints
        assert "市場熱度" in subpoints
        assert "前五大排行" in subpoints
        assert "Top 5" in aliases
        assert "成交量集中" in subpoints

    def test_numbered_child_points_fold_under_visible_parent(self):
        """A visible parent point can require all numbered child points."""
        rule = {
            "semanticAnchors": [
                "交易量前三大",
                "1-1 台積電",
                "1-2 聯電",
                "1-3 華邦電",
            ],
            "expectedKeywords": [],
            "mustMentionFacts": [],
            "negativeSignals": [],
        }

        normalized = topic_card_service.normalize_coverage_rule_for_important_points(rule)
        facts = normalized["mustMentionFacts"]

        assert len(facts) == 1
        assert facts[0]["text"] == "交易量前三大"
        assert facts[0]["subpoints"] == ["台積電", "聯電", "華邦電"]

    def test_create_topic_card_from_analysis(self, db_session):
        """Test creating topic card from analysis data."""
        analysis_data = {
            "title": "測試主題",
            "description": "測試描述",
            "importance": "must",
            "topicType": "problem",
            "coverageRule": {
                "semanticAnchors": ["核心概念1", "核心概念2"],
                "expectedKeywords": ["關鍵字1", "關鍵字2"],
                "mustMentionFacts": [
                    {
                        "text": "必須提到的事實",
                        "required": True,
                        "aliases": ["別名1"]
                    }
                ],
                "negativeSignals": ["不該出現的詞"],
                "thresholds": {
                    "probablyCovered": 0.62,
                    "covered": 0.78
                }
            },
            "suggestedScript": "建議的講稿內容",
            "estimatedSeconds": 35,
            "orderIndex": 0
        }

        # This would normally require a real database session
        # In actual tests, you'd use pytest fixtures with test database
        # For now, this demonstrates the expected structure

        # Verify the analysis data structure is valid
        assert "title" in analysis_data
        assert "coverageRule" in analysis_data
        assert "semanticAnchors" in analysis_data["coverageRule"]
        assert len(analysis_data["coverageRule"]["semanticAnchors"]) >= 1

        # Verify coverage rule has all required fields
        coverage_rule = analysis_data["coverageRule"]
        assert "thresholds" in coverage_rule
        assert "probablyCovered" in coverage_rule["thresholds"]
        assert "covered" in coverage_rule["thresholds"]


class TestCoverageRules:
    """Test coverage rule structure and validation."""

    def test_coverage_rule_schema(self):
        """Test that coverage rule schema validates correctly."""
        rule = CoverageRule(
            semanticAnchors=["語意錨點1", "語意錨點2"],
            expectedKeywords=["關鍵字1", "關鍵字2", "關鍵字3"],
            mustMentionFacts=[
                MustMentionFact(
                    text="必須事實",
                    required=True,
                    aliases=["別名1", "別名2"]
                )
            ],
            negativeSignals=["負面信號"]
        )

        # Verify default values are set
        assert rule.thresholds.probablyCovered == 0.62
        assert rule.thresholds.covered == 0.78
        assert rule.scoringWeights.semanticSimilarity == 0.55
        assert rule.scoringWeights.keywordCoverage == 0.25
        assert rule.scoringWeights.factCoverage == 0.20

    def test_scoring_weights_sum_to_one(self):
        """Test that scoring weights approximately sum to 1.0."""
        rule = CoverageRule(
            semanticAnchors=["test"],
            expectedKeywords=[]
        )

        total = (
            rule.scoringWeights.semanticSimilarity +
            rule.scoringWeights.keywordCoverage +
            rule.scoringWeights.factCoverage
        )

        assert abs(total - 1.0) < 0.01  # Allow small floating point difference

    def test_threshold_ordering(self):
        """Test that covered threshold is higher than probably covered."""
        rule = CoverageRule(
            semanticAnchors=["test"],
            expectedKeywords=[]
        )

        assert rule.thresholds.covered > rule.thresholds.probablyCovered


@pytest.fixture
def db_session():
    """Mock database session for testing."""
    # In real tests, this would return a test database session
    return Mock()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
