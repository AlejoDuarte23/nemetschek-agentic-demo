from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class ReinforcementParamsTabGeometry(BaseModel):
    width: int = Field(default=1000)
    height: int = Field(default=3000)
    cover: int = Field(default=50)
    stirrup_dia: int = Field(default=10)
    spacing_bottom: int = Field(default=200)
    dia_bottom: int = Field(default=25)
    spacing_top: int = Field(default=200)
    dia_top: int = Field(default=16)


class ReinforcementParamsTabLoadingCombinationsItem(BaseModel):
    label: str = Field(...)
    m_ed: float = Field(..., alias='M_Ed')
    n_ed: float = Field(..., alias='N_Ed')


class ReinforcementParamsTabLoading(BaseModel):
    concrete_class: str = Field(default='C25/30')
    steel_grade: str = Field(default='B500')
    combinations: list[ReinforcementParamsTabLoadingCombinationsItem] = Field(default_factory=lambda: [ReinforcementParamsTabLoadingCombinationsItem.model_validate(item) for item in deepcopy([{'label': 'LC1', 'M_Ed': -1000.0, 'N_Ed': -100.0}, {'label': 'LC2', 'M_Ed': 3000.0, 'N_Ed': 100.0}])])


class ReinforcementParamsTabOptimise(BaseModel):
    spacing_min: int = Field(default=50)


class ReinforcementParams(BaseModel):
    tab_geometry: ReinforcementParamsTabGeometry = Field(default_factory=ReinforcementParamsTabGeometry)
    tab_loading: ReinforcementParamsTabLoading = Field(default_factory=ReinforcementParamsTabLoading)
    tab_optimise: ReinforcementParamsTabOptimise = Field(default_factory=ReinforcementParamsTabOptimise)
