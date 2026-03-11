# AgentOS — Sales & Marketing Materials Pack

> **For internal use:** Sales team, pre-sales engineers, and executive presentations.
> Last updated: 2026-03-10. All claims are factual and tied to shipped capabilities.

---

## 1. Elevator Pitches

### 15-Second Pitch

**AgentOS** is the enterprise operating system for AI agents — on-premise, LLM-agnostic, and built for organizations that can't afford to send their data to the cloud. While tools like Copilot or ChatGPT are built for individual productivity, AgentOS is the platform that lets enterprises deploy, govern, and connect AI agents across every department, with the security controls and audit trails that IT and compliance teams actually require.

---

### 1-Minute Pitch

Every enterprise is being told to "adopt AI" — but the tools on the market were designed for individual users, not organizations. ChatGPT, Copilot, Notion AI: these are personal productivity tools, not enterprise infrastructure. When a company tries to use them at scale, they immediately hit three walls: data leaves the organization, there's no governance or audit trail, and IT can't control who accesses what.

**AgentOS** is the answer. It's a full enterprise platform — not another AI chat tool — that lets you deploy AI agents entirely on your own infrastructure. Your data never leaves. Your LLMs run locally via Ollama if needed. Every action is logged, every role is controlled, every credential is encrypted at rest.

What makes it different is the platform architecture: a visual workflow canvas for building agent automations, a hierarchical memory system with per-user isolation, multi-channel delivery to Telegram, Teams, and WhatsApp, and an MCP integration layer that connects agents to your real enterprise systems.

If you're serious about AI in the enterprise — not a pilot, but production deployment at scale — we should talk. A full stack runs on Docker Compose and can be live on your infrastructure in under a day.

---

### 3-Minute Pitch

Let me start with where AI has been and where it's going.

**Phase one was prompt engineering.** You learned how to ask ChatGPT the right question. That was useful, but it was still a conversation — human-in-the-loop every step of the way.

**Phase two was context engineering.** Tools like Cursor, Notion AI, and Copilot learned to inject your documents, your code, your calendar into the prompt. Better results, same paradigm: the AI waits for a human to ask.

**Phase three — where we are now — is agentic AI.** Agents don't wait. They plan, they take actions, they call tools, they loop. An agent can read your emails, update your CRM, draft a summary, and send it to Slack before you finish your morning coffee. This is the shift that changes everything.

Here's the problem: every agentic AI tool on the market today was built for individuals. ChatGPT's operator features. Anthropic's Claude Projects. Cursor for developers. These are exceptional personal tools. But when an enterprise tries to use them at scale, four things break immediately:

First, **data sovereignty**. Every prompt, every document, every customer record goes to a third-party cloud. For regulated industries — finance, healthcare, government — this is a non-starter.

Second, **governance**. Who authorized that agent to access the CRM? Which tools can the HR agent use? What did it do last Tuesday at 3pm? No audit trail, no controls, no answer.

Third, **memory and continuity**. Consumer AI has no institutional memory. Every conversation starts cold. Agents that can't remember context across sessions aren't agents — they're chatbots.

Fourth, **integration**. Enterprise workflows touch dozens of systems: ERP, CRM, ITSM, email, calendar, BI. Consumer AI tools don't connect to any of them in a controlled, secure way.

**AgentOS** was built to solve exactly these four problems. It's not a tool — it's a platform. Think of it the way you think about an operating system: the OS doesn't do your work for you, but it makes it possible for all your applications to run safely, with access to shared resources, under a governance model you control.

Three things make AgentOS genuinely different:

**One: complete data sovereignty.** AgentOS runs entirely on your infrastructure — Docker Compose, your servers, your network. With Ollama integration, not a single token has to leave your organization. No cloud LLM required.

**Two: enterprise-grade security from the ground up.** Keycloak SSO, three-layer security on every agent action (JWT validation, RBAC roles, per-tool ACL), AES-256 encrypted credentials, full audit logs in structured JSON ready for your SIEM. This isn't bolted on — it's architectural.

**Three: a true platform with a visual canvas.** Non-technical users can build agent workflows using the low-code canvas without writing code. A workflow that pulls emails, checks the calendar, queries the CRM, and delivers a formatted brief to Telegram every morning at 7am — built in 20 minutes, running autonomously every day thereafter.

Here's a concrete example. One of the first workflows we built internally: an executive morning digest. Every day at 7am, an agent chain wakes up, reads the last 24 hours of unread email, pulls the day's calendar, checks open project statuses, and delivers a formatted summary to Telegram. No engineer touches it after setup. It runs on local infrastructure, all data stays internal, and the full execution log is available for audit. That's the power of the platform.

We can have AgentOS running on your infrastructure this week. Docker Compose deployment, under a day from zero to live. The question isn't whether your organization needs this — it does. The question is whether you build it yourself over the next 18 months, or whether you deploy a production-ready platform today.

What does your timeline look like?

---

## 2. Executive One-Pager

---

### THE CHALLENGE

- **Data is leaving the building.** Every time an employee uses ChatGPT, Copilot, or any cloud AI tool with business data, that data transits third-party infrastructure — outside your DLP controls, outside your compliance boundary, outside your visibility.
- **Shadow AI is already here.** Your people are using AI tools with or without IT approval. Without a governed platform, you have no audit trail, no access controls, and no way to stop credential or data leakage.
- **Enterprise AI has a governance gap.** Existing AI tools have no RBAC, no per-tool ACLs, no institutional memory, and no integration with your systems of record. You cannot run an enterprise on individual productivity tools.

---

### THE SOLUTION

**AgentOS** is the enterprise operating system for AI agents — a full platform that runs entirely on your infrastructure, connects to your enterprise systems, and puts your IT and security teams in complete control. Unlike point tools (Copilot, Agentforce, ChatGPT Enterprise), AgentOS is the layer beneath the agents: it governs what they can do, what data they can access, and what they remember, across your entire organization.

---

### KEY CAPABILITIES

| | |
|---|---|
| **Visual Workflow Canvas** — Build agent automations without code using the low-code canvas. Drag, connect, deploy. | **Hierarchical Memory** — Per-user isolated short, medium, and long-term memory with semantic search. Agents remember context across sessions. |
| **Enterprise Security** — Keycloak SSO, 3-layer security gates (JWT + RBAC + ACL), AES-256 credential encryption, full audit logs. | **Local LLM Support** — Run entirely on Ollama with no cloud LLM dependency. Or use Claude/GPT via LiteLLM proxy. Your choice. |
| **MCP Integration Layer** — Connect agents to CRM, ERP, ITSM, and any enterprise system via the Model Context Protocol. | **Multi-Channel Delivery** — Deliver agent outputs to Telegram, WhatsApp, or Microsoft Teams. Agents reach users where they work. |

---

### WHY AGENTOS IS DIFFERENT

**🔒 Data Sovereignty — Absolute**
Your data never leaves your infrastructure. Not a design goal — an architectural guarantee. Local LLMs, on-premise deployment, no third-party data processing.

**🏗️ Platform, Not a Tool**
AgentOS is the OS layer for your AI agents. One platform governs all agents, all tools, all credentials, and all memory — not a collection of siloed point solutions.

**🛡️ Security Built In, Not Bolted On**
Three security gates on every agent action. No tool executes without passing JWT validation, RBAC permission check, and per-tool ACL. Your CISO gets complete control.

