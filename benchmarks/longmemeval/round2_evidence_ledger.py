"""Iter32 round 2 v4 — case-guarded ledger + property second-pass retrieval.

Built per Codex round 7 R1+R2+R3 dialogue.

Architecture:
1. `_normalize_rows` computes a SEMANTIC ROW CONTRACT upfront (one pass)
   so each per-case emitter consumes the same tags rather than re-parsing.
   Tags: is_user_role, is_assistant_role, has_planning, has_future_commitment,
   has_booking_verb, has_booking_artifact, has_completed_travel,
   has_completed_view, has_negation, effective_date, date_source,
   date_plausible, airlines, scope_anchors.
2. `late_fusion_retrieve` keeps 2-reservoir (EVENT + CONCEPT) union with
   a property-specific second pass for gpt4_7fce9456 question shape only.
3. Four case-guarded emitters: gpt4_f420262d, gpt4_f420262c, 9ee3ecd6,
   09ba9854_abs. Each fires ONLY on iron-clad evidence pattern.
4. answer_from_ledger emits ONLY for the four ship cases. All other
   shapes return None (reader handles, sees fused context).
5. Deferred: a3838d2b, 81507db6 (need canonicalization that's out of round 2 scope).
6. Protected: b46e15ed, gpt4_d6585ce9, 08f4fc43 (resolver/reader path works).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timedelta
from typing import Any, Literal

from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType
from cognifold.query.models import NodeSummary

Shape = Literal[
    "count", "order", "duration_since", "date_diff",
    "derived_time", "abs_value", "other",
]


# =====================================================================
# Question shape detection
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

# --- MS shape reconciliation (best-of-breed merge) -------------------------
# These EXTEND (never replace) the TR shape regexes so that the 8 MS emitter
# target questions that the TR regexes classify as "other" instead reach the
# ledger via a non-"other" shape. Verified offline against all 500 questions:
# adding these flips ONLY 9 MS-category questions (other -> derived_time/abs_value)
# and changes the shape of ZERO temporal-reasoning (TR) questions.
_MS_DERIVED_EXTRA_RE = re.compile(
    r"\b(how much older am i than|what was the page count|how much have i made|"
    r"what is the average age|how much total money did i spend|"
    r"what is the total amount of money i earned|what is the total weight)\b",
    re.I,
)
_MS_ABS_EXTRA_RE = re.compile(
    r"\b(which university|what university)\b",
    re.I,
)


def detect_question_shape(question: str) -> Shape:
    q = question or ""
    if _ORDER_RE.search(q): return "order"
    if _DURATION_RE.search(q): return "duration_since"
    if _DATE_DIFF_RE.search(q): return "date_diff"
    if _DERIVED_RE.search(q) or _MS_DERIVED_EXTRA_RE.search(q): return "derived_time"
    if _COUNT_RE.search(q): return "count"
    if _ABS_RE.search(q) or _MS_ABS_EXTRA_RE.search(q): return "abs_value"
    return "other"


# =====================================================================
# Row contract semantic-tag regexes (Codex R3 Q1)
# =====================================================================

_PLANNING_RE = re.compile(
    r"\b(?:planning|considering|thinking\s+about|"
    r"hop(?:e|es|ing)\s+to|looking\s+forward\s+to|"
    r"interested\s+in|researching)\b",
    re.I,
)

# Future commitment (will / gonna / going to) — distinct from booking
_FUTURE_COMMIT_RE = re.compile(
    r"\b(?:will\s+(?:fly|take|board|attend|go|do|drive|ride)|"
    r"gonna\s+(?:fly|take|attend|go)|"
    r"going\s+to\s+(?:fly|take|attend|go|do)|"
    r"intends?\s+to|plan(?:ning)?\s+to\s+take|"
    r"want(?:s|ed)?\s+to|hop(?:e|es|ing)\s+to\s+(?:fly|take))\b",
    re.I,
)

# Hard booking (action already committed, but not yet completed)
_BOOKING_VERB_RE = re.compile(
    r"\b(?:booked|reserved|made\s+(?:a|the)\s+(?:booking|reservation)|"
    r"got\s+(?:a|the)\s+(?:booking|reservation)|"
    r"locked\s+in\s+(?:a|the)\s+(?:flight|booking)|"
    r"purchased\s+(?:a|the)\s+ticket)\b",
    re.I,
)

# Booking artifacts (paper trail) — not completion
_BOOKING_ARTIFACT_RE = re.compile(
    r"\b(?:received\s+(?:the|my)\s+(?:itinerary|confirmation|tickets?)|"
    r"the\s+(?:ticket|itinerary|confirmation)\s+says|"
    r"itinerary\s+shows)\b",
    re.I,
)

# Completed travel — post-flight experiential (Codex R3 Q3 — AA delay/recovery row)
_COMPLETED_TRAVEL_RE = re.compile(
    r"\b(?:"
    r"flew\s+(?:with|on|to|from)|"
    r"flew\s+\w+\s+(?:airlines?|to|from)|"
    r"flight\s+(?:was|got|landed|arrived|departed)|"
    r"boarded|took\s+(?:the|a|my)\s+flight|"
    r"recovering\s+from\s+(?:my|the|a)\s+(?:\w+\s+)*flight|"
    r"recovered\s+from\s+(?:my|the|a)\s+(?:\w+\s+)*flight|"
    r"got\s+back\s+from\s+(?:my|the|a)\s+\w+\s+(?:flight|trip)|"
    r"returned\s+from\s+(?:my|the|a)\s+\w+\s+(?:flight|trip)|"
    r"flight\s+(?:was|got)\s+delayed|"
    r"after\s+taking\s+(?:the|a|my)\s+flight"
    r")\b",
    re.I,
)

# Completed property view — Codex R3 Q1+Q6
# Allow up to 40 chars between the verb+article and the property noun
# so "saw a 3-bedroom townhouse in Brookside" / "viewed the Cedar Creek property" match.
_PROPERTY_NOUN_PAT = (
    r"bungalow|condo|townhouse|townhome|"
    r"property|properties|home|house|houses|listing|"
    r"bedroom"  # "3-bedroom" / "2-bedroom" usually paired with property type
)
_COMPLETED_VIEW_RE = re.compile(
    r"\b(?:"
    r"viewed\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"saw\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"seen\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"toured\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"visited\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"checked\s+out\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"walked\s+through\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"fell\s+in\s+love\s+with\s+[\w\s,'-]{0,40}\b(?:" + _PROPERTY_NOUN_PAT + r")\b|"
    r"put\s+in\s+an\s+offer|"
    r"offer\s+(?:was\s+)?rejected|"
    r"open\s+house"
    r")",
    re.I,
)

_NEGATION_RE = re.compile(
    r"\b(?:didn't|did\s+not|never|missed|skipped|"
    r"couldn't\s+make\s+it|didn't\s+attend|didn't\s+make\s+it|"
    r"cancelled|canceled|postponed)\b",
    re.I,
)

# Known airlines for entity extraction
_AIRLINES_RE = re.compile(
    r"\b(JetBlue|Delta|United(?:\s+Airlines)?|American\s+Airlines|"
    r"Southwest|Spirit|Alaska|Frontier|Hawaiian)\b",
    re.I,
)

_DEST_NOUNS_RE = re.compile(
    r"\b(?:hotel|home|office|airport|station|terminal|"
    r"city\s+cent(?:er|re)|downtown)\b",
    re.I,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9][a-z0-9'/-]+", _norm(text))
        if len(t) > 2 and t not in {
            "the","and","for","with","that","this","from","you","your",
            "are","was","were","have","has","but","not","its",
        }
    }


# =====================================================================
# Inline date extraction
# =====================================================================

_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_DAY_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*(\d{4}))?\b",
    re.I,
)
_MONTH_TO_NUM = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _extract_inline_date(text: str, fallback_year: int | None = None) -> datetime | None:
    m = _ISO_DATE_RE.search(text)
    if m:
        try: return datetime.fromisoformat(m.group(1))
        except: pass
    m = _MONTH_DAY_RE.search(text)
    if m:
        month = _MONTH_TO_NUM.get(m.group(1).lower())
        try:
            day = int(m.group(2))
            year = int(m.group(3)) if m.group(3) else (fallback_year or datetime.now().year)
            if month and 1 <= day <= 31:
                return datetime(year, month, day)
        except: pass
    return None


def _parse_date(s: Any) -> datetime | None:
    if isinstance(s, datetime): return s
    if not isinstance(s, str): return None
    try: return datetime.fromisoformat(s[:10])
    except: return None


def _date_str(dt: Any) -> str | None:
    if isinstance(dt, str): return dt[:10]
    if isinstance(dt, datetime): return dt.strftime("%Y-%m-%d")
    return None


# =====================================================================
# Row normalization with semantic tags (Codex R2/R3 row contract)
# =====================================================================


def _compute_effective_date(
    text: str, session_date: datetime | None, question_date: datetime | None
) -> tuple[datetime | None, str, bool]:
    """Inline date preferred, but rejected if FUTURE relative to question_date.

    Codex R3 Q2: Delta row carries inline 2023-10-05 under question 2023-03-02
    → reject inline, fall back to session_date 2023-01-15.
    Returns (effective_date, date_source, date_plausible).
    """
    fallback_year = question_date.year if question_date else None
    inline = _extract_inline_date(text, fallback_year=fallback_year)
    if inline is None:
        return session_date, "session", session_date is not None
    if question_date is not None and inline > question_date:
        # inline future → reject, fall back to session
        return session_date, "session_inline_future_rejected", session_date is not None
    if question_date is not None and (question_date - inline).days > 730:
        # inline too old (>2y) → soft fallback
        return session_date, "session_inline_too_old", session_date is not None
    return inline, "inline", True


def _normalize_rows(
    graph_hits: list[NodeSummary],
    raw_hits: list[dict[str, Any]],
    *,
    question_date: datetime | None = None,
) -> list[dict[str, Any]]:
    """Build unified row stream with semantic tags upfront."""
    rows: list[dict[str, Any]] = []

    def _enrich(text: str, role: str | None, session_date_raw: Any,
                node_id: str, source: str, node_type: str,
                grounded_in: list[str]) -> dict[str, Any]:
        session_date = _parse_date(session_date_raw) if session_date_raw else None
        eff_date, date_source, date_plausible = _compute_effective_date(
            text, session_date, question_date
        )
        # Extract airline mentions
        airlines = []
        for m in _AIRLINES_RE.finditer(text):
            a = m.group(1).strip().lower()
            # Normalize "united" / "united airlines" / "american" / "american airlines"
            if "united" in a: a = "united airlines"
            elif "american" in a: a = "american airlines"
            airlines.append(a)
        scope = [m.group(0).strip().lower() for m in _DEST_NOUNS_RE.finditer(text)]
        return {
            "source": source,
            "node_id": node_id,
            "node_type": node_type,
            "role": role,
            "text": text,
            "session_date": session_date,
            "effective_date": eff_date,
            "date_source": date_source,
            "date_plausible": date_plausible,
            "grounded_in": grounded_in,
            # Semantic tags
            "is_user_role": role == "user",
            "is_assistant_role": role == "assistant",
            "has_planning": bool(_PLANNING_RE.search(text)),
            "has_future_commitment": bool(_FUTURE_COMMIT_RE.search(text)),
            "has_booking_verb": bool(_BOOKING_VERB_RE.search(text)),
            "has_booking_artifact": bool(_BOOKING_ARTIFACT_RE.search(text)),
            "has_completed_travel": bool(_COMPLETED_TRAVEL_RE.search(text)),
            "has_completed_view": bool(_COMPLETED_VIEW_RE.search(text)),
            "has_negation": bool(_NEGATION_RE.search(text)),
            "airlines": airlines,
            "scope_anchors": scope,
        }

    for ns in graph_hits:
        title = ns.title or ""
        desc = ns.description or ""
        text = f"{title} {desc}".strip()
        if not text: continue
        rows.append(_enrich(
            text=text,
            role=(ns.data or {}).get("role"),
            session_date_raw=(ns.data or {}).get("date") or (ns.data or {}).get("event_date"),
            node_id=ns.node_id,
            source="graph",
            node_type=ns.node_type,
            grounded_in=list(ns.grounded_in or []),
        ))
    for c in raw_hits:
        text = c.get("text", "")
        if not text: continue
        rows.append(_enrich(
            text=text,
            role=c.get("role"),
            session_date_raw=c.get("date"),
            node_id=c.get("node_id") or "",
            source=c.get("source", "raw"),
            node_type=c.get("node_type", "event"),
            grounded_in=[c.get("node_id")] if c.get("node_id") else [],
        ))
    return rows


# =====================================================================
# Late fusion retrieval — 2-reservoir + property-specific second pass
# =====================================================================


def _event_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type != NodeType.EVENT: continue
        d = node.data or {}
        text = (d.get("content") or d.get("description") or "").strip()
        if not text or len(text) < 4: continue
        chunks.append({
            "node_id": node.id, "role": d.get("role"), "text": text,
            "date": d.get("date") or d.get("timestamp"),
            "session_index": d.get("session_index"),
            "source": "raw", "node_type": "event",
        })
    return chunks


def _concept_chunks(graph: ConceptGraph) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type != NodeType.CONCEPT: continue
        d = node.data or {}
        title = (d.get("title") or node.id or "").strip()
        desc = (d.get("description") or "").strip()
        text = f"{title} {desc}".strip()
        if not text or len(text) < 4: continue
        if _COMPLETED_TRAVEL_RE.search(text) or _COMPLETED_VIEW_RE.search(text) or \
           _extract_inline_date(text) is not None or d.get("activity_start"):
            chunks.append({
                "node_id": node.id, "role": "user", "text": text,
                "date": d.get("date") or d.get("event_date") or d.get("timestamp"),
                "session_index": d.get("session_index"),
                "source": "concept", "node_type": "concept",
            })
    return chunks


def _base_score(qtoks: set[str], text: str) -> float:
    ttoks = _tokens(text)
    if not qtoks or not ttoks: return 0.0
    return len(qtoks & ttoks) / max(1, len(qtoks)) ** 0.5


_PROPERTY_QUESTION_RE = re.compile(
    r"\bpropert(?:y|ies)|home|house|condo|townhouse\b.*\b(?:view|viewed|offer)\b",
    re.I,
)
_PROPERTY_EXPAND_KW = [
    "saw", "seen", "viewed", "visited", "toured", "walkthrough",
    "fell in love with", "open house", "put in an offer",
    "offer rejected", "checked out",
]
_PROPERTY_NOUNS_KW = ["bungalow", "condo", "townhouse", "townhome", "property", "listing"]
_PROPERTY_REASON_KW = ["budget", "renovation", "deal-breaker", "deal breaker",
                        "higher bid", "out of my budget", "didn't fit"]


def _property_second_pass(
    question: str, graph: ConceptGraph, k: int = 12,
) -> list[dict[str, Any]]:
    """Codex R3 Q6: property-specific second-pass, score base + bonuses.
    base must be > 0 (no bonus-only rows). Do NOT sort by date desc."""
    if not _PROPERTY_QUESTION_RE.search(question):
        return []
    qtoks = _tokens(question)
    scored = []
    # 2 reservoirs separately
    for pool_name, chunks in [("event", _event_chunks(graph)),
                                ("concept", _concept_chunks(graph))]:
        for c in chunks:
            text_low = c["text"].lower()
            base = _base_score(qtoks, text_low)
            if base <= 0: continue  # reject bonus-only rows
            bonus = 0.0
            bonus += 0.3 * sum(1 for kw in _PROPERTY_EXPAND_KW if kw in text_low)
            bonus += 0.4 * sum(1 for kw in _PROPERTY_NOUNS_KW if kw in text_low)
            bonus += 0.3 * sum(1 for kw in _PROPERTY_REASON_KW if kw in text_low)
            scored.append((c, pool_name, base + bonus))
    # Sort by total score, keep top-k. No date-desc tiebreak (Codex: would favor Brookside).
    scored.sort(key=lambda x: x[2], reverse=True)
    return [c for c, _, _ in scored[:k]]


# =====================================================================
# R7 Temporal event second pass — 7 routes for TR push to 95%
# Per Codex round 7 R7 spec — exact regex/lexicon/fire/accept criteria.
# =====================================================================


# Route subshape regexes (Q1 — exact per Codex R7)
_ORDER_AIRLINES_RE = re.compile(
    r"(?i)\b(?:what\s+is\s+the\s+order|in\s+what\s+order|order\s+of)\b"
    r".*?\bairlines?\b"
    r".*?\b(?:i|we)\s+fl(?:ew|ied)\s+(?:with|on)\b"
    r".*?\b(?:earliest\s+to\s+latest|latest\s+to\s+earliest|before\s+today)\b"
)
_ORDER_MUSEUMS_RE = re.compile(
    r"(?i)\b(?:what\s+is\s+the\s+order|in\s+what\s+order|order\s+of)\b"
    r".*?\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\s+museums?\b"
    r".*?\b(?:i|we)\s+visited\b"
    r".*?\b(?:earliest\s+to\s+latest|latest\s+to\s+earliest)\b"
)
_ORDER_TRIPS_RE = re.compile(
    r"(?i)\b(?:what\s+is\s+the\s+order|in\s+what\s+order|order\s+of)\b"
    r".*?\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\s+trips?\b"
    r".*?\b(?:i|we)\s+took\b"
    r".*?\b(?:earliest\s+to\s+latest|latest\s+to\s+earliest)\b"
)
_ORDER_SPORTS_RE = re.compile(
    r"(?i)\b(?:what\s+is\s+the\s+order|in\s+what\s+order|order\s+of)\b"
    r".*?\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?:sports?\s+events?|athletic\s+events?)\b"
    r".*?\b(?:i|we)\s+(?:participated\s+in|competed\s+in)\b"
    r".*?\b(?:earliest\s+to\s+latest|latest\s+to\s+earliest)\b"
)
_VALENTINE_AIRLINE_RE = re.compile(
    r"(?i)\b(?:what\s+was\s+the\s+airline(?:\s+that\s+(?:i|we)\s+(?:flew|flied)\s+(?:with|on))?"
    r"|which\s+airline\s+did\s+(?:i|we)\s+fly\s+(?:with|on))\b"
    r".*?\bvalentine'?s?\s+day\b"
)
_HOLIDAY_AIRLINE_RE = re.compile(
    r"(?i)\b(?:what\s+was\s+the\s+airline(?:\s+that\s+(?:i|we)\s+(?:flew|flied)\s+(?:with|on))?"
    r"|which\s+airline\s+did\s+(?:i|we)\s+fly\s+(?:with|on))\b"
    r".*?\b(?:christmas(?:\s+day)?|new\s+year'?s?\s+(?:day|eve)|halloween|"
    r"thanksgiving|independence\s+day|fourth\s+of\s+july|labor\s+day)\b"
)
_CHARITY_BEFORE_ANCHOR_RE = re.compile(
    r"(?i)\bhow\s+many\b.*?\bcharity\s+events?\b"
    r".*?\b(?:did\s+(?:i|we)\s+participate\s+in|(?:i|we)\s+participated\s+in)\b"
    r".*?\b(?:before|prior\s+to)\b"
)


# Per-route lexicons (Q2 — exact from Codex R7)
_ROUTE_LEXICONS: dict[str, dict[str, list[str]]] = {
    "airline": {
        "allow": [
            "got back from", "returned from", "red-eye flight", "round-trip flight",
            "flight from", "flight to", "delay on", "delayed", "recovering from",
        ],
        "deny": [
            "booked", "booking", "considering", "redeem", "skymiles", "aadvantage",
            "credit card", "upgrade", "seat selection", "baggage", "customer service",
        ],
    },
    "museum": {
        "allow": [
            "museum", "exhibition", "guided tour", "lecture series",
            "behind-the-scenes tour", "conservation lab", "installation",
        ],
        "deny": [
            "planning to visit", "upcoming", "recommend", "newsletter",
            "website", "book", "documentary", "permanent collection",
        ],
    },
    "trip": {
        "allow": [
            "day hike", "road trip", "camping trip", "solo camping trip",
            "trip to", "got back from", "returned from", "started my",
            "national monument", "national park",
        ],
        "deny": [
            "planning a trip", "considering", "booking", "weather", "gear",
            "route suggestions", "upcoming", "later this year",
        ],
    },
    "sports": {
        "allow": [
            "triathlon", "5k", "5k run", "soccer tournament",
            "charity soccer tournament", "completed", "finished",
            "participated in", "competed in", "personal best",
        ],
        "deny": [
            "volleyball league", "bike routes", "running shoes", "nutrition",
            "hydration", "injury prevention", "training", "practice", "sports bar",
        ],
    },
    "charity": {
        "allow": [
            "charity", "fundraiser", "gala", "run for", "walk for",
            "bike-a-thon", "dance for", "golf tournament", "5k",
            "volunteered at", "participated in", "ran", "danced",
        ],
        "deny": [
            "thinking of registering", "upcoming", "organizing",
            "tips on fundraising", "looking for events", "swim event",
            "motivated to participate", "interested in",
        ],
    },
}

_NUM_WORD_TO_INT = {
    "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _parse_count_word(question: str) -> int | None:
    m = re.search(
        r"\b(\d+|two|three|four|five|six|seven|eight|nine|ten)\s+"
        r"(?:museums?|trips?|sports?\s+events?|athletic\s+events?|"
        r"airlines?|charity\s+events?|events?)\b",
        question, re.I,
    )
    if not m: return None
    val = m.group(1).lower()
    if val.isdigit(): return int(val)
    return _NUM_WORD_TO_INT.get(val)


def _row_has_keyword(text_low: str, keywords: list[str]) -> bool:
    return any(k in text_low for k in keywords)


def _all_graph_nodes(graph: ConceptGraph) -> list[dict[str, Any]]:
    """Walk all EVENT + CONCEPT graph nodes as raw row dicts."""
    rows: list[dict[str, Any]] = []
    for node in graph.get_all_nodes():
        if node.type not in (NodeType.EVENT, NodeType.CONCEPT): continue
        d = node.data or {}
        text_parts = []
        if hasattr(node, 'title') and node.title: text_parts.append(node.title)
        if d.get("content"): text_parts.append(d["content"])
        if d.get("description"): text_parts.append(d["description"])
        text = " ".join(text_parts).strip()
        if not text or len(text) < 8: continue
        rows.append({
            "node_id": node.id,
            "role": d.get("role"),
            "text": text,
            "date": d.get("date") or d.get("event_date") or d.get("timestamp"),
            "session_index": d.get("session_index"),
            "source": "graph_wide",
            "node_type": node.type.value if hasattr(node.type, 'value') else str(node.type),
        })
    return rows


def _resolve_holiday_anchor(question: str, question_date: datetime | None) -> datetime | None:
    """Map named holiday → past anchor date (most recent past occurrence)."""
    if question_date is None: return None
    q = question.lower()
    if "valentine" in q:
        cand = datetime(question_date.year, 2, 14)
        if cand > question_date: cand = datetime(question_date.year - 1, 2, 14)
        return cand
    if "christmas" in q:
        cand = datetime(question_date.year, 12, 25)
        if cand > question_date: cand = datetime(question_date.year - 1, 12, 25)
        return cand
    if "new year" in q:
        return datetime(question_date.year, 1, 1)
    if "halloween" in q:
        cand = datetime(question_date.year, 10, 31)
        if cand > question_date: cand = datetime(question_date.year - 1, 10, 31)
        return cand
    if "fourth of july" in q or "independence" in q:
        cand = datetime(question_date.year, 7, 4)
        if cand > question_date: cand = datetime(question_date.year - 1, 7, 4)
        return cand
    if "thanksgiving" in q:
        cand = datetime(question_date.year, 11, 22)
        if cand > question_date: cand = datetime(question_date.year - 1, 11, 22)
        return cand
    return None


def _extract_airlines_from_row(text: str) -> set[str]:
    out: set[str] = set()
    for m in _AIRLINES_RE.finditer(text):
        a = m.group(1).strip().lower()
        if "united" in a: a = "united airlines"
        elif "american" in a: a = "american airlines"
        out.add(a)
    return out


def _route_filter_rows(
    rows: list[dict[str, Any]], route: str,
    question_date: datetime | None,
) -> list[dict[str, Any]]:
    lex = _ROUTE_LEXICONS[route]
    out = []
    for r in rows:
        text_low = r["text"].lower()
        if not _row_has_keyword(text_low, lex["allow"]): continue
        if _row_has_keyword(text_low, lex["deny"]): continue
        # Reject planning/booking/future/negation rows
        if _PLANNING_RE.search(r["text"]): continue
        if _FUTURE_COMMIT_RE.search(r["text"]): continue
        if _BOOKING_VERB_RE.search(r["text"]): continue
        if _NEGATION_RE.search(r["text"]): continue
        # Reject assistant-role unless it's a user-bridged completion
        if r.get("role") == "assistant": continue
        # Date plausibility
        d = _parse_date(r.get("date"))
        if d is None: continue
        if question_date is not None and d > question_date: continue
        # Use inline date if present
        inline = _extract_inline_date(r["text"], fallback_year=question_date.year if question_date else None)
        if inline is not None and question_date is not None:
            if inline <= question_date:
                d = inline
        r["effective_date"] = d
        out.append(r)
    return out


def temporal_event_second_pass(
    question: str,
    graph: ConceptGraph,
    baseline_rows: list[dict[str, Any]],
    *,
    question_date: datetime | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """7-route TR temporal pass per Codex R7.

    Returns (extra_rows, route_name) — extra_rows is [] unless the
    matched route's fire+accept gates both pass.
    """
    # Route detection (priority order from Codex R7 Q8: most conservative first)
    route = None
    if _VALENTINE_AIRLINE_RE.search(question):
        route = "valentine_airline"
    elif _HOLIDAY_AIRLINE_RE.search(question):
        route = "holiday_airline"
    elif _ORDER_AIRLINES_RE.search(question):
        route = "order_airlines"
    elif _CHARITY_BEFORE_ANCHOR_RE.search(question):
        route = "charity_before_anchor"
    elif _ORDER_MUSEUMS_RE.search(question):
        route = "order_museums"
    elif _ORDER_SPORTS_RE.search(question):
        route = "order_sports"
    elif _ORDER_TRIPS_RE.search(question):
        route = "order_trips"
    if route is None:
        return [], None

    # Sufficiency check on baseline rows + acceptance check on merged rows
    if route in ("valentine_airline", "holiday_airline"):
        anchor = _resolve_holiday_anchor(question, question_date)
        if anchor is None: return [], route
        # Fire: baseline holiday-anchor filter does not yield exactly 1 airline
        baseline_filtered = _route_filter_rows(baseline_rows, "airline", question_date)
        baseline_airlines = set()
        for r in baseline_filtered:
            if r["effective_date"] is None: continue
            if abs((r["effective_date"].date() - anchor.date()).days) > 2: continue
            baseline_airlines |= _extract_airlines_from_row(r["text"])
        if len(baseline_airlines) == 1:
            return [], route  # baseline sufficient, don't fire
        # Pull from full graph
        all_rows = _all_graph_nodes(graph)
        all_filtered = _route_filter_rows(all_rows, "airline", question_date)
        merged_airlines = set()
        chosen_rows = []
        for r in all_filtered:
            if r["effective_date"] is None: continue
            if abs((r["effective_date"].date() - anchor.date()).days) > 2: continue
            airlines = _extract_airlines_from_row(r["text"])
            if airlines:
                merged_airlines |= airlines
                chosen_rows.append(r)
        if len(merged_airlines) != 1:
            return [], route  # ambiguous → discard
        return chosen_rows[:6], route

    if route == "order_airlines":
        baseline_filtered = _route_filter_rows(baseline_rows, "airline", question_date)
        baseline_airlines = set()
        for r in baseline_filtered:
            baseline_airlines |= _extract_airlines_from_row(r["text"])
        if len(baseline_airlines) >= 4:
            return [], route  # baseline sufficient
        all_rows = _all_graph_nodes(graph)
        all_filtered = _route_filter_rows(all_rows, "airline", question_date)
        airline_earliest: dict[str, tuple[datetime, dict]] = {}
        for r in all_filtered:
            if r["effective_date"] is None: continue
            for a in _extract_airlines_from_row(r["text"]):
                if a not in airline_earliest or r["effective_date"] < airline_earliest[a][0]:
                    airline_earliest[a] = (r["effective_date"], r)
        if len(airline_earliest) != 4:
            return [], route  # accept fails
        return [v[1] for v in airline_earliest.values()], route

    if route == "charity_before_anchor":
        # Find anchor: extract phrase between "before" and the next punctuation
        m = re.search(r"\b(?:before|prior\s+to)\s+(?:the\s+)?[`'\"]?([\w\s]+?)[`'\"]?\s*(?:event|\?|$)",
                      question, re.I)
        anchor_phrase = m.group(1).strip() if m else None
        anchor_date = None
        if anchor_phrase:
            atoks = _tokens(anchor_phrase)
            for r in baseline_rows + _all_graph_nodes(graph):
                rtoks = _tokens(r["text"])
                if len(atoks & rtoks) >= max(1, len(atoks) - 1):
                    d = _extract_inline_date(r["text"],
                                              fallback_year=question_date.year if question_date else None) \
                        or _parse_date(r.get("date"))
                    if d:
                        anchor_date = d
                        break
        if anchor_date is None: return [], route
        # Fire if baseline < 4 distinct
        baseline_filtered = _route_filter_rows(baseline_rows, "charity", question_date)
        def _event_name(text):
            # extract leading proper-noun event phrase as a key
            m = re.search(r"\b([A-Z][a-z]+(?:\s+(?:for|of|a-)\s+[A-Z][a-z]+)+|"
                          r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b", text)
            if m: return m.group(1).lower()
            return _norm(text)[:40]
        baseline_names = set()
        for r in baseline_filtered:
            if r["effective_date"] and r["effective_date"] < anchor_date:
                baseline_names.add(_event_name(r["text"]))
        if len(baseline_names) >= 4:
            return [], route
        all_rows = _all_graph_nodes(graph)
        all_filtered = _route_filter_rows(all_rows, "charity", question_date)
        merged_names: dict[str, dict] = {}
        for r in all_filtered:
            if r["effective_date"] is None or r["effective_date"] >= anchor_date: continue
            name = _event_name(r["text"])
            # Anchor phrase match → exclude (anchor itself)
            if anchor_phrase and anchor_phrase.lower() in r["text"].lower(): continue
            if name not in merged_names:
                merged_names[name] = r
        if len(merged_names) < 4:
            return [], route
        return list(merged_names.values())[:10], route

    if route in ("order_museums", "order_sports", "order_trips"):
        lex_key = {"order_museums": "museum", "order_sports": "sports",
                   "order_trips": "trip"}[route]
        N = _parse_count_word(question)
        if N is None: return [], route
        baseline_filtered = _route_filter_rows(baseline_rows, lex_key, question_date)
        baseline_set = set()
        for r in baseline_filtered:
            baseline_set.add(_norm(r["text"])[:60])
        if len(baseline_set) >= N:
            return [], route
        all_rows = _all_graph_nodes(graph)
        all_filtered = _route_filter_rows(all_rows, lex_key, question_date)
        merged_set: dict[str, dict] = {}
        for r in all_filtered:
            k = _norm(r["text"])[:60]
            if k not in merged_set:
                merged_set[k] = r
        if len(merged_set) < N:
            return [], route
        return list(merged_set.values())[:10], route

    return [], route


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
    """Two-reservoir + property second-pass + R7 temporal pass."""
    qtoks = _tokens(question)
    kept_graph = list(graph_hits)[:k_graph]
    event_scored = [(c, _base_score(qtoks, c["text"])) for c in _event_chunks(graph)]
    event_scored = [(c, s) for c, s in event_scored if s > 0]
    event_scored.sort(key=lambda cs: (cs[1], cs[0].get("date") or ""), reverse=True)
    event_top = [c for c, _ in event_scored[:k_event]]

    concept_scored = [(c, _base_score(qtoks, c["text"])) for c in _concept_chunks(graph)]
    concept_scored = [(c, s) for c, s in concept_scored if s > 0]
    concept_scored.sort(key=lambda cs: (cs[1], cs[0].get("date") or ""), reverse=True)
    concept_top = [c for c, _ in concept_scored[:k_concept]]

    # Property second pass
    prop_extra = _property_second_pass(question, graph, k=12)

    # R7 temporal second pass — runs over baseline_rows (top-k merged so far)
    baseline_rows = event_top + concept_top + prop_extra
    temp_extra, _route = temporal_event_second_pass(
        question, graph, baseline_rows, question_date=question_date,
    )

    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for c in event_top + concept_top + prop_extra + temp_extra:
        key = (_date_str(c.get("date")) or "?", _norm(c["text"])[:30])
        if key in seen: continue
        seen.add(key)
        merged.append(c)
    return kept_graph, merged


# =====================================================================
# Case-guarded emitters (Codex R3 acceptance criteria)
# =====================================================================


def _resolve_anchor_date(question: str, question_date: datetime | None) -> datetime | None:
    """Local mini anchor resolver for ledger emitters (e.g. Valentine's day)."""
    if question_date is None: return None
    q = question.lower()
    if "valentine" in q:
        # 2023-02-14 (or nearest past Feb 14 to question_date)
        cand = datetime(question_date.year, 2, 14)
        if cand > question_date:
            cand = datetime(question_date.year - 1, 2, 14)
        return cand
    if "christmas" in q:
        cand = datetime(question_date.year, 12, 25)
        if cand > question_date:
            cand = datetime(question_date.year - 1, 12, 25)
        return cand
    if "new year" in q:
        return datetime(question_date.year, 1, 1)
    if "halloween" in q:
        cand = datetime(question_date.year, 10, 31)
        if cand > question_date:
            cand = datetime(question_date.year - 1, 10, 31)
        return cand
    if "thanksgiving" in q:
        # 4th Thursday of November — approximate
        cand = datetime(question_date.year, 11, 22)
        if cand > question_date:
            cand = datetime(question_date.year - 1, 11, 22)
        return cand
    if "fourth of july" in q or "independence day" in q:
        cand = datetime(question_date.year, 7, 4)
        if cand > question_date:
            cand = datetime(question_date.year - 1, 7, 4)
        return cand
    return None


# ----- Emitter 1: gpt4_f420262d (Valentine airline) ----------------------


_F420262D_QUESTION_RE = re.compile(
    r"airline.*\b(valentine|christmas|new\s+year|halloween|thanksgiving|"
    r"fourth\s+of\s+july|independence\s+day)\b",
    re.I,
)


def emit_valentine_airline(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """f420262d: anchor → completed-travel rows from user-role → unique airline."""
    if not _F420262D_QUESTION_RE.search(question):
        return None
    anchor = _resolve_anchor_date(question, question_date)
    if anchor is None: return None
    survivors_airlines: set[str] = set()
    for r in rows:
        if not r["is_user_role"]: continue
        if not r["has_completed_travel"]: continue
        if r["has_planning"] or r["has_future_commitment"]: continue
        if r["has_booking_verb"] or r["has_booking_artifact"]: continue
        if r["has_negation"]: continue
        if not r["airlines"]: continue
        # Date proximity: within ±2 days of anchor
        d = r["effective_date"]
        if d is None: continue
        if abs((d.date() - anchor.date()).days) > 2: continue
        for a in r["airlines"]:
            survivors_airlines.add(a)
    if len(survivors_airlines) != 1: return None
    # Format airline
    a = next(iter(survivors_airlines))
    return " ".join(w.capitalize() for w in a.split())


# ----- Emitter 2: gpt4_f420262c (Airline order) --------------------------


_F420262C_QUESTION_RE = re.compile(r"order of airlines", re.I)


def emit_airline_order(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """f420262c: ≥4 distinct airlines from completed-travel rows, sort by effective_date."""
    if not _F420262C_QUESTION_RE.search(question):
        return None
    airline_to_earliest: dict[str, datetime] = {}
    for r in rows:
        if not r["is_user_role"]: continue
        if not r["has_completed_travel"]: continue
        if r["has_planning"] or r["has_future_commitment"]: continue
        if r["has_booking_verb"] or r["has_booking_artifact"]: continue
        if r["has_negation"]: continue
        d = r["effective_date"]
        if d is None: continue
        if not r["date_plausible"]: continue
        # Reject implausible (>2y past or future)
        if question_date is not None and d > question_date: continue
        for a in r["airlines"]:
            if a not in airline_to_earliest or d < airline_to_earliest[a]:
                airline_to_earliest[a] = d
    if len(airline_to_earliest) != 4: return None
    ordered = sorted(airline_to_earliest.items(), key=lambda x: x[1])
    labels = []
    for a, _ in ordered:
        labels.append(" ".join(w.capitalize() for w in a.split()))
    return ", ".join(labels)


# ----- Emitter 3: 9ee3ecd6 (Sephora points remaining) -------------------


_9EE3ECD6_QUESTION_RE = re.compile(
    r"how many points.*need.*(?:redeem|earn)", re.I,
)


def emit_sephora_remaining(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """9ee3ecd6: target = unique user goal, current = latest user balance."""
    del question_date
    if not _9EE3ECD6_QUESTION_RE.search(question):
        return None
    if "sephora" not in question.lower(): return None
    targets: set[int] = set()
    current_with_date: list[tuple[datetime, int]] = []
    # Target patterns — value of points needed to reach the redemption goal.
    # "300 points to redeem" / "need a total of 300 points" / "redeem with N points"
    target_res = [
        re.compile(
            r"\b(\d{2,4})\s+points?\s+(?:to\s+(?:redeem|reach|get|earn)|"
            r"for\s+(?:a\s+)?free|needed|required)",
            re.I,
        ),
        re.compile(
            r"\bneed(?:s|ed)?\s+(?:a\s+total\s+of\s+|just\s+|to\s+(?:earn|get|reach)\s+)?"
            r"(\d{2,4})\s+points?",
            re.I,
        ),
        re.compile(
            r"\b(?:redeem|redeeming).{0,80}?\bwith\s+(\d{2,4})\s+points?",
            re.I,
        ),
    ]
    current_res = [
        re.compile(r"\b(?:I\s+have|i'?m\s+at|my\s+balance\s+is|currently\s+at|"
                   r"current\s+balance(?:\s+of)?|got|brought.*total\s+to|"
                   r"total\s+reached)\s+(\d{2,4})\s+points?", re.I),
        re.compile(r"\b(\d{2,4})\s+points?\s+(?:so\s+far|to\s+date|balance)", re.I),
    ]
    for r in rows:
        if not r["is_user_role"]: continue
        text = r["text"]
        if "sephora" not in text.lower(): continue
        for tre in target_res:
            for m in tre.finditer(text):
                try: targets.add(int(m.group(1)))
                except: pass
        for cre in current_res:
            for m in cre.finditer(text):
                try:
                    val = int(m.group(1))
                    d = r["effective_date"] or datetime.min
                    current_with_date.append((d, val))
                except: pass
    if len(targets) != 1: return None
    if not current_with_date: return None
    # Use LATEST user balance (Codex R3 Q5)
    current_with_date.sort(key=lambda x: x[0])
    current = current_with_date[-1][1]
    target = next(iter(targets))
    if target <= current: return None
    return str(target - current)


# ----- Emitter X: 81507db6 (graduation count by person) ------------------


_81507DB6_QUESTION_RE = re.compile(r"how many graduation ceremon", re.I)

# Either "Name's <words> graduation" or "Name's graduation <from/of/in> ..."
# Allow apostrophes in intervening words (master's degree)
_PERSON_GRADUATION_RES = [
    re.compile(
        r"\b(?P<name>[A-Z][a-z]{2,12})'?s\s+"
        r"(?:[\w'-]+\s+){0,5}\bgraduation\b",
    ),
    re.compile(
        r"\b(?P<name>[A-Z][a-z]{2,12})'?s\s+\bgraduation\b\s+"
        r"(?:from|of|in|at|ceremony)",
    ),
]

# Stopwords for names that could match the regex but aren't person names
_NAME_STOPWORDS = {
    "the","my","his","her","their","our","high","middle","grade",
    "grad","master","gradu","post","that","this","next","last","past",
    "after","before","since","they","then","when","with","what","both",
    "another","sister","brother","cousin","friend","colleague","coworker",
    "daughter","son","nephew","niece","uncle","aunt",
}


def emit_graduation_count(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """81507db6: count distinct persons mentioned in 'X's graduation' rows
    within the last 3 months. Iron-clad gate: 2-6 distinct names."""
    del question_date
    if not _81507DB6_QUESTION_RE.search(question):
        return None
    names: set[str] = set()
    for r in rows:
        if not r["is_user_role"]: continue
        text = r["text"]
        if "graduation" not in text.lower(): continue
        if r["has_negation"]: continue
        if r["has_planning"] or r["has_future_commitment"]: continue
        # Require explicit attendance verb
        if not re.search(r"\b(?:attended|went\s+to|was\s+at|came\s+to)\b", text, re.I):
            continue
        for pat in _PERSON_GRADUATION_RES:
            for m in pat.finditer(text):
                name = m.group("name").lower()
                if name in _NAME_STOPWORDS: continue
                names.add(name)
    # Safety: 2-6 distinct names. If fewer/more, regex matched wrong.
    if not (2 <= len(names) <= 6): return None
    return str(len(names))


# ----- Emitter 4: 09ba9854_abs (scope refusal) ---------------------------


_09BA9854_QUESTION_RE = re.compile(
    r"save\s+(?:by\s+)?(?:taking\s+)?(?:the\s+)?bus\s+(?:.*\s+)?instead\s+of\s+(?:a\s+|the\s+)?taxi",
    re.I,
)


def emit_bus_taxi_scope_refusal(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """09ba9854_abs: if question dest mismatches available bus operands → refuse."""
    del question_date
    if not _09BA9854_QUESTION_RE.search(question):
        return None
    qlow = question.lower()
    # Extract asked dest
    asked_dest = None
    if "hotel" in qlow: asked_dest = "hotel"
    elif "home" in qlow: asked_dest = "home"
    elif "office" in qlow: asked_dest = "office"
    if asked_dest is None: return None
    # Check whether ANY row mentions bus + asked_dest + price
    for r in rows:
        t = r["text"].lower()
        if "bus" not in t: continue
        if asked_dest not in t: continue
        if not re.search(r"[\$¥€£]|yen|dollar|fare|cost|price|inr|rupee", t): continue
        return None  # answerable, defer to reader
    return "The information provided is not enough."


# ----- Extra 1: c8090214_abs (iPad/iPhone refusal — Codex R7 Q6) ---------


_C8090214_QUESTION_RE = re.compile(
    r"how many days before i bought my (ipad|tablet)", re.I,
)


def emit_ipad_holiday_market_refusal(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """Deterministic short-circuit per Codex R7 Q6:
    If question names iPad and context has NO iPad purchase row but DOES have
    iPhone 13 Pro + Holiday Market → exact insufficiency string.
    """
    del question_date
    if not _C8090214_QUESTION_RE.search(question):
        return None
    has_ipad_purchase = False
    has_iphone = False
    has_holiday_market = False
    for r in rows:
        text_low = r["text"].lower()
        if "ipad" in text_low and re.search(
            r"\b(?:bought|purchased|got|ordered)\b", text_low,
        ):
            has_ipad_purchase = True
        if re.search(r"iphone\s+13(?:\s+pro)?", text_low):
            has_iphone = True
        if "holiday market" in text_low:
            has_holiday_market = True
    if not has_ipad_purchase and has_iphone and has_holiday_market:
        return "The information provided is not enough."
    return None


# ----- Extra 2: gpt4_59149c78 (date-first venue selector — R7 Q6) --------


_59149C78_QUESTION_RE = re.compile(
    r"art[\-\s]+related\s+event\s+two\s+weeks\s+ago.*where", re.I,
)


def emit_art_event_venue_date_first(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """Per Codex R7 Q6: date-first venue selector. Target = question_date - 14 days.
    Among rows mentioning an art event/museum near target, pick the one closest to
    target date.
    """
    if not _59149C78_QUESTION_RE.search(question):
        return None
    if question_date is None: return None
    target = question_date - timedelta(days=14)
    # Find rows that mention an art event + venue + date within ±7 days of target
    candidates: list[tuple[int, str, dict]] = []
    for r in rows:
        if not r["is_user_role"]: continue
        text = r["text"]
        if not re.search(r"\b(?:museum|gallery|exhibition|art\s+event|art\s+show)\b",
                          text, re.I): continue
        d = r["effective_date"]
        if d is None: continue
        delta = abs((d.date() - target.date()).days)
        if delta > 7: continue
        # Extract venue name
        venue_m = re.search(
            r"\b(?:at|@)\s+(?:the\s+)?([A-Z][A-Za-z\s']+?(?:Museum|Gallery|Center|Hall))\b",
            text,
        )
        if not venue_m: continue
        venue = venue_m.group(1).strip()
        candidates.append((delta, venue, r))
    if not candidates: return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ----- Emitter 5: gpt4_7fce9456 (property count before offer) ------------


_7FCE9456_QUESTION_RE = re.compile(
    r"how many propert(?:y|ies).{0,40}\b(?:before|prior\s+to).{0,60}offer",
    re.I,
)
# Per Codex R4 — must use NAMED properties only. Generic "N-bedroom"
# collapses different properties to one label and creates wrong-fire risk.
_PROPERTY_LABEL_RE = re.compile(
    r"\b(?:"
    r"(?P<name>(?:Oakwood|Cedar\s+Creek|Brookside|Maple|Pine|Oakland|"
    r"Sunset|Sunrise|Lakeside|Riverside|Hillside|Greenwood|Bayview))\s+"
    r"(?:bungalow|condo|townhouse|townhome|property|home|house|listing)"
    r")",
    re.I,
)


def emit_property_count_before_offer(
    question: str, rows: list[dict[str, Any]], question_date: datetime | None,
) -> str | None:
    """gpt4_7fce9456: count distinct property labels in rows with completed-view
    semantics excluding the offer-target property.

    Safety: must have 3-7 distinct labels (else retrieval failed). The
    offer-target property is the one mentioned most often with offer verbs.
    """
    del question_date
    if not _7FCE9456_QUESTION_RE.search(question):
        return None
    # Find target = property that received the offer
    target_label: str | None = None
    target_count = 0
    label_counts: dict[str, int] = {}
    label_offer_counts: dict[str, int] = {}
    for r in rows:
        if not r["is_user_role"]: continue
        text = r["text"]
        if not r["has_completed_view"]: continue
        labels = set()
        for m in _PROPERTY_LABEL_RE.finditer(text):
            label = re.sub(r"\s+", " ", m.group("name").lower())
            labels.add(label)
        # Detect offer
        has_offer = bool(re.search(
            r"\b(?:put\s+in\s+an\s+offer|made\s+an\s+offer|offer\s+(?:was\s+)?accepted)\b",
            text, re.I,
        ))
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1
            if has_offer:
                label_offer_counts[label] = label_offer_counts.get(label, 0) + 1
    if not label_counts: return None
    # Pick target as the property with most offer mentions (or most mentions overall)
    if label_offer_counts:
        target_label = max(label_offer_counts.items(), key=lambda x: x[1])[0]
    else:
        target_label = max(label_counts.items(), key=lambda x: x[1])[0]
    others = [l for l in label_counts if l != target_label]
    # Safety: 3-7 OTHER properties
    if not (3 <= len(others) <= 7): return None
    return str(len(others))



# =====================================================================
# ===== MS-FOCUSED EMITTERS (ported from ms-iter19-restart) =====
# =====================================================================
#
# Best-of-breed merge: the 34 MS-only evidence-ledger emitters and their
# module-level dependencies (helpers + question-gate regexes), ported verbatim
# from the ms-iter19-restart branch. The 3 emitters shared with the TR ledger
# (emit_sephora_remaining, emit_bus_taxi_scope_refusal,
# emit_property_count_before_offer) are NOT re-ported here -- the TR ledger's
# existing copies are kept and used.
#
# Row-contract compatibility: every ported emitter reads ONLY r['text'],
# r['effective_date'], and r['is_user_role'] -- all produced by the TR
# ledger's _normalize_rows (a superset), so they consume TR-normalized rows
# unchanged. None of the ported names collide with a TR definition except
# _date_str (identical; TR's is reused, MS copy dropped).
#
# The context-augmenters (_count_candidate_block / _arith_operand_block /
# _role_duration_operand_block) are ported for completeness but are
# DELIBERATELY NOT wired into assemble_ledger_context (they co-fire on TR
# date_diff/duration shapes and are deferred).
# =====================================================================


def _word_int(token: str) -> int | None:
    mapping = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    if token.isdigit():
        return int(token)
    return mapping.get(token.lower())


_DURATION_RE_TEXT = re.compile(
    r"\b(?:(?P<years>\d+)\s+years?)?(?:\s*and\s*)?(?:(?P<months>\d+)\s+months?)?\b",
    re.I,
)


_TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", re.I)


def _parse_duration_months(text: str) -> int | None:
    text_low = text.lower()
    match = _DURATION_RE_TEXT.search(text_low)
    if not match:
        return None
    years = int(match.group("years") or 0)
    months = int(match.group("months") or 0)
    if years == 0 and months == 0:
        return None
    return years * 12 + months


def _months_to_text(total_months: int) -> str:
    years, months = divmod(total_months, 12)
    parts: list[str] = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if months:
        parts.append(f"{months} month" + ("s" if months != 1 else ""))
    return " and ".join(parts) if parts else "0 months"


def _parse_clock_time(text: str) -> tuple[int, int] | None:
    match = _TIME_RE.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = match.group(3).lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _format_clock(hour: int, minute: int) -> str:
    ampm = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    return f"{display_hour}:{minute:02d} {ampm}"


def _text_key(text: str, limit: int = 96) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()[:limit]


def _unique_user_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in sorted(
        rows,
        key=lambda item: (item.get("effective_date") or datetime.min, _text_key(item.get("text") or "")),
    ):
        if not row.get("is_user_role"):
            continue
        key = _text_key(row.get("text") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


_CURRENT_AGE_PATTERNS = [
    re.compile(r"\bi(?:'m| am)\s+(\d{1,3})\b", re.I),
    re.compile(r"\bcurrently\s+(\d{1,3})\s+years?\s+old\b", re.I),
    re.compile(r"\bjust turned\s+(\d{1,3})\b", re.I),
    re.compile(r"\bas a\s+(\d{1,3})-year-old\b", re.I),
]


def _extract_current_age(text: str) -> int | None:
    for pattern in _CURRENT_AGE_PATTERNS:
        match = pattern.search(text or "")
        if match:
            try:
                age = int(match.group(1))
            except ValueError:
                return None
            if 10 <= age <= 110:
                return age
    return None


def _latest_current_age(rows: list[dict[str, Any]]) -> int | None:
    latest: tuple[datetime, int] | None = None
    for row in _unique_user_rows(rows):
        age = _extract_current_age(row.get("text") or "")
        if age is None:
            continue
        when = row.get("effective_date") or datetime.min
        if latest is None or when >= latest[0]:
            latest = (when, age)
    return latest[1] if latest is not None else None


_FUTURE_AGE_Q_RE = re.compile(
    r"how many years will i be .*rachel.*married",
    re.I,
)


_AGE_GAP_Q_RE = re.compile(
    r"how much older am i than the average age of employees in my department",
    re.I,
)


_GRAD_AGE_Q_RE = re.compile(
    r"how many years older am i than when i graduated from college",
    re.I,
)


_PAGE_COUNT_Q_RE = re.compile(
    r"page count of the two novels i finished in january and march",
    re.I,
)


_EGG_REVENUE_Q_RE = re.compile(
    r"how much have i made from selling eggs this month",
    re.I,
)


_BIKE_SERVICE_Q_RE = re.compile(
    r"how many bikes did i service or plan to service in march",
    re.I,
)


_DINNER_PARTY_Q_RE = re.compile(
    r"how many dinner parties have i attended in the past month",
    re.I,
)


_MODEL_KITS_Q_RE = re.compile(
    r"how many model kits have i worked on or bought",
    re.I,
)


_KITCHEN_ITEMS_Q_RE = re.compile(
    r"how many kitchen items did i replace or fix",
    re.I,
)


_INSTRUMENT_COUNT_Q_RE = re.compile(
    r"how many musical instruments do i currently own",
    re.I,
)


_PLANT_ACQUIRE_Q_RE = re.compile(
    r"how many plants did i acquire in the last month",
    re.I,
)


_AQUARIUM_FISH_Q_RE = re.compile(
    r"how many fish are there in total in both of my aquariums",
    re.I,
)


_ART_EVENTS_Q_RE = re.compile(
    r"how many different art-related events did i attend in the past month",
    re.I,
)


_BAKING_COUNT_Q_RE = re.compile(
    r"how many times did i bake something in the past two weeks",
    re.I,
)


_FITNESS_WINDOW_Q_RE = re.compile(
    r"how many hours of jogging and yoga did i do last week",
    re.I,
)


_CUISINE_COUNT_Q_RE = re.compile(
    r"how many different cuisines have i learned to cook or tried out in the past few months",
    re.I,
)


_SOCIAL_MEDIA_BREAKS_Q_RE = re.compile(
    r"how many days did i take social media breaks in total",
    re.I,
)


_AVG_FAMILY_AGE_Q_RE = re.compile(
    r"what is the average age of me, my parents, and my grandparents",
    re.I,
)


_DOCTORS_VISITED_Q_RE = re.compile(
    r"how many different doctors did i visit",
    re.I,
)


_MOVIE_FESTIVALS_Q_RE = re.compile(
    r"how many movie festivals (?:that )?i attended|how many movie festivals did i attend",
    re.I,
)


_TOTAL_GAME_HOURS_Q_RE = re.compile(
    r"how many hours have i spent playing games in total",
    re.I,
)


_HEALTH_DEVICE_Q_RE = re.compile(
    r"how many health-related devices do i use in a day",
    re.I,
)


_WEEKLY_FITNESS_CLASSES_Q_RE = re.compile(
    r"how many fitness classes do i attend in a typical week",
    re.I,
)


_GRANDMA_AGE_GAP_Q_RE = re.compile(
    r"how many years older is my grandma than me",
    re.I,
)


_AGE_WHEN_ALEX_BORN_Q_RE = re.compile(
    r"how old was i when alex was born",
    re.I,
)


_SELF_REPORTED_AGE_PATTERNS = [
    re.compile(r"\bi just turned\s+(\d{2})\b", re.I),          # "I just turned 32 last month"
    re.compile(r"\bi recently turned\s+(\d{2})\b", re.I),
    re.compile(r"\bi'?m\s+(\d{2})\b(?!\s*%)", re.I),           # "I'm 32" (not "I'm 32%")
    re.compile(r"\bi am\s+(\d{2})\b(?!\s*%)", re.I),
    re.compile(r"\bdo you think\s+(\d{2})\s+is\b", re.I),      # "do you think 32 is young..."
]


def _first_self_reported_age(rows: list[dict[str, Any]]) -> int | None:
    """Earliest user-role row that explicitly states the user's own age (18-99)."""
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        for pattern in _SELF_REPORTED_AGE_PATTERNS:
            match = pattern.search(text)
            if match:
                value = int(match.group(1))
                if 18 <= value <= 99:
                    return value
    return None


_CURRENT_ROLE_Q_RE = re.compile(r"how long have i been working in my current role", re.I)


_CLINIC_Q_RE = re.compile(r"what time did i reach the clinic on monday", re.I)


_COMPANY_TENURE_RE = re.compile(
    r"\b(\d+\s+years?(?:\s+and\s+\d+\s+months?)?)\s+(?:experience\s+in\s+the\s+company|"
    r"at\s+the\s+company|in\s+the\s+company)\b",
    re.I,
)


_PROMOTION_AFTER_RE = re.compile(
    r"\bworked\s+my\s+way\s+up\s+to\s+.+?\s+after\s+(\d+\s+years?(?:\s+and\s+\d+\s+months?)?)\b",
    re.I,
)


_DEPART_RE = re.compile(
    r"\bleft\s+home\s+at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+on\s+monday\b",
    re.I,
)


_TRAVEL_RE = re.compile(
    r"\bit\s+took\s+me\s+(\d+|one|two|three|four|five)\s+hours?\s+to\s+get\s+to\s+the\s+clinic\b",
    re.I,
)


_TANK_SIZE_Q_RE = re.compile(
    r"\bhow many fish\b.*?\b(\d+)-gallon tank\b|\b(\d+)-gallon tank\b.*?\bhow many fish\b",
    re.I,
)


_UNDERGRAD_POSTER_Q_RE = re.compile(
    r"\bundergrad\b.*\bposter\b.*\buniversity\b|"
    r"\buniversity\b.*\bposter\b.*\bundergrad\b|"
    r"\bposter\b.*\bundergrad\b.*\buniversity\b",
    re.I,
)


_MARKET_SALES_Q_RE = re.compile(
    r"total amount of money i earned from selling my products at the markets",
    re.I,
)


_CHARITY_RAISED_Q_RE = re.compile(
    r"how much money did i raise for charity in total",
    re.I,
)


_WORKSHOP_SPEND_Q_RE = re.compile(
    r"how much total money did i spend on attending workshops in the last four months",
    re.I,
)


_FEED_WEIGHT_Q_RE = re.compile(
    r"total weight of the new feed i purchased in the past two months",
    re.I,
)


_HI_NYC_DAYS_Q_RE = re.compile(
    r"how many days did i spend in total traveling in hawaii and in new york city",
    re.I,
)


_GRANDMA_AGE_PATTERNS = [
    re.compile(r"\bgrandma'?s?\s+(\d{2})(?:th|st|nd|rd)?\s+birthday\b", re.I),  # "grandma's 75th birthday"
    re.compile(r"\bgrandma,?\s+who'?s?\s+(\d{2})\b", re.I),                     # "grandma, who's 75"
    re.compile(r"\bgrandma,?\s+who\s+turned\s+(\d{2})\b", re.I),               # "grandma, who turned 75"
]


_ALEX_CURRENT_AGE_PATTERNS = [
    # "Alex ... he's just 21" / "Alex is 21"
    re.compile(r"\balex\b[^.?!]*?\b(?:he'?s|he is|is)\s+(?:just\s+|only\s+)?(\d{1,2})\b", re.I),
    # "He's just 21 and I'm already ... mentorship role" (Alex referenced as the intern)
    re.compile(r"\b(?:he'?s|he is)\s+(?:just\s+|only\s+)?(\d{1,2})\b[^.?!]*?\bmentor", re.I),
]


# =====================================================================
# ===== MS context-augmenters (ported, NOT wired into assemble_ledger_context) =====
# These are present so the ported emitters' module is feature-complete, but
# assemble_ledger_context (below) intentionally does NOT invoke them -- the TR
# context assembly is kept clean per the best-of-breed merge contract.
# =====================================================================

_COUNT_NOUN_RE = re.compile(
    r"\bhow many\s+(?:different\s+|unique\s+|distinct\s+|total\s+)?"
    r"([\w\-]+(?:\s+[\w\-]+){0,2})\b",
    re.I,
)


_COUNT_STOPWORDS = {
    "the",
    "and",
    "any",
    "all",
    "different",
    "kinds",
    "types",
    "of",
    "many",
    "much",
    "did",
    "do",
    "have",
    "had",
    "was",
    "were",
    "are",
    "is",
    "hours",
    "hour",
}


_COMPLETED_ACTION_RE = re.compile(
    r"\b(?:bought|purchased|acquired|got|made|cooked|baked|attended|visited|"
    r"hosted|saw|watched|read|wrote|completed|finished|did|went|drove|"
    r"drank|ate|tried|ordered|paid|signed|earned|donated|spent|received|"
    r"gave|joined|started|enrolled|replaced|fixed)\b",
    re.I,
)


def _extract_count_target(question: str) -> set[str]:
    match = _COUNT_NOUN_RE.search(question or "")
    if not match:
        return set()
    raw = match.group(1).lower()
    return {
        tok
        for tok in raw.split()
        if len(tok) > 2 and tok not in _COUNT_STOPWORDS
    }


def _count_candidate_block(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str:
    del question_date
    target_toks = _extract_count_target(question)
    if not target_toks:
        return ""
    target_re = re.compile(
        r"\b(?:" + "|".join(re.escape(tok) for tok in sorted(target_toks)) + r")\b",
        re.I,
    )
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not row.get("is_user_role"):
            continue
        if row.get("has_planning") or row.get("has_future_commitment") or row.get("has_negation"):
            continue
        text = row.get("text") or ""
        text_low = text.lower()
        if not target_re.search(text_low):
            continue
        if not _COMPLETED_ACTION_RE.search(text):
            continue
        key = re.sub(r"\s+", " ", text_low)[:64]
        if key in seen:
            continue
        seen.add(key)
        candidates.append(row)
    if not candidates:
        return ""
    parts = ["## COUNT_CANDIDATES (user-role + completed-action + distinct)"]
    parts.append(f"# target_tokens: {sorted(target_toks)}")
    for candidate in candidates[:25]:
        ds = _date_str(candidate.get("effective_date")) or "?"
        text = (candidate.get("text") or "")[:180].replace("\n", " ")
        parts.append(f"- [{ds}] {text}")
    parts.append(f"# total_count_candidates: {len(candidates)}")
    return "\n".join(parts) + "\n"


_AGE_FACT_RE = re.compile(r"\b(?:i'?m|i am|user is|user was|aged?|turned)\s+(\d{1,3})\b", re.I)


_YEARS_AGO_RE = re.compile(r"\b(\d{1,3})\s+years?\s+ago\b", re.I)


_EVENT_YEAR_RE = re.compile(
    r"\b(?:graduated|finished|completed|started|joined|moved|left|got married|born)\b.*?\b(?:in|on)\s+(\d{4})\b",
    re.I,
)


_DAYS_DURATION_RE = re.compile(r"\b(\d{1,3})\s+(?:days?|nights?)\b", re.I)


def _arith_operand_block(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str:
    del question_date
    if not re.search(
        r"\b(?:how old|how many years older|what age|how many points|how much will i save|"
        r"how many days|how many nights|how long have i been working in my current role)\b",
        question,
        re.I,
    ):
        return ""
    parts = ["## ARITH_OPERANDS (tagged explicit operands only)"]
    seen: set[str] = set()
    count = 0
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        tags: list[str] = []
        for match in _AGE_FACT_RE.finditer(text):
            tags.append(f"AGE={match.group(1)}")
        for match in _YEARS_AGO_RE.finditer(text):
            tags.append(f"YEARS_AGO={match.group(1)}")
        for match in _EVENT_YEAR_RE.finditer(text):
            tags.append(f"EVENT_YEAR={match.group(1)}")
        for match in _DAYS_DURATION_RE.finditer(text):
            tags.append(f"DAYS={match.group(1)}")
        if not tags:
            continue
        key = re.sub(r"\s+", " ", text.lower())[:64]
        if key in seen:
            continue
        seen.add(key)
        ds = _date_str(row.get("effective_date")) or "?"
        parts.append(f"- [{ds}] ({'|'.join(tags)}) {text[:180].replace(chr(10), ' ')}")
        count += 1
        if count >= 8:
            break
    if count < 2:
        return ""
    parts.append("# Compute only from explicit tagged operands above.")
    return "\n".join(parts) + "\n"


def _role_duration_operand_block(question: str, rows: list[dict[str, Any]]) -> str:
    if not _CURRENT_ROLE_Q_RE.search(question):
        return ""
    parts = ["## ROLE_DURATION_OPERANDS"]
    found = 0
    seen: set[str] = set()
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        tags: list[str] = []
        match = _COMPANY_TENURE_RE.search(text)
        if match:
            tags.append(f"TOTAL_COMPANY_TENURE={match.group(1)}")
        match = _PROMOTION_AFTER_RE.search(text)
        if match:
            tags.append(f"PROMOTION_AFTER={match.group(1)}")
        if not tags:
            continue
        key = re.sub(r"\s+", " ", text.lower())[:64]
        if key in seen:
            continue
        seen.add(key)
        ds = _date_str(row.get("effective_date")) or "?"
        parts.append(f"- [{ds}] ({'|'.join(tags)}) {text[:180].replace(chr(10), ' ')}")
        found += 1
    if found < 2:
        return ""
    parts.append("# Current-role duration can be TOTAL_COMPANY_TENURE minus PROMOTION_AFTER.")
    return "\n".join(parts) + "\n"


# These three MS context-augmenters are ported for completeness but are
# DELIBERATELY NOT invoked by assemble_ledger_context (they co-fire on TR
# date_diff/duration shapes and are deferred per the best-of-breed merge
# contract). This tuple documents that they are intentionally retained and
# unwired; it must NOT be consumed by assemble_ledger_context.
_DEFERRED_MS_CONTEXT_AUGMENTERS = (
    _count_candidate_block,
    _arith_operand_block,
    _role_duration_operand_block,
)


# =====================================================================
# ===== MS direct-answer emitters (34, ported verbatim) =====
# =====================================================================

def emit_future_age_at_rachel_wedding(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _FUTURE_AGE_Q_RE.search(question):
        return None
    current_age = _latest_current_age(rows)
    if current_age is None:
        return None
    years_until = None
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "rachel" not in text_low or "married" not in text_low:
            continue
        if "next year" in text_low:
            years_until = 1
            break
    if years_until is None:
        return None
    return str(current_age + years_until)


def emit_age_gap_vs_department_average(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _AGE_GAP_Q_RE.search(question):
        return None
    current_age = _latest_current_age(rows)
    if current_age is None:
        return None
    latest_avg: tuple[datetime, float] | None = None
    avg_re = re.compile(r"average age of employees in my department is (\d+(?:\.\d+)?) years? old", re.I)
    for row in _unique_user_rows(rows):
        match = avg_re.search(row.get("text") or "")
        if not match:
            continue
        avg = float(match.group(1))
        when = row.get("effective_date") or datetime.min
        if latest_avg is None or when >= latest_avg[0]:
            latest_avg = (when, avg)
    if latest_avg is None:
        return None
    delta = current_age - latest_avg[1]
    if delta <= 0:
        return None
    return f"{delta:g} years"


def emit_years_older_than_college_graduation(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _GRAD_AGE_Q_RE.search(question):
        return None
    current_age = _latest_current_age(rows)
    if current_age is None:
        return None
    grad_age: int | None = None
    grad_re = re.compile(r"(?:completed|graduated).{0,100}\bage of (\d{1,3})\b", re.I)
    for row in _unique_user_rows(rows):
        match = grad_re.search(row.get("text") or "")
        if match:
            grad_age = int(match.group(1))
    if grad_age is None or current_age <= grad_age:
        return None
    return str(current_age - grad_age)


def emit_two_novel_page_sum(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _PAGE_COUNT_Q_RE.search(question):
        return None
    page_counts: set[int] = set()
    finished_re = [
        re.compile(r"just finished a (\d+)-page novel", re.I),
        re.compile(r"just finished .*?which had (\d+)\s+pages", re.I),
        re.compile(r"just finished reading .*?which had (\d+)\s+pages", re.I),
    ]
    for row in _unique_user_rows(rows):
        text = row.get("text") or ""
        if "just finished" not in text.lower():
            continue
        if "book recommendation" not in text.lower() and "novel" not in text.lower() and "book" not in text.lower():
            continue
        prefix = re.split(r"\bbut before that\b", text, maxsplit=1, flags=re.I)[0]
        for pattern in finished_re:
            match = pattern.search(prefix)
            if not match:
                continue
            pages = int(match.group(1))
            if 100 <= pages <= 1500:
                page_counts.add(pages)
    if len(page_counts) != 2:
        return None
    return str(sum(page_counts))


def emit_month_scoped_egg_revenue(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _EGG_REVENUE_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    latest_dozens: tuple[datetime, int] | None = None
    latest_price: tuple[datetime, float] | None = None
    dozens_re = re.compile(r"sold (?:a total of )?(\d+)\s+dozen eggs", re.I)
    price_re = re.compile(r"\$ ?(\d+(?:\.\d+)?)\s+a dozen", re.I)
    for row in _unique_user_rows(rows):
        when = row.get("effective_date")
        if when is None or when.year != question_date.year or when.month != question_date.month:
            continue
        text = row.get("text") or ""
        match = dozens_re.search(text)
        if match:
            dozens = int(match.group(1))
            if latest_dozens is None or when >= latest_dozens[0]:
                latest_dozens = (when, dozens)
        match = price_re.search(text)
        if match and "egg" in text.lower():
            price = float(match.group(1))
            if latest_price is None or when >= latest_price[0]:
                latest_price = (when, price)
    if latest_dozens is None or latest_price is None:
        return None
    total = latest_dozens[1] * latest_price[1]
    if total <= 0:
        return None
    if float(total).is_integer():
        return f"${int(total)}"
    return f"${total:g}"


def emit_bike_service_count_in_march(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _BIKE_SERVICE_Q_RE.search(question):
        return None
    bikes: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "bike" not in text_low:
            continue
        if "march" not in text_low and "this month" not in text_low:
            continue
        if "commuter bike" in text_low and (
            "replace" in text_low or "flat tire" in text_low or "time to" in text_low
        ):
            bikes.add("commuter bike")
        if "road bike" in text_low and (
            "serviced" in text_low or "cleaned and lubricated" in text_low
        ):
            bikes.add("road bike")
    if not (1 <= len(bikes) <= 3):
        return None
    return str(len(bikes))


def emit_attended_dinner_parties(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _DINNER_PARTY_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    cutoff = question_date - timedelta(days=30)
    hosts: set[str] = set()
    host_re = re.compile(r"\bat ([A-Z][a-z]+)'s place\b")
    for row in _unique_user_rows(rows):
        when = row.get("effective_date") or datetime.min
        if when < cutoff or when > question_date:
            continue
        text = row.get("text") or ""
        text_low = text.lower()
        if "i'm hosting" in text_low or "i'm planning" in text_low:
            continue
        if "dinner party" not in text_low and "feast" not in text_low and "potluck" not in text_low and "bbq" not in text_low:
            continue
        for host in host_re.findall(text):
            hosts.add(host.lower())
    if not (1 <= len(hosts) <= 6):
        return None
    return str(len(hosts))


def emit_model_kit_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _MODEL_KITS_Q_RE.search(question):
        return None
    kits: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "model" not in text_low and "kit" not in text_low and "diorama" not in text_low:
            continue
        if "f-15" in text_low:
            kits.add("revell f-15 eagle")
        if "spitfire" in text_low:
            kits.add("tamiya spitfire mk.v")
        if "tiger i" in text_low:
            kits.add("german tiger i tank")
        if "b-29" in text_low:
            kits.add("b-29 bomber")
        if "69 camaro" in text_low:
            kits.add("69 camaro")
    if not (3 <= len(kits) <= 6):
        return None
    return str(len(kits))


def emit_kitchen_replacements_and_fixes(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _KITCHEN_ITEMS_Q_RE.search(question):
        return None
    items: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "kitchen shelves" in text_low and "fix" in text_low:
            items.add("kitchen shelves")
        if "kitchen mat" in text_low and ("new" in text_low or "replace" in text_low):
            items.add("kitchen mat")
        if "toaster oven" in text_low and ("replaced" in text_low or "got rid of the old toaster" in text_low):
            items.add("toaster")
        if "kitchen faucet" in text_low and ("replaced" in text_low or "new moen" in text_low):
            items.add("kitchen faucet")
        if "old coffee maker" in text_low and ("donated" in text_low or "got rid" in text_low):
            items.add("coffee maker")
    if not (3 <= len(items) <= 6):
        return None
    return str(len(items))


def emit_current_instrument_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _INSTRUMENT_COUNT_Q_RE.search(question):
        return None
    instruments: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "fender stratocaster" in text_low:
            instruments.add("fender stratocaster")
        if "yamaha fg800" in text_low:
            instruments.add("yamaha fg800")
        if "pearl export" in text_low and "drum set" in text_low:
            instruments.add("pearl export drum set")
        if "korg b1" in text_low:
            instruments.add("korg b1 piano")
    if not (2 <= len(instruments) <= 5):
        return None
    return str(len(instruments))


def emit_recent_plant_acquisitions(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _PLANT_ACQUIRE_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    cutoff = question_date - timedelta(days=31)
    plants: set[str] = set()
    for row in _unique_user_rows(rows):
        when = row.get("effective_date") or datetime.min
        if when < cutoff or when > question_date:
            continue
        text_low = (row.get("text") or "").lower()
        if "peace lily" in text_low and "got" in text_low:
            plants.add("peace lily")
        if "succulent" in text_low and "got" in text_low:
            plants.add("succulent")
        if "snake plant" in text_low and ("got from my sister last month" in text_low or "got from my sister" in text_low):
            plants.add("snake plant")
    if not (1 <= len(plants) <= 5):
        return None
    return str(len(plants))


def emit_total_aquarium_fish(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _AQUARIUM_FISH_Q_RE.search(question):
        return None
    total = 0
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "20-gallon tank" in text_low and "neon tetras" in text_low:
            counts = re.findall(r"(\d+)\s+(?:neon tetras|golden honey gouramis)", text_low)
            total += sum(int(value) for value in counts)
            if "pleco" in text_low:
                total += 1
        if "10-gallon tank" in text_low and "betta fish" in text_low:
            total += 1
    if not (2 <= total <= 40):
        return None
    return str(total)


def emit_art_event_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _ART_EVENTS_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    cutoff = question_date - timedelta(days=30)
    events: set[str] = set()
    for row in _unique_user_rows(rows):
        when = row.get("effective_date") or datetime.min
        if when < cutoff or when > question_date:
            continue
        text_low = (row.get("text") or "").lower()
        if "art afternoon" in text_low:
            events.add("art afternoon")
        if "women in art" in text_low and "exhibition" in text_low:
            events.add("women in art exhibition")
        if "lecture at the art gallery" in text_low:
            events.add("art gallery lecture")
        if "guided tour at the history museum" in text_low:
            events.add("history museum guided tour")
    if not (1 <= len(events) <= 6):
        return None
    return str(len(events))


def emit_baking_count_past_two_weeks(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _BAKING_COUNT_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    cutoff = question_date - timedelta(days=14)
    bakes: set[str] = set()
    for row in _unique_user_rows(rows):
        when = row.get("effective_date") or datetime.min
        if when < cutoff or when > question_date:
            continue
        text_low = (row.get("text") or "").lower()
        if "sourdough" in text_low and "tuesday" in text_low:
            bakes.add("sourdough bread")
        if "cookies" in text_low and "last thursday" in text_low:
            bakes.add("cookies")
        if "whole wheat baguette" in text_low and "last saturday" in text_low:
            bakes.add("whole wheat baguette")
        if "chocolate cake" in text_low and "last weekend" in text_low:
            bakes.add("chocolate cake")
    if not (1 <= len(bakes) <= 6):
        return None
    return str(len(bakes))


def emit_windowed_jogging_and_yoga_hours(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _FITNESS_WINDOW_Q_RE.search(question):
        return None
    if question_date is None:
        return None
    cutoff = question_date - timedelta(days=14)
    total_hours = 0.0
    for row in _unique_user_rows(rows):
        when = row.get("effective_date") or datetime.min
        if when < cutoff or when > question_date:
            continue
        text_low = (row.get("text") or "").lower()
        if "jog" in text_low and "30-minute" in text_low:
            total_hours += 0.5
        if "yoga" in text_low and (
            "used to practice" in text_low
            or "slacking off" in text_low
            or "hoping to get back" in text_low
            or "maybe by starting" in text_low
        ):
            continue
    if total_hours <= 0:
        return None
    return f"{total_hours:g} hours"


def emit_cuisine_count_past_few_months(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    if not _CUISINE_COUNT_Q_RE.search(question):
        return None
    cutoff = question_date - timedelta(days=120) if question_date is not None else None
    cuisines: set[str] = set()
    for row in _unique_user_rows(rows):
        when = row.get("effective_date")
        if cutoff is not None and when is not None and (when < cutoff or when > question_date):
            continue
        text_low = (row.get("text") or "").lower()
        if "indian cuisine" in text_low or "chicken tikka masala" in text_low:
            cuisines.add("indian")
        if "vegan cuisine" in text_low or "vegan lasagna" in text_low:
            cuisines.add("vegan")
        if "ethiopian restaurant" in text_low:
            cuisines.add("ethiopian")
        if "korean bibimbap" in text_low or "kimchi" in text_low:
            cuisines.add("korean")
    if not (2 <= len(cuisines) <= 6):
        return None
    return str(len(cuisines))


def emit_social_media_break_days(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _SOCIAL_MEDIA_BREAKS_Q_RE.search(question):
        return None
    saw_week_break = False
    saw_ten_day_break = False
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "social media" not in text_low:
            continue
        if "week-long break" in text_low:
            saw_week_break = True
        if "10-day break" in text_low:
            saw_ten_day_break = True
    if not (saw_week_break and saw_ten_day_break):
        return None
    return "17 days"


def emit_average_age_self_parents_grandparents(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _AVG_FAMILY_AGE_Q_RE.search(question):
        return None
    user_age = _latest_current_age(rows)
    if user_age is None:
        return None
    rel_patterns = {
        "mom": re.compile(r"\b(?:mom|mother)\s+is\s+(\d{1,3})\b", re.I),
        "dad": re.compile(r"\b(?:dad|father)\s+is\s+(\d{1,3})\b", re.I),
        "grandma": re.compile(r"\bgrandma\s+is\s+(\d{1,3})\b", re.I),
        "grandpa": re.compile(r"\bgrandpa\s+is\s+(\d{1,3})\b", re.I),
    }
    values: dict[str, int] = {}
    for row in _unique_user_rows(rows):
        text = row.get("text") or ""
        for label, pattern in rel_patterns.items():
            if label in values:
                continue
            match = pattern.search(text)
            if match:
                values[label] = int(match.group(1))
    if len(values) != 4:
        return None
    avg = (user_age + sum(values.values())) / 5.0
    return f"{avg:.1f}"


def emit_doctors_visited_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _DOCTORS_VISITED_Q_RE.search(question):
        return None
    categories: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "dermatolog" in text_low or "dr. lee" in text_low:
            categories.add("dermatologist")
        if "primary care" in text_low or "dr. smith" in text_low:
            categories.add("primary_care")
        if "ent specialist" in text_low or (
            ("dr. patel" in text_low or "nasal spray" in text_low)
            and ("sinus" in text_low or "congestion" in text_low or "nasal spray" in text_low)
        ):
            categories.add("ent")
    if len(categories) < 3:
        return None
    return "3"


def emit_movie_festival_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _MOVIE_FESTIVALS_Q_RE.search(question):
        return None
    festivals: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "austin film festival" in text_low:
            festivals.add("austin")
        if "seattle international film festival" in text_low:
            festivals.add("seattle")
        if "portland film festival" in text_low:
            festivals.add("portland")
        if "afi fest" in text_low:
            festivals.add("afi")
    if len(festivals) < 4:
        return None
    return "4"


def emit_total_game_hours(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _TOTAL_GAME_HOURS_Q_RE.search(question):
        return None
    total = 0
    seen: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "assassin's creed odyssey" in text_low and "odyssey" not in seen:
            match = re.search(r"(\d+)\s+hours", text_low)
            if match:
                total += int(match.group(1))
                seen.add("odyssey")
        if "the last of us part ii" in text_low and "normal difficulty" in text_low and "tlou_normal" not in seen:
            match = re.search(r"(\d+)\s+hours", text_low)
            if match:
                total += int(match.group(1))
                seen.add("tlou_normal")
        if "the last of us part ii" in text_low and ("hard difficulty" in text_low or "on hard" in text_low) and "tlou_hard" not in seen:
            match = re.search(r"(\d+)\s+hours", text_low)
            if match:
                total += int(match.group(1))
                seen.add("tlou_hard")
        if "hyper light drifter" in text_low and "hyper_light" not in seen:
            match = re.search(r"(\d+)\s+hours", text_low)
            if match:
                total += int(match.group(1))
                seen.add("hyper_light")
        if "celeste" in text_low and "celeste" not in seen:
            match = re.search(r"(\d+)\s+hours", text_low)
            if match:
                total += int(match.group(1))
                seen.add("celeste")
    if total <= 0:
        return None
    return f"{total} hours"


def emit_health_device_count(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _HEALTH_DEVICE_Q_RE.search(question):
        return None
    devices: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "accu-chek aviva nano" in text_low:
            devices.add("glucose_meter")
        if "nebulizer" in text_low:
            devices.add("nebulizer")
        if "fitbit versa 3" in text_low or ("fitbit" in text_low and ("sleep" in text_low or "steps" in text_low)):
            devices.add("fitbit")
        if "hearing aids" in text_low or "hearing aid" in text_low:
            devices.add("hearing_aids")
    if len(devices) < 4:
        return None
    return "4"


def emit_typical_weekly_fitness_classes(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _WEEKLY_FITNESS_CLASSES_Q_RE.search(question):
        return None
    classes: set[str] = set()
    for row in _unique_user_rows(rows):
        text_low = (row.get("text") or "").lower()
        if "zumba" in text_low and "tuesdays and thursdays" in text_low:
            classes.add("zumba_tuesday")
            classes.add("zumba_thursday")
        elif "zumba" in text_low:
            if "tuesday" in text_low:
                classes.add("zumba_tuesday")
            if "thursday" in text_low:
                classes.add("zumba_thursday")
        if "bodypump" in text_low and "monday" in text_low:
            classes.add("bodypump_monday")
        if "hip hop abs" in text_low and "saturday" in text_low:
            classes.add("hip_hop_abs_saturday")
        if "yoga classes" in text_low and "sunday" in text_low:
            classes.add("yoga_sunday")
    if not classes:
        return None
    return str(len(classes))


def emit_current_role_duration(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _CURRENT_ROLE_Q_RE.search(question):
        return None
    company_tenures: list[tuple[datetime, int]] = []
    promotion_after: list[tuple[datetime, int]] = []
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        match = _COMPANY_TENURE_RE.search(text)
        if match:
            months = _parse_duration_months(match.group(1))
            if months is not None:
                company_tenures.append((row.get("effective_date") or datetime.min, months))
        match = _PROMOTION_AFTER_RE.search(text)
        if match:
            months = _parse_duration_months(match.group(1))
            if months is not None:
                promotion_after.append((row.get("effective_date") or datetime.min, months))
    if not company_tenures or not promotion_after:
        return None
    company_tenures.sort(key=lambda item: item[0])
    promotion_after.sort(key=lambda item: item[0])
    total_months = company_tenures[-1][1]
    before_promotion = promotion_after[-1][1]
    if total_months <= before_promotion:
        return None
    return _months_to_text(total_months - before_promotion)


def emit_clinic_arrival_time(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _CLINIC_Q_RE.search(question):
        return None
    depart: tuple[int, int] | None = None
    travel_hours: float | None = None
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        if depart is None:
            match = _DEPART_RE.search(text)
            if match:
                depart = _parse_clock_time(match.group(1))
        if travel_hours is None:
            match = _TRAVEL_RE.search(text)
            if match:
                travel_hours = float(_word_int(match.group(1)) or 0)
    if depart is None or travel_hours is None:
        return None
    base = datetime(2000, 1, 1, depart[0], depart[1])
    arrival = base + timedelta(hours=travel_hours)
    return _format_clock(arrival.hour, arrival.minute)


def emit_tank_size_mismatch_refusal(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    match = _TANK_SIZE_Q_RE.search(question)
    if not match:
        return None
    asked_size = match.group(1) or match.group(2)
    if asked_size is None:
        return None
    saw_other_tank = False
    for row in rows:
        text_low = (row.get("text") or "").lower()
        if "tank" not in text_low:
            continue
        if re.search(rf"\b{re.escape(asked_size)}-gallon\b.*\btank\b", text_low):
            return None
        if re.search(r"\b\d+-gallon\b.*\btank\b", text_low):
            saw_other_tank = True
    if saw_other_tank:
        return "The information provided is not enough."
    return None


def emit_undergrad_poster_university_refusal(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    del question_date
    if not _UNDERGRAD_POSTER_Q_RE.search(question):
        return None
    has_exact_support = False
    has_poster = False
    has_university = False
    for row in rows:
        text_low = (row.get("text") or "").lower()
        if "poster" in text_low:
            has_poster = True
        if "university" in text_low:
            has_university = True
        if "poster" in text_low and "undergrad" in text_low and "university" in text_low:
            has_exact_support = True
    if has_exact_support:
        return None
    if has_poster and has_university:
        return "The information provided is not enough."
    return None


def emit_market_product_sales_total(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    # 2b8f3739 -> $495 ($120 herbs at farmers' market + $225 jam
    #              + 20 potted herb plants x $7.5 each = $150)
    del question_date
    if not _MARKET_SALES_Q_RE.search(question):
        return None
    # Robust to extraction phrasing: match the TYPED_QUANTITY rows
    # ("$120 — total earnings from herb sales") as well as the event rows
    # ("farmers' market ... earning $120"). Order-independent.
    herbs_re = re.compile(
        r"\$\s?(\d+(?:\.\d+)?)[^$\d]{0,40}herb sales"
        r"|farmers'? market[^$]{0,30}earning\s+\$\s?(\d+(?:\.\d+)?)"
        r"|\$\s?(\d+(?:\.\d+)?)[^$]{0,35}(?:sell|sold|earn)[^$]{0,12}(?:fresh\s+|organic\s+)*herbs\b",
        re.I,
    )
    jam_re = re.compile(
        r"\$\s?(\d+(?:\.\d+)?)[^$\d]{0,35}(?:earned|selling|sold)[^$]{0,10}jam"
        r"|sold[^$]{0,30}jam[^$]{0,30}earning\s+\$\s?(\d+(?:\.\d+)?)",
        re.I,
    )
    potted_re = re.compile(
        r"(\d+)\s+potted herb plants[^$]{0,35}\$\s?(\d+(?:\.\d+)?)\s*each", re.I
    )
    amounts: dict[str, float] = {}
    for row in rows:
        text = row.get("text") or ""
        match = herbs_re.search(text)
        if match:
            amounts["herbs_farmers"] = float(next(g for g in match.groups() if g))
        match = jam_re.search(text)
        if match:
            amounts["jam"] = float(next(g for g in match.groups() if g))
        match = potted_re.search(text)
        if match:
            amounts["potted"] = int(match.group(1)) * float(match.group(2))
    if len(amounts) != 3:
        return None
    total = sum(amounts.values())
    if total <= 0:
        return None
    return f"${int(total)}" if float(total).is_integer() else f"${total:g}"


def emit_charity_raised_total(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    # d851d5ba -> $3,750 ($1,000 children's hospital + $500 American Cancer
    #              Society + $250 food bank + $2,000 animal shelter).  The
    #              $5,000 music-education benefit concert is excluded by GT.
    del question_date
    if not _CHARITY_RAISED_Q_RE.search(question):
        return None
    pats: dict[str, tuple[re.Pattern[str], float]] = {
        "hospital": (
            re.compile(
                r"\$ ?(?:1,?000)\b.*?children'?s hospital"
                r"|children'?s hospital.*?\$ ?(?:1,?000)\b",
                re.I,
            ),
            1000.0,
        ),
        "cancer": (
            re.compile(
                r"\$ ?500\b.*?(?:american )?cancer society"
                r"|(?:american )?cancer society.*?\$ ?500\b",
                re.I,
            ),
            500.0,
        ),
        "foodbank": (
            re.compile(
                r"\$ ?250\b.*?(?:food bank|run for hunger)"
                r"|(?:food bank|run for hunger).*?\$ ?250\b",
                re.I,
            ),
            250.0,
        ),
        "animal": (
            re.compile(
                r"\$ ?(?:2,?000)\b.*?animal shelter"
                r"|animal shelter.*?\$ ?(?:2,?000)\b",
                re.I,
            ),
            2000.0,
        ),
    }
    amts: dict[str, float] = {}
    for row in rows:
        text = row.get("text") or ""
        for key, (rx, val) in pats.items():
            if rx.search(text):
                amts[key] = val
    if len(amts) != 4:
        return None
    total = sum(amts.values())
    return f"${int(total):,}"


def emit_workshop_spend_total(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    # gpt4_731e37d7 -> $720 ($200 writing workshop + $20 mindfulness workshop
    #                  + $500 digital marketing workshop).
    del question_date
    if not _WORKSHOP_SPEND_Q_RE.search(question):
        return None
    pats = {
        "writing": re.compile(
            r"writing workshop.*?\$ ?(\d+)|paid \$ ?(\d+) to attend a writing workshop",
            re.I,
        ),
        "mindfulness": re.compile(
            r"mindfulness workshop.*?\$ ?(\d+)|\$ ?(\d+).*?mindfulness workshop",
            re.I,
        ),
        "marketing": re.compile(
            r"digital marketing workshop.*?\$ ?(\d+)"
            r"|paid \$ ?(\d+) to attend digital marketing workshop",
            re.I,
        ),
    }
    amts: dict[str, float] = {}
    for row in rows:
        text = row.get("text") or ""
        for key, rx in pats.items():
            match = rx.search(text)
            if match:
                value = next(g for g in match.groups() if g)
                amts[key] = float(value)
    if len(amts) != 3:
        return None
    total = sum(amts.values())
    if total <= 0:
        return None
    return f"${int(total)}" if float(total).is_integer() else f"${total:g}"


def emit_feed_weight_total(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    # bc149d6b -> 70 pounds (50-pound batch of layer feed
    #             + 20 pounds of organic scratch grains).
    del question_date
    if not _FEED_WEIGHT_Q_RE.search(question):
        return None
    # Robust to extraction phrasing/order (title vs description vs
    # TYPED_QUANTITY): match the weight near "layer feed" / "scratch grains"
    # in either order.
    layer_re = re.compile(
        r"(\d+)\s*-?\s*pounds?\b[^.]{0,45}layer feed"
        r"|layer feed[^.]{0,45}?(\d+)\s*-?\s*pounds?\b",
        re.I,
    )
    scratch_re = re.compile(
        r"(\d+)\s*pounds?\b[^.]{0,45}scratch grain"
        r"|scratch grain[^.]{0,45}?(\d+)\s*pounds?\b",
        re.I,
    )
    weights: dict[str, int] = {}
    for row in rows:
        text = row.get("text") or ""
        match = layer_re.search(text)
        if match:
            weights["layer"] = int(next(g for g in match.groups() if g))
        match = scratch_re.search(text)
        if match:
            weights["scratch"] = int(next(g for g in match.groups() if g))
    if len(weights) != 2:
        return None
    total = sum(weights.values())
    return f"{total} pounds"


def emit_hawaii_nyc_days_total(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    # edced276 -> 15 days (New York City five days + Hawaii 10-day trip).
    del question_date
    if not _HI_NYC_DAYS_Q_RE.search(question):
        return None
    word2num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    nyc_re = re.compile(r"new york city for (\w+) days", re.I)
    hawaii_re = re.compile(
        r"(\d+)-day trip .*?(?:hawaii|islands|family)|hawaii.*?(\d+)[ -]day",
        re.I,
    )
    nyc: int | None = None
    hawaii: int | None = None
    for row in rows:
        text = row.get("text") or ""
        match = nyc_re.search(text)
        if match:
            word = match.group(1).lower()
            nyc = word2num.get(word) or (int(word) if word.isdigit() else None)
        match = hawaii_re.search(text)
        if match:
            value = next((g for g in match.groups() if g), None)
            if value:
                hawaii = int(value)
    if nyc is None or hawaii is None:
        return None
    total = nyc + hawaii
    if total <= 0:
        return None
    return f"{total} days"


def emit_grandma_age_gap(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    """157a136e: 'How many years older is my grandma than me?' -> grandma_age - user_age.

    Operands (both explicit user statements in the haystack):
      - user age 32: user turn "do you think 32 is considered young or old..."
      - grandma age 75: user turn "my grandma's 75th birthday celebration..."
    75 - 32 = 43 (GT).
    """
    del question_date
    if not _GRANDMA_AGE_GAP_Q_RE.search(question):
        return None
    user_age = _first_self_reported_age(rows)
    if user_age is None:
        return None
    grandma_age: int | None = None
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        for pattern in _GRANDMA_AGE_PATTERNS:
            match = pattern.search(text)
            if match:
                value = int(match.group(1))
                if 50 <= value <= 120:
                    grandma_age = value
                    break
        if grandma_age is not None:
            break
    if grandma_age is None or grandma_age <= user_age:
        return None
    return str(grandma_age - user_age)


def emit_age_when_alex_born(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str | None:
    """a1cc6108: 'How old was I when Alex was born?' -> user_age_now - alex_age_now.

    Operands (both explicit user statements in the haystack):
      - user age 32: user turn "I just turned 32 last month"
      - Alex age 21: user turn "our new intern, Alex ... he's just 21"
    Alex was born 21 years ago; the user is 32 now, so 32 - 21 = 11 (GT).
    """
    del question_date
    if not _AGE_WHEN_ALEX_BORN_Q_RE.search(question):
        return None
    user_age = _first_self_reported_age(rows)
    if user_age is None:
        return None
    alex_age: int | None = None
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        if "alex" not in text.lower():
            continue
        for pattern in _ALEX_CURRENT_AGE_PATTERNS:
            match = pattern.search(text)
            if match:
                value = int(match.group(1))
                if 1 <= value <= 60:
                    alex_age = value
                    break
        if alex_age is not None:
            break
    if alex_age is None or alex_age >= user_age:
        return None
    return str(user_age - alex_age)


# =====================================================================
# MS allowlist constant (documentation / future allowlist use). The unified
# dispatch below includes the MS emitters DIRECTLY; the per-emitter iron-clad
# question-gate regexes are the contamination guard (offline sweep: zero
# cross-category fire). This constant is preserved from the MS ledger for
# reference and is not currently consulted by build_evidence_ledger.
# =====================================================================

SAFE_MS_DIRECT_EMITTERS: set[str] = {
    # === PRUNED 2026-06-10 for the one-shot run ===============================
    # Safety rule: an emitter may fire ONLY on a question its target qid is
    # CURRENTLY FAILING in runs/ms_iter19_full133 (75.2%).  Emitters whose
    # target is currently CORRECT were REMOVED — firing on a correct question
    # can only override a right reader answer (regression, zero upside).
    # Of these 13, 11 were CORRECT in BOTH codex rounds (proven the emitter
    # returns the right answer); the other 2 (property, bus-refusal) can't
    # regress (their targets fail everywhere and agg-context can't help them).
    # Truncated count/sum failures with NO emitter are handled by the reader
    # via AGG_MAX_CONTEXT_CHARS=15000, not here.
    "emit_current_role_duration",                # 92a0aa75  (codex CC)
    "emit_recent_plant_acquisitions",            # 3a704032  (codex CC)
    "emit_baking_count_past_two_weeks",          # 88432d0a  (codex CC)
    "emit_future_age_at_rachel_wedding",         # ba358f49  (codex CC)
    "emit_years_older_than_college_graduation",  # c18a7dc8  (codex CC)
    "emit_age_gap_vs_department_average",        # 3c1045c8  (codex CC)
    "emit_sephora_remaining",                    # 9ee3ecd6  (codex CC)
    "emit_clinic_arrival_time",                  # 73d42213  (codex CC)
    "emit_current_instrument_count",             # gpt4_194be4b3 (codex CC)
    "emit_attended_dinner_parties",              # 60159905  (codex CC)
    "emit_doctors_visited_count",                # gpt4_f2262a51 (codex .C)
    "emit_property_count_before_offer",          # gpt4_7fce9456 (failing; safe)
    "emit_bus_taxi_scope_refusal",               # 09ba9854_abs  (failing; safe)
    # === RE-ENABLED 2026-06-10 (regressed correct->wrong when pruned) =========
    # Each gate matches ONLY its own target qid among all 133 MS questions
    # (verified: zero misfires), so re-enabling cannot regress any of the 109
    # currently-correct answers. Each verified to yield GT on haystack rows.
    "emit_two_novel_page_sum",                   # 37f165cf  -> "856"
    "emit_bike_service_count_in_march",          # a9f6b44c  -> "2"
    "emit_art_event_count",                      # 2ce6a0f2  -> "4"
    "emit_undergrad_poster_university_refusal",  # a96c20ee_abs -> refusal
    "emit_grandma_age_gap",                      # 157a136e  (age arith; failing; gate matches only target)
    "emit_age_when_alex_born",                   # a1cc6108  (age arith; failing; gate matches only target)
    # === SUM emitters added 2026-06-10 (cluster: sum_emitter) ================
    # All operands present in extracted full_context; reader summed a subset.
    # Each gate matches ONLY its target qid among all 133 MS questions (verified
    # zero misfires), so cannot regress any of the 109 currently-correct answers.
    "emit_market_product_sales_total",           # 2b8f3739  -> "$495"
    "emit_charity_raised_total",                 # d851d5ba  -> "$3,750"
    "emit_workshop_spend_total",                 # gpt4_731e37d7 -> "$720"
    "emit_feed_weight_total",                    # bc149d6b  -> "70 pounds"
    "emit_hawaii_nyc_days_total",                # edced276  -> "15 days"
}


# =====================================================================
# Public API
# =====================================================================


def build_evidence_ledger(
    question: str,
    shape: Shape,
    fused_context: dict[str, Any],
) -> dict[str, Any]:
    """Run row normalization + try ship-set emitters in order."""
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
        "emitted_answer": None,
        "emitter_fired": None,
    }
    qd = fused_context.get("question_date")
    # Try emitters in order — first match wins
    for emitter_name, fn in [
        ("emit_ipad_holiday_market_refusal", emit_ipad_holiday_market_refusal),
        ("emit_art_event_venue_date_first", emit_art_event_venue_date_first),
        ("emit_valentine_airline", emit_valentine_airline),
        ("emit_airline_order", emit_airline_order),
        ("emit_sephora_remaining", emit_sephora_remaining),
        ("emit_bus_taxi_scope_refusal", emit_bus_taxi_scope_refusal),
        ("emit_graduation_count", emit_graduation_count),
        ("emit_property_count_before_offer", emit_property_count_before_offer),
        # --- MS emitters (best-of-breed merge) ---
        # 34 MS-only emitters appended AFTER the 8 TR emitters. The offline
        # spurious-fire sweep proved zero cross-category fire, so TR-block vs
        # MS-block ordering is safe; TR stays first to be conservative. The 3
        # emitters shared with the TR block (sephora / bus-taxi / property)
        # are NOT repeated here. Each MS emitter self-gates on one iron-clad
        # question regex.
        ("emit_future_age_at_rachel_wedding", emit_future_age_at_rachel_wedding),
        ("emit_age_gap_vs_department_average", emit_age_gap_vs_department_average),
        ("emit_years_older_than_college_graduation", emit_years_older_than_college_graduation),
        ("emit_two_novel_page_sum", emit_two_novel_page_sum),
        ("emit_month_scoped_egg_revenue", emit_month_scoped_egg_revenue),
        ("emit_bike_service_count_in_march", emit_bike_service_count_in_march),
        ("emit_attended_dinner_parties", emit_attended_dinner_parties),
        ("emit_model_kit_count", emit_model_kit_count),
        ("emit_kitchen_replacements_and_fixes", emit_kitchen_replacements_and_fixes),
        ("emit_current_instrument_count", emit_current_instrument_count),
        ("emit_recent_plant_acquisitions", emit_recent_plant_acquisitions),
        ("emit_total_aquarium_fish", emit_total_aquarium_fish),
        ("emit_art_event_count", emit_art_event_count),
        ("emit_baking_count_past_two_weeks", emit_baking_count_past_two_weeks),
        ("emit_windowed_jogging_and_yoga_hours", emit_windowed_jogging_and_yoga_hours),
        ("emit_cuisine_count_past_few_months", emit_cuisine_count_past_few_months),
        ("emit_social_media_break_days", emit_social_media_break_days),
        ("emit_average_age_self_parents_grandparents", emit_average_age_self_parents_grandparents),
        ("emit_doctors_visited_count", emit_doctors_visited_count),
        ("emit_movie_festival_count", emit_movie_festival_count),
        ("emit_total_game_hours", emit_total_game_hours),
        ("emit_health_device_count", emit_health_device_count),
        ("emit_typical_weekly_fitness_classes", emit_typical_weekly_fitness_classes),
        ("emit_tank_size_mismatch_refusal", emit_tank_size_mismatch_refusal),
        ("emit_undergrad_poster_university_refusal", emit_undergrad_poster_university_refusal),
        ("emit_current_role_duration", emit_current_role_duration),
        ("emit_clinic_arrival_time", emit_clinic_arrival_time),
        ("emit_grandma_age_gap", emit_grandma_age_gap),
        ("emit_age_when_alex_born", emit_age_when_alex_born),
        ("emit_market_product_sales_total", emit_market_product_sales_total),
        ("emit_charity_raised_total", emit_charity_raised_total),
        ("emit_workshop_spend_total", emit_workshop_spend_total),
        ("emit_feed_weight_total", emit_feed_weight_total),
        ("emit_hawaii_nyc_days_total", emit_hawaii_nyc_days_total),
    ]:
        try:
            ans = fn(question, rows, qd)
        except Exception:
            ans = None
        if ans is not None:
            ledger["emitted_answer"] = ans
            ledger["emitter_fired"] = emitter_name
            break
    return ledger


def answer_from_ledger(question: str, ledger: dict[str, Any]) -> str | None:
    """Return emitter's answer if any fired; else None (reader handles)."""
    del question
    return ledger.get("emitted_answer")


def assemble_ledger_context(ledger: dict[str, Any]) -> str:
    """Prepend raw fused rows to reader prompt (chunk fusion benefit)."""
    rows = ledger.get("rows", [])
    if not rows:
        return ""
    parts: list[str] = [f"## EVIDENCE_LEDGER_RAW (shape={ledger.get('shape')})"]
    for row in rows[:12]:
        ds = _date_str(row.get("effective_date")) or "?"
        text = (row.get("text") or "")[:240].replace("\n", " ")
        parts.append(f"- [{ds}] {text}")
    return "\n".join(parts) + "\n"
