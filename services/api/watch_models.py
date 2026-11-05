"""Watch contracts: monitoring decisions are evidence rules, not trained hazard probabilities."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .selection import normalize_polygon

FEATURES = ('water', 'vegetation', 'forest', 'ground', 'coast')

class WatchArea(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-85, le=85)
    longitude: float = Field(ge=-180, le=180)
    side_km: float = Field(default=20, ge=1, le=500)
    aoi_polygon: list[list[float]] | None = Field(default=None, min_length=3, max_length=65)
    features: list[Literal['water','vegetation','forest','ground','coast']] = Field(default_factory=lambda:list(FEATURES), min_length=1, max_length=5)
    interval_hours: int = Field(default=6, ge=6, le=168)
    enabled: bool = True
    use_muse: bool = False
    auto_satellite: bool = True

    @model_validator(mode='after')
    def validate_area(self):
        self.label = self.label.strip()
        if not self.label: raise ValueError('Give this watch area a name.')
        self.features = list(dict.fromkeys(self.features))
        if self.aoi_polygon is not None:
            self.aoi_polygon,self.longitude,self.latitude,self.side_km,_=normalize_polygon(self.aoi_polygon,60)
        return self

class WatchSwitch(BaseModel):
    enabled: bool
    auto_satellite: bool | None = None

class SatelliteOptions(BaseModel):
    include_sam: bool = True

class Brief(BaseModel):
    summary: str = Field(min_length=10, max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    next_steps: list[str] = Field(min_length=1, max_length=5)
