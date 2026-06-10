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

    def calculate_keyword_score(
        self,
        utterance_text: str,
        expected_keywords: List[str]
    ) -> float:
        """
        Calculate keyword coverage score.

        Score = (number of matched keywords) / (total expected keywords)

        Args:
            utterance_text: The transcribed utterance
            expected_keywords: List of expected keywords from topic card

        Returns:
            Keyword coverage score between 0 and 1

        Example:
            >>> score = service.calculate_keyword_score(
            ...     "今天介紹機器學習和深度學習",
            ...     ["機器學習", "深度學習", "神經網路"]
            ... )
            >>> print(f"Score: {score:.3f}")
            Score: 0.667  # 2 out of 3 keywords matched
        """
        try:
            if not expected_keywords:
                return 1.0  # No keywords to match

            if not utterance_text:
                return 0.0

            # Normalize texts
            normalized_utterance = self.normalize_text(utterance_text)

            # Count matched keywords
            matched_count = 0
            for keyword in expected_keywords:
                normalized_keyword = self.normalize_text(keyword)
                if normalized_keyword in normalized_utterance:
                    matched_count += 1
                    logger.debug(f"Keyword matched: {keyword}")

            score = matched_count / len(expected_keywords)
            logger.debug(f"Keyword score: {matched_count}/{len(expected_keywords)} = {score:.3f}")

            return score

        except Exception as e:
            logger.error(f"Error calculating keyword score: {str(e)}")
            return 0.0

    def calculate_fact_score(
        self,
        utterance_text: str,
        must_mention_facts: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate fact coverage score.

        Each fact can have aliases. Score considers required vs optional facts.

        Args:
            utterance_text: The transcribed utterance
            must_mention_facts: List of fact objects with 'text', 'required', 'aliases'

        Returns:
            Fact coverage score between 0 and 1

        Example:
            >>> facts = [
            ...     {"text": "92%準確率", "required": True, "aliases": ["92%", "九成二"]},
            ...     {"text": "降低成本", "required": False}
            ... ]
            >>> score = service.calculate_fact_score("達到92%的準確率", facts)
            >>> print(f"Score: {score:.3f}")
            Score: 1.0  # Required fact matched
        """
        try:
            if not must_mention_facts:
                return 1.0  # No facts to match

            if not utterance_text:
                return 0.0

            normalized_utterance = self.normalize_text(utterance_text)

            # Separate required and optional facts
            required_facts = [f for f in must_mention_facts if f.get('required', True)]
            optional_facts = [f for f in must_mention_facts if not f.get('required', True)]

            # Check required facts
            required_matched = 0
            for fact in required_facts:
                if self._is_fact_mentioned(normalized_utterance, fact):
                    required_matched += 1
                    logger.debug(f"Required fact matched: {fact['text']}")

            # Check optional facts
            optional_matched = 0
            for fact in optional_facts:
                if self._is_fact_mentioned(normalized_utterance, fact):
                    optional_matched += 1
                    logger.debug(f"Optional fact matched: {fact['text']}")

            # Calculate score
            # Required facts are weighted more heavily
            if len(required_facts) > 0:
                required_score = required_matched / len(required_facts)
            else:
                required_score = 1.0

            if len(optional_facts) > 0:
                optional_score = optional_matched / len(optional_facts)
            else:
                optional_score = 1.0

            if required_facts and optional_facts:
                final_score = required_score * 0.8 + optional_score * 0.2
            elif required_facts:
                final_score = required_score
            else:
                final_score = optional_score

            logger.debug(
                f"Fact score: required={required_matched}/{len(required_facts)}, "
                f"optional={optional_matched}/{len(optional_facts)}, "
                f"final={final_score:.3f}"
            )

            return final_score

        except Exception as e:
            logger.error(f"Error calculating fact score: {str(e)}")
            return 0.0

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

    def calculate_final_score(
        self,
        semantic_score: float,
        keyword_score: float,
        fact_score: float,
        weights: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Calculate weighted final score.

        Default weights:
        - semantic: 55%
        - keyword: 25%
        - fact: 20%

        Args:
            semantic_score: Semantic similarity score (0-1)
            keyword_score: Keyword coverage score (0-1)
            fact_score: Fact coverage score (0-1)
            weights: Optional custom weights

        Returns:
            Final weighted score between 0 and 1

        Example:
            >>> score = service.calculate_final_score(0.85, 0.67, 1.0)
            >>> print(f"Final score: {score:.3f}")
            Final score: 0.821
        """
        try:
            # Default weights from architecture spec
            if weights is None:
                weights = {
                    'semanticSimilarity': 0.55,
                    'keywordCoverage': 0.25,
                    'factCoverage': 0.20
                }

            w_semantic = weights.get('semanticSimilarity', 0.55)
            w_keyword = weights.get('keywordCoverage', 0.25)
            w_fact = weights.get('factCoverage', 0.20)

            final_score = (
                semantic_score * w_semantic +
                keyword_score * w_keyword +
                fact_score * w_fact
            )

            # Clamp to [0, 1]
            final_score = max(0.0, min(1.0, final_score))

            logger.debug(
                f"Final score calculation: "
                f"semantic={semantic_score:.3f}*{w_semantic:.2f} + "
                f"keyword={keyword_score:.3f}*{w_keyword:.2f} + "
                f"fact={fact_score:.3f}*{w_fact:.2f} = "
                f"{final_score:.3f}"
            )

            return final_score

        except Exception as e:
            logger.error(f"Error calculating final score: {str(e)}")
            return 0.0

    def determine_status(
        self,
        final_score: float,
        thresholds: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Determine card status based on final score and thresholds.

        Default thresholds:
        - covered: 0.78
        - probably_covered: 0.62

        Args:
            final_score: The final weighted score
            thresholds: Optional custom thresholds

        Returns:
            Card status: 'covered', 'probably_covered', or 'pending'

        Example:
            >>> status = service.determine_status(0.82)
            >>> print(status)
            'covered'
        """
        try:
            # Default thresholds (optimized for GPT-5.4-mini fast semantic understanding)
            if thresholds is None:
                thresholds = {
                    'covered': 0.70,
                    'probablyCovered': 0.55
                }

            covered_threshold = thresholds.get('covered', 0.70)
            probably_threshold = thresholds.get('probablyCovered', 0.55)

            if final_score >= covered_threshold:
                return 'covered'
            elif final_score >= probably_threshold:
                return 'probably_covered'
            else:
                return 'pending'

        except Exception as e:
            logger.error(f"Error determining status: {str(e)}")
            return 'pending'


# Singleton instance
scoring_service = ScoringService()
