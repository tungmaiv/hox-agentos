

## 1. Requirements and constraints

For an email summary use case:

- The system must access the user’s mailbox (Gmail, O365, IMAP, internal mail).
- Access must be **on behalf of the user**, not a shared root key.
- Tokens must **never** be visible to the LLM or frontend.
- Tokens should be revocable (user leaves company, revokes access, changes password).
- Scheduler jobs (e.g., morning summary) should still work with no user interaction.

***

## 2. Option A – Delegated OAuth flow + refresh tokens

This is closest to how OpenClaw and similar agents access email/Drive.

### Flow

1. User links their email account in a **settings page** in Blitz AgentOS.
2. Frontend redirects user to provider’s OAuth consent (Google, Microsoft, internal IdP) requesting scopes like:
    - `https://www.googleapis.com/auth/gmail.readonly`
    - `offline_access` for refresh token.
3. Provider redirects back with an auth code; backend exchanges it for:
    - Access token.
    - Refresh token.
4. Backend stores tokens in `user_credentials` table, encrypted and keyed by:
    - `user_id` (from Keycloak).
    - `provider` (e.g., `gmail`, `o365`).
    - `scope`/`account_id`.

### Data model

```sql
CREATE TABLE user_credentials (
  id             UUID PRIMARY KEY,
  user_id        UUID NOT NULL,
  provider       TEXT NOT NULL,           -- "gmail", "o365"
  account_id     TEXT NOT NULL,           -- email address
  access_token   TEXT NOT NULL,
  refresh_token  TEXT,
  expires_at     TIMESTAMPTZ,
  scopes         TEXT[],
  created_at     TIMESTAMPTZ DEFAULT now(),
  updated_at     TIMESTAMPTZ DEFAULT now()
);
```


### Usage in tools / MCP

- Backend email tool or MCP server:

1. Receives only `user_id` and params (no tokens).
2. Looks up `user_credentials` for `provider="gmail"` and `user_id`.
3. If `expires_at < now()`, uses refresh token to obtain a new access token, updates DB.
4. Calls provider API to fetch emails.
5. Returns structured data to agent.

LLM never sees tokens; it just calls `email.fetch` or `mcp.gmail.list_messages(user_id=...)`. Tools do the credential plumbing.[^2][^1]

**Pros**

- Fine‑grained user consent per provider.
- Revocable via provider dashboard.
- Scheduler can run as long as refresh token valid.

**Cons**

- You must manage refresh and token rotation.
- Need to guard against token leaks (encrypt at rest, strict access control).

***

## 3. Option B – Backend‑stored secrets \& delegated internal auth

Useful when email is an **internal system**, not Gmail/O365.

### Flow

1. Internal mail system trusts Keycloak (e.g., via JWT or mutual TLS).
2. Blitz AgentOS never stores per‑user app passwords; instead:
    - It passes a signed backend token asserting `user_id` and roles to the internal mail API.
3. Internal mail system maps that to the mailbox and enforces its own ACL.

### Implementation

- `email_tools.py` calls `INTERNAL_MAIL_API` with:
    - User’s Keycloak ID or email.
    - A short‑lived signed JWT from Blitz backend asserting the user identity.
- Internal mail validates this and queries the mailbox.

**Pros**

- No extra credential database; all auth is centralized in your IAM + mail system.
- Easy to revoke: disable user in Keycloak.

**Cons**

- Requires you control the mail system or have strong integration capabilities.

***

## 4. Option C – Service account + per‑user mapping

Pattern commonly used for Google Workspace / O365 with domain‑wide delegation.

### Flow

1. Blitz AgentOS uses a **service account** with domain‑wide delegation.
2. When user authorizes, you *don’t* store their personal token; instead, you store:
    - Mapping from `user_id` → `email_address`.
3. For each call, the email tool:
    - Uses the service account to impersonate that email address (subject= user’s email).
    - Provider enforces per‑user access based on domain rules.

