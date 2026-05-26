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
    CPT_PILE_BEARING_STORAGE_KEY,
    FOUNDATION_PARAMS_STORAGE_KEY,
    FOUNDATION_STORAGE_KEY,
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


class ReinforcementDetailingInputs(BaseModel):
    design_strip_width: int = Field(
        default=1000,
        description="Representative design strip width in mm for plate moments in kNm/m.",
    )
    cover: int = Field(default=50, description="Concrete cover in mm.")
    stirrup_dia: int = Field(default=10, description="Stirrup diameter in mm.")
    spacing_bottom: int = Field(default=200, description="Bottom reinforcement spacing in mm.")
    dia_bottom: int = Field(default=25, description="Bottom reinforcement bar diameter in mm.")
    spacing_top: int = Field(default=200, description="Top reinforcement spacing in mm.")
    dia_top: int = Field(default=16, description="Top reinforcement bar diameter in mm.")


class ReinforcementMaterialInputs(BaseModel):
    concrete_class: str = Field(default="C25/30")
    steel_grade: str = Field(default="B500")


class ReinforcementOptimiseInputs(BaseModel):
    spacing_min: int = Field(default=50, description="Minimum reinforcement spacing in mm.")


class WindTurbineReinforcementParams(BaseModel):
    detailing: ReinforcementDetailingInputs = Field(default_factory=ReinforcementDetailingInputs)
    materials: ReinforcementMaterialInputs = Field(default_factory=ReinforcementMaterialInputs)
    optimise: ReinforcementOptimiseInputs = Field(default_factory=ReinforcementOptimiseInputs)


class ReinforcementCombination(BaseModel):
    label: str
    M_Ed: float
    N_Ed: float = 0.0


class ReinforcementTabGeometry(BaseModel):
    width: int = Field(default=1000)
    height: int = Field(default=3000)
    cover: int = Field(default=50)
    stirrup_dia: int = Field(default=10)
    spacing_bottom: int = Field(default=200)
    dia_bottom: int = Field(default=25)
    spacing_top: int = Field(default=200)
    dia_top: int = Field(default=16)


class ReinforcementTabLoading(BaseModel):
    concrete_class: str = Field(default="C25/30")
    steel_grade: str = Field(default="B500")
    combinations: list[ReinforcementCombination]


class ReinforcementTabOptimise(BaseModel):
    spacing_min: int = Field(default=50)


class ReinforcementComputeParams(BaseModel):
    tab_geometry: ReinforcementTabGeometry
    tab_loading: ReinforcementTabLoading
    tab_optimise: ReinforcementTabOptimise


def summarize_reinforcement_data(data: Any) -> dict[str, Any]:
    return {
        "width_mm": get_data_value(data, "width", "Width b"),
        "height_mm": get_data_value(data, "height", "Height h"),
        "bottom_steel_mm2": get_data_value(data, "A_s", "Bottom steel A_s"),
        "top_steel_mm2": get_data_value(data, "A_s2", "Top steel A_s2"),
        "steel_mass_kg_m3": get_data_value(data, "kg_m3", "Steel mass per m3"),
        "unity_check_1": get_data_value(data, "UC_item", "Unity check M_Ed / M_Rd"),
    }


def reinforcement_payload_from_saved_params(
    saved_params: dict[str, Any],
) -> WindTurbineReinforcementParams:
    geometry = saved_params.get("tab_geometry", {}) if isinstance(saved_params, dict) else {}
    loading = saved_params.get("tab_loading", {}) if isinstance(saved_params, dict) else {}
    optimise = saved_params.get("tab_optimise", {}) if isinstance(saved_params, dict) else {}

    default_payload = WindTurbineReinforcementParams().model_dump()
    saved_payload = {
        "detailing": {
            "design_strip_width": geometry.get("width"),
            "cover": geometry.get("cover"),
            "stirrup_dia": geometry.get("stirrup_dia"),
            "spacing_bottom": geometry.get("spacing_bottom"),
            "dia_bottom": geometry.get("dia_bottom"),
            "spacing_top": geometry.get("spacing_top"),
            "dia_top": geometry.get("dia_top"),
        },
        "materials": {
            "concrete_class": loading.get("concrete_class"),
            "steel_grade": loading.get("steel_grade"),
        },
        "optimise": {
            "spacing_min": optimise.get("spacing_min"),
        },
    }

    def drop_none(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: drop_none(v) for k, v in value.items() if v is not None}
        return value

    return WindTurbineReinforcementParams.model_validate(
        deep_merge_params(default_payload, drop_none(saved_payload))
    )


