# Codex Round 2 — Retry with All Data Inline

Your previous attempt failed because the sandbox (bwrap) could not
launch (`Failed RTM_NEWADDR: Operation not permitted`). You produced
a cluster-level table but could not deliver the 45-row per-case
table. This retry inlines all 45 wrong cases below so you do not
need file access.

You may still attempt file reads, but if they fail again, just
proceed — everything you need is in this single stdin payload.

---

## Mission (unchanged from prior briefing)

Deliver a per-case fix table for all **45 wrong cases** (15 TR + 30
MS) such that, deployed together as round 2, the iter31 stack hits
SOTA (MS ≥ 90%, TR ≥ 93% on N=500). Operate under the skill's
HARD-GATE and full-coverage habit: every case gets a row, none are
silently dropped.

## Accepted framework from your prior critique

**(A) Question-shape router + structured evidence ledger**
**(B) Chunk-level late fusion (lexical BM25 over raw event chunks)**

Your prior architecture spec (in `CODEX_CRITIQUE.md`) is accepted as
the skeleton. You proposed:

- `QuestionShape = Literal["count", "order", "duration_since", "date_diff", "derived_time", "abs_value", "other"]`
- `detect_question_shape(q)`, `late_fusion_retrieve(...)`,
  `build_evidence_ledger(...)`, `answer_from_ledger(...)`
- Detection regexes for each shape
- Ledger JSON shapes (count / order / duration_since / abs_value)
- Resolver patches (start-anchor selection, order backfill,
  same-day disambig, date-diff convention)
- Backoff: structured→reader→refusal

For the per-case table: each row's `fix mechanism` column should
map to `A` (one of the 4 ledger shapes you defined), `B`
(chunk-fusion-required, name what raw evidence would surface), a
small qa_answer rule body (≤ 12 lines, cited qid), a 3-5 line
resolver patch, or `defer` with reason.

## Constraints recap

- TR + MS ONLY (ignore KU/SSA/SSP/SSU risk for this round)
- Provider routing HARD: gpt-5.4-mini → commonstack only
- Total dev budget ≤ 4 hours
- No BATCH_SYSTEM_PROMPT changes (writer-side broke iter28-30)
- Two LongMemEval cases are publicly disputed annotations and should
  be deferred:
  - `370a8ff4` (flu→jog) — LongMemEval issue #41
  - `eac54add` (4 weeks ago milestone) — LongMemEval issue #37

## Output format

### Section 1 — Per-case fix table (REQUIRED — 45 rows, no skip)

```
| label | qid | cluster | root cause from full_context | fix mechanism | target file:func | regression risk | expected delta |
```

Where:
- `label`: TR-01..TR-15, MS-01..MS-30 (matches headings below)
- `fix mechanism`:
  - `A:count` / `A:order` / `A:duration_since` / `A:date_diff` /
    `A:derived_time` / `A:abs_value` (one of your ledger shapes)
  - `B:chunk_fusion` (name what raw-text evidence surfaces the
    missing fact)
  - `qa_rule:"<≤12-line body ending with (case qid)>"`
  - `resolver:<function_name>` (3-5 line pseudocode patch)
  - `defer:judge_variance` / `defer:retrieval_miss_no_signal` /
    `defer:disputed_annotation_issue_<N>` / `defer:other`

### Section 2 — Round-2 architecture spec (≤ 600 lines total)

Finalize the architecture spec you sketched in CODEX_CRITIQUE.md
with concrete commitments:
- Final detect_question_shape regex set
- Final ledger JSON shapes (one per question shape)
- Final late_fusion_retrieve API + integration point
  (`benchmarks/longmemeval/run_eval.py`)
- Final answer_from_ledger backoff behavior
- Resolver patches (function signatures + before/after diffs)
- qa_answer rules added (consolidated list, no duplicates)
- Smoke test plan (which 6-10 qids validate before N=500)
- Dev hour budget per piece

### Section 3 — Bottom line on SOTA

- TR projection on N=500 (with disputed cases excluded)
- MS projection
- Total N=500 projection
- One-shot 94.87% — possible or not? If not, what's the realistic
  ceiling this round and what's the structural piece beyond this
  round?

---

## The 45 cases (inline, 2000-char excerpts)

