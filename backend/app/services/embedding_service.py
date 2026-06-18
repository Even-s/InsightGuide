"""Embedding service for semantic similarity computation."""

import logging
from typing import List, Dict, Any, Optional
import numpy as np
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for computing text embeddings and semantic similarity."""

    def __init__(self):
        """Initialize embedding service."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL
        self.embedding_dimension = 3072  # text-embedding-3-large dimension

    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Example:
            >>> embedding = service.get_embedding("機器學習的基本概念")
            >>> len(embedding)
            3072
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text provided for embedding")
                return [0.0] * self.embedding_dimension

            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )

            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding for text: {text[:50]}...")

            return embedding

        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts in a single API call.

        More efficient than calling get_embedding multiple times.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors

        Example:
            >>> texts = ["機器學習", "深度學習", "神經網路"]
            >>> embeddings = service.get_embeddings_batch(texts)
            >>> len(embeddings)
            3
        """
        try:
            if not texts:
                return []

            # Filter out empty texts
            valid_texts = [t for t in texts if t and t.strip()]
            if not valid_texts:
                logger.warning("All texts are empty")
                return [[0.0] * self.embedding_dimension] * len(texts)

            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts
            )

            embeddings = [item.embedding for item in response.data]
            logger.debug(f"Generated {len(embeddings)} embeddings in batch")

            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch embeddings: {str(e)}")
            raise

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between -1 and 1 (typically 0 to 1)

        Example:
            >>> similarity = service.cosine_similarity(emb1, emb2)
            >>> print(f"Similarity: {similarity:.3f}")
            Similarity: 0.876
        """
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = dot_product / (norm_a * norm_b)

            # Clamp to [-1, 1] to handle floating point errors
            similarity = max(-1.0, min(1.0, float(similarity)))

            return similarity

        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0



# Singleton instance
embedding_service = EmbeddingService()
