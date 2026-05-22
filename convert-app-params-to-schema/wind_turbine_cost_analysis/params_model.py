from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class WindTurbineCostAnalysisParamsStep1Mast(BaseModel):
    d_mast: int = Field(default=5)


class WindTurbineCostAnalysisParamsStep1Plate(BaseModel):
    d_plate: int = Field(default=20)
    t_centre: int = Field(default=3)
    t_edge: int = Field(default=1)
    h_pedestal: float = Field(default=1.0)


class WindTurbineCostAnalysisParamsStep1Rebar(BaseModel):
    plate_main_reinforcement: int = Field(default=60)
    multiplication_factor: float = Field(default=2.0)


class WindTurbineCostAnalysisParamsStep1Piles(BaseModel):
    n_piles: int = Field(default=30)
    pile_length: int = Field(default=20)
    pile_diameter: int = Field(default=500)


class WindTurbineCostAnalysisParamsStep1(BaseModel):
    mast: WindTurbineCostAnalysisParamsStep1Mast = Field(default_factory=WindTurbineCostAnalysisParamsStep1Mast)
    plate: WindTurbineCostAnalysisParamsStep1Plate = Field(default_factory=WindTurbineCostAnalysisParamsStep1Plate)
    rebar: WindTurbineCostAnalysisParamsStep1Rebar = Field(default_factory=WindTurbineCostAnalysisParamsStep1Rebar)
    piles: WindTurbineCostAnalysisParamsStep1Piles = Field(default_factory=WindTurbineCostAnalysisParamsStep1Piles)


class WindTurbineCostAnalysisParamsStep2Concrete(BaseModel):
    cost_concrete: int = Field(default=150)


class WindTurbineCostAnalysisParamsStep2RebarCost(BaseModel):
    cost_rebar: int = Field(default=900)


class WindTurbineCostAnalysisParamsStep2PileCosts(BaseModel):
    ref_diameter: int = Field(default=500)
    cost_pile_install: int = Field(default=80)
    cost_pile_material: int = Field(default=120)


class WindTurbineCostAnalysisParamsStep2(BaseModel):
    concrete: WindTurbineCostAnalysisParamsStep2Concrete = Field(default_factory=WindTurbineCostAnalysisParamsStep2Concrete)
    rebar_cost: WindTurbineCostAnalysisParamsStep2RebarCost = Field(default_factory=WindTurbineCostAnalysisParamsStep2RebarCost)
    pile_costs: WindTurbineCostAnalysisParamsStep2PileCosts = Field(default_factory=WindTurbineCostAnalysisParamsStep2PileCosts)


class WindTurbineCostAnalysisParams(BaseModel):
    step_1: WindTurbineCostAnalysisParamsStep1 = Field(default_factory=WindTurbineCostAnalysisParamsStep1)
    step_2: WindTurbineCostAnalysisParamsStep2 = Field(default_factory=WindTurbineCostAnalysisParamsStep2)
