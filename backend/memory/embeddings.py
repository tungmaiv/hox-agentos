"""
Embedding provider protocol and BGE_M3Provider implementation.

ARCHITECTURE:
- EmbeddingProvider: Protocol that all embedding providers must satisfy.
- BGE_M3Provider: Wraps BAAI/bge-m3 via FlagEmbedding.
  - Dimension: 1024 (locked — changing requires full DB reindex)
  - Multilingual: Vietnamese + English natively
  - CPU-bound: ALWAYS called from Celery workers, NEVER from FastAPI request handlers.
  - Model loaded lazily on first call, cached at class level (one instance per worker process).

USAGE:
    from memory.embeddings import BGE_M3Provider
    provider = BGE_M3Provider()
    vectors = await provider.embed(["User prefers dark mode", "Người dùng thích chế độ tối"])
    # vectors: list of 1024-float lists
"""

import asyncio
import threading
from typing import Protocol, runtime_checkable

import structlog

logger = structlog.get_logger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """
    Protocol for embedding providers.

    All implementations must:
    - Return list[list[float]] with inner lists of length == self.dimension
    - Be safe to call from async context (e.g., via run_in_executor for CPU-bound work)
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns one vector per text."""
        ...

    @property
    def dimension(self) -> int:
        """Return the embedding dimension (e.g., 1024 for bge-m3)."""
        ...


class BGE_M3Provider:
    """
    bge-m3 embedding provider via FlagEmbedding.

    Dimension: 1024. Multilingual (Vietnamese + English).
    CPU-bound: always called from Celery workers, never from FastAPI request handlers.
    Model is loaded lazily on first call and cached at class level (one per worker process).
    """

    _model = None  # class-level model cache — shared across instances within a process
    _lock = threading.Lock()  # guards lazy initialization against concurrent threads
    dimension: int = 1024

    def _get_model(self):  # type: ignore[return]
        """Load FlagModel on first use, then return cached instance.

        Double-checked locking: outer check avoids lock acquisition on every call
        after the model is loaded; inner check prevents duplicate loading when two
        threads race through the outer check simultaneously.
        """
        if self.__class__._model is None:
            with self.__class__._lock:
                if self.__class__._model is None:
                    from FlagEmbedding import FlagModel

                    self.__class__._model = FlagModel(
                        "BAAI/bge-m3",
                        use_fp16=True,  # halves memory; negligible accuracy loss on bge-m3
                        query_instruction_for_retrieval="",
                    )
                    logger.info("bge_m3_model_loaded")
        return self.__class__._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed texts using bge-m3.

        Runs model.encode() in a thread executor to avoid blocking the event loop.
        Returns list of 1024-dim float vectors, one per input text.
        """
        loop = asyncio.get_running_loop()
        model = self._get_model()
        result: list[list[float]] = await loop.run_in_executor(
            None, lambda: model.encode(texts).tolist()
        )
        logger.debug("embeddings_generated", count=len(texts))
        return result
