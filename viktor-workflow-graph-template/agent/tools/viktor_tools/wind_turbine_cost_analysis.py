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
    COST_STORAGE_KEY,
    FOUNDATION_PARAMS_STORAGE_KEY,
    REINFORCEMENT_STORAGE_KEY,
    get_data_value,
    get_number,
    read_json_from_storage,
    rounded_positive_int,
    select_and_store_result,
)


COST_WORKSPACE_ID = 2647
COST_ENTITY_ID = 12169
COST_METHOD_NAME = "view_data"
COST_RESULT_KEY = "data"


class CostConcreteInputs(BaseModel):
    cost_concrete: int = Field(default=150, description="Concrete unit cost.")


class CostRebarInputs(BaseModel):
    cost_rebar: int = Field(default=900, description="Rebar unit cost.")
    multiplication_factor: float = Field(
        default=2.0,
        description="Multiplier for top/bottom or secondary plate reinforcement.",
    )


class CostPileInputs(BaseModel):
    ref_diameter: int = Field(default=500, description="Reference pile diameter in mm.")
    cost_pile_install: int = Field(default=80, description="Pile installation unit cost.")
    cost_pile_material: int = Field(default=120, description="Pile material unit cost.")


class WindTurbineCostAnalysisParams(BaseModel):
    concrete: CostConcreteInputs = Field(default_factory=CostConcreteInputs)
    rebar: CostRebarInputs = Field(default_factory=CostRebarInputs)
    piles: CostPileInputs = Field(default_factory=CostPileInputs)


class CostMastInputs(BaseModel):
    d_mast: int = Field(default=5)


class CostPlateInputs(BaseModel):
    d_plate: int = Field(default=20)
    t_centre: int = Field(default=3)
    t_edge: int = Field(default=1)
    h_pedestal: float = Field(default=1.0)


class CostRebarGeometryInputs(BaseModel):
    plate_main_reinforcement: int = Field(default=60)
    multiplication_factor: float = Field(default=2.0)


class CostPilesGeometryInputs(BaseModel):
    n_piles: int = Field(default=30)
    pile_length: int = Field(default=20)
    pile_diameter: int = Field(default=500)


class CostStep1(BaseModel):
    mast: CostMastInputs
    plate: CostPlateInputs
    rebar: CostRebarGeometryInputs
    piles: CostPilesGeometryInputs


class CostStep2Concrete(BaseModel):
    cost_concrete: int = Field(default=150)


class CostStep2RebarCost(BaseModel):
    cost_rebar: int = Field(default=900)


class CostStep2PileCosts(BaseModel):
    ref_diameter: int = Field(default=500)
    cost_pile_install: int = Field(default=80)
    cost_pile_material: int = Field(default=120)


class CostStep2(BaseModel):
    concrete: CostStep2Concrete
    rebar_cost: CostStep2RebarCost
    pile_costs: CostStep2PileCosts


class CostComputeParams(BaseModel):
    step_1: CostStep1
    step_2: CostStep2


def summarize_cost_data(data: Any) -> dict[str, Any]:
    return {
        "plate_volume_m3": get_data_value(data, "vol_plate", "Total volume plate"),
        "pedestal_volume_m3": get_data_value(data, "vol_pedestal", "Pedestal volume"),
        "rebar_mass_kg": get_data_value(data, "rebar_mass", "Rebar mass (plate)"),
        "plate_total_reinforcement_kg": get_data_value(
            data,
            "plate_total_reinforcement",
            "Plate total reinforcement",
        ),
        "total_pile_length_m": get_data_value(data, "total_pile_length", "Total pile length"),
    }


