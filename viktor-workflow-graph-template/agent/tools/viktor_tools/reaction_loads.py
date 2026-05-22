import json
from typing import Any

import viktor as vkt
from pydantic import BaseModel, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient, select_result_key


REACTION_LOADS_WORKSPACE_ID = 2672
REACTION_LOADS_ENTITY_ID = 12162
REACTION_LOADS_METHOD_NAME = "get_data_view"
REACTION_LOADS_RESULT_KEY = "table"
REACTION_LOADS_STORAGE_KEY = "reaction_loads_table"


class ReactionLoadsInputs(BaseModel):
    distributed_load: float = Field(
        default=25.0,
        description="Distributed load used by the reaction-load app.",
    )
    number_of_reactions: int = Field(
        default=6,
        description="Number of reaction rows to generate.",
    )


class ReactionLoadsParams(BaseModel):
    inputs: ReactionLoadsInputs = Field(
        default_factory=ReactionLoadsInputs,
        description="VIKTOR parametrization payload for the reaction-load app.",
    )


def write_json_to_storage(key: str, payload: Any) -> None:
    vkt.Storage().set(
        key,
        data=vkt.File.from_data(json.dumps(payload, indent=2)),
        scope="entity",
    )


def normalize_header(header: Any) -> str:
    title = header.get("title") if isinstance(header, dict) else header
    return str(title or "").split("[", 1)[0].strip().lower()


def get_cell_value(cell: Any) -> Any:
    if isinstance(cell, dict) and "value" in cell:
        return cell["value"]
    return cell


def summarize_table(table: dict[str, Any]) -> dict[str, Any]:
    column_headers = table.get("column_headers") or []
    data = table.get("data") or []
    columns = [
        header.get("title") if isinstance(header, dict) else str(header)
        for header in column_headers
        if header
    ]
    summary: dict[str, Any] = {
        "row_count": len(data),
        "columns": columns,
    }

    normalized_headers = [normalize_header(header) for header in column_headers]
    if "p" not in normalized_headers or not isinstance(data, list):
        return summary

    p_index = normalized_headers.index("p")
    reaction_index = (
        normalized_headers.index("reaction")
        if "reaction" in normalized_headers
        else None
    )
    p_values: list[tuple[int, str, float]] = []
    for row_index, row in enumerate(data, start=1):
        if not isinstance(row, list) or p_index >= len(row):
            continue
        try:
            p_value = float(get_cell_value(row[p_index]))
        except (TypeError, ValueError):
            continue

        reaction_label = f"Row {row_index}"
        if reaction_index is not None and reaction_index < len(row):
            reaction_label = str(get_cell_value(row[reaction_index]) or reaction_label)
        p_values.append((row_index, reaction_label, p_value))

    if not p_values:
        return summary

    min_p = min(p_values, key=lambda item: item[2])
    max_p = max(p_values, key=lambda item: item[2])
    summary.update(
        min_p_kN=round(min_p[2], 2),
        max_p_kN=round(max_p[2], 2),
        critical_reaction=max_p[1],
    )
    return summary


def summarize_response(summary: dict[str, Any]) -> str:
    row_count = summary.get("row_count", 0)
    if {"min_p_kN", "max_p_kN", "critical_reaction"} <= summary.keys():
        return (
            f"Generated {row_count} reactions. "
            f"P ranges {summary['min_p_kN']} to {summary['max_p_kN']} kN; "
            f"critical: {summary['critical_reaction']}."
        )
    return f"Generated {row_count} reactions."


async def run_reaction_loads_func(context: Any, args: str) -> str:
    try:
        payload = ReactionLoadsParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_reaction_loads",
            message="Invalid reaction-load tool arguments.",
            error=exc,
            retry_tool="run_reaction_loads",
            retry_reason=(
                "Retry with inputs.distributed_load as a number and "
                "inputs.number_of_reactions as an integer."
            ),
        )

    params = payload.model_dump()

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=REACTION_LOADS_WORKSPACE_ID,
            entity_id=REACTION_LOADS_ENTITY_ID,
            method_name=REACTION_LOADS_METHOD_NAME,
            params=params,
        )
        table = select_result_key(result, REACTION_LOADS_RESULT_KEY)
        write_json_to_storage(REACTION_LOADS_STORAGE_KEY, table)
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_reaction_loads",
            message="The reaction-load app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_reaction_loads",
            retry_reason="Retry with valid reaction-load inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_reaction_loads",
            message="Reaction-load SDK compute or storage write failed.",
            error=exc,
        )

    summary = summarize_table(table)
    return tool_response(
        "completed",
        message=summarize_response(summary),
        method_name=REACTION_LOADS_METHOD_NAME,
        result_key=REACTION_LOADS_RESULT_KEY,
        storage_key=REACTION_LOADS_STORAGE_KEY,
        summary=summary,
    )
