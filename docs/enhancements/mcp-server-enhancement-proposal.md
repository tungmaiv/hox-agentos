# MCP Server Management Enhancement Proposal

## Problem Statement

The current MCP implementation only supports **built-in Docker-based servers** with HTTP+SSE transport. It cannot handle:

1. **Public MCP servers** requiring CLI installation (Context7, NotebookLM)
2. **Stdio-based transport** (most public MCP servers use this)
3. **Environment variable configuration** for API keys
4. **On-demand process spawning** for CLI servers
5. **Installation status tracking**

## Proposed Solution: 3-Tier MCP Architecture

### Tier 1: Built-in Servers (Current)
Docker-based, always-on, HTTP+SSE transport

### Tier 2: Public Servers (New)
CLI-installed, stdio transport, on-demand spawning

### Tier 3: OpenAPI Bridge (Current)
REST API wrapper, HTTP proxy

---

## 1. Enhanced Database Schema

### Modified Table: `mcp_servers`

```sql
-- Add new columns to existing mcp_servers table
ALTER TABLE mcp_servers ADD COLUMN server_type VARCHAR(20) NOT NULL DEFAULT 'builtin'
    CHECK (server_type IN ('builtin', 'public', 'openapi_bridge'));

ALTER TABLE mcp_servers ADD COLUMN transport VARCHAR(20) NOT NULL DEFAULT 'http'
    CHECK (transport IN ('http', 'stdio', 'websocket'));

ALTER TABLE mcp_servers ADD COLUMN installation_source VARCHAR(50);
-- Examples: 'npm:@upstash/context7-mcp', 'pip:mcp-server-fetch', 'docker:context7-mcp'

ALTER TABLE mcp_servers ADD COLUMN installation_status VARCHAR(20) DEFAULT 'not_installed'
    CHECK (installation_status IN ('not_installed', 'installing', 'installed', 'error'));

ALTER TABLE mcp_servers ADD COLUMN installation_error TEXT;

ALTER TABLE mcp_servers ADD COLUMN env_vars JSONB DEFAULT '{}';
-- Example: {"UPSTASH_REDIS_REST_URL": "https://...", "API_KEY": "{{credentials.upstash.api_key}}"}

ALTER TABLE mcp_servers ADD COLUMN docs_url TEXT;
-- Link to official documentation

ALTER TABLE mcp_servers ADD COLUMN process_id VARCHAR(100);
-- For stdio servers: stores subprocess PID or container ID

ALTER TABLE mcp_servers ADD COLUMN last_heartbeat_at TIMESTAMP;
-- For health checking stdio processes

-- Add indexes
CREATE INDEX idx_mcp_servers_type ON mcp_servers(server_type);
CREATE INDEX idx_mcp_servers_transport ON mcp_servers(transport);
CREATE INDEX idx_mcp_servers_install_status ON mcp_servers(installation_status);
```

### New Table: `mcp_server_catalog`

Curated registry of public MCP servers that can be auto-installed.

