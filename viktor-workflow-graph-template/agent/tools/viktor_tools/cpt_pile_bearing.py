import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    needs_prerequisite_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.wind_turbine_common import (
    FOUNDATION_PARAMS_STORAGE_KEY,
    FOUNDATION_STORAGE_KEY,
    get_data_value,
    get_number,
    read_json_from_storage,
    select_and_store_result,
)
from agent.tools.viktor_tools.workflow_entities import (
    deep_merge_params,
    needs_workflow_run_response,
    read_last_saved_params,
    resolve_workflow_entity,
    set_last_saved_params,
)


class CptLocation(BaseModel):
    lat: float = Field(default=51.9694, description="Latitude for nearest CPT lookup.")
    lon: float = Field(default=5.0965, description="Longitude for nearest CPT lookup.")


class CptStep1(BaseModel):
    location: CptLocation = Field(default_factory=CptLocation)
    search_radius: float = Field(default=1.0, description="CPT search radius in km.")
    min_cpt_depth: float = Field(default=20.0, description="Minimum CPT depth in m.")


class CptPileSection(BaseModel):
    pile_tip_level: float = Field(default=-17.0, description="Pile tip level in m NAP.")
    pile_diameter: int = Field(default=400, description="Pile diameter or width in mm.")
    pile_shape: str = Field(default="Round", description="Pile cross-section shape.")
    pile_type: str = Field(default="Bored pile", description="Pile construction type.")


class CptLoadSection(BaseModel):
    design_load: float = Field(default=1100.0, description="Applied design load in kN.")


class CptStep2(BaseModel):
    sec_pile: CptPileSection = Field(default_factory=CptPileSection)
    sec_load: CptLoadSection = Field(default_factory=CptLoadSection)


class CptPileBearingParams(BaseModel):
    step1: CptStep1 = Field(default_factory=CptStep1)
    step2: CptStep2 = Field(default_factory=CptStep2)


def summarize_cpt_data(data: Any) -> dict[str, Any]:
    return {
        "pile_type": get_data_value(data, "pile_type_item", "Pile type"),
        "pile_diameter_mm": get_data_value(data, "diameter_item", "Diameter / width"),
        "pile_length_m": get_data_value(
            data,
            "length_item",
            "Pile length",
            "required_length",
            "required_length_item",
            "required_pile_length",
            "required_pile_length_item",
            "Required pile length",
            "depth_item",
            "Depth",
            "required_depth_item",
            "required_pile_depth",
            "required_pile_depth_item",
            "Required depth",
            "Required pile depth",
        ),
        "pile_tip_level_m_nap": get_data_value(data, "tip_item", "Pile tip level"),
        "design_capacity_kN": get_data_value(data, "rc_d", "Rc;d (design value)"),
        "design_load_kN": get_data_value(data, "fc_d", "Fc;d (applied design load)"),
        "utilization": get_data_value(data, "util", "Utilisation Fc;d / Rc;d"),
    }


def _optional_number(data: Any, *keys: str) -> float | None:
    value = get_data_value(data, *keys)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def required_pile_length_from_cpt_data(data: Any) -> float | None:
    direct_length = _optional_number(
        data,
        "length_item",
        "Pile length",
        "required_length",
        "required_length_item",
        "required_pile_length",
        "required_pile_length_item",
        "Required pile length",
        "depth_item",
        "Depth",
        "required_depth",
        "required_depth_item",
        "required_pile_depth",
        "required_pile_depth_item",
        "Required depth",
        "Required pile depth",
        "Required Pile Depth",
    )
    if direct_length is not None:
        return direct_length

    ground_level = _optional_number(data, "ground_item", "Ground level", "Ground level (from CPT)")
    tip_level = _optional_number(
        data,
        "tip_item",
        "Pile tip level",
        "required_tip_level",
        "Required pile tip level",
        "Required tip level",
    )
    if ground_level is not None and tip_level is not None:
        return abs(ground_level - tip_level)

    return None


