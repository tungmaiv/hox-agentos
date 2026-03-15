# Topic #24: Third-Party Apps UI Design Document

**Date:** 2026-03-15  
**Status:** Approved for Implementation  
**Target Release:** v1.7+  
**Author:** AgentOS Design Team  
**Related Topics:** #21 (Universal Integration), #23 (Plugin Templates)

---

## Executive Summary

Third-Party Apps UI enables users to interact with connected integrations (MCP, API, CLI-Anything) through AI-generated, customizable forms. Instead of writing code or memorizing API parameters, users chat with an AI to create tailored UIs for their specific workflows.

**Key Capabilities:**
- **Auto-Generated Forms:** System creates default forms when integrations connect
- **Chat-Based Customization:** Users describe changes in natural language, AI updates forms
- **A2UI Rendering:** Dynamic forms rendered using existing CopilotKit A2UI infrastructure
- **Form Persistence:** Save customized forms for reuse across the organization
- **Real-Time Preview:** See changes immediately as you chat with the AI

**Business Value:**
- Reduces barrier to using integrations (no API knowledge required)
- Democratizes workflow creation for non-technical users
- Increases integration adoption through intuitive UI
- Builds reusable form library per organization

---

## 1. User Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        USER FLOW: CHAT WITH APPS                             │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: CONNECT APP (Topic #21)
User connects HubSpot via MCP
        ↓
System auto-generates DEFAULT FORMS:
• "View Contacts" (table view)
• "Create Deal" (form view)
• "Update Deal Stage" (form view)
        ↓

STEP 2: OPEN "CHAT WITH APPS"
User clicks left nav → "Chat with Apps"
        ↓

STEP 3: SELECT INTEGRATION
User selects HubSpot from connected apps list
        ↓

STEP 4: AI PRESENTS DEFAULT FORMS
AI: "I can help you work with HubSpot. I have some 
     pre-built forms for common tasks, or you can 
     describe what you'd like to do."

Available Forms:
• View Contacts (table)
• Create Deal (form)
• Update Deal Stage (form)

Or describe what you want to do...
        ↓

STEP 5: USER CHOOSES CUSTOMIZE
User: "I want to create a form to bulk update deals 
      with a filter for amount > $1000"
        ↓

STEP 6: AI GENERATES FORM (A2UI)
AI analyzes HubSpot API schema
Generates A2UI JSON for custom form
        ↓

STEP 7: RENDER FORM (A2UIRenderer)
Frontend renders the interactive form with:
• Min Amount input (default: 1000)
• Stage dropdown
• Matching deals table
        ↓

STEP 8: INTERACTIVE CUSTOMIZATION
User clicks "Customize"
AI: "What would you like to change?"
User: "Add a dropdown to select which fields to update"
AI updates A2UI spec, form re-renders
        ↓
User: "Great! Now remove the preview table"
AI removes table component
        ↓
User: "Add validation that at least one field is selected"
AI adds validation rules
        ↓

STEP 9: SAVE FORM
User: "Save this form as 'Bulk Update High-Value Deals'"
AI: "Saved! You can now access this form anytime from 
     'Chat with Apps > HubSpot > My Saved Forms'"
        ↓

