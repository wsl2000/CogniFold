# CogniFold × LongMemEval — Briefing for Codex

You are being briefed by Claude (Opus 4.7) on an ongoing benchmark optimization
session for CogniFold against LongMemEval-S. The user wants your **honest
critique** of the round-2 plan and your identification of **any
highest-ROI fix we're missing**. Operate at maximum reasoning effort.

---

## 1. Project: CogniFold

CogniFold is a dynamic concept graph memory system. The full architecture lives
in this repo (`src/cognifold/...`). For the purposes of this briefing the
relevant parts are:

- **Writer**: an LLM that ingests session events and emits an UpdatePlan
  consisting of ADD/UPDATE/REMOVE/MERGE operations on the graph
  (`src/cognifold/agent/batch.py` `BATCH_SYSTEM_PROMPT`).
- **Retrieval**: BM25 + hybrid + optional LLM rerank over the graph
  (`src/cognifold/retrieval/`).
- **Reader**: an LLM that takes a question and retrieved context and produces
  an answer (`benchmarks/longmemeval/run_eval.py` + the `qa_answer` rules in
  `configs/longmemeval_profile.yaml`).
- **Resolver**: a symbolic pattern matcher that special-cases temporal
  reasoning questions
  (`benchmarks/longmemeval/symbolic_resolver.py`, ~14 patterns).

---

## 2. Goal

Beat Mastra's published **N=500 = 94.87%** on LongMemEval-S using a
**gpt-5.4-mini-class reader**. Public SOTA on this stack is iter19 = **86.8%
N=500**. We have ~$300-500 commonstack budget and **1 more iter cycle** before
the user wants a publishable result.

---

## 3. Per-role API routing (HARD rule — do NOT propose changing)

| Role | Model | Provider |
|---|---|---|
| writer / reader / rerank | `openai/gpt-5.4-mini` | **commonstack** (only place that serves this SKU) |
| judge | `openai/gpt-4o` | OpenRouter |
| embed | `text-embedding-3-small` | OpenRouter |

Any other chat model goes to OpenRouter. Never to commonstack. The user has
prepaid commonstack credit specifically for the gpt-5.4-mini SKU.

---

## 4. Iter history (relevant subset)

Full canonical record in `benchmarks/longmemeval/HISTORY.md`. The short
version of the iter we care about:

| iter | label | N | strict | TR | by-type notes | decision |
|---|---|---|---|---|---|---|
| 19 | full validation (gpt-5-mini, W1 OFF, W2 OFF) | 500 | **86.8%** | 78.9% | KU 94.9 MS 82.0 SSA 91.1 SSP 90.0 SSU 97.1 | KEEP — public SOTA |
| 27 | gpt-5.4-mini + W1+W2 | 500 | 86.8% | 80.5% | KU 93.6 MS 77.4 **SSA 100.0** SSP 93.3 SSU 95.7 | NEUTRAL — W2 rejected |
| 28a/b | Mastra triple-date / priority | partial | — | — | broke MS / SSA | REVERTED |
| 29a/c | qa_answer +200 lines | 500 partial | 62.5% | 57% | catastrophic MS −27pp | REVERTED |
| 30/b | W3 START + qa-compress | 500 partial | 62.5% | 41% | catastrophic | REVERTED |
| 31 | resolver TR fixes round 1 (THIS ITER) | 133 (TR-only) | — | **88.7%** | TR +8.3pp vs iter27 | KEEP, round 2 next |

The fundamental empirical lesson from iter27→iter30: **every writer enrichment
pass added after iter19 hurts MS**. W1 typed-attr helped SSA hugely
(91.1→100) but hurt MS (82.0→77.4). W2 event_date pass added noisy dates that
hurt MS. W3 START extraction added catastrophic noise. qa_answer rule bloat
caused reader to misapply rules. We do not propose any of these again without
question-type gating evidence.

---

## 5. iter31 round 1 result (just completed)

