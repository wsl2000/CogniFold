"""iter29 F — Mastra-style Reflector pass.

After the writer extracts concepts from all sessions of a single qid, the
Reflector consolidator runs once on the entire graph and stamps explicit
supersession markers onto concept.data:

    status:           "current" | "outdated" | "completed" | None
    superseded_by:    concept_id of the newer fact (when status="outdated")
    superseded_on:    ISO date (best-effort) when the supersession happened
    replaces:         concept_id of the older fact (when status="current"
                      and this concept supersedes one)
    supersession_subject: short topic phrase that disambiguates the lineage

The reader-side renderer (assembly._format_node) reads these fields and
adds [✅ OUTDATED] / [🆕 CURRENT] / (superseded by X on YYYY-MM-DD) /
(replaces Y) markers to the rendered concept line, so the reader can
resolve KNOWLEDGE-UPDATE questions without inferring chronology from
[YYYY-MM-DD] prefixes.

Borrowed in spirit from mastra-ai/mastra packages/memory/src/processors/
observational-memory/Reflector — but stripped down to a single
gpt-4o-mini call per qid (no 5-level compression retry; our graphs at
~50 sessions × ~15 concepts ≈ 750 concept lines fit a 30K-token prompt
comfortably).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from cognifold.agent.config import AgentConfig
from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType

logger = logging.getLogger(__name__)


_REFLECTOR_SYSTEM = """\
You are the Reflector: a consolidator that looks at every concept
extracted from a user's chat history and identifies supersession chains
— pairs of concepts where one is the newer version of an older one, OR
groups of concepts where one is the completion of a planned action.

You receive a list of concepts, each with:
  id          — stable concept id (e.g. "c-job-google-2023-08-15")
  date        — when the user mentioned this fact (YYYY-MM-DD)
  title       — short concept title
  description — one-sentence concept body

Your job has TWO outputs:

A. SUPERSESSIONS — pairs that share a SAME SUBJECT (same job, same
   address, same pet, same preference, same plan/task) where the
   content has CHANGED, REPLACED, or been MARKED UNDONE.

B. COMPLETIONS — planned actions with later evidence of completion.

(START detection is handled separately by the W3 per-session pass —
do NOT emit starts here. iter30 moved that responsibility out of the
Reflector because per-session focused calls proved more reliable than
asking one big consolidator to do everything.)

Output a JSON object with this shape:

{
  "supersessions": [
    {
      "old_id": "c-...",
      "new_id": "c-...",
      "subject": "<short noun phrase, e.g. 'home address', 'current job'>",
      "superseded_on": "YYYY-MM-DD"   // best-effort
    }
  ],
  "completions": [
    {
      "id": "c-...",
      "completion_on": "YYYY-MM-DD"
    }
  ]
}

RULES:
- SUPERSESSIONS: only include when subjects clearly match. DO NOT
  supersede merely-related concepts (coffee → tea is coexistence,
  not supersession). For chain A → B → C, output {A,B} and {B,C}
  (NOT {A,C}).
- COMPLETIONS: only when later concept references the planned action
  as done/finished/back from. Habits/recurring are not completed.
- Output strictly valid JSON. No markdown fences. No trailing commas.
- If no entries for a section, return its empty array — never omit
  the key.
"""


@dataclass
class _ReflectorConcept:
    id: str
    date: str
    title: str
    description: str


def _collect_concepts(graph: ConceptGraph) -> list[_ReflectorConcept]:
    """Pull every CONCEPT node from the graph into Reflector-input form.

    EVENT nodes are skipped (they are raw turns; supersession lives at
    the concept layer). W1 typed-attribute concepts (titles like
    "TYPED_QUANTITY: ...") are also skipped — they are atomic value
    nodes, not subjects that get superseded.
    """
    out: list[_ReflectorConcept] = []
    for n in graph.get_all_nodes():
        if n.type != NodeType.CONCEPT:
            continue
        ctype = (n.data.get("concept_type") or "").lower()
        if ctype.startswith("typed_"):
            continue
        title = n.data.get("title", "") or n.id
        # Strip [YYYY-MM-DD] / [YYYY-MM-DD HH:MM] prefix from title — the
        # date is captured separately.
        title_clean = re.sub(
            r"^\s*\[\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\]\s*",
            "",
            title,
        )
        desc = (n.data.get("description") or "").strip()
        date_field = (
            n.data.get("event_date")
            or n.data.get("date")
            or n.data.get("timestamp")
            or ""
        )
        date_short = str(date_field)[:10] if date_field else ""
        out.append(
            _ReflectorConcept(
                id=n.id,
                date=date_short,
                title=title_clean[:140],
                description=desc[:240],
            )
        )
    out.sort(key=lambda c: c.date)
    return out


def _build_user_prompt(concepts: list[_ReflectorConcept]) -> str:
    """Render the concept list as a JSON-friendly block for the LLM."""
    lines = ["Concepts to analyze:\n"]
    for c in concepts:
        lines.append(
            f'  {{"id": "{c.id}", "date": "{c.date}", '
            f'"title": "{c.title}", "description": "{c.description}"}}'
        )
    lines.append(
        "\nReturn the JSON object as specified. No prose, no markdown."
    )
    return "\n".join(lines)


def _parse_response(raw: str) -> dict[str, Any]:
    """Lenient JSON extractor — strip markdown fences if the model added them."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except Exception:
        # Try to locate the first { ... } block.
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"supersessions": [], "completions": []}