```sql
CREATE TABLE mcp_server_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200),
    description TEXT,
    publisher VARCHAR(100),  -- e.g., "Upstash", "ModelContextProtocol"
    
    -- Installation info
    package_source VARCHAR(50) NOT NULL,
    -- Format: "npm:package-name", "pip:package-name", "docker:image-name"
    
    install_command VARCHAR(500),
    -- Example: "npx -y @upstash/context7-mcp@latest"
    
    -- Configuration schema
    required_env_vars JSONB DEFAULT '[]',
    -- Example: ["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"]
    
    optional_env_vars JSONB DEFAULT '[]',
    
    config_schema JSONB,
    -- JSON Schema for additional configuration
    
    -- Metadata
    version VARCHAR(20),
    docs_url TEXT,
    repository_url TEXT,
    license VARCHAR(50),
    
    -- Curation
    category VARCHAR(50),
    tags JSONB DEFAULT '[]',
    is_featured BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE,
    
    -- Stats
    install_count INTEGER DEFAULT 0,
    rating DECIMAL(2,1),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Popular public MCP servers to pre-populate
INSERT INTO mcp_server_catalog (name, display_name, description, publisher, package_source, install_command, required_env_vars, category, tags, is_featured) VALUES
('context7', 'Context7', 'Upstash Context7 MCP server for vector search', 'Upstash', 'npm:@upstash/context7-mcp', 'npx -y @upstash/context7-mcp@latest', '["UPSTASH_REDIS_REST_URL", "UPSTASH_REDIS_REST_TOKEN"]', 'database', '["vector", "redis", "search"]', TRUE),

('fetch', 'Fetch', 'Web content fetching and processing', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-fetch', 'npx -y @modelcontextprotocol/server-fetch', '[]', 'web', '["http", "scraping"]', TRUE),

('filesystem', 'Filesystem', 'Secure file system operations', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-filesystem', 'npx -y @modelcontextprotocol/server-filesystem', '[]', 'storage', '["files", "fs"]', TRUE),

('postgres', 'PostgreSQL', 'PostgreSQL database operations', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-postgres', 'npx -y @modelcontextprotocol/server-postgres', '["POSTGRES_CONNECTION_STRING"]', 'database', '["sql", "postgres"]', TRUE),

('github', 'GitHub', 'GitHub API integration', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-github', 'npx -y @modelcontextprotocol/server-github', '["GITHUB_PERSONAL_ACCESS_TOKEN"]', 'devops', '["git", "api"]', TRUE),

('slack', 'Slack', 'Slack workspace integration', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-slack', 'npx -y @modelcontextprotocol/server-slack', '["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"]', 'communication', '["chat", "messaging"]', FALSE),

('google-drive', 'Google Drive', 'Google Drive file operations', 'ModelContextProtocol', 'npm:@modelcontextprotocol/server-gdrive', 'npx -y @modelcontextprotocol/server-gdrive', '["GDRIVE_CREDENTIALS_PATH"]', 'storage', '["cloud", "google"]', FALSE),

('notebooklm', 'NotebookLM', 'NotebookLM integration for podcast generation', 'Community', 'npm:@modelcontextprotocol/server-notebooklm', 'npx -y @modelcontextprotocol/server-notebooklm', '["NOTEBOOKLM_API_KEY"]', 'ai', '["google", "audio"]', TRUE);
```

---

## 2. Enhanced Backend Architecture

### 2.1 MCP Server Types

**`backend/mcp/types.py`**
```python
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class ServerType(str, Enum):
    BUILTIN = "builtin"           # Docker-based, always-on
    PUBLIC = "public"             # CLI-installed, on-demand
    OPENAPI_BRIDGE = "openapi_bridge"  # REST API wrapper

class TransportType(str, Enum):
    HTTP = "http"                 # HTTP+SSE (current)
    STDIO = "stdio"               # stdin/stdout subprocess
    WEBSOCKET = "websocket"       # Future: WebSocket transport

class InstallationStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    INSTALLED = "installed"
    ERROR = "error"

class PackageSource(BaseModel):
    """Parsed package source like npm:@scope/package or pip:package-name"""
    manager: str  # npm, pip, docker
    package: str
    version: Optional[str] = None
    
    @classmethod
    def parse(cls, source: str) -> "PackageSource":
        if ":" not in source:
            raise ValueError(f"Invalid package source: {source}")
        manager, package = source.split(":", 1)
        if "@" in package:
            package, version = package.rsplit("@", 1)
        else:
            version = None
        return cls(manager=manager, package=package, version=version)
    
    def install_command(self) -> str:
        if self.manager == "npm":
            cmd = f"npx -y {self.package}"
            if self.version:
                cmd += f"@{self.version}"
            return cmd
        elif self.manager == "pip":
            cmd = f"pip install {self.package}"
            if self.version:
                cmd += f"=={self.version}"
            return cmd
        elif self.manager == "docker":
            return f"docker pull {self.package}"
        else:
            raise ValueError(f"Unknown package manager: {self.manager}")
```