def governing_foundation_combinations(data: Any) -> list[ReinforcementCombination]:
    moment_fields = [
        ("Min m_xD+", get_data_value(data, "Minimum m_xD+")),
        ("Max m_xD-", get_data_value(data, "Maximum m_xD-")),
    ]
    combinations: list[ReinforcementCombination] = []
    for label, value in moment_fields:
        try:
            moment = float(value)
        except (TypeError, ValueError):
            continue
        combinations.append(ReinforcementCombination(label=label, M_Ed=moment, N_Ed=0.0))

    if not combinations:
        raise ValueError(
            "Foundation data does not contain usable m_xD+ or m_xD- moment extremes."
        )
    if len(combinations) < len(moment_fields):
        raise ValueError("Foundation data is missing one of the required m_xD load combinations.")
    return combinations


async def run_wind_turbine_reinforcement_func(context: Any, args: str) -> str:
    try:
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        target = resolve_workflow_entity("reinforcement")
        saved_params = read_last_saved_params(target)
        base_payload = reinforcement_payload_from_saved_params(saved_params)
        payload = WindTurbineReinforcementParams.model_validate(
            deep_merge_params(base_payload.model_dump(), explicit_args)
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_wind_turbine_reinforcement",
            node_id="reinforcement",
        )
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Invalid reinforcement arguments.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Retry with detailing, materials, and optimise fields.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Could not read the workflow reinforcement entity.",
            error=exc,
        )

    try:
        foundation_params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)
        foundation_data = read_json_from_storage(FOUNDATION_STORAGE_KEY)
        read_json_from_storage(CPT_PILE_BEARING_STORAGE_KEY)
    except FileNotFoundError as exc:
        missing_key = str(exc).split("'")[1] if "'" in str(exc) else FOUNDATION_STORAGE_KEY
        retry_tool = (
            "run_cpt_pile_bearing"
            if missing_key == CPT_PILE_BEARING_STORAGE_KEY
            else "run_wind_turbine_foundation_analysis"
        )
        retry_reason = (
            "run_cpt_pile_bearing patches the final required pile length before reinforcement."
            if missing_key == CPT_PILE_BEARING_STORAGE_KEY
            else (
                "run_wind_turbine_foundation_analysis stores plate geometry and "
                "governing moments needed by reinforcement."
            )
        )
        return needs_prerequisite_response(
            tool="run_wind_turbine_reinforcement",
            message="Missing upstream workflow output in VIKTOR Storage.",
            missing_storage_key=missing_key,
            retry_tool=retry_tool,
            retry_reason=retry_reason,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Stored foundation or CPT output is invalid.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Regenerate foundation results and CPT required-depth sizing.",
        )

    try:
        plate = foundation_params["step_geo"]["sec_plate"]
        combinations = governing_foundation_combinations(foundation_data)
        compute_params = ReinforcementComputeParams(
            tab_geometry=ReinforcementTabGeometry(
                width=payload.detailing.design_strip_width,
                height=rounded_positive_int(plate["slab_thickness"] * 1000.0, default=3000),
                cover=payload.detailing.cover,
                stirrup_dia=payload.detailing.stirrup_dia,
                spacing_bottom=payload.detailing.spacing_bottom,
                dia_bottom=payload.detailing.dia_bottom,
                spacing_top=payload.detailing.spacing_top,
                dia_top=payload.detailing.dia_top,
            ),
            tab_loading=ReinforcementTabLoading(
                concrete_class=payload.materials.concrete_class,
                steel_grade=payload.materials.steel_grade,
                combinations=combinations,
            ),
            tab_optimise=ReinforcementTabOptimise(
                spacing_min=payload.optimise.spacing_min,
            ),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Could not map foundation output into reinforcement inputs.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Regenerate a successful foundation Results Summary first.",
        )

    compute_payload = compute_params.model_dump(by_alias=True)
    try:
        set_last_saved_params(
            target,
            deep_merge_params(saved_params, compute_payload),
            message="Agent patched reinforcement params with foundation workflow inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Could not update the workflow reinforcement entity params.",
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
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="The reinforcement app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Retry after checking foundation moments and reinforcement inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Reinforcement SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Computed reinforcement demand/capacity checks and stored reinforcement data.",
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        input_storage_keys=[
            FOUNDATION_PARAMS_STORAGE_KEY,
            FOUNDATION_STORAGE_KEY,
            CPT_PILE_BEARING_STORAGE_KEY,
        ],
        storage_key=target.storage_key,
        combination_count=len(compute_params.tab_loading.combinations),
        summary=summarize_reinforcement_data(data),
    )
