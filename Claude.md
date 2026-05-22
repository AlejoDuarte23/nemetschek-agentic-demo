# Claude.md

Use this file when asking Claude to add or update VIKTOR-backed Agents SDK tools in this repository.

## Architecture

The app has four main parts:

```text
viktor-workflow-graph-template/
  app.py                         # VIKTOR Controller, Chat, and WebView
  agent/
    runner.py                    # Agents SDK runner and streamed chat events
    system_prompt.xml            # Agent behavior, tools, workflow nodes, graph icons
    tools/
      registry.py                # Registers all Agents SDK tools
      graph_tools/workflow.py    # Compose graph, plan, todo, progress tools
      viktor_tools/              # Generated tools that call VIKTOR apps
  workflow_graph/
    models.py                    # Workflow graph state models
    state.py                     # Entity-scoped graph state persistence
    viewer.py                    # Self-contained HTML WebView renderer
    workflow.js                  # Draggable graph UI, pan/zoom, icons, plan overlay
    styles.css                   # Graph visual style
```

Runtime flow:

```text
User chat
  -> app.py vkt.Chat method
  -> agent/runner.py
  -> Agents SDK Agent
  -> tool registry
  -> graph tools and/or generated VIKTOR tools
  -> VIKTOR Storage for handoffs and graph state
  -> WebView renders workflow_graph state
  -> streamed tool calls are rendered back into chat
```

The app uses `vkt.ViktorOpenAI` for the LLM. Do not add `OPENAI_API_KEY`.

## Environment

Use this exact shape for notebooks and local app runs:

```env
TOKEN_VK_APP=vktrpat_your_viktor_token
VIKTOR_ENVIRONMENT=demo.viktor.ai
```

Rules:

- `TOKEN_VK_APP` is a VIKTOR Personal Access Token.
- Do not include `Bearer`, `Authorization:`, quotes, or spaces.
- `VIKTOR_ENVIRONMENT` is host-only.
- Do not use `https://demo.viktor.ai`.
- Do not use `https://demo.viktor.ai/api`.
- Add `TOKEN_VK_APP` to VIKTOR app secrets before publishing.

For real apps, move app IDs into env values when possible:

```env
MY_APP_WORKSPACE_ID=1234
MY_APP_ENTITY_ID=5678
```

## Notebook Artifacts

The notebooks live in:

```text
convert-app-params-to-schema/
```

For each VIKTOR app, copy a notebook and update:

```python
WORKSPACE_ID = your_workspace_id
ENTITY_ID = your_entity_id
APP_OUTPUT_DIR = Path("your_app_name")
```

Each notebook generates:

```text
input_schema.json
available_methods.json
first_method_result.json
```

How the notebook gets defaults:

1. Create editor session:

```http
POST /api/workspaces/{workspace_id}/entities/{entity_id}/session/
```

2. Request parametrization with empty params:

```http
POST /api/workspaces/{workspace_id}/entities/{entity_id}/parametrization/
```

3. Read saved entity params:

```http
GET /api/workspaces/{workspace_id}/entities/{entity_id}/?properties=true&clean_params=true&param_types=true
```

4. Merge declared defaults with saved properties. Saved properties win.

How the notebook gets methods:

- read `entity_type.views[*].controller_method`;
- walk parametrization nodes and collect nodes with `method`;
- deduplicate by method name.

How the notebook gets method output:

```http
POST /api/workspaces/{workspace_id}/entities/{entity_id}/jobs/
```

with:

```json
{
  "method_name": "selected_method",
  "params": {},
  "poll_result": false
}
```

Then poll the returned `url` until `status == "success"`.

Pick the first useful result key in this order:

```text
data, table, download, geometry, plotly, geojson, web, pdf, image, ifc, optimization, set_params
```

The JSON files are generation fixtures. Do not use them as runtime output.

## Generated VIKTOR Tool Architecture

Generated tools live in:

```text
viktor-workflow-graph-template/agent/tools/viktor_tools/
```

Use these references:

- Producer tool: `reaction_loads.py`
- Consumer/storage handoff tool: `footing_design.py`
- Shared SDK compute helper: `sdk_compute.py`
- JSON response helpers: `responses.py`

Tool requirements:

- convert `input_schema.json` to explicit Pydantic models;
- preserve defaults so `{}` is valid when the VIKTOR app has defaults;
- ask which method to implement when `available_methods.json` has multiple methods;
- call the live VIKTOR app with `ViktorSdkComputeClient`;
- select the correct result key using `first_method_result.json`;
- return short JSON output with `status`, `message`, and a compact summary;
- return recoverable failures as tool output, not hard exceptions.

