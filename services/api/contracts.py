from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from .config import SOURCES
from .selection import normalize_polygon

Theme = Literal['water','vegetation','forest','ground','coast']

class AnalysisRequest(BaseModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-89, le=89)
    side_km: float = Field(default=20, ge=1, le=500)
    source: Literal['landsat','sentinel2','hls_l30','hls_s30','modis','sentinel1'] = 'landsat'
    mode: Literal['history','event'] = 'history'
    from_year: int = Field(default=2000, ge=1982, le=2100)
    to_year: int = Field(default=2020, ge=1982, le=2100)
    start_month: int = Field(default=6, ge=1, le=12)
    end_month: int = Field(default=8, ge=1, le=12)
    before_date: date | None = None
    after_date: date | None = None
    window_days: int = Field(default=14, ge=0, le=45)
    resolution: int = Field(default=30, ge=20, le=5000)
    max_scenes: int = Field(default=3, ge=1, le=8)
    theme: Theme = 'water'  # accepts older saved requests
    themes: list[Theme] | None = Field(default=None, min_length=1, max_length=5)
    aoi_polygon: list[list[float]] | None = Field(default=None, min_length=3, max_length=65)
    use_sam: bool = True
    use_reasoning: bool = True
    use_weather: bool = True
    label: str = Field(default='Selected area', max_length=160)

    @model_validator(mode='after')
    def validate_period(self):
        self.themes = list(dict.fromkeys(self.themes if self.themes is not None else [self.theme]))
        self.theme = self.themes[0]
        if self.source == 'sentinel1' and self.themes != ['water']:
            raise ValueError('Radar supports backscatter investigation only. Select Water, or use an optical source for other themes.')
        if self.aoi_polygon is not None:
            self.aoi_polygon, self.longitude, self.latitude, self.side_km, _ = normalize_polygon(self.aoi_polygon, self.resolution)
        minimum = SOURCES[self.source]['start']
        if self.mode == 'history':
            if self.from_year > self.to_year or self.to_year > date.today().year:
                raise ValueError('Choose an ordered year range ending no later than this year.')
            if self.from_year < minimum:
                raise ValueError(f'{SOURCES[self.source]["name"]} in this catalog starts in {minimum}. Choose a different source or range.')
            if self.start_month > self.end_month:
                raise ValueError('Use a seasonal window within one calendar year.')
        else:
            if not self.before_date or not self.after_date or self.before_date >= self.after_date:
                raise ValueError('Event mode needs two ordered dates.')
            if self.before_date.year < minimum or self.after_date > date.today():
                raise ValueError('Dates lie outside the selected archive or in the future.')
            if (self.after_date-self.before_date).days <= self.window_days*2:
                raise ValueError('Observation windows overlap. Reduce the search window.')
        if self.resolution < SOURCES[self.source]['resolution']:
            raise ValueError('Analysis resolution cannot be finer than the source bands.')
        if self.side_km*1000/self.resolution > 2048:
            raise ValueError('Selection exceeds the local 2048 × 2048 analysis grid. Increase the explicit analysis cell size or reduce the square.')
        return self

class RefineRequest(BaseModel):
    index: int = Field(ge=0)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)

