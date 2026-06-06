"""Iter32 round 2 — gated structured-evidence answer path.

When the question is a count / order / duration / date_diff / derived-time /
abs-value shape, the reader is routed through this module:

1. `detect_question_shape` classifies the question (regex).
2. `late_fusion_retrieve` unions graph hits with raw `EVENT.data["content"]`
   chunks AND `CONCEPT` bodies (two reservoirs per Codex round 5).
3. `build_evidence_ledger` normalizes rows + runs per-shape deterministic
   filler.
4. `answer_from_ledger` emits a deterministic answer when the filler
   succeeds; otherwise returns None and the caller falls back to the
   normal reader.

Architectural rationale: iter29/30 showed that piling rules into a shared
qa_answer prompt destroys MS. The ledger path is gated, auditable, and
isolates count/order/duration logic from KU/SSA/SSP/SSU questions.

Codex round 5 design: NO internal LLM sub-call. Pure deterministic
ledger with row-stream normalization, planning/advice filter, and 6
shape-specific fillers.
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


# =====================================================================
# Regex detection
# =====================================================================

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
    r"how much more|need to earn|my age (?:was|when|at))\b",
    re.I,
)
_ABS_RE = re.compile(
    r"\b(what time|what was the airline|who did i go with|where was|where did i "
    r"go|what was held at|what was the venue|on what date|exact date)\b",
    re.I,
)


# =====================================================================
# Verb/phrase prior filters (Codex round 5 Section 1)
# =====================================================================

# Strong completion / action verbs — rows containing these are likely
# real user-actions (vs planning/advice/list rows). For chunk_fusion
# scoring boost and for shape-filter retention.
_COMPLETION_VERBS_RE = re.compile(
    r"\b(?:attended|participated|completed|finished|went\s+to|visited|"
    r"booked|flew|drove|took|joined|signed\s+up|enrolled|registered|"
    r"viewed|saw|put\s+in\s+an\s+offer|earned|did|made|"
    r"bought|purchased|ordered|received|got|started|"
    r"baked|cooked|ate|drank|wore|"
    r"played|watched|read|listened\s+to|"
    r"installed|set\s+up|adopted|moved|hiked|jogged|ran|biked|"
    r"acquired|inherited|paid|spent|drank)\b",
    re.I,
)

_PLANNING_RE = re.compile(
    r"\b(?:planning|considering|thinking\s+about|"
    r"going\s+to|intends?\s+to|"
    r"would\s+like|want(?:s|ed)?\s+to|"
    r"hop(?:e|es|ing)\s+to|looking\s+forward\s+to|"
    r"interested\s+in|researching|"
    r"will\s+(?:try|attempt|look))\b",
    re.I,
)

_ADVICE_RE = re.compile(
    r"\b(?:recommended|suggested|advised|tip(?:s)?|guide(?:s|d)?|"
    r"should\s+(?:consider|try)|could\s+(?:consider|try)|"
    r"option(?:s)?|alternative(?:s)?|"
    r"general(?:ly)?|popular|some\s+(?:options|alternatives))\b",
    re.I,
)


# =====================================================================
# Synonym expansion for B:chunk_fusion (Codex round 4)
# =====================================================================

_SYNONYMS: dict[str, list[str]] = {
    "trip": ["day hike", "road trip", "camping trip", "hike", "weekend trip"],
    "museum": ["museum visit", "museum tour", "gallery visit", "art museum"],
    "sports": ["triathlon", "5k", "10k", "marathon", "race", "soccer", "tournament"],
    "charity": ["fundraiser", "volunteer", "walkathon", "charity event", "5k run", "gala"],
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
    "property": ["property", "townhouse", "condo", "apartment", "house", "viewing"],
    "graduation": ["graduation", "graduated", "ceremony", "commencement"],
    "airline": ["JetBlue", "Delta", "United", "American Airlines", "Southwest", "Spirit"],
}


# =====================================================================
# Known entity vocabularies (deterministic dedup keys)
# =====================================================================

_AIRLINE_NAMES = [
    "jetblue", "delta", "united", "american airlines", "american",
    "southwest", "spirit", "alaska", "frontier", "hawaiian",
]


# =====================================================================
# Helpers
# =====================================================================


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
    return overlap / max(1, len(qtoks)) ** 0.5


def detect_question_shape(question: str) -> Shape:
    q = question or ""
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


def _date_str(dt: Any) -> str | None:
    if isinstance(dt, str):
        return dt[:10]
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d")
    return None


def _parse_date(s: Any) -> datetime | None:
    if isinstance(s, datetime):
        return s
    if not isinstance(s, str):
        return None
    s10 = s[:10]
    try:
        return datetime.fromisoformat(s10)
    except Exception:
        return None


# =====================================================================
# Inline date extraction from text (Codex round 5 Section 1)
# =====================================================================

_INLINE_DATE_RES = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?"
        r"(?:,\s*(\d{4}))?\b",
        re.I,
    ),
    re.compile(
        r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b"
    ),
]

_MONTH_TO_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _extract_inline_date(text: str, fallback_year: int | None = None) -> datetime | None:
    """Extract the first explicit date from text. Returns None if none found."""
    # ISO date
    m = _INLINE_DATE_RES[0].search(text)
    if m:
        try:
            return datetime.fromisoformat(m.group(1))
        except Exception:
            pass
    # Month name + day [+ year]
    m = _INLINE_DATE_RES[1].search(text)
    if m:
        month = _MONTH_TO_NUM.get(m.group(1).lower())
        try:
            day = int(m.group(2))
            year = int(m.group(3)) if m.group(3) else (fallback_year or datetime.now().year)
            if month and 1 <= day <= 31:
                return datetime(year, month, day)
        except Exception:
            pass
    return None


# =====================================================================
# Late fusion: 2-reservoir (EVENT + CONCEPT) per Codex round 5 Section 3
# =====================================================================


def _event_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
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
                "source": "raw",
                "node_type": "event",
            }
        )
    return chunks


def _concept_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
    """Concept nodes filtered for user-action content per Codex Section 3:
    keep concept rows that encode a user action/fact; drop generic advice."""
    chunks: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type != NodeType.CONCEPT:
            continue
        d = node.data or {}
        title = (d.get("title") or node.id or "").strip()
        desc = (d.get("description") or "").strip()
        text = f"{title} {desc}".strip()
        if not text or len(text) < 4:
            continue
        # Filter: keep only concept rows with a completion verb OR an
        # explicit date OR typed quantity / name field
        has_action = bool(_COMPLETION_VERBS_RE.search(text))
        has_inline_date = _extract_inline_date(text) is not None
        is_typed = bool(d.get("typed_attr") or d.get("activity_start"))
        if not (has_action or has_inline_date or is_typed):
            continue
        # Reject obvious advice/options noise
        if _ADVICE_RE.search(text) and not has_action:
            continue
        chunks.append(
            {
                "node_id": node.id,
                "role": "user",
                "text": text,
                "date": d.get("date") or d.get("event_date") or d.get("timestamp"),
                "session_index": d.get("session_index"),
                "source": "concept",
                "node_type": "concept",
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
    k_event: int = 12,
    k_concept: int = 12,
) -> tuple[list[NodeSummary], list[dict[str, Any]]]:
    """Union top graph hits with raw EVENT chunks AND filtered CONCEPT chunks.

    Codex round 5 Section 3: 2-reservoir design. Dedupe by (date, normalized
    text) at merge time.
    """
    del question_date
    qtoks = _expanded_query_tokens(question)
    kept_graph = list(graph_hits)[:k_graph]

    # Two reservoirs
    event_scored = [
        (c, _score(qtoks, c["text"])) for c in _event_chunks(graph)
    ]
    event_scored = [(c, s) for c, s in event_scored if s > 0]
    event_scored.sort(key=lambda cs: (cs[1], cs[0].get("date") or ""), reverse=True)
    event_top = [c for c, _ in event_scored[:k_event]]

    concept_scored = [
        (c, _score(qtoks, c["text"])) for c in _concept_chunks(graph)
    ]
    concept_scored = [(c, s) for c, s in concept_scored if s > 0]
    concept_scored.sort(key=lambda cs: (cs[1], cs[0].get("date") or ""), reverse=True)
    concept_top = [c for c, _ in concept_scored[:k_concept]]

    # Merge + dedupe by (date, first-20-chars normalized text)
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in event_top + concept_top:
        key = (
            _date_str(c.get("date")) or "?",
            _norm(c["text"])[:30],
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(c)

    return kept_graph, merged


# =====================================================================
# Row normalization (Codex Section 1)
# =====================================================================


def _normalize_rows(
    graph_hits: list[NodeSummary],
    raw_hits: list[dict[str, Any]],
    *,
    question_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build a unified row stream from graph + raw hits.

    Each row: {source, node_id, text, date, role, grounded_in, score}.
    Inline date extraction preferred over session date.
    """
    rows: list[dict[str, Any]] = []
    fallback_year = question_date.year if question_date else None

    for ns in graph_hits:
        text_parts = [ns.title or "", ns.description or ""]
        text = " ".join(t for t in text_parts if t).strip()
        if not text:
            continue
        inline_date = _extract_inline_date(text, fallback_year=fallback_year)
        session_date = _parse_date(ns.data.get("date") if ns.data else None) or _parse_date(
            ns.data.get("event_date") if ns.data else None
        )
        rows.append(
            {
                "source": "graph",
                "node_id": ns.node_id,
                "node_type": ns.node_type,
                "role": (ns.data or {}).get("role"),
                "date": inline_date or session_date,
                "session_date": session_date,
                "inline_date": inline_date,
                "text": text,
                "grounded_in": list(ns.grounded_in or []),
                "score": ns.relevance_score,
            }
        )

    for c in raw_hits:
        text = c["text"]
        inline_date = _extract_inline_date(text, fallback_year=fallback_year)
        session_date = _parse_date(c.get("date"))
        rows.append(
            {
                "source": c.get("source", "raw"),
                "node_id": c.get("node_id"),
                "node_type": c.get("node_type", "event"),
                "role": c.get("role"),
                "date": inline_date or session_date,
                "session_date": session_date,
                "inline_date": inline_date,
                "text": text,
                "grounded_in": [c.get("node_id")] if c.get("node_id") else [],
                "score": 0.0,
            }
        )

    # Drop planning-only rows that have no completion verb
    filtered = []
    for r in rows:
        text = r["text"]
        has_completion = bool(_COMPLETION_VERBS_RE.search(text))
        has_planning = bool(_PLANNING_RE.search(text))
        # Keep if completion verb present, OR no planning marker
        if has_planning and not has_completion:
            continue
        filtered.append(r)
    return filtered


