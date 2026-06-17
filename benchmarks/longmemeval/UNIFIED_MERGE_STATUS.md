# LongMemEval best-of-breed merge — `unified-longmemeval`

Branch base: **`misc/hello`** (iter32 R7, the TR-complete state that produced the verified TR 88.7).
Goal: one runnable config that captures every category's best at once, instead of the paper's
3-config best-of-breed *stitch*.

## Per-category provenance (what we are trying to combine)

| Cat | Best | Source | Backing |
|---|---|---|---|
| SSU | 97.1 (68/70) | iter19 | doc-claim |
| SSA | 100.0 (56/56) | iter27 (W1 typed-attr) | doc-claim |
| SSP | 93.3 (28/30) | iter27 | doc-claim |
| MS  | **82.0 (109/133) measured** / 91.0 *claimed* | iter19 / *projection* | **MS 91.0 UNBACKED** — planning projection (`CODEX_ROUND2_PLAN.md:476`); branch committed "prepare only — not executed"; best executed full-MS ≈ 50% with ledger firing 0×. |
| KU  | 94.9 (74/78) | iter19 | doc-claim |
| TR  | **88.7 (118/133)** | iter31 (`iter31_tr_round1`) | **ARTIFACT-BACKED**, recomputable |

Paper composite 93.0% (465/500) = stitch using the unbacked MS 121. Honest best-backed stitch = **453/500 = 90.6%** (MS→109), and even that is a 3-config stitch, not one run. iter32 R7's TR 95% never materialized (its one run was −1 vs iter31).

## What this branch merges

The two antagonisms that made "one run" look impossible are both resolved:
1. **W2 (event-date resolution) TR↔MS antagonism is moot**: iter31 earns TR 88.7 with **W2 OFF** (resolver + `start_date` writer rule replace it), and MS also wants W2 OFF. They agree → W2 stays globally OFF. No per-question-type W2 routing needed.
2. **No oracle routing**: the merge is **label-blind**. The only "routing" is the evidence ledger's per-emitter question-text regex self-gating (legitimate — the system inspects the question it is answering, not the hidden `question_type` label).

Concretely merged:
- TR stack (symbolic_resolver iter31, 8 TR emitters, profile TR+MS qa_answer rules, `--tr-topic-timeline`, W1 ON / W2 OFF): **inherited intact from `misc/hello`, byte-identical, 0 TR shape changes.**
- **34 MS-only emitters** unioned into `round2_evidence_ledger.py` (37 MS − 3 shared with identical targets). `run_eval.py` needed **zero change** — it already dispatches this ledger; `detect_question_shape` now returns non-`other` for the 9 MS targets so they reach the dispatch.

## Verification (all $0, no paid API) — Stage 0

| Gate | Result |
|---|---|
| Import + count | 42 emitters, clean import of `round2_evidence_ledger.py` and full `run_eval.py` |
| **Spurious-fire sweep** (500 Qs) | every emitter fires on exactly its 1 target question, in its own category — **XCAT=0, dead=0, multi=0**. Reproduced independently. |
| TR preservation | `detect_question_shape` unchanged on all 133 TR Qs (0 changes); 8 TR emitters + `assemble_ledger_context` + `answer_from_ledger` + `_normalize_rows` byte-identical; base 8-entry dispatch is an exact prefix of the merged 42 |
| Dispatch reachability | first-match-wins reaches each MS emitter on its target (no earlier gate matches it) |
| Lint/type | ruff/pyright: 0 new findings on the ledger vs base (pre-existing TR-region findings remain) |

Sweep is committed at `scripts/ledger_spurious_sweep.py` (re-runnable, $0).

`assemble_ledger_context` is **unchanged** — the MS context-augmenters (`_count_candidate_block`/`_arith_operand_block`) are ported but **NOT wired** (they co-fire on TR `date_diff`/`duration` shapes; deferred).

## Honest ceiling & what is NOT yet proven

- The MS emitters' **answers** are not proven correct here — Stage 0 only proves they don't cross-fire. The MS emitter mechanism was **never observed to contribute a single answer in any executed run** (ledger fired 0× in the only real full-MS run). So the realistic MS contribution is unknown and must be **measured**.
- Realistic single-run ceiling if everything transfers: **~90.6%**; the paper's 93.0% inherits the unbacked MS cell.
- **Writer-model risk**: TR 88.7 was measured on a gpt-5.4-mini *writer*; the cheapest merged stack uses gpt-4o-mini writer (iter27 says writer model is "no measurable advantage", but unverified for the TR `start_date` path). Validation must check this; fallback = gpt-5.4-mini writer globally (single writer either way).

## Deferred (not blocking a first measurement)
- MS resolver carve-out (1-line qid `60159905` bypass-suppression from `ms-iter19-restart`).
- MS context-augmentation wiring (kept off by default).

## Validation plan (paid — requires approval; user is cost-sensitive)
- **Stage 0 offline sweep — DONE, $0, PASS.**
- Stage 1 smoke (30 Qs) ≈ $3–5 → pipeline integrity, ledger fires on targets.
- Stage 2a TR re-lock (133) ≈ $12–18 → reproduce iter31 88.7 on merged stack + gpt-4o-mini writer (the writer-risk test).
- Stage 2b MS measure (133) ≈ $12–18 → **first real measurement of the unioned ledger's MS** (the decisive unknown).
- Stage 3 full N=500 ≈ $45–75 → only after 2a+2b pass.

Cheapest decisive path = Stage 0→1→2a→2b ≈ **$34**, answers "does TR survive the cheap writer" and "is MS really > 82%" before committing to the full run.
