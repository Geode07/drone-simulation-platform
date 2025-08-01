# models.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class GPSPoint(BaseModel):
    ts: datetime
    lat: float
    lon: float
    alt: float
    agl: Optional[float]
    heading: Optional[float]

class DroneBatch(BaseModel):
    drone_id: str
    data: List[GPSPoint]
