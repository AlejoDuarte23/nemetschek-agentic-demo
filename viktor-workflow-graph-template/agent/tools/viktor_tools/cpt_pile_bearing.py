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
        "pile_length_m": get_data_value(data, "length_item", "Pile length"),
        "pile_tip_level_m_nap": get_data_value(data, "tip_item", "Pile tip level"),
        "design_capacity_kN": get_data_value(data, "rc_d", "Rc;d (design value)"),
        "design_load_kN": get_data_value(data, "fc_d", "Fc;d (applied design load)"),
        "utilization": get_data_value(data, "util", "Utilisation Fc;d / Rc;d"),
    }


async def run_cpt_pile_bearing_func(context: Any, args: str) -> str:
    try:
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        target = resolve_workflow_entity("cpt_pile_bearing")
        saved_params = read_last_saved_params(target)
        compute_payload = deep_merge_params(saved_params, explicit_args)
        payload = CptPileBearingParams.model_validate(compute_payload or {})
        compute_payload = deep_merge_params(payload.model_dump(), compute_payload)
        set_last_saved_params(
            target,
            compute_payload,
            message="Agent updated CPT pile bearing params for workflow run.",
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_cpt_pile_bearing",
            node_id="cpt_pile_bearing",
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
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_cpt_pile_bearing",
            message="The CPT pile bearing app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_cpt_pile_bearing",
            retry_reason="Retry with valid CPT location, pile, and design load inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_cpt_pile_bearing",
            message="CPT pile bearing SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Computed pile bearing capacity and stored pile geometry for foundation analysis.",
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        storage_key=target.storage_key,
        summary=summarize_cpt_data(data),
    )
