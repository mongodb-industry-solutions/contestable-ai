from __future__ import annotations
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


def get_telemetry() -> Collection:
    return get_db()["device_telemetry"]


def get_historical_cases() -> Collection:
    return get_db()["historical_cases"]


def get_argument_records() -> Collection:
    return get_db()["argument_records"]


def get_care_plans() -> Collection:
    return get_db()["care_plans"]


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
