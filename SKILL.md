---
name: convert-schema-to-tool
description: Use when converting VIKTOR parametrization schemas and available-method metadata into typed Agents SDK tools that call VIKTOR app methods through the VIKTOR SDK API.
---

# Convert VIKTOR Schema To Agent Tool

Use this skill when a VIKTOR app has:

- a per-app artifact folder such as `convert-app-params-to-schema/app1/`;
- an input schema at `input_schema.json`;
- available method metadata at `available_methods.json`;
- an optional default method result at `first_method_result.json`;
- a target entity and workspace that can be called with the VIKTOR SDK API.

The output is a typed Agents SDK tool with Pydantic defaults and a deterministic SDK compute call.

## Workflow

1. Read the generated app artifact folder.
   - Load `input_schema.json` for the tool input model.
   - Load `available_methods.json` for callable VIKTOR methods.
   - Load `first_method_result.json` when you need the default output shape.
2. Ask the user which available method to implement.
   - Show the method name, label, view/action type, and source from the available-methods file.
   - If there is exactly one method, state that method and continue unless the user asked to choose explicitly.
   - If there are multiple methods, do not guess; ask before writing tool code.
3. Build Pydantic models from the schema.
   - Preserve nested structure, for example `inputs.distributed_load`.
   - Preserve `default` values from the schema.
   - Use `default_factory` for nested models and list defaults.
4. Create one tool for the selected callable VIKTOR method.
   - Prefer a stable verb phrase such as `run_reaction_loads`.
   - Keep tool args typed; do not expose arbitrary `dict[str, Any]` as the tool input.
5. Execute the VIKTOR method through SDK compute:
   - Use `vkt.api_v1.API(token=...).get_workspace(workspace_id).get_entity(entity_id).compute(method_name, params=params)`.
   - Use a token for cross-workspace calls.
   - Pass `environment=...` when running outside the deployed VIKTOR app context.
6. Select the output payload from the result.
   - Prefer the selected method's expected key, for example `table` for `TableView` and `data` for `DataView`.
   - Otherwise check keys in this order: `data`, `table`, `download`, `geometry`, `plotly`, `geojson`, `web`, `pdf`, `image`, `ifc`, `optimization`, `set_params`.
   - Keep the full result if none of those keys exist.
7. Store the selected result in `vkt.Storage` with a stable key for downstream tools.
   - Use `scope="entity"` for handoffs that belong to the current VIKTOR entity.
   - When generating a downstream tool, expose only the parameters not provided by upstream storage.
   - Read upstream JSON with `vkt.Storage().get(key, scope="entity").getvalue_binary().decode("utf-8")`.
8. Register the tool in the Agents SDK registry and add a short display name.
9. Validate:
   - Python compile passes.
   - Pydantic schema has defaults and no open-ended tool input dict.
   - A live SDK compute smoke test works with `TOKEN_VK_APP` and `VIKTOR_ENVIRONMENT` when needed.
10. Return recoverable failures as tool output instead of exceptions.
   - Use `status="validation_error"` when arguments or stored data are malformed.
   - Use `status="needs_prerequisite"` when a required storage key is missing.
   - Include `retry_action.tool` when the agent can call another tool to recover.

## Pydantic Pattern

For this schema:

```json
{
  "properties": {
    "inputs": {
      "properties": {
        "distributed_load": {"type": "number", "default": 25.0},
        "number_of_reactions": {"type": "integer", "default": 6}
      }
    }
  }
}
```

Use this shape:

```python
class ReactionLoadsInputs(BaseModel):
    distributed_load: float = Field(default=25.0)
    number_of_reactions: int = Field(default=6)


class ReactionLoadsParams(BaseModel):
    inputs: ReactionLoadsInputs = Field(default_factory=ReactionLoadsInputs)
```

This lets the agent call the tool with `{}` and still send valid VIKTOR params.

## SDK Compute Pattern

Use a small client/helper instead of repeating SDK setup. It should:

- read `TOKEN_VK_APP` or `VIKTOR_TOKEN`;
- read `VIKTOR_ENVIRONMENT` as a host-only value such as `demo.viktor.ai` when running outside a deployed VIKTOR app context;
- create `vkt.api_v1.API(token=...)` for cross-workspace calls;
- call `workspace.get_entity(entity_id).compute(method_name, params=params, timeout=timeout)`;
- return the JSON `dict` result.

The notebook-generated `first_method_result.json` is a useful fixture for shaping summaries and storage keys, but the tool should still call live SDK compute at runtime. The SDK compute call is built on top of the VIKTOR API job mechanism, but it hides the raw `POST /jobs/` and polling.

Tool function shape:

```python
async def run_reaction_loads_func(context: Any, args: str) -> str:
    payload = ReactionLoadsParams.model_validate_json(args or "{}")
    params = payload.model_dump()
    result = client.compute_method(
        workspace_id=2672,
        entity_id=12162,
        method_name="get_data_view",
        params=params,
    )
    table = result["table"]
    write_json_to_storage("reaction_loads_table", table)
    return json.dumps({"status": "completed", "storage_key": "reaction_loads_table"})
```

## Strict Schema Rules

- Do not use a shared `Tool` base class to solve strict schema issues.
- Do not expose arbitrary `dict[str, Any]` fields in Agents SDK tool args.
- Use explicit Pydantic fields for generated app params.
- If a tool truly needs arbitrary JSON, expose it as a JSON string and parse internally.
