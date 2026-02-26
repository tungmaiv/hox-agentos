"""
TDD tests for BGE_M3Provider.

CRITICAL: Mock FlagEmbedding.FlagModel — do NOT load the 570MB model in CI.
The real model loads from BAAI/bge-m3 on first use; tests must never trigger this.
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from memory.embeddings import BGE_M3Provider, EmbeddingProvider


@pytest.fixture(autouse=True)
def mock_flag_model():
    """
    Mock FlagModel to avoid loading 570MB model in tests.

    Returns numpy arrays matching the real bge-m3 output shape.
    Resets class-level model cache before each test to ensure isolation.
    """
    mock_model = MagicMock()

    def mock_encode(texts: list[str]) -> np.ndarray:
        return np.zeros((len(texts), 1024), dtype=np.float32)

    mock_model.encode.side_effect = mock_encode

    # Reset class-level cache so each test starts fresh
    BGE_M3Provider._model = None
    with patch.object(BGE_M3Provider, "_get_model", return_value=mock_model):
        yield mock_model


def test_bge_m3_provider_dimension() -> None:
    """dimension class attribute returns 1024."""
    provider = BGE_M3Provider()
    assert provider.dimension == 1024


@pytest.mark.asyncio
async def test_bge_m3_provider_embed_returns_correct_shape() -> None:
    """embed(['hello']) returns list of len 1, inner list len 1024."""
    provider = BGE_M3Provider()
    result = await provider.embed(["hello"])
    assert len(result) == 1
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_bge_m3_provider_embed_multiple_texts() -> None:
    """embed(3 texts) returns list of 3 embeddings, each 1024-dim."""
    provider = BGE_M3Provider()
    result = await provider.embed(["a", "b", "c"])
    assert len(result) == 3
    for vec in result:
        assert len(vec) == 1024


@pytest.mark.asyncio
async def test_bge_m3_provider_embed_returns_floats() -> None:
    """embed() returns list[list[float]], not numpy arrays."""
    provider = BGE_M3Provider()
    result = await provider.embed(["test"])
    assert isinstance(result, list)
    assert isinstance(result[0], list)
    assert isinstance(result[0][0], float)


def test_embedding_provider_protocol() -> None:
    """BGE_M3Provider satisfies EmbeddingProvider protocol (runtime_checkable)."""
    provider = BGE_M3Provider()
    assert isinstance(provider, EmbeddingProvider)


@pytest.mark.asyncio
async def test_bge_m3_encode_called_with_texts(mock_flag_model: MagicMock) -> None:
    """model.encode() is called with the input texts list."""
    provider = BGE_M3Provider()
    await provider.embed(["test text"])
    mock_flag_model.encode.assert_called_once_with(["test text"])