def run_reflector(
    graph: ConceptGraph,
    config: AgentConfig,
    *,
    call_llm: Any,
) -> dict[str, int]:
    """Run the Reflector pass on the graph.

    Mutates concept.data in-place: stamps `status`, `superseded_by`,
    `superseded_on`, `replaces`, `supersession_subject` fields. Returns
    a small stats dict for logging.

    Args:
        graph: the per-qid ConceptGraph.
        config: an AgentConfig pointed at the reflector LLM (use writer
            config with low effort; reflection is a mechanical pass).
        call_llm: the callable used to invoke the LLM. Passed in to
            avoid an import cycle with run_eval.

    Returns:
        Stats dict {"concepts": N, "supersessions": K, "completions": M}.
    """
    concepts = _collect_concepts(graph)
    if len(concepts) < 2:
        return {"concepts": len(concepts), "supersessions": 0, "completions": 0}

    prompt = _REFLECTOR_SYSTEM + "\n\n" + _build_user_prompt(concepts)
    try:
        raw = call_llm(prompt, config, json_mode=True)
    except TypeError:
        # Older call_llm signature without json_mode.
        raw = call_llm(prompt, config)
    except Exception as e:
        logger.warning(f"Reflector LLM call failed: {e}")
        return {"concepts": len(concepts), "supersessions": 0, "completions": 0}

    parsed = _parse_response(raw or "")
    supersessions = parsed.get("supersessions", []) or []
    completions = parsed.get("completions", []) or []

    n_sup = 0
    for s in supersessions:
        old_id = s.get("old_id")
        new_id = s.get("new_id")
        if not old_id or not new_id or old_id == new_id:
            continue
        subject = (s.get("subject") or "").strip()
        sup_on = (s.get("superseded_on") or "").strip()
        # Graph nodes are immutable Pydantic models — mutate via
        # update_node which copies and re-indexes.
        if not graph.has_node(old_id) or not graph.has_node(new_id):
            continue
        old_patch: dict[str, Any] = {
            "status": "outdated",
            "superseded_by": new_id,
        }
        if sup_on:
            old_patch["superseded_on"] = sup_on
        if subject:
            old_patch["supersession_subject"] = subject
        graph.update_node(old_id, old_patch)
        new_patch: dict[str, Any] = {
            "status": "current",
            "replaces": old_id,
        }
        if subject:
            new_patch["supersession_subject"] = subject
        graph.update_node(new_id, new_patch)
        n_sup += 1

    n_done = 0
    for c in completions:
        cid = c.get("id")
        if not cid or not graph.has_node(cid):
            continue
        node = graph.get_node_or_none(cid)
        if node is None:
            continue
        # Don't overwrite a more specific "outdated"/"current" marker.
        if node.data.get("status") in (None, "ongoing", "planned"):
            done_patch: dict[str, Any] = {"status": "completed"}
            done_on = (c.get("completion_on") or "").strip()
            if done_on:
                done_patch["completion_on"] = done_on
            graph.update_node(cid, done_patch)
            n_done += 1

    logger.info(
        f"Reflector: concepts={len(concepts)} "
        f"supersessions={n_sup} completions={n_done}"
    )
    return {
        "concepts": len(concepts),
        "supersessions": n_sup,
        "completions": n_done,
    }
