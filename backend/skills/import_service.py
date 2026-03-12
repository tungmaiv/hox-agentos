"""
UnifiedImportService: route skill imports through adapters with security gate.

Import pipeline:
1. Detect adapter via AdapterRegistry.detect_adapter(source)
2. Validate source reachability (adapter.validate_source)
3. Fetch and normalize skill content (adapter.fetch_and_normalize → NormalizedSkill)
4. Run security scan if scan_client available (scan_skill_with_fallback)
5. Create registry entry via UnifiedRegistryService.create_entry
6. Return RegistryEntry

The security scanner (24-05) is imported conditionally — if it doesn't exist yet,
_HAS_SCANNER is False and the scan step is skipped with a warning log.
"""
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.registry import RegistryEntryCreate
from registry.models import RegistryEntry
from registry.service import UnifiedRegistryService
from skills.adapters.base import NormalizedSkill
from skills.adapters.registry import AdapterRegistry

# Conditional import of security scanner (plan 24-05 may not exist yet in wave 2)
try:
    from security.scan_client import scan_skill_with_fallback  # type: ignore[import-not-found]
    _HAS_SCANNER = True
except ImportError:
    _HAS_SCANNER = False

logger = structlog.get_logger(__name__)


class UnifiedImportService:
    """Service that routes skill imports through the appropriate adapter.

    Wraps the full import pipeline:
    detect adapter → validate → fetch → scan → create registry entry.
    """

    def __init__(self) -> None:
        self._adapter_registry = AdapterRegistry()
        self._registry_service = UnifiedRegistryService()

    async def import_skill(
        self,
        source: str,
        session: AsyncSession,
        owner_id: UUID,
    ) -> RegistryEntry:
        """Import a skill from an external source.

        Args:
            source: URL, URI, or identifier for the skill source.
            session: Async SQLAlchemy session for DB operations.
            owner_id: UUID of the importing user (from JWT).

        Returns:
            Created RegistryEntry with type='skill'.

        Raises:
            ValueError: If no adapter can handle the source, or source is invalid.
        """
        # 1. Detect adapter
        adapter = self._adapter_registry.detect_adapter(source)
        logger.info(
            "skill_import_start",
            source=source,
            adapter=type(adapter).__name__,
        )

        # 2. Validate source
        validation = await adapter.validate_source(source)
        if not validation.get("valid", True):
            raise ValueError(
                f"Invalid skill source: {validation.get('reason', 'unknown')}"
            )

        # 3. Fetch and normalize
        normalized: NormalizedSkill = await adapter.fetch_and_normalize(source)

        # 4. Security gate
        scan_result: dict = {}
        if _HAS_SCANNER:
            skill_data = {
                "name": normalized.name,
                "scripts": normalized.instruction_markdown or "",
                "procedure_json": normalized.procedure_json,
            }
            scan_result = await scan_skill_with_fallback(skill_data, None)
            logger.info(
                "skill_import_scanned",
                name=normalized.name,
                score=scan_result.get("score"),
                recommendation=scan_result.get("recommendation"),
            )
        else:
            logger.warning(
                "security_scan_skipped",
                reason="scan_client not available",
                skill=normalized.name,
            )

        # 5. Create registry entry
        config = {
            "skill_type": normalized.skill_type,
            "instruction_markdown": normalized.instruction_markdown,
            "procedure_json": normalized.procedure_json,
            "allowed_tools": normalized.allowed_tools,
            "tags": normalized.tags,
            "category": normalized.category,
            "source_url": normalized.source_url or source,
            "source_type": normalized.source_type,
            "author": normalized.author,
            "license": normalized.license,
            "version": normalized.version,
            "security_score": scan_result.get("score"),
            "security_report": scan_result or None,
            "scan_engine": scan_result.get("scan_engine", "none"),
        }
        entry_data = RegistryEntryCreate(
            type="skill",
            name=normalized.name,
            display_name=normalized.name,
            description=normalized.description,
            config=config,
            status="draft",
        )
        entry = await self._registry_service.create_entry(
            session,
            entry_data,
            owner_id=owner_id,
        )
        logger.info(
            "skill_import_complete",
            name=normalized.name,
            entry_id=str(entry.id),
        )
        return entry
