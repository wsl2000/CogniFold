# Codex Round 7 — Dialogue R3 (final discussion before ship)

R2 ship plan accepted. Implementation-level questions before I code.

## What I'm locking in

- 4 emitters: f420262d, f420262c, 9ee3ecd6, 09ba9854_abs
- 1 retrieval expansion: 7fce9456 property-specific second-pass
- Defer: a3838d2b, 81507db6
- Protect: 08f4fc43 stays at "30 days" or "31 inclusive"
- Row contract upfront in `_normalize_rows`
- Mandatory offline smoke pre-screen before any paid run

## R3 implementation questions

### Q1 — Row contract regex precision

You named tags: `has_planning`, `has_booking_verb`,
`has_completed_travel`, `has_completed_view`, `has_negation`,
`effective_date`, `date_source`, `date_plausible`, `airlines`,
`scope_anchors`.

I'll implement:

```python
_BOOKING_VERBS = re.compile(
    r"\b(?:booked|reserved|will\s+(?:fly|take|board)|"
    r"got\s+(?:a|the)\s+(?:flight|booking)|"
    r"(?:going|gonna)\s+to\s+(?:fly|take))\b", re.I)

_COMPLETED_TRAVEL = re.compile(
    r"\b(?:flew\s+with|flew\s+on|"
    r"flight\s+(?:was|got|landed|arrived)|"
    r"boarded|took\s+(?:the|a)\s+flight|"
    r"(?:my|our)\s+flight\s+(?:was|landed))\b", re.I)

_COMPLETED_VIEW = re.compile(
    r"\b(?:viewed|saw|toured|visited|checked\s+out|"
    r"walked\s+through|open\s+house|did\s+a\s+walkthrough|"
    r"put\s+in\s+an\s+offer|offer\s+(?:was\s+)?rejected)\b", re.I)

_NEGATION = re.compile(
    r"\b(?:didn't|did\s+not|never|missed|skipped|"
    r"couldn't\s+make\s+it|didn't\s+attend|"
    r"cancelled|canceled|postponed)\b", re.I)

_AIRLINES_RE = re.compile(
    r"\b(JetBlue|Delta|United(?:\s+Airlines)?|American\s+Airlines|"
    r"Southwest|Spirit|Alaska|Frontier|Hawaiian)\b", re.I)

_DEST_NOUNS_RE = re.compile(
    r"\b(?:hotel|home|office|airport|station|terminal|"
    r"city\s+center|downtown)\b", re.I)
```

Two questions:
- a) Is the booking pattern too narrow? Should it include "received the
  itinerary" / "the ticket says" or are those completed-travel?
- b) For `_COMPLETED_VIEW` — "drove by" / "looked at the outside" —
  is that completed or rejected from property count?

### Q2 — `effective_date` plausibility fallback

You said: "live code currently prefers `inline_date` over
`session_date`, and that is unsafe for `gpt4_f420262c` because the
Delta row carries an inline `2023-10-05` under a question whose
TODAY is `2023-03-02`".

Proposed logic:

```python
def _compute_effective_date(text, session_date, question_date):
    inline = _extract_inline_date(text, fallback_year=question_date.year if question_date else None)
    if inline is None:
        return session_date, "session"
    # Plausibility: inline must be ≤ question_date AND within ±2 years
    if question_date and inline > question_date:
        return session_date, "session (inline_future_rejected)"
    if question_date and (question_date - inline).days > 730:
        return session_date, "session (inline_too_old)"
    return inline, "inline"
```

Question: does that match what you intended? Specifically, for
the Delta row with inline `2023-10-05` under question_date
`2023-03-02`, my logic falls back to session_date because
`inline > question_date`. Confirm.

### Q3 — gpt4_f420262d: AA delay/recovery row

You said: "The `American Airlines` delay/recovering row should
survive". Could you sketch the text shape of that row so I know what
my completed-travel regex must match? E.g., is it:
- "My AA flight from BOS to MIA was delayed and we recovered…"
- "AA flight 207 landed at 9pm after a 3-hour delay…"

Without the actual phrase I can't validate my regex. If you can't
recall the exact text, please tell me what verb / noun pattern
typically appears so I can widen.

### Q4 — gpt4_f420262c: Spirit row signature

