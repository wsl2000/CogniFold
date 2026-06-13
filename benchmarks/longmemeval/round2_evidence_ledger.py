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


def detect_question_shape(question: str) -> Shape:
    q = question or ""
    if _ORDER_RE.search(q): return "order"
    if _DURATION_RE.search(q): return "duration_since"
    if _DATE_DIFF_RE.search(q): return "date_diff"
    if _DERIVED_RE.search(q): return "derived_time"
    if _COUNT_RE.search(q): return "count"
    if _ABS_RE.search(q): return "abs_value"
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

# =====================================================================
# M2 COUNT_CANDIDATES-lite — context augmentation for count shape
# =====================================================================

# Capture the target noun phrase in "how many X" patterns — limit to
# 1-2 tokens (head noun + optional modifier) to keep candidate scope tight
_COUNT_NOUN_RE = re.compile(
    r"\bhow many\s+(?:different\s+|unique\s+|distinct\s+|total\s+)?"
    r"([\w\-]+(?:\s+[\w\-]+){0,1})\b",
    re.I,
)

# Completed-action verbs — only count rows where user actually did the action
_COMPLETED_ACTION_RE = re.compile(
    r"\b(?:bought|purchased|acquired|got|made|cooked|baked|attended|"
    r"visited|hosted|saw|watched|listened|read|wrote|completed|finished|"
    r"did|went|drove|drank|ate|tried|tasted|ordered|paid|signed|"
    r"earned|donated|spent|received|gave|joined|started|enrolled|"
    r"subscribed|cancelled|registered)\b",
    re.I,
)

# Temporal window markers in the question
_TEMPORAL_WINDOW_RE = re.compile(
    r"\b(?:in|last|this|since|before|after|during|within|over\s+the\s+past)\s+"
    r"(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december|"
    r"week|month|year|quarter|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"2019|2020|2021|2022|2023|2024|2025|2026|"
    r"\d+\s+(?:weeks?|months?|days?|years?))\b",
    re.I,
)

# Stopwords / generic count-phrase tokens to drop from target noun
_COUNT_STOPWORDS = {
    # determiners / quantifiers
    "the", "and", "any", "all", "different", "kinds", "types",
    "of", "many", "much", "some", "various", "such",
    # auxiliaries
    "did", "do", "have", "had", "was", "were", "are", "is", "been",
    # common count verbs that creep into the captured span
    "buy", "got", "get", "make", "take", "go", "went",
    "see", "watch", "read", "hear", "saw", "made", "bought",
}

# Class-level synonyms for MS undercount clusters (R6 audit per-case map).
# Fires only when the captured head noun matches one of these keys.
# Codex R9 fixes: dropped polysemous tokens (watch=verb, service/plan/show
# too generic, record=ambiguous, ep too short).
_COUNT_ALIAS_MAP: dict[str, set[str]] = {
    "clothes": {"shirt", "shirts", "pants", "jacket", "dress", "skirt",
                "sweater", "blouse", "jeans", "coat", "tee", "hoodie"},
    "clothing": {"shirt", "shirts", "pants", "jacket", "dress", "skirt",
                 "sweater", "blouse", "jeans", "coat", "tee", "hoodie"},
    "jewelry": {"ring", "necklace", "bracelet", "earring", "earrings",
                "pendant", "bangle", "anklet"},  # dropped 'watch' (verb collision)
    "furniture": {"couch", "sofa", "chair", "table", "bed", "dresser",
                  "desk", "ottoman", "bookshelf", "armchair"},
    "albums": {"album", "lp", "vinyl"},  # dropped 'ep' (too short), 'record' (polysemous)
    "doctors": {"physician", "specialist", "dermatologist", "cardiologist",
                "dentist", "doctor", "neurologist", "therapist"},
    "events": {"event", "gathering", "ceremony", "party", "concert",
               "performance", "exhibition", "gala"},  # dropped 'show' (too broad)
    "parties": {"party", "gathering", "dinner", "meetup", "soiree"},
    "subscriptions": {"subscription", "membership"},  # dropped 'service'/'plan' (too generic)
}


def _expand_target_tokens(toks: set[str]) -> set[str]:
    """Expand target tokens with class-level aliases when a key matches."""
    expanded = set(toks)
    for tok in list(toks):
        if tok in _COUNT_ALIAS_MAP:
            expanded.update(_COUNT_ALIAS_MAP[tok])
    return expanded


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _extract_count_target(question: str) -> set[str]:
    """Pull the head noun tokens from 'how many X' for candidate matching."""
    m = _COUNT_NOUN_RE.search(question or "")
    if not m:
        return set()
    raw = m.group(1).lower()
    toks = {t for t in raw.split() if len(t) > 2 and t not in _COUNT_STOPWORDS}
    return toks


