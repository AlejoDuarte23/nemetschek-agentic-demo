import copy
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.wind_turbine_common import (
    get_data_value,
    read_json_from_storage,
)
from agent.tools.viktor_tools.workflow_entities import (
    WORKFLOW_ENTITY_DIRECTORY_KEY,
    WorkflowNodeId,
    WorkflowRunEntity,
    get_workflow_entity_service,
    needs_workflow_run_response,
)


SourceKind = Literal["saved_params", "stored_output"]


RUN_TOOL_BY_NODE: dict[WorkflowNodeId, str] = {
    "wind_turbine_selector": "run_wind_turbine_selector",
    "cpt_pile_bearing": "run_cpt_pile_bearing",
    "foundation_analysis": "run_wind_turbine_foundation_analysis",
    "reinforcement": "run_wind_turbine_reinforcement",
    "cost_analysis": "run_wind_turbine_cost_analysis",
}


class MissingStoredOutputError(FileNotFoundError):
    def __init__(self, *, source_entity: WorkflowRunEntity) -> None:
        self.storage_key = source_entity.storage_key
        self.retry_tool = RUN_TOOL_BY_NODE[source_entity.node_id]
        super().__init__(
            f"Missing upstream stored output '{self.storage_key}'. Run {self.retry_tool} first."
        )


class WorkflowParamMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_node: WorkflowNodeId
    to_node: WorkflowNodeId
    source: str = Field(
        ...,
        description=(
            "Source key/path. Supports dotted and bracket paths, for example "
            "'step_geo.sec_plate.slab_thickness' or 'rows[0][3]'. DataView labels "
            "are also searched when source_kind='stored_output'."
        ),
    )
    target: str = Field(
        ...,
        description=(
            "Downstream saved-param path. Supports table/list rows with bracket "
            "indices, for example 'tab_loading.combinations[0].M_Ed'."
        ),
    )
    source_kind: SourceKind = Field(
        default="stored_output",
        description="Read from upstream saved params or from the upstream stored output.",
    )


class PropagateWorkflowParamsArgs(BaseModel):
    mappings: list[WorkflowParamMapping] = Field(
        ...,
        min_length=1,
        description="One or more explicit upstream-to-downstream parameter mappings.",
    )
    save_downstream: bool = Field(
        default=True,
        description="Persist patched downstream params through the VIKTOR API.",
    )


PathToken = str | int


class JsonPath:
    """Minimal dotted/bracket path helper for VIKTOR params and table rows."""

    @classmethod
    def get(cls, data: Any, path: str) -> Any:
        current = data
        for token in cls.parse(path):
            if isinstance(token, int):
                if not isinstance(current, list):
                    raise KeyError(f"Expected a list before index [{token}] in '{path}'.")
                current = current[token]
            else:
                if not isinstance(current, dict) or token not in current:
                    raise KeyError(f"Missing key '{token}' in '{path}'.")
                current = current[token]
        return current

    @classmethod
    def set(cls, data: dict[str, Any], path: str, value: Any) -> None:
        tokens = cls.parse(path)
        if not tokens:
            raise ValueError("Target path cannot be empty.")

        current: Any = data
        for index, token in enumerate(tokens):
            is_last = index == len(tokens) - 1
            next_token = None if is_last else tokens[index + 1]

            if isinstance(token, str):
                if not isinstance(current, dict):
                    raise TypeError(f"Cannot set key '{token}' on non-object path in '{path}'.")
                if is_last:
                    current[token] = copy.deepcopy(value)
                    return
                expected = [] if isinstance(next_token, int) else {}
                if not isinstance(current.get(token), (dict, list)):
                    current[token] = expected
                current = current[token]
                continue

            if not isinstance(current, list):
                raise TypeError(f"Cannot set index [{token}] on non-list path in '{path}'.")
            cls._extend_list(current, token, next_token=next_token)
            if is_last:
                current[token] = copy.deepcopy(value)
                return
            current = current[token]

    @classmethod
    def parse(cls, path: str) -> list[PathToken]:
        raw_path = path.strip()
        if not raw_path:
            raise ValueError("Path cannot be empty.")

        tokens: list[PathToken] = []
        for segment in raw_path.split("."):
            tokens.extend(cls._parse_segment(segment))
        return tokens

    @staticmethod
    def _parse_segment(segment: str) -> list[PathToken]:
        if not segment:
            raise ValueError("Path contains an empty segment.")
        if "[" not in segment:
            return [segment]

        tokens: list[PathToken] = []
        pos = 0
        while pos < len(segment):
            bracket = segment.find("[", pos)
            if bracket == -1:
                text = segment[pos:]
                if text:
                    tokens.append(text)
                break

            text = segment[pos:bracket]
            if text:
                tokens.append(text)

            end = segment.find("]", bracket)
            if end == -1:
                return [segment]
            index_text = segment[bracket + 1:end]
            if not index_text.isdigit():
                return [segment]
            tokens.append(int(index_text))
            pos = end + 1

        return tokens or [segment]

    @staticmethod
    def _extend_list(values: list[Any], index: int, *, next_token: PathToken | None) -> None:
        fill_value: Any = None
        if next_token is not None:
            fill_value = [] if isinstance(next_token, int) else {}
        while len(values) <= index:
            values.append(copy.deepcopy(fill_value))