STEP 10: USE FORM
Form saved to database
User can now:
• Use form immediately
• Access from "My Saved Forms"
• Share with team
```

---

## 2. Architecture

### 2.1 High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    THIRD-PARTY APPS UI - APPROACH C                          │
│              A2UI + Chat-Based Customization Architecture                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         FRONTEND (Next.js)                             │ │
│  │                                                                         │ │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────┐ │ │
│  │  │   ChatWithApps Page  │  │   A2UI Renderer      │  │ Form Actions │ │ │
│  │  │                      │  │                      │  │              │ │ │
│  │  │ • Integration picker │  │ • FormDisplay        │  │ • Submit     │ │ │
│  │  │ • CopilotKit chat    │  │ • FormCustomizer     │  │ • Validate   │ │ │
│  │  │ • Saved forms list   │  │ • Live preview       │  │ • Execute    │ │ │
│  │  └──────────────────────┘  └──────────────────────┘  └──────────────┘ │ │
│  │           │                         │                         │        │ │
│  │           ▼                         ▼                         ▼        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    CopilotKit Runtime                            │ │ │
│  │  │  • AG-UI streaming protocol                                      │ │ │
│  │  │  • A2UIMessageRenderer (detects form envelopes)                  │ │ │
│  │  │  • useHumanInTheLoop (customization mode)                        │ │ │
│  │  │  • useFrontendTool (form submission)                             │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    │ AG-UI Stream (A2UI envelopes)          │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                      BACKEND (FastAPI + LangGraph)                     │ │
│  │                                                                         │ │
│  │  ┌─────────────────────┐    ┌─────────────────────┐    ┌────────────┐ │ │
│  │  │   Form Generator    │    │   Form Customizer   │    │  Form Saver │ │ │
│  │  │      Agent          │    │      Agent          │    │   Service   │ │ │
│  │  │                     │    │                     │    │             │ │ │
│  │  │ • Analyze API       │    │ • useHumanInLoop    │    │ • Save A2UI │ │ │
│  │  │ • Generate A2UI     │    │ • Modify A2UI       │    │ • Load A2UI │ │ │
│  │  │ • Suggest defaults  │    │ • Re-render form    │    │ • List saved│ │ │
│  │  └─────────────────────┘    └─────────────────────┘    └────────────┘ │ │
│  │           │                         │                         │        │ │
│  │           ▼                         ▼                         ▼        │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐ │ │
│  │  │                   A2UI SPEC REGISTRY (JSONB)                     │ │ │
│  │  │  • app_form table (id, integration_id, a2ui_spec, metadata)      │ │ │
│  │  └──────────────────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                   UNIVERSAL INTEGRATION (Topic #21)                    │ │
│  │                                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │ │
│  │  │ MCP Adapter  │  │ REST Adapter │  │ CLI Adapter  │                 │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                 │ │
│  │                                                                         │ │
│  │  • Schema discovery  • OpenAPI parse  • CLI introspect                │ │
│  │  • Tool execution    • HTTP requests   • Command execution            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Form Generator Agent** | LangGraph + Pydantic | Analyzes integration schema, generates A2UI JSON |
| **Form Customizer Agent** | LangGraph + useHumanInLoop | Interactive chat to modify forms |
| **A2UI Renderer** | CopilotKit `@copilotkit/a2ui-renderer` | Renders A2UI JSON as React components |
| **Form Actions** | `useFrontendTool` | Handle form submission, validation |
| **Form Registry** | PostgreSQL + JSONB | Store/load saved A2UI specs |
| **Universal Integration** | Topic #21 adapters | Execute actual API calls |

---

## 3. Data Model

### 3.1 New Table: `app_form`

```sql
CREATE TABLE app_form (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- References
    integration_id UUID NOT NULL,
    company_id UUID NOT NULL,
    owner_user_id UUID NOT NULL,
    
    -- Form metadata
    name VARCHAR(200) NOT NULL,
    description TEXT,
    slug VARCHAR(100) NOT NULL,
    
    -- A2UI specification (the generated form definition)
    a2ui_spec JSONB NOT NULL,
    
    -- Form configuration
    form_config JSONB DEFAULT '{}',
    -- {
    --   "default_values": {...},
    --   "validation_rules": [...],
    --   "submit_action": "create_deal",
    --   "refresh_on_change": true
    -- }
    
    -- Execution settings
    execution_config JSONB DEFAULT '{}',
    -- {
    --   "adapter_type": "mcp|rest|cli",
    --   "tool_name": "hubspot_create_deal",
    --   "pre_submit_validation": true,
    --   "success_message": "Deal created successfully!"
    -- }
    
    -- Status and visibility
    status VARCHAR(20) DEFAULT 'active', -- active, archived, draft
    is_system_generated BOOLEAN DEFAULT false,
    is_shared BOOLEAN DEFAULT false,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Versioning
    version INTEGER DEFAULT 1,
    parent_form_id UUID REFERENCES app_form(id),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(company_id, slug),
    UNIQUE(integration_id, slug)
);

