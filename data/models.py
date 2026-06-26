from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


CARE_OPTIONS = {
    "A": "Adjust insulin dosing and increase CGM alert sensitivity",
    "B": "Refer to cardiology for BP and HRV workup, defer glucose management",
    "C": "Comprehensive review — simultaneous medication adjustment, cardiology referral, and sleep hygiene intervention",
}

AGENT_ROLES = ["Endocrinologist", "Cardiologist", "Sleep Medicine", "Geriatrician"]


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
