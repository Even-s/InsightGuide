"""Scoring service for topic card coverage calculation."""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for calculating coverage scores (keyword, fact, final)."""

    def __init__(self):
        """Initialize scoring service."""
        pass

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for matching (lowercase, remove punctuation).

        Args:
            text: Input text

        Returns:
            Normalized text

        Example:
            >>> service.normalize_text("Machine Learning!")
            'machine learning'
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove common punctuation but keep spaces
        text = re.sub(r'[,\.!\?;:，。！？；：、]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text


    def _is_fact_mentioned(
        self,
        normalized_utterance: str,
        fact: Dict[str, Any]
    ) -> bool:
        """
        Check if a fact is mentioned in the utterance.

        Checks both the main text and aliases. If subpoints are present, every
        subpoint must be mentioned before the parent fact counts as mentioned.

        Args:
            normalized_utterance: Normalized utterance text
            fact: Fact object with 'text' and optional 'aliases'

        Returns:
            True if fact is mentioned
        """
        subpoints = fact.get('subpoints') or []
        if subpoints:
            normalized_subpoints = [
                self.normalize_text(subpoint)
                for subpoint in subpoints
                if self.normalize_text(subpoint)
            ]
            if not normalized_subpoints:
                return False
            return all(
                subpoint in normalized_utterance
                for subpoint in normalized_subpoints
            )

        # Check main fact text
        fact_text = self.normalize_text(fact.get('text', ''))
        if fact_text and fact_text in normalized_utterance:
            return True

        # Check aliases
        aliases = fact.get('aliases', [])
        for alias in aliases:
            normalized_alias = self.normalize_text(alias)
            if normalized_alias and normalized_alias in normalized_utterance:
                return True

        return False



# Singleton instance
scoring_service = ScoringService()
