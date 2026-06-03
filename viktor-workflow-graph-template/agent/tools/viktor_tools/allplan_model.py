import json
import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent.tools.viktor_tools.cpt_pile_bearing import required_pile_length_from_cpt_data
from agent.tools.viktor_tools.responses import (
    execution_error_response,
    needs_prerequisite_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.wind_turbine_common import (
    ALLPLAN_MODEL_STORAGE_KEY,
    CPT_PILE_BEARING_STORAGE_KEY,
    FOUNDATION_PARAMS_STORAGE_KEY,
    REINFORCEMENT_STORAGE_KEY,
    get_data_value,
    read_json_from_storage,
    rounded_positive_int,
    select_and_store_result,
)
from agent.tools.viktor_tools.workflow_entities import (
    deep_merge_params,
    needs_workflow_run_response,
    read_last_saved_params,
    resolve_workflow_entity,
    set_last_saved_params,
)


class AllplanGeometryInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    foundation_diameter: float = Field(default=14500.0)
    foundation_edge_thickness: float = Field(default=1000.0)
    foundation_center_thickness: float = Field(default=4500.0)
    pedestal_diameter: float = Field(default=5000.0)
    pedestal_height: float = Field(default=1000.0)
    pile_count: int = Field(default=24)
    pile_edge_distance: float = Field(default=750.0)
    pile_diameter: float = Field(default=400.0)
    pile_depth: float = Field(default=10000.0)


class AllplanReinforcementInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover: float = Field(default=75.0)
    top_radial_bar_diameter: float = Field(default=25.0)
    top_radial_bar_count: int = Field(default=32)
    ring_bar_diameter: float = Field(default=20.0)
    ring_spacing: float = Field(default=550.0)
    pedestal_grid_bar_diameter: float = Field(default=20.0)
    pedestal_grid_spacing: float = Field(default=350.0)
    pedestal_tie_diameter: float = Field(default=12.0)
    pedestal_tie_spacing: float = Field(default=250.0)
    pile_vertical_diameter: float = Field(default=16.0)
    pile_vertical_count: int = Field(default=8)
    pile_vertical_embed_depth: float = Field(default=500.0)
    pile_hoop_diameter: float = Field(default=10.0)
    pile_hoop_spacing: float = Field(default=300.0)


class AllplanComputeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: AllplanGeometryInputs = Field(default_factory=AllplanGeometryInputs)
    reinforcement: AllplanReinforcementInputs = Field(
        default_factory=AllplanReinforcementInputs
    )


class AllplanGeometryOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    foundation_diameter: float | None = Field(default=None, description="Override in mm.")
    foundation_edge_thickness: float | None = Field(
        default=None, description="Override in mm."
    )
    foundation_center_thickness: float | None = Field(
        default=None, description="Override in mm."
    )
    pedestal_diameter: float | None = Field(default=None, description="Override in mm.")
    pedestal_height: float | None = Field(default=None, description="Override in mm.")
    pile_count: int | None = Field(default=None)
    pile_edge_distance: float | None = Field(default=None, description="Override in mm.")
    pile_diameter: float | None = Field(default=None, description="Override in mm.")
    pile_depth: float | None = Field(default=None, description="Override in mm.")


class AllplanReinforcementOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover: float | None = Field(default=None, description="Override in mm.")
    top_radial_bar_diameter: float | None = Field(default=None, description="Override in mm.")
    top_radial_bar_count: int | None = None
    ring_bar_diameter: float | None = Field(default=None, description="Override in mm.")
    ring_spacing: float | None = Field(default=None, description="Override in mm.")
    pedestal_grid_bar_diameter: float | None = Field(
        default=None, description="Override in mm."
    )
    pedestal_grid_spacing: float | None = Field(default=None, description="Override in mm.")
    pedestal_tie_diameter: float | None = Field(default=None, description="Override in mm.")
    pedestal_tie_spacing: float | None = Field(default=None, description="Override in mm.")
    pile_vertical_diameter: float | None = Field(default=None, description="Override in mm.")
    pile_vertical_count: int | None = None
    pile_vertical_embed_depth: float | None = Field(
        default=None, description="Override in mm."
    )
    pile_hoop_diameter: float | None = Field(default=None, description="Override in mm.")
    pile_hoop_spacing: float | None = Field(default=None, description="Override in mm.")


class AllplanModelParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geometry: AllplanGeometryOverrides = Field(default_factory=AllplanGeometryOverrides)
    reinforcement: AllplanReinforcementOverrides = Field(
        default_factory=AllplanReinforcementOverrides
    )


def drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: drop_none(item) for key, item in value.items() if item is not None}
    return value