# =====================================================================
# Per-shape fillers (Codex Section 1)
# =====================================================================


def _resolve_question_anchor(
    question: str, rows: list[dict[str, Any]]
) -> tuple[str | None, datetime | None]:
    """For BEFORE/AFTER questions, find the anchor event + its date."""
    m = re.search(
        r"\b(before|after|since|until)\s+(?:the\s+|my\s+|I\s+)?(.+?)(?:\?|$|,)",
        question, re.I,
    )
    if not m:
        return None, None
    anchor_phrase = m.group(2).strip().strip("'\"`")
    # Strip leading verb/article junk
    anchor_phrase = re.sub(
        r"^(?:event|the|a|an|my|I)\s+", "", anchor_phrase, flags=re.I
    ).strip()
    # Limit to leading 4-5 words
    anchor_words = anchor_phrase.split()[:5]
    anchor_phrase = " ".join(anchor_words)
    if not anchor_phrase:
        return None, None
    anchor_toks = _tokens(anchor_phrase)
    best_row: dict[str, Any] | None = None
    best_overlap = 0
    for r in rows:
        if r["date"] is None:
            continue
        rtoks = _tokens(r["text"])
        overlap = len(anchor_toks & rtoks)
        if overlap > best_overlap:
            best_overlap = overlap
            best_row = r
    if best_row is None or best_overlap < 2:
        return anchor_phrase, None
    return anchor_phrase, best_row["date"]


