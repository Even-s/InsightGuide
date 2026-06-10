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

    def find_most_similar(
        self,
        query_text: str,
        candidate_texts: List[str],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find most similar texts to query from candidates.

        Args:
            query_text: The query text
            candidate_texts: List of candidate texts to compare
            top_k: Number of top results to return

        Returns:
            List of dicts with 'index', 'text', 'similarity' sorted by similarity

        Example:
            >>> results = service.find_most_similar(
            ...     "機器學習算法",
            ...     ["深度學習", "數據分析", "神經網路"],
            ...     top_k=2
            ... )
            >>> results[0]['text']
            '深度學習'
        """
        try:
            if not query_text or not candidate_texts:
                return []

            # Get query embedding
            query_embedding = self.get_embedding(query_text)

            # Get candidate embeddings
            candidate_embeddings = self.get_embeddings_batch(candidate_texts)

            # Calculate similarities
            similarities = []
            for idx, (text, embedding) in enumerate(zip(candidate_texts, candidate_embeddings)):
                similarity = self.cosine_similarity(query_embedding, embedding)
                similarities.append({
                    'index': idx,
                    'text': text,
                    'similarity': similarity
                })

            # Sort by similarity descending
            similarities.sort(key=lambda x: x['similarity'], reverse=True)

            # Return top k
            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Error finding most similar: {str(e)}")
            return []

    def calculate_semantic_score(
        self,
        utterance_text: str,
        semantic_anchors: List[str]
    ) -> float:
        """
        Calculate semantic similarity score between utterance and topic anchors.

        Uses the maximum similarity among all semantic anchors.

        Args:
            utterance_text: The transcribed utterance
            semantic_anchors: List of semantic anchor texts from topic card

        Returns:
            Semantic similarity score between 0 and 1

        Example:
            >>> score = service.calculate_semantic_score(
            ...     "今天介紹機器學習的三大類型",
            ...     ["機器學習分類", "監督式與非監督式學習"]
            ... )
            >>> print(f"Score: {score:.3f}")
            Score: 0.823
        """
        try:
            if not utterance_text or not semantic_anchors:
                return 0.0

            # Get utterance embedding
            utterance_embedding = self.get_embedding(utterance_text)

            # Get anchor embeddings
            anchor_embeddings = self.get_embeddings_batch(semantic_anchors)

            # Calculate max similarity across all anchors
            max_similarity = 0.0
            for anchor_embedding in anchor_embeddings:
                similarity = self.cosine_similarity(utterance_embedding, anchor_embedding)
                max_similarity = max(max_similarity, similarity)

            logger.debug(f"Semantic score: {max_similarity:.3f}")

            return max_similarity

        except Exception as e:
            logger.error(f"Error calculating semantic score: {str(e)}")
            return 0.0


# Singleton instance
embedding_service = EmbeddingService()
