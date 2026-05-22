"""LongMemEval symbolic resolver — ToMi-style deterministic answer for the
temporal-reasoning + knowledge-update query patterns.

Modeled after `src/cognifold/symbolic/belief_tracker.py::SymbolicBeliefTracker.
answer_belief_query()`: pattern-match the query → look up dated concepts in the
graph → compute a deterministic answer string. Returns `None` on no-match so
the runner falls through to the LLM reader.

Targeted query patterns (LongMemEval 26.6% temporal-reasoning + 15.6%
knowledge-update = 42.2% of the dataset):

| Pattern             | Trigger                                              |
|---------------------|------------------------------------------------------|
| date_diff_between   | "how many days/weeks/months between X and Y"         |
| date_diff_ago       | "how many days/weeks/months ago did I X"             |
| date_diff_since     | "how many months/years have passed since X"          |
| which_first         | "which event happened first, X or Y"                 |
| chronological_order | "which N events happened in order from first to last"|
| latest_value        | "what was my (most recent / personal best / current) X" |
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from cognifold.graph.store import ConceptGraph
from cognifold.models.node import NodeType

# ---------------------------------------------------------------------------
# Lexical matching utilities
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "did", "does",
    "for", "from", "had", "has", "have", "he", "her", "here", "his", "how",
    "i", "in", "into", "is", "it", "its", "many", "me", "my", "of", "on", "or",
    "she", "since", "so", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "to", "today", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "why", "will", "with", "you", "your",
    "passed", "between", "ago", "after", "before", "until", "long", "much",
    "did", "happen", "happened", "event", "events", "day", "days", "week", "weeks",
    "month", "months", "year", "years", "first", "last", "latest", "recent",
    "most", "current", "personal", "best", "earliest", "now", "currently",
    "more", "less",
}


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in _STOPWORDS]


def _phrase_score(phrase: str, node_text: str) -> float:
    """Recall-based score: fraction of phrase tokens present in node text."""
    p = set(_tokenize(phrase))
    if not p:
        return 0.0
    n = set(_tokenize(node_text))
    return len(p & n) / len(p)


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


@dataclass
class _Concept:
    node_id: str
    title: str
    description: str
    date: datetime | None
    raw_text: str  # title + description for matching


class LongMemEvalSymbolicResolver:
    """Pattern-match LongMemEval queries against graph time-anchored concepts
    and return a deterministic answer, or None to fall through to LLM."""

    # Time-unit conversions (in days)
    _UNIT_DAYS = {
        "day": 1, "days": 1,
        "week": 7, "weeks": 7,
        "month": 30, "months": 30,
        "year": 365, "years": 365,
    }

    # ----------------------- public API ----------------------------

    def __init__(self, graph: ConceptGraph, question_date: datetime | None = None) -> None:
        self.graph = graph
        self.question_date = question_date
        self._concepts: list[_Concept] = self._index_concepts()

    def _index_concepts(self) -> list[_Concept]:
        """Pull every CONCEPT (and EVENT with a description) node along with
        its session date from the `date` data field we wrote in
        process_session_batch()."""
        out: list[_Concept] = []
        for n in self.graph.get_all_nodes():
            if n.type not in (NodeType.CONCEPT, NodeType.EVENT):
                continue
            date_str = n.data.get("date") or n.data.get("extracted_at") or n.data.get("timestamp")
            dt = None
            if date_str:
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", ""))
                except Exception:
                    pass
            title = n.data.get("title", "")
            desc = n.data.get("description") or n.data.get("content") or ""
            # Strip the [YYYY-MM-DD] prefix we added in process_session_batch
            # (now lives on the title; old runs may have it on the description).
            date_re = r"^\s*\[\d{4}-\d{2}-\d{2}\]\s*"
            title_stripped = re.sub(date_re, "", title)
            desc_stripped = re.sub(date_re, "", desc)
            out.append(_Concept(
                node_id=n.id, title=title_stripped, description=desc_stripped, date=dt,
                raw_text=f"{title_stripped} {desc_stripped}",
            ))
        return out

    def resolve(self, query: str) -> dict[str, Any] | None:
        """Try each pattern in order; return {answer, reasoning, pattern}."""
        for pattern_name, fn in [
            ("date_diff_between",  self._try_diff_between),
            ("which_first",        self._try_which_first),
            ("chronological_order", self._try_chronological_order),
            ("date_diff_ago",      self._try_diff_ago),
            ("date_diff_since",    self._try_diff_since),
            ("latest_value",       self._try_latest_value),
            ("topic_recall",       self._try_topic_recall),
        ]:
            try:
                result = fn(query)
            except Exception:
                continue
            if result is not None:
                return {"pattern": pattern_name, **result}
        return None

    # ----------------------- matching helpers ----------------------------

    def _topk_dated(
        self,
        phrase: str,
        k: int = 3,
        min_score: float = 0.34,
        concepts_only: bool = False,
    ) -> list[tuple[float, _Concept]]:
        """Top-K *dated* concepts by phrase score.

        Default includes both CONCEPT and EVENT nodes — date_diff resolvers
        need EVENT raw-turn content to find specific entity names. Set
        concepts_only=True for resolvers whose answer is rendered verbatim
        (latest_value broad trigger, topic_recall), to avoid dumping noisy
        raw turn text into the bypass path.
        """
        scored = []
        for c in self._concepts:
            if c.date is None:
                continue
            if concepts_only and c.node_id.startswith("evt-"):
                continue
            s = _phrase_score(phrase, c.raw_text)
            if s >= min_score:
                scored.append((s, c))
        scored.sort(key=lambda x: (-x[0], x[1].date or datetime.min))
        return scored[:k]

    def _best_concept(self, phrase: str) -> _Concept | None:
        hits = self._topk_dated(phrase, k=1)
        return hits[0][1] if hits else None

    # ----------------------- pattern resolvers ----------------------------

    # Patterns matching event phrases after key prepositions
    _BETWEEN_RE = re.compile(
        r"between\s+(.+?)\s+and\s+(.+?)(?:\?|$)", re.IGNORECASE
    )

    def _try_diff_between(self, query: str) -> dict | None:
        m = self._BETWEEN_RE.search(query)
        if not m:
            return None
        phrase_a = m.group(1).strip()
        phrase_b = m.group(2).strip()
        a = self._best_concept(phrase_a)
        b = self._best_concept(phrase_b)
        if not a or not b or a.date is None or b.date is None:
            return None
        # Detect unit from question
        unit = self._detect_unit(query, default="day")
        diff_days = abs((a.date - b.date).days)
        diff_units = max(1, round(diff_days / self._UNIT_DAYS[unit])) if unit != "day" else diff_days
        unit_word = unit if diff_units != 1 else unit.rstrip("s")
        return {
            "answer": f"{diff_units} {unit_word}",
            "reasoning": (
                f"Event A '{a.title}' on {a.date.date()}; "
                f"Event B '{b.title}' on {b.date.date()}; "
                f"interval = {diff_days} days."
            ),
            "bypass": True,
        }

    _WHICH_FIRST_RE = re.compile(
        r"which\s+(?:event\s+)?happened\s+first(?:,)?\s+(.+?)\s+or\s+(.+?)(?:\?|$)",
        re.IGNORECASE,
    )

    def _try_which_first(self, query: str) -> dict | None:
        m = self._WHICH_FIRST_RE.search(query)
        if not m:
            return None
        phrase_a = m.group(1).strip()
        phrase_b = m.group(2).strip()
        a = self._best_concept(phrase_a)
        b = self._best_concept(phrase_b)
        if not a or not b or a.date is None or b.date is None:
            return None
        first = a if a.date <= b.date else b
        return {
            "answer": first.title,
            "reasoning": (
                f"'{a.title}' on {a.date.date()} vs '{b.title}' on {b.date.date()}. "
                f"Earlier = '{first.title}'."
            ),
            "bypass": True,
        }

    _ORDER_HEAD_RE = re.compile(
        r"which\s+(?:two|three|four|five|2|3|4|5)\s+events\s+happened\s+in\s+(?:the\s+)?order\s+from\s+first\s+to\s+last\s*:?\s*",
        re.IGNORECASE,
    )

    def _try_chronological_order(self, query: str) -> dict | None:
        m = self._ORDER_HEAD_RE.search(query)
        if not m:
            return None
        # Take the part after the head; strip trailing punctuation
        tail = query[m.end():].rstrip("?. ").strip()
        # Split on ", and" first, then on ","
        parts = re.split(r"\s*,\s*and\s+|\s+and\s+|\s*,\s*", tail)
        parts = [p.strip().rstrip(".") for p in parts if p.strip()]
        if len(parts) < 2:
            return None
        resolved: list[tuple[str, _Concept]] = []
        for phrase in parts:
            c = self._best_concept(phrase)
            if c is None or c.date is None:
                return None
            resolved.append((phrase, c))
        resolved.sort(key=lambda x: x[1].date or datetime.min)
        ordered_phrases = [phrase for phrase, _ in resolved]
        # Render English: "First, A, then B, and lastly C."
        if len(ordered_phrases) == 3:
            sentence = (
                f"First, {ordered_phrases[0]}; then {ordered_phrases[1]}; "
                f"and lastly {ordered_phrases[2]}."
            )
        else:
            sentence = " → ".join(ordered_phrases)
        reasoning = "; ".join(
            f"'{p}' = {c.date.date()}" for p, c in resolved if c.date
        )
        return {"answer": sentence, "reasoning": reasoning, "bypass": True}

    _DIFF_AGO_RE = re.compile(
        r"how\s+many\s+(day|days|week|weeks|month|months|year|years)\s+ago\s+(?:did|have|has)\s+(?:i|my|we)\s+(.+?)(?:\?|$)",
        re.IGNORECASE,
    )

    def _try_diff_ago(self, query: str) -> dict | None:
        if self.question_date is None:
            return None
        m = self._DIFF_AGO_RE.search(query)
        if not m:
            return None
        unit = m.group(1).lower()
        unit_key = unit if unit.endswith("s") else unit + "s"
        phrase = m.group(2).strip()
        c = self._best_concept(phrase)
        if c is None or c.date is None:
            return None
        diff_days = (self.question_date - c.date).days
        if diff_days < 0:
            return None
        diff_units = max(1, round(diff_days / self._UNIT_DAYS[unit_key]))
        unit_word = unit_key if diff_units != 1 else unit_key.rstrip("s")
        return {
            "answer": f"{diff_units} {unit_word}",
            "reasoning": (
                f"'{c.title}' on {c.date.date()}; "
                f"question date {self.question_date.date()}; "
                f"diff = {diff_days} days."
            ),
            "bypass": True,
        }

    _DIFF_SINCE_RE = re.compile(
        r"how\s+many\s+(day|days|week|weeks|month|months|year|years)\s+(?:have\s+passed\s+)?since\s+(?:i|my|we)\s+(.+?)(?:\?|$)",
        re.IGNORECASE,
    )

    def _try_diff_since(self, query: str) -> dict | None:
        if self.question_date is None:
            return None
        m = self._DIFF_SINCE_RE.search(query)
        if not m:
            return None
        unit = m.group(1).lower()
        unit_key = unit if unit.endswith("s") else unit + "s"
        phrase = m.group(2).strip()
        c = self._best_concept(phrase)
        if c is None or c.date is None:
            return None
        diff_days = (self.question_date - c.date).days
        if diff_days < 0:
            return None
        diff_units = max(1, round(diff_days / self._UNIT_DAYS[unit_key]))
        unit_word = unit_key if diff_units != 1 else unit_key.rstrip("s")
        return {
            "answer": f"{diff_units} {unit_word}",
            "reasoning": (
                f"'{c.title}' on {c.date.date()}; "
                f"question date {self.question_date.date()}; "
                f"diff = {diff_days} days."
            ),
            "bypass": True,
        }

    _LATEST_RE = re.compile(
        r"(?:what|where|how\s+often|how\s+many)\s+(?:was|is|are|do|did|have)?\s*(?:my|i)?\s*"
        r"(?:most\s+recent|recent|latest|current|personal\s+best|new(?:est)?)\s+(.+?)(?:\?|$)",
        re.IGNORECASE,
    )

    # Broad trigger — fires when ANY "recent/latest/currently" keyword appears
    # anywhere in the question (not just adjacent to the question subject).
    # Catches third-person patterns: "Where did Rachel move after her recent X".
    _LATEST_TRIGGER = re.compile(
        r"\b(?:most\s+recent(?:ly)?|recent(?:ly)?|latest|lately|currently|now\b|new(?:est)?|"
        r"personal\s+best)\b",
        re.IGNORECASE,
    )

    def _try_latest_value(self, query: str) -> dict | None:
        # Strict regex preferred — clearer topic phrase + safe to bypass.
        m = self._LATEST_RE.search(query)
        if m:
            topic = m.group(1).strip()
            hits = self._topk_dated(topic, k=5, min_score=0.30, concepts_only=True)
            if not hits or hits[0][0] < 0.40:
                return None
            latest = max(hits, key=lambda x: x[1].date or datetime.min)[1]
            return {
                "answer": latest.description.strip() or latest.title,
                "reasoning": (
                    f"Topic '{topic[:80]}'; top match score={hits[0][0]:.2f}; "
                    f"latest concept = '{latest.title}' on {latest.date.date() if latest.date else '?'}."
                ),
                "bypass": True,
            }
        # Broad trigger fallback — inject only (no bypass), LLM picks.
        if self._LATEST_TRIGGER.search(query):
            topic = query.strip("?. ").strip()
            hits = self._topk_dated(topic, k=5, min_score=0.50, concepts_only=True)
            if not hits or hits[0][0] < 0.60:
                return None
            latest = max(hits, key=lambda x: x[1].date or datetime.min)[1]
            return {
                "answer": latest.description.strip() or latest.title,
                "reasoning": (
                    f"Topic '{topic[:80]}' (broad trigger); top match score={hits[0][0]:.2f}; "
                    f"latest concept = '{latest.title}' on {latest.date.date() if latest.date else '?'}."
                ),
                "bypass": False,
            }
        return None

    # Topic-recall: questions like "going back to our previous conversation
    # about X, remind me Y" / "I'm planning to revisit X, you mentioned Y".
    # These fail in plain retrieval because the topic phrase gets diluted by
    # other concepts. Match the trigger then run a recall-biased BM25 over
    # concepts and return the top match's description.
    _TOPIC_RECALL_TRIGGER = re.compile(
        r"(?:previous\s+conversation|we\s+(?:talked|discussed|had\s+a\s+(?:chat|conversation))\s+about|"
        r"remind\s+me|you\s+(?:mentioned|told\s+me|suggested)|"
        r"going\s+back\s+to\s+our|i'm\s+planning\s+to\s+revisit|"
        r"i\s+was\s+wondering\s+if\s+you\s+could\s+remind|"
        r"earlier\s+(?:i|we|you)\s+(?:told|mentioned|discussed))",
        re.IGNORECASE,
    )

    def _try_topic_recall(self, query: str) -> dict | None:
        if not self._TOPIC_RECALL_TRIGGER.search(query):
            return None
        topic = query.strip("?. ").strip()
        # Concept-only + reasonable threshold. Topic-recall is a catch-all so
        # we accept lower phrase overlap than latest_value's broad trigger,
        # but still require ≥30% phrase tokens to be present in the concept.
        hits = self._topk_dated(topic, k=5, min_score=0.30, concepts_only=True)
        if not hits:
            return None
        # Confidence gate: weak match → hand off to LLM rather than dump a
        # noisy concept that happens to share a noun with the query.
        if hits[0][0] < 0.40:
            return None
        top = hits[0][1]
        return {
            "answer": top.description.strip() or top.title,
            "reasoning": (
                f"Topic-recall match (score={hits[0][0]:.2f}): "
                f"'{top.title}' on {top.date.date() if top.date else '?'}."
            ),
            # Never bypass — BM25 lexical match can pick wrong concept
            # (Italian restaurant: La Pergola vs Roscioli). Inject + let LLM choose.
            "bypass": False,
        }

    # ----------------------- misc helpers ----------------------------

    def _detect_unit(self, query: str, default: str = "day") -> str:
        q = query.lower()
        for u in ("years", "year", "months", "month", "weeks", "week", "days", "day"):
            if re.search(r"\b" + u + r"\b", q):
                return u if u.endswith("s") else u + "s"
        return default


def render_symbolic_block(result: dict[str, Any]) -> str:
    """Render the resolver output as a fenced markdown block.

    Two flavors keyed by `bypass`:
    - bypass=True  → SYMBOLIC_ANSWER (deterministic — reader restates verbatim).
    - bypass=False → RECALL_HINT (BM25 best guess — reader verifies & may override).
    """
    if result.get("bypass", True):
        return (
            "## SYMBOLIC_ANSWER (computed deterministically from graph time anchors)\n"
            f"**Pattern**: {result.get('pattern', '?')}\n"
            f"**Answer**: {result.get('answer', '')}\n"
            f"**Reasoning**: {result.get('reasoning', '')}\n"
        )
    return (
        "## RECALL_HINT (best lexical match for the question — verify against context)\n"
        f"**Pattern**: {result.get('pattern', '?')}\n"
        f"**Candidate**: {result.get('answer', '')}\n"
        f"**Reasoning**: {result.get('reasoning', '')}\n"
    )
