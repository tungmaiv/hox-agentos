# Blitz Keycloak Setup Guide

**Version:** 1.0  
**Last Updated:** 2026-02-14  
**Realm:** blitz-internal  
**Structure:** 8 teams, 5 roles, 40 employees

---

## 🎯 Overview

This guide sets up **Blitz** identity infrastructure using Keycloak with a clean, organized structure supporting:

- **8 Teams:** sales, pre-sales, tech, swift, support, admin, hr, financial
- **5 Realm Roles:** employee, manager, team-lead, it-admin, executive
- **2 Active Clients:** blitz-portal, blitz-odoo
- **2 Deprecated Clients:** blitz-huly (deprecated 2026-02-19, see Epic 13), blitz-kimai (deprecated 2026-02-19, see Epic 13)
- **15 Initial Users:** Admin + team leads + sample employees

---

## 📁 File Structure

```
infrastructure/
├── shared/
│   ├── docker-compose.shared.yml    # Keycloak + Observability
│   └── keycloak/
│       └── realms/
│           ├── blitz-internal-realm.json   # ✅ New Blitz realm
│           └── hox-aa-realm.json           # (old - not imported)
├── nginx/
│   └── nginx.conf                   # Updated for blitz.local
└── huly/                            # DEPRECATED (2026-02-19, see Epic 13)
    └── docker-compose.huly.yml      # Deprecated — blitz-huly client removed

scripts/
└── blitz-keycloak-reset.sh          # Bootstrap/reset script

docs/
└── blitz-keycloak-setup.md          # This guide

.env.local                           # Updated Blitz config
.env.example                         # Template
```

---

## 🚀 Quick Start

### Step 1: DNS (Cloudflare)

All services are accessed via `*.lumiaitech.com` subdomains through Cloudflare Zero Trust tunnel. No `/etc/hosts` changes needed.

### Step 2: Bootstrap Keycloak

```bash
# Navigate to project root
cd /home/tungvm/Projects/hox-aa

# Run bootstrap script (interactive - requires confirmation)
./scripts/blitz-keycloak-reset.sh

# Or force without confirmation (careful!)
./scripts/blitz-keycloak-reset.sh --force
```

This will:
1. Stop existing Keycloak services
2. Remove old data volumes
3. Start fresh Keycloak
4. Auto-import `blitz-internal` realm
5. Create 15 initial users

### Step 3: Verify Setup

```bash
# Check Keycloak health
curl -k https://keycloak.lumiaitech.com/health/ready

# Check realm import
docker logs hox-aa-keycloak | grep -i "blitz-internal"
```

### Step 4: Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Keycloak Admin** | https://keycloak.lumiaitech.com/admin | admin/admin |
| **Portal** | https://portal.lumiaitech.com | (via Keycloak) |
| **Odoo** | https://odoo.lumiaitech.com | (via Keycloak) |
| **Huly** (deprecated) | https://huly.lumiaitech.com | **(deprecated 2026-02-19, see Epic 13)** |
| **Grafana** | https://grafana.lumiaitech.com | admin/admin |

---

## 👥 User Structure

### Realm Roles

| Role | Description | MFA Required |
|------|-------------|--------------|
| `employee` | Base access for all staff | Optional |
| `manager` | Team managers, cross-team visibility | Optional |
| `team-lead` | Technical leads, approval authority | Optional |
| `it-admin` | Full system admin access | **Yes** |
| `executive` | C-level, strategic access | **Yes** |

### Teams (Groups)

- **/sales** - Sales representatives and managers
- **/pre-sales** - Solution engineers and consultants
- **/tech** - Non-Swift technical team (backend, frontend, devops)
- **/swift** - Swift services dedicated team
- **/support** - Customer support agents and leads
- **/admin** - System administrators
- **/hr** - Human resources
- **/financial** - Finance and accounting

### Initial Users

