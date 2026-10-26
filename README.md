# Contestable AI — IoMT & Manufacturing Demo

A multi-domain AI demo that shows what high-stakes decisions look like when humans stay in control. AI agents analyse data and propose a recommendation — but the recommendation is **contestable**: a domain expert can challenge, modify, or override any argument, and the system updates its recommendation accordingly. Every action is auditable.

Two domains are included: one in healthcare (patient IoMT review) and one in manufacturing (HVAC metadata normalisation). Both use the same underlying framework.

---

## What it demonstrates

Most AI demos show AI making a decision. This one shows AI making a *contestable* decision.

Specialist AI agents generate arguments for and against a set of options. A mathematical scoring framework (QBAF) weighs all arguments and surfaces a recommendation. Then the human expert steps in — rejecting an argument they disagree with, adding context the AI didn't have — and the recommendation changes. The whole interaction is stored in MongoDB Atlas with a full audit trail.

### Healthcare scenario

Four specialist agents review 21 days of wearable sensor data for a 74-year-old patient and debate three care plan options. The Family Physician rejects a flawed argument and adds family cardiac history. Option C (comprehensive review) wins over Option A (insulin adjustment alone).

### Manufacturing scenario

Two AI agents analyse a synthetic HVAC point name (`AHU-1-DISCH-T` on a fictional EQ-7700 series unit) and propose a Brick ontology mapping. The String Matcher favours Option B (Discharge sensor) based on the abbreviation. The Documentation Reader finds section 4.2 of the manual and argues for Option C (Mixed Air sensor). A Brick domain expert rejects the String Matcher's challenge and adds documentation-backed evidence. Option C wins — the correct mapping per the equipment documentation.

---

## Architecture (both domains share the same 4-phase structure)

```
Data Source (MongoDB)
        ↓
Phase 1 — Data Analyst Agent
    Reads site/patient data from MongoDB
    Vector search on historical cases / verified mappings (Voyage AI embeddings)
    Produces structured context (PatientContext or SiteContext)
    Saved to session_contexts collection
        ↓
Phase 2 — Specialist Agents (CrewAI, 4 for healthcare / 2 for manufacturing)
    Each generates 6 arguments (support + challenge × 3 options)
    QBAF scoring: score = sigmoid(τ + 0.3·Σsupport − 0.3·Σchallenge)
    → One option leads on initial scores
        ↓
Phase 3 — Human Contestation
    Accept / Reject / Modify any argument
    Add new arguments with domain expert context
    Recompute QBAF scores → recommendation changes
        ↓
Phase 4 — Output Agent
    Healthcare: generates care plan with rationale + implementation steps
    Manufacturing: generates onboarding record with propagation steps
    Before/after confidence chart + full audit trail saved to MongoDB
```

---

## Tech stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| Agent orchestration | CrewAI |
| LLM | GPT-4o (OpenAI or Grove gateway) |
| Embeddings | Voyage AI (`voyage-3-large`, 1024 dims) |
| Database | MongoDB Atlas (time series, vector search, document) |
| Argumentation | QBAF — pure Python, 10-iteration convergence |
| Data validation | Pydantic v2 |

---

## Project structure

```
├── app.py                        # Streamlit entry point + domain switcher
├── seed_data.py                  # Seed MongoDB (both domains)
├── data/
│   ├── config.py                 # Env config, client factories
│   ├── db.py                     # MongoDB singleton + query functions
│   └── models.py                 # Pydantic models, DOMAIN_CONFIGS, options
├── agents/
│   ├── patient_analyzer.py       # Phase 1 healthcare: PatientContext
│   ├── specialist_agents.py      # Phase 2 healthcare: 4 specialist agents
│   ├── careplan_agent.py         # Phase 4 healthcare: care plan generation
│   ├── site_reader.py            # Phase 1 manufacturing: SiteContext
│   ├── mapping_agent.py          # Phase 2 manufacturing: String Matcher + Documentation Reader
│   └── onboarding_agent.py       # Phase 4 manufacturing: onboarding record
├── argumentation/
│   └── qbaf.py                   # QBAF scoring engine
├── contestation/
│   └── handler.py                # Apply expert edits + rescore
└── ui/
    ├── sidebar.py                # Domain-aware sidebar + demo guide
    ├── tab1_overview.py          # Phase 1 (branched by domain)
    ├── tab2_argumentation.py     # Phase 2 (branched by domain)
    ├── tab3_contestation.py      # Phase 3 (domain-aware options + reviewer)
    └── tab4_careplan.py          # Phase 4 (branched by domain)
```

