# Email System & Channel Notifications

**Topic #18**
**Status:** ✅ Design Complete
**Priority:** Medium
**Target:** v1.7+
**Estimated Effort:** 1 Phase (6 weeks)
**Created:** 2026-03-17

---

## Problem Statement

AgentOS currently lacks email as a communication channel and has no centralized notification system. Users cannot:

1. Send or receive emails via AgentOS chat
2. Receive system notifications via email (workflow completions, errors, security events, etc.)
3. Configure email delivery preferences per notification type
4. Manage email accounts with proper authentication (OAuth + IMAP/SMTP)

**Current State:**
- Email agent exists but returns mock data only (no real email integration)
- Channel architecture supports Telegram, WhatsApp, MS Teams, Web — but not email
- No centralized notification routing system
- No per-user notification preferences
- Email templates not managed
- System-wide email settings not configurable

**Impact:**
- Users miss critical system notifications (workflow failures, security events)
- No email communication channel for organizations that prefer email over chat
- Notifications are limited to in-app and Telegram only
- Admin cannot enforce system-wide email policies

---

## Target State (To-Be)

Transform email into a **first-class channel** alongside Telegram/WhatsApp, with:

### Core Capabilities

1. **Full Bi-Directional Email Channel**
   - Users can receive emails (IMAP/IMAP IDLE)
   - Users can send emails via agent ("send email to john@example.com")
   - Email is a true `channel` in the architecture (not just notification delivery)

2. **Hybrid Authentication**
   - OAuth 2.0 for Gmail/Microsoft 365 (primary, no passwords)
   - IMAP/SMTP app passwords for other providers (fallback)
   - Automatic OAuth token refresh (background Celery task)

3. **Centralized Notification Service**
   - 8 notification types with per-type routing
   - Multi-channel delivery (email + telegram + whatsapp + in-app)
   - Per-user notification preferences (which channel for which event type)

4. **System-Wide Email Settings (Admin-Only)**
   - SMTP server configuration enforced by admin
   - System sender email (`noreply@blitz.local`)
   - Email templates (HTML + plain text)
   - Rate limits and retry policies

5. **User Email Account Management**
   - Single email account per user (linked from user profile)
   - Email address auto-populated from Keycloak/AD/LDAP profile
   - "Link Email" button in user profile with OAuth + IMAP/SMTP options
   - Credentials stored in AES-256-GCM encrypted `UserCredential` table (ADR-008)

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AgentOS Backend                               │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  NotificationService (NEW)                                   │   │
│  │  - send_notification(type, user_id, message)                 │   │
│  │  - Routes to user's preferred channels                         │   │
│  │  - Reads UserNotificationPreferences table                        │   │
│  │  - Sends system notifications via system SMTP                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  ChannelGateway (EXISTING)                                   │   │
│  │  - send_outbound(msg: InternalMessage)                         │   │
│  │  - Calls all sidecar /send endpoints                           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                              │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
           ▼                   ▼                   ▼
    ┌───────────┐      ┌───────────┐      ┌─────────────────────┐
    │  Telegram  │      │  WhatsApp  │      │      Email          │
    │  Sidecar   │      │  Sidecar   │      │     Sidecar        │
    │ (existing) │      │ (future)   │      │       (NEW)        │
    │  Port N/A  │      │  Port 8002 │      │       Port 8003     │
    └───────────┘      └───────────┘      └─────────────────────┘
                                                      │
                                      ┌───────────────┼───────────────┐
                                      │               │               │
                                      ▼               ▼               ▼
                            ┌────────────────┐  ┌──────────┐  ┌────────────────┐
                            │ Gmail API    │  │ M365 API │  │ IMAP/SMTP    │
                            │ (OAuth 2.0) │  │(OAuth)   │  │  Providers    │
                            └────────────────┘  └──────────┘  └────────────────┘
                                      │               │               │
                                      └───────────────┼───────────────┘
                                                      │
                                                      ▼
                                        ┌──────────────────────────────┐
                                        │  System Email Server        │
                                        │  (Admin-configured SMTP)    │
                                        │  Used for system           │
                                        │  notifications only          │
                                        └──────────────────────────────┘
```

### Key Architectural Decisions

| Decision | Rationale |
|-----------|------------|
| **Sidecar pattern** for email adapter | Consistent with Telegram/WhatsApp, isolates IMAP/SMTP complexity, scalable |
| **NotificationService** as centralized router | Enables per-notification-type preferences, reusable for all notification types |
| **Hybrid auth** (OAuth + IMAP) | Best UX for Gmail/M365, supports all providers via IMAP fallback |
| **UserCredential table** for email passwords | Reuses AES-256-GCM vault (ADR-008), proven security pattern |
| **System SMTP** for notifications only | Enforced admin settings, users can't override system email config |
| **Email Sidecar manages IMAP connections** | Backend remains stateless, IMAP IDLE connections isolated |

---

## Components

### Component 1: Email Sidecar Service

**Location:** `channel-gateways/email/`

**Responsibilities:**
1. Send outbound emails (POST `/send`)
2. Receive inbound emails (IMAP IDLE or polling → POST `/api/channels/incoming`)
3. OAuth 2.0 flows for Gmail/M365
4. IMAP/SMTP connection management
5. Token refresh for OAuth accounts

**Endpoints:**

| Endpoint | Method | Purpose |
|----------|---------|---------|
| `/send` | POST | Send outbound email (from backend) |
| `/health` | GET | Health check for sidecar monitoring |
| `/oauth/gmail/start` | GET | Initiate Gmail OAuth flow |
| `/oauth/gmail/callback` | GET | Handle Gmail OAuth callback |
| `/oauth/m365/start` | GET | Initiate Microsoft 365 OAuth flow |
| `/oauth/m365/callback` | GET | Handle M365 OAuth callback |

**Technology Stack:**
- **Language:** Python 3.12+
- **IMAP Client:** `aiosmtplib` (SMTP) + `aioimaplib` (IMAP)
- **OAuth:** `google-auth-oauthlib` + `msal` (Microsoft Authentication Library)
- **Storage:** SQLite (local, for IMAP message tracking) - shared volume mount
- **Health:** `/health` endpoint returns status (IMAP connected, SMTP connected, OAuth tokens valid)

**Configuration (Environment Variables):**
```bash
# Sidecar settings
EMAIL_SIDECAR_PORT=8003
LOG_LEVEL=INFO