-- Indexes
CREATE INDEX idx_app_form_integration ON app_form(integration_id);
CREATE INDEX idx_app_form_company ON app_form(company_id);
CREATE INDEX idx_app_form_owner ON app_form(owner_user_id);
CREATE INDEX idx_app_form_status ON app_form(status);
CREATE INDEX idx_app_form_system ON app_form(is_system_generated) WHERE is_system_generated = true;
```

### 3.2 Example Records

**System-generated default form:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "integration_id": "660e8400-e29b-41d4-a716-446655440001",
  "company_id": "770e8400-e29b-41d4-a716-446655440002",
  "owner_user_id": "880e8400-e29b-41d4-a716-446655440003",
  "name": "Create HubSpot Deal",
  "description": "Create a new deal in HubSpot CRM",
  "slug": "hubspot-create-deal",
  "a2ui_spec": {
    "type": "form",
    "id": "hubspot-create-deal",
    "title": "Create New Deal",
    "components": [
      {
        "type": "text-input",
        "id": "deal_name",
        "label": "Deal Name",
        "placeholder": "Enter deal name",
        "required": true
      },
      {
        "type": "select",
        "id": "deal_stage",
        "label": "Deal Stage",
        "required": true,
        "options": [
          {"value": "appointmentscheduled", "label": "Appointment Scheduled"},
          {"value": "qualifiedtobuy", "label": "Qualified to Buy"},
          {"value": "closedwon", "label": "Closed Won"}
        ]
      },
      {
        "type": "number-input",
        "id": "amount",
        "label": "Deal Amount",
        "prefix": "$"
      }
    ],
    "actions": [
      {"type": "submit", "label": "Create Deal", "variant": "primary"},
      {"type": "button", "label": "Customize", "action": "enter_customization_mode"}
    ]
  },
  "form_config": {
    "default_values": {"deal_stage": "appointmentscheduled"},
    "submit_action": "hubspot_create_deal"
  },
  "execution_config": {
    "adapter_type": "mcp",
    "tool_name": "hubspot_create_deal",
    "success_message": "Deal created successfully!"
  },
  "is_system_generated": true,
  "is_shared": true,
  "version": 1
}
```

**User-customized form:**
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "integration_id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Bulk Update High-Value Deals",
  "description": "Bulk update deal stages with amount filter",
  "slug": "hubspot-bulk-update-high-value",
  "a2ui_spec": {
    "type": "form",
    "id": "hubspot-bulk-update-high-value",
    "title": "Bulk Update High-Value Deals",
    "components": [
      {
        "type": "number-input",
        "id": "min_amount",
        "label": "Minimum Deal Amount",
        "defaultValue": 1000,
        "prefix": "$",
        "required": true
      },
      {
        "type": "multi-select",
        "id": "fields_to_update",
        "label": "Fields to Update",
        "required": true,
        "options": [
          {"value": "stage", "label": "Stage"},
          {"value": "amount", "label": "Amount"},
          {"value": "close_date", "label": "Close Date"}
        ]
      },
      {
        "type": "table",
        "id": "matching_deals",
        "label": "Matching Deals",
        "columns": [
          {"key": "name", "label": "Deal Name"},
          {"key": "stage", "label": "Current Stage"},
          {"key": "amount", "label": "Amount", "format": "currency"}
        ],
        "dataSource": "dynamic"
      }
    ]
  },
  "is_system_generated": false,
  "is_shared": false,
  "usage_count": 5,
  "last_used_at": "2026-03-15T15:30:00Z"
}
```

---

## 4. A2UI Specification & Component Types

### 4.1 A2UI Form Schema

```typescript
// A2UI Form Specification (stored in app_form.a2ui_spec)
interface A2UIFormSpec {
  type: "form";
  id: string;
  title: string;
  description?: string;
  layout?: "vertical" | "horizontal" | "grid";
  
