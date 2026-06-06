# CogniFold × LongMemEval — Round 2 Per-Case Fix Briefing

You (Codex) are being re-invoked. Your previous critique
(`CODEX_CRITIQUE.md`) is **accepted in principle**: gated answer-path
+ chunk-level late-fusion retrieval are the two structural changes
we want to ship in round 2.

This briefing **constrains** your task and **adds the data** you
need:

1. Scope: **TR + MS ONLY**. We do not care about KU / SSA / SSP / SSU
   for round 2. If any proposed fix risks regression on TR or MS, say
   so; if it touches KU/SSA/SSP/SSU at all, ignore that risk —
   not our concern this round.
2. Ambition: **one-shot to SOTA**. SOTA target = beat Mastra's
   published 94.87% on N=500. Realistically that means MS ≥ 90% and
   TR ≥ 93% on N=500. If you think that's not achievable in one
   round on this stack, say so and tell us the realistic ceiling.
3. Output: a **per-case fix table that covers EVERY one of the 45
   wrong cases below** (15 TR + 30 MS), per our skill's HARD-GATE
   and full-coverage habit. No case may be silently skipped.
4. Method: operate as if you were Claude under our skill
   `lme-auto-optimize` (see `§ Skill Constraints` below for the
   parts you must honor). Critically: provider routing is HARD
   (gpt-5.4-mini → commonstack only, judge gpt-4o → OR, embed → OR;
   do NOT propose substitutes), and rule-style guide caps rules at
   12 lines each with a cited qid.

---

## Skill Constraints (from `.claude/skills/lme-auto-optimize/SKILL.md`)

### PROVIDER-ROUTING-HARD-RULE
- gpt-5.4-mini → commonstack only (writer / reader / rerank)
- gpt-4o judge → OpenRouter
- text-embedding-3-small → OpenRouter
- NEVER swap reader/writer to OR gpt-5-mini (gpt-5-mini ≠ gpt-5.4-mini,
  invalidates baselines)

### HARD-GATE for code changes
1. Inspect at least 5 wrong cases' full_context to verify the
   proposed fix matches the actual failure mode (not a guess).
2. Present a per-cluster fix table with: cluster name, # cases,
   proposed change, file/line, risk to other types.
3. Get explicit approval before editing source.

