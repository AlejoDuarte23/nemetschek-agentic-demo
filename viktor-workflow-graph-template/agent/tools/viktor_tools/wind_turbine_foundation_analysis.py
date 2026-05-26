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
    WIND_TURBINE_SELECTOR_STORAGE_KEY,
    get_data_value,
    get_number,
    read_json_from_storage,
    select_and_store_result,
    write_json_to_storage,
)
from agent.tools.viktor_tools.workflow_entities import (
    WorkflowRunEntity,
    deep_merge_params,
    needs_workflow_run_response,
    read_last_saved_params,
    resolve_workflow_entity,
    set_last_saved_params,
)


class FoundationPlateInputs(BaseModel):
    slab_diameter: float = Field(default=20.0, description="Circular plate diameter in m.")
    slab_thickness: float = Field(default=3.0, description="Plate thickness at centre in m.")
    plate_edge_thickness: float = Field(default=1.0, description="Plate thickness at edge in m.")
    pedestal_height: float = Field(default=1.0, description="Pedestal height in m.")


class FoundationPileLayoutInputs(BaseModel):
    num_piles: int = Field(default=30, ge=6, description="Number of piles in the circular layout.")
    pile_length: float = Field(
        default=20.0,
        description="Initial pile length in m used for the first SCIA analysis.",
    )
    pile_diameter: int = Field(
        default=500,
        description="Pile diameter or width in mm.",
    )
    pile_edge_distance: int = Field(
        default=600,
        description="Horizontal distance from plate edge to pile centre in mm.",
    )


class FoundationGeotechnicalInputs(BaseModel):
    tip_stiffness: float = Field(
        default=50000.0,
        description="Axial spring stiffness at pile tip in kN/m.",
    )
    lateral_stiffness: float = Field(
        default=10000.0,
        description="Horizontal spring stiffness per unit length in kN/m/m.",
    )


class WindTurbineFoundationAnalysisParams(BaseModel):
    plate: FoundationPlateInputs = Field(default_factory=FoundationPlateInputs)
    pile_layout: FoundationPileLayoutInputs = Field(default_factory=FoundationPileLayoutInputs)
    geotechnical: FoundationGeotechnicalInputs = Field(
        default_factory=FoundationGeotechnicalInputs
    )


class FoundationSecMast(BaseModel):
    mast_diameter: float = Field(default=5.0)
    mast_vertical_load: float = Field(default=4000.0)
    mast_horizontal_load: float = Field(default=1500.0)
    mast_moment: float = Field(default=150000.0)


class FoundationSecPlate(BaseModel):
    slab_diameter: float = Field(default=20.0)
    slab_thickness: float = Field(default=3.0)
    plate_edge_thickness: float = Field(default=1.0)
    pedestal_height: float = Field(default=1.0)


class FoundationSecPiles(BaseModel):
    num_piles: int = Field(default=30)
    pile_length: float = Field(default=20.0)
    pile_diameter: int = Field(default=500)
    pile_edge_distance: int = Field(default=600)


class FoundationStepGeo(BaseModel):
    sec_mast: FoundationSecMast = Field(default_factory=FoundationSecMast)
    sec_plate: FoundationSecPlate = Field(default_factory=FoundationSecPlate)
    sec_piles: FoundationSecPiles = Field(default_factory=FoundationSecPiles)


class FoundationSecTip(BaseModel):
    tip_stiffness: float = Field(default=50000.0)


class FoundationSecLateral(BaseModel):
    lateral_stiffness: float = Field(default=10000.0)


class FoundationStepGeoTech(BaseModel):
    sec_tip: FoundationSecTip = Field(default_factory=FoundationSecTip)
    sec_lateral: FoundationSecLateral = Field(default_factory=FoundationSecLateral)


class FoundationComputeParams(BaseModel):
    step_geo: FoundationStepGeo = Field(default_factory=FoundationStepGeo)
    step_geo_tech: FoundationStepGeoTech = Field(default_factory=FoundationStepGeoTech)


def summarize_foundation_data(data: Any) -> dict[str, Any]:
    return {
        "max_pile_reaction_kN": get_data_value(data, "Maximum pile reaction (Rz)"),
        "min_pile_reaction_kN": get_data_value(data, "Minimum pile reaction (Rz)"),
        "min_m_xd_plus_kNm_per_m": get_data_value(data, "Minimum m_xD+"),
        "max_m_xd_minus_kNm_per_m": get_data_value(data, "Maximum m_xD-"),
        "min_m_yd_plus_kNm_per_m": get_data_value(data, "Minimum m_yD+"),
        "max_m_yd_minus_kNm_per_m": get_data_value(data, "Maximum m_yD-"),
    }


