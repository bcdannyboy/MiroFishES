"""Embedding client backed by an OpenAI-compatible embeddings API."""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from openai import OpenAI

from ..config import Config
from .model_routing import TaskModelRouter


class LocalEmbeddingClient:
    """Resolve embeddings through the task router and normalize vectors locally."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        router: TaskModelRouter | None = None,
    ):
        self.router = router or TaskModelRouter()
        route = self.router.resolve('embedding')
        self.route = type(route)(
            task=route.task,
            model=model or route.model,
            api_key=api_key or route.api_key,
            base_url=base_url or route.base_url,
        )
        if not self.route.api_key:
            raise ValueError("LOCAL_EMBEDDING_API_KEY, OPENAI_API_KEY, or LLM_API_KEY is not configured")

        self.dimensions = dimensions if dimensions is not None else Config.get_embedding_dimensions()
        self.client = OpenAI(
            api_key=self.route.api_key,
            base_url=self.route.base_url,
        )

    def embed_text(self, text: str, *, normalize: bool = True) -> list[float]:
        """Embed a single text string."""
        return self.embed_texts([text], normalize=normalize)[0]

    def embed_texts(self, texts: Sequence[str], *, normalize: bool = True) -> list[list[float]]:
        """Embed multiple texts and optionally L2-normalize the results."""
        if not texts:
            return []

        kwargs: dict[str, object] = {
            'model': self.route.model,
            'input': list(texts),
            'encoding_format': 'float',
        }
        if self.dimensions is not None:
            kwargs['dimensions'] = self.dimensions

        response = self.client.embeddings.create(**kwargs)
        vectors = [list(item.embedding) for item in response.data]
        if not normalize:
            return vectors
        return [self._normalize(vector) for vector in vectors]

    @staticmethod
    def _normalize(vector: Iterable[float]) -> list[float]:
        """Normalize one vector to unit length while handling zero vectors."""
        materialized = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in materialized))
        if norm == 0.0:
            return [0.0 for _ in materialized]
        return [value / norm for value in materialized]
