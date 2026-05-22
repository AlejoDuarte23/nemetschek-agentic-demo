from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class CptPileBearingParamsStep1Location(BaseModel):
    lat: float = Field(default=51.9694)
    lon: float = Field(default=5.0965)


class CptPileBearingParamsStep1(BaseModel):
    location: CptPileBearingParamsStep1Location = Field(default_factory=CptPileBearingParamsStep1Location)
    search_radius: float = Field(default=1.0)
    min_cpt_depth: float = Field(default=20.0)


class CptPileBearingParamsStep2SecPile(BaseModel):
    pile_tip_level: float = Field(default=-17.0)
    pile_diameter: int = Field(default=400)
    pile_shape: str = Field(default='Round')
    pile_type: str = Field(default='Bored pile')


class CptPileBearingParamsStep2SecLoad(BaseModel):
    design_load: float = Field(default=1100.0)


class CptPileBearingParamsStep2(BaseModel):
    sec_pile: CptPileBearingParamsStep2SecPile = Field(default_factory=CptPileBearingParamsStep2SecPile)
    sec_load: CptPileBearingParamsStep2SecLoad = Field(default_factory=CptPileBearingParamsStep2SecLoad)


class CptPileBearingParams(BaseModel):
    step1: CptPileBearingParamsStep1 = Field(default_factory=CptPileBearingParamsStep1)
    step2: CptPileBearingParamsStep2 = Field(default_factory=CptPileBearingParamsStep2)