You said: "It will include `Spirit` from a planned spring-break
trip". So the Spirit row contains booking language. My
`_BOOKING_VERBS` regex catches "booked" / "will fly". Will it catch
"planned" or "considering Spirit for spring break"? I'll add
"considering" / "planning to take" to `_BOOKING_VERBS` and rely on
`has_completed_travel` being the affirmative gate. Confirm.

### Q5 — 9ee3ecd6 conflicting target totals

You said: "If you see conflicting target totals or conflicting
current balances, return `None`; do not guess".

How do I check "conflicting"? Two user-role rows say "300 points
to redeem" — same value → fine. But what if one says "300" and
another says "500" (maybe two different rewards)? My
implementation:

```python
targets = set()
currents = set()
for r in user_rows:
    m = re.search(r"\b(\d+)\s+points?\s+(?:to\s+redeem|for.*free)", text)
    if m: targets.add(int(m.group(1)))
    m = re.search(r"\b(?:I have|i'm at|my balance is|currently at)\s+(\d+)", text)
    if m: currents.add(int(m.group(1)))
if len(targets) != 1 or len(currents) != 1: return None
target = targets.pop()
current = currents.pop()
```

OK?

### Q6 — 7fce9456 retrieval second-pass score formula

You wrote: "Score with base overlap plus bonuses for property-type
nouns and completed-view / offer verbs. Do not sort on bonus alone."

My implementation idea:

```python
def property_question_second_pass(question, graph):
    if not re.search(r"propert(?:y|ies)|home|house|condo|townhouse", question, re.I):
        return []
    if not re.search(r"view|viewed|offer", question, re.I):
        return []
    EXPAND_KW = ["viewed","view","saw","toured","walkthrough","checked out",
                 "visited","open house","put in an offer","offer rejected",
                 "bungalow","condo","townhouse","listing","bedroom"]
    qtoks = _expanded_query_tokens(question)
    all_chunks = _event_chunks(graph) + _concept_chunks(graph)
    scored = []
    for c in all_chunks:
        text_low = c["text"].lower()
        base = _score(qtoks, text_low)
        bonus = sum(0.3 for kw in EXPAND_KW if kw in text_low)
        if base + bonus > 0.1:
            scored.append((c, base, bonus))
    # Sort by (base + bonus), but require base ≥ 0.05 so we never sort on bonus alone
    scored = [(c,b,bo) for c,b,bo in scored if b >= 0.05]
    scored.sort(key=lambda x: (x[1] + x[2], x[0].get("date") or ""), reverse=True)
    return [c for c, _, _ in scored[:12]]
```

Question: is `base ≥ 0.05` the right cutoff? Too strict and Oakwood
gets dropped; too lax and assistant advice slips in. What's your
floor?

### Q7 — Offline smoke pre-screen scope

I'll build `scripts/smoke_pre_screen.py` that:
1. Loads `runs/iter31_tr_round1/hypothesis.jsonl` + iter27 baseline
2. For each smoke qid: extract graph_hits + question + question_date
3. Run the new emitters against stored full_context (no LLM)
4. Assert:
   - f420262d → "American Airlines"
   - f420262c → "JetBlue, Delta, United, American Airlines" (or
     formatted order string)
   - 9ee3ecd6 → "100"
   - 09ba9854_abs → "The information provided is not enough."
   - a3838d2b → None (defer)
   - 81507db6 → None (defer)
   - b46e15ed, gpt4_d6585ce9, 08f4fc43 → None (let resolver/reader)
   - 7fce9456 → retrieval pool contains Oakwood + Cedar Creek + 1BR
     + 2BR + Brookside (5 properties)

Pass criterion: 8/8 assertions hold.

Question: should I also check that on N=500 the emitters never fire
spuriously? I have iter27 wrong_cases + iter27 correct hyps —
running the emitters offline against all 500 stored contexts would
catch "emitter fires on a non-target case and emits wrong answer".
Worth the dev time (maybe 30 min)?

## Wrap

After this R3 reply I'll start coding. Goal:
1. `_normalize_rows` with row contract
2. 4 emitters with case-specific guards
3. 7fce9456 second-pass retrieval
4. `scripts/smoke_pre_screen.py` offline harness
5. Run pre-screen
6. If 8/8 → re-smoke v4 on commonstack
7. If v4 hits 7-8/10 → TR+MS N=266 verification

Maximum effort. This is the last dialogue before code freeze.