### 2.2 MCP Client Factory

**`backend/mcp/client_factory.py`**
```python
from typing import Optional
from core.models.mcp_server import McpServer
from mcp.client import MCPClient
from mcp.stdio_client import StdioMCPClient

class MCPClientFactory:
    """Factory for creating appropriate MCP client based on transport."""
    
    @staticmethod
    async def create_client(server: McpServer) -> MCPClient:
        """Create client based on server configuration."""
        if server.transport == "http":
            return await MCPClientFactory._create_http_client(server)
        elif server.transport == "stdio":
            return await MCPClientFactory._create_stdio_client(server)
        else:
            raise ValueError(f"Unsupported transport: {server.transport}")
    
    @staticmethod
    async def _create_http_client(server: McpServer) -> MCPClient:
        """Create HTTP+SSE client (existing implementation)."""
        from mcp.client import MCPClient
        auth_token = decrypt_auth_token(server.auth_token) if server.auth_token else None
        return MCPClient(server_url=server.url, auth_token=auth_token)
    
    @staticmethod
    async def _create_stdio_client(server: McpServer) -> "StdioMCPClient":
        """Create stdio subprocess client (new)."""
        from mcp.stdio_client import StdioMCPClient
        
        # Ensure server is installed
        if server.installation_status != "installed":
            raise RuntimeError(f"Server {server.name} is not installed")
        
        # Parse installation source to get command
        from mcp.types import PackageSource
        package = PackageSource.parse(server.installation_source)
        command = package.install_command()
        
        # Resolve environment variables
        env_vars = await resolve_env_vars(server.env_vars or {}, server.owner_id)
        
        return StdioMCPClient(
            command=command,
            env_vars=env_vars,
            server_name=server.name
        )

async def resolve_env_vars(env_vars: Dict[str, str], owner_id: str) -> Dict[str, str]:
    """Resolve environment variables, including credential references.
    
    Supports template syntax:
    - "{{credentials.provider.key}}" - Lookup in user's credentials store
    - Plain values - Used as-is
    """
    resolved = {}
    for key, value in env_vars.items():
        if value.startswith("{{") and value.endswith("}}"):
            # Extract credential path: credentials.provider.key
            path = value[2:-2].strip()
            parts = path.split(".")
            if len(parts) == 3 and parts[0] == "credentials":
                provider = parts[1]
                credential_key = parts[2]
                # Fetch from user's credential store
                credential = await get_user_credential(owner_id, provider, credential_key)
                resolved[key] = credential
            else:
                raise ValueError(f"Invalid credential reference: {value}")
        else:
            resolved[key] = value
    return resolved
```

### 2.3 Stdio MCP Client (New)

