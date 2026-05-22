# VIKTOR Workflow Graph Agent Template

This template combines:

- `vkt.Chat` backed by the VIKTOR LLM service through the Agents SDK.
- A `@vkt.WebView` workflow graph that reads `WorkflowCanvasState` from `vkt.Storage`.
- Function tools for composing a DAG, updating plan items, and rendering progress.
- Chat rows for tool calls by streaming `tool_called` and `tool_output` events.
- A generated reaction-load tool that calls the demo VIKTOR app through the SDK API.
- A generated footing-design tool that reads reaction loads from entity-scoped VIKTOR Storage.

## Layout

- `app.py`: VIKTOR controller and views.
- `agent/runner.py`: Agents SDK agent, VIKTOR LLM client, runner, and stream handling.
- `agent/system_prompt.xml`: XML system prompt.
- `agent/tools/graph_tools/`: graph, plan, and progress tools.
- `agent/tools/viktor_tools/`: generated SDK-backed VIKTOR app tools.
- `workflow_graph/`: graph state, models, and self-contained WebView renderer.

## Run

```bash
viktor-cli create-app "Workflow Graph Agent" --registered-name workflow-graph-agent
viktor-cli clean-start
```

Set these values in `.env` for local runs:

```env
TOKEN_VK_APP=vktrpat_your_viktor_token
VIKTOR_ENVIRONMENT=demo.viktor.ai
```

No `OPENAI_API_KEY` is needed. The runner uses `vkt.ViktorOpenAI.get_base_url(...)` and `vkt.ViktorOpenAI.get_api_key()` for the LLM client.
The `openai` Python package is used only as the OpenAI-compatible client for VIKTOR's endpoint.

Use one canonical environment value in `.env`: the VIKTOR host only. Good examples are `demo.viktor.ai` and `cloud.us1.viktor.ai`. Do not include `https://` or `/api`. Inside a deployed VIKTOR app that calls another workspace in the same environment, `TOKEN_VK_APP` is enough and `VIKTOR_ENVIRONMENT` can be left unset.

## Generated Tools

Generated tools start from the notebook output in `convert-app-params-to-schema/<app>/`:

- `input_schema.json`: Pydantic tool input model and defaults.
- `available_methods.json`: methods the user can choose to implement.
- `first_method_result.json`: default output shape used to pick `data`, `table`, or another result key and design the summary/storage handoff.

Use the repo-root `SKILL.md` or `Claude.md` when adding another tool. The implemented files in `agent/tools/viktor_tools/` are the reference style.

`run_reaction_loads` uses a Pydantic model generated from the demo app parametrization:

```python
class ReactionLoadsInputs(BaseModel):
    distributed_load: float = 25.0
    number_of_reactions: int = 6
```

The tool calls the cross-workspace entity with `vkt.api_v1.API(...).get_workspace(2672).get_entity(12162).compute("get_data_view", params=...)`, selects the `table` result, and stores it in entity storage at `reaction_loads_table`.
The source artifacts for this shape are generated under `convert-app-params-to-schema/app1/` as `input_schema.json`, `available_methods.json`, and `first_method_result.json`.

`run_footing_design` calls the footing app at `https://demo.viktor.ai/workspaces/2673/app/editor/12163`. It exposes only `pad_thickness` in the tool signature, reads `P`, `My`, and `Mz` from `reaction_loads_table`, sends those reactions to the footing app, selects the `data` result, and stores it at `footing_design_data`.

Expected validation and prerequisite failures are returned as JSON tool output instead of hard exceptions. For example, if `reaction_loads_table` is missing, `run_footing_design` returns `status="needs_prerequisite"` with `retry_action.tool="run_reaction_loads"` so the agent can recover and retry.

Storage handoffs use entity scope:

```python
vkt.Storage().set(key, data=vkt.File.from_data(json.dumps(payload, indent=2)), scope="entity")
stored_file = vkt.Storage().get(key, scope="entity")
payload = json.loads(stored_file.getvalue_binary().decode("utf-8"))
```
