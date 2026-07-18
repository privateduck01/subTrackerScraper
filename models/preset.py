from typing import List
from pydantic import BaseModel, Field

class PresetPrice(BaseModel):
    cost: float
    currency: str
    region: str

class PresetTier(BaseModel):
    name: str
    prices: List[PresetPrice]
    periodQty: int = 1
    periodUnit: str = "MONTH"

class Preset(BaseModel):
    id: str
    name: str
    iconUrl: str
    tiers: List[PresetTier]
    defaultTier: int = 0
    tags: List[str] = Field(default_factory=list)
