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

<OPERATIONAL-HABITS>
These are user-imposed habits, repeated across many sessions. Mirrored in
the `feedback-lme-*` memory entries. Skim them every time before starting
an iter — forgetting any of these costs the user time and money.

**Branch discipline (`feedback-lme-branch`)**
- All iter work commits to the `longmemeval-iter` branch.
- Do NOT create per-iter branches (`iter29_*`, `tier3`, `iter32-dev`)
  except for BIG risky surgery (writer/reader model swap, retrieval
  rewrite). When you do branch, name it semantically (e.g.
  `tr-only-optimization`, `iter30_cleanup`), not by iter number.
- Default action: `git checkout longmemeval-iter` before editing.

**Iter folder convention (`feedback-lme-iter-folder`)**
- Every run output lives in `benchmarks/longmemeval/runs/iter<NN>_<label>/`.
  Example: `runs/iter31_tr_round1/`, `runs/iter27_gpt54mini_full_n500_W1W2/`.
- Each iter folder MUST contain a `CHANGES.md` with:
  - one-paragraph summary of what changed
  - the score and per-type breakdown
  - any regressions called out in plain text
  - the launcher invocation used
- `iter_history.py` (Step 0) parses this folder layout; deviating
  breaks the per-iter timeline view.

**Batching discipline (`feedback-batch-edits`, `feedback-batch-full-coverage`)**
- Do NOT trickle one tiny code change per failure case. Bundle all
  per-cluster fixes into ONE commit per cluster (`Step 4`).
- BEFORE running, present in chat the FULL per-case fix table (every
  wrong qid, every proposed change). User reviews once, approves
  once, then we run once.
- After each cluster's commit, smoke ONE representative qid (Step
  5) before continuing to the next cluster.

**Full-coverage habit (HARD — `feedback-batch-full-coverage`)**
- "Every iter is the last iter" — when the user picks target categories
  (e.g. TR + MS), the analysis MUST list ALL wrong cases in those
  categories with a per-case fix proposed. Do NOT cherry-pick the
  easy ones, do NOT leave any case as "skip / out-of-scope" without
  an explicit reason in the table.
- Inspect at least one `full_context` per cluster (HARD-GATE Step 3)
  before proposing a fix — guessing at the failure mode without
  verification has caused 3 of the last 4 iters to introduce
  regressions (iter27 W2, iter29a bloat, iter30 W3).
- If a case has NO known fix (e.g. judge-strict variance, retrieval
  miss with no signal in context), say so in the table as
  "(no fix in current architecture — defer)" — explicitly, not by
  omission.
- The fix table covers cases A through Z; the user gets to see EVERY
  row before approving any code change.

**Audit discipline (`feedback-full-audit`)**
- When asked to audit a case, STORE the full `full_context` —
  never the truncated `[:120]` preview that ends up in console
  output. The audit file must let the user re-grep months later
  without having to re-run the eval.
- Format: `audits/<qid>_<iter>.md` with the question, GT, HY, full
  context, and your reasoning.

**Issue → PR version management**
- Every iter cycle gets:
  1. A GitHub issue describing the cluster being targeted + the
     hypothesis ("Fix TR-A duration_since_start, target +5 cases").
  2. A draft PR on a dedicated branch, linked to the issue via
     `Closes #<n>` in the PR body.
  3. Per-cluster commits pushed to the PR's branch.
  4. PR merged to `longmemeval-iter` (NOT `main`) when N=133/N=500
     verifies the delta. Issue auto-closes.
- Do NOT use long-lived feature branches as a stash for unproven
  experiments — make it an issue + draft PR so the user can review.

**Doc-guard sentinel**
- The repo has a PreToolUse hook (`doc-guard`) that intercepts
  `git commit` when `src/` is staged AND the doc sentinel is stale.
- Refresh the sentinel before any commit that touches `src/`,
  `benchmarks/`, `configs/`, or `scripts/`:
  ```bash
  date +%s > .claude/docguard_last_run
  git add -f .claude/docguard_last_run
  ```
- Do NOT skip with `--no-verify` — fix the underlying staleness
  instead.

**Subagent-driven implementation (Step 4)**
- For multi-cluster iter changes, spawn one `general-purpose`
  subagent per cluster. Each subagent's prompt should:
  - Name the cluster + qids
  - Cite the file path + line range to edit
  - Include the rule style guide (`references/rule-style-guide.md`)
  - Forbid `_internal` / `_helper` refactors outside the cluster scope
  - Return a one-paragraph summary of what was changed
- After each subagent returns, do the import sanity check (Step
  4 below), commit immediately, then move to the next cluster.

**N=133 ≠ N=500**
- A green TR-only N=133 is necessary but NOT sufficient. Some
  fixes that help TR cluster A hurt MS cluster B in ways that
  only show up on N=500. Always re-run on N=500 before claiming
  a win — and re-run apples-compare on N=500 too (the regression
  list often grows from TR-only → full).
</OPERATIONAL-HABITS>

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
    iter32_tr_only 10
