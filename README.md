# agentic-apps-template

Template for VIKTOR apps that use the OpenAI Agents SDK, a draggable workflow graph, streamed tool calls, and generated VIKTOR app tools.

## 1. Clone The Repository

Clone this repo from Alejandro's GitHub repositories:

https://github.com/AlejoDuarte23?tab=repositories

Use the `agentic-apps-template` repository as the starting point.

## 2. Add Environment Files

Add a `.env` in the notebook folder:

```text
convert-app-params-to-schema/.env
```

Add a `.env` in the VIKTOR app template:

```text
viktor-workflow-graph-template/.env
```

Use the same values in both:

```env
TOKEN_VK_APP=vktrpat_your_viktor_token
VIKTOR_ENVIRONMENT=demo.viktor.ai
```

`TOKEN_VK_APP` is the VIKTOR Personal Access Token. Do not add `Bearer`, quotes, or `Authorization:`.

`VIKTOR_ENVIRONMENT` is the host only. Do not use `https://` or `/api`.

## 3. Copy The Notebooks

Copy one notebook per VIKTOR app from:

```text
convert-app-params-to-schema/
```

In each copied notebook, update:

```python
WORKSPACE_ID = your_workspace_id
ENTITY_ID = your_entity_id
APP_OUTPUT_DIR = Path("your_app_name")
```

Run the notebook.

## 4. Generate The JSON Files

Each notebook should generate:

```text
input_schema.json
available_methods.json
first_method_result.json
```

The notebook gets the parametrization with defaults by:

1. Creating an editor session:

```http
POST /api/workspaces/{workspace_id}/entities/{entity_id}/session/
```

2. Calling parametrization with empty params:

```http
POST /api/workspaces/{workspace_id}/entities/{entity_id}/parametrization/
```

3. Reading current saved params from the entity:

```http
GET /api/workspaces/{workspace_id}/entities/{entity_id}/?properties=true&clean_params=true&param_types=true
```

4. Merging declared defaults plus saved properties. Saved properties win.

The notebook gets available methods from:

- `entity_type.views[*].controller_method`
- parametrization nodes with a `method`

The notebook gets the first method output by running a REST job:

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

## 5. Prompt Claude To Create The Tool

Use `Claude.md`.

Prompt Claude with the generated JSON folder:

```text
Use Claude.md.
Create an Agents SDK VIKTOR tool from convert-app-params-to-schema/<app_folder>.
Use SKILL.md.
Convert input_schema.json into Pydantic models with defaults.
Use available_methods.json to choose the method.
Use first_method_result.json to understand the output key and summary.
Match the current implementation style in viktor-workflow-graph-template/agent/tools/viktor_tools.
Register the tool in viktor-workflow-graph-template/agent/tools/registry.py.
```

The tool should call the live VIKTOR app through:

```python
vkt.api_v1.API(...).get_workspace(...).get_entity(...).compute(...)
```

Do not use the JSON files as runtime output. They are only fixtures for generating the tool.

## 6. Update The System Prompt

After adding a tool, update:

```text
viktor-workflow-graph-template/agent/system_prompt.xml
```

Add:

- tool name
- tool description
- app URL
- method name
- input/output storage keys
- dependency rules between tools
- expected workflow sequence

## 7. Add The Graph Node And Icon

Update the workflow graph nodes in the system prompt or wherever the graph is composed.

Ask Claude to add a clean icon for each new node:

```text
Add graph nodes for the new tools.
Use short node ids.
Use a nice icon label and icon background for each node.
Use dependencies to connect the DAG.
```

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

## 8. Use VIKTOR Storage For Large Outputs

Do not make the agent manually pass big outputs between tools.

For large outputs like reaction tables:

1. Producer tool writes to entity-scoped storage.
2. Consumer tool reads from entity-scoped storage.
3. Consumer tool exposes only the missing user inputs.

Current example:

```text
run_reaction_loads -> stores reaction_loads_table
run_footing_design -> reads reaction_loads_table
run_footing_design -> stores footing_design_data
```

Use:

```python
vkt.Storage().set(key, data=vkt.File.from_data(json.dumps(payload)), scope="entity")
stored_file = vkt.Storage().get(key, scope="entity")
```

## 9. Remove The Demo Tools For A Real App

Before using this template for another project, remove the demo reaction and footing tools from:

```text
viktor-workflow-graph-template/agent/tools/registry.py
viktor-workflow-graph-template/agent/system_prompt.xml
```

Move real app IDs to env values where possible:

```env
TOKEN_VK_APP=vktrpat_your_viktor_token
VIKTOR_ENVIRONMENT=demo.viktor.ai
MY_APP_WORKSPACE_ID=1234
MY_APP_ENTITY_ID=5678
```

Then use those env values in the generated tool instead of hardcoded demo IDs.

## 10. Publish Checklist

Before publishing the VIKTOR app:

- add `TOKEN_VK_APP` to the app secrets;
- confirm `VIKTOR_ENVIRONMENT` matches the published environment;
- confirm `agent/system_prompt.xml` lists only the real tools;
- confirm `get_tools()` registers only the real tools;
- run the app locally once with `viktor-cli clean-start`.

The app uses `vkt.ViktorOpenAI` for the LLM. No `OPENAI_API_KEY` is needed.
