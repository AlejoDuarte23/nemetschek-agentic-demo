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
    REINFORCEMENT_STORAGE_KEY,
    get_data_value,
    read_json_from_storage,
    rounded_positive_int,
    select_and_store_result,
)


REINFORCEMENT_WORKSPACE_ID = 2640
REINFORCEMENT_ENTITY_ID = 12166
REINFORCEMENT_METHOD_NAME = "view_results"
REINFORCEMENT_RESULT_KEY = "data"


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


def governing_foundation_combinations(data: Any) -> list[ReinforcementCombination]:
    moment_fields = [
        ("m_xD+", get_data_value(data, "Minimum m_xD+")),
        ("m_xD-", get_data_value(data, "Maximum m_xD-")),
        ("m_yD+", get_data_value(data, "Minimum m_yD+")),
        ("m_yD-", get_data_value(data, "Maximum m_yD-")),
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
            "Foundation data does not contain usable m_xD/m_yD moment extremes."
        )
    return combinations


async def run_wind_turbine_reinforcement_func(context: Any, args: str) -> str:
    try:
        payload = WindTurbineReinforcementParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Invalid reinforcement arguments.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Retry with detailing, materials, and optimise fields.",
        )

    try:
        foundation_params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)
        foundation_data = read_json_from_storage(FOUNDATION_STORAGE_KEY)
    except FileNotFoundError as exc:
        missing_key = str(exc).split("'")[1] if "'" in str(exc) else FOUNDATION_STORAGE_KEY
        return needs_prerequisite_response(
            tool="run_wind_turbine_reinforcement",
            message="Missing foundation analysis output in VIKTOR Storage.",
            missing_storage_key=missing_key,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason=(
                "run_wind_turbine_foundation_analysis stores plate geometry and "
                "governing moments needed by reinforcement."
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_reinforcement",
            message="Stored foundation output is invalid.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Regenerate foundation results.",
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

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=REINFORCEMENT_WORKSPACE_ID,
            entity_id=REINFORCEMENT_ENTITY_ID,
            method_name=REINFORCEMENT_METHOD_NAME,
            params=compute_params.model_dump(by_alias=True),
        )
        data = select_and_store_result(
            result=result,
            result_key=REINFORCEMENT_RESULT_KEY,
            storage_key=REINFORCEMENT_STORAGE_KEY,
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
        method_name=REINFORCEMENT_METHOD_NAME,
        result_key=REINFORCEMENT_RESULT_KEY,
        input_storage_keys=[FOUNDATION_PARAMS_STORAGE_KEY, FOUNDATION_STORAGE_KEY],
        storage_key=REINFORCEMENT_STORAGE_KEY,
        combination_count=len(compute_params.tab_loading.combinations),
        summary=summarize_reinforcement_data(data),
    )