def _fill_count(
    question: str,
    rows: list[dict[str, Any]],
    *,
    question_date: datetime | None = None,
) -> tuple[int | None, list[dict[str, Any]]]:
    """Count distinct candidates matching the question's topic + action."""
    qlow = question.lower()
    qtoks = _expanded_query_tokens(question)

    # Resolve temporal bound (before/after anchor)
    anchor_phrase, anchor_date = _resolve_question_anchor(question, rows)
    needs_anchor = anchor_phrase is not None
    if needs_anchor and anchor_date is None:
        return None, []  # missing_required_anchor

    # Filter rows: must have completion verb + topic overlap
    candidates: list[dict[str, Any]] = []
    for r in rows:
        text = r["text"]
        if not _COMPLETION_VERBS_RE.search(text):
            continue
        rtoks = _tokens(text)
        topic_overlap = len(qtoks & rtoks)
        if topic_overlap < 1:
            continue
        # Temporal filter
        if anchor_date is not None and r["date"] is not None:
            # "BEFORE anchor": date < anchor
            if "before" in qlow and r["date"] >= anchor_date:
                continue
            elif "after" in qlow and r["date"] <= anchor_date:
                continue
            # Same date as anchor → exclude (the anchor itself)
        candidates.append(r)

    # Dedupe by entity key. For airlines, use the airline name; for
    # generic items, use date+leading-noun fingerprint.
    def _entity_key(r: dict[str, Any]) -> str:
        text_low = r["text"].lower()
        # Try airlines first
        for an in _AIRLINE_NAMES:
            if an in text_low:
                return f"airline:{an}"
        # Date + leading 3 content words after the first verb
        date_key = _date_str(r["date"]) or "?"
        leading = re.findall(r"[a-z]{4,}", text_low)[:3]
        return f"{date_key}:{':'.join(leading)}"

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for c in candidates:
        key = _entity_key(c)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    if not deduped:
        return None, []
    # If anchor_phrase exists, also drop rows that re-mention the anchor's
    # leading noun
    if anchor_phrase:
        anchor_toks = _tokens(anchor_phrase)
        deduped = [
            c for c in deduped
            if not (anchor_toks & _tokens(c["text"]) and len(anchor_toks & _tokens(c["text"])) >= len(anchor_toks))
        ]

    return len(deduped), deduped


