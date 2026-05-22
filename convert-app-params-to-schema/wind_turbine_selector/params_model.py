from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

class WindTurbineSelectorParams(BaseModel):
    turbine_model: str = Field(default='Vestas V150-4.5 MW')