### Rule-style guide (`references/rule-style-guide.md`)
- One rule = one cluster
- Every rule body must end with `(case <qid>)`
- Worked examples use the actual qid's question + context
- HARD 12-line ceiling per rule (iter29a's +200 lines caused MS −27pp)
- Negative form preferred ("NEVER", not "AVOID")
- Cross-reference clusters when they overlap

### Full-coverage habit
- Every wrong case in the targeted clusters MUST appear in the fix
  table with a proposed change OR an explicit "no fix — defer"
  reason. No cherry-picking.

### Failure taxonomy (`references/failure-taxonomy.md`)
- **TR-A duration_since_start**: writer didn't extract START concept,
  resolver picks LATEST not EARLIEST
- **TR-B order_among**: resolver finds < N candidates because of
  BM25 top-K cutoff or strict verb filter
- **TR-C named_day disambig**: multiple candidates on same day,
  resolver picks wrong by BM25
- **TR-D date_diff off-by-one**: inclusive vs exclusive boundary
- **TR-E refusal-with-data**: derivable but reader refused
- **TR-F derived_time**: relative offset arithmetic
- **TR-G _abs / which_first / count_among**: misc
- **MS-A undercount**: reader stops scanning after 2-3 hits
- **MS-B refusal-with-data**: AGE-INFERENCE failure etc.
- **MS-C wrong_winner**: picks wrong of 2 candidates
- **MS-D _abs misses refusal**

---

## Current state recap

- iter31 round 1 (TR-only N=133): **118/133 = 88.7% strict**
  (+8.3pp vs iter27 80.5%), 0 empty HY.
- iter31 stack: gpt-5.4-mini W1/W2/W3/Reflector OFF, X1
  topic_timeline ON, X4 CHRONOLOGICAL-SCAN ON, 8 new qa_answer rules.
- Round 2 target: **MS to ≥90%, TR to ≥93% on N=500**, single iter.
- Provider state: commonstack 10p–20p stable; health-check every 10
  results is mandatory.

---

## Accepted from your previous critique

You proposed two structural moves; we accept both as the round-2
backbone:

**(A) Question-shape router + structured evidence pass**
(in `run_eval.py`). Detect: how-many / total / what-order /
since-before-after / `_abs`. Emit JSON evidence ledger
`[{item, date, value, evidence_id}]`. Then count / order / refuse
deterministically. Gated, auditable.

**(B) Chunk-level late fusion retrieval**.
Union graph retrieval with cheap lexical/BM25 retriever over raw
message/event chunks. Trigger especially for count/order/anchor
questions. Helps both TR-B order misses (missing JetBlue, Museum of
History) and MS-A undercount when items got merged away.

Your job in this round-2 briefing: **map each of the 45 wrong cases
to a fix that either (i) is handled by A or B, (ii) needs a small
case-specific case-cited qa_answer rule (12-line max), (iii) is a
tiny resolver patch, or (iv) is explicitly out-of-scope (judge
variance, public LongMemEval annotation dispute, or retrieval-miss
with no signal in context).**

For each case, deliver:

```
| qid | cluster | root cause (one line, from the full_context evidence) |
fix mechanism (A / B / qa_answer-rule / resolver-patch / defer-reason) |
target file:line if known | regression risk to other TR/MS cases |
expected delta |
```

If a fix is "A" (gated answer path), spell out the exact question-
detection regex and the JSON ledger shape for that question type.

If a fix is "B" (chunk fusion), say what evidence in the
full_context tells you the item is in raw text but not in retrieved
context.

If a fix is "qa_answer-rule", write the actual rule body (≤12 lines)
in the row, ending with `(case <qid>)`.

If a fix is "resolver-patch", point to the function name in
`benchmarks/longmemeval/symbolic_resolver.py` and sketch the change
in 3-5 lines of pseudo-code.

If "defer", give the exact reason (e.g., "LongMemEval issue #41
disputed labeling", "retrieval miss with no in-context signal",
"judge subjective tie").

---

## Reading order

1. This file — skill constraints + your task
2. `CODEX_CRITIQUE.md` — your prior critique (referenced)
3. `CODEX_BRIEFING.md` — the original briefing (full project context)
4. `benchmarks/longmemeval/HISTORY.md` — canonical iter history,
   read iter19 + iter27 + iter28-30 + iter31 sections
5. `benchmarks/longmemeval/symbolic_resolver.py` — current resolver
   implementation; line-verify your patches against it
6. `configs/longmemeval_profile.yaml` — current `qa_answer` rules;
   verify you are not duplicating a rule that already exists
7. `benchmarks/longmemeval/run_eval.py` — `build_topic_timeline`,
   reader call, rerank-pool code; verify gated-answer-path
   architecture proposal
8. `src/cognifold/agent/batch.py` — `BATCH_SYSTEM_PROMPT`; verify
   any writer-rule proposal does not contradict
9. **The 45 wrong cases below** — these are the data. Inspect each
   one's `full_context` before proposing a fix.

---

## The 45 wrong cases (full_context excerpts)

The complete dump of all 15 TR + 30 MS wrong cases, each with
question, ground truth, iter31/iter27 hypothesis, symbolic pattern,
graph_node_count, and a 6000-char excerpt of `full_context`, is at:

**`/tmp/all_wrongs.md`** (~294KB)

Read it. For each case, the `full_context` shows the TOPIC_TIMELINE
block, CONCEPTS block, EVENTS block, and any other retrieval-side
data the reader actually received. The right test of a proposed fix
is: would this fix have made the reader produce GT *given the
full_context as shown*? If the answer is no (because the relevant
evidence is not in `full_context` at all), the fix is either
"B — chunk fusion" (and you must explain what raw-text evidence
would have surfaced it) or "defer — retrieval miss".

---

## Deliverable

A single markdown document with two sections:

### Section 1 — Per-case fix table (45 rows)

15 rows for TR (numbered TR-01 … TR-15 matching `/tmp/all_wrongs.md`),
30 rows for MS (numbered MS-01 … MS-30). No case skipped. Each row
uses the schema above (qid / cluster / root cause / fix mechanism /
target / risk / expected delta).

### Section 2 — Round-2 architecture spec

For the two structural changes (A) and (B):
- Exact function signatures (Python)
- Exact question-detection regexes
- Exact JSON ledger shapes per question type
- Exact integration point in `run_eval.py` (line number)
- Backoff behavior when the structured path returns "I don't know"
- Test plan: which specific qids will validate this path before
  N=500
- Estimated dev hours

For any qa_answer rules:
- One rule per cluster, ≤ 12 lines, cited qid, written in negative
  form where appropriate, no overlap with existing rules in
  `configs/longmemeval_profile.yaml`

For any resolver patches:
- Function name, before/after diff, justification, regression test
  qids

### Section 3 — Bottom line on SOTA

Honest call: what's the highest N=500 score this round-2 plan can
realistically deliver? Specifically:
- TR projection (with disputed cases excluded)
- MS projection
- KU/SSA/SSP/SSU projection (we're not changing rules for them but
  some changes will leak)
- Total N=500 projection with confidence band

If you think 94.87% is out of reach in one round and you can name
the structural change beyond round 2 that would close the rest of
the gap, say so in two sentences.

---

## Reasoning effort

xhigh. The local exec tool should work this time
(`sandbox_mode="workspace-write"` is configured). Verify you can
read the 9 files listed above and `/tmp/all_wrongs.md` before
writing the deliverable. If exec still fails, say so up front and
proceed with the briefing-only critique.

---

## What you will NOT do

- Propose changing the gpt-5.4-mini SKU
- Propose changing the provider routing
- Propose KU / SSA / SSP / SSU rules
- Propose anything that takes > 4 hours of dev work (we have 1
  round)
- Propose writer-prompt changes that touch the BATCH_SYSTEM_PROMPT
  beyond minimal additions (iter28-30 each broke MS by changing the
  writer; assume any writer change has high regression risk)
- Skip any of the 45 wrong cases

Begin.