### Data model

```sql
CREATE TABLE user_email_accounts (
  id          UUID PRIMARY KEY,
  user_id     UUID NOT NULL,
  provider    TEXT NOT NULL,        -- "gmail-domain", "o365-delegated"
  email       TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

Service account credentials live only in backend secrets (KMS, environment, or vault).

**Pros**

- No per‑user refresh token management.
- Easy to rotate service account keys centrally.
- Works well in corporate domains.

**Cons**

- Dangerous if misconfigured: service can impersonate anyone.
- Needs strong RBAC, auditing, and key management.

***

## 5. Where credentials flow in Blitz AgentOS

Across all options, key design rules:

- **Frontend never sees tokens**: only triggers tools that operate “on behalf of user”.
- **LLM never sees tokens**: tools receive `user_id` and domain parameters, not secrets.
- **MCP servers are trusted backend processes**: they read secrets from backend DB or vault, not from prompts.

Recommended pattern in code:

```python
@tool
def fetch_email_summary(input: EmailSummaryInput) -> EmailSummaryOutput:
    user_ctx = get_user_context()  # from Keycloak JWT in FastAPI
    creds = credentials_repo.get_email_credentials(user_ctx.user_id)

    # or domain-delegated: account = mapping_repo.get_email_account(user_ctx.user_id)

    client = EmailClient.from_credentials(creds)
    messages = client.list_recent(...)
    summary = summarize_messages(messages)
    return summary
```


***

## 6. Tool/MCP integration variants

### 6.1 Direct backend tool

- `email.fetch` is a Python tool that uses credentials and calls provider API.
- For scheduled jobs, scheduler passes `user_id` to the tool; tool does the rest.


### 6.2 MCP‑backed email server

- Implement `email_mcp_server` exposing:
    - `list_messages(user_id, ...)`
    - `get_message(user_id, message_id)`
- MCP server loads credentials and calls provider.
- Copilot Runtime ACL ensures only allowed roles can call “email” MCP tools.[^3]

**Benefit**: decouple email implementation from main backend; can swap Gmail↔O365 without changing tools.

***

## 7. Security hardening checklist

For enterprise Blitz:

- Store credentials in a secure table or external vault:
    - Encrypt columns (`access_token`, `refresh_token`) with KMS.
    - Restrict DB user that can read them to the credential service only.
- Limit scopes:
    - Use read‑only scopes for summaries (`read`, not `send`), unless sending is needed.
- Add revocation UI:
    - “Disconnect email” button that deletes or disables credentials.
- Add observability:
    - Log when a tool uses credentials (user, time, scope, mailbox).
    - Expose an admin audit log for compliance.
- Use sandboxing for any tool that writes files derived from email content, but sandbox is not for token storage—tokens stay in main backend or vault.[^4][^1]

***

## 8. Recommended approach for Blitz

For a typical SaaS‑style setup:

- **Short term**:
    - Use **Option A** (OAuth + per‑user refresh tokens) for Gmail/O365.
    - Implement email tools that read encrypted tokens from DB.
- **Mid‑term (if you control infra)**:
    - For internal email, transition to **Option B** or **C** with domain‑wide delegation and service accounts, to simplify token management.

If you want, next step I can sketch the exact `user_credentials` table, the FastAPI OAuth callbacks, and a sample `EmailMCPServer` that reads those credentials and exposes MCP tools to your agents.

<div align="center">⁂</div>

[^1]: 17-Kien-truc-Tich-hop-Ky-nang-Backend-cho-AI-Agent.md

[^2]: 16-Kien-Truc-Trien-Khai-Agent-Va-Cong-Cu-Trong-Copilot-Kit.md

[^3]: 12-Trien-Khai-ACL-Cho-Cong-Cu-MCP-Trong-Copilot-Runtime.md

[^4]: 05-Bao-Mat-Agent-AI-Bang-Co-Che-Docker-Sandboxing.md

