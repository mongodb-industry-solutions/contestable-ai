# IoMT Contestable AI

A multi-agent AI demo that shows what clinical decision-making looks like when humans stay in control. AI specialist agents analyse patient IoMT data and recommend a care plan — but the recommendation is **contestable**: a clinician can challenge, modify, or override any argument, and the system updates its recommendation accordingly. Every action is auditable.

This is built as a reference demo for the medical devices / digital health vertical.

---

## What it demonstrates

Most AI demos show AI making a decision. This one shows AI making a *contestable* decision.

Four specialist AI agents review 21 days of wearable sensor data for a 74-year-old patient and generate arguments for and against three care plan options. A mathematical scoring framework (QBAF — Quantitative Bipolar Argumentation Framework) weighs all arguments and surfaces a recommendation. Then the Family Physician steps in — rejecting an argument they disagree with, adding clinical context the AI didn't have — and the recommendation changes. Everything is stored in MongoDB Atlas with a full audit trail.

**For example:** AI recommends Option A (insulin adjustment). GP adds family history of arrhythmia. Option C (comprehensive review) wins.

---

## Architecture

```
IoMT Telemetry (MongoDB)
        ↓
Phase 1 — Patient Analyzer Agent
    Pulls 21 days of CGM, HRV, BP, sleep data
    Vector search on historical cases (Voyage AI embeddings)
    Produces structured PatientContext
        ↓
Phase 2 — 4 Specialist Agents (CrewAI)
    Endocrinologist · Cardiologist · Sleep Medicine · Geriatrician
    Each generates 6 arguments (support + challenge × 3 options)
    QBAF scoring: score = sigmoid(τ + 0.3·Σsupport − 0.3·Σchallenge)
    → Option A leads
        ↓
Phase 3 — Human Contestation (Family Physician)
    Accept / Reject / Modify any argument
    Add new arguments with clinical context
    Recompute QBAF scores
    → Option C wins
        ↓
Phase 4 — Care Plan Agent
    Generates final care plan with rationale + implementation steps
    Before/after confidence chart
    Full audit trail saved to MongoDB
```

---

## Tech stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| Agent orchestration | CrewAI |
| LLM | GPT-4o (OpenAI / Grove gateway) |
| Embeddings | Voyage AI (`voyage-3-large`, 1024 dims) |
| Database | MongoDB Atlas (time series, vector search, document) |
| Argumentation | QBAF — pure Python, 10-iteration convergence |
| Data validation | Pydantic v2 |

---

## Project structure

```
├── app.py                      # Streamlit entry point
├── seed_data.py                # Populate MongoDB with telemetry + historical cases
├── data/
│   ├── config.py               # Env config, OpenAI + Voyage client factories
│   ├── db.py                   # MongoDB singleton + query functions
│   └── models.py               # Pydantic models, CARE_OPTIONS, AGENT_ROLES
├── agents/
│   ├── patient_analyzer.py     # Phase 1: patient context + vector search
│   ├── specialist_agents.py    # Phase 2: 4 specialist CrewAI agents
│   └── careplan_agent.py       # Phase 4: final care plan generation
├── argumentation/
│   └── qbaf.py                 # QBAF scoring engine
├── contestation/
│   └── handler.py              # Apply GP edits + rescore
└── ui/
    ├── sidebar.py              # Patient info, phase status, demo guide
    ├── tab1_overview.py        # Phase 1 charts + complexity assessment
    ├── tab2_argumentation.py   # Phase 2 live agent progress + argument graph
    ├── tab3_contestation.py    # Phase 3 argument cards + GP controls
    └── tab4_careplan.py        # Phase 4 care plan + audit trail
```

---

## Prerequisites

- Python 3.11+
- MongoDB Atlas cluster with:
  - A database named `iomt_contestable_ai`
  - A **Vector Search index** on `historical_cases` collection (see setup below)
- OpenAI API key (or Grove gateway credentials)
- Voyage AI API key

---

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/mongodb-industry-solutions/iomt-contestable-ai.git
cd iomt-contestable-ai
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
# Edit .env with your credentials
```

**3. Seed the database**

```bash
python seed_data.py
```

This creates synthetic telemetry (147 readings) and 5 historical cases with Voyage AI embeddings in MongoDB Atlas.

**4. Create the Atlas Vector Search index**

In MongoDB Atlas UI → your cluster → Search Indexes → Create Index:

- Collection: `iomt_contestable_ai.historical_cases`
- Index name: `vector_index`
- Definition:
```json
{
  "fields": [{
    "type": "vector",
    "path": "embedding",
    "numDimensions": 1024,
    "similarity": "cosine"
  }]
}
```

**5. Run the app**

```bash
streamlit run app.py
```

---

## Demo flow

Open the **🎯 Demo Guide** in the sidebar for a step-by-step walkthrough. The core narrative:

1. Run Phase 1 — AI analyses patient trends (~20s)
2. Run Phase 2 — 4 agents generate 24 arguments, Option A leads (~2 min)
3. Phase 3 — GP rejects the Cardiologist's challenge on Option C, adds a family history argument → **Option C wins**
4. Phase 4 — Care plan generated with full audit trail

---

## MongoDB collections

| Collection | Purpose |
|---|---|
| `device_telemetry` | Time series IoMT readings (CGM, HRV, BP, sleep) |
| `historical_cases` | Past patient cases with Voyage AI embeddings for vector search |
| `arguments` | All AI-generated and GP-edited arguments per session |
| `care_plans` | Final care plan output per session |

---

## Environment variables

See `.env.example` for all required variables. The app supports both direct OpenAI and custom gateway configurations via `OPENAI_BASE_URL` and `OPENAI_API_KEY_HEADER`.
