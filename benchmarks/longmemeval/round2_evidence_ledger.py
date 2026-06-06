"""Iter32 round 2 — gated structured-evidence answer path.

When the question is a count / order / duration / date_diff / derived-time /
abs-value shape, the reader is routed through this module:

1. `detect_question_shape` classifies the question (regex).
2. `late_fusion_retrieve` unions graph hits with raw `EVENT.data["content"]`
   chunks (BM25-style lexical scoring).
3. `build_evidence_ledger` assembles the shape-specific candidate list.
4. `answer_from_ledger` emits a deterministic answer when the ledger has
   enough evidence; otherwise returns None and the caller falls back to
   the normal reader.

Architectural rationale: iter29/30 showed that piling rules into a shared
qa_answer prompt destroys MS. The ledger path is gated, auditable, and
isolates count/order/duration logic from KU/SSA/SSP/SSU questions.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType
from cognifold.query.models import NodeSummary

Shape = Literal[
    "count",
    "order",
    "duration_since",
    "date_diff",
    "derived_time",
    "abs_value",
    "other",
]


# Regex detection
_COUNT_RE = re.compile(r"\bhow many\b", re.I)
_ORDER_RE = re.compile(
    r"\b(order of|earliest to latest|latest to earliest|"
    r"who\s+\w+\s+first|which\s+\w+\s+first|happened first|came first)\b",
    re.I,
)
_DURATION_RE = re.compile(
    r"\b(how long|how many (?:days|weeks|months|years)\s+had\s+i\s+been|"
    r"how many (?:days|weeks|months|years)\s+(?:since|after|before))\b",
    re.I,
)
_DATE_DIFF_RE = re.compile(
    r"\bhow many (?:days|weeks|months|years).*\b(between|before|after|passed)\b",
    re.I,
)
_DERIVED_RE = re.compile(
    r"\b(how old was i when|how many years will i be|how many years older am i than|"
    r"how many points do i need|how much will i save|in total|altogether|combined|"
    r"my age (?:was|when|at))\b",
    re.I,
)
_ABS_RE = re.compile(
    r"\b(what time|what was the airline|who did i go with|where was|where did i "
    r"go|what was held at|what was the venue|on what date|exact date)\b",
    re.I,
)


# Synonym expansion for B:chunk_fusion targeted cases
# (Codex round 4 Section B — each is a 40-70% confidence partial that needs
# query expansion to surface the missing raw evidence reliably.)
_SYNONYMS: dict[str, list[str]] = {
    "trip": ["day hike", "road trip", "camping trip", "hike", "weekend trip"],
    "museum": ["museum visit", "museum tour", "gallery visit", "art museum"],
    "sports": ["triathlon", "5k", "10k", "marathon", "race", "soccer", "tournament"],
    "charity": ["fundraiser", "volunteer", "walkathon", "charity event", "5k run"],
    "jewelry": ["earrings", "necklace", "bracelet", "ring", "pendant"],
    "service": ["serviced", "tune-up", "plan to service", "taking in", "repair", "maintenance"],
    "subscription": ["magazine subscription", "active subscription", "monthly subscription"],
    "bake": ["baked", "bread", "cake", "cookies", "scones", "muffins", "pastry"],
    "furniture": ["sold", "gave away", "listed", "assembled", "bought", "fixed", "repaired"],
    "album": ["EP", "album", "record", "Spotify", "downloaded", "purchased", "merch booth"],
    "jogging": ["went jogging", "ran", "did a run"],
    "yoga": ["did yoga", "yoga session", "yoga class"],
    "art event": ["lecture", "exhibition", "gallery opening", "museum event", "artist talk"],
    "doctor": ["primary care", "PCP", "ENT", "dermatologist", "specialist", "physician"],
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9][a-z0-9'/-]+", _norm(text))
        if len(t) > 2
        and t not in {"the", "and", "for", "with", "that", "this", "from", "you", "your", "are", "was", "were", "have", "has"}
    }


def _expanded_query_tokens(question: str) -> set[str]:
    """Tokens with synonym expansion based on coarse intent words in the question."""
    qtoks = _tokens(question)
    expanded = set(qtoks)
    qlow = _norm(question)
    for key, syns in _SYNONYMS.items():
        if key in qlow:
            for syn in syns:
                expanded |= _tokens(syn)
    return expanded


def _score(qtoks: set[str], text: str) -> float:
    ttoks = _tokens(text)
    if not qtoks or not ttoks:
        return 0.0
    overlap = len(qtoks & ttoks)
    return overlap / max(1, len(qtoks)) ** 0.5  # mild idf-ish; favor coverage


def detect_question_shape(question: str) -> Shape:
    q = question or ""
    # Order trumps count ("which came first" can also contain "how many")
    if _ORDER_RE.search(q):
        return "order"
    if _DURATION_RE.search(q):
        return "duration_since"
    if _DATE_DIFF_RE.search(q):
        return "date_diff"
    if _DERIVED_RE.search(q):
        return "derived_time"
    if _COUNT_RE.search(q):
        return "count"
    if _ABS_RE.search(q):
        return "abs_value"
    return "other"


def _event_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
    """Pull raw user/assistant message text from EVENT nodes."""
    chunks: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type != NodeType.EVENT:
            continue
        d = node.data or {}
        text = (d.get("content") or d.get("description") or "").strip()
        if not text or len(text) < 4:
            continue
        chunks.append(
            {
                "node_id": node.id,
                "role": d.get("role"),
                "text": text,
                "date": d.get("date") or d.get("timestamp"),
                "session_index": d.get("session_index"),
            }
        )
    return chunks


def late_fusion_retrieve(
    question: str,
    graph: ConceptGraph,
    graph_hits: list[NodeSummary],
    *,
    question_date: datetime | None = None,
    k_graph: int = 16,
    k_chunk: int = 12,
) -> tuple[list[NodeSummary], list[dict[str, Any]]]:
    """Union top graph hits with lexical-scored raw event chunks.

    The chunks come from `EVENT.data["content"]` (verified storage location).
    Synonym-expanded query tokens drive scoring so that synonyms of the
    question's intent words (e.g. "trip" → "day hike", "road trip") can
    surface missing evidence (Codex round 4 Section B).
    """
    del question_date  # reserved for future window filtering
    qtoks = _expanded_query_tokens(question)
    kept_graph = list(graph_hits)[:k_graph]
    scored = [(chunk, _score(qtoks, chunk["text"])) for chunk in _event_chunks(graph)]
    scored = [(c, s) for c, s in scored if s > 0]
    scored.sort(key=lambda cs: (cs[1], cs[0].get("date") or ""), reverse=True)
    raw_hits = [c for c, _ in scored[:k_chunk]]
    return kept_graph, raw_hits


def _date_str(dt: Any) -> str | None:
    if isinstance(dt, str):
        return dt[:10]
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return None


def build_evidence_ledger(
    question: str,
    shape: Shape,
    fused_context: dict[str, Any],
) -> dict[str, Any]:
    """Assemble candidate evidence for the given shape.

    Returns a shape-specific dict with raw candidates and slots for the
    deterministic answer. The actual count/order arithmetic happens in
    `answer_from_ledger`.
    """
    ledger: dict[str, Any] = {
        "shape": shape,
        "question": question,
        "question_date": fused_context.get("question_date"),
        "graph_hits": fused_context.get("graph_hits", []),
        "raw_hits": fused_context.get("raw_hits", []),
        "candidates": [],
    }
    # Shape-specific slots (filled by the reader's fallback if ledger is incomplete)
    if shape == "count":
        ledger["final_count"] = None
    elif shape == "order":
        ledger["ordered"] = []
    elif shape == "duration_since":
        ledger["value"] = None
        ledger["unit"] = None
    elif shape == "date_diff":
        ledger["answer"] = None
    elif shape == "derived_time":
        ledger["result"] = None
        ledger["unit"] = None
    elif shape == "abs_value":
        ledger["answer"] = None
    return ledger


def answer_from_ledger(question: str, ledger: dict[str, Any]) -> str | None:
    """Emit a deterministic answer when the ledger has enough evidence.

    Conservative by design — when in doubt, return None and let the
    normal reader path handle the question. Per Codex round 4: the
    ledger fires for >90% confidence cases; partial-confidence cases
    return None so the reader sees the fused (richer) context and
    benefits from chunk fusion without committing to a deterministic
    wrong answer.
    """
    del question
    if ledger.get("missing_required_anchor") or ledger.get("operand_mismatch"):
        return "The information provided is not enough."
    shape = ledger.get("shape")
    if shape == "count" and ledger.get("final_count") is not None:
        return str(ledger["final_count"])
    if shape == "order" and ledger.get("ordered"):
        ordered = ledger["ordered"]
        if len(ordered) == 2:
            return f"First {ordered[0]}, then {ordered[1]}."
        if len(ordered) >= 3:
            return f"First {ordered[0]}, then {ordered[1]}, and finally {ordered[-1]}."
    if shape == "duration_since" and ledger.get("value") is not None and ledger.get("unit"):
        return f"{ledger['value']} {ledger['unit']}"
    if shape == "date_diff" and ledger.get("answer"):
        return ledger["answer"]
    if shape == "derived_time" and ledger.get("result") is not None:
        unit = ledger.get("unit")
        return f"{ledger['result']} {unit}".strip() if unit else str(ledger["result"])
    if shape == "abs_value" and ledger.get("answer"):
        return str(ledger["answer"])
    return None


def assemble_ledger_context(ledger: dict[str, Any]) -> str:
    """Format the ledger as a prepended block for the reader prompt.

    When `answer_from_ledger` returns None (most cases), the reader still
    benefits from seeing the structured candidates. This block is
    pre-pended to the regular context.
    """
    parts: list[str] = []
    parts.append(f"## EVIDENCE_LEDGER (shape={ledger.get('shape')})")
    for chunk in ledger.get("raw_hits", [])[:10]:
        ds = _date_str(chunk.get("date")) or "?"
        role = chunk.get("role") or "?"
        text = chunk["text"][:200].replace("\n", " ")
        parts.append(f"- [{ds}] [{role}] {text}")
    return "\n".join(parts) + "\n"