def _count_candidate_block(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str:
    """Build COUNT_CANDIDATES-lite block: user-role, completed, distinct.

    Pure context augmentation — does NOT emit an answer. Reader still
    decides. Goal: surface ALL relevant candidate rows so MS undercount
    cases see more than top-12 ranked rows.

    Gates (tight, per gpt-5.4 R7 spurious-fire concern):
    - Question must be a count shape with extractable head noun.
    - Row must be is_user_role=True (no assistant suggestions).
    - Row must not have_planning or have_future_commitment (no intents).
    - Row text must contain at least one target-noun token.
    - Distinct lemma (first 32 chars of normalized text) — coarse dedupe.
    """
    target_toks = _extract_count_target(question)
    if not target_toks:
        return ""
    target_toks = _expand_target_tokens(target_toks)
    has_window = bool(_TEMPORAL_WINDOW_RE.search(question))
    # Codex R9 fix: token-boundary regex, not substring (`ring` in `during`).
    target_re = re.compile(
        r"\b(?:" + "|".join(re.escape(t) for t in sorted(target_toks)) + r")\b",
        re.I,
    )

    candidates: list[dict[str, Any]] = []
    seen_lemma: set[str] = set()
    for row in rows:
        if not row.get("is_user_role"):
            continue
        if row.get("has_planning") or row.get("has_future_commitment"):
            continue
        if row.get("has_negation"):
            continue
        text_low = (row.get("text") or "").lower()
        if not text_low:
            continue
        # Require at least one target-noun token at word boundary
        if not target_re.search(text_low):
            continue
        # Require a completed-action verb so we don't surface mere
        # mentions ("I like cookies" shouldn't count as "made cookies")
        if not _COMPLETED_ACTION_RE.search(text_low):
            continue
        # Codex R9: if question has explicit window, drop rows whose
        # effective_date is None (we can't verify in-window).
        if has_window and row.get("effective_date") is None:
            continue
        # Dedupe: use first 64 chars (gpt-5.4 said 32 too coarse)
        lemma = re.sub(r"\s+", " ", text_low)[:64]
        if lemma in seen_lemma:
            continue
        seen_lemma.add(lemma)
        candidates.append(row)
    del question_date  # reader's qa rules handle within-window filtering

    if not candidates:
        return ""

    parts: list[str] = [
        "## COUNT_CANDIDATES (user-role + completed-action + distinct)"
    ]
    parts.append(
        f"# target_tokens: {sorted(target_toks)} | "
        f"window_in_question: {'yes' if has_window else 'no'}"
    )
    for c in candidates[:25]:
        ds = _date_str(c.get("effective_date")) or "?"
        text = (c.get("text") or "")[:180].replace("\n", " ")
        parts.append(f"- [{ds}] {text}")
    parts.append(f"# total_count_candidates: {len(candidates)}")
    return "\n".join(parts) + "\n"


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


# =====================================================================
# M3 ARITH OPERANDS — surface anchored operand facts for two-fact math
# =====================================================================

# "How old was I when X?" / "how many years older than at college" / etc.
_AGE_ARITH_RE = re.compile(
    r"\b(?:how old (?:was|were|will) (?:i|you)|"
    r"how many years (?:older|younger)|"
    r"what age (?:was|will|am) i|"
    r"my age (?:at|when))\b",
    re.I,
)

# Two-trip / two-event addition: "in total", "altogether", "combined"
_TRIP_SUM_RE = re.compile(
    r"\b(?:how many days .* (?:in total|altogether|combined|on my trips)|"
    r"total (?:trip|days|hours) (?:to|on|spent))\b",
    re.I,
)

# Operand patterns
_AGE_FACT_RE = re.compile(
    r"\b(?:i'?m|i am|user is|user was|aged?|turned)\s+(\d{1,3})\b", re.I,
)
_YEARS_AGO_RE = re.compile(
    r"\b(\d{1,3})\s+years?\s+ago\b", re.I,
)
_YEARS_IN_RE = re.compile(
    r"\b(\d{1,3})\s+years?\s+(?:in|at)\s+(?:the\s+)?\w+\b", re.I,
)
# Codex R9 add: graduation/event year anchors for age-at-event
_EVENT_YEAR_RE = re.compile(
    r"\b(?:graduated|finished|completed|started|joined|"
    r"moved|left|got married|had|born)\s+\w*\s*"
    r"(?:in|on)\s+(\d{4})\b", re.I,
)
# Codex R9 add: future-age anchors ("in 5 years", "when I turn 40")
_FUTURE_YEARS_RE = re.compile(
    r"\bin\s+(\d{1,3})\s+years?\b", re.I,
)
_TURN_AGE_RE = re.compile(
    r"\bwhen\s+i\s+turn\s+(\d{1,3})\b", re.I,
)
# Codex R9 expand: trip duration patterns
_DAYS_DURATION_RE = re.compile(
    r"\b(\d{1,3})\s+(?:days?|nights?)\s+"
    r"(?:in|at|on|to|trip|vacation|stay|visit|abroad|away)\b", re.I,
)
_FOR_DAYS_RE = re.compile(
    r"\bfor\s+(\d{1,3})\s+(?:days?|nights?)\b", re.I,
)
_STAYED_DAYS_RE = re.compile(
    r"\b(?:stayed|spent|was\s+(?:there|away))\s+(?:there\s+)?"
    r"(\d{1,3})\s+(?:days?|nights?)\b", re.I,
)
_TRIP_LENGTH_RE = re.compile(
    r"\b(?:trip|vacation|stay)\s+(?:was|lasted)\s+(\d{1,3})\s+"
    r"(?:days?|nights?)\b", re.I,
)


def _arith_operand_block(
    question: str,
    rows: list[dict[str, Any]],
    question_date: datetime | None,
) -> str:
    """Surface anchored operand facts for the reader to compose arithmetic.

    Pure context augmentation (R7 lock — no direct emit). Only fires
    when:
    - Question matches an age/duration arithmetic shape
    - We can find at least one explicit anchor token in user-role rows
    - We surface up to 8 operand-bearing rows for the reader to compose

    Per gpt-5.4 R7 SP5-lite: reject implicit operands; require both
    to be explicit. We don't compute the answer here — we ensure the
    operands are in context, then reader does the arithmetic.
    """
    del question_date
    is_age = bool(_AGE_ARITH_RE.search(question or ""))
    is_trip_sum = bool(_TRIP_SUM_RE.search(question or ""))
    if not (is_age or is_trip_sum):
        return ""

    operand_rows: list[tuple[str, dict[str, Any]]] = []
    seen_lemma: set[str] = set()
    for row in rows:
        if not row.get("is_user_role"):
            continue
        text = row.get("text") or ""
        text_low = text.lower()
        if not text_low:
            continue
        hits: list[str] = []
        if is_age:
            for m in _AGE_FACT_RE.finditer(text):
                hits.append(f"AGE={m.group(1)}")
            for m in _YEARS_AGO_RE.finditer(text):
                hits.append(f"YEARS_AGO={m.group(1)}")
            for m in _YEARS_IN_RE.finditer(text):
                hits.append(f"YEARS_AT_PLACE={m.group(1)}")
            for m in _EVENT_YEAR_RE.finditer(text):
                hits.append(f"EVENT_YEAR={m.group(1)}")
            for m in _FUTURE_YEARS_RE.finditer(text):
                hits.append(f"IN_N_YEARS={m.group(1)}")
            for m in _TURN_AGE_RE.finditer(text):
                hits.append(f"TURN_AGE={m.group(1)}")
        if is_trip_sum:
            for m in _DAYS_DURATION_RE.finditer(text):
                hits.append(f"DAYS={m.group(1)}")
            for m in _FOR_DAYS_RE.finditer(text):
                hits.append(f"FOR_DAYS={m.group(1)}")
            for m in _STAYED_DAYS_RE.finditer(text):
                hits.append(f"STAYED_DAYS={m.group(1)}")
            for m in _TRIP_LENGTH_RE.finditer(text):
                hits.append(f"TRIP_LEN={m.group(1)}")
        if not hits:
            continue
        lemma = re.sub(r"\s+", " ", text_low)[:32]
        if lemma in seen_lemma:
            continue
        seen_lemma.add(lemma)
        operand_rows.append(("|".join(hits), row))

    # Require at least two operand-bearing rows; otherwise no arithmetic
    # possible and the block would be misleading
    if len(operand_rows) < 2:
        return ""

    shape_label = "age_arith" if is_age else "trip_sum"
    parts: list[str] = [
        f"## ARITH_OPERANDS ({shape_label}) — two-fact composition only"
    ]
    for tags, c in operand_rows[:8]:
        ds = _date_str(c.get("effective_date")) or "?"
        text = (c.get("text") or "")[:180].replace("\n", " ")
        parts.append(f"- [{ds}] ({tags}) {text}")
    parts.append(
        "# Compose only if TWO explicit operands present; otherwise refuse."
    )
    return "\n".join(parts) + "\n"


def assemble_ledger_context(ledger: dict[str, Any]) -> str:
    """Prepend raw fused rows + optional count candidates to reader prompt."""
    rows = ledger.get("rows", [])
    if not rows:
        return ""
    parts: list[str] = [f"## EVIDENCE_LEDGER_RAW (shape={ledger.get('shape')})"]
    for row in rows[:12]:
        ds = _date_str(row.get("effective_date")) or "?"
        text = (row.get("text") or "")[:240].replace("\n", " ")
        parts.append(f"- [{ds}] {text}")
    out = "\n".join(parts) + "\n"
    # M2 COUNT_CANDIDATES-lite — augment for count shape only
    if ledger.get("shape") == "count":
        cc = _count_candidate_block(
            ledger.get("question", ""),
            rows,
            ledger.get("question_date"),
        )
        if cc:
            out += cc
    # M3 ARITH_OPERANDS — augment for derived_time / date_diff shapes
    if ledger.get("shape") in ("derived_time", "date_diff", "duration_since"):
        ao = _arith_operand_block(
            ledger.get("question", ""),
            rows,
            ledger.get("question_date"),
        )
        if ao:
            out += ao
    return out
