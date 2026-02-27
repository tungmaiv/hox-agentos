"""
ORM model registry — import all models here so Alembic autogenerate detects them.

When you add a new model, add its import to this file. Alembic reads Base.metadata
(which is populated on import) to compare against the current DB schema.
"""

from core.models.conversation_title import ConversationTitle  # noqa: F401
from core.models.credentials import UserCredential  # noqa: F401
from core.models.mcp_server import McpServer  # noqa: F401
from core.models.memory import ConversationTurn  # noqa: F401
from core.models.memory_long_term import MemoryEpisode, MemoryFact  # noqa: F401
from core.models.system_config import SystemConfig  # noqa: F401
from core.models.tool_acl import ToolAcl  # noqa: F401
from core.models.user_instructions import UserInstructions  # noqa: F401
from core.models.workflow import Workflow, WorkflowRun, WorkflowTrigger  # noqa: F401
