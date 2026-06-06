# Codex Round 2 Plan — Corrections + Final Pass

Your previous output (`CODEX_ROUND2_PLAN.md`) had the **structure right**
but used **hallucinated file paths and function names**. Here is the
ground truth from the actual repo. Revise the 45-row table to point at
REAL targets, and produce the final canonical plan.

## Hallucinated → Real

| You wrote | Reality |
|---|---|
| `benchmarks/longmemeval/resolvers.py:choose_duration_anchor` | **No such file.** The resolver lives in `benchmarks/longmemeval/symbolic_resolver.py` as a single class `LongMemEvalSymbolicResolver` with `_try_*` methods. There is no `choose_duration_anchor`. |
| `benchmarks/longmemeval/resolvers.py:resolve_anchor_date` | **No such function.** Closest current code: `_try_named_day_recall` (line 1645) which handles named-day questions. Date grounding ("two weeks ago" → absolute date) currently happens inside individual `_try_*` methods, ad-hoc. |
| `benchmarks/longmemeval/resolvers.py:resolve_order_candidates` | **No such function.** Closest: `_try_order_among` (line 532). |
| `benchmarks/longmemeval/resolvers.py:normalize_date_diff` | **No such function.** Closest: `_try_diff_between` (line 980), `_try_diff_since` (line 1201), `_try_diff_ago` (line 1137), `_try_diff_since_when` (line 1449). |
| `benchmarks/longmemeval/commonstack_round2.py:late_fusion_retrieve` | **No such file.** No late-fusion code exists in this repo today. Needs to be CREATED. |
| `benchmarks/longmemeval/commonstack_round2.py:build_evidence_ledger` | **No such file.** No ledger code today. Needs to be CREATED. |
| `benchmarks/longmemeval/qa_rules.py:apply_qa_rules` | **No such file.** qa_answer rules live in `configs/longmemeval_profile.yaml` under `profiles.longmemeval.templates.qa_answer` (a YAML literal block, ~264 lines, loaded via `load_prompt_profiles` and injected into the reader prompt). |

## Real file layout (line numbers verified)

### `benchmarks/longmemeval/symbolic_resolver.py` (2092 lines)
- `class _Concept` (line 71) — internal data
- `class LongMemEvalSymbolicResolver` (line 79)
  - `_topk_dated` (223), `_extract_required_nouns` (271)
  - `_best_concept` (293), `_best_recent_concept` (307)
  - `_find_is_start_concept` (339) ← already has Pass 3 EARLIEST fallback
  - `_best_recent_concept_with_nouns` (441)
  - `_try_order_among` (532)
  - `_try_count_among` (779)
  - `_try_diff_before` (952), `_try_diff_between` (980)
  - `_try_which_first` (1019)
  - `_try_chronological_order` (1059)
  - `_try_rank_among` (1100)
  - `_try_diff_ago` (1137)
  - `_try_diff_since` (1201)
  - `_try_relative_ago_recall` (1273)
  - `_try_diff_since_when` (1449)
  - `_try_duration_activity` (1539)
  - `_try_named_day_recall` (1645)
  - `_try_latest_value` (1997)
  - `_try_topic_recall` (2055)
  - `_detect_unit` (2083)
- `def render_symbolic_block(result)` (2091) — formats resolver output for reader

The `resolve(query)` method (line 176) is the dispatch — it walks
`_try_*` methods until one returns non-None.

### `benchmarks/longmemeval/run_eval.py` (~2500 lines)
- `call_llm` (135) — single LLM call wrapper
- `_parse_longmemeval_date` (247)
- `is_temporal_question` (281) ← could be the basis for the shape router
- `build_temporal_block` (286)
- `build_topic_timeline_block` (800) ← X1 TR-α implementation
- `build_assistant_recall_block` (888)
- `generate_answer` (961) ← the reader call. THIS IS THE INSERTION POINT for the gated answer path
- `_is_junk_reader_output` (1028)
- `download_data` (59), reader/judge plumbing throughout
- The driver `main` is at the bottom

### `configs/longmemeval_profile.yaml`
- `profiles.longmemeval.templates.qa_answer` (line 217 onwards) — YAML
  literal block containing reader system+user prompts. All round-1
  rules live here. New rules MUST be added here, not in a separate
  python module. Reader prompt is assembled in `generate_answer`.

### `src/cognifold/agent/batch.py`
- `BATCH_SYSTEM_PROMPT` ← writer system prompt, 4 rules currently. DO
  NOT propose changes (iter28-30 all broke from writer changes).

## Implementation mapping for your fix mechanisms

Re-use these CANONICAL targets in your revised 45-row table:

- `A:*` (any ledger shape) → **NEW module**:
  `benchmarks/longmemeval/round2_evidence_ledger.py`. Suggested
  functions: `detect_question_shape(question) -> Shape`,
  `late_fusion_retrieve(question, graph_hits, raw_messages, *, k_graph=16, k_chunk=12) -> tuple[list, list]`,
  `build_evidence_ledger(question, shape, fused_context) -> dict`,
  `answer_from_ledger(question, ledger) -> str | None`.
  - Integration: in `benchmarks/longmemeval/run_eval.py:generate_answer`,
    BEFORE the reader call, call `detect_question_shape`; if not
    `"other"`, route through `build_evidence_ledger` and
    `answer_from_ledger`; backoff to existing reader path.
