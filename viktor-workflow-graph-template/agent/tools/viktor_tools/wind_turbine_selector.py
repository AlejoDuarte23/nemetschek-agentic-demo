import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agent.tools.viktor_tools.responses import (
    execution_error_response,
    tool_response,
    validation_error_response,
)
from agent.tools.viktor_tools.sdk_compute import ViktorSdkComputeClient
from agent.tools.viktor_tools.wind_turbine_common import (
    get_data_value,
    select_and_store_result,
)
from agent.tools.viktor_tools.workflow_entities import (
    deep_merge_params,
    needs_workflow_run_response,
    read_last_saved_params,
    resolve_workflow_entity,
    set_last_saved_params,
)


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
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        target = resolve_workflow_entity("wind_turbine_selector")
        saved_params = read_last_saved_params(target)
        compute_payload = deep_merge_params(saved_params, explicit_args)
        payload = WindTurbineSelectorParams.model_validate(compute_payload or {})
        compute_payload = deep_merge_params(payload.model_dump(), compute_payload)
        set_last_saved_params(
            target,
            compute_payload,
            message="Agent updated wind turbine selector params for workflow run.",
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_wind_turbine_selector",
            node_id="wind_turbine_selector",
        )
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_selector",
            message="Invalid wind turbine selector arguments.",
            error=exc,
            retry_tool="run_wind_turbine_selector",
            retry_reason="Retry with turbine_model as a string.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_selector",
            message="Could not read or update the workflow selector entity.",
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
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        storage_key=target.storage_key,
        summary=summarize_turbine_data(data),
    )