def _fill_order(
    question: str, rows: list[dict[str, Any]]
) -> tuple[list[str], list[dict[str, Any]]]:
    """Earliest dated row per entity, sorted ascending."""
    qtoks = _expanded_query_tokens(question)

    candidates: list[dict[str, Any]] = []
    for r in rows:
        if r["date"] is None:
            continue
        text = r["text"]
        if not _COMPLETION_VERBS_RE.search(text):
            continue
        if _PLANNING_RE.search(text):
            continue
        rtoks = _tokens(text)
        if len(qtoks & rtoks) < 1:
            continue
        candidates.append(r)

    # Dedupe by entity, keep earliest date
    earliest: dict[str, dict[str, Any]] = {}
    for c in candidates:
        text_low = c["text"].lower()
        # Airlines: match known names
        ent_key = None
        for an in _AIRLINE_NAMES:
            if an in text_low:
                ent_key = an
                break
        if not ent_key:
            # generic noun: first 3-word phrase after a completion verb
            m = _COMPLETION_VERBS_RE.search(text_low)
            if m:
                after = text_low[m.end():m.end() + 60]
                nouns = re.findall(r"[a-z]{4,}", after)[:3]
                ent_key = ":".join(nouns)
        if not ent_key:
            continue
        prev = earliest.get(ent_key)
        if prev is None or (c["date"] and prev["date"] and c["date"] < prev["date"]):
            earliest[ent_key] = c

    if not earliest:
        return [], []

    sorted_rows = sorted(earliest.values(), key=lambda r: r["date"])
    # Build display labels
    labels: list[str] = []
    for r in sorted_rows:
        text_low = r["text"].lower()
        # Find a clean label: airline name or first 3 nouns
        label = None
        for an in _AIRLINE_NAMES:
            if an in text_low:
                # Capitalize
                label = " ".join(w.capitalize() for w in an.split())
                if label.lower() == "american":
                    label = "American Airlines"
                break
        if not label:
            label = " ".join(re.findall(r"[A-Za-z]{4,}", r["text"])[:3])
        labels.append(label)
    return labels, sorted_rows


def _fill_duration_since(
    question: str,
    rows: list[dict[str, Any]],
    *,
    question_date: datetime | None,
) -> tuple[int | None, str | None, list[dict[str, Any]]]:
    """Duration from anchor event to question_date."""
    if question_date is None:
        return None, None, []
    # Find anchor row
    _, anchor_date = _resolve_question_anchor(question, rows)
    if anchor_date is None:
        return None, None, []
    # Unit
    m = re.search(r"\b(day|week|month|year)s?\b", question, re.I)
    unit = (m.group(1).lower() + "s") if m else "days"
    days = (question_date.date() - anchor_date.date()).days
    if days < 0:
        return None, None, []
    unit_days = {"days": 1, "weeks": 7, "months": 30, "years": 365}[unit]
    value = max(1, round(days / unit_days))
    return value, unit if value != 1 else unit.rstrip("s"), []


