# utils/schemas.py
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

class LogisticsRequirements(BaseModel):
    mobility_level: str = Field(description="Must be: Ambulatory, Wheelchair, or Stretcher")
    required_equipment: List[str] = Field(description="List of medical equipment like Oxygen, IV Drip, etc.")
    medical_escort_needed: bool = Field(description="True if a nurse or doctor must travel with the patient")
    search_query: str = Field(description="Optimized string for searching transport prices")


class TotalCarePackage(BaseModel):
    base_medical_cost: float = Field(description="Estimated treatment cost before grants and travel.")
    grant_reduction: float = Field(default=0.0, description="Estimated subsidy applied to the package.")
    travel_cost: float = Field(default=0.0, description="Simulated travel cost for the patient.")
    net_cost: float = Field(default=0.0, description="Final estimated package cost after grants.")
    within_budget: bool = Field(default=False, description="Whether the net package cost fits within the user's budget.")


class UserPriorityPreference(BaseModel):
    mode: Literal["balanced", "lowest_net_cost", "fastest_access", "clinical_quality"] = "balanced"
    manual_override: bool = False


class StructuredItinerary(BaseModel):
    headline: str
    summary: str
    origin_city: str
    destination_city: str
    destination_hospital: str
    travel_mode: str = "Commercial Flight"
    travel_duration_hours: float = 0.0
    travel_cost_usd: float = 0.0
    grant_name: Optional[str] = None
    grant_amount_usd: float = 0.0


class AntigravityState(BaseModel):
    retriever_source: str = "chromadb"
    retrieval_strategy: str = "financial_reranker"
    user_origin: str
    hospital_location: str
    user_priority_preference: UserPriorityPreference
    total_care_package: TotalCarePackage
    logistics: Dict[str, Any] = Field(default_factory=dict)
    charity: Optional[Dict[str, Any]] = None