| Username | Team | Role | Email | Password | MFA |
|----------|------|------|-------|----------|-----|
| admin | admin | it-admin | admin@blitz.local | admin | ✅ |
| sales-lead | sales | manager | sales-lead@blitz.local | Sales123! | ❌ |
| sales-rep | sales | employee | sales-rep@blitz.local | Sales123! | ❌ |
| pre-sales-lead | pre-sales | manager | pre-sales-lead@blitz.local | PreSales123! | ❌ |
| pre-sales-eng | pre-sales | employee | pre-sales-eng@blitz.local | PreSales123! | ❌ |
| tech-lead | tech | team-lead | tech-lead@blitz.local | Tech123! | ❌ |
| tech-dev | tech | employee | tech-dev@blitz.local | Tech123! | ❌ |
| swift-lead | swift | team-lead | swift-lead@blitz.local | Swift123! | ❌ |
| swift-dev | swift | employee | swift-dev@blitz.local | Swift123! | ❌ |
| support-lead | support | manager | support-lead@blitz.local | Support123! | ❌ |
| support-agent | support | employee | support-agent@blitz.local | Support123! | ❌ |
| hr-lead | hr | manager | hr-lead@blitz.local | HR123! | ✅ |
| hr-specialist | hr | employee | hr-specialist@blitz.local | HR123! | ✅ |
| financial-lead | financial | manager | financial-lead@blitz.local | Finance123! | ✅ |
| financial-analyst | financial | employee | financial-analyst@blitz.local | Finance123! | ✅ |

**Note:** All passwords are temporary and must be changed on first login.

---

## 🔐 Clients (Applications)

### blitz-portal

**Purpose:** Main Blitz portal application  
**Redirect URIs:** https://portal.lumiaitech.com/*  
**Access Type:** Confidential  
**Flows:** Standard (OIDC), Direct Access Grants  

**Scopes:** web-origins, acr, roles, profile, email, groups

### blitz-odoo

**Purpose:** Odoo 18 unified backend integration (tickets, projects, timesheets, knowledge base)
**Redirect URIs:** https://odoo.lumiaitech.com/*
**Access Type:** Confidential
**Flows:** Standard (OIDC)

**Claim Mappers:**
- email → email
- given_name → firstName
- family_name → lastName (REQUIRED)
- preferred_username → username
- groups → groups (used by mcp_auth addon for Odoo role mapping)

### blitz-huly *(deprecated 2026-02-19, see Epic 13)*

> **DEPRECATED:** This client is no longer active. Huly has been replaced by Odoo 18. Retained for reference until Epic 13 cleanup completes.

**Purpose:** ~~Huly project management integration~~
**Status:** Deprecated — do not configure for new environments

