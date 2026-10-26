from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ------------------------------------------------------------------ Healthcare

CARE_OPTIONS = {
    "A": "Adjust insulin dosing and increase CGM alert sensitivity",
    "B": "Refer to cardiology for BP and HRV workup, defer glucose management",
    "C": "Comprehensive review — simultaneous medication adjustment, cardiology referral, and sleep hygiene intervention",
}

AGENT_ROLES = ["Endocrinologist", "Cardiologist", "Sleep Medicine", "Geriatrician"]

# ------------------------------------------------------------------ Manufacturing

MAPPING_OPTIONS = {
    "A": "brick:Supply_Air_Temperature_Sensor",
    "B": "brick:Discharge_Air_Temperature_Sensor",
    "C": "brick:Mixed_Air_Temperature_Sensor",
}

MAPPING_AGENT_ROLES = ["String Matcher", "Documentation Reader"]

# ------------------------------------------------------------------ Domain configs

DOMAIN_CONFIGS = {
    "healthcare": {
        "name": "Healthcare",
        "subtitle": "IoMT Patient Review",
        "icon": "🏥",
        "description": "Four AI specialist agents analyse 21 days of wearable sensor data for a patient and debate three care plan options. A Family Physician reviews and contests the recommendation.",
        "subject_id": "PAT-0074",
        "subject_label": "Patient",
        "options": CARE_OPTIONS,
        "agent_roles": AGENT_ROLES,
        "reviewer_role": "Family Physician",
        "phase_labels": ["Patient Overview", "Argumentation", "Contestation", "Care Plan"],
        "phase_icons": ["📊", "🧠", "✋", "📋"],
    },
    "manufacturing": {
        "name": "Manufacturing",
        "subtitle": "HVAC Metadata Normalization",
        "icon": "🏭",
        "description": "Two AI agents analyse a synthetic site's vendor-specific HVAC point names and map them to a standard Brick ontology. A domain expert reviews and corrects the AI's mapping proposals.",
        "subject_id": "SITE-0042",
        "subject_label": "Site",
        "options": MAPPING_OPTIONS,
        "agent_roles": MAPPING_AGENT_ROLES,
        "reviewer_role": "Brick Domain Expert",
        "phase_labels": ["Site Overview", "Mapping Analysis", "Expert Review", "Onboarding Record"],
        "phase_icons": ["🏗️", "🔗", "✋", "📋"],
        "focus_point": "AHU-1-DISCH-T",
    },
}

# ------------------------------------------------------------------ Shared Argument model

class Argument(BaseModel):
    argument_id: str
    session_id: str
    content: str
    type: Literal["support", "challenge"]
    agent_role: str
    option: Literal["A", "B", "C"]
    tau: float = Field(ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    final_score: Optional[float] = None
    human_edit: bool = False
    edit_type: Optional[Literal["accept", "reject", "modify", "add"]] = None
    original_content: Optional[str] = None
    editor_role: Optional[str] = None
    is_rejected: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_mongo(self) -> dict:
        d = self.model_dump()
        d["timestamp"] = self.timestamp
        return d


# ------------------------------------------------------------------ Healthcare context

class PatientContext(BaseModel):
    patient_id: str = "PAT-0074"
    age: int = 74
    complexity_score: str = "High"
    complexity_reason: str = ""
    patient_summary: str = ""
    key_concerns: list[str] = Field(default_factory=list)
    glucose_trend: str = ""
    hrv_trend: str = ""
    bp_trend: str = ""
    sleep_trend: str = ""
    similar_cases: list[dict] = Field(default_factory=list)


# ------------------------------------------------------------------ Manufacturing context

class SiteContext(BaseModel):
    site_id: str = "SITE-0042"
    site_type: str = "Commercial Office Building"
    location: str = "Chicago, IL"
    equipment_series: str = "HVAC Systems Manufacturer EQ-7700"
    equipment_summary: str = ""
    complexity_score: str = "High"
    complexity_reason: str = ""
    focus_point: str = "AHU-1-DISCH-T"
    point_description: str = ""
    documentation_fragments: list[str] = Field(default_factory=list)
    similar_mappings: list[dict] = Field(default_factory=list)
    total_points: int = 0
    ambiguous_points: int = 0