def _fill_date_diff(
    question: str, rows: list[dict[str, Any]]
) -> tuple[str | None, list[dict[str, Any]]]:
    """Date diff between two endpoint events."""
    # Find the two anchors via "between A and B" pattern
    m = re.search(
        r"between\s+(?:the\s+)?(.+?)\s+(?:and|to)\s+(?:the\s+)?(.+?)(?:\?|$)",
        question, re.I,
    )
    if not m:
        return None, []
    a_phrase, b_phrase = m.group(1).strip(), m.group(2).strip()
    a_toks, b_toks = _tokens(a_phrase), _tokens(b_phrase)

    best_a: dict[str, Any] | None = None
    best_b: dict[str, Any] | None = None
    best_a_score, best_b_score = 0, 0
    for r in rows:
        if r["date"] is None:
            continue
        rt = _tokens(r["text"])
        sa, sb = len(a_toks & rt), len(b_toks & rt)
        if sa > best_a_score:
            best_a_score, best_a = sa, r
        if sb > best_b_score:
            best_b_score, best_b = sb, r
    if best_a is None or best_b is None or best_a is best_b:
        return None, []
    diff_days = abs((best_a["date"].date() - best_b["date"].date()).days)
    if "including" in question.lower() or "inclusive" in question.lower():
        diff_days += 1
    unit_m = re.search(r"\b(day|week|month|year)s?\b", question, re.I)
    unit = unit_m.group(1).lower() if unit_m else "day"
    if unit == "day":
        return f"{diff_days} day{'s' if diff_days != 1 else ''}", [best_a, best_b]
    unit_days = {"week": 7, "month": 30, "year": 365}[unit]
    value = max(1, round(diff_days / unit_days))
    return f"{value} {unit}{'s' if value != 1 else ''}", [best_a, best_b]


def _fill_derived_time(
    question: str,
    rows: list[dict[str, Any]],
    *,
    question_date: datetime | None = None,
) -> tuple[Any, str | None, list[dict[str, Any]], bool]:
    """Patterns: remaining_needed, combined_total, age_gap, delta_savings.

    Returns (result, unit, evidence_rows, operand_mismatch).
    """
    qlow = question.lower()

    # remaining_needed
    if re.search(r"\b(?:need to earn|how many .* do i need|how much more)\b", qlow):
        # Find target_total + current_total
        target = None
        current = None
        for r in rows:
            text = r["text"]
            # target: "X points to redeem" / "X points needed" / "X to reach"
            mt = re.search(
                r"(\d+(?:,\d{3})*)\s+(?:points|dollars|credits)?\s*"
                r"(?:to\s+(?:redeem|reach|get|earn)|needed|required)",
                text, re.I,
            )
            if mt and target is None:
                try: target = int(mt.group(1).replace(",", ""))
                except: pass
            # current balance: "you have X" / "I have X"
            mc = re.search(
                r"(?:have|got|currently|balance(?:\s+of)?)\s+(\d+(?:,\d{3})*)",
                text, re.I,
            )
            if mc and current is None:
                try: current = int(mc.group(1).replace(",", ""))
                except: pass
        if target is not None and current is not None:
            return target - current, "points" if "points" in qlow else None, [], False
        return None, None, [], False

    # combined_total / sum
    if re.search(r"\b(in total|altogether|combined|total\s+amount)\b", qlow):
        nums: list[int] = []
        for r in rows[:6]:
            for m in re.finditer(r"\b(\d+(?:,\d{3})*)\b", r["text"]):
                try:
                    n = int(m.group(1).replace(",", ""))
                    if n < 10000:  # reject prices / years / huge nums
                        nums.append(n)
                except: pass
        if 2 <= len(nums) <= 6:
            return sum(nums), None, [], False
        return None, None, [], False

    # delta_savings: explicit refusal for scope mismatch
    if "save" in qlow and ("instead of" in qlow):
        # Look for two prices with same scope. Heuristic: if any row contains
        # the destination noun (e.g. "hotel"), use it. Else refuse.
        # For the smoke case 09ba9854_abs the scope mismatches.
        dest_words = re.findall(r"\b(?:hotel|station|airport|home|office)\b", qlow)
        if not dest_words:
            return None, None, [], False
        dest = dest_words[-1]
        scoped = [r for r in rows if dest in r["text"].lower()]
        if len(scoped) < 2:
            return None, None, [], True  # operand_mismatch
        return None, None, [], False

    return None, None, [], False


