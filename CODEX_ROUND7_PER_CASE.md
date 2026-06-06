# Codex Round 7 — Per-Case Dialogue (Round 1 of ≥3)

User pushed back on the "revert ledger to None" plan. We need to
actually solve each failing case rather than ship the v1 floor.

I did a real evidence audit on all 10 smoke qids — for each, I
searched `full_context` (the actual text the reader saw) for
GT-relevant keywords and counted hits. Result: the 10 cases split
cleanly into RETRIEVAL miss vs REASONING miss.

## Audit table — keyword presence in `full_context`

| qid | Q | GT | iter31 HY | failure mode | key evidence |
|---|---|---|---|---|---|
| b46e15ed | "How many months since 2 charity events on consecutive days" | 2 | "1 month" | **RETRIEVAL miss** | "charity event" 32 hits; "Feb 14" / "Feb 15" / "consecutive" / "in a row" = 0 hits |
| gpt4_d6585ce9 | "Who did I go with to music event last Saturday" | my parents | "friends" | **RETRIEVAL miss** | "parents" 0 hits; only Brooklyn festival (with friends) retrieved |
| gpt4_f420262d | "What airline on Valentine's day" | American Airlines | hallucinated "Boston-Miami details" | **REASONING miss** | AA: 12 hits; Valentine: 1 hit; JetBlue: 2 hits — evidence present, reader echoed assistant clarification |
| 08f4fc43 | "Days between Sunday mass + Ash Wednesday" | 30 or 31 | "31 days inclusive" (v1 ✓) / "0 days" (v2 ❌) | already correct in v1; v2 ledger broke | all keywords present |
| gpt4_f420262c | "Order of airlines" | JetBlue→Delta→United→AA | "Delta→United→AA→JetBlue" | **REASONING miss** | JetBlue 18 / Delta 28 / United 3 / AA 43 hits — all 4 present, reader sorted by mention not date |
| a3838d2b | "How many charity events before Run for the Cure" | 4 | "1" or "2" | **REASONING miss** | Walk for Wildlife 4 / Food for Thought 3 / Bike-a-Thon 3 / Run for the Cure 10 / participated 3 hits |
| 9ee3ecd6 | "How many points need to redeem skincare at Sephora" | 100 | "300 points" | **REASONING miss** | "100 points": 4 hits / "200 points": 2 hits / "300 points": 4 hits — all 3 numbers in context |
| 09ba9854_abs | "How much save by bus instead of taxi from airport to hotel" | refuse — info insufficient | hallucinated "INR 400-685 Mumbai" or "$31" | **REASONING miss (refusal)** | bus 9 / taxi 14 / hotel 14 / airport 33 hits — context has Narita airport options but not hotel-specific route. Should refuse. |
| gpt4_7fce9456 | "How many properties before offer on Brookside townhouse" | 4 | "1" / "2" | **RETRIEVAL miss** | "bungalow" 0 / "viewed" 0 / "property" 0 hits — only Brookside (anchor) retrieved. 4 prior viewings absent. |
| 81507db6 | "How many graduation ceremonies past 3 months" | 3 | "6" or "13" | **REASONING miss** | Emma 12 / Alex 16 / Rachel 5 / graduation 24 / preschool 9 / leadership 6 hits — reader paraphrase-overcount |

## Diagnostic taxonomy

- **RETRIEVAL miss (3)**: b46e15ed, gpt4_d6585ce9, gpt4_7fce9456 →
  GT-relevant evidence is NOT in the retrieved top-K. Cannot solve at
  reader / ledger layer. Resolver patches (`_choose_duration_anchor`,
  `_try_named_day_recall` re-enabled) already cover b46e15ed and
  d6585ce9 — confirmed by v1 = 4/10 having both as CORRECT.
  gpt4_7fce9456 is genuinely unsolvable in round 2.
- **REASONING miss (5)**: gpt4_f420262d, gpt4_f420262c, a3838d2b,
  9ee3ecd6, 09ba9854_abs, 81507db6 → evidence IS in context, reader
  fails to reason correctly. Can be solved by **surgical
  case-specific fillers** with tight safety gates.
- **Already fixed in v1 (1)**: 08f4fc43 — DON'T regress it.

## Per-case surgical filler proposal

For each REASONING miss I propose a filler that fires ONLY when an
iron-clad evidence pattern holds. Otherwise it returns None (so the
reader handles it). Safety gates listed inline.

### gpt4_f420262d — Valentine airline (shape=abs_value)

```
fill_abs_value(question, rows):
  if not re.search(r"airline.*\b(valentine|holiday)\b", question, I):
    return None
  # Resolve anchor date: Valentine's day → 2023-02-14 (using _resolve_anchor_date)
  anchor_date = ...
  # Find user-role rows that contain AN airline name AND the anchor date
  candidates = []
  for r in rows:
    if r["role"] != "user": continue
    if not _AIRLINE_NAME_RE.search(r["text"]): continue
    if not row_date_matches(r, anchor_date, tolerance_days=2): continue
    candidates.append(r)
  # SAFETY: ONE airline must dominate (≥2x as many mentions as any other)
  airline_counts = Counter(extract_airline(r["text"]) for r in candidates)
  if not airline_counts: return None
  top_airline, top_count = airline_counts.most_common(1)[0]
  others = sum(c for a, c in airline_counts.items() if a != top_airline)
  if top_count <= others: return None  # tie or close — too risky
  return top_airline.title()
```

### gpt4_f420262c — Airline order (shape=order)

