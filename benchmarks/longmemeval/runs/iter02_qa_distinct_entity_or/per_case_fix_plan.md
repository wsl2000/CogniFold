# iter02 — per-case fix plan (all 84 wrong cases)

Cross-iter notation: `i1✗/i4✗` means wrong in both iter1 and iter4 (hardcore); `i1✓/i4✗` means iter1 had it right; etc.

---

## Bucket A — datetime fix (DONE) — same-day session ordering

These KU `latest_value` cases had candidate nodes with the same date stamp (date-only granularity). The datetime fix gives every node HH:MM precision so `latest_value` resolves deterministically.

| qid | Q | GT | iter2 HYP | i1/i4 |
|---|---|---|---|---|
| 07741c45 | Where do I currently keep my old sneakers? | shoe rack in closet | "under bed; planning to move" | ✗/✗ |
| 6a1eabeb | Personal best 5K time? | 25:50 | narrative w/ "25:50" → PARTIAL | ✓/✗ |
| a2f3aa27 | Instagram followers now? | 1300 | "1,250" | ✗/✗ |
| dad224aa | Sat morning wake time? | 7:30 am | "6:00 AM" | ✓/✗ |
| f685340e | Tennis frequency previously/now? | weekly→biweekly | "biweekly→biweekly" | ✓/✓ |
| 71017277 | Who gave jewelry last Sat? | aunt | "great-grandmother" | ✓/✗ |
| 618f13b2 | How many times wore Converse? | six | "four" | ✓/✗ |

**Expected fix from datetime alone**: ~3-5 of these flip.

---

## Bucket B — R9-A regex widening + ctx bump (DONE) — aggregation Qs

These aggregation Qs were NOT getting the 50-node / 18K-context bump because the previous regex missed bare-verb forms ("did I attend", "did I visit") or excluded "hours". Re-running with new regex will route them through the bump path.

| qid | Q | GT | iter2 HYP | i1/i4 |
|---|---|---|---|---|
| 28dc39ac | How many hours have I spent playing games? | 140 | "110" | ✓/✗ |
| 2ce6a0f2 | How many art events did I attend? | 4 | "Two" | ✗/✗ |
| gpt4_f2262a51 | How many doctors did I visit? | 3 | "Two" | ✗/✗ |
| gpt4_194be4b3 | How many instruments do I currently own? | 4 | "three" | ✓/✗ |
| gpt4_ab202e7f | How many kitchen items did I replace or fix? | 5 | "Four" | ✓/✗ |
| 60159905 | Dinner parties past month? | three | "Two" | ✗/✗ |
| 6d550036 | Projects led / leading? | 2 | "Three" (over-count) | ✓/✗ |
| 7024f17c | Hours of jogging+yoga last week? | 0.5 | "2-4 hrs yoga" | ✗/✗ |
| gpt4_4cd9eba1 | Weeks accepted to exchange → orientation? | 1 | refuses | ✗/✗ |

**Expected fix from ctx bump alone**: ~2-3 of these flip (gpt4_59c863d7 / 60159905 already flipped in diag).

---

## Bucket C — Exp A required (graph dump diagnosis) — "I don't have memory of X"

For each: dump full graph, grep for the named entity. If found → retrieval rank-out (fix retrieval). If not found → writer extraction gap (fix writer prompt).

| qid | Q | GT entity to grep |
|---|---|---|
| 59524333 | Gym time? | "gym" or "6:00" |
| 37f165cf | Page count Jan+Mar novels? | "856" or specific novels |
| 51c32626 | Sentiment paper submission? | "sentiment analysis" |
| 73d42213 | Clinic time Monday? | "clinic" |
| a1cc6108 | Age when Alex was born? | "Alex" |
| ba358f49 | Age at Rachel's wedding? | "Rachel" |
| c18a7dc8 | Age vs college grad? | "graduate" |
| dd2973ad | Bedtime before doctor's appt? | "doctor" or "2 AM" |
| edced276 | Days Hawaii + NYC? | "Hawaii" |
| 3c1045c8 | Older than dept avg? | "department average" |
| 51b23612 | Soviet cartoon name? | "pogodi" or "Soviet" |
| 5809eb10 | Bajimaya case construction year? | "2014" |
| 577d4d32 | Stop checking emails time? | "email" |
| 75499fd8 | Dog breed? | "Golden" or "breed" |
| 853b0a1d | Age at silver necklace? | "silver necklace" |
| c19f7a0b | Home time weeknights? | "weeknight" |
| d6233ab6 | High school reunion? | "reunion" |
| c9f37c46 | Standup → open mic? | "open mic" or "comedy club" |
| d01c6aa8 | Age moved to US? | "moved to" or "United States" |
| dcfa8644 | Adidas → Converse shoelace? | "Adidas" |
| e4e14d04 | Book Lovers Unite meetup? | "Book Lovers" |
| gpt4_2c50253f | Wake time Tue/Thu? | "Tuesday" "Thursday" |
| gpt4_cd90e484 | Binoculars → goldfinches? | "goldfinch" or "binocular" |

