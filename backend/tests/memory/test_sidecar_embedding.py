"""Tests for SidecarEmbeddingProvider."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from memory.embeddings import SidecarEmbeddingProvider


@pytest.mark.asyncio
async def test_embed_calls_sidecar():
    """SidecarEmbeddingProvider calls the sidecar /embeddings endpoint."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"embedding": [0.1] * 1024, "index": 0}
        ]
    }

    with patch("memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        provider = SidecarEmbeddingProvider(sidecar_url="http://test-sidecar:7997")
        result = await provider.embed(["hello world"])

    assert len(result) == 1
    assert len(result[0]) == 1024
    mock_client.post.assert_called_once_with(
        "http://test-sidecar:7997/embeddings",
        json={"input": ["hello world"], "model": "BAAI/bge-m3"},
        timeout=30.0,
    )


@pytest.mark.asyncio
async def test_embed_falls_back_on_connect_error():
    """Falls back to BGE_M3Provider when sidecar is unreachable."""
    fallback_mock = AsyncMock(return_value=[[0.5] * 1024])

    with patch("memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client_cls.return_value = mock_client

        with patch("memory.embeddings.BGE_M3Provider") as MockBGE:
            instance = AsyncMock()
            instance.embed = fallback_mock
            MockBGE.return_value = instance

            provider = SidecarEmbeddingProvider(sidecar_url="http://test-sidecar:7997")
            result = await provider.embed(["hello"])

    assert result == [[0.5] * 1024]
    fallback_mock.assert_called_once_with(["hello"])


@pytest.mark.asyncio
async def test_validate_dimension_mismatch_raises():
    """validate_dimension() raises RuntimeError when sidecar returns wrong dim."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"model": "BAAI/bge-m3", "dimensions": 768}

    with patch("memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        provider = SidecarEmbeddingProvider(sidecar_url="http://test-sidecar:7997")
        with pytest.raises(RuntimeError, match="dimension mismatch"):
            await provider.validate_dimension()


@pytest.mark.asyncio
async def test_validate_dimension_ok():
    """validate_dimension() succeeds when sidecar reports 1024."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"model": "BAAI/bge-m3", "dimensions": 1024}

    with patch("memory.embeddings.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        provider = SidecarEmbeddingProvider(sidecar_url="http://test-sidecar:7997")
        await provider.validate_dimension()  # Must not raise