  components: A2UIComponent[];
  actions?: A2UIAction[];
  
  conditionalVisibility?: {
    [fieldId: string]: {
      dependsOn: string;
      condition: "equals" | "notEquals" | "contains" | "greaterThan";
      value: any;
    };
  };
  
  theme?: {
    variant?: "default" | "card" | "bordered";
    size?: "sm" | "md" | "lg";
    className?: string;
  };
}

type A2UIComponent = 
  | TextInputComponent
  | NumberInputComponent
  | SelectComponent
  | MultiSelectComponent
  | DatePickerComponent
  | TextareaComponent
  | CheckboxComponent
  | RadioGroupComponent
  | TableComponent
  | ChartComponent
  | SearchComponent
  | FileUploadComponent;

interface BaseComponent {
  id: string;
  label: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  helpText?: string;
  validation?: ValidationRule[];
  width?: "full" | "half" | "third" | "quarter";
}

interface TextInputComponent extends BaseComponent {
  type: "text-input";
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  defaultValue?: string;
}

interface NumberInputComponent extends BaseComponent {
  type: "number-input";
  min?: number;
  max?: number;
  step?: number;
  prefix?: string;
  suffix?: string;
  defaultValue?: number;
}

interface SelectComponent extends BaseComponent {
  type: "select";
  options: Array<{
    value: string | number;
    label: string;
    disabled?: boolean;
    group?: string;
  }>;
  defaultValue?: string | number;
  searchable?: boolean;
  creatable?: boolean;
}

interface MultiSelectComponent extends BaseComponent {
  type: "multi-select";
  options: Array<{
    value: string | number;
    label: string;
  }>;
  defaultValue?: (string | number)[];
  maxSelections?: number;
  minSelections?: number;
}

interface DatePickerComponent extends BaseComponent {
  type: "date-picker";
  minDate?: string;
  maxDate?: string;
  defaultValue?: string;
  showTime?: boolean;
  dateFormat?: string;
}

interface TextareaComponent extends BaseComponent {
  type: "textarea";
  minLength?: number;
  maxLength?: number;
  rows?: number;
  defaultValue?: string;
}

interface CheckboxComponent extends BaseComponent {
  type: "checkbox";
  defaultValue?: boolean;
}

interface RadioGroupComponent extends BaseComponent {
  type: "radio-group";
  options: Array<{
    value: string | number;
    label: string;
  }>;
  defaultValue?: string | number;
  layout?: "horizontal" | "vertical";
}

interface TableComponent extends BaseComponent {
  type: "table";
  columns: Array<{
    key: string;
    label: string;
    type?: "text" | "number" | "currency" | "date" | "badge" | "action";
    width?: string;
    sortable?: boolean;
    filterable?: boolean;
  }>;
  dataSource: "static" | "dynamic";
  data?: any[];
  dataKey?: string;
  pagination?: {
    enabled: boolean;
    pageSize: number;
  };
  selection?: {
    enabled: boolean;
    mode: "single" | "multiple";
  };
}

interface ChartComponent extends BaseComponent {
  type: "chart";
  chartType: "bar" | "line" | "pie" | "area" | "donut";
  dataSource: "static" | "dynamic";
  data?: any[];
  xAxis?: string;
  yAxis?: string | string[];
  options?: {
    stacked?: boolean;
    showLegend?: boolean;
    colors?: string[];
  };
}

interface SearchComponent extends BaseComponent {
  type: "search";
  searchEndpoint: string;
  searchParam: string;
  resultLabelField: string;
  resultValueField: string;
  debounceMs?: number;
  minQueryLength?: number;
}

interface FileUploadComponent extends BaseComponent {
  type: "file-upload";
  accept?: string[];
  maxSize?: number;
  maxFiles?: number;
  multiple?: boolean;
}

interface ValidationRule {
  type: "required" | "minLength" | "maxLength" | "min" | "max" | 
         "pattern" | "email" | "url" | "custom";
  message: string;
  value?: any;
  customFunction?: string;
}