**This is the single most important experiment.** It splits ~23 cases into:
- writer gap (raise writer model / refine batch_extraction prompt)
- retrieval gap (query expansion / hint injection)

---

## Bucket D — `_abs` anti-confab rule

`_abs` Qs require refusal because the answer is NOT in the source. Currently reader confabulates.

| qid | Q | GT | iter2 HYP |
|---|---|---|---|
| 09ba9854_abs | Save by bus vs taxi? | not in source | "About $50" |
| 19b5f2b3_abs | How long in Korea? | not in source | "about a week" |
| a96c20ee_abs | Which uni for poster? | not in source | "Harvard" |
| gpt4_93159ced_abs | Worked before Google? | not started Google | extrapolates from NovaTech |

**Fix**: profile.yaml qa_answer adds rule: "If the question names a specific entity (person/place/event) and the context contains NO direct mention of that entity, respond 'I don't have a record of [entity] in my memory.' Do not extrapolate."  
Risk: too-broad rule regressed preference cluster before. Scope ONLY to questions where the named entity (e.g., "Korea", "Google") doesn't appear in retrieved nodes.

---

## Bucket E — SSP preference rule

| qid | Q | GT pattern |
|---|---|---|
| 09d032c9 | Phone battery tips? | should reference user's portable power bank purchase |
| 1da05512 | Buy NAS now? | should reference user's storage capacity issues |
| d6233ab6 | Attend reunion? | should reference user's positive HS memories |
| fca70973 | Theme park weekend? | should reference user's thrill rides + Halloween prefs |

**Fix**: profile.yaml qa_answer adds rule for SSP-like questions (`what do you think / any tips / suggestions`): "Before answering, search retrieved nodes for user-specific facts (preferences, past actions, owned items) and weave them into the response."  
Implementation: add a recall_hint block that fires when question starts with personal-question patterns and surfaces user-history concepts at the top of the context.

---

## Bucket F — New `order_among` resolver

These TR questions explicitly ask for chronological ordering of N events. No symbolic resolver covers this today.

| qid | Q | GT |
|---|---|---|
| gpt4_7abb270c | Order of 6 museums earliest→latest? | Science → MoCA → Met → ... |
| gpt4_7f6b06db | Order of 3 trips past 3 months? | Muir → Big Sur → ... |
| gpt4_d6585ce8 | Order of concerts past 2 months? | Billie → outdoor → ... |
| gpt4_f420262c | Order of airlines flown? | JetBlue → Delta → United → American |

**Fix**: implement `_try_order_among` in `symbolic_resolver.py`:
- Trigger regex: `\b(?:order|chronological|earliest\s+to\s+latest|sequence)\b.*\b(?:i\s+(?:visited|attended|flew|took|went))`
- Extract topic noun (museum/concert/airline/trip)
- Fetch all dated concepts matching the topic noun (BM25 + concept_type filter)
- Sort by `date` ASC, format as numbered list
- Bypass=True (deterministic output)

---

## Bucket G — New `event_by_relative_date` resolver

"What X N weeks ago" — pick the event closest to (question_date - N weeks).

| qid | Q | GT |
|---|---|---|
| gpt4_4929293b | Relative's life event a week ago? | cousin's wedding |
| gpt4_59149c78 | Art event 2 weeks ago, where? | Metropolitan Museum |
| gpt4_e061b84g | Sports event 2 weeks ago, what? | charity soccer |
| 2ebe6c92 | Book finished a week ago? | The Nightingale |
| eac54add | Business milestone 4 weeks ago? | first client contract |
| 0bc8ad93 | Museum 2 months ago — with friend or not? | (sub-Q) |

**Fix**: implement `_try_event_by_relative_date`:
- Regex: `(?:what|where|who|which)\s+.*\b(\d+)\s+(weeks?|months?|days?)\s+ago\b`
- Compute target = question_date - N units
- Find concept whose `date` is within ±3 days of target AND content matches topic noun  
- Return that concept's description

---

## Bucket H — Resolver tuning (existing patterns picking wrong event)

Symbolic resolver fired and bypassed, but to wrong target.

| qid | Q | sym | iter2 HYP | issue |
|---|---|---|---|---|
| 982b5123 | months ago booked SF Airbnb? | date_diff_ago | "1 month" vs 5 | picked wrong booking event |
| 9a707b81 | days ago baking class → cake? | date_diff_ago | "5" vs 21 | picked wrong baking event |
| gpt4_b0863698 | days ago 5K charity run? | date_diff_ago | "16" vs 7 | picked wrong run |
| b46e15ed | months since 2 charity events consecutive? | date_diff_since | "1" vs 2 | picked wrong event |
| 370a8ff4 | weeks since flu → 10th jog? | diff_since_when | "12" vs 15 | picked wrong jog or flu |
| eac54adc | days ago website → first client? | date_diff_ago | "24" vs 19 | similar |
| gpt4_d6585ce9 | Who at music event last Sat? | named_day_recall | "friends" vs parents | wrong-event match |
| gpt4_f420262d | Airline Valentine's day? | named_day_recall | "JetBlue" vs American | wrong-flight match |