---

## Prerequisites

- Python 3.11+
- MongoDB Atlas cluster with a database named `iomt_contestable_ai`
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

**3. Seed both domains**

```bash
python seed_data.py
```

This seeds:
- **Healthcare:** 147 IoMT telemetry readings + 5 historical cases with Voyage AI embeddings
- **Manufacturing:** SITE-0042 site document + 5 verified Brick mappings with embeddings

It also attempts to create both Atlas Vector Search indexes automatically. If that fails (Atlas M0 free tiers restrict programmatic index creation), create them manually:

**Healthcare — `historical_cases.vector_index`**
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

**Manufacturing — `verified_mappings.mapping_vector_index`**
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

Both indexes take 1–2 minutes to build after creation. Run the app only after both show status **Active**.

**4. Run the app**

```bash
streamlit run app.py
```

---

## Demo flows

The **🎯 Demo Guide** in the sidebar gives step-by-step instructions for the active domain.

### Healthcare

| Phase | Action | Expected result |
|---|---|---|
| 1 | Run Phase 1 | ~20s · Patient summary, complexity badge, 4 trend charts, 3 similar cases |
| 2 | Run Phase 2 | ~2 min · 4 agents complete · Option A leads at ~60–70% |
| 3 | Select Option C · Reject Cardiologist challenge · Add GP argument (pre-filled) · Recompute | Option C overtakes A |
| 4 | Generate Care Plan | Option C confirmed · Before/after chart · Audit trail |

### Manufacturing

| Phase | Action | Expected result |
|---|---|---|
| 1 | Run Phase 1 | ~20s · Site info, AHU-1-DISCH-T focus point, 3 doc fragments, 3 similar verified mappings |
| 2 | Run Phase 2 | ~1 min · 2 agents complete · Option B likely leads (String Matcher favours "DISCH") |
| 3 | Select Option C · Reject String Matcher challenge · Add expert argument (pre-filled) · Recompute | Option C wins |
| 4 | Generate Onboarding Record | `brick:Mixed_Air_Temperature_Sensor` confirmed · Propagation steps · Audit trail |

To switch between domains: click **🔄 Change Domain** in the sidebar. All session state resets.

---

## MongoDB collections

| Collection | Domain | Purpose |
|---|---|---|
| `device_telemetry` | Healthcare | Time series IoMT readings (CGM, HRV, BP, sleep) |
| `historical_cases` | Healthcare | Past patient cases with embeddings for vector search |
| `site_telemetry` | Manufacturing | HVAC site documents (point lists, documentation fragments) |
| `verified_mappings` | Manufacturing | Historical verified Brick mappings with embeddings |
| `argument_records` | Both | AI-generated and human-edited arguments per session |
| `care_plans` | Healthcare | Final care plan output per session |
| `onboarding_records` | Manufacturing | Verified mapping record per session |
| `session_contexts` | Both | PatientContext / SiteContext saved per session |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URI` | Yes | Atlas connection string |
| `OPENAI_API_KEY` | Yes | OpenAI or Grove API key |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4o`) |
| `OPENAI_BASE_URL` | No | Gateway base URL (Grove / Azure / etc.) |
| `OPENAI_API_KEY_HEADER` | No | Custom auth header name for gateways |
| `VOYAGE_API_KEY` | Yes | Voyage AI API key |
| `VOYAGE_MODEL` | No | Embedding model (default: `voyage-3-large`) |
