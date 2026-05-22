---
name: viktor-workflow-graph-template
description: Create a VIKTOR app template with Agents SDK chat backed by VIKTOR's LLM service, an agent/runner.py module, agent/system_prompt.xml, grouped graph tools, SDK-backed generated VIKTOR tools, entity-scoped vkt.Storage handoffs, workflow graph rendering, and streamed tool-call status in chat.
---

# VIKTOR Workflow Graph Template

Use this skill when building a VIKTOR app that combines an agent chat, a workflow graph WebView, tool-call progress in chat, generated VIKTOR app tools, and entity-scoped `vkt.Storage` handoffs between tools.

## Grounding

This template follows the local VIKTOR skill sequence:

1. Load `viktor-core` for `app.py`, `Parametrization`, `Controller`, views, and `vkt.UserError`.
2. Load `viktor-parametrization` before changing inputs.
3. Load `viktor-styling` before writing app text.
4. Load `viktor-cli-config` before creating or running the app.
5. Load `viktor-sdk-api` for generated tools that execute VIKTOR methods through `Entity.compute(...)`.

It also mirrors the inspected repository patterns:

- `app/workflow_graph/models.py`, `state.py`, and `viewer.py` for schema, storage state, and self-contained HTML.
- `app/agent/tools/graph_tools/` for workflow graph composition, plan updates, and progress tools.
- `app/agent/tools/viktor_tools/` for SDK-backed generated VIKTOR app tools.
- `app/agent/runner.py` for `Runner.run_streamed(...)` into `vkt.ChatResult` using `vkt.ViktorOpenAI`, including rendered tool-call rows.
- `app/agent/system_prompt.xml` for XML-structured agent instructions.

## Template Location

This folder is the VIKTOR app template root. Copy the app files from this folder into a new VIKTOR app folder.

## Required Environment

- `TOKEN_VK_APP` or `VIKTOR_TOKEN` for cross-workspace SDK API calls.
- `VIKTOR_ENVIRONMENT`, host-only, for example `demo.viktor.ai` or `cloud.us1.viktor.ai`, when running outside the deployed VIKTOR app context.
- No `OPENAI_API_KEY`; the LLM client uses `vkt.ViktorOpenAI`.

## First Run

```bash
viktor-cli create-app "Workflow Graph Agent" --registered-name workflow-graph-agent
viktor-cli clean-start
```

Make sure `viktor.config.toml` contains the same `registered_name`.

## Implementation Rules

1. Keep `app.py` as the VIKTOR entrypoint.
2. Keep workflow graph schema and state in `workflow_graph/`.
3. Keep agent and runner code in `agent/runner.py`.
4. Keep the system prompt in `agent/system_prompt.xml`.
5. Keep graph tools in `agent/tools/graph_tools/` and generated VIKTOR tools in `agent/tools/viktor_tools/`.
6. Always call `compose_workflow_graph` before plan or progress tools.
7. Always call `get_workflow_plan` before `update_workflow_plan`.
8. Register only generated tools that are currently implemented.
9. Use `vkt.api_v1.API(token=...).get_workspace(...).get_entity(...).compute(...)` for generated tools that call external VIKTOR app methods.
10. Use `vkt.Storage(..., scope="entity")` for tool handoffs; producer tools write stable keys and consumer tools read them internally instead of exposing generated data in the tool signature.
11. Return expected validation or missing-prerequisite failures as JSON tool output with `status`, `message`, and optional `retry_action`; do not raise for recoverable workflow issues.
12. Stream tool calls into chat by consuming `result.stream_events()` and rendering `tool_called` and `tool_output` events.

## Files

- `app.py`: VIKTOR controller and graph WebView.
- `agent/runner.py`: Agents SDK agent construction with the VIKTOR LLM client and streamed runner.
- `agent/system_prompt.xml`: XML system prompt.
- `agent/tools/graph_tools/`: graph, plan, and progress tools.
- `agent/tools/viktor_tools/`: generated reaction-load and footing-design tools plus the SDK compute client.
- `workflow_graph/`: graph models, state, renderer, CSS, and JS.
- `requirements.txt`: Python dependencies for the VIKTOR app.
- `viktor.config.toml`: local VIKTOR app config.