**⚠️ Warning:** Huly OpenID has known bugs (GitHub #88, #94, #252). Use Shadow Registry pattern for production.

### blitz-kimai *(deprecated 2026-02-19, see Epic 13)*

> **DEPRECATED:** This client is no longer active. Kimai has been replaced by Odoo 18. Retained for reference until Epic 13 cleanup completes.

**Purpose:** ~~Kimai time tracking integration~~
**Status:** Deprecated — do not configure for new environments

---

## 🔧 Configuration Details

### Environment Variables

Key variables in `.env.local`:

```bash
# Realm Configuration
KEYCLOAK_REALM=blitz-internal
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/blitz-internal/protocol/openid-connect/certs
KEYCLOAK_ISSUER=http://keycloak:8080/realms/blitz-internal

# Client Secrets
BLITZ_PORTAL_CLIENT_SECRET=blitz-portal-secret
BLITZ_ODOO_CLIENT_SECRET=blitz-odoo-secret

# Deprecated client secrets (retained for Epic 13 cleanup reference)
# BLITZ_HULY_CLIENT_SECRET=blitz-huly-secret  # deprecated 2026-02-19
# BLITZ_KIMAI_CLIENT_SECRET=blitz-kimai-secret  # deprecated 2026-02-19
```

### MFA Configuration

**Conditional MFA Flow:**
- Required for: it-admin, hr-*, financial-*
- Optional for: All others

Configured in realm authentication flows using conditional OTP based on realm roles.

---

## 📋 Management Commands

### Reset Keycloak (Fresh Bootstrap)

```bash
./scripts/blitz-keycloak-reset.sh
```

### Stop Services

```bash
just shared-down
# or
docker compose -f infrastructure/shared/docker-compose.shared.yml down
```

### Start Services

```bash
just shared-up
# or
docker compose -f infrastructure/shared/docker-compose.shared.yml up -d
```

### View Logs

```bash
# Keycloak
docker logs -f hox-aa-keycloak

# Database
docker logs -f hox-aa-keycloak-db
```

### Access Database

```bash
docker exec -it hox-aa-keycloak-db psql -U keycloak -d keycloak
```

---

## 🔍 Troubleshooting

### Issue: "Unknown authentication strategy 'oidc'" in Huly *(deprecated — Huly removed 2026-02-19)*

**Cause:** Huly bug (GitHub #88, #94) — no longer applicable as Huly has been replaced by Odoo 18.
**Solution:** N/A — migrate to Odoo OIDC integration via blitz-odoo client

### Issue: last_name null constraint

**Cause:** Keycloak user missing lastName  
**Solution:** Ensure all users have both firstName and lastName set

### Issue: Cannot access Keycloak

**Cause:** Cloudflare tunnel not running or misconfigured
**Solution:** Check `cloudflared` is running and tunnel routes are configured for `keycloak.lumiaitech.com`

### Issue: Keycloak admin console keeps spinning

**Cause:** `KC_HOSTNAME_URL` doesn't match the browser URL
**Solution:** Ensure `KC_HOSTNAME_URL=https://keycloak.lumiaitech.com` in docker-compose

### Issue: Realm not imported

**Cause:** Keycloak database not empty  
**Solution:** Run `./scripts/blitz-keycloak-reset.sh` to wipe and re-import

---

## 🏗️ Architecture Decisions

### Why Single Realm?

- **Simplicity:** One identity for all internal apps
- **SSO:** Seamless login across Portal, Odoo
- **Centralized Policy:** Single MFA, password policy
- **Manageable:** 40 employees don't need realm separation

### Future: Multi-Tenancy

If Blitz becomes SaaS provider:

```
Realm 1: blitz-internal (employees)
Realm 2: blitz-customers (external clients)
   Groups: /tenant-a, /tenant-b
```

Keep realms per trust boundary, not per team.

---

## 📝 Next Steps

1. **Test Login:** Access https://portal.lumiaitech.com and login as admin
2. **Setup MFA:** Configure TOTP for admin account (required)
3. **Add More Users:** Use Keycloak Admin Console
4. **Start Other Services:**
   ```bash
   just odoo-up      # Start Odoo (replaces Huly + Kimai as of 2026-02-19)
   just hox-up       # Start Portal
   ```
5. **Configure Apps:** Update app configs to use blitz-internal realm
6. **Production Prep:**
   - Change all default passwords
   - Generate secure client secrets
   - Setup proper SSL certificates
   - Enable production Keycloak mode (not start-dev)

---

## 📚 References

- **Keycloak Docs:** https://www.keycloak.org/documentation
- **OIDC Spec:** https://openid.net/specs/openid-connect-core-1_0.html
- **Odoo MCP Server Guide:** `docs/odoo/odoo-mcp-server-guide.md`
- **Blitz Realm Config:** `infrastructure/shared/keycloak/realms/blitz-internal-realm.json`
- **Environment Template:** `.env.example`

---

## 💡 Tips

1. **Use Groups for Teams:** Easier to manage than individual role assignments
2. **Client Roles for Apps:** Each app defines its own roles (portal-user, portal-admin)
3. **Realm Roles for Org:** Use for org-wide permissions (manager, executive)
4. **Test in Dev:** Always test changes in dev before production
5. **Backup Realm:** Export realm config periodically: `kc.sh export --realm blitz-internal`

---

**Questions?** Check the bootstrap script or Keycloak Admin Console at https://keycloak.lumiaitech.com/admin