async def run_wind_turbine_cost_analysis_func(context: Any, args: str) -> str:
    try:
        payload = WindTurbineCostAnalysisParams.model_validate_json(args or "{}")
    except ValidationError as exc:
        return validation_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="Invalid cost analysis arguments.",
            error=exc,
            retry_tool="run_wind_turbine_cost_analysis",
            retry_reason="Retry with concrete, rebar, and piles cost inputs.",
        )

    try:
        foundation_params = read_json_from_storage(FOUNDATION_PARAMS_STORAGE_KEY)
    except FileNotFoundError:
        return needs_prerequisite_response(
            tool="run_wind_turbine_cost_analysis",
            message="Missing foundation geometry params in VIKTOR Storage.",
            missing_storage_key=FOUNDATION_PARAMS_STORAGE_KEY,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Foundation analysis stores geometry needed by cost analysis.",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="Stored foundation params are invalid.",
            error=exc,
            retry_tool="run_wind_turbine_foundation_analysis",
            retry_reason="Regenerate foundation params.",
        )

    try:
        reinforcement_data = read_json_from_storage(REINFORCEMENT_STORAGE_KEY)
    except FileNotFoundError:
        return needs_prerequisite_response(
            tool="run_wind_turbine_cost_analysis",
            message="Missing reinforcement data in VIKTOR Storage.",
            missing_storage_key=REINFORCEMENT_STORAGE_KEY,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Reinforcement data provides the plate reinforcement quantity for cost.",
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="Stored reinforcement data is invalid.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Regenerate reinforcement results.",
        )

    try:
        step_geo = foundation_params["step_geo"]
        mast = step_geo["sec_mast"]
        plate = step_geo["sec_plate"]
        piles = step_geo["sec_piles"]
        steel_mass = get_number(reinforcement_data, "kg_m3", "Steel mass per m3", default=60.0)

        compute_params = CostComputeParams(
            step_1=CostStep1(
                mast=CostMastInputs(
                    d_mast=rounded_positive_int(mast["mast_diameter"], default=5),
                ),
                plate=CostPlateInputs(
                    d_plate=rounded_positive_int(plate["slab_diameter"], default=20),
                    t_centre=rounded_positive_int(plate["slab_thickness"], default=3),
                    t_edge=rounded_positive_int(plate["plate_edge_thickness"], default=1),
                    h_pedestal=float(plate["pedestal_height"]),
                ),
                rebar=CostRebarGeometryInputs(
                    plate_main_reinforcement=rounded_positive_int(steel_mass, default=60),
                    multiplication_factor=payload.rebar.multiplication_factor,
                ),
                piles=CostPilesGeometryInputs(
                    n_piles=rounded_positive_int(piles["num_piles"], default=30),
                    pile_length=rounded_positive_int(piles["pile_length"], default=20),
                    pile_diameter=rounded_positive_int(piles["pile_diameter"], default=500),
                ),
            ),
            step_2=CostStep2(
                concrete=CostStep2Concrete(cost_concrete=payload.concrete.cost_concrete),
                rebar_cost=CostStep2RebarCost(cost_rebar=payload.rebar.cost_rebar),
                pile_costs=CostStep2PileCosts(
                    ref_diameter=payload.piles.ref_diameter,
                    cost_pile_install=payload.piles.cost_pile_install,
                    cost_pile_material=payload.piles.cost_pile_material,
                ),
            ),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="Could not map foundation/reinforcement output into cost inputs.",
            error=exc,
            retry_tool="run_wind_turbine_reinforcement",
            retry_reason="Regenerate foundation and reinforcement outputs.",
        )

    try:
        client = ViktorSdkComputeClient()
        result = client.compute_method(
            workspace_id=COST_WORKSPACE_ID,
            entity_id=COST_ENTITY_ID,
            method_name=COST_METHOD_NAME,
            params=compute_params.model_dump(),
        )
        data = select_and_store_result(
            result=result,
            result_key=COST_RESULT_KEY,
            storage_key=COST_STORAGE_KEY,
        )
    except (KeyError, ValueError) as exc:
        return validation_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="The cost analysis app returned an unexpected result shape.",
            error=exc,
            retry_tool="run_wind_turbine_cost_analysis",
            retry_reason="Retry after checking foundation, reinforcement, and unit cost inputs.",
        )
    except Exception as exc:
        return execution_error_response(
            tool="run_wind_turbine_cost_analysis",
            message="Cost analysis SDK compute or storage write failed.",
            error=exc,
        )

    return tool_response(
        "completed",
        message="Computed wind turbine foundation quantities/cost inputs and stored cost data.",
        method_name=COST_METHOD_NAME,
        result_key=COST_RESULT_KEY,
        input_storage_keys=[FOUNDATION_PARAMS_STORAGE_KEY, REINFORCEMENT_STORAGE_KEY],
        storage_key=COST_STORAGE_KEY,
        summary=summarize_cost_data(data),
    )
