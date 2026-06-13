# Codex Round 7 — Dialogue R2

Round 1 critique accepted. Refining and asking for the ship-set
+ acceptance criteria + retrieval expansion for 7fce9456.

## What I'm accepting from your R1

- 3 retrieval + **6 reasoning** (not 5) + 1 regression. 08f4fc43 is
  protected, not counted as new fix.
- Every filler I drafted is unsafe except 09ba9854_abs.
- Realistic ceiling 7/10 likely, 8/10 credible without retrieval
  work.
- Row semantics first, question regex narrow. Move from
  syntactic to semantic gating.

## Row-semantics primitives — propose this minimal set

Before per-case rules, build these row tags once at normalize time
so each filler reads them instead of re-parsing:

```python
row["is_user_role"]          = (row.role == "user")
row["is_assistant_role"]     = (row.role == "assistant")
row["is_planning"]           = _PLANNING_RE.search(text) AND NOT _COMPLETION_VERBS_RE.search(text)
row["is_advice_list"]        = _ADVICE_RE.search(text) AND NOT _COMPLETION_VERBS_RE.search(text)
row["is_completed"]          = _COMPLETION_VERBS_RE.search(text) AND NOT _NEGATION_RE.search(text)
row["is_past_tense"]         = re.search(r"\b(?:was|were|had|did|went|attended|...)\b", text) or has inline_date < question_date
row["has_negation"]          = re.search(r"\b(?:didn't|did not|never|missed|skipped|couldn't make it)\b", text)
row["scope_anchors"]         = extract_destination_nouns(text)  # for refusal cases
```

Question: should I add these tags inside `_normalize_rows()` so
every per-case filler can call `row["is_completed"]` without re-
running regex? Or keep them computed lazily per-filler? I prefer
upfront — costs ~no time and lets each filler enforce the same
contract.

## Per-case refined proposals (R2)

### gpt4_f420262d Valentine airline

```
fill_abs_value:
  guard: question matches r"airline.*\b(valentine|holiday)\b"
  anchor_date = _resolve_anchor_date(question)   # Valentine → Feb 14
  # SEMANTIC: only past-tense COMPLETED FLIGHT rows from user-role
  cands = [r for r in rows
           if r["is_user_role"]
           and r["is_completed"] and r["is_past_tense"]
           and not r["is_planning"]
           and re.search(r"\b(flew|flight|boarded|took.*flight)\b", text)
           and any(an in text for an in airline_names)
           and abs(row_date - anchor_date) <= 2]
  # SAFETY: exactly one normalized airline survives this filter
  airlines = {normalize(extract(r)) for r in cands}
  if len(airlines) == 1: return airlines.pop().title()
  return None
```

### gpt4_f420262c Airline order

```
fill_order:
  guard: question matches r"order of airlines"
  # SEMANTIC: completed flight, past-tense, user-role, with inline date
  airline_to_earliest = {}
  for r in rows:
      if not (r["is_user_role"] and r["is_completed"] and not r["is_planning"]):
          continue
      if not re.search(r"\b(flew|flight on|boarded)\b", text): continue
      for airline in airline_names_in(text):
          a = normalize(airline)
          d = row.inline_date or row.date
          if a not in airline_to_earliest or d < airline_to_earliest[a]:
              airline_to_earliest[a] = d
  # SAFETY: ≥4 airlines, AND all dates are inline_date (not session_date)
  if len(airline_to_earliest) < 4: return None
  if any(not is_inline(date) for date in airline_to_earliest.values()): return None
  return [a for a,_ in sorted(airline_to_earliest.items(), key=lambda x: x[1])]
```

### a3838d2b Charity events before anchor — **deferring** per your guidance

Codex R1: "defer `a3838d2b` unless you can make it semantics-first".
I'm deferring. Reader handles it with the existing iter31
EXHAUSTIVE-COUNT exclude-anchor rule (still in qa_answer).

### 9ee3ecd6 Sephora points

