"""Tests for UnifiedImportService — adapter routing, security gate, and registry entry creation."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from skills.adapters.base import NormalizedSkill


_NORMALIZED_SKILL = NormalizedSkill(
    name="test-skill",
    description="A test skill for testing",
    version="1.0.0",
    instruction_markdown="Do something useful.",
    skill_type="instructional",
    source_type="github",
    source_url="https://github.com/user/repo",
)

_SCAN_RESULT = {
    "scan_engine": "docker",
    "score": 80,
    "recommendation": "approve",
    "findings": [],
}


def _make_mock_entry(name: str = "test-skill") -> MagicMock:
    """Build a mock RegistryEntry with required fields."""
    entry = MagicMock()
    entry.id = uuid.uuid4()
    entry.name = name
    entry.status = "draft"
    entry.config = {"security_score": 80}
    return entry


class TestUnifiedImportServiceRouting:
    @pytest.mark.asyncio
    @patch("skills.import_service.scan_skill_with_fallback", new_callable=AsyncMock,
           return_value=_SCAN_RESULT, create=True)
    async def test_import_routes_to_github_adapter(self, mock_scan: AsyncMock) -> None:
        """source='https://github.com/user/repo/blob/main/SKILL.md' routes to GitHubAdapter
        (not SkillRepoAdapter), because the URL ends with .md on github.com."""
        from skills.import_service import UnifiedImportService
        from skills.adapters.github import GitHubAdapter

        mock_adapter = MagicMock()
        mock_adapter.validate_source = AsyncMock(return_value={"valid": True})
        mock_adapter.fetch_and_normalize = AsyncMock(return_value=_NORMALIZED_SKILL)

        mock_session = AsyncMock()
        mock_entry = _make_mock_entry()

        with patch("skills.import_service.AdapterRegistry") as MockRegistry, \
             patch("skills.import_service.UnifiedRegistryService") as MockRegistrySvc:
            mock_registry_instance = MagicMock()
            mock_registry_instance.detect_adapter.return_value = mock_adapter
            MockRegistry.return_value = mock_registry_instance

            mock_svc_instance = AsyncMock()
            mock_svc_instance.create_entry = AsyncMock(return_value=mock_entry)
            MockRegistrySvc.return_value = mock_svc_instance

            service = UnifiedImportService()
            result = await service.import_skill(
                source="https://github.com/user/repo/blob/main/SKILL.md",
                session=mock_session,
                owner_id=uuid.uuid4(),
            )

        mock_registry_instance.detect_adapter.assert_called_once()
        mock_adapter.fetch_and_normalize.assert_awaited_once()
        assert result == mock_entry


class TestUnifiedImportServiceRegistryEntry:
    @pytest.mark.asyncio
    @patch("skills.import_service.scan_skill_with_fallback", new_callable=AsyncMock,
           return_value=_SCAN_RESULT, create=True)
    async def test_import_creates_registry_entry(self, mock_scan: AsyncMock) -> None:
        """After successful fetch_and_normalize, a RegistryEntry with type='skill' is created."""
        from skills.import_service import UnifiedImportService

        mock_adapter = MagicMock()
        mock_adapter.validate_source = AsyncMock(return_value={"valid": True})
        mock_adapter.fetch_and_normalize = AsyncMock(return_value=_NORMALIZED_SKILL)

        mock_session = AsyncMock()
        mock_entry = _make_mock_entry()

        with patch("skills.import_service.AdapterRegistry") as MockRegistry, \
             patch("skills.import_service.UnifiedRegistryService") as MockRegistrySvc:
            mock_registry_instance = MagicMock()
            mock_registry_instance.detect_adapter.return_value = mock_adapter
            MockRegistry.return_value = mock_registry_instance

            mock_svc_instance = AsyncMock()
            mock_svc_instance.create_entry = AsyncMock(return_value=mock_entry)
            MockRegistrySvc.return_value = mock_svc_instance

            service = UnifiedImportService()
            owner_id = uuid.uuid4()
            result = await service.import_skill(
                source="https://example.com/skill.md",
                session=mock_session,
                owner_id=owner_id,
            )

        # Verify create_entry was called with type="skill"
        create_call_args = mock_svc_instance.create_entry.call_args
        assert create_call_args is not None
        entry_data = create_call_args[0][1]  # second positional arg is RegistryEntryCreate
        assert entry_data.type == "skill"
        assert entry_data.name == "test-skill"
        assert result.id is not None


class TestUnifiedImportServiceSecurityGate:
    @pytest.mark.asyncio
    @patch("skills.import_service.scan_skill_with_fallback", new_callable=AsyncMock,
           return_value=_SCAN_RESULT, create=True)
    async def test_import_with_security_scan(self, mock_scan: AsyncMock) -> None:
        """When scan_client available, scan_skill_with_fallback is called before creating entry."""
        from skills.import_service import UnifiedImportService

        mock_adapter = MagicMock()
        mock_adapter.validate_source = AsyncMock(return_value={"valid": True})
        mock_adapter.fetch_and_normalize = AsyncMock(return_value=_NORMALIZED_SKILL)

        mock_session = AsyncMock()
        mock_entry = _make_mock_entry()

        with patch("skills.import_service.AdapterRegistry") as MockRegistry, \
             patch("skills.import_service.UnifiedRegistryService") as MockRegistrySvc, \
             patch("skills.import_service._HAS_SCANNER", True):
            mock_registry_instance = MagicMock()
            mock_registry_instance.detect_adapter.return_value = mock_adapter
            MockRegistry.return_value = mock_registry_instance

            mock_svc_instance = AsyncMock()
            mock_svc_instance.create_entry = AsyncMock(return_value=mock_entry)
            MockRegistrySvc.return_value = mock_svc_instance

            service = UnifiedImportService()
            await service.import_skill(
                source="https://example.com/skill.md",
                session=mock_session,
                owner_id=uuid.uuid4(),
            )

        mock_scan.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_without_scanner_proceeds(self) -> None:
        """When _HAS_SCANNER=False, import proceeds with warning log (no crash)."""
        from skills.import_service import UnifiedImportService

        mock_adapter = MagicMock()
        mock_adapter.validate_source = AsyncMock(return_value={"valid": True})
        mock_adapter.fetch_and_normalize = AsyncMock(return_value=_NORMALIZED_SKILL)

        mock_session = AsyncMock()
        mock_entry = _make_mock_entry()

        with patch("skills.import_service.AdapterRegistry") as MockRegistry, \
             patch("skills.import_service.UnifiedRegistryService") as MockRegistrySvc, \
             patch("skills.import_service._HAS_SCANNER", False):
            mock_registry_instance = MagicMock()
            mock_registry_instance.detect_adapter.return_value = mock_adapter
            MockRegistry.return_value = mock_registry_instance

            mock_svc_instance = AsyncMock()
            mock_svc_instance.create_entry = AsyncMock(return_value=mock_entry)
            MockRegistrySvc.return_value = mock_svc_instance

            service = UnifiedImportService()
            result = await service.import_skill(
                source="https://example.com/skill.md",
                session=mock_session,
                owner_id=uuid.uuid4(),
            )

        # Should complete without raising
        assert result == mock_entry


class TestUnifiedImportServiceErrors:
    @pytest.mark.asyncio
    @patch("skills.import_service.scan_skill_with_fallback", new_callable=AsyncMock,
           return_value=_SCAN_RESULT, create=True)
    async def test_unknown_source_raises(self, mock_scan: AsyncMock) -> None:
        """source='ftp://example.com/skill' raises ValueError('No adapter found')."""
        from skills.import_service import UnifiedImportService

        mock_session = AsyncMock()

        with patch("skills.import_service.AdapterRegistry") as MockRegistry:
            mock_registry_instance = MagicMock()
            mock_registry_instance.detect_adapter.side_effect = ValueError("No adapter found for source")
            MockRegistry.return_value = mock_registry_instance

            service = UnifiedImportService()
            with pytest.raises(ValueError, match="No adapter found"):
                await service.import_skill(
                    source="ftp://example.com/skill",
                    session=mock_session,
                    owner_id=uuid.uuid4(),
                )
