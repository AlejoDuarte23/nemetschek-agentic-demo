from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.wind_turbine_common import (
    WIND_TURBINE_SELECTOR_STORAGE_KEY,
    get_data_value,
    select_and_store_result,
)


WIND_TURBINE_SELECTOR_WORKSPACE_ID = 2544
WIND_TURBINE_SELECTOR_ENTITY_ID = 12164
WIND_TURBINE_SELECTOR_METHOD_NAME = "view_turbine_data"
WIND_TURBINE_SELECTOR_RESULT_KEY = "data"


class WindTurbineSelectorParams(BaseModel):
    turbine_model: str = Field(
        default="Vestas V150-4.5 MW",
        description="Wind turbine model selected in the turbine selector app.",
    )


def summarize_turbine_data(data: Any) -> dict[str, Any]:
    return {
        "capacity_MW": get_data_value(data, "capacity", "Rated capacity"),
        "hub_height_m": get_data_value(data, "hub_height", "Hub height"),
        "base_diameter_m": get_data_value(data, "base_diameter", "Base diameter"),
        "base_vertical_force_kN": get_data_value(
            data,
            "base_vert_force",
            "Max. vertical force at base",
        ),
        "base_horizontal_force_kN": get_data_value(
            data,
            "base_horiz_force",
            "Max. horizontal force at base",
        ),
        "base_moment_kNm": get_data_value(data, "base_moment", "Max. moment at base"),
    }


async def run_wind_turbine_selector_func(context: Any, args: str) -> str:
    try:
        payload = WindTurbineSelectorParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_wind_turbine_selector",
            message="Invalid wind turbine selector arguments.",
            error=exc,
            retry_tool="run_wind_turbine_selector",
            retry_reason="Retry with turbine_model as a string.",
        )

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=WIND_TURBINE_SELECTOR_WORKSPACE_ID,
            entity_id=WIND_TURBINE_SELECTOR_ENTITY_ID,
            method_name=WIND_TURBINE_SELECTOR_METHOD_NAME,
            params=payload.model_dump(),
        )
        data = select_and_store_result(
            result=result,
            result_key=WIND_TURBINE_SELECTOR_RESULT_KEY,
            storage_key=WIND_TURBINE_SELECTOR_STORAGE_KEY,
        )
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_selector",
            message="The turbine selector app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_wind_turbine_selector",
            retry_reason="Retry with a valid turbine model.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_selector",
            message="Wind turbine selector SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message=(
            f"Selected {payload.turbine_model}. "
            f"Base loads and mast diameter were stored for foundation analysis."
        ),
        method_name=WIND_TURBINE_SELECTOR_METHOD_NAME,
        result_key=WIND_TURBINE_SELECTOR_RESULT_KEY,
        storage_key=WIND_TURBINE_SELECTOR_STORAGE_KEY,
        summary=summarize_turbine_data(data),
    )