# IMAP/SMTP connection pool
MAX_IMAP_CONNECTIONS=50
IMAP_IDLE_TIMEOUT=300  # seconds
SMTP_POOL_SIZE=10

# OAuth configuration (Gmail)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8003/oauth/gmail/callback

# OAuth configuration (M365)
MICROSOFT_OAUTH_CLIENT_ID=...
MICROSOFT_OAUTH_CLIENT_SECRET=...
MICROSOFT_OAUTH_REDIRECT_URI=http://localhost:8003/oauth/m365/callback
MICROSOFT_OAUTH_TENANT_ID=...

# Shared volume (for IMAP message tracking)
SHARED_VOLUME_PATH=/app/shared
```

**OAuth Flow (Gmail/M365):**

```
User clicks "Connect with Gmail" in profile
    ↓
Email Sidecar → /oauth/gmail/start
    ↓
Redirect to Google consent screen
    ↓
User authorizes → Google redirects to /oauth/gmail/callback?code=...
    ↓
Email Sidecar exchanges code for access_token + refresh_token
    ↓
POST /api/channels/email/oauth-callback
    ↓
Backend stores tokens in UserCredential (AES-256-GCM encrypted)
    ↓
Email Sidecar starts IMAP IDLE connection using access_token
```

**IMAP Connection Management:**

- **IDLE Mode (Gmail/M365):** Real-time push when new email arrives
- **Polling Mode (Other providers):** Check every 30 seconds
- **Connection Pool:** Reuse connections, close after 5 minutes of inactivity
- **Error Handling:** Reconnect on connection drops, exponential backoff (1s, 2s, 4s, 8s)

---

### Component 2: NotificationService

**Location:** `backend/notifications/`

**Responsibilities:**
1. Centralized routing for all 8 notification types
2. Lookup user notification preferences
3. Send notifications to multiple channels (email, telegram, whatsapp, in-app)
4. Event-driven integration with Celery, workflows, scheduler
5. Rate limiting and retry logic

**API (Internal Service):**

```python
class NotificationService:
    async def send_notification(
        self,
        notification_type: NotificationType,
        user_id: UUID,
        message: str,
        metadata: dict | None = None
    ) -> None:
        """
        Send notification to user's preferred channels.

        1. Query UserNotificationPreferences for (user_id, notification_type)
        2. For each channel in preferences.channels:
           - Create InternalMessage (direction=outbound)
           - Call ChannelGateway.send_outbound(msg)
        """

    async def send_system_notification(
        self,
        notification_type: NotificationType,
        user_ids: list[UUID],
        message: str
    ) -> None:
        """
        Send system-wide notification (from admin).
        Uses system SMTP settings (not user's email).
        """
```

**Notification Types Enum:**

```python
class NotificationType(str, Enum):
    WORKFLOW_SUCCESS = "workflow_success"
    WORKFLOW_FAILURE = "workflow_failure"
    SCHEDULED_JOB_SUCCESS = "scheduled_job_success"
    SCHEDULED_JOB_FAILURE = "scheduled_job_failure"
    AGENT_ERROR = "agent_error"
    SECURITY_EVENT = "security_event"
    SYSTEM_ALERT = "system_alert"
    WEEKLY_DIGEST = "weekly_digest"
    TOOL_USAGE_ALERT = "tool_usage_alert"
    MENTION = "mention"
```

**Event Integration:**

| Event Source | Trigger | Integration Point |
|---------------|----------|-------------------|
| Celery workflow completion | `on_task_success` / `on_task_failure` | Celery signal → NotificationService |
| Scheduler job completion | `post_job_hook` | Celery beat → NotificationService |
| Agent exception | `try/except` wrapper | Agent nodes → NotificationService |
| Security event (login, permission change) | Security middleware | Auth routes → NotificationService |
| System alert (service health) | Health check failure | Monitoring service → NotificationService |
| Weekly digest | Cron job (Sunday 00:00 UTC) | Celery beat → NotificationService |

**Rate Limiting:**

```python
# Per-user rate limits
RATE_LIMITS = {
    "email": {"max_per_hour": 50, "burst": 5},
    "telegram": {"max_per_hour": 100, "burst": 10},
    "in_app": {"max_per_minute": 10, "burst": 2}
}
```

**Retry Logic:**

- Email: 3 retries with exponential backoff (5s, 10s, 20s)
- Telegram: 2 retries with fixed backoff (2s)
- In-app: No retry (WebSocket)

---

### Component 3: Database Tables

**New Table: UserNotificationPreferences**

```sql
CREATE TABLE user_notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    notification_type VARCHAR(64) NOT NULL,
    channels TEXT[] NOT NULL,  -- ["email", "telegram", "whatsapp", "in_app"]
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_user_notification UNIQUE (user_id, notification_type),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES ... (implicit, no FK in AgentOS)
);