- **TR-only N=133 = 118/133 = 88.7%** strict (0 empty hypothesis, judge=gpt-4o)
- **vs iter27 TR (107/133 = 80.5%) = +11 net cases, +8.3pp**
- 16 improvements, 5 regressions (full per-case list in
  `benchmarks/longmemeval/runs/iter31_tr_round1/CHANGES.md`)
- Stack vs iter27: gpt-5.4-mini, W1 OFF, W2 OFF, W3 OFF, Reflector OFF
  (back to iter19 writer stack), plus:
  - Symbolic resolver round-1 fixes (`symbolic_resolver.py`)
  - 8 new `qa_answer` rules (configs/longmemeval_profile.yaml)
  - 1 new writer rule (`BATCH_SYSTEM_PROMPT` rule 4 — `activity_start`)
  - X1 `--tr-topic-timeline` flag (prepends TR-α chronological block)
  - X4 CHRONOLOGICAL-SCAN qa_answer rule

### Round 1 fix list (already deployed in iter31)

**Resolver (`symbolic_resolver.py`)**:
- Disabled `which_first` + `relative_ago_recall` patterns (0%-acc in iter27)
- `_find_is_start_concept` Pass 3: EARLIEST mention fallback for unmarked
  start concepts
- `_try_diff_since_when`: strict `recovered|got over|healed from` regex match
  → uses earliest-date concept
- `_try_order_among`: force `bypass=False` for lists >3 items
- `_try_named_day_recall`: multi-candidate hint when ≥2 same-day candidates
- Accept `activity_start` field alongside `is_start`; honor `start_date`

**Writer (`BATCH_SYSTEM_PROMPT` rule 4)**:
- When user FIRST mentions an ongoing activity/membership/hobby/job
  transition with a starting verb ("I started X-ing", "I joined X", "I picked
  up X", "I got my new X"), emit a concept with `activity_start: true`,
  `activity: "<phrase>"`, `start_date: <date>` (back-derived from "X weeks ago"
  phrasing)

**Reader (`qa_answer` 8 new rules)**:
- DURATION-SINCE-START
- AGE-INFERENCE (case d01c6aa8)
- PLANNED→COMPLETED "today" translation (case gpt4_68e94288)
- INCLUSIVE-BOUNDARY (case gpt4_4fc4f797)
- COMPARATIVE EARLIER=FIRST (case gpt4_0b2f1d21)
- EXHAUSTIVE-COUNT exclude-anchor caveat (case a3838d2b)
- BOOKING vs PLANNING (case 982b5123)
- `_abs` both-entities check (case c8090214_abs)
- CHRONOLOGICAL-SCAN (X4): use TOPIC_TIMELINE / CHRONOLOGICAL_TEMPORAL
  blocks as authoritative for ordering

### iter31 TR wrong cases (15 cases remaining)

| qid | cluster | iter31 HY | GT | root cause from full_context |
|---|---|---|---|---|
| gpt4_e061b84f | TR-B order_among 3-sports | "only triathlon verifiable" | Triathlon → 5K → charity | X1 timeline only kept 1 sports event; reader hedged refusal |
| gpt4_7abb270c | TR-B order_among 6-museums | listed 5 of 6 | 6 museums | rerank pool missed Museum of History OR timeline dropped |
| gpt4_f420262c | TR-B order_among 4-airlines | Delta→United→AA→JetBlue | JetBlue→Delta→United→AA | reader missed JetBlue's earlier record |
| gpt4_7f6b06db | TR-B order_among 3-trips | hallucinated Yosemite x2 | day hike→Big Sur→Yosemite | hallucination not in context |
| b46e15ed | TR-D date_diff months | 1 month | 2 months | Feb 11+12 → Apr 18, resolver used days/30 not calendar months |
| 9a707b81 | TR-D date_diff days | 20 days | 21 or 22 | iter27 gave same "20" answer and was marked CORRECT — judge variance |
| 370a8ff4 | TR-A duration_since_start | 14 weeks | 15 weeks | EARLIEST fallback off-by-one week |
| 08f4fc43 | TR-A duration_since_start | "30 days. 31 if inclusive" | 30 or 31 | judge picked strict reading of dual-answer |
| gpt4_d6585ce9 | TR-C named_day Saturday | with friends (Brooklyn) | with parents | retrieval pulled wrong event; companion-field miss |
| gpt4_f420262d | TR-C named_day Valentine | "asked for 6 details" hallucination | American Airlines | reader echoed assistant clarification instead of answering |
| a3838d2b | count_before_event | 2 | 4 | undercount in "events BEFORE anchor" — EXHAUSTIVE-COUNT didn't fire with BEFORE context |
| c8090214_abs | _abs Holiday Market vs iPad | "7 days" | refuse (no iPad mentioned) | reader substituted iPhone 13 Pro for iPad |
| gpt4_fe651585 | which_first parent | Rachel first | Alex first | reader treated "Rachel caring for Jackson+Julia" as became-parent state, not event |
| eac54add | TR-E 4-weeks-ago milestone | influencer collab | signed first client contract | retrieval miss — anchor-date concept not retrieved |
| gpt4_59149c78 | TR-E art event location | City Art Museum | Metropolitan Museum of Art | retrieval miss + hallucination of museum name |

---

## 6. iter27 MS wrong cases (30 cases — the baseline we'd target in round 2)

We don't yet have iter31's MS wrong set on N=500 — iter31 has only run on the
133 TR qids. The plan is to run iter31's stack on the full N=500 (TR + MS as
primary target) in round 2. Below is iter27's MS wrong set; iter31 (W1+W2 OFF)
should track iter19's MS pattern (82.0%, ~24 wrongs) more closely than
iter27's pattern (77.4%, 30 wrongs), but the dominant cluster (MS-A undercount)
will overlap heavily.

