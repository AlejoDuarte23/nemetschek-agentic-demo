import json
from typing import Any

import viktor as vkt
from pydantic import BaseModel, Field, ValidationError

from agent.tools.viktor_tools.reaction_loads import REACTION_LOADS_STORAGE_KEY
from agent.tools.viktor_tools.responses import (
    execution_error_response,
    needs_prerequisite_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient, select_result_key


FOOTING_WORKSPACE_ID = 2673
FOOTING_ENTITY_ID = 12163
FOOTING_METHOD_NAME = "get_data_view"
FOOTING_RESULT_KEY = "data"
FOOTING_STORAGE_KEY = "footing_design_data"


class FootingReaction(BaseModel):
    p: float = Field(description="Axial reaction P in kN.")
    my: float = Field(description="Moment My in kNm.")
    mz: float = Field(description="Moment Mz in kNm.")


class FootingInputs(BaseModel):
    reactions: list[FootingReaction] = Field(
        description="Reaction rows loaded from the reaction-load app output.",
    )
    pad_thickness: float = Field(
        default=0.6,
        description="Pad thickness in meters.",
    )


class FootingComputeParams(BaseModel):
    inputs: FootingInputs


class FootingDesignParams(BaseModel):
    pad_thickness: float = Field(
        default=0.6,
        gt=0.0,
        description=(
            "Pad thickness in meters. Reaction rows are read from entity-scoped "
            "VIKTOR Storage key 'reaction_loads_table'."
        ),
    )


def read_json_from_storage(key: str) -> Any:
    stored_file = vkt.Storage().get(key, scope="entity")
    if not stored_file:
        raise FileNotFoundError(f"Missing VIKTOR Storage key '{key}'.")
    return json.loads(stored_file.getvalue_binary().decode("utf-8"))


def write_json_to_storage(key: str, payload: Any) -> None:
    vkt.Storage().set(
        key,
        data=vkt.File.from_data(json.dumps(payload, indent=2)),
        scope="entity",
    )


def get_cell_value(cell: Any) -> Any:
    if isinstance(cell, dict) and "value" in cell:
        return cell["value"]
    return cell


def parse_float(value: Any, *, field_name: str, row_number: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid {field_name} value in reaction table row {row_number}: {value!r}"
        ) from exc


def normalize_header(title: Any) -> str:
    return str(title or "").split("[", 1)[0].strip().lower()


def column_indexes(table: dict[str, Any]) -> dict[str, int]:
    headers = table.get("column_headers") or []
    normalized_headers = [
        normalize_header(header.get("title") if isinstance(header, dict) else header)
        for header in headers
    ]
    indexes: dict[str, int] = {}
    for key in ("p", "my", "mz"):
        if key not in normalized_headers:
            raise ValueError(
                f"Reaction table is missing required column '{key}'. "
                f"Available columns: {normalized_headers}"
            )
        indexes[key] = normalized_headers.index(key)
    return indexes


def reactions_from_table(table: dict[str, Any]) -> list[FootingReaction]:
    data_rows = table.get("data") or []
    if not isinstance(data_rows, list) or not data_rows:
        raise ValueError("Reaction table in storage does not contain any data rows.")

    indexes = column_indexes(table)
    reactions: list[FootingReaction] = []
    for row_number, row in enumerate(data_rows, start=1):
        if not isinstance(row, list):
            raise ValueError(f"Reaction table row {row_number} must be a list of cells.")
        reactions.append(
            FootingReaction(
                p=parse_float(
                    get_cell_value(row[indexes["p"]]),
                    field_name="P",
                    row_number=row_number,
                ),
                my=parse_float(
                    get_cell_value(row[indexes["my"]]),
                    field_name="My",
                    row_number=row_number,
                ),
                mz=parse_float(
                    get_cell_value(row[indexes["mz"]]),
                    field_name="Mz",
                    row_number=row_number,
                ),
            )
        )

    return reactions


def flatten_data_items(items: Any) -> dict[str, Any]:
    flattened: dict[str, Any] = {}

    def walk(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return

        key = value.get("key")
        if key and value.get("children") == []:
            flattened[str(key)] = value.get("value")

        walk(value.get("children"))

    walk(items)
    return flattened


def summarize_footing_data(data: Any) -> dict[str, Any]:
    flattened = flatten_data_items(data)
    summary_keys = [
        "width",
        "length",
        "thickness",
        "area",
        "maximum",
        "minimum",
        "utilization",
        "ratio",
        "reaction",
        "p",
        "my",
        "mz",
        "controlling_check",
    ]
    return {key: flattened[key] for key in summary_keys if key in flattened}


async def run_footing_design_func(context: Any, args: str) -> str:
    try:
        payload = FootingDesignParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_footing_design",
            message="Invalid footing-design tool arguments.",
            error=exc,
            retry_tool="run_footing_design",
            retry_reason="Retry with pad_thickness as a positive number in meters.",
        )

    try:
        reaction_table = read_json_from_storage(REACTION_LOADS_STORAGE_KEY)
        if not isinstance(reaction_table, dict):
            raise ValueError(
                f"Storage key '{REACTION_LOADS_STORAGE_KEY}' must contain a table object."
        )
        reactions = reactions_from_table(reaction_table)
    except FileNotFoundError as exc:
        return needs_prerequisite_response(
            tool="run_footing_design",
            message=(
                "Missing reaction-load table in VIKTOR Storage. "
                "Run run_reaction_loads first so it writes the required entity-scoped key."
            ),
            missing_storage_key=REACTION_LOADS_STORAGE_KEY,
            retry_tool="run_reaction_loads",
            retry_reason=(
                "run_reaction_loads creates the reaction_loads_table storage key "
                "needed by run_footing_design."
            ),
        )
    except json.JSONDecodeError as exc:
        return validation_error_response(
            tool="run_footing_design",
            message=f"Storage key '{REACTION_LOADS_STORAGE_KEY}' does not contain valid JSON.",
            error=exc,
            retry_tool="run_reaction_loads",
            retry_reason="Regenerate the reaction-load table in storage.",
        )
    except (ValueError, ValidationError, IndexError) as exc:
        return validation_error_response(
            tool="run_footing_design",
            message=(
                f"Storage key '{REACTION_LOADS_STORAGE_KEY}' does not contain "
                "a valid reaction-load table."
            ),
            error=exc,
            retry_tool="run_reaction_loads",
            retry_reason="Regenerate the reaction-load table in the expected TableView format.",
        )

    compute_params = FootingComputeParams(
        inputs=FootingInputs(
            reactions=reactions,
            pad_thickness=payload.pad_thickness,
        )
    )

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=FOOTING_WORKSPACE_ID,
            entity_id=FOOTING_ENTITY_ID,
            method_name=FOOTING_METHOD_NAME,
            params=compute_params.model_dump(),
        )
        data = select_result_key(result, FOOTING_RESULT_KEY)
        write_json_to_storage(FOOTING_STORAGE_KEY, data)
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_footing_design",
            message="The footing app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_footing_design",
            retry_reason="Retry after regenerating reaction_loads_table if needed.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_footing_design",
            message="Footing-design SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        method_name=FOOTING_METHOD_NAME,
        result_key=FOOTING_RESULT_KEY,
        input_storage_key=REACTION_LOADS_STORAGE_KEY,
        storage_key=FOOTING_STORAGE_KEY,
        reaction_count=len(reactions),
        summary=summarize_footing_data(data),
    )
