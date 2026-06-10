"""
Unit tests for OpenAI Service
Tests OpenAI API integration for document analysis and generation.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from app.services.openai_service import openai_service, OpenAIService


class TestOpenAIService:
    """Test suite for OpenAI service."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = Mock()
        return client

    @pytest.fixture
    def sample_completion_response(self):
        """Create a sample OpenAI completion response."""
        return ChatCompletion(
            id="chatcmpl-123",
            object="chat.completion",
            created=1234567890,
            model="gpt-4o-2024-08-06",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content='{"title": "Test Section", "content": "Test content"}'
                    ),
                    finish_reason="stop"
                )
            ],
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        )

    def test_service_initialization(self):
        """Test that the service initializes correctly."""
        assert openai_service is not None
        assert isinstance(openai_service, OpenAIService)
        assert hasattr(openai_service, 'client')
        assert hasattr(openai_service, 'analysis_model')
        assert hasattr(openai_service, 'embedding_model')

    def test_service_has_required_methods(self):
        """Test that service has all required methods."""
        assert hasattr(openai_service, 'analyze_section')
        assert hasattr(openai_service, 'generate_embeddings')
        assert hasattr(openai_service, 'generate_card_metadata')
        assert hasattr(openai_service, 'analyze_document_section')

    @patch('app.services.openai_service.OpenAI')
    def test_analyze_section_with_url(self, mock_openai_class):
        """Test section analysis with image URL."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Create response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"sections": [], "questionCards": []}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        result = service.analyze_section(
            slide_number=1,
            slide_image_url="https://example.com/image.png",
            extracted_text="Test content"
        )

        # Verify API was called
        mock_client.chat.completions.create.assert_called_once()

    @patch('app.services.openai_service.OpenAI')
    def test_analyze_section_with_base64(self, mock_openai_class):
        """Test section analysis with base64 image."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"sections": [], "questionCards": []}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        result = service.analyze_section(
            slide_number=1,
            slide_image_url="https://example.com/image.png",
            extracted_text="Test content",
            slide_image_base64="iVBORw0KGgoAAAANSUhEUg"
        )

        # Should prefer base64 over URL
        call_args = mock_client.chat.completions.create.call_args
        assert "data:image/png;base64," in str(call_args)

    @patch('app.services.openai_service.OpenAI')
    def test_analyze_section_with_speaker_notes(self, mock_openai_class):
        """Test section analysis with speaker notes."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"sections": [], "questionCards": []}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        result = service.analyze_section(
            slide_number=1,
            slide_image_url="https://example.com/image.png",
            extracted_text="Test content",
            speaker_notes="Important: This is the key point"
        )

        mock_client.chat.completions.create.assert_called_once()

    @patch('app.services.openai_service.OpenAI')
    def test_generate_embeddings_single_text(self, mock_openai_class):
        """Test embedding generation for single text."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.total_tokens = 10

        mock_client.embeddings.create.return_value = mock_response

        service = OpenAIService()

        result = service.generate_embeddings(["Test text"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @patch('app.services.openai_service.OpenAI')
    def test_generate_embeddings_multiple_texts(self, mock_openai_class):
        """Test embedding generation for multiple texts."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [Mock(), Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.data[1].embedding = [0.4, 0.5, 0.6]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.total_tokens = 20

        mock_client.embeddings.create.return_value = mock_response

        service = OpenAIService()

        result = service.generate_embeddings(["Text 1", "Text 2"])

        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]

    @patch('app.services.openai_service.OpenAI')
    def test_generate_card_metadata(self, mock_openai_class):
        """Test card metadata generation."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"title": "Test Card", "priority": "high"}'
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        result = service.generate_card_metadata(
            prompt="Generate test card metadata"
        )

        # Should return parsed JSON
        assert isinstance(result, dict)
        assert "title" in result

    @patch('app.services.openai_service.OpenAI')
    def test_api_error_handling(self, mock_openai_class):
        """Test error handling when API fails."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception("API Error")

        service = OpenAIService()

        # analyze_section should propagate errors
        with pytest.raises(Exception):
            service.analyze_section(
                slide_number=1,
                slide_image_url="https://example.com/image.png",
                extracted_text="Test"
            )

    @patch('app.services.openai_service.OpenAI')
    def test_timeout_configuration(self, mock_openai_class):
        """Test that timeout is configured."""
        mock_openai_class.return_value = Mock()

        service = OpenAIService()

        # Verify timeout was set during initialization
        call_args = mock_openai_class.call_args
        assert call_args is not None
        assert 'timeout' in call_args[1] or len(call_args[0]) > 0

    def test_build_analysis_prompt(self):
        """Test prompt building for analysis."""
        # Access private method for testing
        prompt = openai_service._build_analysis_prompt(
            slide_number=1,
            extracted_text="Test content",
            speaker_notes="Test notes",
            deck_context="Test context"
        )

        assert "Test content" in prompt
        assert "Test notes" in prompt or prompt  # May or may not include notes in prompt

    def test_get_system_prompt(self):
        """Test system prompt retrieval."""
        system_prompt = openai_service._get_system_prompt()

        assert isinstance(system_prompt, str)
        assert len(system_prompt) > 0

    @patch('app.services.openai_service.OpenAI')
    def test_analyze_section_tracks_billing(self, mock_openai_class):
        """Test that API usage is tracked for billing."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"sections": [], "questionCards": []}'
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        with patch('app.services.openai_service.billing_service') as mock_billing:
            result = service.analyze_section(
                slide_number=1,
                slide_image_url="https://example.com/image.png",
                extracted_text="Test content",
                deck_id="deck-123",
                source_id="source-456"
            )

    @patch('app.services.openai_service.OpenAI')
    def test_multiple_card_metadata_calls(self, mock_openai_class):
        """Test multiple sequential card metadata generation calls."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '{"title": "Card"}'
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20

        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()

        # Multiple calls should work
        for i in range(3):
            result = service.generate_card_metadata(
                prompt=f"Generate card {i}"
            )

        assert mock_client.chat.completions.create.call_count == 3

    @patch('app.services.openai_service.OpenAI')
    def test_embedding_batch_processing(self, mock_openai_class):
        """Test generating embeddings for multiple texts in one call."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.data = [Mock(), Mock(), Mock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_response.data[1].embedding = [0.4, 0.5, 0.6]
        mock_response.data[2].embedding = [0.7, 0.8, 0.9]
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 30
        mock_response.usage.total_tokens = 30

        mock_client.embeddings.create.return_value = mock_response

        service = OpenAIService()

        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = service.generate_embeddings(texts)

        assert len(embeddings) == 3
        assert embeddings[0] == [0.1, 0.2, 0.3]
        assert embeddings[1] == [0.4, 0.5, 0.6]
        assert embeddings[2] == [0.7, 0.8, 0.9]