interface A2UIAction {
  type: "submit" | "button" | "reset";
  label: string;
  variant?: "primary" | "secondary" | "outline" | "danger" | "ghost";
  size?: "sm" | "md" | "lg";
  icon?: string;
  disabled?: boolean;
  action?: string;
  confirmation?: {
    title: string;
    message: string;
  };
}
```

---

## 5. Frontend UI Design

### 5.1 Page: `/chat-with-apps`

**Layout Overview:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Chat with Apps                                               [User Avatar] │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────┐  ┌───────────────────────────────┐ │
│  │  Connected Apps                     │  │                               │ │
│  │                                     │  │     A2UI FORM RENDERER        │ │
│  │  [🔍 Search apps...]               │  │                               │ │
│  │                                     │  │  ┌─────────────────────────┐  │ │
│  │  HubSpot [● Connected]             │  │  │  Bulk Update Deals      │  │ │
│  │  ├── 📄 View Contacts              │  │  │                         │  │ │
│  │  ├── 📄 Create Deal                │  │  │  Min Amount: [1000    ] │  │ │
│  │  ├── 📄 Update Deal Stage          │  │  │                         │  │ │
│  │  └── 📁 My Saved Forms (3)         │  │  │  New Stage: [Proposal▼] │  │ │
│  │      ├── ✏️ Bulk Update Deals      │  │  │                         │  │ │
│  │      ├── ✏️ Quick Contact Search   │  │  │  [Matching Deals Table] │  │ │
│  │      └── ✏️ Import CSV Deals       │  │  │                         │  │ │
│  │                                     │  │  │  [Update] [Customize]   │  │ │
│  │  Slack [● Connected]               │  │  └─────────────────────────┘  │ │
│  │  ├── 📄 Send Message               │  │                               │ │
│  │  ├── 📄 List Channels              │  │                               │ │
│  │  └── 📁 My Saved Forms (1)         │  │                               │ │
│  │                                     │  │                               │ │
│  │  Jira [○ Connecting...]            │  │                               │ │
│  │                                     │  │                               │ │
│  └─────────────────────────────────────┘  └───────────────────────────────┘ │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                         COPILOTKIT CHAT                                │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │
│  │  │ AI: What would you like to do with HubSpot?                     │   │ │
│  │  │                                                                 │   │ │
│  │  │ • Use existing form: "Create Deal"                              │   │ │
│  │  │ • Create custom form                                            │   │ │
│  │  │ • Describe what you need                                        │   │ │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                         │ │
│  │  [Type your message...                              ] [Send]           │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Breakdown

**ConnectedAppsSidebar Component:**
```tsx
interface ConnectedAppsSidebarProps {
  integrations: Integration[];
  selectedIntegrationId?: string;
  onSelectIntegration: (id: string) => void;
  savedFormsCount: Record<string, number>;
}
```

**A2UIFormRenderer Component:**
```tsx
interface A2UIFormRendererProps {
  formSpec: A2UIFormSpec;
  formData: Record<string, any>;
  onFieldChange: (fieldId: string, value: any) => void;
  onSubmit: (data: Record<string, any>) => void;
  onCustomize: () => void;
  isCustomizing?: boolean;
}
```

**FormCustomizer Component:**
```tsx
interface FormCustomizerProps {
  currentFormSpec: A2UIFormSpec;
  integrationCapabilities: IntegrationCapabilities;
  onFormUpdate: (newSpec: A2UIFormSpec) => void;
  onSave: (name: string, description: string) => void;
}
```

---

## 6. REST API Specification

### 6.1 Endpoints

```yaml
# Get connected integrations with their forms
GET /api/chat-with-apps/integrations
Response:
{
  "integrations": [
    {
      "id": "uuid",
      "name": "HubSpot",
      "type": "mcp",
      "status": "connected",
      "icon_url": "/icons/hubspot.svg",
      "default_forms": [...],
      "saved_forms_count": 3
    }
  ]
}

