---
created: 2026-03-05T00:17:42.593Z
title: Stack initialization wizard for multi-platform deployment
area: tooling
files: []
---

## Problem

Currently, deploying Blitz AgentOS requires manual setup of Docker Compose, environment variables, database migrations, Keycloak realm import, LiteLLM config, and service health checks. There is no guided provisioning flow for administrators deploying the stack to a new environment. As the product matures, it needs to support multiple deployment targets beyond the current Docker Compose MVP.

## Solution

Build a stack initialization wizard (CLI or web-based) that guides an administrator through complete provisioning and setup for their target platform:

**Target platforms:**
- Docker Compose (current MVP — formalize as wizard)
- Docker Swarm (multi-node, overlay networking)
- Dokploy (self-hosted PaaS)
- Kubernetes (vanilla k8s / k3s)
- Azure (AKS + Azure services)
- AWS (EKS + AWS services)
- Google Cloud (GKE + GCP services)

**Wizard should handle:**
1. Platform selection and prerequisite checks
2. Secrets generation (DB passwords, JWT keys, encryption keys)
3. Infrastructure provisioning (IaC templates per platform)
4. Service deployment with health verification
5. Keycloak realm + client setup
6. Database migration execution
7. LiteLLM model routing configuration
8. Smoke test / validation suite

**Priority:** This should be one of the last tasks — after the core solution is feature-complete and stable. The wizard codifies the deployment knowledge accumulated during development.

**Brainstorming candidate:** Needs `/superpowers:brainstorming` to evaluate CLI vs web wizard, IaC tool choice (Terraform/Pulumi/Helm), and per-platform trade-offs.
