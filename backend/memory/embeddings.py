"""
Embedding provider protocol and BGE_M3Provider implementation.

ARCHITECTURE:
- EmbeddingProvider: Protocol that all embedding providers must satisfy.
- BGE_M3Provider: Wraps BAAI/bge-m3 via FlagEmbedding.
  - Dimension: 1024 (locked — changing requires full DB reindex)
  - Multilingual: Vietnamese + English natively
  - CPU-bound: ALWAYS called from Celery workers, NEVER from FastAPI request handlers.
  - Model loaded lazily on first call, cached at class level (one instance per worker process).
- SidecarEmbeddingProvider: Calls infinity-emb HTTP sidecar (POST /embeddings).
  - Primary path for FastAPI request handlers — non-blocking HTTP call.
  - Falls back to BGE_M3Provider if sidecar is unreachable.

USAGE:
    from memory.embeddings import BGE_M3Provider
    provider = BGE_M3Provider()
    vectors = await provider.embed(["User prefers dark mode", "Người dùng thích chế độ tối"])
    # vectors: list of 1024-float lists

    from memory.embeddings import SidecarEmbeddingProvider
    provider = SidecarEmbeddingProvider()
    vectors = await provider.embed(["hello world"])
    # vectors: list of 1024-float lists (from sidecar or fallback)
"""

import asyncio
import threading
from typing import Protocol, runtime_checkable

import httpx
import structlog

from core.config import settings

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


class SidecarEmbeddingProvider:
    """
    Embedding provider backed by an infinity-emb HTTP sidecar.

    Primary path: POST {sidecar_url}/embeddings (OpenAI-compat format).
    Fallback path: BGE_M3Provider (Celery worker, in-process) if sidecar unreachable.

    Dimension: 1024 (bge-m3). Validated on startup via validate_dimension().
    """

    dimension: int = 1024

    def __init__(self, sidecar_url: str | None = None) -> None:
        self._sidecar_url = sidecar_url or settings.embedding_sidecar_url
        self._model_name = settings.embedding_model_path

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Embed texts via sidecar HTTP. Falls back to BGE_M3Provider on ConnectError.
        """
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._sidecar_url}/embeddings",
                    json={"input": texts, "model": self._model_name},
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                # OpenAI-compat: {"data": [{"embedding": [...], "index": N}, ...]}
                sorted_items = sorted(data["data"], key=lambda x: x["index"])
                result: list[list[float]] = [item["embedding"] for item in sorted_items]
                logger.debug("sidecar_embeddings_generated", count=len(texts))
                return result
        except httpx.ConnectError:
            logger.warning(
                "embedding_sidecar_unreachable",
                url=self._sidecar_url,
                fallback="BGE_M3Provider",
            )
            fallback = BGE_M3Provider()
            return await fallback.embed(texts)

    async def validate_dimension(self) -> None:
        """
        Check sidecar /health and verify dimension == 1024.

        Raises RuntimeError on mismatch. Called once at backend startup.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._sidecar_url}/health", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            reported_dim = data.get("dimensions") or data.get("dim")
            if reported_dim is not None and reported_dim != self.dimension:
                raise RuntimeError(
                    f"Embedding sidecar dimension mismatch: "
                    f"expected {self.dimension}, got {reported_dim}. "
                    f"Ensure EMBEDDING_MODEL=BAAI/bge-m3 in sidecar config."
                )
            logger.info(
                "embedding_sidecar_validated",
                url=self._sidecar_url,
                dimension=self.dimension,
            )