def foundation_payload_from_saved_params(
    saved_params: dict[str, Any],
) -> WindTurbineFoundationAnalysisParams:
    geo = saved_params.get("step_geo", {}) if isinstance(saved_params, dict) else {}
    geo_tech = saved_params.get("step_geo_tech", {}) if isinstance(saved_params, dict) else {}
    sec_plate = geo.get("sec_plate", {}) if isinstance(geo, dict) else {}
    sec_piles = geo.get("sec_piles", {}) if isinstance(geo, dict) else {}
    sec_tip = geo_tech.get("sec_tip", {}) if isinstance(geo_tech, dict) else {}
    sec_lateral = geo_tech.get("sec_lateral", {}) if isinstance(geo_tech, dict) else {}

    default_payload = WindTurbineFoundationAnalysisParams().model_dump()
    saved_payload = {
        "plate": {
            "slab_diameter": sec_plate.get("slab_diameter"),
            "slab_thickness": sec_plate.get("slab_thickness"),
            "plate_edge_thickness": sec_plate.get("plate_edge_thickness"),
            "pedestal_height": sec_plate.get("pedestal_height"),
        },
        "pile_layout": {
            "num_piles": sec_piles.get("num_piles"),
            "pile_length": sec_piles.get("pile_length"),
            "pile_diameter": sec_piles.get("pile_diameter"),
            "pile_edge_distance": sec_piles.get("pile_edge_distance"),
        },
        "geotechnical": {
            "tip_stiffness": sec_tip.get("tip_stiffness"),
            "lateral_stiffness": sec_lateral.get("lateral_stiffness"),
        },
    }

    def drop_none(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: drop_none(v) for k, v in value.items() if v is not None}
        return value

    merged = deep_merge_params(default_payload, drop_none(saved_payload))
    return WindTurbineFoundationAnalysisParams.model_validate(merged)


def build_foundation_compute_params(
    *,
    payload: WindTurbineFoundationAnalysisParams,
    selector_data: Any,
) -> FoundationComputeParams:
    return FoundationComputeParams(
        step_geo=FoundationStepGeo(
            sec_mast=FoundationSecMast(
                mast_diameter=get_number(
                    selector_data,
                    "base_diameter",
                    "Base diameter",
                    default=5.0,
                ),
                mast_vertical_load=get_number(
                    selector_data,
                    "base_vert_force",
                    "Max. vertical force at base",
                    default=4000.0,
                ),
                mast_horizontal_load=get_number(
                    selector_data,
                    "base_horiz_force",
                    "Max. horizontal force at base",
                    default=1500.0,
                ),
                mast_moment=get_number(
                    selector_data,
                    "base_moment",
                    "Max. moment at base",
                    default=150000.0,
                ),
            ),
            sec_plate=FoundationSecPlate(
                slab_diameter=payload.plate.slab_diameter,
                slab_thickness=payload.plate.slab_thickness,
                plate_edge_thickness=payload.plate.plate_edge_thickness,
                pedestal_height=payload.plate.pedestal_height,
            ),
            sec_piles=FoundationSecPiles(
                num_piles=payload.pile_layout.num_piles,
                pile_length=payload.pile_layout.pile_length,
                pile_diameter=payload.pile_layout.pile_diameter,
                pile_edge_distance=payload.pile_layout.pile_edge_distance,
            ),
        ),
        step_geo_tech=FoundationStepGeoTech(
            sec_tip=FoundationSecTip(tip_stiffness=payload.geotechnical.tip_stiffness),
            sec_lateral=FoundationSecLateral(
                lateral_stiffness=payload.geotechnical.lateral_stiffness
            ),
        ),
    )


