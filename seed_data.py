#!/usr/bin/env python3
"""
Seed MongoDB with data for the Contestable AI demo.
Covers both domains:
  - Healthcare: synthetic IoMT telemetry + historical cases for Patient PAT-0074
  - Manufacturing: HVAC site telemetry + verified Brick mappings for SITE-0042

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
# Manufacturing seed data
# ---------------------------------------------------------------------------

SITE_TELEMETRY_DOC = {
    "site_id": "SITE-0042",
    "site_type": "Commercial Office Building",
    "location": "Chicago, IL",
    "equipment_series": "HVAC Systems Manufacturer EQ-7700",
    "total_points": 247,
    "ambiguous_points": 18,
    "focus_point": "AHU-1-DISCH-T",
    "point_list_sample": [
        "AHU-1-DISCH-T", "AHU-1-SUPPLY-T", "AHU-1-RETURN-T",
        "AHU-1-OA-T", "AHU-1-COOL-CMD", "AHU-1-HEAT-CMD",
        "AHU-2-DISCH-T", "AHU-2-SUPPLY-T",
        "VAV-1-01-FLOW", "VAV-1-02-FLOW", "VAV-1-03-FLOW",
        "FCU-3-SUPPLY-T", "FCU-3-RETURN-T",
        "CHILLER-1-SUCTION-T", "CHILLER-1-DISCHARGE-T",
        "COOLING-TOWER-1-SUPPLY-T",
    ],
    "documentation_fragments": [
        "Section 4.2 — Sensor Placement: The DISCH-T sensor on the EQ-7700 series is mounted in the "
        "mixed air plenum, downstream of the mixing dampers and upstream of the heating coil. This "
        "placement captures the blended temperature of return and outdoor air before conditioning.",
        "EQ-7700 Series Naming Convention (Appendix A): Temperature sensors are named by zone identifier "
        "and location abbreviation. DISCH is derived from the discharge side of the mixing box, not the "
        "coil discharge. SUPPLY-T refers to post-coil conditioned air. OA-T refers to the outdoor air "
        "intake sensor.",
        "Section 7.1 — Point List: AHU-1-DISCH-T — Mixed plenum temperature sensor, 0-10V analog signal, "
        "measurement range 0-50 degrees C, located between mixing dampers and heating coil on AHU-1.",
    ],
}

VERIFIED_MAPPINGS_RAW = [
    {
        "site_id": "SITE-0031",
        "point_name": "AHU-2-DISCH-T",
        "equipment_series": "HVAC Systems Manufacturer EQ-7700",
        "verified_brick_class": "brick:Mixed_Air_Temperature_Sensor",
        "notes": "EQ-7700 series DISCH-T on AHU units maps to Mixed_Air_Temperature_Sensor. Sensor is in the mixed air plenum per section 4.2 of equipment documentation.",
        "verified_by": "Brick Domain Expert",
        "description": "AHU-2-DISCH-T on HVAC Systems Manufacturer EQ-7700 series air handling unit. Temperature sensor in mixed air plenum between mixing dampers and heating coil. Verified mapping: brick:Mixed_Air_Temperature_Sensor.",
    },
    {
        "site_id": "SITE-0019",
        "point_name": "AHU-1-DISCHARGE-TEMP",
        "equipment_series": "Building Automation Systems Manufacturer JC-5500",
        "verified_brick_class": "brick:Discharge_Air_Temperature_Sensor",
        "notes": "JC-5500 series DISCHARGE-TEMP refers to the AHU discharge outlet — post-coil conditioned air. Different naming convention from EQ-7700.",
        "verified_by": "Brick Domain Expert",
        "description": "AHU-1-DISCHARGE-TEMP on Building Automation Systems Manufacturer JC-5500 series. Post-coil conditioned discharge air temperature at AHU outlet. Verified mapping: brick:Discharge_Air_Temperature_Sensor.",
    },
    {
        "site_id": "SITE-0027",
        "point_name": "FCU-3-DISCH-T",
        "equipment_series": "HVAC Systems Manufacturer EQ-7700",
        "verified_brick_class": "brick:Supply_Air_Temperature_Sensor",
        "notes": "On EQ-7700 fan coil units (not AHUs), DISCH-T sits at the fan discharge which delivers supply air to the zone. Equipment type changes the mapping — AHU vs FCU behave differently.",
        "verified_by": "Brick Domain Expert",
        "description": "FCU-3-DISCH-T on HVAC Systems Manufacturer EQ-7700 fan coil unit. Fan discharge temperature, which is supply air delivered to the served zone. Verified mapping: brick:Supply_Air_Temperature_Sensor.",
    },
    {
        "site_id": "SITE-0038",
        "point_name": "RTU-1-DISCH-T",
        "equipment_series": "HVAC Systems Manufacturer EQ-7700",
        "verified_brick_class": "brick:Mixed_Air_Temperature_Sensor",
        "notes": "EQ-7700 rooftop unit DISCH-T behaves identically to AHU DISCH-T — mixed air plenum location confirmed by physical inspection and documentation.",
        "verified_by": "Brick Domain Expert",
        "description": "RTU-1-DISCH-T on HVAC Systems Manufacturer EQ-7700 rooftop unit. Mixed air temperature upstream of DX coil, capturing blended return and outdoor air. Verified mapping: brick:Mixed_Air_Temperature_Sensor.",
    },
    {
        "site_id": "SITE-0042",
        "point_name": "AHU-1-SUPPLY-T",
        "equipment_series": "HVAC Systems Manufacturer EQ-7700",
        "verified_brick_class": "brick:Supply_Air_Temperature_Sensor",
        "notes": "SUPPLY-T in EQ-7700 nomenclature always refers to post-coil conditioned air before zone distribution. Unambiguous mapping.",
        "verified_by": "Brick Domain Expert",
        "description": "AHU-1-SUPPLY-T on HVAC Systems Manufacturer EQ-7700 at site SITE-0042. Post-coil conditioned supply air temperature before VAV box distribution. Verified mapping: brick:Supply_Air_Temperature_Sensor.",
    },
]


def seed_manufacturing(db) -> None:
    print("\nDropping manufacturing collections...")
    for col_name in ["site_telemetry", "verified_mappings", "onboarding_records", "session_contexts"]:
        db.drop_collection(col_name)

    print("Inserting site telemetry for SITE-0042...")
    db["site_telemetry"].insert_one(SITE_TELEMETRY_DOC)
    print("  Inserted 1 site telemetry document")

    print("Generating embeddings and inserting verified mappings...")
    mappings_with_embeddings = []
    for i, mapping in enumerate(VERIFIED_MAPPINGS_RAW):
        print(f"  Embedding mapping {i + 1}/{len(VERIFIED_MAPPINGS_RAW)}: {mapping['point_name']}")
        embedding = embed(mapping["description"])
        mappings_with_embeddings.append({**mapping, "embedding": embedding})

    db["verified_mappings"].insert_many(mappings_with_embeddings)
    print(f"  Inserted {len(mappings_with_embeddings)} verified mappings")

    print("Creating Atlas Vector Search index on verified_mappings.embedding...")
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
            name="mapping_vector_index",
            type="vectorSearch",
        )
        db["verified_mappings"].create_search_index(model=index_model)
        print("  mapping_vector_index created (may take 1-2 minutes to build on Atlas).")
    except Exception as e:
        print(f"  Warning: could not create search index automatically: {e}")
        print(f"  Create it manually: index name 'mapping_vector_index', field 'embedding', {VOYAGE_EMBEDDING_DIMS} dims, cosine.")


# ---------------------------------------------------------------------------
# Main seed routine
# ---------------------------------------------------------------------------

def main() -> None:
    client = MongoClient(MONGODB_URI)
    db = client["iomt_contestable_ai"]

    # ---- Healthcare ----
    print("Dropping existing healthcare collections...")
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
        print(f"  Create it manually in Atlas UI: index name 'vector_index', field 'embedding', {VOYAGE_EMBEDDING_DIMS} dims, cosine.")

    # ---- Manufacturing ----
    seed_manufacturing(db)

    print("\nSeed complete. Wait ~2 minutes for both vector indexes to finish building before running the app.")
    client.close()


if __name__ == "__main__":
    main()