# Get forms for an integration
GET /api/chat-with-apps/integrations/{integration_id}/forms
Query: ?include_system=true&include_saved=true
Response:
{
  "integration": { ... },
  "system_forms": [...],
  "saved_forms": [...]
}

# Get single form details
GET /api/chat-with-apps/forms/{form_id}
Response:
{
  "id": "uuid",
  "name": "Create Deal",
  "a2ui_spec": { ... },
  "form_config": { ... },
  "execution_config": { ... }
}

# Create new form
POST /api/chat-with-apps/forms
Body:
{
  "integration_id": "uuid",
  "name": "My Custom Form",
  "description": "...",
  "a2ui_spec": { ... },
  "form_config": { ... },
  "execution_config": { ... },
  "parent_form_id": "uuid"  // Optional
}

# Update form
PATCH /api/chat-with-apps/forms/{form_id}
Body:
{
  "a2ui_spec": { ... },
  "form_config": { ... }
}

# Delete form
DELETE /api/chat-with-apps/forms/{form_id}

# Execute form (submit)
POST /api/chat-with-apps/forms/{form_id}/execute
Body:
{
  "form_data": {
    "deal_name": "Acme Corp",
    "deal_stage": "qualifiedtobuy",
    "amount": 5000
  }
}
Response:
{
  "success": true,
  "result": {
    "deal_id": "12345",
    "message": "Deal created successfully"
  },
  "execution_time_ms": 450
}

# Preview form (test without saving)
POST /api/chat-with-apps/forms/preview
Body:
{
  "integration_id": "uuid",
  "a2ui_spec": { ... },
  "form_data": { ... }
}
```

---

## 7. Backend Agents

### 7.1 Form Generator Agent

**Purpose:** Analyze integration capabilities and generate A2UI form specifications.

```python
class FormGeneratorState(TypedDict):
    messages: list[BaseMessage]
    integration_id: str
    integration_capabilities: dict
    user_intent: str
    generated_form: A2UIFormSpec
    iteration_count: int

class A2UIFormSpec(BaseModel):
    type: Literal["form"] = "form"
    id: str
    title: str
    description: Optional[str]
    components: list[dict]
    actions: list[dict]

# Agent Nodes:
# 1. analyze_intent - Parse user request
# 2. discover_capabilities - Fetch integration schema
# 3. generate_form - Create A2UI spec
# 4. emit_form - Send via AG-UI stream

FORM_GENERATOR_PROMPT = """
You are the Form Generator Agent for AgentOS. You create dynamic forms 
for third-party app integrations using A2UI specifications.

Your capabilities:
1. Analyze integration schemas (MCP, REST API, CLI)
2. Understand user intentions from natural language
3. Generate appropriate form fields with validation
4. Suggest helpful defaults and options
5. Create preview tables for data listing

When generating forms:
- Use the simplest component that fits the data type
- Group related fields together
- Add helpful placeholder text
- Include field validation (required, min/max, patterns)
- For listing operations, include a table component
- For creation operations, focus on input fields

Always output valid A2UI JSON.
"""
```

### 7.2 Form Customizer Agent

**Purpose:** Interactive chat-based form customization using `useHumanInTheLoop`.

```python
class FormCustomizerState(TypedDict):
    messages: list[BaseMessage]
    current_form: A2UIFormSpec
    integration_capabilities: dict
    customization_requests: list[str]
    pending_changes: list[dict]
    is_complete: bool

