To implement a granular **Access Control List (ACL)** system within your stack (**CopilotKit, LangGraph, Pydantic, Keycloak**), you must leverage the **Copilot Runtime** as a security gateway and utilize the built-in availability controls in the frontend hooks 1-3. This approach ensures that users only see and execute the **tools, skills, and MCP functions** they are authorized to use 1, 4, 5\.

### 1\. Identity Foundation: Keycloak & JWT

The first layer of your ACL must be the authentication of the user identity 1\.

* When a user logs in via **Keycloak**, the frontend receives a **JWT token** containing user roles and metadata 1, 6\.  
* This token is passed in the header of every **AG-UI request** to the **Copilot Runtime** 1, 7, 8\.  
* The **Copilot Runtime (FastAPI)** acts as the "Central Nervous System," validating the JWT and extracting the user's identity and permissions before any agent logic is executed 2, 4, 6\.

### 2\. Frontend Management: Controlling Visibility and Availability

You can implement a UI feature to manage ACLs by dynamically adjusting how tools are registered in the browser 3, 9\.

* **Dynamic Tool Availability:** The useFrontendTool (v2) and useCopilotAction (v1) hooks include an **available** property 3, 10\.  
* You can set this property to **"enabled"** or **"disabled"** based on the user's permissions retrieved from your ACL module 3, 11\.  
* If a tool is set to **"disabled"**, the AI agent will not "see" the tool in its context and will be unable to invoke it, effectively hiding the capability from unauthorized users 3, 9\.  
* **Context Filtering:** Use the **categories** parameter in useCopilotReadable to control which pieces of application state are visible to the agent based on the user's access level 12, 13\.

### 3\. Backend Enforcement: The "Gatekeeper" Middleware

Since frontend logic can be bypassed, the **Copilot Runtime** must strictly enforce the ACL for every tool call 14, 15\.

* **AG-UI Middleware:** Implement a middleware layer in your FastAPI backend using agent.use 14\.  
* This middleware intercepts every **TOOL\_CALL\_START** event 16\.  
* It verifies the **User ID** and **Role** against your backend **ACL/RBAC database** (e.g., PostgreSQL) to ensure the user has the right to execute that specific **skill** or **MCP function** 17, 18\.  
* If unauthorized, the middleware can return an error or a "Permission Denied" message back to the agent through the **AG-UI protocol**, preventing execution 8, 19, 20\.

### 4\. Managing MCP Functions and Skills

MCP functions require special attention because the protocol itself lacks a native policy layer for deep delegation 17, 21\.

* **Delegation Capability Tokens (DCTs):** For enterprise security, you should wrap your MCP tool calls in **capability-based tokens** 17\.  
* These tokens (based on technologies like **Macaroons** or **Biscuits**) use cryptographic caveats to restrict what an agent can do with a tool (e.g., allowing "read-only" access to a specific database folder via MCP) 17, 18\.  
* **Tool-Level RBAC:** Every tool defined in **LangGraph** should be wrapped in a permission-checking decorator that validates the session's JWT against the required ACL for that tool 15, 22, 23\.

### 5\. Frontend ACL Management Feature (User Interface)

To allow admins to manage these permissions, you can build a **Management Canvas** using **A2UI** 24, 25\.

* **Declarative UI for Permissions:** Use **A2UI** to render a dynamic "Permission Matrix" where admins can toggle access to specific tools, sub-agents, or data sources for different user groups 24, 26, 27\.  
* **Real-Time Updates:** When an admin saves changes on this canvas, the update can be synced to the backend via **Shared State (useCoAgent)** and immediately persisted to your ACL database 28-30.  
* **Human-in-the-Loop (HITL):** For high-stakes permission changes, you can use the **renderAndWaitForResponse** pattern to require a second admin's approval before the new ACL is applied 31, 32\.

By combining **Keycloak identity**, **Copilot Runtime middleware**, and the **available property** in frontend hooks, you create a robust, end-to-end ACL system that secures your multi-agent enterprise application 1, 3, 18\.  
**Would you like me to create a tailored report detailing the specific API structures and middleware code snippets needed to connect Keycloak roles to CopilotKit tool availability?**  
