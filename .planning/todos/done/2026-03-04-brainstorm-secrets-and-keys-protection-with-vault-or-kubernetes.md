---
created: 2026-03-04T16:57:28.816Z
title: Brainstorm secrets and keys protection with Vault or Kubernetes
area: auth
files: []
---

## Problem

The current stack stores secrets (API keys, DB passwords, OAuth tokens, encryption keys) in `.env` files and AES-256 encrypted DB columns. CLAUDE.md explicitly defers HashiCorp Vault to post-MVP (ADR-008). As the platform matures beyond MVP toward production deployment, we need a proper secrets management strategy that covers:

- Service-to-service credentials (DB, Redis, LiteLLM, Keycloak)
- User credential vault (currently AES-256 in PostgreSQL)
- LLM API keys (Anthropic, OpenAI, OpenRouter)
- Encryption key rotation (KMS key for AES-256 vault)
- Certificate management (Keycloak TLS, mTLS between services)

## Solution

Brainstorm session needed to evaluate:

1. **HashiCorp Vault** — dedicated secrets engine, dynamic credentials, auto-rotation, audit trail. Could replace `.env` files and DB-stored encrypted credentials.
2. **Kubernetes Secrets + External Secrets Operator** — if moving to K8s, use ESO to sync from Vault/AWS SSM/Azure Key Vault into K8s secrets.
3. **Hybrid approach** — Vault for credential lifecycle management, K8s for runtime injection.
4. **Scope decision** — what stays in DB (user OAuth tokens) vs what moves to Vault (service credentials, API keys).

This is a `/superpowers:brainstorming` candidate — needs structured evaluation of trade-offs before any implementation planning.
