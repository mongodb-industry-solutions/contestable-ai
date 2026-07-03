from __future__ import annotations
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.collection import Collection
from data.config import MONGODB_URI

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client


def get_db():
    return get_client()["iomt_contestable_ai"]


# ------------------------------------------------------------------ Healthcare collections

def get_telemetry() -> Collection:
    return get_db()["device_telemetry"]


def get_historical_cases() -> Collection:
    return get_db()["historical_cases"]


def get_argument_records() -> Collection:
    return get_db()["argument_records"]


def get_care_plans() -> Collection:
    return get_db()["care_plans"]


# ------------------------------------------------------------------ Manufacturing collections

def get_site_telemetry() -> Collection:
    return get_db()["site_telemetry"]


def get_verified_mappings() -> Collection:
    return get_db()["verified_mappings"]


def get_onboarding_records() -> Collection:
    return get_db()["onboarding_records"]


# ------------------------------------------------------------------ Shared context storage

def get_session_contexts() -> Collection:
    return get_db()["session_contexts"]


def save_context(context_dict: dict, session_id: str, domain: str) -> None:
    """Save a PatientContext or SiteContext dict to MongoDB, keyed by session_id."""
    get_session_contexts().update_one(
        {"session_id": session_id},
        {"$set": {
            **context_dict,
            "session_id": session_id,
            "domain": domain,
            "saved_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )


# ------------------------------------------------------------------ Healthcare queries

def vector_search_cases(embedding: list[float], k: int = 3) -> list[dict]:
    """Atlas Vector Search over historical_cases.embedding (cosine similarity)."""
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 50,
                "limit": k,
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "patient_id": 1,
                "age": 1,
                "summary": 1,
                "device_trends": 1,
                "care_plan_changes": 1,
                "outcome": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(get_historical_cases().aggregate(pipeline))


def get_telemetry_for_patient(patient_id: str) -> list[dict]:
    """Return all telemetry docs for a patient, sorted by timestamp."""
    return list(
        get_telemetry()
        .find({"metadata.patient_id": patient_id}, {"_id": 0})
        .sort("timestamp", 1)
    )


# ------------------------------------------------------------------ Manufacturing queries

def get_telemetry_for_site(site_id: str) -> dict:
    """Return the site telemetry document for a given site."""
    doc = get_site_telemetry().find_one({"site_id": site_id}, {"_id": 0})
    return doc or {}


def vector_search_mappings(embedding: list[float], k: int = 3) -> list[dict]:
    """Atlas Vector Search over verified_mappings.embedding (cosine similarity)."""
    pipeline = [
        {
            "$vectorSearch": {
                "index": "mapping_vector_index",
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": 50,
                "limit": k,
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "site_id": 1,
                "point_name": 1,
                "verified_brick_class": 1,
                "equipment_series": 1,
                "notes": 1,
                "verified_by": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    return list(get_verified_mappings().aggregate(pipeline))


# ------------------------------------------------------------------ Shared write operations

def save_arguments(arguments: list[dict]) -> None:
    """Upsert argument records by argument_id."""
    col = get_argument_records()
    for arg in arguments:
        col.update_one(
            {"argument_id": arg["argument_id"]},
            {"$set": arg},
            upsert=True,
        )


def get_arguments_for_session(session_id: str) -> list[dict]:
    return list(get_argument_records().find({"session_id": session_id}, {"_id": 0}))


def save_care_plan(plan: dict) -> None:
    get_care_plans().insert_one(plan)


def save_onboarding_record(record: dict) -> None:
    get_onboarding_records().insert_one(record)