def required_pile_length_or_error(cpt_data: Any) -> float:
    required_length = required_pile_length_from_cpt_data(cpt_data)
    if required_length is None:
        raise ValueError(
            "CPT required-depth output did not include a required pile length or tip level."
        )
    return required_length


async def run_cpt_pile_bearing_func(context: Any, args: str) -> str:
    try:
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        target = resolve_workflow_entity("cpt_pile_bearing")
        saved_params = read_last_saved_params(target)
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_cpt_pile_bearing",
            node_id="cpt_pile_bearing",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_cpt_pile_bearing",
            message="Invalid CPT pile bearing arguments.",
            error=exc,
            retry_tool="run_cpt_pile_bearing",
            retry_reason="Retry with step1 location/search inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_cpt_pile_bearing",
            message="Could not read the workflow CPT entity.",
            error=exc,
        )

    try:
        foundation_data = read_json_from_storage(FOUNDATION_STORAGE_KEY)
        foundation_params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)

        piles = foundation_params["step_geo"]["sec_piles"]
        pile_diameter = int(round(float(piles["pile_diameter"])))
        max_pile_reaction = get_number(foundation_data, "Maximum pile reaction (Rz)")
    except FileNotFoundError as exc:
        missing_storage_key = str(exc).split("'")[1] if "'" in str(exc) else FOUNDATION_STORAGE_KEY
        return needs_prerequisite_response(
            tool="run_cpt_pile_bearing",
            message="Missing foundation analysis output needed by CPT required-depth sizing.",
            missing_storage_key=missing_storage_key,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason=(
                "Run foundation analysis first so max pile reaction and pile diameter "
                "can be passed into the CPT app."
            ),
        )
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as exc:
        return validation_error_response(
            tool="run_cpt_pile_bearing",
            message="Stored foundation output or params are invalid for CPT sizing.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Regenerate foundation results before CPT required-depth sizing.",
        )

    try:
        compute_payload = deep_merge_params(saved_params, explicit_args)
        compute_payload = deep_merge_params(
            compute_payload,
            {
                "step2": {
                    "sec_pile": {"pile_diameter": pile_diameter},
                    "sec_load": {"design_load": max_pile_reaction},
                }
            },
        )
        payload = CptPileBearingParams.model_validate(compute_payload or {})
        compute_payload = deep_merge_params(payload.model_dump(), compute_payload)
        set_last_saved_params(
            target,
            deep_merge_params(saved_params, compute_payload),
            message=(
                "Agent updated CPT pile bearing params from foundation reaction "
                "and pile diameter."
            ),
        )
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_cpt_pile_bearing",
            message="Invalid CPT pile bearing arguments.",
            error=exc,
            retry_tool="run_cpt_pile_bearing",
            retry_reason="Retry with step1 location/search inputs and step2 pile/load inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_cpt_pile_bearing",
            message="Could not read or update the workflow CPT entity.",
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
        data = select_and_store_result(
            result=result,
            result_key=target.result_key,
            storage_key=target.storage_key,
        )
        required_length = required_pile_length_or_error(data)
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_cpt_pile_bearing",
            message=(
                "The CPT pile bearing app returned an unexpected required-depth "
                "result shape."
            ),
            error=exc,
            retry_tool="run_cpt_pile_bearing",
            retry_reason=(
                "Retry with valid CPT location, foundation pile diameter, and max "
                "pile reaction inputs."
            ),
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_cpt_pile_bearing",
            message="CPT pile bearing SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message=(
            "Computed CPT required pile depth. Patch the foundation pile length with "
            "set_params_in_node before reinforcement or cost analysis."
        ),
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        storage_key=target.storage_key,
        next_param_update={
            "tool": "set_params_in_node",
            "node_id": "foundation_analysis",
            "merge": True,
            "params": {
                "step_geo": {
                    "sec_piles": {
                        "pile_length": required_length,
                        "pile_diameter": payload.step2.sec_pile.pile_diameter,
                    }
                }
            },
        },
        required_pile_length_m=required_length,
        design_load_kN=payload.step2.sec_load.design_load,
        pile_diameter_mm=payload.step2.sec_pile.pile_diameter,
        summary=summarize_cpt_data(data),
    )