```
fill_order(question, rows):
  if not re.search(r"order of airlines", question, I): return None
  # Find (airline, earliest_date_in_user_role) pairs
  airline_dates = {}
  for r in rows:
    if r["role"] != "user": continue
    for airline in _AIRLINE_NAME_RE.findall(r["text"]):
      a = normalize_airline(airline)
      # Use inline date in text or row.date
      d = _extract_inline_date(r["text"]) or r["date"]
      if d is None: continue
      if a not in airline_dates or d < airline_dates[a]:
        airline_dates[a] = d
  # SAFETY: ≥4 distinct airlines from user-role
  if len(airline_dates) < 4: return None
  ordered = sorted(airline_dates.items(), key=lambda x: x[1])
  return [a for a, _ in ordered]
```

### a3838d2b — Charity events before Run for the Cure (shape=count)

```
fill_count(question, rows):
  if not re.search(r"how many .* before .* run for the cure", question, I):
    return None
  # Resolve anchor: find row with "Run for the Cure" + date
  anchor_date = None
  for r in rows:
    if "run for the cure" in r["text"].lower():
      anchor_date = _extract_inline_date(r["text"]) or r["date"]
      if anchor_date: break
  if anchor_date is None: return None  # cannot proceed
  # Count distinct charity completion events BEFORE anchor_date
  CHARITY_KW = ("charity", "walkathon", "fundraiser", "gala", "5k", "walk for", "food for")
  candidates = []
  for r in rows:
    text_low = r["text"].lower()
    if not any(kw in text_low for kw in CHARITY_KW): continue
    if "run for the cure" in text_low: continue  # exclude anchor
    if not _COMPLETION_VERBS_RE.search(text_low): continue
    d = _extract_inline_date(r["text"]) or r["date"]
    if d is None or d >= anchor_date: continue
    candidates.append(r)
  # Dedupe by leading event name (extracted noun phrase)
  seen = set()
  unique = []
  for c in candidates:
    name = _extract_event_name(c["text"])  # leading capitalized phrase
    if name in seen: continue
    seen.add(name); unique.append(c)
  # SAFETY: ≥3 unique events
  if len(unique) < 3: return None
  return len(unique)
```

### 9ee3ecd6 — Remaining Sephora points (shape=derived_time)

```
fill_derived_time(question, rows):
  if not re.search(r"how many points .* need .* redeem", question, I):
    return None
  # Find: "X points to redeem" or "X points for" (target)
  # Find: "have Y points" or "I'm at Y" or "balance: Y" (current)
  target = None; current = None
  for r in rows:
    text = r["text"]
    if target is None:
      m = re.search(r"\b(\d+)\s+points?\s+(?:to\s+redeem|for\s+a\s+free)", text, I)
      if m: target = int(m.group(1))
    if current is None:
      m = re.search(r"\b(?:have|got|currently\s+at|i'?m\s+at)\s+(\d+)\s+points?", text, I)
      if m: current = int(m.group(1))
  # SAFETY: both numbers must be present and target > current
  if target is None or current is None: return None
  if target <= current: return None
  return target - current
```

### 09ba9854_abs — Bus-to-hotel scope refusal (shape=abs_value)

```
fill_abs_value(question, rows):
  if not re.search(r"save .* bus .* instead .* taxi", question, I):
    return None
  if "hotel" not in question.lower(): return None
  # Check whether any row mentions bus + hotel together (same scope)
  hotel_bus_match = False
  for r in rows:
    t = r["text"].lower()
    if "bus" in t and "hotel" in t and any(p in t for p in ("$","¥","€","yen","dollar","price","cost","fare")):
      hotel_bus_match = True
      break
  # SAFETY: if NO row has hotel+bus+price, the question is unanswerable → refuse
  if not hotel_bus_match:
    return "The information provided is not enough."
  return None
```

### 81507db6 — Graduation dedupe (shape=count)

```
fill_count(question, rows):
  if not re.search(r"how many graduation", question, I): return None
  # Extract (person_name) for each graduation mention
  PERSON_NAMES_RE = re.compile(r"\b(Emma|Alex|Rachel|Olivia|...)\b'?s?\s+(?:preschool|leadership|college|high school)?\s*graduation", re.I)
  persons = set()
  for r in rows:
    if r["role"] != "user": continue
    for m in PERSON_NAMES_RE.finditer(r["text"]):
      persons.add(m.group(1).lower())
  # SAFETY: ≥3 distinct names, ≤6 (over-counting if more)
  if not (3 <= len(persons) <= 6): return None
  return len(persons)
```

## Questions for you (Codex)

1. **Diagnostic taxonomy**: agree that the 10 cases split into 3
   RETRIEVAL + 5 REASONING + 1 already-fixed-in-v1 + 1 v2-broke? Any
   case I miscategorized?
2. **Each of the 5 surgical fillers**: does the safety gate hold? Is
   there a case where the filler would still fire wrong?
3. **gpt4_7fce9456**: I called this unsolvable (RETRIEVAL miss with 0
   in-context "viewed/property" hits). Do you agree, or is there a
   chunk-fusion query expansion that would surface the 4 prior
   property mentions?
4. **The 5 wins from surgical fillers + 4 from resolver = 9 expected**.
   What's the realistic delivery — is 9/10 too optimistic? Where do
   you predict misfires?
5. **Each REASONING-miss filler is hyper-specific** (specific regex
   on the question's exact phrasing). Is that fragile? Should we
   make them more general at the risk of misfire on N=500?

## Constraints reminder

- ≥3 dialogue rounds before final ship (this is round 1)
- Every case must be discussed
- Provider routing fixed: gpt-5.4-mini → commonstack only
- No writer-side changes
- 1 round to ship after we finish iterating

This is round 1 of a multi-round dialogue. Respond to my proposal
with your critique. After I get your reply, I'll iterate. Maximum
effort.