```

**Parallel = 10** (was 5; bumped 2026-06-05 after empirical
verification that commonstack-with-healthy-balance handles 10p
cleanly when paired with the Step 6.5 health-check). If empty rate
> 20% by the first 10-check, the monitor auto-kills and the user
should drop to 5p for the recovery run.

The launcher (`scripts/run_iter31.sh`) bakes these flags in, and
this list IS the canonical config — match it when writing any
recovery / smoke script:

```
--model openai:openai/gpt-5.4-mini
--writer-model openai:openai/gpt-5.4-mini
--writer-reasoning-effort medium
--judge-model openai:openai/gpt-4o
--embedding openai:openai/text-embedding-3-small
--symbolic-resolver --symbolic-temporal --symbolic-bypass
--tr-topic-timeline                    # TR-α block (TR-only Qs)
--llm-rerank
--rerank-model openai:openai/gpt-5.4-mini
--rerank-reasoning-effort low
--rerank-pool 100                      # rerank candidates from BM25 top-100
--agg-max-context-chars 15000          # reader context budget
--batch-mode --llm-eval
```

Wallclock at writer effort=medium, 10 parallel commonstack:
- TR-only N=133: ~75-90 min
- MS-only N=133: ~75-90 min
- Full N=500: ~5h

Cost (commonstack rate ≈ $50/hr observed 2026-06-05):
- TR-only N=133: ~$60-100
- Full N=500: ~$200-300

### Step 6.5 — Liveness check every 10 results (MANDATORY at 10p)

At 10p the provider can fall over in 10-15 min (the 25p storm on
2026-06-05 burned $45 in 30 min before being noticed). The
mandatory monitor pattern is: **every 10 results, run
`health_check.py`. If STOP on last line, immediately pkill the
workers.** The user has been explicit on this — do not skip and
do not extend the interval beyond 10.

Recommended monitor body (Bash, persistent — drop into `Monitor`
or background loop). 10p version with 429-storm early-stop:

```bash
prev_done=$(wc -l < benchmarks/longmemeval/runs/iter32_tr_only/hypothesis.jsonl 2>/dev/null || echo 0)
last_check=$prev_done
while true; do
  N_BATCH=$(cat benchmarks/longmemeval/output_i31_b*/hypothesis.jsonl 2>/dev/null | wc -l)
  N_FINAL=$(wc -l < benchmarks/longmemeval/runs/iter32_tr_only/hypothesis.jsonl 2>/dev/null || echo 0)
  TOTAL=$(( N_BATCH + N_FINAL ))
  ACTIVE=$(pgrep -af "run_eval.*output_i31_b" | wc -l)
  ERR_429=$(grep -hc "HTTP/1.1 429\|balance" logs/iter31_b*.log 2>/dev/null | awk '{s+=$1}END{print s+0}')

  # Mandatory: every 10 results, run health_check
  if [ "$TOTAL" -ge $(( last_check + 10 )) ]; then
    HC=$(.venv/bin/python .claude/skills/lme-auto-optimize/scripts/health_check.py \
            --run-dir benchmarks/longmemeval/runs/iter32_tr_only \
            --batch-glob "benchmarks/longmemeval/output_i31_b*" \
            --baseline benchmarks/longmemeval/runs/iter27_gpt54mini_full_n500_W1W2 \
            --type temporal-reasoning 2>&1)
    LAST=$(echo "$HC" | tail -1)
    echo "[hc done=$TOTAL active=$ACTIVE 429=$ERR_429] $LAST"
    if echo "$LAST" | grep -q "^STOP"; then
      pkill -KILL -f "run_eval.*output_i31_b"
      pkill -KILL -f "run_iter31.sh"
      echo "TERMINATED-BAD: $LAST" && break
    fi
    last_check=$TOTAL
  fi

  # Early-stop on 429 storm before health_check would fire
  if [ "$ERR_429" -gt 100 ] && [ "$TOTAL" -lt $(( last_check + 5 )) ]; then
    pkill -KILL -f "run_eval.*output_i31_b"
    pkill -KILL -f "run_iter31.sh"
    echo "EARLY-STOP-429-STORM 429=$ERR_429" && break
  fi

  if [ "$TOTAL" -ge 133 ] || [ "$ACTIVE" -eq 0 ]; then
    echo "TERMINAL: done=$TOTAL active=$ACTIVE 429=$ERR_429" && break
  fi
  sleep 120
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
3. **Write a new section in `benchmarks/longmemeval/HISTORY.md`** for this iter (see below — MANDATORY, not optional)
4. **Update the Score summary table at the top of HISTORY.md** with the iter's row
5. **Update the Trajectory summary at the bottom of HISTORY.md** if this iter shifts the trajectory line
6. Verify the GitHub issue is closed and the PR is updated

### Step 8.1 — HISTORY.md update (MANDATORY)

`benchmarks/longmemeval/HISTORY.md` is the canonical hand-curated
record of every iter. `iter_history.py` (Step 0) generates a
machine-parsed timeline view, but the narrative — *why* each iter
was tried, what regressed, what the decision was — only lives in
HISTORY.md. If you do not write the section, future iters will
re-invent the same regression.

The section MUST include:

```markdown
## iterNN — <one-line title>

- **Score**: NN.N% strict (X/Y), partial N.N% — KEEP or REVERT?
- **NET vs <previous SOTA>**: ±N cases (±N.N pts)
- **Stack changes vs <baseline>**:
  - <bullet 1>
  - ...
- **By type vs <baseline>**:

  | type | this iter | baseline | Δ |
  |---|---|---|---|
  | ... | ... | ... | ... |

- **Key findings** (numbered, 3-5 items):
  1. <finding with case-level evidence>
  2. ...
- **Operational notes** (rate limits hit, provider issues, etc.)
- **Decision**: KEEP / REJECT / REVERT — and *why*
- **Branch state**: which branch, pushed or not
```

If the iter is REVERTED, still write a section (shorter) — the
revert reason is what future iters need to avoid re-introducing
the same change.

If the iter is partial / blocked (provider down, budget exhausted),
record the partial result and the block reason. Do NOT skip the
section — partial data is what flagged commonstack-balance-0 as a
recurring failure mode.

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
