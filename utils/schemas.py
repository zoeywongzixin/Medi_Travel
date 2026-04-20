# utils/schemas.py
from pydantic import BaseModel, Field
from typing import List

class LogisticsRequirements(BaseModel):
    mobility_level: str = Field(description="Must be: Ambulatory, Wheelchair, or Stretcher")
    required_equipment: List[str] = Field(description="List of medical equipment like Oxygen, IV Drip, etc.")
    medical_escort_needed: bool = Field(description="True if a nurse or doctor must travel with the patient")
    search_query: str = Field(description="Optimized string for searching transport prices")