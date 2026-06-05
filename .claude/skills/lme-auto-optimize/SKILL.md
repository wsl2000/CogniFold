---
name: lme-auto-optimize
description: This skill should be used when the user asks to "optimize LongMemEval", "fix TR failures", "improve MS / KU / SSU / SSP / SSA", "find next iter improvements", "analyze wrong cases", or starts an iter cycle on the longmemeval-iter line. Composes superpowers' systematic-debugging + writing-plans + verification-before-completion with LME-specific failure taxonomy, per-cluster fix recipes, and the TR-only / N=500 validation pipeline.
---

# LongMemEval Auto-Optimize

A repeatable workflow for one iter cycle on LongMemEval. Built on top
of `superpowers` skills (`systematic-debugging`, `writing-plans`,
`verification-before-completion`, `subagent-driven-development`).

<PROVIDER-ROUTING-HARD-RULE>
This is a HARD constraint, encoded in `feedback-lme-routing` memory and
repeated by the user multiple times. Violating it wastes the user's
prepaid commonstack credit and/or burns OpenRouter spend:

- **gpt-5.4-mini → commonstack** (writer / reader / rerank — only
  commonstack serves this exact model SKU)
- **judge `gpt-4o` → OpenRouter** (commonstack lacks it)
- **embed `text-embedding-3-small` → OpenRouter** (commonstack has no
  `/embeddings` endpoint)
- **ANY other chat model** (gpt-4o-mini, gpt-5-mini, gpt-5, claude, etc.)
  → OpenRouter. **NEVER commonstack.**