---

### PROVEN VALUE DRIVERS

- **Hours recovered per executive per week** — Autonomous digests, briefings, and status reports eliminate manual aggregation work.
- **Compliance risk reduced** — Every agent action logged, every credential encrypted, every access controlled. Audit-ready from day one.
- **LLM cost controlled** — Local Ollama models eliminate per-token cloud LLM costs for internal workloads.
- **AI projects that actually ship** — Visual canvas means business teams build and iterate without waiting for engineering cycles.

---

### DEPLOYMENT

**Simple. On-premise. Under a day.**
AgentOS runs on Docker Compose — your servers, your network, your control. No SaaS onboarding, no cloud accounts, no vendor access to your environment. A standard deployment is live in under 8 hours.

---

### GET STARTED

**Contact:** [sales@blitz.ai] | [Schedule a demo: calendly.com/blitz-agentos]

*AgentOS — The Enterprise AI Operating System. On your terms.*

---

## 3. Battle Cards

### Battle Card 1: AgentOS vs. Microsoft Copilot Studio

**Their Pitch**
"Copilot Studio is the enterprise-grade AI platform from Microsoft, natively integrated with your Microsoft 365 environment, built on Azure AI, with Power Platform connectors for all your enterprise systems."

**Their Strengths (be honest)**
- Deep M365 integration: Teams, SharePoint, Outlook, Power BI — native connectors that work.
- Massive brand trust and existing procurement relationships.
- Azure compliance certifications (SOC 2, ISO 27001, FedRAMP) carry weight with enterprise security teams.
- Power Platform ecosystem means non-technical users can extend it.
- Strong partner network and support infrastructure.

**Their Critical Weaknesses**
- **Data sovereignty is impossible.** All processing happens in Azure. For EU GDPR, FINRA, HIPAA, or sovereign data mandates, the fundamental architecture doesn't comply — regardless of what the MSA says.
- **You rent their infrastructure.** When Azure has an outage, your AI agents go down. You have no on-premise fallback.
- **LLM lock-in.** Copilot Studio is built on Azure OpenAI. You cannot swap to Anthropic, a local model, or a cost-optimized alternative without leaving the platform.
- **Per-user seat pricing compounds fast.** At scale across an org, the cost structure is opaque and grows with headcount, not with value delivered.
- **No local LLM support.** Running sensitive inference on-premise without sending data to OpenAI's API is not a supported path.
- **Audit logs stay in Azure.** Your audit data is in Microsoft's cloud, not on your SIEM.

**Our Counter**
AgentOS runs on your infrastructure — literally your servers, your network closet, your air-gapped environment if needed. With Ollama, not a single token goes to any cloud provider. We pass every data sovereignty audit because the data never leaves. When we say "on-premise," we mean it architecturally, not contractually.

**Killer Question**
"When your security team does a data flow audit, can they confirm that no prompt data — including the text from your documents and emails — ever transits Microsoft's Azure infrastructure? And can they independently verify that, without relying on Microsoft's attestation?"

**When We Win**
- Regulated industries with genuine data residency requirements (finance, healthcare, government, defense).
- Organizations with EU GDPR or sovereign cloud mandates.
- Teams that want local LLM to eliminate cloud AI costs.
- Prospects who've been burned by Azure outages affecting productivity tools.

**When We Lose**
- Organizations already deeply committed to Microsoft stack with no compliance pressure.
- Teams where "good enough in Teams" is the actual decision criteria.
- Buyers with existing EA that includes Copilot at no incremental cost.

---

### Battle Card 2: AgentOS vs. Salesforce Agentforce

**Their Pitch**
"Agentforce is Salesforce's AI platform that puts autonomous agents directly inside your CRM, with Atlas Reasoning Engine, native access to all your Salesforce data, and pre-built agent templates for sales, service, and marketing teams."

**Their Strengths (be honest)**
- If you live in Salesforce, the integration is genuinely seamless — no connectors to build.
- Salesforce has 20+ years of enterprise trust and compliance credibility.
- Pre-built agent templates (Sales Coach, Service Agent) lower time-to-value for Salesforce-native workflows.
- Einstein data layer means agents have deep contextual access to CRM data.
- Strong partner ecosystem for implementation.

**Their Critical Weaknesses**
- **CRM-centric, not enterprise-wide.** Agentforce agents live inside Salesforce. Anything outside Salesforce — ERP, ITSM, internal docs, email systems outside of Salesforce Inbox — requires significant custom work.
- **Your data goes to Salesforce's cloud.** All inference, all context, all agent memory lives in Salesforce infrastructure. On-premise is not an option.
- **Consumption-based pricing can be brutal.** Agentforce charges per conversation. High-volume automation workflows become expensive fast.
- **Not LLM-agnostic.** Salesforce controls the LLM layer. You cannot substitute a local model or a cheaper alternative.
- **No multi-channel delivery.** Agentforce outputs stay in Salesforce channels. Delivering to Telegram, WhatsApp, or custom enterprise systems requires custom development.
- **Governance is Salesforce-native only.** IT teams outside the Salesforce admin model have limited visibility and control.

**Our Counter**
AgentOS is enterprise-wide from day one. It connects to CRM, ERP, ITSM, email, calendar, and any system via the MCP integration layer. Agents operate across your entire tech stack, not inside a single vendor's ecosystem. And when your CRM is down, your agents keep running.

**Killer Question**
"How does Agentforce handle agent workflows that need to touch systems outside Salesforce — like your ERP for order data, or your ITSM for ticket creation? And what does that custom integration cost and maintain over time?"

**When We Win**
- Organizations with complex multi-system workflows (CRM + ERP + ITSM + internal docs).
- Teams outside of sales and service functions where Agentforce has weak templates.
- Prospects concerned about per-conversation pricing at scale.
- Any organization with data sovereignty requirements Salesforce cloud cannot meet.

**When We Lose**
- Salesforce-first organizations where the CRM is the center of gravity for all workflows.
- Prospects who want vendor-provided pre-built agent templates and minimal setup.
- Buyers with existing Salesforce contracts that include Agentforce at low incremental cost.

---

### Battle Card 3: AgentOS vs. ServiceNow AI Agents

**Their Pitch**
"ServiceNow AI Agents bring autonomous AI to the Now Platform, automating complex ITSM, HR, and operations workflows with deep integration into the ServiceNow data model and industry-leading enterprise workflow capabilities."

**Their Strengths (be honest)**
- If the buyer is already on ServiceNow, the Now Platform integration is the most mature workflow automation layer in enterprise IT.
- Strong ITSM, HRSD, and operations use case library — these aren't demos, they're production-proven.
- Enterprise compliance credentials are exceptional. SOC 2 Type II, FedRAMP High, HIPAA — genuinely strong.
- ServiceNow's professional services bench is deep for complex implementations.
- IT buyers trust ServiceNow more than almost any other vendor.

**Their Critical Weaknesses**
- **ServiceNow is the perimeter.** AI agents operate within the ServiceNow world. Anything outside — your internal docs, your Slack, your custom internal tools — is not native territory.
- **Total cost of ownership is very high.** ServiceNow licenses, AI add-ons, and implementation costs combine into one of the most expensive enterprise software relationships in the market.
- **Not for non-IT use cases.** Finance, marketing, and operations teams don't naturally live in ServiceNow. Building cross-functional agent workflows requires the ServiceNow ITSM team to be the integration owner — organizational friction.
- **All data goes to ServiceNow cloud.** On-premise deployments exist but are legacy and not where the AI investment is going.
- **LLM is theirs, not yours.** The Now Intelligence LLM layer is not swappable.
- **No local LLM path.** Inferencing on your hardware is not on the roadmap.