Do not add a generic base tool class to work around schema issues.

Do not expose arbitrary `dict[str, Any]` as the tool input.

## Storage Handoff Architecture

Use VIKTOR Storage for large outputs.

Do not make the agent manually pass large tables, geometry, or result JSON between tools.

Pattern:

```text
Producer tool
  -> calls VIKTOR method
  -> selects useful result payload
  -> writes payload to entity-scoped VIKTOR Storage

Consumer tool
  -> exposes only missing user inputs
  -> reads producer output from entity-scoped VIKTOR Storage
  -> calls next VIKTOR method
  -> writes its result to entity-scoped VIKTOR Storage
```

Current example:

```text
run_reaction_loads
  -> stores reaction_loads_table

run_footing_design
  -> reads reaction_loads_table
  -> exposes only pad_thickness
  -> stores footing_design_data
```

If a required storage key is missing, return:

```json
{
  "status": "needs_prerequisite",
  "retry_action": {
    "tool": "producer_tool_name"
  }
}
```

## Graph Tool Architecture

Graph tools live in:

```text
viktor-workflow-graph-template/agent/tools/graph_tools/workflow.py
```

They manage:

- DAG composition;
- plan card;
- todo updates;
- progress display;
- graph node icons.

Graph nodes support:

```json
{
  "node_id": "reaction_loads",
  "label": "Reaction Loads",
  "node_type": "default",
  "icon": "R",
  "icon_bg": "#dbeafe",
  "url": "https://demo.viktor.ai/workspaces/2672/app/editor/12162",
  "depends_on": []
}
```

When adding tools, add graph nodes with:

- short stable node ids;
- clear labels;
- a nice short icon;
- a clean `icon_bg`;
- correct `depends_on`.

The graph renderer is in `workflow_graph/`. It already supports draggable nodes, pan/zoom, fit view, plan overlay, progress overlay, and custom icon labels.

## System Prompt Architecture

The system prompt lives here:

```text
viktor-workflow-graph-template/agent/system_prompt.xml
```

After adding a new tool, update:

- workflow rules;
- tool list;
- workflow nodes;
- default sequence.

Do not put low-level SDK implementation details in the system prompt.

Do not put low-level VIKTOR Storage implementation details in the system prompt.

The prompt should tell the agent what to do, not how the code is implemented.

## Tool Registry Architecture

Register tools in:

```text
viktor-workflow-graph-template/agent/tools/registry.py
```

Update:

- imports;
- `TOOL_DISPLAY_NAMES`;
- `get_tools()`.

When turning the template into a real app, remove demo tools:

- `run_reaction_loads`;
- `run_footing_design`;
- their imports;
- their system prompt entries;
- their graph nodes.

## Claude Prompt Template

Use this prompt when creating a new tool:

```text
Create an Agents SDK VIKTOR tool from convert-app-params-to-schema/<app_folder>.

Use:
- Claude.md
- SKILL.md
- convert-app-params-to-schema/<app_folder>/input_schema.json
- convert-app-params-to-schema/<app_folder>/available_methods.json
- convert-app-params-to-schema/<app_folder>/first_method_result.json
- viktor-workflow-graph-template/agent/tools/viktor_tools/reaction_loads.py
- viktor-workflow-graph-template/agent/tools/viktor_tools/footing_design.py
- viktor-workflow-graph-template/agent/tools/registry.py
- viktor-workflow-graph-template/agent/system_prompt.xml

Requirements:
- Ask which method to implement if multiple methods exist.
- Convert the schema into explicit Pydantic models with defaults.
- Use ViktorSdkComputeClient for live compute.
- Select the output key from the method result shape.
- Use VIKTOR Storage for large outputs and downstream handoffs.
- Register the tool.
- Update system_prompt.xml.
- Add graph nodes with icon and icon_bg.
- Keep runtime output short and useful.
- Return recoverable failures as JSON tool output.
```

## Validation

Run:

```bash
python3 -m py_compile $(rg --files viktor-workflow-graph-template -g '*.py') $(rg --files sample_apps -g '*.py')
node --check --input-type=module < viktor-workflow-graph-template/workflow_graph/workflow.js
xmllint --noout viktor-workflow-graph-template/agent/system_prompt.xml
git diff --check
```
