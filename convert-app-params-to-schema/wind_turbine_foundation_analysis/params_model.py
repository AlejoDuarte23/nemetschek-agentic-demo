from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class WindTurbineFoundationAnalysisParamsStepGeoSecMast(BaseModel):
    mast_diameter: float = Field(default=5.0)
    mast_vertical_load: float = Field(default=4000.0)
    mast_horizontal_load: float = Field(default=1500.0)
    mast_moment: float = Field(default=150000.0)


class WindTurbineFoundationAnalysisParamsStepGeoSecPlate(BaseModel):
    slab_diameter: float = Field(default=20.0)
    slab_thickness: float = Field(default=4.5)
    plate_edge_thickness: float = Field(default=1.0)
    pedestal_height: float = Field(default=1.0)


class WindTurbineFoundationAnalysisParamsStepGeoSecPiles(BaseModel):
    num_piles: int = Field(default=30)
    pile_length: float = Field(default=20.0)
    pile_diameter: int = Field(default=500)
    pile_edge_distance: int = Field(default=600)


class WindTurbineFoundationAnalysisParamsStepGeo(BaseModel):
    sec_mast: WindTurbineFoundationAnalysisParamsStepGeoSecMast = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoSecMast)
    sec_plate: WindTurbineFoundationAnalysisParamsStepGeoSecPlate = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoSecPlate)
    sec_piles: WindTurbineFoundationAnalysisParamsStepGeoSecPiles = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoSecPiles)


class WindTurbineFoundationAnalysisParamsStepGeoTechSecTip(BaseModel):
    tip_stiffness: float = Field(default=50000.0)


class WindTurbineFoundationAnalysisParamsStepGeoTechSecLateral(BaseModel):
    lateral_stiffness: float = Field(default=10000.0)


class WindTurbineFoundationAnalysisParamsStepGeoTech(BaseModel):
    sec_tip: WindTurbineFoundationAnalysisParamsStepGeoTechSecTip = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoTechSecTip)
    sec_lateral: WindTurbineFoundationAnalysisParamsStepGeoTechSecLateral = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoTechSecLateral)


class WindTurbineFoundationAnalysisParams(BaseModel):
    step_geo: WindTurbineFoundationAnalysisParamsStepGeo = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeo)
    step_geo_tech: WindTurbineFoundationAnalysisParamsStepGeoTech = Field(default_factory=WindTurbineFoundationAnalysisParamsStepGeoTech)
