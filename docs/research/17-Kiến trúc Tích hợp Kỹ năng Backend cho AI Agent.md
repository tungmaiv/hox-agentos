Yes, **backend skills (similar to those found in Claude Code or OpenClaw) should absolutely be implemented in the backend** within this stack.  
In the **CopilotKit** and **AG-UI** ecosystem, there is a fundamental architectural split between **Frontend Tools** and **Backend Tools** based on security, performance, and the nature of the task 1, 2\.

### 1\. Why Implement Skills in the Backend?

For an enterprise application, backend implementation is required for any skill that involves sensitive logic or data:

* **Security & Trusted Environment:** The **Copilot Runtime** provides a trusted server-side environment 3\. Skills implemented here can safely use **API keys**, access internal databases, or interact with file systems without ever exposing those secrets to the user's browser 2, 4\.  
* **Compute-Heavy Operations:** Tasks like complex data processing, file parsing (e.g., PDF extraction), or long-running simulations are better suited for server-side resources than a client-side browser 5, 6\.  
* **Persistent State & Memory:** Backend skills can interact directly with your **Hierarchical Memory** (PostgreSQL/Vector DB) and maintain state across sessions, which is critical for enterprise "Deep Agents" 7, 8\.

### 2\. How to Implement Backend Skills

In your **Python/FastAPI** backend, you define these skills as "Backend Tools."

* **Definition:** Use standard Python functions decorated with the **@tool** decorator (if using LangChain/LangGraph) or define them within a **PydanticAI** agent class 9-11.  
* **Registration:** These tools are registered with the **Copilot Runtime SDK** at the server level. When the AI decides a backend action is needed, the Runtime handles the execution and streams the results back to the frontend via the **AG-UI protocol** 9, 12, 13\.  
* **Execution Flow:** The agent logic in **LangGraph** orchestrates the call. For example, if a user asks for a report, a backend tool might fetch the data from an MCP server, process it, and then stream the structured update back to the UI 14, 15\.

### 3\. Implementing "Claude-like" Capabilities

If you want to replicate the advanced "Skill" behavior of tools like **Claude Code** (which can plan, use a filesystem, and spawn subagents), you should use **LangGraph Deep Agents** 16, 17:

* **Filesystem Middleware:** Deep Agents include middleware that adds backend file tools (e.g., read\_file, edit\_file, ls) 18\.  
* **Subagent Middleware:** This allows a "Master Agent" to spawn isolated backend loops for specialized tasks, mirroring the delegation seen in Claude’s architecture 18, 19\.  
* **To-do List Middleware:** Forces the agent to explicitly plan and update its progress, which can be rendered in the frontend for user transparency 18\.

### 4\. Security: The Sandbox Requirement

Since enterprise-grade backend skills often involve executing code or shell commands (similar to Claude Code's shell access), you should implement **Docker Sandboxing** 20\.

* As seen in **OpenClaw**, any "non-main" or untrusted session should execute its backend skills (like bash or subprocess) inside a **Docker container** to prevent the agent from accessing the host operating system 20, 21\.  
* Your **Copilot Runtime** can gate these tool calls by checking **Keycloak JWT roles** before allowing a backend skill to execute 1, 22\.

### Summary Table: Skill Placement

Skill Type,Examples,Implementation  
Frontend Skill,"Open modals, change UI theme, browser alerts 23, 24",useFrontendTool (React Hook)  
Backend Skill,"DB queries, File System access, API calls 2, 5",Python @tool \+ Copilot Runtime  
Enterprise Skill,"Multi-step research, Subagent spawning 15, 17",LangGraph Deep Agents  
**Recommendation:** Build your folder structure with a dedicated backend/tools/ directory to house these Python-based skills, ensuring they are strictly validated with **Pydantic** models before being exposed through the **Copilot Runtime** 527, Proposed Solution.  
