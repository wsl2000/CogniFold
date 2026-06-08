# MS Iter19 Failure Analysis

Branch baseline:
- Branch: `ms-only-iter19-medium`
- Base commit: `baade50`
- Meaning: revert to the `iter18-19` code state that produced the
  public `iter19` N=500 result (`86.8%` strict overall, `109/133 =
  82.0%` on MS per `HISTORY.md`).

Key baseline check:
- Working tree for the key iter19 files is clean on this branch:
  `benchmarks/longmemeval/run_eval.py`,
  `benchmarks/longmemeval/symbolic_resolver.py`,
  `configs/longmemeval_profile.yaml`,
  `scripts/parallel_longmemeval.sh`,
  `src/cognifold/agent/config.py`.
- `baade50` already contains:
  - W1 typed attributes as an opt-in flag
  - W2 event-date pass as an opt-in flag, OFF by default
  - the iter05-17 reader hint blocks (`TEMPORAL_FACTS`,
    `MOST RECENT MATCHES`, `CLOCK_TIME_MATCHES`, proper-noun block)

## Overall read

Iter19 has 24 MS wrong cases. They are not one bug cluster.

Breakdown:
- 12 `temporal_miss`
- 11 `retrieval_irrelevant`
- 1 uncategorized `_abs` scope-mismatch refusal

Best way to think about them:
- High-confidence already-addressable with narrow deterministic logic:
  `gpt4_7fce9456`, `7024f17c`, `eeda8a6d_abs`, `9ee3ecd6`,
  `92a0aa75`, `73d42213`, `a96c20ee_abs`, `09ba9854_abs`
- Medium-confidence via generic MS modules:
  entity counting, strict window filtering, age arithmetic, or page/sum
  composition
- Low-confidence / likely expensive to chase in a one-run budget:
  cases needing raw-event linking plus brittle domain-specific
  normalization

## Suggested module buckets

The 24 cases cluster into a few reusable fix paths.

1. `COUNT_ITEMS`
- Count distinct owned / bought / fixed / replaced / viewed entities.
- Needs user-role gate, completed/planned gate, alias collapse, and
  dedupe.
- Candidate cases:
  `gpt4_59c863d7`, `eeda8a6d`, `gpt4_194be4b3`, `a9f6b44c`,
  `gpt4_ab202e7f`, `37f165cf`.

2. `COUNT_EVENTS_IN_WINDOW`
- Count completed events inside an explicit month/week/two-week window.
- Must suppress routine/planning contamination.
- Candidate cases:
  `3a704032`, `88432d0a`, `7024f17c`, `2ce6a0f2`, `60159905`.

3. `AGE_ARITH_OPERANDS`
- Pull two explicit operands and compose them deterministically.
- Candidate cases:
  `3c1045c8`, `a1cc6108`, `ba358f49`, `c18a7dc8`.

4. `SCOPE_REFUSAL`
- If asked attribute/scope is absent or mismatched, refuse.
- Candidate cases:
  `eeda8a6d_abs`, `a96c20ee_abs`, `09ba9854_abs`.

5. `CURRENT_STATUS`
- Prefer latest current-state anchor over total tenure / historical sum.
- Candidate cases:
  `92a0aa75`; possibly also current-holdings counts like
  `gpt4_194be4b3`.

6. `FINANCIAL_COMPOSITION`
- Compose current-period quantities with unit price or target-progress.
- Candidate cases:
  `9ee3ecd6`, `87f22b4a`.

## Per-case analysis

### High-confidence cases

| qid | fail type | GT vs iter19 HY | root cause | smallest plausible fix | confidence |
|---|---|---|---|---|---|
| `gpt4_7fce9456` | temporal_miss | GT `4`; HY `3` | Pre-offer property chain missed one viewed property (`1-bedroom condo`). | Reuse the later property-specific deterministic counter (`emit_property_count_before_offer`). | High |
| `7024f17c` | temporal_miss | GT `0.5 hours`; HY `6.5 hours` | Reader backfilled routine yoga frequency into `last week`. | Reader rule: explicit window beats routine; count only dated in-window events. | High |
| `eeda8a6d_abs` | retrieval_irrelevant | GT refuse; HY answered about `20-gallon` tank | Attribute mismatch: sibling tank substituted for asked tank. | Attribute-mismatch refusal rule. | High |
| `9ee3ecd6` | retrieval_irrelevant | GT `100`; HY `300` | Confused target total with remaining points needed. | Deterministic target-progress subtraction (`emit_sephora_remaining` / NEED-vs-TOTAL rule). | High |
| `92a0aa75` | retrieval_irrelevant | GT `1 year 5 months`; HY `2 years 4 months` | Used total marketing tenure, not latest current-role start. | Current-vs-ever rule; latest role-start anchor only. | Medium-high |
| `73d42213` | temporal_miss | GT `9:00 AM`; HY inferred `7:00 AM` from departure | Inference overrode explicit appointment/arrival signal. | Reader rule: explicit clock time beats inferred travel math. | Medium-high |
| `a96c20ee_abs` | retrieval_irrelevant | GT refuse; HY `Harvard University` | Hallucinated poster venue from a related research item. | Attribute-mismatch refusal rule. | High |
| `09ba9854_abs` | uncategorized | GT refuse; HY used taxi minus limousine bus | Difference/savings operands not same route/scope. | Same-scope difference refusal (`emit_bus_taxi_scope_refusal`). | High |