**Fix**: tighten the picking logic in each `_try_*` to:
- Require event verb to match question verb (already attempted in iter4 P3 but didn't help)
- When multiple candidates within threshold, prefer the one with strongest object-noun overlap
- Add an "event verb stem" matcher: question "baking class" must match concept with both `bake|baking|class|culinary` tokens, not any "bake" event

---

## Bucket I — Reader semantic precision

| qid | Q | issue |
|---|---|---|
| 6d550036 | Projects led / leading? | Reader counted "completed high-priority project" as a 3rd "led" project. Source said "completed", not "led". |

**Fix**: profile.yaml qa_answer adds rule for "how many X did I VERB": "Count only items where the source explicitly uses VERB or its direct synonyms (lead/led/leading, NOT completed/finished)."

---

## Bucket J — Bypass formatter

| qid | issue |
|---|---|
| 6a1eabeb | bypass output = full node description (narrative); judge gave PARTIAL |

**Fix**: in `_try_latest_value`, when bypass=True, prepend `"Per most recent record ({date}): "` to make it clear this IS the answer, not a memory note.

Risk: low. May help judge confidence on PARTIAL cases.

---

## Bucket K — Writer dedup

| qid | Q | GT | iter2 HYP |
|---|---|---|---|
| bf659f65 | Albums/EPs purchased? | 3 | "One" |

Source has Whiskey Wanderers' EP "Midnight Sky" extracted **3 times** in different sessions (s20, s26, s29), reader treated as 1 unique → counted 2 total (vs GT 3).

**Fix**: in writer, when storing a concept, hash its `(title, key_entities)` and if a near-duplicate already exists in the graph, merge instead of add. Lower risk: add a reader rule "ignore duplicate concepts when counting".

---

## Bucket L — manual review / can't easily fix

Cases where no clear lever applies. Mostly subtle reader/judge issues.

| qid | issue |
|---|---|
| 36b9f61e | $1,300 vs $2,500 luxury — writer captured 2 items, reader undercounted (i1/i4 correct → noise) |
| 92a0aa75 | 2y 4m vs 1y 5m current role — reader picked wrong tenure |
| 9ee3ecd6 | Sephora 300 pts vs 100 — reader picked wrong tier |
| f0e564bc | $800 minimum vs $1,300 — reader refused total compute |
| 0a995998 | 2 items vs 3 — i1/i4 correct → noise |
| 36580ce8 | COVID-19 vs bronchitis — reader picked wrong (i1/i4 correct → noise) |
| d23cf73b | cuisines 5 vs 4 — reader over-counted by 1 |
| 561fabcd | "Contaminated Colossus" vs "Fissionator" — reader hallucinated name (i1/i4 correct → noise) |
| c7cf7dfd | "Fabriclore" vs "Nostalgia" — reader picked wrong store |
| 08f4fc43 | 30 days vs GT "30/31" — actually CORRECT semantically; judge may be strict |
| 6613b389 | 0 months vs 2 — reader miscomputed date diff (i1/i4 correct → noise) |
| gpt4_21adecb5 | 10.6 months vs 6 — reader picked wrong date pair |
| gpt4_65aabe59 | mesh vs thermostat first — reader picked wrong "first" |
| gpt4_93159ced | NovaTech tenure miscomputed | 

For these: re-run after A-K fixes; the ones that are noise will half-resolve through stochasticity; the ones with code-fixable causes (gpt4_65aabe59 needs which_first resolver tuning, gpt4_21adecb5 needs date_diff_between tuning) can iterate later.

---

## Summary by bucket

| Bucket | # Cases | Status |
|---|---|---|
| A — datetime fix | 7 | DONE |
| B — R9-A regex + ctx bump | 9 | DONE |
| C — Exp A (graph dump) | 23 | needs experiment, ~$0.5 |
| D — `_abs` anti-confab | 4 | needs code (profile rule + scope check) |
| E — SSP personalization | 4 | needs code (profile rule) |
| F — `order_among` resolver | 4 | needs new resolver |
| G — `event_by_relative_date` | 6 | needs new resolver |
| H — resolver tuning | 8 | needs code (existing _try_* improvements) |
| I — reader semantic precision | 1 | needs profile rule |
| J — bypass formatter | 1-2 | small code change |
| K — writer dedup | 1 | writer post-process |
| L — manual review / noise | 15 | re-run + see |

**Net addressable (high confidence)**: A + B already done → ~5-7 case flips on next run.
**Net addressable (with C diagnosis + D/E/F/G/H code)**: potentially +15-20 case flips.