def metres_to_mm(value: Any, *, default: float) -> float:
    try:
        return float(value) * 1000.0
    except (TypeError, ValueError):
        return default


def number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        match = re.search(r"[-+]?\d*\.?\d+", value)
        if not match:
            return None
        value = match.group(0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def reinforcement_output_number(data: Any, *keys: str) -> float | None:
    return number_or_none(get_data_value(data, *keys))


def first_number(*values: Any) -> float | None:
    for value in values:
        number = number_or_none(value)
        if number is not None:
            return number
    return None


def max_number(*values: Any) -> float | None:
    numbers = [number_or_none(value) for value in values]
    numbers = [number for number in numbers if number is not None]
    return max(numbers) if numbers else None


def radial_count_from_spacing(
    *,
    foundation_diameter: float,
    cover: float | None,
    spacing: float | None,
) -> int | None:
    if spacing is None or spacing <= 0:
        return None
    effective_diameter = max(0.0, foundation_diameter - 2.0 * (cover or 0.0))
    if effective_diameter <= 0:
        return None
    return max(1, math.ceil(math.pi * effective_diameter / spacing))


def allplan_payload_from_saved_params(saved_params: dict[str, Any]) -> dict[str, Any]:
    default_payload = AllplanComputeParams().model_dump()
    if not isinstance(saved_params, dict):
        return default_payload
    saved_payload = {
        key: value
        for key, value in saved_params.items()
        if key in {"geometry", "reinforcement"}
    }
    return AllplanComputeParams.model_validate(
        deep_merge_params(default_payload, saved_payload)
    ).model_dump()


def reinforcement_params_from_saved_params(saved_params: dict[str, Any]) -> dict[str, Any]:
    geometry = saved_params.get("tab_geometry", {}) if isinstance(saved_params, dict) else {}
    optimise = saved_params.get("tab_optimise", {}) if isinstance(saved_params, dict) else {}
    return {
        "cover": geometry.get("cover"),
        "dia_bottom": geometry.get("dia_bottom"),
        "dia_top": geometry.get("dia_top"),
        "spacing_bottom": geometry.get("spacing_bottom"),
        "spacing_top": geometry.get("spacing_top"),
        "stirrup_dia": geometry.get("stirrup_dia"),
        "spacing_min": optimise.get("spacing_min"),
    }


def build_allplan_upstream_payload(
    *,
    foundation_params: dict[str, Any],
    cpt_data: Any,
    reinforcement_data: Any,
    reinforcement_saved_params: dict[str, Any],
) -> dict[str, Any]:
    step_geo = foundation_params["step_geo"]
    mast = step_geo["sec_mast"]
    plate = step_geo["sec_plate"]
    piles = step_geo["sec_piles"]

    required_pile_length = required_pile_length_from_cpt_data(cpt_data)
    if required_pile_length is None:
        raise ValueError("Stored CPT output does not include a required pile length.")

    foundation_diameter = metres_to_mm(plate["slab_diameter"], default=14500.0)
    foundation_edge_thickness = metres_to_mm(
        plate["plate_edge_thickness"],
        default=1000.0,
    )
    foundation_center_thickness = metres_to_mm(
        plate["slab_thickness"],
        default=4500.0,
    )
    pedestal_diameter = metres_to_mm(mast["mast_diameter"], default=5000.0)
    pedestal_height = metres_to_mm(plate["pedestal_height"], default=1000.0)

    reinforcement_params = reinforcement_params_from_saved_params(reinforcement_saved_params)
    cover = reinforcement_output_number(reinforcement_data, "cover", "Clear cover")
    optimized_spacing = reinforcement_output_number(
        reinforcement_data,
        "spc_item",
        "spacing",
        "spacing_ctc",
        "spacing_ctc_top_bottom",
        "Spacing ctc (top & bottom)",
        "Spacing ctc",
    )
    optimized_bottom_diameter = reinforcement_output_number(
        reinforcement_data,
        "dia_bot_item",
        "dia_bottom",
        "bottom_bar_diameter",
        "Bottom bar diameter",
    )
    optimized_top_diameter = reinforcement_output_number(
        reinforcement_data,
        "dia_top_item",
        "dia_top",
        "top_bar_diameter",
        "Top bar diameter",
    )
    selected_cover = first_number(cover, reinforcement_params.get("cover"))
    selected_spacing = first_number(
        optimized_spacing,
        reinforcement_params.get("spacing_bottom"),
        reinforcement_params.get("spacing_top"),
    )
    selected_top_diameter = first_number(
        optimized_top_diameter,
        reinforcement_params.get("dia_top"),
    )
    selected_bottom_diameter = first_number(
        optimized_bottom_diameter,
        reinforcement_params.get("dia_bottom"),
    )
    governing_main_diameter = max_number(
        selected_top_diameter,
        selected_bottom_diameter,
    )
    reinforcement_payload = {
        "cover": selected_cover,
        "top_radial_bar_diameter": governing_main_diameter,
        "top_radial_bar_count": radial_count_from_spacing(
            foundation_diameter=foundation_diameter,
            cover=selected_cover,
            spacing=selected_spacing,
        ),
        "ring_bar_diameter": governing_main_diameter,
        "ring_spacing": selected_spacing,
        "pedestal_grid_bar_diameter": selected_top_diameter,
        "pedestal_grid_spacing": selected_spacing or reinforcement_params.get("spacing_top"),
        "pedestal_tie_diameter": reinforcement_params.get("stirrup_dia"),
        "pile_hoop_diameter": reinforcement_params.get("stirrup_dia"),
    }

    return drop_none(
        {
            "geometry": {
                "foundation_diameter": foundation_diameter,
                "foundation_edge_thickness": foundation_edge_thickness,
                "foundation_center_thickness": foundation_center_thickness,
                "pedestal_diameter": pedestal_diameter,
                "pedestal_height": pedestal_height,
                "pile_count": rounded_positive_int(piles["num_piles"], default=24),
                "pile_edge_distance": float(piles["pile_edge_distance"]),
                "pile_diameter": float(piles["pile_diameter"]),
                "pile_depth": required_pile_length * 1000.0,
            },
            "reinforcement": reinforcement_payload,
        }
    )


def table_cell_value(cell: Any) -> Any:
    if isinstance(cell, dict):
        return cell.get("value", cell.get("display_value"))
    return cell


def summarize_allplan_table(table: Any, params: AllplanComputeParams) -> dict[str, Any]:
    if not isinstance(table, dict):
        return {
            "foundation_diameter_mm": params.geometry.foundation_diameter,
            "pile_count": params.geometry.pile_count,
            "pile_depth_mm": params.geometry.pile_depth,
        }

    headers = table.get("column_headers") or []
    rows = table.get("data") or []
    titles = [
        str(header.get("title", ""))
        for header in headers
        if isinstance(header, dict)
    ]
    total_length_index = next(
        (index for index, title in enumerate(titles) if title == "Total length [m]"),
        None,
    )
    total_length = 0.0
    if total_length_index is not None:
        for row in rows:
            if not isinstance(row, list) or total_length_index >= len(row):
                continue
            value = number_or_none(table_cell_value(row[total_length_index]))
            if value is not None:
                total_length += value

    return {
        "foundation_diameter_mm": params.geometry.foundation_diameter,
        "pile_count": params.geometry.pile_count,
        "pile_depth_mm": params.geometry.pile_depth,
        "schedule_rows": len(rows) if isinstance(rows, list) else 0,
        "total_bar_length_m": round(total_length, 2),
    }


async def run_allplan_model_func(context: Any, args: str) -> str:
    try:
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        payload = AllplanModelParams.model_validate(explicit_args or {})
        target = resolve_workflow_entity("allplan_model")
        saved_params = read_last_saved_params(target)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_allplan_model",
            node_id="allplan_model",
        )
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_allplan_model",
            message="Invalid Allplan model arguments.",
            error=exc,
            retry_tool="run_allplan_model",
            retry_reason="Retry with geometry or reinforcement overrides in millimeters.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_allplan_model",
            message="Could not read the workflow Allplan entity.",
            error=exc,
        )

    try:
        foundation_params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)
        cpt_data = read_json_from_storage(CPT_PILE_BEARING_STORAGE_KEY)
        reinforcement_data = read_json_from_storage(REINFORCEMENT_STORAGE_KEY)
    except FileNotFoundError as exc:
        missing_key = str(exc).split("'")[1] if "'" in str(exc) else FOUNDATION_PARAMS_STORAGE_KEY
        retry_tool = {
            FOUNDATION_PARAMS_STORAGE_KEY: "run_wind_turbine_foundation_analysis",
            CPT_PILE_BEARING_STORAGE_KEY: "run_cpt_pile_bearing",
            REINFORCEMENT_STORAGE_KEY: "run_wind_turbine_reinforcement",
        }.get(missing_key, "run_wind_turbine_foundation_analysis")
        return needs_prerequisite_response(
            tool="run_allplan_model",
            message="Missing upstream workflow output needed for the Allplan model.",
            missing_storage_key=missing_key,
            retry_tool=retry_tool,
            retry_reason="Run the upstream foundation, CPT, and reinforcement tools first.",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_allplan_model",
            message="Stored upstream workflow output is invalid.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Regenerate foundation, CPT, and reinforcement outputs.",
        )

    try:
        try:
            reinforcement_target = resolve_workflow_entity("reinforcement")
            reinforcement_saved_params = read_last_saved_params(reinforcement_target)
        except Exception:
            reinforcement_saved_params = {}

        upstream_payload = build_allplan_upstream_payload(
            foundation_params=foundation_params,
            cpt_data=cpt_data,
            reinforcement_data=reinforcement_data,
            reinforcement_saved_params=reinforcement_saved_params,
        )
        compute_payload = deep_merge_params(
            allplan_payload_from_saved_params(saved_params),
            upstream_payload,
        )
        compute_payload = deep_merge_params(
            compute_payload,
            drop_none(payload.model_dump()),
        )
        compute_params = AllplanComputeParams.model_validate(compute_payload)
        compute_payload = compute_params.model_dump()
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_allplan_model",
            message="Could not map foundation geometry and reinforcement into Allplan inputs.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Regenerate foundation/CPT/reinforcement outputs or provide overrides.",
        )

    try:
        set_last_saved_params(
            target,
            deep_merge_params(saved_params, compute_payload),
            message="Agent patched Allplan params with foundation geometry and reinforcement.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_allplan_model",
            message="Could not update the workflow Allplan entity params.",
            error=exc,
        )

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            method_name=target.method_name,
            params=compute_payload,
        )
        table = select_and_store_result(
            result=result,
            result_key=target.result_key,
            storage_key=target.storage_key,
        )
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_allplan_model",
            message="The Allplan model app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_allplan_model",
            retry_reason="Retry after checking Allplan geometry and reinforcement inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_allplan_model",
            message="Allplan model SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Computed Allplan model schedule and stored the table.",
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        input_storage_keys=[
            FOUNDATION_PARAMS_STORAGE_KEY,
            CPT_PILE_BEARING_STORAGE_KEY,
            REINFORCEMENT_STORAGE_KEY,
        ],
        storage_key=ALLPLAN_MODEL_STORAGE_KEY,
        summary=summarize_allplan_table(table, compute_params),
    )