- `B:chunk_fusion` → **SAME NEW module** (`round2_evidence_ledger.py`
  `late_fusion_retrieve` function). The "raw event chunks" come from
  the session messages stored in the graph nodes' `data.session_text`
  or equivalent — you must inspect to confirm where raw user/assistant
  messages live. If unsure, name the field with `# TODO: verify field name`.
- `resolver:*` → **NEW methods on `LongMemEvalSymbolicResolver` class
  in symbolic_resolver.py**. Suggested:
  - `_resolve_anchor_date(query, candidate_concept)` (named-day +
    relative-time → absolute date helper, used by multiple `_try_*`
    methods). Call it from `_try_named_day_recall`,
    `_try_diff_since_when`, etc.
  - `_choose_duration_anchor(query, candidates)` (deterministic anchor
    picker for duration_since_start; replaces / augments
    `_find_is_start_concept` Pass 3 EARLIEST fallback so it does NOT
    fire on recovery/end-state questions).
  - For order: patch `_try_order_among` to backfill candidates from
    late-fusion if fewer than `requested_rank`.
  - For date_diff: patch `_try_diff_between` to use exclusive
    arithmetic by default; explicit "including" → inclusive.
- `qa_rule:"..."` → **YAML block additions to
  `configs/longmemeval_profile.yaml:profiles.longmemeval.templates.qa_answer`**.
  ≤ 12 lines per rule, cited qid at end, no duplication with existing
  iter31 rules. (We have 8 iter31 rules already there — check before
  adding.)

## Other corrections / sanity checks

1. **iter31 already has these qa_answer rules** (do not re-propose):
   - DURATION-SINCE-START
   - AGE-INFERENCE (case d01c6aa8)
   - PLANNED→COMPLETED "today" (case gpt4_68e94288)
   - INCLUSIVE-BOUNDARY (case gpt4_4fc4f797)
   - COMPARATIVE EARLIER=FIRST (case gpt4_0b2f1d21)
   - EXHAUSTIVE-COUNT exclude-anchor (case a3838d2b — but this case
     still fails! see TR-13)
   - BOOKING vs PLANNING (case 982b5123)
   - `_abs` both-entities check (case c8090214_abs — but this case
     still fails! see TR-14)
   - CHRONOLOGICAL-SCAN (X4, uses TOPIC_TIMELINE)

   If your proposed qa_rule overlaps any of the above, refine it or
   say the existing rule needs strengthening, with the specific change.

2. **`_try_diff_since` calendar-month patch you proposed** maps to
   `symbolic_resolver.py:_try_diff_since` (line 1201). Inspect the
   actual function body before committing to the patch — the
   `days/30` pattern may or may not be there literally.

3. **`_find_is_start_concept` patch** maps to
   `symbolic_resolver.py:_find_is_start_concept` (line 339). Your
   prior critique correctly identified that EARLIEST fallback is
   wrong for recovery/state-transition questions. Confirm and
   propose the precise gate (e.g., only fire EARLIEST when query
   contains "started/began/joined/picked up", NOT for
   "recovered/healed/got over").

4. **2 disputed cases** stay deferred:
   - `370a8ff4` (TR-03 in your prior numbering)
   - `eac54add` (TR-10 in your prior numbering)

   You correctly marked these as `defer:disputed_annotation_issue_*`.
   Keep them.

5. **Round-1 iter31 has graph_node_count ≥ 800 across all 133 TR
   qids** — i.e. writer is fine, graphs are healthy. So your
   `B:chunk_fusion` claims must be about retrieval missing chunks
   that DO exist in graph nodes (just not surfaced to top-k or
   timeline). Late fusion = pull from graph node `description` fields
   or `data.session_text` (verify field name) over a wider BM25 pass,
   then dedupe by `node_id`.

## Deliverable for this pass

Produce the **final canonical round-2 plan** as a single markdown
document with:

1. **Section 1 — Per-case fix table (45 rows, real targets)**
   - Same row schema as before, but `target file:func` column must
     reference REAL files and functions (or, for new code, the new
     file path + suggested function name).
   - Mechanism column unchanged (`A:*`, `B:chunk_fusion`,
     `qa_rule:...`, `resolver:...`, `defer:...`).
   - Add a column `existing iter31 rule reuse?` — YES if the existing
     iter31 qa_answer rule should cover this case but isn't firing;
     in that case, propose the SMALLEST strengthening.

2. **Section 2 — Architecture spec, finalized**
   - Final signatures with REAL imports and integration line numbers
   - `round2_evidence_ledger.py` skeleton (≤ 200 lines)
   - Smallest patch list for `symbolic_resolver.py` (function-by-function)
   - YAML block additions for `qa_answer` (with leading existing-rule
     check)
   - `generate_answer` integration (specific line number)

3. **Section 3 — Smoke test plan**
   - 6-10 qids that validate the implementation before full run

4. **Section 4 — Bottom line (unchanged from prior unless evidence
   changes the projection)**

## Reasoning effort
xhigh. You have inline 45 cases from the previous payload — assume
you remember them. If you don't, the user will paste again.

Begin.