**`backend/mcp/stdio_client.py`**
```python
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

class StdioMCPClient:
    """MCP client that communicates with a subprocess via stdin/stdout.
    
    This is the standard transport for public MCP servers installed via CLI.
    """
    
    def __init__(self, command: str, env_vars: Dict[str, str], server_name: str):
        self.command = command
        self.env_vars = env_vars
        self.server_name = server_name
        self.process: Optional[asyncio.subprocess.Process] = None
        self._request_id = 0
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._read_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def ensure_running(self):
        """Start the subprocess if not already running."""
        async with self._lock:
            if self.process is None or self.process.returncode is not None:
                await self._start_process()
    
    async def _start_process(self):
        """Start the MCP server subprocess."""
        logger.info(f"Starting MCP server: {self.server_name}")
        
        # Merge with existing environment
        env = {**os.environ, **self.env_vars}
        
        # Parse command (handle npx, pip, etc.)
        if self.command.startswith("npx "):
            # npx needs shell=True to work properly
            self.process = await asyncio.create_subprocess_shell(
                self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
        else:
            cmd_parts = self.command.split()
            self.process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
        
        # Start reading stdout
        self._read_task = asyncio.create_task(self._read_loop())
        
        # Wait a moment for server to initialize
        await asyncio.sleep(0.5)
        
        logger.info(f"MCP server {self.server_name} started with PID {self.process.pid}")
    
    async def _read_loop(self):
        """Continuously read JSON-RPC messages from stdout."""
        while self.process and self.process.returncode is None:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                message = json.loads(line.decode('utf-8'))
                await self._handle_message(message)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from {self.server_name}: {e}")
            except Exception as e:
                logger.error(f"Error reading from {self.server_name}: {e}")
                break
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle incoming JSON-RPC message."""
        if "id" in message and message["id"] in self._pending_requests:
            future = self._pending_requests.pop(message["id"])
            if "error" in message:
                future.set_exception(RuntimeError(message["error"]))
            else:
                future.set_result(message.get("result"))
    
    async def list_tools(self) -> list[Dict[str, Any]]:
        """List available tools from the MCP server."""
        await self.ensure_running()
        
        result = await self._send_request("tools/list", {})
        return result.get("tools", [])
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        await self.ensure_running()
        
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        return result
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Send JSON-RPC request and wait for response."""
        self._request_id += 1
        request_id = str(self._request_id)
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future
        
        # Send request
        message = json.dumps(request) + "\n"
        self.process.stdin.write(message.encode('utf-8'))
        await self.process.stdin.drain()
        
        # Wait for response with timeout
        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"Request to {self.server_name} timed out")
    
    async def health_check(self) -> bool:
        """Check if the subprocess is healthy."""
        if self.process is None:
            return False
        if self.process.returncode is not None:
            return False
        
        # Try to list tools as health check
        try:
            await asyncio.wait_for(self.list_tools(), timeout=5.0)
            return True
        except:
            return False
    
    async def stop(self):
        """Stop the subprocess."""
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
```

### 2.4 Installation Manager

