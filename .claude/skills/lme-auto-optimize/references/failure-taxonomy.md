# LongMemEval Failure Taxonomy

Updated from iter27 N=500 wrong_cases.json (66 wrongs / 13.2%).

## Cluster ID convention

Single uppercase letter scoped to question type:
- `MS-A`, `MS-B`, ...  for multi-session
- `TR-A`, `TR-B`, ...  for temporal-reasoning
- `KU-A`, ...           for knowledge-update

Cross-references use full `<type>-<letter>` (e.g. `TR-A`).

## MS (multi-session)  30/500 wrong on iter27

### MS-A — UNDERCOUNT (22 cases)
Reader sees N relevant entities but only counts M < N.
Specific patterns:
- "How many different X did I do" — picks unique entities, misses some
- "How much total did I spend on X" — sums some line items, misses others
- "How many X events" — undercount by 1 typically

Root cause: reader stops scanning context after first 2-3 hits; W1
typed-attr nodes crowd top-K (no longer present in iter31).

Fix recipe: qa_answer **EXHAUSTIVE-COUNT** rule — explicit
"scan entire context, list each, tally". Already in iter31 qa_answer.

### MS-B — REFUSAL-WITH-DATA (4 cases)
Reader refuses ("I don't have a memory of") when the answer is
derivable from context (e.g., AGE = current_age − tenure).

Fix recipe: qa_answer **AGE-INFERENCE** + **NO-REFUSAL-extended**
rules. Already in iter31 qa_answer.

### MS-C — WRONG-WINNER (2 cases)
"Which X had the most Y" — reader picks wrong winner because
candidate concept with higher numeric Y is more recent / closer to
question topic.

Fix recipe: not addressed yet. Single-iter ceiling.

### MS-D — _abs misses refusal (2 cases)
Question is `_abs`-suffixed and answer should be "info not enough"
but reader confabulates from related entity.

Fix recipe: qa_answer **_abs-WORKED-EXAMPLES**. Already in iter31.

## TR (temporal-reasoning)  26/133 wrong on iter27

### TR-A — duration_since_start (10 cases)
"How long had I been X-ing when Y happened?"

Two sub-causes:
- **TR-A1 refusal**: writer didn't extract a START concept for X.
- **TR-A2 wrong duration**: resolver picks LATEST X mention but
  GT expects EARLIEST mention.

Fix recipe:
1. Writer prompt rule 4 (iter31): when user says
   "I started X / began X / joined Y", emit concept with
   `activity_start: true, activity: "<X>", start_date: <date>`.
2. Resolver `_find_is_start_concept` Pass 3 (iter31): fall back
   to EARLIEST dated concept matching activity noun when no
   marked start concept exists.

### TR-B — order_among (4 cases)
"Order of N events earliest → latest"

Root cause: `_try_order_among` finds < N candidates due to BM25
top-K cutoff or strict verb filter; resolver bypass=True forces
incomplete list as answer.

Fix recipe: iter31 forces bypass=False for order lists with >3
items. Reader sees the list as a HINT and re-orders from the
chronological_temporal block.

### TR-C — named_day disambig (3 cases)
"What X on Valentine's day / last Saturday" — multiple candidates
land on same day, resolver picks wrong one by BM25 score.

Fix recipe: iter31 named_day_recall returns multi-candidate hint
when 2+ candidates share the target day, bypass=False.

### TR-D — date_diff off-by-one (3 cases)
"How many days between X and Y" — reader picks exclusive count,
GT accepts both but judge marked exclusive as wrong on phrasing.

Fix recipe: qa_answer **INCLUSIVE-BOUNDARY** worked example.
Already in iter31.

### TR-E — refusal-with-data (5 cases)
Overlaps with TR-A1. Same fix.

### TR-F — derived-time (1 case)
"What time on T/Th" — relative offset from baseline (7:00 −
0:15 = 6:45).

Fix recipe: qa_answer **DERIVED-TIME-WORKED-EXAMPLE**. Already
in iter31.

### TR-G — miscellaneous (3 cases)
- `_abs` (1): not refusing when should
- `which_first` (1): wrong direction
- `relative_ago_recall` (1): picked planning concept not event

Fix recipe:
- Disable `which_first`, `relative_ago_recall` (already done in
  iter31)
- qa_answer **COMPARATIVE EARLIER=FIRST** worked example
- qa_answer **BOOKING vs PLANNING** distinction
- qa_answer **_abs both-entities check**

All already in iter31.

## KU (knowledge-update)  5/500 wrong on iter27

### KU-A — supersession confusion (2 cases)
Reader picks outdated value when context has both old and new.

Fix recipe: Mastra reader rules already cover this — iter27
already at 93.6% KU.

### KU-B — count-undercount (2 cases)
Like MS-A but for KU. Covered by MS-A fix.

### KU-C — latest_value mis-pick (1 case)
Resolver `_try_latest_value` picks "User mentioned X" concept
rather than the actual X value.

Fix recipe: not addressed; single-iter ceiling.

## SSU / SSP / SSA

These three rarely fail on iter27 baseline (3/70, 2/30, 0/56
respectively). Failures are usually judge variance.

DO NOT optimize for these — moves the needle by < 0.5pp at most.