**Our Counter**
AgentOS is not ITSM-centric. It's a horizontal platform that covers every department — IT, Finance, HR, Operations, Sales — with the same security controls and audit trail. And it costs a fraction of what ServiceNow charges before implementation fees even begin.

**Killer Question**
"When your Finance team or your Operations team wants to build AI agent workflows, does your ServiceNow implementation team become the bottleneck? And what's the full platform + implementation cost for a cross-functional deployment?"

**When We Win**
- Organizations where AI use cases span multiple departments outside of ITSM.
- Buyers experiencing ServiceNow licensing fatigue or cost overruns.
- Any prospect where TCO is under scrutiny.
- Teams that want business users (not just IT admins) to build and own agent workflows.

**When We Lose**
- Pure ITSM-focused buyers where ServiceNow owns 90% of the relevant workflow.
- Organizations with existing ServiceNow contracts that include AI features at no additional license cost.
- Enterprises where IT team drives all AI decisions and ServiceNow is already the incumbent.

---

### Battle Card 4: AgentOS vs. "Build Your Own" (Internal AI Team with LangChain/LangGraph)

**Their Pitch**
"We have strong engineers. We'll build exactly what we need using open-source frameworks, avoid vendor lock-in, and control the entire stack."

**Their Strengths (be honest)**
- Maximum flexibility — a well-resourced team can build anything.
- No vendor dependency or license risk.
- Engineers who understand the codebase deeply can debug and extend it.
- Open-source components (LangGraph, LangChain) have strong communities.
- For organizations with genuine AI engineering depth, custom builds can be well-tuned to specific needs.

**Their Critical Weaknesses**
- **Timeline is the killer.** Building enterprise-grade agent infrastructure from scratch — security gates, memory isolation, audit logging, RBAC, credential management, scheduler, multi-channel delivery — takes 12 to 24 months for a competent team. The business waits the entire time.
- **The "glue code" problem.** Every enterprise integration, every edge case in the security model, every production stability issue becomes engineering debt that compounds. The team ends up maintaining infrastructure instead of building business value.
- **Security is not a feature, it's a discipline.** JWT + RBAC + per-tool ACL + AES-256 credential encryption + audit logging is not two sprints. Organizations that underestimate this ship agents with security holes.
- **Talent retention risk.** The senior engineer who built the memory isolation layer leaves. Now who maintains it?
- **Total cost is not zero.** Engineering time at market rates for 2-3 senior engineers over 18 months costs more than most commercial platforms. And the commercial platform ships in a week.
- **The framework gap.** LangGraph gives you the orchestration primitives. It does not give you the enterprise platform: the admin console, the visual canvas, the RBAC admin, the audit log viewer, the scheduler management — all of this must be built.

**Our Counter**
AgentOS is built on LangGraph. We're not competing with the framework — we're the enterprise layer on top of it. Your engineers can extend AgentOS, build custom tools, and write custom agents using the same primitives they already know. The difference is they start from a production-ready, security-audited platform instead of from zero. They spend their time on your business problems, not on re-solving credential encryption.

**Killer Question**
"If your team builds this from scratch, what's the projected timeline to production with full audit logging, RBAC-controlled tool access, AES-256 credential management, and a UI for non-technical workflow builders? And what's the engineering cost to reach that milestone?"

**When We Win**
- Teams that have underestimated the scope of what "build your own" actually means.
- Buyers who've started a build and are 6 months in with a working demo but no production security layer.
- Engineering leaders who want their team focused on product, not platform infrastructure.
- Organizations where time-to-value matters and an 18-month build timeline is unacceptable.

**When We Lose**
- Organizations with a mature, well-staffed AI platform team that has already shipped production agents with proper security.
- Companies where the "not invented here" culture is genuinely a cultural value, not just default inertia.
- Buyers with a philosophical commitment to open-source-only stacks and the patience to build.

---

## 4. Pitch Deck Outline

### Slide 1: Title / Agenda

**Title:** AgentOS — The Enterprise AI Operating System
**Key Message:** We're going to show you why the AI tools your teams are already using are the wrong category of product for enterprise deployment — and what the right answer looks like.

**Content:**
- Company logo / product name
- Tagline: "AI agents. On your terms."
- Agenda: 5-minute problem framing | 5-minute solution overview | 10-minute live demo | 5-minute Q&A | 5-minute next steps

**Speaker Notes:**
Open by asking: "Quick show of hands — how many of you have employees using ChatGPT or Copilot for work today?" Let the hands go up. Then: "Keep your hand up if your security team has full visibility into what data those tools are processing." Pause for effect. "That's what we're here to talk about."

---

### Slide 2: The AI Revolution Is Entering a New Phase

**Key Message:** We are at the inflection point between AI as a tool and AI as autonomous infrastructure — and most enterprises are still optimizing for the previous phase.

**Content:**
- Timeline: Phase 1 (2022–2023) → Prompt Engineering: "Ask better questions"
- Phase 2 (2023–2025) → Context Engineering: "Give it your documents"
- Phase 3 (2025–now) → Agentic AI: "Set it running and it acts"
- Visual: progression from human-in-loop → human-on-loop → human-off-loop
- Key stat: "Agentic AI tasks can save 4–8 hours per knowledge worker per week"

**Speaker Notes:**
Make this narrative, not a list. "In 2022, everyone was learning prompt engineering. In 2023, tools started injecting context. In 2025, the paradigm shifted: agents don't wait to be asked. They plan, they act, they iterate. The question is no longer how to use AI — it's how to govern it."

---

### Slide 3: The Problem — AI Tools Were Built for Individuals

**Key Message:** Every major AI tool on the market was designed for individual productivity — not for enterprise governance, not for multi-user isolation, and not for organizational scale.

**Content:**
- Column 1: Consumer / Individual Tools — ChatGPT, Claude, Cursor, Notion AI, Copilot
- Column 2: What they're great at — personal productivity, single-user context, fast answers
- Column 3: What they lack — RBAC, audit logs, credential management, memory isolation, institutional governance
- Visual: a single person vs. an org chart — "one was designed for this person, not this organization"

**Speaker Notes:**
"The tools that got every CXO excited in the pilot — ChatGPT, Copilot — were designed for one user at a desk. That's fine for a demo. It's a liability for a production deployment at 500 users. Let me show you exactly what breaks."

---

### Slide 4: The Enterprise AI Dilemma

**Key Message:** Enterprises face a three-sided trap: their people are already using AI, IT can't govern it, and security can't audit it.

**Content:**
- Problem 1: **Data Sovereignty** — prompts with business data leave the organization with every query
- Problem 2: **Shadow AI** — employees use unapproved tools because approved alternatives don't exist
- Problem 3: **Governance Gap** — no audit trail, no per-user memory isolation, no tool-level access control
- Problem 4: **Integration Reality** — real workflows touch 5–10 systems; consumer AI connects to none of them securely
- Pull quote: "You can't run an enterprise on a tool that has no RBAC."