**`backend/mcp/installer.py`**
```python
import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.models.mcp_server import McpServer
from mcp.types import PackageSource

logger = logging.getLogger(__name__)

class MCPInstaller:
    """Manages installation of public MCP servers."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def install(self, server_id: str) -> McpServer:
        """Install a public MCP server.
        
        Flow:
        1. Validate server is public type
        2. Check if already installed
        3. Run installation command
        4. Verify installation (try to run --help or similar)
        5. Update status to installed
        """
        from core.models.mcp_server import McpServer
        
        result = await self.session.execute(
            select(McpServer).where(McpServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        
        if not server:
            raise ValueError(f"Server {server_id} not found")
        
        if server.server_type != "public":
            raise ValueError(f"Server {server.name} is not a public server")
        
        if server.installation_status == "installed":
            logger.info(f"Server {server.name} is already installed")
            return server
        
        # Update status to installing
        server.installation_status = "installing"
        await self.session.flush()
        
        try:
            # Parse package source
            package = PackageSource.parse(server.installation_source)
            
            # Run installation
            if package.manager == "npm":
                await self._install_npm(package)
            elif package.manager == "pip":
                await self._install_pip(package)
            elif package.manager == "docker":
                await self._install_docker(package)
            else:
                raise ValueError(f"Unknown package manager: {package.manager}")
            
            # Verify installation
            if await self._verify_installation(package):
                server.installation_status = "installed"
                server.installation_error = None
                logger.info(f"Successfully installed {server.name}")
            else:
                raise RuntimeError("Installation verification failed")
                
        except Exception as e:
            server.installation_status = "error"
            server.installation_error = str(e)
            logger.error(f"Failed to install {server.name}: {e}")
            raise
        
        await self.session.flush()
        return server
    
    async def _install_npm(self, package: PackageSource):
        """Install npm package globally."""
        cmd = f"npm install -g {package.package}"
        if package.version:
            cmd += f"@{package.version}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"npm install failed: {stderr.decode()}")
    
    async def _install_pip(self, package: PackageSource):
        """Install pip package."""
        cmd = f"pip install {package.package}"
        if package.version:
            cmd += f"=={package.version}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"pip install failed: {stderr.decode()}")
    
    async def _install_docker(self, package: PackageSource):
        """Pull Docker image."""
        cmd = f"docker pull {package.package}"
        if package.version:
            cmd += f":{package.version}"
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise RuntimeError(f"docker pull failed: {stderr.decode()}")
    
    async def _verify_installation(self, package: PackageSource) -> bool:
        """Verify that the package was installed correctly."""
        try:
            if package.manager == "npm":
                # Try to run the package with --version
                cmd = f"npx {package.package} --version"
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(process.communicate(), timeout=10.0)
                return process.returncode == 0
            elif package.manager == "pip":
                # Check if module can be imported
                cmd = f"python -c 'import {package.package.replace('-', '_')}'"
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await asyncio.wait_for(process.communicate(), timeout=10.0)
                return process.returncode == 0
            elif package.manager == "docker":
                # Check if image exists
                cmd = f"docker images -q {package.package}"
                process = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await process.communicate()
                return len(stdout.decode().strip()) > 0
            return False
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False
    
    async def uninstall(self, server_id: str) -> McpServer:
        """Uninstall a public MCP server."""
        result = await self.session.execute(
            select(McpServer).where(McpServer.id == server_id)
        )
        server = result.scalar_one_or_none()
        
        if not server or server.server_type != "public":
            raise ValueError("Server not found or not a public server")
        
        # Stop any running process
        # TODO: Implement process management
        
        # Update status
        server.installation_status = "not_installed"
        await self.session.flush()
        
        return server
```

### 2.5 Enhanced API Routes

**`backend/api/routes/mcp_servers.py`** (Additions)

```python
# New endpoints for public MCP server management

@router.get("/catalog", response_model=List[MCPServerCatalogEntry])
async def list_catalog(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    session: AsyncSession = Depends(get_session)
):
    """List available public MCP servers from catalog."""
    query = select(McpServerCatalog)
    
    if category:
        query = query.where(McpServerCatalog.category == category)
    if featured_only:
        query = query.where(McpServerCatalog.is_featured == True)
    if search:
        query = query.where(
            or_(
                McpServerCatalog.name.ilike(f"%{search}%"),
                McpServerCatalog.description.ilike(f"%{search}%")
            )
        )
    
    query = query.order_by(McpServerCatalog.install_count.desc())
    
    result = await session.execute(query)
    return result.scalars().all()

@router.post("/catalog/{catalog_id}/install", response_model=McpServerResponse)
async def install_from_catalog(
    catalog_id: str,
    config: PublicServerConfig,
    current_user: UserContext = Depends(require_permission("mcp:install")),
    session: AsyncSession = Depends(get_session)
):
    """Install a public MCP server from catalog.
    
    Flow:
    1. Get catalog entry
    2. Create McpServer row
    3. Install the package
    4. Return server details
    """
    # Get catalog entry
    result = await session.execute(
        select(McpServerCatalog).where(McpServerCatalog.id == catalog_id)
    )
    catalog = result.scalar_one_or_none()
    
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog entry not found")
    
    # Check if already installed
    existing = await session.execute(
        select(McpServer).where(
            and_(
                McpServer.name == catalog.name,
                McpServer.owner_id == current_user.user_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Server already installed")
    
    # Create server entry
    server = McpServer(
        name=catalog.name,
        display_name=config.display_name or catalog.display_name,
        description=catalog.description,
        server_type="public",
        transport="stdio",
        installation_source=catalog.package_source,
        installation_status="not_installed",
        env_vars=config.env_vars,
        docs_url=catalog.docs_url,
        owner_id=current_user.user_id,
        status="disabled"  # Start disabled until installation completes
    )
    
    session.add(server)
    await session.flush()
    
    # Install in background (or synchronously for now)
    installer = MCPInstaller(session)
    try:
        await installer.install(str(server.id))
        server.status = "active"
        await session.flush()
        
        # Increment install count
        catalog.install_count += 1
        await session.flush()
        
    except Exception as e:
        # Installation failed, but entry created
        logger.error(f"Installation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")
    
    return McpServerResponse.from_orm(server)

@router.post("/{server_id}/install", response_model=McpServerResponse)
async def install_server(
    server_id: str,
    current_user: UserContext = Depends(require_permission("mcp:install")),
    session: AsyncSession = Depends(get_session)
):
    """Install or reinstall a public MCP server."""
    result = await session.execute(
        select(McpServer).where(
            and_(
                McpServer.id == server_id,
                McpServer.owner_id == current_user.user_id
            )
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    if server.server_type != "public":
        raise HTTPException(status_code=400, detail="Not a public server")
    
    installer = MCPInstaller(session)
    try:
        await installer.install(server_id)
        return McpServerResponse.from_orm(server)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{server_id}/logs")
async def get_server_logs(
    server_id: str,
    lines: int = Query(100, ge=1, le=1000),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get logs from a stdio-based MCP server."""
    # TODO: Implement log aggregation for subprocesses
    # This would require capturing stderr from StdioMCPClient
    pass
```

