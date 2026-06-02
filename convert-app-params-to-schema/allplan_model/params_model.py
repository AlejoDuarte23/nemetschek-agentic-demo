from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class AllplanModelParamsGeometry(BaseModel):
    foundation_diameter: float = Field(default=14000.0)
    foundation_edge_thickness: float = Field(default=900.0)
    foundation_center_thickness: float = Field(default=1800.0)
    pedestal_diameter: float = Field(default=4200.0)
    pedestal_height: float = Field(default=2200.0)
    pile_count: int = Field(default=12)
    pile_edge_distance: float = Field(default=600.0)
    pile_diameter: float = Field(default=700.0)
    pile_depth: float = Field(default=12000.0)


class AllplanModelParamsReinforcement(BaseModel):
    cover: float = Field(default=75.0)
    top_radial_bar_diameter: float = Field(default=25.0)
    top_radial_bar_count: int = Field(default=32)
    ring_bar_diameter: float = Field(default=20.0)
    ring_spacing: float = Field(default=550.0)
    pedestal_grid_bar_diameter: float = Field(default=20.0)
    pedestal_grid_spacing: float = Field(default=350.0)
    pedestal_frame_embed_depth: float = Field(default=1200.0)
    pedestal_tie_diameter: float = Field(default=12.0)
    pedestal_tie_spacing: float = Field(default=250.0)
    pile_vertical_diameter: float = Field(default=16.0)
    pile_vertical_count: int = Field(default=8)
    pile_vertical_embed_depth: float = Field(default=500.0)
    pile_hoop_diameter: float = Field(default=10.0)
    pile_hoop_spacing: float = Field(default=300.0)


class AllplanModelParams(BaseModel):
    geometry: AllplanModelParamsGeometry = Field(default_factory=AllplanModelParamsGeometry)
    reinforcement: AllplanModelParamsReinforcement = Field(default_factory=AllplanModelParamsReinforcement)