def foundation_scia_template_response(error: Exception, target: WorkflowRunEntity) -> str:
    return tool_response(
        "needs_scia_template",
        tool="run_wind_turbine_foundation_analysis",
        message=(
            "Foundation SCIA result views require a valid SCIA .esa template. The "
            "sample foundation app now reads sample_apps/scia/base_model.esa from "
            "disk. The computed foundation input params were stored for downstream "
            "geometry/cost use."
        ),
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        required_action=(
            "Deploy the updated SCIA sample app with sample_apps/scia/base_model.esa "
            "included. The template must contain materials C30/37 and concrete_plate "
            "plus an I/O document named output with a Reactions table for Combinations."
        ),
        saved_input_storage_key=FOUNDATION_PARAMS_STORAGE_KEY,
        error_type=type(error).__name__,
        details=str(error),
    )


async def run_wind_turbine_foundation_analysis_func(context: Any, args: str) -> str:
    try:
        explicit_args = json.loads(args) if args and args.strip() else {}
        if not isinstance(explicit_args, dict):
            raise ValueError("Tool arguments must be a JSON object.")
        target = resolve_workflow_entity("foundation_analysis")
        saved_params = read_last_saved_params(target)
        base_payload = foundation_payload_from_saved_params(saved_params)
        payload = WindTurbineFoundationAnalysisParams.model_validate(
            deep_merge_params(base_payload.model_dump(), explicit_args)
        )
    except (FileNotFoundError, KeyError):
        return needs_workflow_run_response(
            tool="run_wind_turbine_foundation_analysis",
            node_id="foundation_analysis",
        )
    except (json.JSONDecodeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_foundation_analysis",
            message="Invalid foundation analysis arguments.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason=(
                "Retry with plate, pile_layout, and geotechnical inputs matching the "
                "foundation app parametrization."
            ),
        )

    try:
        selector_data = read_json_from_storage(WIND_TURBINE_SELECTOR_STORAGE_KEY)
    except FileNotFoundError:
        return needs_prerequisite_response(
            tool="run_wind_turbine_foundation_analysis",
            message="Missing turbine selector data in VIKTOR Storage.",
            missing_storage_key=WIND_TURBINE_SELECTOR_STORAGE_KEY,
            retry_tool="run_wind_turbine_selector",
            retry_reason=(
                "run_wind_turbine_selector stores mast diameter and base loads needed "
                "by the foundation app."
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_foundation_analysis",
            message="Stored turbine selector data is invalid.",
            error=exc,
            retry_tool="run_wind_turbine_selector",
            retry_reason="Regenerate turbine selector data.",
        )

    try:
        compute_params = build_foundation_compute_params(
            payload=payload,
            selector_data=selector_data,
        )
    except (ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_foundation_analysis",
            message="Could not map turbine data into foundation inputs.",
            error=exc,
            retry_tool="run_wind_turbine_selector",
            retry_reason="Regenerate upstream turbine results, then retry foundation.",
        )

    compute_payload = compute_params.model_dump()
    write_json_to_storage(FOUNDATION_PARAMS_STORAGE_KEY, compute_payload)

    try:
        set_last_saved_params(
            target,
            deep_merge_params(saved_params, compute_payload),
            message="Agent patched foundation params with turbine loads and current pile geometry.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_foundation_analysis",
            message="Could not update the workflow foundation entity params.",
            error=exc,
        )

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=target.workspace_id,
            entity_id=target.entity_id,
            method_name=target.method_name,
            params=compute_payload,
            timeout=300,
        )
        data = select_and_store_result(
            result=result,
            result_key=target.result_key,
            storage_key=target.storage_key,
        )
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_foundation_analysis",
            message="The foundation app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Retry after checking the SCIA template and foundation inputs.",
        )
    except Exception as exc:
        error_text = str(exc)
        if "Missing VIKTOR token" in error_text or "VIKTOR_ENVIRONMENT" in error_text:
            return execution_error_response(
                tool="run_wind_turbine_foundation_analysis",
                message="Foundation SDK compute could not start because configuration is missing.",
                error=exc,
            )
        return foundation_scia_template_response(exc, target)

    return tool_response(
        "completed",
        message=(
            "Computed foundation SCIA summary and stored pile reactions/moment extremes "
            "for CPT required-depth sizing and reinforcement."
        ),
        entity_id=target.entity_id,
        entity_url=target.url,
        method_name=target.method_name,
        result_key=target.result_key,
        input_storage_keys=[WIND_TURBINE_SELECTOR_STORAGE_KEY],
        params_storage_key=FOUNDATION_PARAMS_STORAGE_KEY,
        storage_key=target.storage_key,
        summary=summarize_foundation_data(data),
    )
