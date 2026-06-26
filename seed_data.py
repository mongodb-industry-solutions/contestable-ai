#!/usr/bin/env python3
"""
Seed MongoDB with synthetic IoMT data for the Contestable AI demo (Patient PAT-0074).
Run once before starting the Streamlit app:
    python seed_data.py
"""
from __future__ import annotations
import random
from datetime import datetime, timedelta, timezone

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

# config loads .env and provides gateway-aware client factories
from data.config import MONGODB_URI, VOYAGE_EMBEDDING_DIMS, embed_texts

random.seed(42)

PATIENT_ID = "PAT-0074"
START_DATE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=21)


# ---------------------------------------------------------------------------
# Telemetry generation
# ---------------------------------------------------------------------------

def generate_telemetry() -> list[dict]:
    readings = []
    for day in range(21):
        date = START_DATE + timedelta(days=day)
        progress = day / 20.0

        # CGM: stable ~8.2 then spikes last 5 days (day 16-20)
        spike = max(0, (day - 15) / 5) * 2.0
        cgm_base = 8.2 + spike
        for hour_offset, meal_bump in [(7, 0.0), (13, 0.5), (20, 0.3)]:
            val = round(cgm_base + meal_bump + random.gauss(0, 0.15), 1)
            readings.append({
                "timestamp": date.replace(hour=hour_offset, tzinfo=timezone.utc),
                "metadata": {"patient_id": PATIENT_ID, "device": "cgm"},
                "value": max(5.5, val),
                "unit": "mmol/L",
            })

        # HRV: declining 55ms -> 38ms
        hrv_val = 55 - 17 * progress
        readings.append({
            "timestamp": date.replace(hour=6, tzinfo=timezone.utc),
            "metadata": {"patient_id": PATIENT_ID, "device": "wearable_hrv"},
            "value": round(max(28.0, hrv_val + random.gauss(0, 1.5)), 1),
            "unit": "ms",
        })

        # Sleep: declining ~5.5h -> 4.8h with noise
        sleep_val = 5.5 - 0.3 * progress
        readings.append({
            "timestamp": date.replace(hour=22, tzinfo=timezone.utc),
            "metadata": {"patient_id": PATIENT_ID, "device": "wearable_sleep"},
            "value": round(max(3.5, sleep_val + random.gauss(0, 0.35)), 1),
            "unit": "hours",
        })

        # BP systolic + diastolic: creeping up
        bp_sys = 128 + 13 * progress
        bp_dia = 82 + 7 * progress
        readings.append({
            "timestamp": date.replace(hour=9, tzinfo=timezone.utc),
            "metadata": {"patient_id": PATIENT_ID, "device": "bp_cuff", "reading": "systolic"},
            "value": round(bp_sys + random.gauss(0, 2.0), 0),
            "unit": "mmHg",
        })
        readings.append({
            "timestamp": date.replace(hour=9, tzinfo=timezone.utc),
            "metadata": {"patient_id": PATIENT_ID, "device": "bp_cuff", "reading": "diastolic"},
            "value": round(bp_dia + random.gauss(0, 1.5), 0),
            "unit": "mmHg",
        })

    return readings


# ---------------------------------------------------------------------------
# Historical cases (text + embedding)
# ---------------------------------------------------------------------------