When probing commonstack health, use `openai/gpt-5.4-mini` —
probing with `openai/gpt-4o-mini` against commonstack is wrong (we
do not route 4o-mini through commonstack and the probe result is
misleading about the provider's state for our workload).

When commonstack breaks, do NOT propose "route reader to OR gpt-5-mini"
as a fallback. gpt-5-mini ≠ gpt-5.4-mini — the swap changes the model
and invalidates all comparisons against the iter27 baseline. The only
valid fallback is "wait for commonstack" or "run on the subset that
already completed."
</PROVIDER-ROUTING-HARD-RULE>

<HARD-GATE>
Before proposing or implementing ANY code change, you MUST:
1. Pull the most recent `wrong_cases.json` for the iter we are
   improving on (default: iter27 baseline at `runs/iter27_*/`).
2. Run the cluster categorization script (see Step 1 below) and
   show the user the taxonomy table.
3. Inspect at least 5 wrong cases' `full_context` to verify each
   proposed fix matches the actual failure mode (not a guess).
4. Present a per-cluster fix table with: cluster name, # cases,
   proposed change, file/line, risk to other types.
5. Get the user's explicit approval before editing any source.
</HARD-GATE>

## Triggers

Use this skill when the user says things like:
- "Optimize LongMemEval TR / MS / KU"
- "Find next iter improvements"
- "Analyze the wrong cases"
- "Fix the duration_since_start cluster"
- "Run TR-only N=133 and see what's left"
- "Start iter32" (or any new iter number)

Do NOT use this skill for:
- Pure infrastructure changes (Makefile, CI, dependency bumps)
- Documentation-only edits
- New benchmark integration (use `cognifold-bench-run` instead)

## Workflow

### Step 0 — Read iter history

```bash
.venv/bin/python .claude/skills/lme-auto-optimize/scripts/iter_history.py
```

Outputs a per-iter timeline: which iter changed what, score delta,
known regressions. Critical to avoid re-introducing iter27's W2
regression or iter30's W3 regression. The fundamental lesson:
**every writer enrichment pass added after iter19 hurt MS.**

### Step 1 — Pull + cluster wrong cases

```bash
# default base: iter27. Override with --base <run-folder>.
.venv/bin/python .claude/skills/lme-auto-optimize/scripts/cluster_failures.py \
    --base benchmarks/longmemeval/runs/iter27_gpt54mini_full_n500_W1W2 \
    --type temporal-reasoning
```

Groups wrong cases by failure pattern (taxonomy below). Outputs a
table like:

```
TR failure clusters in iter27 (26/133 wrong = 80.5% acc):
  A duration_since_start  10  ← "how long had I been X-ing when Y"
  B order_among            4  ← "order of N events"
  C named_day disambig     3  ← multi candidate same day
  D date_diff off-by-one   3  ← boundary convention
  E refusal-with-data      5  ← (overlaps with A)
  F derived-time           1  ← relative offset arithmetic
  G _abs / which_first     3
```

Then for EACH wrong case, dump:
- qid
- question (full)
- GT
- HY (the wrong answer)
- failure pattern (cluster)
- full_context length + grep for key entities (verify they ARE in context)

This step takes ~30 seconds. Do NOT skip.

### Step 2 — Per-case fix table

For each wrong case, fill a row:

| qid | cluster | root cause (one line) | fix location | risk |
|---|---|---|---|---|
| 370a8ff4 | A | `_try_diff_since_when` picks latest "recovered" mention | `symbolic_resolver.py` add strict "recovered/healed/got over" verb match → use EARLIEST date | low |
| gpt4_7abb270c | B | order_among bypass=True with wrong list | `symbolic_resolver.py` force bypass=False for ≥4-item lists | low |
| ... | | | | |

Then **collapse by cluster** — usually 4-5 cluster-level fixes
cover 15-20 cases. Show the user.

### Step 3 — Predict score impact

For each fix, estimate (be honest — these are upper bounds):
- # cases it might fix (count, not %)
- realistic fire rate (gpt-5.4-mini medium effort: ~50-70%)
- realistic Δ = (cases × rate) ÷ 500 × 100

Sum the realistic Δ and add to baseline. **If sum < target Δ,
you do not have enough leverage in this iter — tell the user.**

Honest ceiling for any single iter on the current architecture:
~+3pp total on N=500. Beyond that requires structural change
(writer model upgrade, retrieval architecture, or reader model
upgrade).

### Step 4 — Implement, ONE commit per cluster

Use `subagent-driven-development`. One subagent per cluster:
- Instructions: precisely scoped to the cluster's fix table
- No `_internal` cleanup, no `_helper` refactors — only the rows
  listed in the table.

After each subagent returns, run the import sanity check:

```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from benchmarks.longmemeval.symbolic_resolver import LongMemEvalSymbolicResolver
from cognifold.agent.batch import BATCH_SYSTEM_PROMPT
import yaml; yaml.safe_load(open('configs/longmemeval_profile.yaml'))
print('OK')
"
```

Commit immediately if green. Commit message references the
cluster letter (A/B/C/...) and the qids fixed.

### Step 5 — Smoke (one qid from the targeted cluster)

```bash
# pick one cluster-representative qid that iter27 failed
bash scripts/run_iter31.sh /tmp/smoke1.txt iter32_smoke 1
```

If `verdict=CORRECT` AND `graph_nodes > 800`, proceed. If wrong,
inspect the full_context — DO NOT proceed to N=133 with a broken
graph.

### Step 6 — TR-only N=133 (or MS-only / KU-only depending on target)

```bash
bash scripts/run_iter31.sh benchmarks/longmemeval/qid_sets/tr_only.txt \
    iter32_tr_only 5
```

Wallclock at writer effort=medium, 5 parallel commonstack:
- TR-only N=133: ~3h
- MS-only N=133: ~3h
- Full N=500: ~10h

### Step 6.5 — Liveness check every 10 results (MANDATORY)

While Step 6 is running, the workflow MUST poll
`scripts/health_check.py` every time 10 new results land in the
batch dirs. If it prints `STOP — ...` on the last line, immediately
`pkill` workers and inspect — DO NOT let the run continue with a
broken stack producing empty hypotheses.

Recommended monitor body (Bash, persistent):

```bash
prev=0
while true; do
  N=$(cat benchmarks/longmemeval/output_i31_b*/hypothesis.jsonl 2>/dev/null | wc -l)
  N=$(( N + $(wc -l < runs/iter32_tr_only/hypothesis.jsonl 2>/dev/null || echo 0) ))
  if [ "$N" -ge $(( prev + 10 )) ]; then
    OUT=$(.venv/bin/python .claude/skills/lme-auto-optimize/scripts/health_check.py \
            --run-dir runs/iter32_tr_only \
            --batch-glob "benchmarks/longmemeval/output_i31_b*" \
            --baseline runs/iter27_gpt54mini_full_n500_W1W2 \
            --type temporal-reasoning)
    echo "$OUT" | tail -8
    if echo "$OUT" | tail -1 | grep -q "^STOP"; then
      pkill -KILL -f "run_eval.*output_i31_b"
      pkill -KILL -f "run_iter.*.sh"
      echo "TERMINATED-BAD" && break
    fi
    prev=$N
  fi
  [ "$N" -ge 133 ] && break
  sleep 60
done
```

Danger thresholds (any → STOP):
- empty hypothesis rate > 20% (provider 429 / timeout cascade)
- accuracy more than 10pp below baseline on common qids
- median `graph_node_count` < 300 (writer dropping events)
- `verdict=="ERROR"` rate > 5%

**Empirical provider limits (commonstack, 2026-06-05)**:
- 1 parallel: 0% empty
- 5 parallel writer-medium + reader max_tokens=24K: ~25% empty
- 25 parallel: ~70% empty

Conclusion: the empty rate is TPM-dominated, not RPM. To run > 3
parallel safely on commonstack, lower reader `max_completion_tokens`
to 8K and/or use a separate provider for reader.

### Step 7 — Apples-to-apples vs baseline

```bash
.venv/bin/python .claude/skills/lme-auto-optimize/scripts/apples_compare.py \
    --current iter32_tr_only \
    --baseline iter27_gpt54mini_full_n500_W1W2
```

Outputs Δ per type, regressions list (qids that the BASELINE got
right but we got wrong), improvements list. Decision:
- Net Δ ≥ +1pp AND no cluster regressed > 2pp → commit, push, merge PR
- Otherwise → analyze regressions, fix, repeat from Step 4

### Step 8 — Verification (superpowers)

Before claiming the iter is done, you MUST:
1. Re-run apples-to-apples to confirm the saved metrics match
2. Verify the iter folder has a CHANGES.md with score + per-type breakdown
3. Verify the GitHub issue is closed and the PR is updated

## Failure taxonomy

See `references/failure-taxonomy.md` for the complete list. The
top-level taxonomy:

**MS (multi-session)**:
- UNDERCOUNT (~22 cases on iter27): reader stops scanning before seeing all relevant entities
- REFUSAL-WITH-DATA (~5 cases): refuses when answer is derivable
- WRONG-WINNER (~2 cases): picks the wrong of two candidates

**TR (temporal-reasoning)**:
- duration_since_start (~10 cases)
- order_among (~4 cases)
- named_day disambig (~3 cases)
- date_diff off-by-one (~3 cases)
- refusal-with-data (~5 cases)
- derived-time (~1 case)
- _abs / which_first / count_among (~3 cases)

**KU (knowledge-update)**:
- supersession-confusion: picks outdated value
- count-undercount: like MS UNDERCOUNT but for KU "N times" Qs

**SSU / SSP / SSA**: usually retrieval miss or judge variance —
not structurally addressable in a single iter.

## Rule style guide

See `references/rule-style-guide.md`. Key principles:
- One rule = one cluster
- Every rule references a specific iter27 wrong-case qid in parentheses
- Worked examples use the actual qid's question + context
- No rule longer than 12 lines (anti-bloat; iter29a's +200 lines caused MS -27pp)

## What NOT to do

Lessons learned from iter27 → iter30:
1. **Do NOT add writer enrichment passes** (W1 typed-attr, W2
   event_date, W3 START) on top of iter19 stack. Every one hurt
   MS more than it helped TR.
2. **Do NOT compress qa_answer worked examples** without per-case
   verification (iter30 cleanup cost MS −1.5pp from removing
   iter02/10/13 examples that were actively used).
3. **Do NOT add reasoning to the reader effort** above "high" —
   gpt-5.4-mini effort=high is the ceiling; nothing past it.
4. **Do NOT enable count_among, order_among (>3 items),
   which_first, relative_ago_recall** — all 0-acc on iter27 N=500.
5. **Do NOT trust smoke = 1 qid as validation** — too noisy.
   Always TR-only or MS-only N=133 minimum.

## When TR ceiling reached (~88-90%)

The current resolver-pattern architecture has an empirical ceiling
around 88-90% TR on N=500. To go beyond requires:
- Reader upgrade gpt-5.4-mini → gpt-5 (5-10x cost)
- Retrieval rewrite: BM25+rerank → chronological observation block
- Code-augmented reasoning (PoT/PAL) for date arithmetic

These are out-of-scope for a single iter. Tell the user.