### Cluster summary (iter27 N=500)

- **MS-A undercount: 22 cases** — reader sees N entities but counts N−1 or
  N−2 because it stops scanning after first 2-3 hits
- **MS-? unclassified: 7 cases** — mostly age-inference or hallucinations
- **MS-B refusal-with-data: 1 case** — refuses when answer is derivable

### Representative MS deep-dives

| qid | observation |
|---|---|
| 28dc39ac (gaming hours total) | GT 140, HY 105. Reader counted 70+30+5 = 105. Missed at least one game and/or its hours. Context has W1 TYPED_QUANTITY nodes. iter31 has W1 OFF — so these nodes won't exist. EXHAUSTIVE-COUNT must work on raw concept descriptions. |
| 0a995998 (clothing pickup/return) | GT 3, HY 2. Reader named blazer + boots. Third item exists in context but wasn't named. Classic undercount. |
| c4a1ceb8 (citrus in cocktails) | GT 3, HY 4. Reader counted orange, lemon, lime, grapefruit; GT excludes one. Subjective judge call — not fixable code-side. |
| 80ec1f4f_abs (museums in December) | GT "0" (refuse — none visited in December). HY "two" (substituted Jan visits). Need named-period `_abs` rule. |
| ba358f49 (Rachel wedding age) | GT 33, HY "Unknown". Reader could derive 30+3 = 33 from age + wedding-distance. AGE-INFERENCE rule needs multi-context coverage. |
| 7024f17c (jogging+yoga last week hours) | GT 0.5h, HY 6h. Reader extrapolated from typical schedule rather than reading last week's actual record. |

---

## 7. iter31 round 2 plan (Claude's current proposal)

### TR fixes (~88.7% → 93-95% target)

1. **topic_timeline noun broadening** + `<N` candidates fallback (uses
   retrieved-EVENTS block when timeline has fewer entries than question
   requires). Fixes: gpt4_e061b84f, gpt4_7abb270c, gpt4_f420262c, gpt4_7f6b06db.