**Speaker Notes:**
"Here's the trap: if you ban AI tools, your best people will use them anyway and just hide it. If you approve them without governance, you've accepted an audit finding before the pen tester even shows up. The only path forward is a governed platform."

---

### Slide 5: Introducing AgentOS — The Enterprise AI Operating System

**Key Message:** AgentOS is not another AI tool — it is the platform layer that makes enterprise agentic AI possible: governed, secure, on-premise, and extensible.

**Content:**
- Definition: "AgentOS is the operating system for your AI agents. Just as a server OS lets multiple applications share hardware safely, AgentOS lets multiple agents share enterprise resources — data, credentials, tools, and memory — safely."
- Three words: **On-premise. Governed. Platform.**
- Key capability snapshot: Visual Canvas | Memory | Security | Local LLM | MCP Integration | Multi-Channel
- Deployment: Docker Compose — runs on your hardware, under your control

**Speaker Notes:**
"The name is deliberate. An operating system doesn't do your work — it creates the conditions for your applications to do their work safely. AgentOS does the same for AI agents. Every agent runs under the same security model, uses the same memory layer, and is governed by the same RBAC rules."

---

### Slide 6: How AgentOS Works — Architecture in Three Layers

**Key Message:** Three layers — Security, Runtime, and Integration — work together so every agent action is governed, auditable, and isolated.

