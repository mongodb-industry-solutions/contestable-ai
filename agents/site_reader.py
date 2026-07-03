from __future__ import annotations
import json
import re

from crewai import Agent, Crew, Process, Task

from data import db
from data.config import embed_query, make_crewai_llm
from data.models import SiteContext


def _extract_json(text: str) -> dict:
    text = text.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if block:
        return json.loads(block.group(1).strip())
    obj = re.search(r"\{[\s\S]*\}", text)
    if obj:
        return json.loads(obj.group())
    return json.loads(text)


def run_site_reader(site_id: str = "SITE-0042", session_id: str = "") -> SiteContext:
    """
    Phase 1 (manufacturing): Analyse HVAC site point data and identify mapping challenges.
    Returns a SiteContext with all fields populated.
    """
    site_doc = db.get_telemetry_for_site(site_id)
    if not site_doc:
        return SiteContext(site_id=site_id)

    focus_point = site_doc.get("focus_point", "AHU-1-DISCH-T")
    point_list = site_doc.get("point_list_sample", [])
    doc_fragments = site_doc.get("documentation_fragments", [])
    equipment_series = site_doc.get("equipment_series", "HVAC Systems Manufacturer EQ-7700")

    point_list_text = "\n".join(f"  - {p}" for p in point_list)
    fragments_text = "\n\n".join(f"  [{i+1}] {f}" for i, f in enumerate(doc_fragments))

    agent = Agent(
        role="HVAC Systems Data Analyst",
        goal="Analyse an HVAC site's point naming conventions and identify metadata mapping challenges",
        backstory=(
            "You are a building automation systems analyst with 15 years of experience normalising "
            "proprietary HVAC point name schemas to industry-standard ontologies. You read equipment "
            "documentation carefully and identify where naming conventions create ambiguity."
        ),
        llm=make_crewai_llm(),
        verbose=False,
    )

    task = Task(
        description=f"""
Analyse the HVAC site {site_id} to prepare for mapping its proprietary point names to the Brick ontology.

SITE: {site_id} ({site_doc.get("site_type", "Commercial Office Building")}, {site_doc.get("location", "")})
EQUIPMENT SERIES: {equipment_series}
TOTAL POINTS: {site_doc.get("total_points", 0)} | AMBIGUOUS POINTS: {site_doc.get("ambiguous_points", 0)}

POINT NAME SAMPLE:
{point_list_text}

DOCUMENTATION FRAGMENTS:
{fragments_text}

FOCUS POINT FOR MAPPING REVIEW: {focus_point}

Provide your assessment as a JSON object with exactly these fields:
{{
  "equipment_summary": "2-3 sentence summary of the EQ-7700 equipment series and its naming conventions",
  "point_description": "1-2 sentence description of what {focus_point} likely measures and why it is ambiguous",
  "complexity_score": "High",
  "complexity_reason": "2-3 sentence explanation of what makes this site's metadata normalisation challenging"
}}

Return ONLY the JSON object.
""",
        expected_output="JSON object with site complexity assessment",
        agent=agent,
    )

    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    parsed = _extract_json(result.raw)

    # Embed focus point description for vector search against verified mappings
    query_text = (
        f"{focus_point} on {equipment_series}. "
        f"{parsed.get('point_description', '')}"
    )
    embedding = embed_query(query_text)
    similar_mappings = db.vector_search_mappings(embedding, k=3)

    ctx = SiteContext(
        site_id=site_id,
        site_type=site_doc.get("site_type", "Commercial Office Building"),
        location=site_doc.get("location", "Chicago, IL"),
        equipment_series=equipment_series,
        equipment_summary=parsed.get("equipment_summary", ""),
        complexity_score=parsed.get("complexity_score", "High"),
        complexity_reason=parsed.get("complexity_reason", ""),
        focus_point=focus_point,
        point_description=parsed.get("point_description", ""),
        documentation_fragments=doc_fragments,
        similar_mappings=similar_mappings,
        total_points=site_doc.get("total_points", 0),
        ambiguous_points=site_doc.get("ambiguous_points", 0),
    )

    if session_id:
        db.save_context(ctx.model_dump(), session_id, "manufacturing")

    return ctx