HISTORICAL_CASES_RAW = [
    {
        "patient_id": "hist_001",
        "age": 72,
        "summary": (
            "72-year-old male with Type 2 diabetes and hypertension. CGM showed glucose spike "
            "from 8.1 to 10.5 mmol/L over 2 weeks. Blood pressure rising from 130/84 to 143/91 mmHg. "
            "HRV declining from 52ms to 40ms. Sleep averaging 5.0 hours. Multi-system decline pattern "
            "in elderly diabetic patient with cardiovascular comorbidity."
        ),
        "device_trends": {
            "glucose": "spike 8.1→10.5 mmol/L over 2 weeks",
            "blood_pressure": "rising 130/84→143/91 mmHg",
            "hrv": "declining 52ms→40ms",
            "sleep": "5.0 hours average",
        },
        "care_plan_changes": [
            "Simultaneous insulin dose adjustment (+2 units evening)",
            "Cardiology referral for BP management",
            "Sleep hygiene consultation",
            "Weekly remote IoMT monitoring review",
        ],
        "outcome": "effective",
    },
    {
        "patient_id": "hist_002",
        "age": 68,
        "summary": (
            "68-year-old female with Type 2 diabetes, no cardiac history. CGM showing glucose spike "
            "from 7.8 to 9.8 mmol/L over 3 weeks. Blood pressure stable at 125/80 mmHg. "
            "HRV within normal range at 58ms. Sleep adequate at 6.5 hours. "
            "Isolated glucose management issue with no multi-system involvement."
        ),
        "device_trends": {
            "glucose": "spike 7.8→9.8 mmol/L",
            "blood_pressure": "stable 125/80 mmHg",
            "hrv": "normal 58ms",
            "sleep": "adequate 6.5 hours",
        },
        "care_plan_changes": [
            "Insulin dosing adjustment (+1.5 units morning)",
            "CGM alert sensitivity threshold reduced to 8.5 mmol/L",
            "Dietary consultation for carbohydrate management",
        ],
        "outcome": "effective",
    },
    {
        "patient_id": "hist_003",
        "age": 76,
        "summary": (
            "76-year-old male with Type 2 diabetes and prior atrial fibrillation history. "
            "HRV declining sharply from 48ms to 28ms over 3 weeks indicating arrhythmia risk. "
            "Blood pressure rising 135/85 to 148/94 mmHg. Glucose relatively controlled at 8.3 mmol/L. "
            "Sleep disrupted at 4.8 hours. High cardiac risk profile requiring urgent intervention."
        ),
        "device_trends": {
            "glucose": "controlled 8.3 mmol/L",
            "blood_pressure": "rising sharply 135/85→148/94 mmHg",
            "hrv": "sharp decline 48ms→28ms — AF risk",
            "sleep": "disrupted 4.8 hours",
        },
        "care_plan_changes": [
            "Emergency cardiology referral within 48 hours",
            "48-hour Holter monitor for AF recurrence assessment",
            "Antihypertensive medication adjustment",
            "Deferred insulin changes pending cardiac workup",
        ],
        "outcome": "effective",
    },
    {
        "patient_id": "hist_004",
        "age": 70,
        "summary": (
            "70-year-old male with Type 2 diabetes and obstructive sleep apnea. "
            "HRV declining from 50ms to 35ms. Sleep quality poor averaging 4.5 hours with fragmented patterns. "
            "Glucose stable elevated at 8.6 mmol/L. Blood pressure borderline at 132/85 mmHg. "
            "Sleep-cardiovascular interaction pattern driving multi-system effects."
        ),
        "device_trends": {
            "glucose": "stable elevated 8.6 mmol/L",
            "blood_pressure": "borderline 132/85 mmHg",
            "hrv": "declining 50ms→35ms",
            "sleep": "fragmented 4.5 hours",
        },
        "care_plan_changes": [
            "CPAP therapy initiation for sleep apnea",
            "Sleep specialist referral",
            "Monitor glucose response to improved sleep quality",
            "Mild antihypertensive introduction",
        ],
        "outcome": "partially_effective",
    },
    {
        "patient_id": "hist_005",
        "age": 73,
        "summary": (
            "73-year-old female with Type 2 diabetes, hypertension, and CKD stage 2. "
            "Multi-system IoMT decline: glucose rising 8.0→10.2 mmol/L, HRV declining 54ms→39ms, "
            "blood pressure creeping 129/83→142/90 mmHg, sleep 5.1 hours. "
            "High-complexity coordinated multi-system intervention required in elderly diabetic patient."
        ),
        "device_trends": {
            "glucose": "rising 8.0→10.2 mmol/L",
            "blood_pressure": "creeping 129/83→142/90 mmHg",
            "hrv": "declining 54ms→39ms",
            "sleep": "5.1 hours",
        },
        "care_plan_changes": [
            "Comprehensive multi-disciplinary review within 1 week",
            "Simultaneous insulin adjustment and antihypertensive titration",
            "Renal function monitoring",
            "Sleep hygiene and stress management program",
            "Fortnightly IoMT data review appointments",
        ],
        "outcome": "effective",
    },
]


def embed(text: str) -> list[float]:
    return embed_texts([text])[0]


# ---------------------------------------------------------------------------
# Main seed routine
# ---------------------------------------------------------------------------

def main() -> None:
    client = MongoClient(MONGODB_URI)
    db = client["iomt_contestable_ai"]

    print("Dropping existing collections...")
    for col_name in ["device_telemetry", "historical_cases", "argument_records", "care_plans"]:
        db.drop_collection(col_name)

    # Create time series collection for telemetry
    print("Creating device_telemetry time series collection...")
    db.create_collection(
        "device_telemetry",
        timeseries={
            "timeField": "timestamp",
            "metaField": "metadata",
            "granularity": "hours",
        },
    )

    print("Inserting 3 weeks of telemetry for Patient PAT-0074...")
    readings = generate_telemetry()
    db["device_telemetry"].insert_many(readings)
    print(f"  Inserted {len(readings)} telemetry readings")

    print("Generating embeddings and inserting historical cases...")
    cases_with_embeddings = []
    for i, case in enumerate(HISTORICAL_CASES_RAW):
        print(f"  Embedding case {i + 1}/{len(HISTORICAL_CASES_RAW)}: {case['patient_id']}")
        embedding = embed(case["summary"])
        cases_with_embeddings.append({**case, "embedding": embedding})

    db["historical_cases"].insert_many(cases_with_embeddings)
    print(f"  Inserted {len(cases_with_embeddings)} historical cases")

    # Create Atlas Vector Search index
    print("Creating Atlas Vector Search index on historical_cases.embedding...")
    try:
        index_model = SearchIndexModel(
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": VOYAGE_EMBEDDING_DIMS,
                        "similarity": "cosine",
                    }
                ]
            },
            name="vector_index",
            type="vectorSearch",
        )
        db["historical_cases"].create_search_index(model=index_model)
        print("  Vector search index created (may take 1-2 minutes to build on Atlas).")
    except Exception as e:
        print(f"  Warning: could not create search index automatically: {e}")
        print("  Create it manually in Atlas UI: index name 'vector_index', field 'embedding', 1536 dims, cosine.")

    print("\nSeed complete. Wait ~2 minutes for the vector index to finish building before running the app.")
    client.close()


if __name__ == "__main__":
    main()