**Content:**

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                     │
│  Visual Canvas (workflow builder) | Chat UI | Admin     │
│  Multi-Channel: Telegram, WhatsApp, Microsoft Teams     │
├─────────────────────────────────────────────────────────┤
│  AGENT RUNTIME                                          │
│  Master Agent (LangGraph) | Sub-agents (Email, Cal...)  │
│  Celery Scheduler | Skill Registry | Memory System      │
│  Short-term | Medium-term | Long-term (pgvector)        │
├─────────────────────────────────────────────────────────┤
│  SECURITY & GOVERNANCE LAYER                            │
│  Gate 1: JWT (Keycloak SSO)                             │
│  Gate 2: RBAC (role → permission mapping)               │
│  Gate 3: Tool ACL (per-user, per-tool access)           │
│  AES-256 Credential Vault | Structured Audit Logs       │
├─────────────────────────────────────────────────────────┤
│  INTEGRATION LAYER                                      │
│  LiteLLM Proxy (Ollama / Claude / GPT / any LLM)        │
│  MCP Servers (CRM, ERP, ITSM, Docs)                     │
│  Docker Sandbox (safe code execution)                   │
└─────────────────────────────────────────────────────────┘
```

**Speaker Notes:**
"Walk them through bottom-up: 'Everything that happens — every agent action — passes through the security layer first. There is no bypass. Then the runtime executes the work. Then results are delivered through whatever channel the user is in.' This architecture is what makes 'enterprise-grade' a real claim, not a marketing label."

---

### Slide 7: The Platform Difference — Tool vs. OS

**Key Message:** The right analogy is not "better AI tool" — it is "infrastructure vs. application." AgentOS is to AI agents what Linux is to applications.

**Content:**
- Left column — **The Tool Paradigm:** One-off integrations | Per-tool credentials | No shared memory | No central governance | Each agent is an island
- Right column — **The Platform Paradigm (AgentOS):** Shared security layer | Centralized credential vault | Institutional memory across agents | Single RBAC model | Agents collaborate through shared context
- Visual metaphor: "Running AI tools is like running applications without an OS — possible, fragile, and ungovernable at scale."
- Business outcome: "With AgentOS, adding a new AI capability is configuration, not an engineering project."

**Speaker Notes:**
"Here's the test question: if you add a 10th AI agent to your environment today, does your governance overhead grow by 10x, or is it already handled? With a platform, it's already handled. That's the difference."

---

### Slide 8: Key Capabilities — Six Pillars

**Key Message:** Six capabilities combine to make AgentOS the complete enterprise AI operating system — each one addresses a specific failure mode of tool-based approaches.

**Content:**

| Capability | What It Does | Why It Matters |
|---|---|---|
| **Visual Workflow Canvas** | Low-code builder for agent workflows; drag, connect, deploy | Business teams ship automations without engineering sprints |
| **Hierarchical Memory** | Per-user short/medium/long-term memory with semantic search | Agents remember across sessions; institutional knowledge compounds |
| **3-Layer Security** | JWT + RBAC + Tool ACL on every agent action | No tool executes without authorization; zero bypass paths |
| **Local LLM Support** | Ollama integration; no cloud LLM required | Full sovereignty; eliminate cloud AI token costs |
| **MCP Integration** | Model Context Protocol adapters for CRM, ERP, ITSM | Agents operate on real enterprise data, not sandboxed demos |
| **Autonomous Scheduler** | Celery-based; recurring jobs run as job owner | Workflows run on schedule without human trigger; access controls apply |

**Speaker Notes:**
"Don't read the table. Pick two or three that are most relevant to this particular buyer's pain points. For a CISO: lead with security. For a COO: lead with canvas and scheduler. For a CTO: lead with MCP and local LLM."

---

### Slide 9: Live Demo Scenarios

**Key Message:** This isn't a mockup — this is running on local infrastructure right now, with no cloud connection.

**Content (three use cases to choose from based on audience):**

**Demo A — Data Sovereignty Proof (for CISOs)**
Show Ollama running locally, network monitor showing zero external API calls, full audit log of agent actions. Message: "Your data never left this room."

**Demo B — Morning Digest Workflow (for COOs/Business Leaders)**
Show workflow canvas with scheduler set to 7am, agent chain pulling email + calendar + project status, delivering formatted brief to Telegram. Message: "This runs every morning for every executive, without any engineer involved."

**Demo C — Admin Control Center (for IT Admins)**
Show Keycloak SSO login, RBAC role management, tool ACL configuration, audit log with full action history, AES-256 credential panel. Message: "Your security team gets complete control and full visibility. No exceptions."

**Speaker Notes:**
"Always do a live demo, never a video. The live demo on local hardware is itself a proof of concept — if they can see it running on a laptop with no internet, they believe the on-premise story. Ask the room before starting: 'Which of these three scenarios is most relevant to what you're evaluating?' Let them choose."

---

### Slide 10: Security & Compliance

**Key Message:** AgentOS was designed with a security-first architecture — not as a feature added after the fact.

**Content:**

**Authentication & Identity**
- Keycloak SSO (SAML 2.0 / OIDC) — integrates with your existing IdP
- JWT-based session management, tokens in memory only (XSS protection)

**Authorization**
- RBAC with Keycloak role mapping
- Per-tool, per-user ACL table — every tool access is explicitly authorized or denied

**Data Protection**
- AES-256 encrypted credential storage — no plain-text credentials anywhere in the system
- Credentials never passed to LLM prompts — tool resolves internally from vault

**Audit & Compliance**
- Structured JSON audit logs (structlog) — Loki/Splunk/SIEM-ready
- Every tool call logged: user_id, tool name, access decision, duration, timestamp
- Per-user memory isolation: `WHERE user_id = ?` enforced at every query

**Deployment Security**
- On-premise: your network perimeter, your firewall rules
- Docker Compose: reproducible, auditable deployment
- No vendor access to your environment — ever

**Speaker Notes:**
"Hand this slide to the CISO and let them read it. Then ask: 'What's on your checklist that you don't see here?' This slide is intentionally dense — it's designed to be reviewed, not presented."

---

### Slide 11: Competitive Comparison

**Key Message:** AgentOS is the only enterprise AI platform that combines on-premise deployment, LLM-agnosticism, and true platform governance in a single product.

**Content:**

| Feature | **AgentOS** | Copilot Studio | Agentforce | ServiceNow AI | Build Your Own |
|---|---|---|---|---|---|
| On-premise deployment | ✅ Yes | ❌ Azure only | ❌ Salesforce cloud | ❌ Cloud | ✅ (18+ months) |
| Local LLM (no cloud) | ✅ Ollama native | ❌ | ❌ | ❌ | ✅ (build it) |
| Visual workflow canvas | ✅ Built-in | ✅ Power Automate | ⚠️ Limited | ✅ ServiceNow | ❌ Build it |
| 3-layer security gates | ✅ Architectural | ⚠️ App-level | ⚠️ App-level | ✅ Strong | ❌ Build it |
| LLM-agnostic | ✅ Any via LiteLLM | ❌ Azure OpenAI | ❌ Salesforce | ❌ Now Intelligence | ✅ (build it) |
| Multi-system MCP integration | ✅ Built-in | ⚠️ Connectors | ❌ Salesforce only | ⚠️ Now Platform | ✅ (build it) |
| Per-user memory isolation | ✅ pgvector | ❌ | ❌ | ❌ | ✅ (build it) |
| Time to production | **< 1 day** | Weeks | Weeks | Months | 12–24 months |

**Speaker Notes:**
"Don't over-explain this slide. Put it up, give them 30 seconds, then ask: 'What column represents your current strategy, and what's it costing you?' Let the comparison do the work."

---

### Slide 12: Getting Started

**Key Message:** We can have AgentOS running on your infrastructure this week — not after a procurement cycle, not after a six-month implementation. This week.

**Content:**

**Three paths forward:**

1. **Proof of Concept (Week 1)**
   - We deploy AgentOS on your hardware or a local VM
   - Your IT team verifies the security architecture
   - You run one real workflow with your actual data
   - Outcome: go/no-go decision with evidence, not assumptions

2. **Pilot (30 days)**
   - 3–5 workflows live and running for real users
   - Full audit log review with your security team
   - Integration with one enterprise system (CRM, ITSM, or ERP)
   - Outcome: production deployment decision

3. **Production Deployment**
   - Full rollout with your team
   - Custom skill development for your specific workflows
   - Optional: Blitz implementation support

**CTA:** "What's the one workflow that, if automated, would make the biggest impact on your team this quarter? That's where we start."

**Speaker Notes:**
"End with the question. Don't close with a pitch — close with curiosity. Find out their most painful manual workflow, agree that AgentOS solves it, and propose a PoC around that specific use case. The fastest path to a sale is a live proof on their real data."

---

## 5. Key Messages by Persona

### CISO (Chief Information Security Officer)

**Their Top 3 Concerns:**
1. Data leaving the organization through uncontrolled AI tool usage (shadow AI)
2. Lack of audit trail and governance for AI agent actions
3. Credential exposure — employees connecting AI tools to enterprise systems without IT oversight

**The One Message That Resonates:**
"Every agent action passes through three security gates before it executes. Nothing bypasses this. And every action is logged in a format your SIEM can ingest."

**Supporting Proof Points:**
- JWT validation, RBAC permission check, and per-tool ACL on every agent action — architectural, not configurable
- AES-256 credential encryption; credentials are never passed to LLM prompts
- Structured JSON audit logs (structlog) with user_id, tool name, decision, timestamp — Loki/Splunk-ready
- Per-user memory isolation enforced at the database query level, not the application level
- Keycloak SSO integration with your existing IdP — no new identity silo
- On-premise deployment: your firewall, your network perimeter, no vendor access

**What NOT to Say:**
- Don't lead with features or the workflow canvas — they don't care yet.
- Don't say "industry-leading security" — show the architecture, don't describe it.
- Don't promise compliance certifications AgentOS doesn't have yet. Be specific and honest.
- Don't minimize their concerns — validate them. "You're right to be skeptical; here's the architecture."

---

### CTO / VP Engineering

**Their Top 3 Concerns:**
1. Technical debt and long-term maintainability — is this something they'll be stuck supporting?
2. Integration depth — does this actually connect to their systems, or is it another demo-only product?
3. Engineering team implications — does this help or compete with what their AI team is building?

**The One Message That Resonates:**
"AgentOS is built on LangGraph. Your engineers aren't locked out — they extend it. You get production-ready enterprise infrastructure on day one so your team can focus on building business logic, not re-implementing credential vaults."

**Supporting Proof Points:**
- LangGraph-native orchestration — engineers already know the primitives
- MCP integration layer for enterprise systems — extensible without forking core
- Docker Compose deployment — standard infrastructure, no exotic dependencies
- LiteLLM proxy for LLM agnosticism — swap models without rewriting agent code
- pgvector for memory — no separate vector DB to operate
- Open architecture: custom tools register in tool_registry.py; no black box

**What NOT to Say:**
- Don't over-sell the "no code" angle to a CTO — they'll see it as a limitation.
- Don't dismiss their in-house capabilities. The "build your own" path is valid; just help them understand the real cost.
- Don't get lost in demo features — they want to talk architecture.
- Avoid vague claims like "enterprise-grade" without specifics. CTOs want to see the stack, not the marketing.

---

### IT Admin / Platform Team

**Their Top 3 Concerns:**
1. Operational burden — what does it take to keep this running, and who owns it when something breaks?
2. Integration with existing infrastructure — SSO, network policies, existing tooling
3. Control — can we actually enforce policies, or is this another tool users run around?

**The One Message That Resonates:**
"You deploy it on Docker Compose, connect it to your Keycloak, and your existing firewall rules apply. You control what agents can access. You own the audit logs. This adds to your governance, it doesn't create a new silo."

**Supporting Proof Points:**
- Docker Compose deployment — standard runbooks, no Kubernetes required for MVP
- Keycloak SSO integration — works with your existing realm and IdP configuration
- RBAC and tool ACL managed through admin UI — no code changes to restrict access
- Audit logs to a volume you control — not a SaaS dashboard you can't export
- All data on your storage — backups, retention, and data lifecycle under your policies
- No vendor access required for normal operations

**What NOT to Say:**
- Don't promise "zero maintenance" — nothing is zero maintenance. Say "minimal operational footprint."
- Don't dismiss their operational concerns as blockers — they're the people who have to run this.
- Don't skip the Keycloak integration story — it's the most important integration for this persona.
- Avoid showing the workflow canvas as the lead feature — they care about ops, not UX.

---

### Line-of-Business Manager (Operations, Finance, HR)

**Their Top 3 Concerns:**
1. Dependency on engineering — will they have to wait for IT to build and change every workflow?
2. Reliability — will this actually run every day without babysitting?
3. Business value — what specifically will this save, and how do we measure it?

**The One Message That Resonates:**
"Your team builds the workflow on the visual canvas. IT reviews and approves it. Then it runs — every day, on schedule, without anyone touching it. No engineering tickets, no dependency."

**Supporting Proof Points:**
- Visual low-code canvas — business analysts can build and modify workflows
- Celery-based autonomous scheduler — workflows run on schedule, as the job owner
- Multi-channel delivery: results arrive in Telegram, Teams, or WhatsApp where your team already works
- Concrete example: morning digest workflow (email + calendar + project status) built and deployed in under 30 minutes, runs daily
- Governance model: IT sets the guardrails (tool ACL, RBAC); business team operates within them

**What NOT to Say:**
- Don't go deep on security architecture — they want to know what it does for their team.
- Don't say "you'll need to work with IT" as the primary answer — validate that this reduces that dependency.
- Avoid technical jargon (JWT, LangGraph, pgvector) entirely.
- Don't make promises about specific time savings without grounding them in their workflows.

---

### CEO / COO (When They're in the Room)

**Their Top 3 Concerns:**
1. Strategic positioning — are we ahead of competitors, or catching up?
2. Risk — is this going to create a compliance incident or security breach?
3. ROI — what does this cost and what does it return?

**The One Message That Resonates:**
"Your competitors are deploying AI agents today. AgentOS lets you do it without accepting the compliance and security risk that their cloud AI tools create. You move fast and stay safe — you don't have to choose."

**Supporting Proof Points:**
- Competitive framing: every competitor with Copilot, Agentforce, or ChatGPT Enterprise is sending their data to third-party clouds — you won't be
- On-premise = data sovereignty = no regulatory exposure from AI data processing
- Time to value: under a day to first deployment — this is not an 18-month IT project
- Platform ROI: one deployment governs all agents across all departments — not per-tool licensing
- Concrete business outcomes: executives get daily briefings automatically; operations teams get automated status reports; no additional headcount

**What NOT to Say:**
- Don't lose them in technical detail — one sentence on how it works, then get back to business outcomes.
- Don't position this as an IT project. Position it as a strategic competitive initiative.
- Don't quote hourly engineering time as the primary ROI — use business outcomes (decisions faster, reports automated, analyst hours reclaimed).
- Avoid the word "pilot" — CEOs don't approve pilots, they approve initiatives. Frame it as phase one.

---

## 6. Objection Handling Guide

### Objection 1: "We already have Microsoft Copilot / M365 Copilot for this."

**Why They're Saying It:**
They have an existing Microsoft relationship, possibly an EA that includes Copilot. They want to maximize sunk cost and minimize new vendor relationships. The underlying fear is adding complexity without clear incremental value.

**Response Strategy:**
Acknowledge Copilot's real strengths, then expose the specific capability gaps. Don't position as replacement — position as the governance layer they need in addition to, or instead of, Copilot for use cases involving sensitive data.

**Response Script:**
"Copilot is excellent for personal productivity within the Microsoft ecosystem — and if your team lives in Teams and SharePoint, that's real value. What Copilot doesn't give you is data sovereignty. Every prompt your users type, every document they share with Copilot, transits Azure. For workloads involving customer records, financial data, or anything under your compliance scope, that's an architectural problem, not a policy one. AgentOS handles exactly the use cases where Copilot's cloud model creates risk. You can run both — Copilot for everyday productivity, AgentOS for governed, sensitive-data workflows."

**Follow-Up Question:**
"When your security team audited Copilot usage, what did the data flow report show about where your documents and prompts are processed? Do you have independent verification of that, or are you relying on Microsoft's attestation?"

---

### Objection 2: "Our data is already in the cloud anyway — Office 365, Salesforce — so sovereignty doesn't matter."

**Why They're Saying It:**
They've rationalized the risk already, or they genuinely don't see the difference between data stored in the cloud and data processed by a third-party AI. The underlying fear is reopening a decision they thought was settled.

**Response Strategy:**
Draw a clear distinction between data at rest in SaaS systems (with data processing agreements) and data actively processed by LLMs (which may be used for model training, accessible to AI vendor staff, or not covered by existing DPAs).

**Response Script:**
"There's an important distinction between data stored in Salesforce under a DPA and data actively processed by an LLM. When an AI agent reads a document and sends it to OpenAI's API as part of a prompt, that data crosses a new boundary — often outside your existing data processing agreements. Most enterprise SaaS DPAs weren't written with AI inference in mind. Whether or not it's a real risk for you depends on your specific compliance scope, but it's worth having your legal and security teams confirm the coverage rather than assuming it's already handled."

**Follow-Up Question:**
"Has your legal team reviewed whether your existing DPAs with Microsoft and Salesforce explicitly cover third-party LLM processing of your data? That's worth confirming before a compliance audit raises it."

---

### Objection 3: "We don't have AI engineers to set this up and run it."

**Why They're Saying It:**
They're worried about operational capability. The underlying fear is buying a product that requires specialized skills they don't have, then being stuck with an unmaintainable system.

**Response Strategy:**
Separate the deployment complexity (low) from the ongoing operational complexity (also low). AgentOS runs on Docker Compose — any infrastructure team can operate it. Business users build workflows on the canvas. The engineering dependency is minimal and purposely designed out.

**Response Script:**
"AgentOS runs on Docker Compose — if your team can operate any containerized application, they can operate AgentOS. There's no custom runtime, no proprietary infrastructure to learn. For workflow building, the visual canvas is designed for business analysts, not engineers. We've designed specifically to minimize the engineering dependency because we know most enterprise teams can't staff a dedicated AI engineering team. Typical deployment involves one or two IT ops people for the infrastructure layer, and business users who own the workflows from there."

**Follow-Up Question:**
"Who on your team manages your Docker or containerized application stack today? Because that's the profile of person who would own the infrastructure side of AgentOS."

---

### Objection 4: "We're waiting to see which AI platform wins before committing."

**Why They're Saying It:**
They're risk-averse about picking the wrong horse. The underlying fear is making a commitment to a platform that becomes irrelevant or gets acquired. This is also sometimes a polite deferral.

**Response Strategy:**
Challenge the premise that "waiting" is lower risk. The risk of waiting is that competitors act, internal shadow AI grows ungoverned, and the team falls further behind. Also: AgentOS is LLM-agnostic, so the "which LLM wins" question is actually solved by the platform.

**Response Script:**
"The platform war between LLMs is real — but that's exactly why AgentOS's LLM-agnostic architecture matters. We route through LiteLLM, which means you can run Ollama today, switch to Claude next quarter, and add GPT-5 when it ships — all without changing your agent code. You're not betting on which LLM wins; you're betting on a governance architecture that works regardless. Meanwhile, your competitors aren't waiting. Every month of inaction is another month of ungoverned Copilot usage, shadow AI, and manual workflows your team is doing by hand."

**Follow-Up Question:**
"What specific signal are you waiting for before acting? If we can tie the proof-of-concept to that signal, you're de-risking the decision rather than deferring it."

---

### Objection 5: "This looks like it's still early / not production-ready."

**Why They're Saying It:**
They've seen the product and it doesn't have the polish of a $500M ARR SaaS company. Or they're worried about being an early customer with all the pain that implies. The underlying fear is production incidents on an immature platform.

**Response Strategy:**
Acknowledge honestly. Don't oversell maturity. Instead, point to what is production-ready (security architecture, core runtime, scheduler, memory system), what the current scale target is (100 users — not trying to be AWS), and the advantage of being an early customer (roadmap influence, direct support access).

**Response Script:**
"Fair observation — AgentOS is not a decade-old platform, and I won't pretend otherwise. What is production-ready today is the security architecture, the core agent runtime, the scheduler, and the memory system — the things that break in production if they're wrong. The visual canvas and admin UI are functional but will get more polished. We're designed for 100-user enterprise deployments, not millions — and at that scale, every issue gets direct attention, not a support ticket queue. Early customers get direct roadmap access and response times that enterprise SaaS vendors can't match."

**Follow-Up Question:**
"What specific capability are you concerned about from a production-readiness standpoint? Let's address that directly — some things may be concerns I should acknowledge honestly, and others may be stronger than the UI suggests."

---

### Objection 6: "Our IT security team will never approve this."

**Why They're Saying It:**
Security teams often block new tools as a default. The underlying fear is that the champion doesn't want to fight the battle internally if they're not sure they'll win.

**Response Strategy:**
Offer to engage the security team directly. This objection is actually an opportunity — AgentOS's security architecture is designed to impress security teams, not just business buyers. The CISO demo is our strongest demo.

**Response Script:**
"That's actually one of our favorite conversations to have. AgentOS was built to pass a security review, not to avoid one. Three-layer security gates on every agent action, AES-256 credential encryption, full audit logs in your SIEM format, Keycloak SSO with your existing IdP — these aren't features that security teams object to, they're features security teams ask for. We'd welcome the chance to present the security architecture directly to your IT security team. In our experience, security teams become advocates once they see the architecture, because it gives them more visibility and control than whatever the current shadow AI situation looks like."

**Follow-Up Question:**
"Can we set up a 45-minute technical session with your security team specifically? I'll bring the architecture diagram and we can walk through each security gate. What's the fastest way to get that on the calendar?"

---

### Objection 7: "The price is too high — we can just use ChatGPT."

**Why They're Saying It:**
Price anchoring to a free/cheap tool. The underlying fear is budget justification — they don't know how to explain to their CFO why they're paying for a platform when "ChatGPT is free."

**Response Strategy:**
Change the comparison frame. ChatGPT is a tool for individuals. AgentOS is infrastructure. Compare it to the cost of the alternative: engineering time to build equivalent capabilities, or the cost of a compliance incident from uncontrolled ChatGPT usage. Also: ChatGPT at scale has per-token costs that add up.

**Response Script:**
"ChatGPT Enterprise for 100 users, at scale with frequent use, isn't free — you're looking at per-user monthly costs that compound fast, plus the cost of zero governance, zero audit trail, and the organizational risk of a data handling incident. The right comparison isn't ChatGPT vs. AgentOS; it's the cost of ChatGPT usage plus the engineering time to bolt governance on top of it, versus a platform that includes governance by design. For 100 users, AgentOS typically costs less than one junior engineer's annual salary — and it automates work that would otherwise require multiple engineers to build."

**Follow-Up Question:**
"If one of your employees sent a customer's financial data to ChatGPT and it became a compliance incident, what would the cost of that be? I'm not trying to scare you — I'm trying to get the comparison on the same basis."

---

### Objection 8: "We'd rather build our own AI system internally."

**Why They're Saying It:**
Either genuine engineering confidence, or "not invented here" culture, or both. The underlying fear is vendor dependency and loss of control. Sometimes it's also a politically safer answer than making a buy decision.

**Response Strategy:**
Don't fight the build instinct — validate it. Then reframe what "build" actually means at enterprise production quality. AgentOS is built on LangGraph; they're not choosing between "build" and "buy," they're choosing how much of the platform layer to re-implement.

**Response Script:**
"Building on LangGraph and open-source tooling is a completely reasonable path — and AgentOS is built on exactly those foundations. The question is: what's the scope of 'build your own'? LangGraph gives you agent orchestration. It doesn't give you RBAC-controlled tool access, AES-256 credential management, per-user memory isolation, a visual workflow canvas, a multi-channel delivery layer, and a Celery scheduler — all production-hardened and security-audited. That's 12 to 18 months of engineering work. AgentOS is that work, already done. Your engineers can extend it, build custom tools on top of it, and own it — without starting from zero."

**Follow-Up Question:**
"When your team scopes the 'build your own' path, what's the estimate for the security layer alone — JWT + RBAC + per-tool ACL + AES-256 credential vault — before you've written a single line of business logic?"

---

## 7. Demo Scenarios

### Demo 1: The Data Sovereignty Proof

**Objective:** Prove, visually and undeniably, that no data leaves the organization during AI agent operations.

**Audience:** CISO, security team, compliance officers, skeptical CTOs.

**Setup Required:**
- AgentOS running on local machine or local server (not on any cloud VM)
- Ollama running locally with a model loaded (e.g., qwen2.5 or llama3)
- Network monitor open (e.g., Wireshark, Little Snitch, or `nethogs`) showing live outbound connections
- A sample document with clearly fake but plausible-looking "sensitive" data (customer names, financial figures)
- Browser open to the AgentOS chat UI
- Audit log viewer open in a separate tab

**Step-by-Step Flow:**

**Step 1 — Set the scene (1 minute)**
Before touching the keyboard: "What you're about to see is running entirely on this machine. There is no cloud connection for AI processing. Watch the network monitor in the corner — I'll point to it when the AI is working."

**Step 2 — Show the Ollama connection (1 minute)**
Open the LiteLLM config, show the model route pointing to `host.docker.internal:11434` (Ollama on localhost). "This is our LLM. It runs on this machine. It's an open-weight model — no license, no API key, no external call."

**Step 3 — Submit a sensitive query (2 minutes)**
In the chat UI, paste the sample document and ask: "Summarize the key financial figures in this document and flag any risks."
While the model is working, point to the network monitor: "See the outbound traffic? No connection to OpenAI, Anthropic, or any external API. The inference is happening on this CPU/GPU right here."

**Step 4 — Show the audit log (2 minutes)**
Switch to the audit log viewer. Show the entry for the query: user_id, timestamp, tool called, decision (allowed), duration. "Every action is logged here. Your SIEM can ingest this format directly. Nothing happened that isn't in this log."

**Step 5 — Show the ACL control (2 minutes)**
Navigate to the Tool ACL admin. Show a user who has access to the summarization tool and another who doesn't. "If I revoke this user's access right now..." [revoke it] "...and they try the same query..." [try it in a second browser tab] "...they get a 403. The control is live, it's immediate, and it's in your hands."

**Key Moments to Highlight:**
- The network monitor showing no outbound traffic during inference
- The audit log entry appearing in real time
- The ACL revocation taking immediate effect

**What to Say at Each Step:**
- Opening: "Most AI demos show you a polished UI. This demo shows you the security architecture. That's what you're actually buying."
- Network monitor: "This is not a policy claim or a contractual promise. This is physics. The data does not leave this network."
- Audit log: "When your auditor asks 'what did your AI agents do last Tuesday?' — this is your answer. It's already there."
- ACL demo: "You control who can do what. Not us. Not the model vendor. You."

---

### Demo 2: The Morning Digest Workflow

**Objective:** Show a real, business-valuable automation built by a non-technical user, running autonomously on a schedule.

**Audience:** COOs, operations managers, finance leads, HR directors, any business stakeholder who thinks AI automation requires engineers.

**Setup Required:**
- AgentOS running with workflow canvas accessible
- A pre-built "Morning Digest" workflow ready to show (don't build from scratch during the demo — walk through the pre-built one and explain each node)
- A second, simpler workflow pre-built that you'll "build" live (3–4 nodes, takes 5 minutes)
- Scheduler configured to show the morning workflow running at 7am (show the last run record)
- Telegram bot configured on a phone visible to the room (or screen-share the phone)
- Sample output from a previous run ready to show in Telegram

**Step-by-Step Flow:**

**Step 1 — Start with the outcome (1 minute)**
Show the Telegram message first. "This arrived in this executive's Telegram at 7:03 this morning. Let me show you how it was built and how it runs."

**Step 2 — Show the workflow canvas (3 minutes)**
Open the pre-built Morning Digest workflow. Walk through each node:
- Trigger: "Scheduler, 7:00 AM daily"
- Node 1: Email agent — "reads the last 24 hours of unread email, extracts key items"
- Node 2: Calendar agent — "reads today's meetings, flags any conflicts or high-priority attendees"
- Node 3: Project agent — "queries open project statuses from the connected project system"
- Node 4: Synthesis node — "combines all three inputs into a structured brief"
- Node 5: Telegram delivery — "sends the formatted brief to the executive's Telegram"

"This workflow was built by an operations analyst. No engineering ticket. No sprint. It took about 20 minutes."

**Step 3 — Show the scheduler (2 minutes)**
Navigate to the scheduler view. Show the Morning Digest job with its schedule (7:00 AM daily), last run time, next run time, and status (success). "This has run every day for the past three weeks without anyone touching it."

**Step 4 — Live build: a simple workflow (5 minutes)**
"Let me show you how fast this is to build. Give me a simple workflow idea — something your team does manually every week." Take their suggestion (or use a prepared fallback: "Weekly project status email to the team"). Drag the nodes, connect them, set the trigger, deploy. "This is now scheduled. It will run for the first time [day/time]."

**Step 5 — Show the security layer (1 minute)**
"Behind every one of these workflows, the security model is applying. Each node that accesses email, calendar, or project data is doing so under the user's credentials — encrypted in the vault — and every access is logged. The user who built this workflow can only build workflows using tools their role permits."

**Key Moments to Highlight:**
- The Telegram message arriving on the phone
- The visual clarity of the workflow canvas (non-technical audience should immediately understand the flow)
- The "last run: successful" status on the scheduler
- The live build — completing a workflow in 5 minutes in front of them

**What to Say at Each Step:**
- Opening (Telegram message): "This is the outcome. An executive started their day with a complete briefing — emails, calendar, project status — at 7am, without reading a single email or opening a single dashboard."
- Canvas: "You can read this workflow like a sentence: 'every morning, read email, read calendar, check projects, synthesize, deliver.' That's the entire program. No code."
- Scheduler: "This is not a demo environment. This ran this morning. It will run tomorrow. No engineer involved."
- Live build: "I want you to think about the workflow your team does manually every Monday. How long does that take? Because we just built the automated version in five minutes."

---

### Demo 3: The Admin Control Demonstration

**Objective:** Win the CISO, IT admin, and compliance stakeholder by showing the complete control and visibility layer.

**Audience:** CISO, IT director, security team, compliance officers, IT admins.

**Setup Required:**
- Two browser sessions: one as an admin user, one as a regular user
- Keycloak admin console accessible (separate tab)
- AgentOS admin panel open with: user list, role assignments, tool ACL configuration
- Audit log viewer with at least a week of historical entries
- AES-256 credential management panel (show the credential form, NOT the actual secret values)
- A pre-configured role that has been recently modified (to demonstrate live ACL effect)

**Step-by-Step Flow:**

**Step 1 — SSO and Identity (2 minutes)**
"We start at login. AgentOS doesn't have its own identity system — it connects to your Keycloak instance, which connects to your existing Active Directory or IdP." Show the Keycloak admin console, the blitz-internal realm, the role structure. "Your IT team already knows how to manage this. There's no new identity silo."

**Step 2 — RBAC Role Management (2 minutes)**
In the AgentOS admin panel, show the role list: admin, power_user, standard_user, read_only. Click into power_user. Show which tools this role can access. "These are the tools a power user is permitted to invoke. If a tool isn't in this list, an agent running as this user cannot call it — regardless of what the agent is instructed to do."

Demonstrate: remove one tool from the power_user role. Switch to the regular user session. Try to invoke that tool. Show the 403 response. "That change took effect immediately. No restart. No cache flush. Live."

**Step 3 — Per-User Tool ACL (2 minutes)**
Navigate to the Tool ACL table. Show that ACL is applied at the user level, not just the role level. "We can grant an individual user access to a specific tool even if their role doesn't have it — or revoke access for one user without changing anyone else's permissions. Granularity at the individual level."

**Step 4 — Credential Management (2 minutes)**
Navigate to the credential management panel. Show a credential entry: name, type, associated user. "Credentials are stored AES-256 encrypted. The actual token is never displayed — not here, not in logs, not in LLM prompts. When an agent needs to call an external system on behalf of this user, it retrieves the credential internally from the vault and uses it without exposing it to the LLM or logging it."

Show the credential creation form: name, type (OAuth token, API key, etc.), the value field. "This is the only time the credential value is accessible — when the user or admin sets it. After that, it's ciphertext."

**Step 5 — Audit Log Review (3 minutes)**
Open the audit log viewer. Filter by user and date range. Show a week of entries. Walk through one entry: "user_id, timestamp, tool called (email.fetch), decision (allowed), duration in milliseconds. Every action. Every user. Every tool. Searchable, exportable, and in your SIEM format."

Apply a filter: "Show me all tool calls that were denied in the last 7 days." Show the results. "This is your anomaly detection input. If a user is hitting 403s repeatedly, something is wrong — either their permissions are misconfigured, or they're trying to access something they shouldn't."

**Step 6 — The "What Happened?" Question (1 minute)**
"One more thing. When your auditor asks: 'On March 5th at 14:37, what did your AI agents do with customer data?' — what can you show them today with your current AI tools?" [Pause.] "With AgentOS, you show them this." [Filter the log to that exact timestamp.] "Complete answer, under 10 seconds."

**Key Moments to Highlight:**
- The live ACL revocation taking immediate effect
- The audit log showing complete action history with sub-second filtering
- The credential management panel showing encrypted storage (and never showing the actual value)
- The Keycloak integration — no new identity silo

**What to Say at Each Step:**
- SSO: "You manage identity in Keycloak. AgentOS integrates with it. Your existing IdP policies, MFA requirements, and session management all apply."
- ACL revocation: "This is not eventual consistency. It's immediate. The moment you revoke access, the next agent action is denied."
- Credentials: "The LLM never sees this token. The logs never contain this token. Only the encrypted vault and the tool executor that retrieves it at runtime ever touch the actual value."
- Audit log: "This is the answer to every compliance question about AI usage in your organization. It already exists. It's already searchable."
- Closing: "Your security team's job with AI is usually 'try to stop it or hope nothing bad happens.' AgentOS gives them a third option: govern it properly."

---

*End of Sales & Marketing Materials Pack*

---

> **Document metadata:**
> Version: 1.0 | Date: 2026-03-10 | Audience: Sales team, pre-sales, executive sponsors
> All capability claims reflect shipped features as of v1.2.
> Competitive claims are based on publicly available product documentation and should be verified before customer-facing use in regulated industries.
