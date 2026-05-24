from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.workflow_entities import (
    WorkflowNodeId,
    get_workflow_entity_service,
    needs_workflow_run_response,
)


class SetParamsInNodeArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: WorkflowNodeId = Field(
        ...,
        description="Known workflow node id whose saved VIKTOR params should be updated.",
    )
    params: dict[str, JsonValue] = Field(
        ...,
        min_length=1,
        description=(
            "Saved-param object to write into the workflow node. Tables should be "
            "passed as their full list/dict structure."
        ),
    )
    merge: bool = Field(
        default=True,
        description="Deep merge into the node's current saved params. If false, replace all saved params.",
    )


class WorkflowNodeParamService:
    """Updates saved params for an entity in the active workflow directory."""

    def __init__(self) -> None:
        self.entity_service = get_workflow_entity_service()

    def set_params(self, payload: SetParamsInNodeArgs) -> dict[str, Any]:
        target = self.entity_service.resolve_entity(payload.node_id)
        updates = dict(payload.params)
        next_params = updates

        if payload.merge:
            current_params = self.entity_service.read_last_saved_params(target)
            next_params = self.entity_service.deep_merge(current_params, updates)

        self.entity_service.set_last_saved_params(
            target,
            next_params,
            message="Agent updated workflow node params.",
        )

        return {
            "node_id": payload.node_id,
            "entity_id": target.entity_id,
            "url": target.url,
            "merge": payload.merge,
            "updated_top_level_keys": sorted(updates),
        }


async def set_params_in_node_func(context: Any, args: str) -> str:
    try:
        payload = SetParamsInNodeArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="set_params_in_node",
            message="Invalid workflow node params arguments.",
            error=exc,
            retry_tool="set_params_in_node",
            retry_reason="Retry with node_id and a JSON-safe params object.",
        )

    try:
        result = WorkflowNodeParamService().set_params(payload)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="set_params_in_node",
            node_id=payload.node_id,
        )
    except Exception as exc:
        return execution_error_response(
            tool="set_params_in_node",
            message="Could not update workflow node saved params.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Updated workflow node saved params.",
        **result,
    )