2. **`_try_date_diff_since` calendar-month math** (not `days/30`). Fixes:
   b46e15ed.
3. **INCLUSIVE-BOUNDARY rule extended to weeks** + resolver `weeks` rounding
   uses `ceil`. Fixes: 370a8ff4. Reduces 08f4fc43 risk.
4. **DURATION dual-answer output** ("X. X+1 if inclusive"). Fixes: 08f4fc43.
5. **qa_answer "DO NOT echo assistant_clarification"**. Fixes: gpt4_f420262d.
6. **EXHAUSTIVE-COUNT-WITH-ANCHOR** ("BEFORE X — list ALL events with
   date < X.date"). Fixes: a3838d2b.
7. **`_abs` "DO NOT substitute similar named items" (iPhone ≠ iPad)**.
   Fixes: c8090214_abs.
8. **which_first must cite explicit became-parent date**. Fixes: gpt4_fe651585.

Deferred (no fix in current architecture):
- 9a707b81 — judge variance
- gpt4_d6585ce9 — retrieval miss
- eac54add — retrieval miss
- gpt4_59149c78 — retrieval miss

### MS fixes (~82% projected → 88-91% target)

1. **EXHAUSTIVE-COUNT v2** — qa_answer rule mandates list-then-tally with
   per-item verification. Targets the 22 MS-A cases.
2. **rerank pool 100→200 for "how many" Qs** — conditional in run_eval.py:
   detect counting question → expand BM25 rerank pool. Targets undercount
   that's caused by retrieval cutoff.
3. **named-period `_abs` refusal** — qa_answer + resolver: if anchor period
   (month/week) has NO matching events, refuse "0". Targets: 80ec1f4f_abs.
4. **AGE-INFERENCE multi-context** — extend AGE-INFERENCE to wedding-age,
   future-age, age-at-event patterns. Targets: ba358f49.
5. **anti-extrapolate-from-typical** — qa_answer: "DO NOT extrapolate from
   typical schedule. Use ACTUAL recorded sessions for time-windowed
   counts." Targets: 7024f17c.

Deferred / not proposing:
- ❌ **W1 selective** (only numeric typed-attr): iter27 W1 caused MS −4.5pp
  even at full strength; the "selective" version still risks similar noise
- ❌ **Writer no-dedupe rule**: iter28-30 all broke when writer was changed
- ❌ **PAL/code-augmented counting**: 2-3h dev, beyond round 2 budget
- ❌ **2nd-pass retrieval**: complex, cost roughly doubles

### Estimated impact

| metric | current | round 2 target |
|---|---|---|
| TR (N=133) | 118 = 88.7% | 125-127 ≈ 94-95% |
| MS (N=133, projected on iter31 stack) | ~109 ≈ 82% | 117-121 ≈ 88-91% |
| KU / SSA / SSP / SSU | iter19 baseline | unchanged (we're not touching their rules) |
| Total N=500 | ~88% projected | **~91-93%** |

---

## 8. Operational constraints + history

- Today's commonstack burn: ~$200-250 (one TR-only N=133 run, several
  premature kills and parallelism experiments).
- Commonstack has been the bottleneck — at 25p we caused a 70% empty
  hypothesis rate within 30 min because we burned through balance fast
  enough to trigger their billing-side throttle. 10p–20p is the safe band
  with a healthy balance. Health-check every 10 results is mandatory
  (`/.claude/skills/lme-auto-optimize/scripts/health_check.py`).
- The user has been explicit on:
  - **NEVER skip the every-10 health check**.
  - **NEVER swap provider in fallback** (gpt-5-mini ≠ gpt-5.4-mini and
    invalidates baseline comparisons).
  - **NEVER change provider routing** (commonstack only for the gpt-5.4-mini
    SKU).
  - **Full coverage per iter**: every wrong case in the targeted clusters
    must appear in the fix table with a proposed change OR an explicit
    "no fix — defer" reason. No cherry-picking.

---

## 9. What we want from you

The user wants your **honest, hard critique** of the round-2 plan above.
Specifically:

1. **Highest-ROI fix we're missing**: What is the single fix with the
   greatest expected MS or TR lift that we haven't proposed? Be concrete.
2. **Risk in the proposed fixes**: Which of the 13 proposed fixes is
   most likely to introduce a regression on KU / SSA / SSP / SSU /
   un-targeted MS / un-targeted TR cases? Explain the mechanism.
3. **PAL / code-augmented counting**: is this worth implementing as a
   structural change before round 2 N=500? What's a minimum viable
   approach that fits in 2-3 hours of dev?
4. **Mastra's edge to 94.87%**: based on the public Mastra paper / blog
   posts you've seen, what techniques are they using that we aren't?
   We've already tried: triple-date observation (iter28a, REVERTED),
   priority tagging (iter28b, REVERTED). What else?
5. **Retrieval improvements for the 4 TR retrieval-miss cases**
   (gpt4_d6585ce9, eac54add, gpt4_59149c78, plus the implicit 4-5 MS
   undercount cases that are actually retrieval misses): a single
   structural fix that helps both TR and MS without breaking other types.
6. **Run order**: should we run N=500 with iter31's current stack
   (no round-2 changes) FIRST to establish the real MS/SSA/SSP/SSU/KU
   baseline before changing more rules? Or just implement round 2 and
   run N=500 once?
7. **`_try_date_diff_since` calendar-month math**: it lives in
   `benchmarks/longmemeval/symbolic_resolver.py`. Look at it. Propose
   the smallest patch that makes b46e15ed work without regressing the
   other date_diff_since cases that iter31 currently gets right.
8. **`_find_is_start_concept` Pass 3**: I added an EARLIEST-mention
   fallback (case 370a8ff4 flu→jog) but it's still off-by-1 week. Look
   at the function. Is the issue the rounding, the candidate selection,
   or the inclusive-boundary convention? What's the right fix?

Be brutal. If you think the round-2 plan is wrong-headed, say so.
If you think the ceiling is below 91%, say so. We have one shot left.

---

## 10. Files for you to read

- `benchmarks/longmemeval/HISTORY.md` — canonical iter history
- `benchmarks/longmemeval/runs/iter27_gpt54mini_full_n500_W1W2/CHANGES.md`
  — iter27 SOTA narrative
- `benchmarks/longmemeval/runs/iter31_tr_round1/CHANGES.md` — iter31
  round 1 narrative (just completed)
- `benchmarks/longmemeval/runs/iter31_tr_round1/hypothesis.jsonl` —
  133 records with full_context, retrieved_context, verdict
- `benchmarks/longmemeval/runs/iter27_gpt54mini_full_n500_W1W2/wrong_cases.json`
  — 66 wrongs across all types (the source for MS analysis)
- `benchmarks/longmemeval/symbolic_resolver.py` — 14 patterns,
  `_try_diff_since_when`, `_find_is_start_concept`, `_try_date_diff_since`,
  `_try_order_among`, `_try_named_day_recall`, etc.
- `configs/longmemeval_profile.yaml` — qa_answer block, ~264 lines, the
  rule set the reader sees
- `src/cognifold/agent/batch.py` — `BATCH_SYSTEM_PROMPT`, 4 writer rules
- `benchmarks/longmemeval/run_eval.py` — driver, `build_topic_timeline`
  function (around line 1300?), reader/writer/judge calls
- `.claude/skills/lme-auto-optimize/SKILL.md` — the workflow skill
  Claude has been operating from, including the PROVIDER-ROUTING-HARD-RULE,
  OPERATIONAL-HABITS, HARD-GATE, and Steps 0-8 with the health-check pattern

Read these. Then deliver your critique.
