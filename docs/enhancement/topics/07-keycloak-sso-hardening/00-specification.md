# Keycloak SSO Hardening

**Status:** ✅ Design Complete  
**Priority:** High (Critical)  
**Target:** v1.4  
**Estimated Effort:** 0.5 Phase (3 weeks)  
**Last Updated:** 2026-03-16

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Architecture Overview](#architecture-overview)
4. [Health Monitoring & Diagnostics](#health-monitoring--diagnostics)
5. [User Experience Improvements](#user-experience-improvements)
6. [Configuration Validation](#configuration-validation)
7. [Implementation Phases](#implementation-phases)
8. [Success Criteria](#success-criteria)
9. [Risks and Mitigations](#risks-and-mitigations)
10. [Related Documents](#related-documents)

---

## Executive Summary

This enhancement hardens the Keycloak SSO integration to eliminate the recurring "Server error — Configuration" issue and provide robust, user-friendly authentication. **Keycloak is an optional feature** — AgentOS works perfectly with local authentication only.

### Core Principle: Keycloak is OPTIONAL

AgentOS operates seamlessly without SSO:
- **Not configured** → System works with local auth (default)
- **Configured but unhealthy** → Graceful fallback to local auth
- **Configured and healthy** → SSO option available as enhancement

### Three-Pillar Hardening Approach

```
┌─────────────────────────────────────────────────────────────────┐
│              KEYCLOAK SSO HARDENING SYSTEM                       │
│              (Optional Enhancement Layer)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  1. HEALTH MONITORING & DIAGNOSTICS                         ││
│  │     • Real-time health checks (when configured)             ││
│  │     • Error categorization (cert/config/unreachable)       ││
│  │     • Admin dashboard with actionable insights              ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  2. USER EXPERIENCE IMPROVEMENTS                            ││
│  │     • Graceful error handling (no "Configuration" errors)   ││
│  │     • Smart fallback to local auth                          ││
│  │     • Circuit breaker pattern                               ││
│  │     • Dynamic SSO button visibility                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  3. CONFIGURATION VALIDATION                                ││
│  │     • Pre-flight testing before save                        ││
│  │     • Certificate validation                                ││
│  │     • OIDC discovery verification                           ││
│  │     • Specific fix recommendations                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Improvements

| Area | Before | After |
|------|--------|-------|
| **Error Messages** | "Server error — Configuration" | Friendly: "SSO temporarily unavailable. Please use your username and password." |
| **Error Visibility** | Generic error, no details | Categorized: certificate/config/unreachable/timeout |
| **Admin Tools** | None | Health dashboard + test connection + diagnostics |
| **User Experience** | Login fails mysteriously | Graceful fallback to local auth |
| **Configuration** | Save and hope it works | Pre-flight validation with specific fixes |
| **Resilience** | Repeated failed attempts | Circuit breaker stops the cascade |

---

## Problem Statement

### Current State (As-Is)

| Issue | Impact | Current Workaround |
|-------|--------|-------------------|
| **"Server error — Configuration"** | Users cannot log in via SSO, no guidance | Users must guess to use local auth |
| **No error categorization** | Cannot diagnose root cause | Manual log inspection required |
| **No admin visibility** | Admins don't know SSO is broken | Users report issues reactively |
| **No pre-flight validation** | Invalid configs saved, break production | Trial and error configuration |
| **Cascade failures** | Repeated failed SSO attempts | None — keeps failing |
| **Partial fix applied** | `fetchWithRetry` added in Phase 24-01 | Helps startup timing, not other issues |

### Target State (To-Be)

| Issue | Target Solution |
|-------|----------------|
| **Generic errors** | Friendly, actionable error messages |
| **No diagnostics** | Admin dashboard with health checks |
| **No visibility** | Real-time status + notifications |
| **No validation** | Pre-flight testing with fix guidance |
| **Cascade failures** | Circuit breaker + graceful degradation |

### Root Causes (From STATE.md)

The "Server error — Configuration" error occurs when next-auth Keycloak provider fails during OIDC discovery or token exchange:

1. **Certificate Issues** (40% of cases)
   - Self-signed certificate not trusted by Node.js
   - Missing `KEYCLOAK_CA_CERT` configuration
   - Certificate expired or invalid

2. **Configuration Mismatch** (35% of cases)
   - `KEYCLOAK_CLIENT_ID` mismatch with Keycloak realm
   - `KEYCLOAK_CLIENT_SECRET` incorrect
   - Issuer URL format incorrect

3. **Service Unavailable** (20% of cases)
   - Keycloak container not running
   - Network connectivity issues
   - DNS resolution failure
   - Keycloak still starting up

4. **Timeout** (5% of cases)
   - Keycloak slow to respond
   - Network latency

---

## Architecture Overview

### Core Principle: Keycloak is OPTIONAL

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                           │
│              (Works with or without Keycloak)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  User Visits Login Page                                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Check: Is Keycloak configured?                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│          │                              │                        │
│          ▼ NO                          ▼ YES                     │
│   ┌──────────────┐              ┌──────────────────────┐        │
│   │ Show Local   │              │ Check Health Status  │        │
│   │ Auth Only    │              │ (Circuit Breaker)    │        │
│   └──────────────┘              └──────────────────────┘        │
│                                          │                       │
│                    ┌─────────────────────┼─────────────────────┐ │
│                    ▼                     ▼                     ▼ │
│             ┌──────────┐          ┌──────────┐          ┌──────┐ │
│             │ Healthy  │          │Degraded  │          │ Down │ │
│             └────┬─────┘          └────┬─────┘          └──┬───┘ │
│                  │                     │                   │     │
│                  ▼                     ▼                   ▼     │
│           ┌──────────┐          ┌──────────┐          ┌────────┐ │
│           │Show SSO  │          │Show SSO  │          │Hide SSO│ │
│           │+ Local   │          │+ Warning │          │+ Local │ │
│           │Button    │          │+ Local   │          │Only    │ │
│           └──────────┘          └──────────┘          └────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Graceful Degradation

When SSO fails, the system automatically falls back:

```
User Clicks SSO Button
       │
       ▼
┌─────────────────────────────────────┐
│   Check: Circuit breaker open?      │
└─────────────────────────────────────┘
       │
       ├─ YES ──► Hide SSO Button
       │            Show: "SSO temporarily unavailable"
       │            Focus local auth form
       │
       └─ NO ──► Attempt Keycloak Auth
                      │
                      ▼
            ┌──────────────────┐
            │   Success?       │
            └──────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
    ┌──────────┐        ┌──────────┐
    │   YES    │        │    NO    │
    └────┬─────┘        └────┬─────┘
         │                   │
         ▼                   ▼
    ┌──────────┐        ┌─────────────────┐
    │Logged In │        │ Record Failure  │
    │   ✓      │        │ Update Circuit  │
    └──────────┘        │ Breaker         │
                        └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │ Show Friendly   │
                        │ Error + Local   │
                        │ Auth Form       │
                        └─────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Keycloak Optional** | System must work without SSO for simple deployments |
| **Graceful Degradation** | SSO issues shouldn't block user login |
| **Health Checks On-Demand** | No background polling overhead when not needed |
| **Smart Error Messages** | Different guidance for different error types |
| **Circuit Breaker** | Prevent cascade of failed auth attempts |
| **No User-Visible Errors** | SSO is optional — errors shouldn't alarm users |

---

## Health Monitoring & Diagnostics

### Health Check Service

**Location:** Backend FastAPI endpoint

**Endpoint:** `GET /api/admin/keycloak/health`

**Test Sequence:**
1. **DNS Resolution** → Resolve issuer hostname
2. **TLS/Certificate** → Verify certificate chain
3. **OIDC Discovery** → Fetch `.well-known/openid-configuration`
4. **Client Auth** → Validate client credentials

```typescript
interface KeycloakHealthResponse {
  configured: boolean;
  status: 'healthy' | 'degraded' | 'unhealthy' | 'not_configured';
  checks: {
    dns: { passed: boolean; error?: string };
    tls: { passed: boolean; error?: string; certInfo?: {...} };
    discovery: { passed: boolean; error?: string; endpoints?: {...} };
    client: { passed: boolean; error?: string };
  };
  lastCheck: string;
  lastSuccess?: string;
  errorType?: 'certificate' | 'configuration' | 'unreachable' | 'timeout';
  recommendations: string[];
}
```

### Error Categorization

```typescript
function categorizeError(error: Error): ErrorType {
  const message = error.message.toLowerCase();
  
  if (message.includes('certificate') || 
      message.includes('self signed') ||
      message.includes('unable to verify')) {
    return 'certificate';
  }
  
  if (message.includes('client_id') || 
      message.includes('client_secret') ||
      message.includes('unauthorized')) {
    return 'configuration';
  }
  
  if (message.includes('econnrefused') || 
      message.includes('enotfound') ||
      message.includes('timeout')) {
    return 'unreachable';
  }
  
  return 'unknown';
}
```

### Admin Dashboard Integration

**Health Widget** (on `/admin/identity`):
```
┌─────────────────────────────────────┐
│  SSO Health                         │
├─────────────────────────────────────┤
│  ● Healthy                          │
│  Last check: 2 minutes ago          │
│  [View Details] [Test Now]          │
└─────────────────────────────────────┘
```

**Health Details Page** (`/admin/identity/sso-health`):
- **Status Card**: Large indicator (green/yellow/red)
- **Test Results**: Pass/fail for each check with details
- **Error Log**: Last 10 errors with timestamps
- **Actions**:
  - "Test Connection Now" button
  - "View Configuration" link
  - "Edit Configuration" link
  - "Disable SSO" button (emergency)

### Recommendations Engine

Based on error type, provide specific fix guidance:

| Error Type | Recommendation |
|------------|---------------|
| **Certificate** | "Add Keycloak CA certificate to `frontend/certs/keycloak-ca.crt` and set `KEYCLOAK_CA_CERT` environment variable." |
| **Configuration** | "Verify client_id and client_secret match Keycloak realm configuration. Check Admin Console > Identity > Keycloak SSO." |
| **Unreachable** | "Verify Keycloak service is running (`just ps`). Check network connectivity from frontend container to Keycloak." |
| **Timeout** | "Keycloak may be starting up. Wait 30 seconds and retry. Check Keycloak logs: `just logs keycloak`" |

---

## User Experience Improvements

### Enhanced Error Handling

**Current State:** Only handles `SessionExpired` and `RefreshAccessTokenError`

**Enhanced Error Map:**
```typescript
const errorMessages: Record<string, { title: string; message: string }> = {
  Configuration: {
    title: "Single Sign-On Temporarily Unavailable",
    message: "We're experiencing issues with our SSO provider. Please sign in with your username and password below.",
  },
  OAuthSignin: {
    title: "Sign-In Error",
    message: "There was a problem starting the sign-in process. Please try again or use local credentials.",
  },
  OAuthCallback: {
    title: "Sign-In Error",
    message: "We couldn't complete the sign-in. Please try again or use your username and password.",
  },
  SessionExpired: {
    title: "Session Expired",
    message: "Your session has expired for security reasons. Please sign in again.",
  },
  RefreshAccessTokenError: {
    title: "Session Expired",
    message: "Your session has expired. Please sign in again.",
  },
};
```

### Login Page Enhancements

**Error Display:**
```
┌─────────────────────────────────────────────────────────┐
│  ⚠️ Single Sign-On Temporarily Unavailable              │
│                                                          │
│  We're experiencing issues with our SSO provider.        │
│  Please sign in with your username and password below.   │
│                                                          │
│  ┌──────────────────────────┐                           │
│  │ Username                 │                           │
│  └──────────────────────────┘                           │
│  ┌──────────────────────────┐                           │
│  │ Password                 │                           │
│  └──────────────────────────┘                           │
│                                                          │
│  [Sign In]                                               │
│                                                          │
│  ─────────── OR ───────────                              │
│                                                          │
│  [Try SSO Again]  ← Button still available for retry    │
└─────────────────────────────────────────────────────────┘
```

### Dynamic SSO Button Visibility

**Logic:**
```typescript
function shouldShowSSOButton(): boolean {
  // 1. Check if SSO is enabled in config
  if (!ssoEnabled) return false;
  
  // 2. Check recent health status
  if (recentHealthCheckFailed) return false;
  
  // 3. Check circuit breaker
  if (circuitBreakerOpen) return false;
  
  return true;
}
```

### Circuit Breaker Pattern

**State Machine:**
```
┌──────────┐     5 failures      ┌─────────┐
│  CLOSED  │ ───────────────────▶│  OPEN   │
│ (normal) │                     │(blocked)│
└────┬─────┘                     └────┬────┘
     │                                │
     │ Success                        │ 60s timeout
     │                                │
     │◄───────────────────────────────┘
     │         Half-Open
     ▼
┌──────────┐
│ HALF-OPEN│─── Success ───▶ CLOSED
│ (testing)│
└──────────┘─── Failure ────▶ OPEN
```

**Implementation:**
```typescript
interface CircuitBreaker {
  state: 'closed' | 'open' | 'half-open';
  failureCount: number;
  lastFailureTime?: Date;
  threshold: number;  // 5 failures
  timeout: number;    // 60 seconds
}

// Usage in auth flow
if (circuitBreaker.state === 'open') {
  // Skip SSO, go straight to local auth
  return null;
}

try {
  const result = await attemptKeycloakAuth();
  circuitBreaker.recordSuccess();
  return result;
} catch (error) {
  circuitBreaker.recordFailure();
  return null;
}
```

### Admin Notifications

When an admin is logged in and SSO fails:
```typescript
if (session?.user?.isAdmin && ssoHealthStatus === 'unhealthy') {
  toast.warning(
    "SSO Health Alert: Keycloak connection is down. Users are falling back to local auth.",
    {
      duration: 10000,
      action: {
        label: "View Details",
        onClick: () => router.push('/admin/identity/sso-health'),
      },
    }
  );
}
```

---

## Configuration Validation

### Pre-Flight Test API

**Endpoint:** `POST /api/admin/keycloak/test-config`

**Request:**
```typescript
interface TestConfigRequest {
  clientId: string;
  clientSecret: string;
  issuer: string;
  caCert?: string;
}
```

**Response:**
```typescript
interface TestConfigResponse {
  valid: boolean;
  tests: {
    dns: { passed: boolean; message: string };
    tls: { passed: boolean; message: string; certificateValid?: boolean };
    discovery: { passed: boolean; message: string; authEndpoint?: string; tokenEndpoint?: string };
    client: { passed: boolean; message: string };
  };
  errors?: string[];
  suggestions?: string[];
}
```

### Admin UI Integration

**"Test Connection" Button:**
```
┌─────────────────────────────────────────────────────────┐
│  Keycloak SSO Configuration                             │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Issuer URL:                                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ https://keycloak.blitz.local:7443/realms/blitz  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  Client ID:                                             │
│  ┌─────────────────────────────────────────────────┐   │
│  │ blitz-frontend                                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  Client Secret:                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ••••••••••••••••••••••••••••••••••••••••••••  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  [🔄 Test Connection]  [💾 Save Configuration]         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Test Results:**

*Success:*
```
┌─────────────────────────────────────────────────────────┐
│  Test Results                                           │
├─────────────────────────────────────────────────────────┤
│  ✅ DNS Resolution    keycloak.blitz.local → 172.18.0.5 │
│  ✅ TLS Certificate   Valid, expires in 365 days        │
│  ✅ OIDC Discovery    Found endpoints                   │
│  ✅ Client Auth       Credentials valid                 │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ ✓ All tests passed! Configuration is valid.     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  [💾 Save Configuration]                                │
└─────────────────────────────────────────────────────────┘
```

*Failure:*
```
┌─────────────────────────────────────────────────────────┐
│  Test Results                                           │
├─────────────────────────────────────────────────────────┤
│  ✅ DNS Resolution    keycloak.blitz.local → 172.18.0.5 │
│  ❌ TLS Certificate   Self-signed certificate rejected  │
│  ⏸️ OIDC Discovery    (skipped due to TLS error)        │
│  ⏸️ Client Auth       (skipped due to TLS error)        │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Error: Self-signed certificate not trusted      │   │
│  │                                                   │   │
│  │ Fix: Add CA certificate path or set             │   │
│  │ KEYCLOAK_CA_CERT environment variable.          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  [🔄 Retry Test]  [📖 Troubleshooting Guide]            │
└─────────────────────────────────────────────────────────┘
```

### Configuration Safety

**Before Save:**
- Must pass all tests before saving
- Warning if saving without testing
- Backup previous config (allow rollback)

**After Save:**
- Clear auth cache
- Reset circuit breaker
- Trigger immediate health check
- Log configuration change (audit trail)

---

## Implementation Phases

### Phase 1: Backend Health Check API (Week 1)

**Backend Tasks:**
- Create `/api/admin/keycloak/health` endpoint
  - DNS resolution test
  - TLS certificate validation
  - OIDC discovery endpoint check
  - Client credentials test
- Implement error categorization logic
- Create `/api/admin/keycloak/test-config` endpoint
- Add health check service with caching (5-minute TTL)

**Deliverables:**
- Health check API functional
- Error categorization working
- Test configuration API working

---

### Phase 2: Admin UI Health Dashboard (Week 1.5)

**Frontend Tasks:**
- Add health widget to `/admin/identity` page
- Create `/admin/identity/sso-health` page
  - Status indicator
  - Test results display
  - Error log (last 10 entries)
  - "Test Now" button
- Add "Test Connection" button to existing Keycloak config page
- Create test results component

**Deliverables:**
- Admin can view SSO health status
- Admin can test configuration before saving
- Health details page functional

---

### Phase 3: Login Page Improvements (Week 2)

**Frontend Tasks:**
- Enhance `/login/page.tsx` error handling
  - Handle `?error=Configuration`
  - Handle `?error=OAuthSignin`
  - Handle `?error=OAuthCallback`
- Create error message mapping
- Add graceful fallback to local auth
- Implement dynamic SSO button visibility
  - Hide button if health check fails
  - Show helpful message when SSO unavailable
- Add circuit breaker state checking

**Deliverables:**
- Users see friendly error messages
- SSO failures gracefully fall back to local auth
- SSO button hides when service is unhealthy

---

### Phase 4: Circuit Breaker & Notifications (Week 2.5)

**Backend Tasks:**
- Implement circuit breaker pattern
  - Track failure counts
  - Open circuit after 5 failures
  - Half-open after 60 seconds
  - Close on success
- Add admin notification endpoint
- Create failure logging (structured logs)

**Frontend Tasks:**
- Enhance `AuthErrorToasts` component
  - Show admin notifications for SSO issues
  - Add link to health page
- Implement circuit breaker status indicator

**Deliverables:**
- Circuit breaker prevents repeated failed attempts
- Admins notified when SSO goes down
- System automatically recovers

---

### Phase 5: Testing & Documentation (Week 3)

**Testing Tasks:**
- Test all error scenarios:
  - Certificate errors
  - Configuration errors
  - Network unreachable
  - Keycloak down
- Test graceful degradation
- Test circuit breaker behavior
- Test admin notifications
- Mobile responsiveness check

**Documentation Tasks:**
- Update troubleshooting guide
- Add Keycloak setup guide
- Document error messages
- Create admin runbook

**Deliverables:**
- Production-ready SSO hardening
- Comprehensive documentation
- All tests passing

---

## Success Criteria

### Health Monitoring
- [ ] Health check API returns accurate status for all 4 test categories
- [ ] Error categorization correctly identifies: certificate, configuration, unreachable, timeout
- [ ] Admin dashboard shows SSO health status clearly
- [ ] "Test Connection" button validates config before save
- [ ] Health checks don't run when Keycloak is not configured (no overhead)

### User Experience
- [ ] Login page handles all error types gracefully
- [ ] Users see friendly messages, never "Server error — Configuration"
- [ ] SSO failures automatically fall back to local auth
- [ ] SSO button hides when service is unhealthy
- [ ] No user-visible errors for optional feature

### Configuration Management
- [ ] Pre-flight validation prevents saving invalid configs
- [ ] Test results show specific fix recommendations
- [ ] Configuration changes trigger immediate health check
- [ ] Audit log tracks configuration changes

### Circuit Breaker
- [ ] Opens after 5 consecutive failures
- [ ] Prevents cascade of failed auth attempts
- [ ] Automatically retries after timeout
- [ ] Logs state transitions

### Performance
- [ ] Health check API responds in < 2 seconds
- [ ] Login page shows SSO button state instantly (cached health)
- [ ] No impact on local auth flow when Keycloak disabled

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Health check overhead** | Low | Low | Only run when admin views page; 5-min cache |
| **False positives in health check** | Medium | Medium | Multiple test levels; verify before alerting |
| **Circuit breaker too aggressive** | Low | Medium | Configurable thresholds; manual override |
| **Breaking existing local auth** | Low | High | Extensive testing; feature flag for rollout |
| **Admin notification spam** | Medium | Low | Debounce notifications; only notify on state change |
| **Certificate validation too strict** | Medium | Medium | Allow custom CA; document self-signed cert process |

---

## Related Documents

- [Brainstorming Tracking](../BRAINSTORMING-TRACKING.md) - Project context and status
- [STATE.md](/.planning/STATE.md) - Current tech debt entry for this issue
- [Phase 24-01 Plan](/.planning/phases/24-unified-registry-mcp-platform-enhancement-skill-import-adapters/24-01-PLAN.md) - Partial fix already applied
- [Identity Configuration Design](../identity-configuration/00-specification.md) - Related identity management topic

---

**Document Owner:** Architecture Team  
**Reviewers:** Backend Team, Frontend Team, DevOps Team  
**Approved:** Pending Implementation Review
