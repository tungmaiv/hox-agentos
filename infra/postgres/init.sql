-- Initialize extensions for Blitz AgentOS
-- This runs once when the postgres container is first created.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