---

## 3. Frontend Implementation

### 3.1 Types

**`frontend/lib/mcp-types.ts`**
```typescript
export type ServerType = 'builtin' | 'public' | 'openapi_bridge';
export type TransportType = 'http' | 'stdio' | 'websocket';
export type InstallationStatus = 'not_installed' | 'installing' | 'installed' | 'error';

export interface McpServer {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  server_type: ServerType;
  transport: TransportType;
  url?: string;
  installation_source?: string;
  installation_status: InstallationStatus;
  installation_error?: string;
  env_vars: Record<string, string>;
  docs_url?: string;
  status: 'active' | 'disabled' | 'deprecated';
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface McpServerCatalogEntry {
  id: string;
  name: string;
  display_name: string;
  description: string;
  publisher: string;
  package_source: string;
  install_command: string;
  required_env_vars: string[];
  optional_env_vars: string[];
  version: string;
  docs_url: string;
  category: string;
  tags: string[];
  is_featured: boolean;
  is_verified: boolean;
  install_count: number;
  rating?: number;
}

export interface InstallPublicServerRequest {
  display_name?: string;
  env_vars: Record<string, string>;
}
```

### 3.2 Catalog Browser Component

**`frontend/components/mcp/catalog-browser.tsx`**
```typescript
'use client';

import { useState, useEffect } from 'react';
import { McpServerCatalogEntry } from '@/lib/mcp-types';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { InstallServerDialog } from './install-server-dialog';

export function CatalogBrowser() {
  const [catalog, setCatalog] = useState<McpServerCatalogEntry[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [installing, setInstalling] = useState<McpServerCatalogEntry | null>(null);

  useEffect(() => {
    fetchCatalog();
  }, []);

  const fetchCatalog = async () => {
    const res = await fetch('/api/mcp/catalog?featured_only=false');
    const data = await res.json();
    setCatalog(data);
  };

  const categories = Array.from(new Set(catalog.map(c => c.category)));

  const filtered = catalog.filter(entry => {
    const matchesSearch = !search || 
      entry.name.toLowerCase().includes(search.toLowerCase()) ||
      entry.description.toLowerCase().includes(search.toLowerCase());
    const matchesCategory = !selectedCategory || entry.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  return (
    <div className="space-y-6">
      <div className="flex gap-4">
        <Input
          placeholder="Search MCP servers..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-md"
        />
        <select
          value={selectedCategory || ''}
          onChange={(e) => setSelectedCategory(e.target.value || null)}
          className="border rounded px-3"
        >
          <option value="">All Categories</option>
          {categories.map(cat => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(entry => (
          <Card key={entry.id} className={entry.is_featured ? 'border-primary' : ''}>
            <CardHeader>
              <div className="flex justify-between items-start">
                <CardTitle className="text-lg">{entry.display_name}</CardTitle>
                {entry.is_featured && <Badge>Featured</Badge>}
              </div>
              <CardDescription>{entry.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex gap-2 flex-wrap">
                  {entry.tags.map(tag => (
                    <Badge key={tag} variant="secondary">{tag}</Badge>
                  ))}
                </div>
                <div className="text-sm text-muted-foreground">
                  By {entry.publisher} • {entry.install_count} installs
                </div>
                <div className="text-xs text-muted-foreground">
                  <code>{entry.install_command}</code>
                </div>
                <div className="flex gap-2 pt-2">
                  <Button 
                    size="sm" 
                    onClick={() => setInstalling(entry)}
                  >
                    Install
                  </Button>
                  <Button size="sm" variant="outline" asChild>
                    <a href={entry.docs_url} target="_blank" rel="noopener">Docs</a>
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {installing && (
        <InstallServerDialog
          catalogEntry={installing}
          open={!!installing}
          onClose={() => setInstalling(null)}
        />
      )}
    </div>
  );
}
```