# Customization Examples:
# User: "Add a filter for deal amount > $1000"
# AI: [Adds number-input component with min: 1000]
#
# User: "Remove the description field"
# AI: [Removes textarea component]
#
# User: "Make the stage dropdown searchable"
# AI: [Adds searchable: true to select component]
#
# User: "Add validation that close date is in the future"
# AI: [Adds validation rule: {type: "future_date"}]
```

---

## 8. Error Handling & Edge Cases

| Error | Cause | Handling |
|-------|-------|----------|
| **Integration Not Connected** | User tries to use form for disconnected app | Show "Connect [App] first" with link to integrations page |
| **A2UI Parse Error** | Generated JSON is invalid | Fallback to text description + "Regenerate" button |
| **Component Render Error** | Frontend can't render A2UI component | Show error boundary with component ID + "Report Issue" |
| **Form Execution Error** | API call fails (MCP/REST/CLI) | Show error in form with retry option + error details |
| **Validation Error** | User input fails validation | Highlight fields inline with specific error messages |
| **Permission Denied** | User lacks access to integration | Show 403 error + contact admin message |
| **Rate Limited** | API rate limit hit | Show countdown timer + "Retry in X seconds" |
| **Schema Mismatch** | Integration schema changed since form creation | Detect on load + suggest "Update Form" |

### Error Recovery Flow

```
Form Execution Error:
┌─────────────────────────────────────┐
│ ⚠️ Failed to Create Deal           │
│                                     │
│ Error: HubSpot API returned 400     │
│ Message: "Invalid deal stage"       │
│                                     │
│ [Retry] [Edit Form] [View Details]  │
└─────────────────────────────────────┘

Click [Edit Form]:
→ Opens customization chat
→ AI: "The deal stage value seems invalid. 
       Let me update the available options."
→ Updates A2UI spec with new options
→ User retries → Success
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- Database migration (app_form table)
- A2UI schema definitions
- Form Registry service (CRUD operations)
- Basic API endpoints

### Phase 2: Form Generator Agent (Week 3-4)
- LangGraph agent structure
- Integration schema analysis
- A2UI generation logic
- AG-UI streaming integration

### Phase 3: Frontend Core (Week 5-6)
- ChatWithApps page layout
- ConnectedAppsSidebar component
- A2UIFormRenderer component
- CopilotKit integration

### Phase 4: Customization & Chat (Week 7)
- Form Customizer Agent
- useHumanInTheLoop integration
- Interactive customization flow
- Form save/load functionality

### Phase 5: Execution & Integration (Week 8)
- Form execution via Topic #21 adapters
- Validation and error handling
- Success/failure feedback
- Usage tracking

### Phase 6: Polish & Testing (Week 9-10)
- Component library expansion
- Edge case handling
- Performance optimization
- Documentation

---

## 10. Integration with Topic #21 (Universal Integration)

### Data Flow

```
Form Generator Agent
        ↓
Calls Topic #21 Integration Service
        ↓
Gets: Schema, operations, fields, examples
        ↓
Generates A2UI form
        ↓
User fills form
        ↓
Form submission
        ↓
Calls Topic #21 Adapter (MCP/REST/CLI)
        ↓
Executes actual API/tool call
        ↓
Returns result to user
```

### Required from Topic #21

- **Schema Discovery:** Get available operations and parameters
- **Field Types:** Map API types to A2UI components
- **Validation Rules:** Extract min/max, required, patterns
- **Execution:** Submit form data via appropriate adapter

---

## 11. Success Criteria

- [ ] User can connect integration and see auto-generated forms
- [ ] User can chat to generate custom forms
- [ ] Forms render correctly using A2UI
- [ ] User can customize forms via chat
- [ ] Customized forms can be saved and reused
- [ ] Form execution works via Topic #21 adapters
- [ ] Validation works inline and on submit
- [ ] Error handling provides helpful recovery options
- [ ] Forms work across different integration types (MCP, REST, CLI)

---

## 12. References

### Existing Documentation
- Topic #21: Universal Integration (schema discovery)
- Topic #23: Plugin Templates (form persistence patterns)
- CopilotKit GenUI Guide (`docs/kb/copilotkit-genui-guide.md`)
- A2UI Research (`docs/research/06-A2UI_*.md`)

### External Resources
- CopilotKit Documentation: https://docs.copilotkit.ai
- A2UI Specification: https://a2ui.org
- AG-UI Protocol: Agent-UI streaming specification

---

*Document Version: 1.0*  
*Last Updated: 2026-03-15*  
*Status: Approved for Implementation*