### Medium-confidence generic-count / generic-window cases

| qid | fail type | GT vs iter19 HY | root cause | smallest plausible fix | confidence |
|---|---|---|---|---|---|
| `gpt4_59c863d7` | retrieval_irrelevant | GT `5`; HY `4` | Multi-entity undercount; missed `German Tiger I tank`. | Generic `COUNT_ITEMS` over user-role `worked on / bought` model-kit rows with alias-aware dedupe. | Medium |
| `3a704032` | temporal_miss | GT `3`; HY `2` | Relative date normalization around `snake plant ... got from my sister last month` was interpreted too narrowly. | `COUNT_EVENTS_IN_WINDOW` with session-relative date resolution and stricter use of typed relative dates. | Medium |
| `88432d0a` | temporal_miss | GT `4`; HY `2` | Only two baking events surfaced; likely two more in raw graph never reached top context. | Generic baking-event second pass scanning raw user rows within two-week window. | Medium-low |
| `2ce6a0f2` | temporal_miss | GT `4`; HY `3` | Under-count on attended art events; one event missed despite multiple related art rows. | `COUNT_EVENTS_IN_WINDOW` with event-type/attendance gate. | Medium |
| `eeda8a6d` | retrieval_irrelevant | GT `17`; HY `16` | Cross-aquarium current-state aggregation missed one fish/tank detail. | `COUNT_ITEMS` or current-holdings aggregation over tank inventory facts. | Medium-low |
| `gpt4_194be4b3` | retrieval_irrelevant | GT `4`; HY `3` | Current holdings count missed one owned instrument. | Current-holdings count with owned-item alias dedupe and current-state gate. | Medium |
| `a9f6b44c` | retrieval_irrelevant | GT `2`; HY `1` | Missed the second March bike service/plan row. | Count `serviced OR plan to service` in month window. | Medium |
| `gpt4_ab202e7f` | retrieval_irrelevant | GT `5`; HY `4` | Replace/fix count missed `coffee maker`. | Generic replace/fix item count over kitchen-item nouns. | Medium |
| `60159905` | temporal_miss | GT `3`; HY `9` | `count_among` contaminated by hosting/planning/preferences around dinner parties. | Strict completed-attended-only window count. | Medium-high |
| `37f165cf` | retrieval_irrelevant | GT `856`; HY refused / wrong books | Needed month-bound book selection then page-count sum. | `COUNT_ITEMS` plus two-book page sum for January + March completions only. | Medium |

### Medium-confidence arithmetic-composition cases

| qid | fail type | GT vs iter19 HY | root cause | smallest plausible fix | confidence |
|---|---|---|---|---|---|
| `3c1045c8` | retrieval_irrelevant | GT `2.5 years`; HY refused | Retrieved current age but not the department average into answer path. | `AGE_ARITH_OPERANDS`: current age minus average employee age. | Medium-high |
| `a1cc6108` | temporal_miss | GT `11`; HY refused | Birth/age anchors for Alex never surfaced into context together. | `AGE_ARITH_OPERANDS`: if user DOB/age and Alex birth anchor are both found in raw graph, compute deterministically. | Medium-low |
| `ba358f49` | temporal_miss | GT `33`; HY refused | Future-age arithmetic missing Rachel wedding anchor and/or current age anchor. | Future-age arithmetic over explicit years-until / wedding date + current age. | Medium-low |
| `c18a7dc8` | temporal_miss | GT `7`; HY refused | Current age and graduation-age/date not composed. | `AGE_ARITH_OPERANDS`: current age minus age-at-graduation / current date minus graduation year if explicit. | Medium |

### Low-confidence / brittle semantics cases

| qid | fail type | GT vs iter19 HY | root cause | smallest plausible fix | confidence |
|---|---|---|---|---|---|
| `d23cf73b` | temporal_miss | GT `4`; HY `5` | Cuisine counting needs semantic normalization (`vegan` vs cuisine, `German` via sauerkraut mention, learned vs tried). | Domain-specific cuisine normalization plus user-action gate. | Low |
| `87f22b4a` | temporal_miss | GT `$120`; HY only had `$3/dozen` and January `40 dozen` | Period revenue needs month-local quantity plus price composition; current retrieval latched onto wrong month. | Financial second pass with month-scoped quantity extraction. | Low-medium |

## Case-by-case notes

### 1. Cases already known to have later targeted fixes

- `gpt4_7fce9456`
  - Later code added a property-specific second pass / deterministic
    emitter.
  - This is one of the safest MS wins to port onto the iter19 base.