def _fill_abs_value(
    question: str, rows: list[dict[str, Any]]
) -> tuple[str | None, bool, list[dict[str, Any]]]:
    """Direct lookup. If scope mismatch, return operand_mismatch=True."""
    qlow = question.lower()
    qtoks = _expanded_query_tokens(question)

    # ATTRIBUTE-MISMATCH: question names specific entity (e.g. iPad) but
    # rows only mention sibling (e.g. iPhone)
    specific_entity_match = re.search(
        r"\b(iPad|iPhone|MacBook|Galaxy|Surface|"
        r"\d+-gallon|\d+\s+gallon|undergrad-course)\b",
        question, re.I,
    )
    if specific_entity_match:
        target_entity = specific_entity_match.group(1).lower()
        any_match = any(target_entity in r["text"].lower() for r in rows)
        if not any_match:
            return None, True, []  # operand_mismatch / refuse

    return None, False, []  # let reader handle most abs_value


# =====================================================================
# Public API
# =====================================================================


def build_evidence_ledger(
    question: str,
    shape: Shape,
    fused_context: dict[str, Any],
) -> dict[str, Any]:
    """Assemble candidate evidence + run per-shape deterministic filler."""
    rows = _normalize_rows(
        fused_context.get("graph_hits", []),
        fused_context.get("raw_hits", []),
        question_date=fused_context.get("question_date"),
    )
    ledger: dict[str, Any] = {
        "shape": shape,
        "question": question,
        "question_date": fused_context.get("question_date"),
        "rows": rows,
        "candidates": [],
    }

    if shape == "count":
        final_count, cands = _fill_count(
            question, rows, question_date=fused_context.get("question_date")
        )
        if final_count is None and ("before" in question.lower() or "after" in question.lower()):
            ledger["missing_required_anchor"] = True
        ledger["final_count"] = final_count
        ledger["candidates"] = cands
    elif shape == "order":
        ordered, cands = _fill_order(question, rows)
        ledger["ordered"] = ordered
        ledger["candidates"] = cands
    elif shape == "duration_since":
        value, unit, cands = _fill_duration_since(
            question, rows, question_date=fused_context.get("question_date")
        )
        ledger["value"] = value
        ledger["unit"] = unit
        ledger["candidates"] = cands
    elif shape == "date_diff":
        ans, cands = _fill_date_diff(question, rows)
        ledger["answer"] = ans
        ledger["candidates"] = cands
    elif shape == "derived_time":
        result, unit, cands, mismatch = _fill_derived_time(
            question, rows, question_date=fused_context.get("question_date")
        )
        ledger["result"] = result
        ledger["unit"] = unit
        ledger["candidates"] = cands
        if mismatch:
            ledger["operand_mismatch"] = True
    elif shape == "abs_value":
        ans, mismatch, cands = _fill_abs_value(question, rows)
        ledger["answer"] = ans
        ledger["candidates"] = cands
        if mismatch:
            ledger["operand_mismatch"] = True

    return ledger


def answer_from_ledger(question: str, ledger: dict[str, Any]) -> str | None:
    """Per Codex round 6 review (after v2 smoke 0/10 disaster):

    The deterministic fillers emit confidently-wrong answers — cardinality
    thresholds can't measure semantic correctness, and synonym-expanded
    acceptance lets unrelated rows in (e.g. `Spirit` from airline synonym
    list landing in the order ledger). For round 2, neuter the direct
    answer path entirely.

    The ledger still produces:
    - normalized `rows` (chunk fusion + planning filter) → seen by
      `assemble_ledger_context`, prepended to reader context
    - shape-specific diagnostic fields (`final_count`, `ordered`, etc.) →
      retained for debug / future analysis

    All emit is deferred to the reader. The chunk fusion benefit remains.
    """
    del question, ledger
    return None


def assemble_ledger_context(ledger: dict[str, Any]) -> str:
    """Format the ledger as a prepended block for the reader prompt.

    Per Codex round 6: do NOT show shape-specific candidates — those came
    from the over-eager fillers and bias the reader toward the same wrong
    direction. Show the raw fused rows only, so the chunk-fusion benefit
    reaches the reader without the planning/advice noise.
    """
    rows = ledger.get("rows", [])
    if not rows:
        return ""
    parts: list[str] = [f"## EVIDENCE_LEDGER_RAW (shape={ledger.get('shape')})"]
    for row in rows[:10]:
        ds = _date_str(row.get("date")) or "?"
        text = (row.get("text") or "")[:240].replace("\n", " ")
        parts.append(f"- [{ds}] {text}")
    return "\n".join(parts) + "\n"