CREATE INDEX idx_user_notification_preferences_user_id ON user_notification_preferences(user_id);
```

**Table: ChannelAccount (Extend existing)**

```sql
-- Add email-specific columns
ALTER TABLE channel_accounts ADD COLUMN email_provider VARCHAR(32);  -- "gmail", "m365", "imap_smtp"
ALTER TABLE channel_accounts ADD COLUMN email_address VARCHAR(256);  -- for IMAP/SMTP fallback
```

**Table: SystemEmailSettings (Use platform_config)**

```python
# Store in platform_config table (existing)
{
    "email_smtp_host": "smtp.gmail.com",
    "email_smtp_port": 587,
    "email_smtp_tls": true,
    "email_from_address": "noreply@blitz.local",
    "email_from_name": "AgentOS Notifications",
    "email_rate_limit_per_hour": 1000,
    "email_retry_max_attempts": 3,
    "email_retry_backoff_seconds": 5
}
```

---

### Component 4: Email Templates

**Location:** `backend/templates/email/`

**Template Structure:**

```
backend/templates/email/
├── workflow_success.html.j2
├── workflow_success.txt.j2
├── workflow_failure.html.j2
├── workflow_failure.txt.j2
├── scheduled_job_success.html.j2
├── scheduled_job_failure.html.j2
├── agent_error.html.j2
├── agent_error.txt.j2
├── security_event.html.j2
├── security_event.txt.j2
├── system_alert.html.j2
├── system_alert.txt.j2
├── weekly_digest.html.j2
├── weekly_digest.txt.j2
├── tool_usage_alert.html.j2
├── tool_usage_alert.txt.j2
├── mention.html.j2
└── mention.txt.j2
```

**Template Variables (Jinja2):**

```jinja2
{# workflow_success.html.j2 #}
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .success { color: #10b981; }
        .workflow-name { font-weight: bold; }
    </style>
</head>
<body>
    <h2>✓ Workflow Completed Successfully</h2>

    <p>Hello {{ user_name }},</p>

    <p>Your workflow <span class="workflow-name">{{ workflow_name }}</span> completed successfully.</p>

    <h3>Details:</h3>
    <ul>
        <li><strong>Started:</strong> {{ started_at }}</li>
        <li><strong>Completed:</strong> {{ completed_at }}</li>
        <li><strong>Duration:</strong> {{ duration_seconds }} seconds</li>
        <li><strong>Agent:</strong> {{ agent_name }}</li>
    </ul>

    <p><a href="{{ workflow_url }}">View in AgentOS</a></p>

    <hr>
    <p><small>AgentOS Notification System</small></p>
</body>
</html>
```

**Template Rendering Service:**

```python
class EmailTemplateService:
    def render(
        self,
        template_name: str,
        context: dict,
        format: Literal["html", "txt"] = "html"
    ) -> str:
        """
        Render email template with Jinja2.

        Args:
            template_name: e.g., "workflow_success"
            context: {user_name, workflow_name, started_at, ...}
            format: "html" or "txt"
        """
        filename = f"{template_name}.{format}.j2"
        return jinja_env.get_template(filename).render(context)
```

---

### Component 5: User Profile - Link Email Button

**Location:** `frontend/src/app/(authenticated)/settings/profile/page.tsx`

**UI Flow:**

```
User Profile Page
    ↓
"Email Account" Section
    ├─ "Link Email" button (if no email linked)
    └─ "Connected: john@example.com" (if already linked)
        └─ "Unlink" button
```

**Link Email Flow:**

```
User clicks "Link Email"
    ↓
Read email from user profile (Keycloak/AD/LDAP)
    ↓
Show modal:
    "Link email account for john@example.com"
    ├─ [Option 1] "Connect with Gmail" (OAuth)
    └─ [Option 2] "Use IMAP/SMTP" (App password)

[Option 1 - Gmail OAuth]:
    User clicks "Connect with Gmail"
    ↓
Redirect to Email Sidecar: /oauth/gmail/start?redirect_url=...
    ↓
Google consent screen
    ↓
OAuth callback → Backend stores tokens in UserCredential
    ↓
Create ChannelAccount: channel="email", external_user_id="john@example.com"
    ↓
Success message: "Email linked successfully!"

[Option 2 - IMAP/SMTP]:
    User clicks "Use IMAP/SMTP"
    ↓
Show form:
    ┌─────────────────────────────────────┐
    │ IMAP Server: imap.gmail.com       │
    │ IMAP Port: 993                 │
    │ SMTP Server: smtp.gmail.com        │
    │ SMTP Port: 587                   │
    │ App Password: ***********         │
    └─────────────────────────────────────┘
    ↓
POST /api/channels/email/link
    ↓
Backend encrypts password → Store in UserCredential
    ↓
Create ChannelAccount row
    ↓
Success message: "Email linked successfully!"
```

---

### Component 6: Admin Email Settings UI

**Location:** `frontend/src/app/(authenticated)/admin/email-settings/page.tsx`

**Settings Sections:**

**Section 1: SMTP Configuration**

```
┌───────────────────────────────────────────────┐
│ SMTP Server Configuration                   │
├───────────────────────────────────────────────┤
│ SMTP Host:     [smtp.gmail.com        ]  │
│ SMTP Port:     [587                 ]  │
│ Use TLS:       [✓]                  │
│                                       │
│ Test Connection [Send Test Email]         │
└───────────────────────────────────────────────┘
```

**Section 2: Sender Information**

```
┌───────────────────────────────────────────────┐
│ Sender Email                             │
├───────────────────────────────────────────────┤
│ From Email:     [noreply@blitz.local] │
│ From Name:      [AgentOS Notifications]   │
│                                       │
│ Reply-to Email: [support@blitz.local ] │
└───────────────────────────────────────────────┘
```

**Section 3: Rate Limits**

```
┌───────────────────────────────────────────────┐
│ Rate Limits                             │
├───────────────────────────────────────────────┤
│ Max emails/hour:   [1000            ]  │
│ Burst size:        [50               ]  │
│                                       │
│ Retry Attempts:    [3                ]  │
│ Retry Backoff:     [5 seconds       ]  │
└───────────────────────────────────────────────┘
```

**Section 4: Email Templates**

```
┌───────────────────────────────────────────────┐
│ Email Templates                          │
├───────────────────────────────────────────────┤
│ Workflow Success [View/Edit]               │
│ Workflow Failure [View/Edit]               │
│ Security Event   [View/Edit]               │
│ ...                                       │
│                                       │
│ [Customize Template]                      │
└───────────────────────────────────────────────┘
```

**Backend API Endpoints:**

```
GET  /api/admin/email-settings          # Get current settings
POST /api/admin/email-settings          # Update settings
POST /api/admin/email-settings/test    # Send test email
GET  /api/admin/email-settings/templates  # List templates
GET  /api/admin/email-settings/templates/{name}  # Get template
PUT  /api/admin/email-settings/templates/{name}  # Update template
```

---

## Data Flow

### Flow 1: User Links Email Account (Gmail OAuth)

```
User Profile → "Link Email" button
    │
    ▼
Frontend reads user email from Keycloak profile
    │
    ▼
Show modal: "Link john@example.com"
    │
    ├─ Option 1: "Connect with Gmail" (OAuth)
    │       │
    │       ▼
    │   Frontend → GET /oauth/gmail/start?redirect_url=https://agentos.local/settings/profile
    │       │
    │       ▼
    │   Email Sidecar → Generate OAuth state
    │       │
    │       ▼
    │   Redirect to https://accounts.google.com/o/oauth2/v2/auth
    │       ?client_id=...
    │       &redirect_uri=http://localhost:8003/oauth/gmail/callback
    │       &response_type=code
    │       &scope=https://mail.google.com/
    │       &state=xyz123
    │       │
    │       ▼
    │   Google → User authorizes app
    │       │
    │       ▼
    │   Google → Redirect to http://localhost:8003/oauth/gmail/callback?code=...&state=xyz123
    │       │
    │       ▼
    │   Email Sidecar → Validate state → Exchange code for tokens
    │       │
    │       ▼
    │   POST /api/channels/email/oauth-callback
    │       {
    │           "user_id": "uuid",
    │           "email_address": "john@example.com",
    │           "provider": "gmail",
    │           "access_token": "...",
    │           "refresh_token": "...",
    │           "expires_in": 3600
    │       }
    │       │
    │       ▼
    │   Backend → Encrypt tokens with AES-256-GCM
    │       │
    │       ▼
    │   Backend → INSERT INTO user_credentials
    │       (user_id, provider="email_gmail", credentials_encrypted)
    │       │
    │       ▼
    │   Backend → INSERT INTO channel_accounts
    │       (user_id, channel="email", external_user_id="john@example.com",
    │        email_provider="gmail", is_paired=true)
    │       │
    │       ▼
    │   Email Sidecar → Start IMAP IDLE connection using access_token
    │       │
    │       ▼
    │   Frontend → "Email linked successfully!"
```

### Flow 2: User Links Email Account (IMAP/SMTP App Password)

```
User Profile → "Link Email" button
    │
    ▼
Frontend reads user email from Keycloak profile
    │
    ▼
Show modal: "Link john@example.com"
    │
    └─ Option 2: "Use IMAP/SMTP"
            │
            ▼
        Frontend → Show form:
            IMAP Server: [imap.gmail.com]
            IMAP Port: [993]
            SMTP Server: [smtp.gmail.com]
            SMTP Port: [587]
            App Password: [**********]
            │
            ▼
        Frontend → POST /api/channels/email/link
            {
                "email_address": "john@example.com",
                "imap_server": "imap.gmail.com",
                "imap_port": 993,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "app_password": "**********"
            }
            │
            ▼
        Backend → Validate IMAP/SMTP connection
            │
            ▼
        Backend → Encrypt app_password with AES-256-GCM
            │
            ▼
        Backend → INSERT INTO user_credentials
            (user_id, provider="email_imap", credentials_encrypted)
            │
            ▼
        Backend → INSERT INTO channel_accounts
            (user_id, channel="email", external_user_id="john@example.com",
             email_provider="imap_smtp", is_paired=true)
            │
            ▼
        Email Sidecar → Start IMAP polling (every 30 seconds)
            │
            ▼
        Frontend → "Email linked successfully!"
```

### Flow 3: Outbound Notification (System Notification)

```
Event Trigger (e.g., Workflow completes successfully)
    │
    ├─ Celery task success signal
    ├─ Scheduler job completion hook
    ├─ Agent exception handler
    └─ Security event middleware
    │
    ▼
Backend → NotificationService.send_notification(
        notification_type="workflow_success",
        user_id="uuid",
        message="Workflow 'Daily Report' completed",
        metadata={
            "workflow_name": "Daily Report",
            "workflow_url": "https://agentos.local/workflows/abc",
            "started_at": "2026-03-14T10:00:00Z",
            "completed_at": "2026-03-14T10:05:00Z",
            "duration_seconds": 300
        }
    )
    │
    ▼
NotificationService → SELECT FROM user_notification_preferences
    WHERE user_id="uuid" AND notification_type="workflow_success"
    │
    ▼
User Preference: channels=["email", "telegram"]
    │
    ▼
For each channel in ["email", "telegram"]:
    │
    ├─ Channel: "email"
    │       │
    │       ▼
    │   NotificationService → Create InternalMessage
    │       {
    │           direction="outbound",
    │           channel="email",
    │           user_id="uuid",
    │           text=render_template("workflow_success.html", metadata)
    │       }
    │       │
    │       ▼
    │   Backend → ChannelGateway.send_outbound(msg)
    │       │
    │       ▼
    │   Backend → POST http://email:8003/send
    │       {
    │           "direction": "outbound",
    │           "channel": "email",
    │           "user_id": "uuid",
    │           "text": "Workflow 'Daily Report' completed...",
    │           "metadata": {"use_system_smtp": true}  # System notification
    │       }
    │       │
    │       ▼
    │   Email Sidecar → Read SystemEmailSettings from backend
    │       │
    │       ▼
    │   Email Sidecar → Send via system SMTP (noreply@blitz.local)
    │       │
    │       ▼
    │   Email Sidecar → SMTP client → Send email
    │       To: john@example.com (from ChannelAccount.email_address)
    │       From: noreply@blitz.local (system setting)
    │       Subject: "✓ Workflow Completed Successfully"
    │       Body: [HTML email from template]
    │       │
    │       ▼
    │   Email Sidecar → Log: "notification_sent", user_id=uuid, channel=email
    │
    └─ Channel: "telegram"
            │
            ▼
        NotificationService → Create InternalMessage
        {
            direction="outbound",
            channel="telegram",
            user_id="uuid",
            text="✓ Workflow 'Daily Report' completed successfully..."
        }
        │
        ▼
        Backend → ChannelGateway.send_outbound(msg)
        │
        ▼
        Backend → POST http://telegram/send
        │
        ▼
        Telegram Sidecar → Send via Telegram API
        │
        ▼
        Telegram Sidecar → Log: "notification_sent", user_id=uuid, channel=telegram
```

### Flow 4: Outbound User Email (Agent sends email)

```
User in chat: "Send an email to sarah@example.com about project status"
    │
    ▼
Agent → LLM decides to use email tool
    │
    ▼
Agent → Tool: send_email(
        to="sarah@example.com",
        subject="Project Status Update",
        body="Hi Sarah, here's the latest status..."
    )
    │
    ▼
Tool executor → Execute send_email tool
    │
    ▼
Backend → Resolve user's email ChannelAccount
    │
    ▼
Backend → Decrypt user credentials from UserCredential (AES-256-GCM)
    │
    ▼
Backend → ChannelGateway.send_outbound()
    {
        direction="outbound",
        channel="email",
        user_id="uuid",
        to="sarah@example.com",
        subject="Project Status Update",
        body="Hi Sarah, here's the latest status...",
        metadata={"use_user_smtp": true}  # User's email account
    }
    │
    ▼
Backend → POST http://email:8003/send
    │
    ▼
Email Sidecar → Send via user's SMTP/IMAP credentials
    │
    ▼
Email Sidecar → SMTP client → Send email
    │
    │
    │
    ├─ Gmail OAuth: Use access_token to send via Gmail API
    └─ IMAP/SMTP: Use app_password to send via SMTP server
    │
    ▼
Email Sidecar → Log: "email_sent", from=john@example.com, to=sarah@example.com
```

### Flow 5: Inbound Email (User receives email)

```
External sender: sarah@example.com sends email to john@example.com
    │
    ▼
Email arrives at john@example.com inbox
    │
    ├─ Gmail OAuth: Gmail API push notification
    └─ IMAP/SMTP: IMAP IDLE or polling (every 30 seconds)
    │
    ▼
Email Sidecar → Detect new email
    │
    ▼
Email Sidecar → Parse email
    {
        from="sarah@example.com",
        to="john@example.com",
        subject="Re: Project Status",
        body="Thanks for the update! Quick question...",
        timestamp="2026-03-14T11:00:00Z"
    }
    │
    ▼
Email Sidecar → Create InternalMessage
    {
        direction="inbound",
        channel="email",
        external_user_id="john@example.com",
        external_chat_id="sarah@example.com",  # Thread/conversation ID
        text="Thanks for the update! Quick question...",
        metadata={"from": "sarah@example.com", "subject": "..."}
    }
    │
    ▼
Email Sidecar → POST http://backend:8000/api/channels/incoming
    │
    ▼
Backend → ChannelGateway.handle_inbound(msg, db)
    │
    ▼
Backend → Resolve ChannelAccount
    WHERE channel="email" AND external_user_id="john@example.com"
    │
    ▼
Backend → user_id = ChannelAccount.user_id
    │
    ▼
Backend → Resolve or Create ChannelSession
    WHERE channel_account_id AND external_chat_id="sarah@example.com"
    │
    ▼
Backend → conversation_id = ChannelSession.conversation_id
    │
    ▼
Backend → Set user_id and conversation_id on msg
    │
    ▼
Backend → Invoke master agent
    │
    ▼
Agent → Process email content
    │
    ├─ If email is a question: "Sarah asks about project status..."
    ├─ If email is a task: "Sarah wants me to send weekly report..."
    └─ If email is a mention: "Sarah mentions @john in this email..."
    │
    ▼
Agent → Generate response
    │
    ▼
Agent → Output to delivery_router_node
    │
    ▼
Backend → ChannelGateway.send_outbound(response)
    │
    ▼
Backend → POST http://email:8003/send
    │
    ▼
Email Sidecar → Send response via user's email account
    │
    ▼
Email Sidecar → Send email to sarah@example.com
    From: john@example.com
    To: sarah@example.com
    Body: [Agent response]
```

### Flow 6: Weekly Digest Notification

```
Cron job (Sunday 00:00 UTC) → Celery beat trigger
    │
    ▼
Celery → Query activity for last 7 days
    │
    ├─ Workflows completed: count
    ├─ Scheduled jobs run: count
    ├─ Agent errors: count
    ├─ Security events: count
    └─ Active conversations: count
    │
    ▼
Celery → Aggregate digest data
    {
        user_id="uuid",
        period_start="2026-03-07T00:00:00Z",
        period_end="2026-03-14T00:00:00Z",
        workflows_completed=15,
        scheduled_jobs_run=42,
        agent_errors=2,
        security_events=0,
        active_conversations=5
    }
    │
    ▼
Celery → NotificationService.send_notification(
        notification_type="weekly_digest",
        user_id="uuid",
        message="Your weekly activity summary",
        metadata={digest_data}
    )
    │
    ▼
NotificationService → Render weekly_digest.html template
    │
    ▼
NotificationService → Send to user's preferred channels
    (e.g., ["email"] only)
    │
    ▼
Backend → Email Sidecar → Send digest email
    │
    ▼
Email Sidecar → Email to john@example.com
    Subject: "📊 Your Weekly Activity Summary"
    Body: [HTML digest with charts and tables]
```

### Flow 7: OAuth Token Refresh

```
Background task (Celery beat every 55 minutes)
    │
    ▼
Celery → Query UserCredential for expiring OAuth tokens
    WHERE provider IN ("email_gmail", "email_m365")
    AND expires_at < NOW() + 5 minutes
    │
    ▼
For each expiring token:
    │
    ├─ Gmail OAuth
    │       │
    │       ▼
    │   Email Sidecar → POST https://oauth2.googleapis.com/token
    │       {
    │           "grant_type": "refresh_token",
    │           "refresh_token": "...",
    │           "client_id": "...",
    │           "client_secret": "..."
    │       }
    │       │
    │       ▼
    │   Email Sidecar → Receive new access_token, refresh_token
    │       │
    │       ▼
    │   Email Sidecar → POST /api/channels/email/token-refresh
    │       {
    │           "user_id": "uuid",
    │           "provider": "email_gmail",
    │           "access_token": "...",
    │           "refresh_token": "...",
    │           "expires_in": 3600
    │       }
    │       │
    │       ▼
    │   Backend → Encrypt new tokens → Update UserCredential
    │
    └─ M365 OAuth
            │
            ▼
        Email Sidecar → POST https://login.microsoftonline.com/common/oauth2/v2.0/token
        {
            "grant_type": "refresh_token",
            "refresh_token": "...",
            "client_id": "...",
            "client_secret": "...",
            "scope": "https://graph.microsoft.com/.default"
        }
        │
        ▼
        Email Sidecar → Receive new tokens
        │
        ▼
        Email Sidecar → POST /api/channels/email/token-refresh
        │
        ▼
        Backend → Encrypt new tokens → Update UserCredential
```

---

## Error Handling & Testing

### Error Handling Strategy

#### Email Sidecar Error Handling

| Error Type | Detection | Handling | Logging |
|-------------|------------|-----------|----------|
| **SMTP send failure** | `httpx.HTTPStatusError` / `smtplib.SMTPException` | Retry 3 times with exponential backoff (5s, 10s, 20s) | `error=email_send_failed, error_detail=...` |
| **IMAP connection lost** | `aioimaplib.IMAPClientError` / Connection closed | Reconnect with exponential backoff (1s, 2s, 4s, 8s, max 3 attempts) | `error=imap_reconnect, attempt=...` |
| **OAuth token expired** | `google.auth.exceptions.RefreshError` | Trigger token refresh flow immediately | `error=oauth_token_expired, provider=gmail` |
| **OAuth refresh failed** | `google.auth.exceptions.RefreshError` (no retry) | Mark email as "needs re-auth", notify user via in-app + telegram | `error=oauth_refresh_failed, provider=gmail, user_id=...` |
| **IMAP authentication failed** | `aioimaplib.AuthenticationError` | Mark ChannelAccount as "unlinked", notify user | `error=imap_auth_failed, user_id=...` |
| **Rate limit exceeded** | Gmail API error 429 / SMTP 4xx | Backoff 60 seconds, retry once | `error=rate_limit_exceeded, retry_after=60s` |
| **Malformed email** | Email parsing exception | Log error, skip processing | `error=email_parse_failed, from=...` |

#### NotificationService Error Handling

| Error Type | Detection | Handling | Logging |
|-------------|------------|-----------|----------|
| **Channel delivery failed** | `ChannelGateway.send_outbound()` raises exception | Retry based on channel policy | `error=notification_delivery_failed, channel=...` |
| **User preference lookup failed** | DB query error | Default to all channels, alert admin | `error=user_preference_lookup_failed, user_id=...` |
| **Template rendering failed** | Jinja2 exception | Send fallback plain text, alert admin | `error=template_render_failed, template=...` |
| **Rate limit exceeded** | User sent > max emails/hour | Queue notification, send when quota resets | `error=notification_rate_limit, user_id=...` |
| **NotificationService down** | Health check failure | Queue notifications in Redis, retry when healthy | `error=notification_service_down, queued_count=...` |

#### Database Error Handling

| Error Type | Handling |
|-------------|-----------|
| **UserCredential not found** | Return 404 to email sidecar, trigger re-auth flow |
| **ChannelAccount not found** | Log error, return 404 to user (message: "Email not linked") |
| **NotificationPreferences not found** | Default to all channels for user, insert default row |
| **Encryption/Decryption failed** | Log critical error, alert admin via Telegram/in-app |
| **Foreign key constraint violated** | Rollback transaction, return 400 to user with detail |
| **Unique constraint violated** | Email already linked, return 409 to user (message: "Email already linked") |

---

### Testing Strategy

#### Unit Tests

**Email Sidecar:**
- `test_send_email_via_oauth_gmail()`
- `test_send_email_via_imap_smtp()`
- `test_oauth_flow_gmail()`
- `test_oauth_token_refresh()`
- `test_imap_idle_reconnect()`
- `test_rate_limit_handling()`

**NotificationService:**
- `test_send_notification_single_channel()`
- `test_send_notification_multiple_channels()`
- `test_send_system_notification()`
- `test_rate_limit_enforcement()`
- `test_template_rendering()`

#### Integration Tests

- `test_full_email_linking_flow_gmail_oauth()`
- `test_full_email_linking_flow_imap_smtp()`
- `test_inbound_email_processing()`
- `test_outbound_notification_flow()`
- `test_oauth_token_refresh_background_task()`

#### End-to-End Tests (Playwright)

- `test('User links Gmail account via OAuth')`
- `test('User links email via IMAP/SMTP app password')`
- `test('Admin configures SMTP settings')`
- `test('User receives workflow completion notification via email')`

#### Performance Tests

- `test_imap_pool_handles_100_connections()`
- `test_notification_service_handles_1000_notifications_per_minute()`
- `test_oauth_refresh_completes_within_5_seconds()`

---

### Monitoring & Observability

**Metrics to Track:**

| Metric | Description | Alert Threshold |
|---------|-------------|------------------|
| `email_sidecar_imap_connections_active` | Number of active IMAP connections | > 80 (warn), > 95 (critical) |
| `email_sidecar_smtp_send_success_rate` | % of successful SMTP sends | < 95% (warn), < 90% (critical) |
| `email_sidecar_oauth_token_refresh_failures` | Number of failed OAuth refreshes | > 5/minute (critical) |
| `notification_service_queue_depth` | Number of queued notifications | > 1000 (warn), > 5000 (critical) |
| `notification_service_delivery_latency_p95` | 95th percentile delivery time (seconds) | > 30s (warn), > 60s (critical) |
| `email_send_rate_per_user` | Emails sent per user per hour | > 50 (warn), > 100 (critical) |

**Health Checks:**

```python
# Email Sidecar /health endpoint
{
    "status": "healthy",
    "components": {
        "imap_connections": {"status": "healthy", "count": 42},
        "smtp_client": {"status": "healthy", "last_send": "2026-03-14T10:00:00Z"},
        "oauth_tokens": {"status": "healthy", "valid_count": 38, "expiring_count": 0}
    },
    "dependencies": {
        "backend_api": {"status": "healthy", "latency_ms": 25},
        "gmail_api": {"status": "healthy", "latency_ms": 150},
        "m365_api": {"status": "healthy", "latency_ms": 180}
    }
}

# NotificationService health check
{
    "status": "healthy",
    "components": {
        "channel_gateway": {"status": "healthy"},
        "user_preferences": {"status": "healthy"},
        "email_templates": {"status": "healthy"}
    },
    "queue_depth": 0,
    "last_notification_sent": "2026-03-14T10:00:00Z"
}
```

**Alerting Rules:**

```python
# Alert rules (Grafana/Prometheus)
- alert: EmailSidecarIMAPConnectionsHigh
  expr: email_sidecar_imap_connections_active > 95
  for: 5m
  annotations:
    summary: "Email sidecar IMAP connections near capacity"

- alert: NotificationServiceQueueDepthHigh
  expr: notification_service_queue_depth > 5000
  for: 5m
  annotations:
    summary: "Notification queue backlog critical"

- alert: OAuthRefreshFailureRateHigh
  expr: rate(email_sidecar_oauth_token_refresh_failures[5m]) > 5
  for: 5m
  annotations:
    summary: "OAuth token refresh failures critical"
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Backend:**
1. Create `UserNotificationPreferences` table (migration 032_user_notification_preferences)
2. Extend `ChannelAccount` with email_provider and email_address columns (migration 033_email_channel_columns)
3. Create `NotificationService` class in `backend/notifications/`
4. Add notification types enum to `backend/core/schemas/notification.py`
5. Implement `send_notification()` and `send_system_notification()` methods

**Frontend:**
1. Create notification preferences page (`/settings/notifications/page.tsx`)
2. Add checkbox grid for 8 notification types × 4 channels
3. Save preferences to backend API (`POST /api/user/notification-preferences`)

**Testing:**
1. Unit tests for `NotificationService`
2. Integration tests for preference storage/retrieval
3. E2E tests for notification preferences UI

---

### Phase 2: Email Sidecar (Week 2-4)

**Backend:**
1. Create `channel-gateways/email/` directory
2. Implement Email Sidecar (Python)
3. Add OAuth flows for Gmail/M365
4. Implement IMAP IDLE connection management
5. Implement SMTP client (with system SMTP support)
6. Add `/send`, `/health`, OAuth endpoints
7. Add email sidecar to `docker-compose.yml`

**Configuration:**
1. Add `GOOGLE_OAUTH_CLIENT_ID`, `MICROSOFT_OAUTH_CLIENT_ID` to `.env`
2. Add email sidecar to `ChannelGateway.sidecar_urls`

**Testing:**
1. Unit tests for Email Sidecar
2. Integration tests for OAuth flows
3. Integration tests for IMAP/SMTP sending/receiving
4. Health check tests

---

### Phase 3: Email Templates & Admin Settings (Week 4-5)

**Backend:**
1. Create `EmailTemplateService` in `backend/notifications/`
2. Create Jinja2 templates for 8 notification types (HTML + plain text)
3. Add admin email settings endpoints (`/api/admin/email-settings/*`)
4. Implement system email settings storage in `platform_config`

**Frontend:**
1. Create admin email settings page (`/admin/email-settings/page.tsx`)
2. Add SMTP configuration form
3. Add sender information form
4. Add rate limits form
5. Add email template editor (with live preview)

**Testing:**
1. Unit tests for `EmailTemplateService`
2. Integration tests for admin settings CRUD
3. E2E tests for admin email settings UI

---

### Phase 4: User Email Linking (Week 5)

**Backend:**
1. Add `/api/channels/email/link` endpoint (IMAP/SMTP)
2. Add `/api/channels/email/oauth-callback` endpoint (OAuth)
3. Implement credential encryption (AES-256-GCM) before storing
4. Implement IMAP/SMTP connection validation

**Frontend:**
1. Add "Link Email" button to user profile page
2. Add OAuth flow UI ("Connect with Gmail", "Connect with M365")
3. Add IMAP/SMTP form UI
4. Show linked email status in profile

**Email Sidecar:**
1. Start IMAP IDLE connections after account linking
2. Handle inbound emails (parse → POST `/api/channels/incoming`)

**Testing:**
1. E2E tests for Gmail OAuth linking
2. E2E tests for IMAP/SMTP linking
3. Integration tests for credential encryption/decryption

---

### Phase 5: Inbound Email & Agent Integration (Week 6)

**Backend:**
1. Update `ChannelGateway.handle_inbound()` to handle `channel="email"`
2. Update `InternalMessage` model to include `channel="email"`
3. Email Sidecar: Implement inbound email parsing
4. Email Sidecar: POST to `/api/channels/incoming`
5. Test end-to-end: External email → Email Sidecar → Backend → Agent → Response → Email

**Testing:**
1. Integration tests for inbound email processing
2. Integration tests for agent response via email
3. E2E tests: Send email → Receive response

---

### Phase 6: Event Integration & Weekly Digest (Week 6-7)

**Backend:**
1. Wire Celery signals to `NotificationService` (workflow completion, job failure)
2. Wire security event middleware to `NotificationService`
3. Implement Celery beat task for weekly digest (Sunday 00:00 UTC)
4. Implement OAuth token refresh task (every 55 minutes)

**Testing:**
1. Integration tests for workflow completion notifications
2. Integration tests for scheduled job notifications
3. Integration tests for weekly digest generation
4. Performance tests for 1000 notifications/minute

---

### Phase 7: Error Handling & Monitoring (Week 7)

**Email Sidecar:**
1. Implement exponential backoff for SMTP/IMAP errors
2. Implement OAuth token refresh error handling
3. Add retry logic with max attempts
4. Add structured logging for all errors

**NotificationService:**
1. Implement rate limiting per user
2. Implement notification queueing (Redis)
3. Add fallback to secondary channels
4. Add structured logging for delivery failures

**Monitoring:**
1. Add Prometheus metrics to Email Sidecar
2. Add Prometheus metrics to NotificationService
3. Create Grafana dashboards for email metrics
4. Configure alerting rules (IMAP connections, queue depth, delivery latency)

**Testing:**
1. Unit tests for error handling
2. Performance tests for rate limiting
3. Load tests for 100 concurrent users

---

## Success Criteria

- [ ] Email is a first-class channel in `InternalMessage.channel` enum
- [ ] Users can link email via Gmail OAuth (no passwords)
- [ ] Users can link email via IMAP/SMTP app passwords
- [ ] Email credentials stored encrypted in `UserCredential` table (AES-256-GCM)
- [ ] Email Sidecar handles inbound emails (IMAP IDLE or polling)
- [ ] Email Sidecar sends outbound emails via Gmail/M365 API or IMAP/SMTP
- [ ] Email Sidecar auto-refreshes OAuth tokens (background Celery task)
- [ ] `NotificationService` sends notifications to user's preferred channels
- [ ] 8 notification types supported (workflow, scheduler, errors, security, etc.)
- [ ] Per-notification-type preferences work (email + telegram + whatsapp + in-app)
- [ ] System notifications use admin-configured SMTP settings
- [ ] User emails use user's email account credentials
- [ ] Admin can configure system-wide SMTP settings
- [ ] Admin can customize email templates (HTML + plain text)
- [ ] Admin can test email connection
- [ ] Weekly digest emails sent on Sunday 00:00 UTC
- [ ] OAuth token refresh happens automatically (every 55 minutes)
- [ ] Error handling with retry logic and exponential backoff
- [ ] Rate limiting enforced (50 emails/hour per user)
- [ ] Health checks work for Email Sidecar and NotificationService
- [ ] Prometheus metrics exported and visible in Grafana
- [ ] Alerting rules configured (IMAP connections, queue depth, delivery latency)
- [ ] All E2E tests pass (linking, notifications, templates)
- [ ] Performance tests pass (100 IMAP connections, 1000 notifications/minute)

---

## Key Dependencies

| Dependency | Type | Required For | Status |
|------------|-------|---------------|--------|
| `google-auth-oauthlib` | Python package | Gmail OAuth | ⏳ To be installed |
| `msal` | Python package | M365 OAuth | ⏳ To be installed |
| `aiosmtplib` | Python package | Async SMTP | ⏳ To be installed |
| `aioimaplib` | Python package | Async IMAP | ⏳ To be installed |
| Google Cloud Project | External | Gmail OAuth credentials | ⏳ To be created |
| Microsoft Azure App Registration | External | M365 OAuth credentials | ⏳ To be created |
| `jinja2` | Python package (existing) | Email templates | ✅ Already available |
| `redis` | Python package (existing) | Notification queue | ✅ Already available |
| `celery` | Python package (existing) | Background tasks | ✅ Already available |

---

## Open Questions

1. **Gmail/M365 OAuth credentials:** Who manages Google Cloud Project and Microsoft Azure App Registration?
   - Option A: AgentOS team provides shared credentials (all users use same OAuth app)
   - Option B: Each organization provides their own OAuth credentials (multi-tenant)

2. **IMAP connection pooling for 100 users:** Is SQLite sufficient for message tracking, or should we use PostgreSQL?

3. **Email template localization:** Should templates support multiple languages (based on user profile)?

4. **Email attachment handling:** Should inbound emails with attachments be supported? If so, store in Topic #19 Storage Service?

5. **Email threading:** Should we preserve Gmail/M365 thread IDs for conversation continuity?

---

## References

- **ADR-008:** AES-256-GCM credential vault (backend/security/credentials.py)
- **Channel Architecture:** `backend/channels/adapter.py`, `backend/channels/gateway.py`
- **NotificationTypes:** 8 types defined in design (workflow, scheduler, errors, security, etc.)
- **Email Agent:** `backend/agents/subagents/email_agent.py` (mock data, to be replaced with real integration)
- **OAuth 2.0 Flows:** Gmail and Microsoft 365 documentation
- **Jinja2 Documentation:** https://jinja.palletsprojects.com/

---

*This design document is ready for implementation planning. Run `/gsd:plan-phase` to create detailed implementation plans.*