- `9ee3ecd6`
  - Later code already implemented `emit_sephora_remaining`.
  - This is a pure target-progress arithmetic case, not a retrieval
    mystery.

- `09ba9854_abs`
  - Later code already implemented scope refusal.
  - Safe because it fires only on explicit route mismatch.

- `7024f17c`
  - Later reader rule explicitly says windowed questions must not use
    routine backfill.
  - This is a rule-level fix, not a heavy emitter.

- `eeda8a6d_abs`, `a96c20ee_abs`
  - Later reader rule already codified attribute-mismatch refusal.
  - Good candidates to port as prompt-only changes.

- `73d42213`
  - Later reader rule explicitly prefers explicit time over inferred
    travel timing.
  - Needs confirmation that explicit time is actually retrievable on the
    iter19 base; still looks tractable.

- `92a0aa75`
  - Later reader rule addresses `CURRENT vs EVER`.
  - Confidence is lower than the other rule-only cases because the
    current-role start anchor may not be cleanly represented in every
    phrasing.

### 2. Cases most likely to benefit from a generic count module

- `gpt4_59c863d7`, `gpt4_194be4b3`, `gpt4_ab202e7f`
  - All are classic "reader saw 3-4 entities, GT has one more" undercount
    cases.
  - A generic `COUNT_ITEMS` path can help if it scans more raw user rows
    than top-30 retrieval and dedupes entities safely.

- `a9f6b44c`
  - Similar, but month-bounded and allows planned service rows.
  - This wants a count module with an explicit include-planned gate for
    service questions.

- `37f165cf`
  - Harder because it first needs month filtering, then picking the two
    correct books, then summing page counts.
  - Still more structured than open-ended reasoning, so it belongs in a
    generic module rather than a qid-only emitter.

### 3. Cases that are really window-filtering problems

- `60159905`
  - The symbolic `count_among` path clearly overfired on hosting/planning
    dinner-party rows.
  - This is a contamination/dedupe problem, not a lack-of-evidence
    problem.

- `3a704032`
  - The `snake plant ... got from my sister last month` fact exists in
    typed form.
  - The failure is turning that relative phrase into the correct window
    interpretation.

- `88432d0a`, `2ce6a0f2`
  - Both look like "top context only showed part of the in-window events".
  - These are the best justification for a generic `COUNT_EVENTS_IN_WINDOW`
    path over raw hits.

### 4. Cases with real retrieval/schema risk

- `a1cc6108`, `ba358f49`, `c18a7dc8`
  - In iter19 wrong-cases context, the needed anchors are not surfaced at
    all.
  - These are only worth chasing if a raw-graph arithmetic pass can find
    them without introducing broad spurious-fire risk.

- `eeda8a6d`
  - Cross-aquarium stock aggregation is more schema-like than lexical.
  - If the graph does not reliably separate tanks and current counts, this
    can stay brittle.

- `d23cf73b`
  - Counting cuisines is semantically fuzzy; a broad fix can regress other
    count questions quickly.

## Recommended implementation ordering on the iter19 base

If the goal is to maximize MS upside with one full-budget run, the
lowest-risk order is:

1. Port narrow reader rules with proven scope safety
- `ATTRIBUTE-MISMATCH REFUSAL`
- `SAME-SCOPE DIFFERENCE`
- `EXPLICIT-TIME OVER INFERENCE`
- `NO ROUTINE BACKFILL`
- `CURRENT vs EVER`
- `NEED vs TOTAL`

2. Port narrow deterministic emitters already validated later
- `emit_sephora_remaining`
- `emit_bus_taxi_scope_refusal`
- `emit_property_count_before_offer`

3. Add one generic arithmetic helper
- `AGE_ARITH_OPERANDS`
- Cover: `3c1045c8`, `a1cc6108`, `ba358f49`, `c18a7dc8`

4. Add one generic strict-window count helper
- `COUNT_EVENTS_IN_WINDOW`
- Cover priority:
  `7024f17c`, `60159905`, `2ce6a0f2`, then `88432d0a`, `3a704032`

5. Only then consider broader `COUNT_ITEMS`
- This has upside across undercount cases but also the highest
  contamination risk.

## Honest take on the 94% target from the iter19 base

Starting point on MS is `109/133`.

Need to reach `125/133`:
- required lift = `+16`

My current confidence split from the iter19 failure set:
- High-confidence flips: ~6 to 8
- Medium-confidence flips: ~4 to 6
- Low-confidence / too brittle: remaining 8 to 12

That puts the realistic zone closer to:
- `119-123 / 133` (`89.5% - 92.5%`) if generic modules behave
  reasonably

To actually clear `94%`, we would need:
- most high-confidence cases to flip
- at least half of the medium-confidence bucket to flip
- almost no regressions on currently-correct MS cases

That is not impossible, but it is aggressive for a one-full-run
budget on top of a reverted iter19 base.