class WorkflowParamPropagationService:
    def __init__(self) -> None:
        self.entity_service = get_workflow_entity_service()

    def propagate(self, payload: PropagateWorkflowParamsArgs) -> dict[str, Any]:
        downstream_params: dict[WorkflowNodeId, dict[str, Any]] = {}
        downstream_entities: dict[WorkflowNodeId, WorkflowRunEntity] = {}
        applied: list[dict[str, Any]] = []

        for mapping in payload.mappings:
            from_entity = self.entity_service.resolve_entity(mapping.from_node)
            to_entity = self.entity_service.resolve_entity(mapping.to_node)
            downstream_entities[mapping.to_node] = to_entity

            if mapping.to_node not in downstream_params:
                downstream_params[mapping.to_node] = self.entity_service.read_last_saved_params(
                    to_entity
                )

            source_data = self._read_source(mapping, from_entity)
            source_value = self._extract_source_value(
                source_data,
                source=mapping.source,
                source_kind=mapping.source_kind,
            )
            JsonPath.set(downstream_params[mapping.to_node], mapping.target, source_value)

            applied.append(
                {
                    "from_node": mapping.from_node,
                    "to_node": mapping.to_node,
                    "source_kind": mapping.source_kind,
                    "source": mapping.source,
                    "target": mapping.target,
                    "value_preview": self._preview_value(source_value),
                }
            )

        if payload.save_downstream:
            for node_id, params in downstream_params.items():
                target = downstream_entities[node_id]
                self.entity_service.set_last_saved_params(
                    target,
                    params,
                    message="Agent propagated workflow values into downstream params.",
                )

        return {
            "mapping_count": len(applied),
            "saved_downstream": payload.save_downstream,
            "updated_nodes": [
                {
                    "node_id": node_id,
                    "entity_id": downstream_entities[node_id].entity_id,
                    "url": downstream_entities[node_id].url,
                }
                for node_id in downstream_params
            ],
            "applied_mappings": applied,
        }

    def _read_source(self, mapping: WorkflowParamMapping, source_entity: WorkflowRunEntity) -> Any:
        if mapping.source_kind == "saved_params":
            return self.entity_service.read_last_saved_params(source_entity)
        try:
            return read_json_from_storage(source_entity.storage_key)
        except FileNotFoundError as exc:
            raise MissingStoredOutputError(source_entity=source_entity) from exc

    @staticmethod
    def _extract_source_value(data: Any, *, source: str, source_kind: SourceKind) -> Any:
        try:
            return JsonPath.get(data, source)
        except (KeyError, IndexError, TypeError):
            if source_kind == "stored_output":
                value = get_data_value(data, source)
                if value is not None:
                    return value
            raise ValueError(f"Could not resolve source '{source}'.")

    @staticmethod
    def _preview_value(value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        encoded = json.dumps(value, default=str)
        return encoded[:180] + ("..." if len(encoded) > 180 else "")


async def propagate_workflow_params_func(context: Any, args: str) -> str:
    try:
        payload = PropagateWorkflowParamsArgs.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="propagate_workflow_params",
            message="Invalid workflow propagation arguments.",
            error=exc,
            retry_tool="propagate_workflow_params",
            retry_reason="Retry with a mappings list containing source and target paths.",
        )

    try:
        result = WorkflowParamPropagationService().propagate(payload)
    except MissingStoredOutputError as exc:
        return tool_response(
            "needs_prerequisite",
            tool="propagate_workflow_params",
            message=str(exc),
            missing_storage_key=exc.storage_key,
            retry_action={
                "tool": exc.retry_tool,
                "reason": "Run the upstream compute tool so its output is available.",
            },
        )
    except FileNotFoundError as exc:
        if WORKFLOW_ENTITY_DIRECTORY_KEY in str(exc):
            return needs_workflow_run_response(
                tool="propagate_workflow_params",
                node_id=payload.mappings[0].to_node,
            )
        return tool_response(
            "needs_prerequisite",
            tool="propagate_workflow_params",
            message=str(exc),
        )
    except KeyError as exc:
        return needs_workflow_run_response(
            tool="propagate_workflow_params",
            node_id=payload.mappings[0].to_node,
        )
    except (TypeError, ValueError, IndexError) as exc:
        return validation_error_response(
            tool="propagate_workflow_params",
            message="Could not apply one or more workflow parameter mappings.",
            error=exc,
            retry_tool="propagate_workflow_params",
            retry_reason="Check source paths, target paths, and table/list indices.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="propagate_workflow_params",
            message="Workflow parameter propagation failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Propagated workflow values into downstream params.",
        **result,
    )