### 3.3 Install Dialog with Env Vars

**`frontend/components/mcp/install-server-dialog.tsx`**
```typescript
'use client';

import { useState } from 'react';
import { McpServerCatalogEntry } from '@/lib/mcp-types';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';

interface InstallServerDialogProps {
  catalogEntry: McpServerCatalogEntry;
  open: boolean;
  onClose: () => void;
}

export function InstallServerDialog({ catalogEntry, open, onClose }: InstallServerDialogProps) {
  const [displayName, setDisplayName] = useState(catalogEntry.display_name);
  const [envVars, setEnvVars] = useState<Record<string, string>>({});
  const [installing, setInstalling] = useState(false);
  const { toast } = useToast();

  const handleInstall = async () => {
    setInstalling(true);
    try {
      const res = await fetch(`/api/mcp/catalog/${catalogEntry.id}/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: displayName,
          env_vars: envVars
        })
      });

      if (!res.ok) {
        const error = await res.text();
        throw new Error(error);
      }

      toast({ title: `${catalogEntry.display_name} installed successfully` });
      onClose();
    } catch (e) {
      toast({ 
        title: 'Installation failed', 
        description: e instanceof Error ? e.message : 'Unknown error',
        variant: 'destructive'
      });
    } finally {
      setInstalling(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Install {catalogEntry.display_name}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Display Name</Label>
            <Input 
              value={displayName} 
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>

          {catalogEntry.required_env_vars.length > 0 && (
            <div className="space-y-3">
              <Label>Required Configuration</Label>
              {catalogEntry.required_env_vars.map((envVar) => (
                <div key={envVar} className="space-y-1">
                  <Label className="text-sm">{envVar}</Label>
                  <Input
                    type="password"
                    placeholder={`Enter ${envVar}`}
                    value={envVars[envVar] || ''}
                    onChange={(e) => setEnvVars(prev => ({
                      ...prev,
                      [envVar]: e.target.value
                    }))}
                  />
                </div>
              ))}
            </div>
          )}

          <Alert>
            <AlertDescription>
              This will run: <code>{catalogEntry.install_command}</code>
            </AlertDescription>
          </Alert>

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button 
              onClick={handleInstall} 
              disabled={installing || catalogEntry.required_env_vars.some(v => !envVars[v])}
            >
              {installing ? 'Installing...' : 'Install'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## 4. User Flow Examples

### Flow 1: Install Context7 from Catalog

1. User goes to **Admin → Registry → MCP Catalog**
2. Sees Context7 card with "Install" button
3. Clicks Install, dialog shows:
   - Display name input (default: "Context7")
   - Required fields: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
   - User fills in their Upstash credentials
4. Clicks "Install"
5. Backend runs: `npx -y @upstash/context7-mcp@latest`
6. Server appears in **My MCP Servers** list
7. Tools are auto-discovered and available

### Flow 2: Create Custom MCP from OpenAPI

1. User goes to **Admin → Registry → MCP Servers → Create**
2. Selects "OpenAPI Bridge" type
3. Uploads/pastes OpenAPI spec URL
4. System generates MCP server wrapper
5. User tests endpoints
6. Saves → Server registered as `openapi_bridge` type

### Flow 3: Built-in Docker Server

1. DevOps adds to docker-compose.yml
2. Server starts with system
3. Admin registers in UI with URL: `http://mcp-crm:8001`
4. Tools auto-discovered
5. No installation needed

---

## 5. Migration Strategy

### Phase 1: Schema Updates (1 day)
1. Add columns to `mcp_servers` table
2. Create `mcp_server_catalog` table
3. Populate catalog with popular servers

### Phase 2: Backend Implementation (3 days)
1. Implement stdio transport client
2. Create installation manager
3. Add catalog API endpoints
4. Update registry to support new types

### Phase 3: Frontend Implementation (2 days)
1. Build catalog browser
2. Create install dialog with env var support
3. Update server list to show installation status
4. Add type badges

### Phase 4: Testing & Documentation (1 day)
1. Test installation of Context7, Fetch, Filesystem
2. Document common issues
3. Create admin guide

---

## 6. Benefits

| Feature | Before | After |
|---------|--------|-------|
| **Public MCP Support** | ❌ Not possible | ✅ Full support |
| **CLI Installation** | ❌ Manual only | ✅ Auto-install from catalog |
| **Stdio Transport** | ❌ HTTP only | ✅ HTTP + stdio |
| **Env Var Config** | ❌ Hardcoded | ✅ Dynamic + credentials integration |
| **Server Curation** | ❌ None | ✅ Featured + verified badges |
| **One-click Install** | ❌ 5+ manual steps | ✅ Single button |

---

## 7. Security Considerations

1. **Sandboxing**: Public MCP servers run in subprocess, isolated from main app
2. **Credential Injection**: Use template syntax `{{credentials.provider.key}}` to inject secrets
3. **Network Isolation**: Stdio servers can't make network calls unless explicitly allowed
4. **Installation Verification**: Verify package signatures or checksums where available
5. **Rate Limiting**: Limit installation attempts per user

---

## 8. Files to Create/Modify

### New Files
```
backend/mcp/
  ├── types.py
  ├── client_factory.py
  ├── stdio_client.py
  └── installer.py

backend/core/models/mcp_server_catalog.py

frontend/components/mcp/
  ├── catalog-browser.tsx
  ├── install-server-dialog.tsx
  └── server-type-badge.tsx

frontend/lib/mcp-types.ts
```

### Modified Files
```
backend/core/models/mcp_server.py (add columns)
backend/mcp/client.py (refactor to use factory)
backend/mcp/registry.py (support stdio clients)
backend/api/routes/mcp_servers.py (add catalog endpoints)

frontend/app/(authenticated)/admin/registry/mcp-servers/page.tsx (add catalog tab)
```

---

## 9. Success Criteria

- [ ] Can browse catalog of 8+ public MCP servers
- [ ] One-click install of Context7 with env var input
- [ ] Stdio servers spawn on-demand and stop when idle
- [ ] Tools from stdio servers appear in tool registry
- [ ] Built-in HTTP servers continue working unchanged
- [ ] Installation status tracked and displayed
- [ ] Can uninstall and reinstall servers
- [ ] Env vars can reference user's stored credentials
