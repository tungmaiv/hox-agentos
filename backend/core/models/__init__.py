"""
ORM model registry — import all models here so Alembic autogenerate detects them.

When you add a new model, add its import to this file. Alembic reads Base.metadata
(which is populated on import) to compare against the current DB schema.
"""

from core.models.agent_definition import AgentDefinition  # noqa: F401
from core.models.local_auth import LocalGroup, LocalGroupRole, LocalUser, LocalUserGroup, LocalUserRole  # noqa: F401
from core.models.artifact_permission import ArtifactPermission  # noqa: F401
from core.models.channel import ChannelAccount, ChannelSession  # noqa: F401
from core.models.conversation_title import ConversationTitle  # noqa: F401
from core.models.credentials import UserCredential  # noqa: F401
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.memory import ConversationTurn  # noqa: F401
from core.models.memory_long_term import MemoryEpisode, MemoryFact  # noqa: F401
from core.models.role_permission import RolePermission  # noqa: F401
from core.models.skill_definition import SkillDefinition  # noqa: F401
from core.models.system_config import SystemConfig  # noqa: F401
from core.models.tool_acl import ToolAcl  # noqa: F401
from core.models.tool_definition import ToolDefinition  # noqa: F401
from core.models.user_artifact_permission import UserArtifactPermission  # noqa: F401
from core.models.user_instructions import UserInstructions  # noqa: F401
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger  # noqa: F401