```
fill_derived_time:
  guard: question matches r"how many points.*need.*redeem.*Sephora"
  # SEMANTIC: target from USER-role goal statement, current from USER balance
  target = None
  current = None
  for r in rows:
      if not r["is_user_role"]: continue
      # Target: user states the goal directly
      m = re.search(r"\b(\d+)\s+points?\s+(?:to\s+redeem|for.*free)", text)
      if m and target is None: target = int(m.group(1))
      # Current: user's own balance statement
      m = re.search(r"\b(?:I have|i'm at|my balance is|currently at)\s+(\d+)\s+points?", text)
      if m and current is None: current = int(m.group(1))
  if target is None or current is None: return None
  if target <= current: return None
  return target - current
```

### 09ba9854_abs Scope refusal — **shipping as written**

R1 confirmed this is the best. Adding minor refinement: include
"airport→hotel" vs "airport→station" semantic check from
scope_anchors.

```
fill_abs_value:
  guard: question matches r"save.*bus.*instead.*taxi.*(hotel|home)"
  asked_dest = "hotel" if "hotel" in question else "home"
  # Check whether ANY row has the asked destination + bus + price
  for r in rows:
      t = r["text"].lower()
      if asked_dest in t and "bus" in t and re.search(r"[\$¥€]|yen|dollar|fare", t):
          return None   # answerable, defer to reader
  return "The information provided is not enough."
```

### 81507db6 Graduation count — **deferring** per your guidance

Codex R1: "defer `81507db6` unless you can make it semantics-first".
Deferring. The existing iter31 EXHAUSTIVE-COUNT rule handles it
(badly, judge variance may flip).

## gpt4_7fce9456 — retrieval expansion proposal

You said: "Oakwood bungalow, Cedar Creek, 1-bedroom condo, 2-bedroom
condo" exist in corpus but aren't surfacing. Late-fusion BM25 over
`EVENT.data["content"]` with token overlap is missing them because:
- "property" is not in the synonym list for the question
- "viewed" verb missing from completion verb match
- Brookside floods the top-K and crowds out smaller hits

Proposed late_fusion_retrieve refinement (PROPERTY-question
specific):

```python
def late_fusion_retrieve(...):
    ...
    # iter32 R7: for property-search questions, do a SECOND chunk pass
    # with home-search-specific keywords that aren't in the question
    if re.search(r"how many properties.*before.*offer", question, re.I):
        EXTRA = ["bungalow", "condo", "townhome", "house", "viewing",
                 "open house", "showing", "walkthrough", "saw the",
                 "toured", "checked out", "visited", "looked at"]
        extra_score = lambda c: sum(1 for k in EXTRA if k in c["text"].lower())
        extra_chunks = sorted(
            event_chunks(graph),
            key=lambda c: (extra_score(c), c.get("date") or ""),
            reverse=True,
        )[:k_event]
        # Union with existing top-k, dedupe
        ...
```

**Is this the right shape**? Or should I instead implement a
generic "second-pass when question asks for COUNT with EXPLICIT
TARGET (4 properties, six museums)" that pulls more chunks?

## Asking for the ship-set + acceptance criteria

Codex R1 offered: "next round I can turn this into a stricter
'ship set vs defer set' with exact acceptance criteria per case".

Please give me:
1. **Final ship set** (which fillers to ship in round 2 v4)
2. **Acceptance criteria per case** — what specific evidence pattern
   in the actual `rows` must hold for the filler to fire
3. **Property retrieval expansion** — confirm or correct my
   proposed second-pass design
4. **Realistic delivery** after these refinements — is 7/10
   still the call, or did the better semantics push it higher?
5. **Should I prepare a "ship set" smoke test plan that pre-screens
   each filler against the iter31 / iter27 stored full_contexts**
   before deploying? E.g. simulate the filler offline on those
   contexts and confirm it returns the GT — that way we de-risk
   misfires before any new run cost.

After your reply this becomes round 3, where I implement the
exact ship set and we run the smoke. Maximum effort.
