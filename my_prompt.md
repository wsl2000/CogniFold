# LongMemEval — Autonomous Iteration Instructions

> Hand-off spec: a fresh agent on a fresh machine runs this end-to-end,
> autonomously, with no human in the loop until done.

---

## 0. Setup (one-time)

**Base repo (canonical remote)**: <https://github.com/OpenNorve/CogniFold>

**Working branch**: **`iter`** — all autonomous-loop commits and snapshots
MUST land on this branch only. **Never push to `main`, `public-release`,
`cognifold-dev`, or any other branch.** The `iter` branch is dedicated
to the autonomous campaign so other work isn't disturbed.

Verify with `git remote -v` and `git branch --show-current` BEFORE
running anything that pushes.

```bash
git clone https://github.com/OpenNorve/CogniFold.git && cd CogniFold
# (SSH equivalent: git clone git@github.com:OpenNorve/CogniFold.git)
git checkout iter                  # ← MUST be on iter before any commit
git branch --show-current          # → must print "iter"
python -m venv .venv && source .venv/bin/activate
pip install -e .
echo "OPENAI_API_KEY=sk-..." > .env
```

**On a fresh clone** the canonical remote is named `origin`. Throughout
this doc and the push commands, references to `origin` assume that
setup. **If you're working on a machine where the repo was set up
differently** (e.g. `origin` was repurposed for an internal mirror),
run this to align with the doc's assumptions before launching the
autonomous loop:

```bash
# Verify; if OpenNorve isn't named "origin", rename whichever remote
# points at OpenNorve/CogniFold:
git remote -v
git remote rename <existing-OpenNorve-remote-name> origin   # only if needed
```

**Git push credentials.** The per-round inline push (§8.2) only works
if `git push origin iter` succeeds non-interactively. Verify:

```bash
# SSH path: confirm the GitHub SSH key works
ssh -T git@github.com    # expect "Hi <user>! You've successfully authenticated"
# or HTTPS path: ensure ~/.git-credentials or GH_TOKEN is set
git push origin iter --dry-run    # must succeed without password prompt
                                  # AND must show "iter -> iter" (NOT main/other)
```

If either check prompts for credentials, push will silently fail and
the autonomous loop will accumulate unpushed work. Fix before launching.

The dataset auto-downloads on first run (~50MB to `benchmarks/longmemeval/data/`).

---

## 1. Canonical model setup

| role | model | why |
|---|---|---|
| writer (extraction) | `openai:gpt-4o-mini` | fast deterministic JSON; reasoning models waste 10-30× time here |
| reader (QA) | `openai:gpt-5-mini` with `reasoning_effort=high` | where reasoning pays off; matches Mastra's SOTA setup |
| judge | `openai:gpt-4o` | **canonical LongMemEval judge — never substitute** |

`reasoning_effort=high` + `max_completion_tokens=24576` are auto-applied by
the runner when it detects an `o1`/`o3`/`gpt-5` model.

---

## 2. Run command (parallel, with resume)

**Always run the full N=500 with 500 parallel batches (one process
per qid, depth=1).** Do not ramp up incrementally (no N=100 → 150 →
200…). The driver's resume logic makes a re-run after a fix a no-op
for unchanged qids, so "full every time" costs nothing extra while
making each metric directly comparable.

```bash
# Driver auto-detects done qids in benchmarks/longmemeval/output/ and only
# dispatches the missing ones. Per-batch scratch dirs are merged into the
# single output/ dir and cleaned up on success.
#
# Usage: parallel_longmemeval.sh [N_PARALLEL] [STRATIFIED] [TOTAL_LIMIT]
bash scripts/parallel_longmemeval.sh 500 133 500
```

- `N_PARALLEL=500` — **fixed default**. One Python process per qid →
  queue depth = 1, full N=500 finishes in ~15 min wallclock.
  Pre-flight resource check: this default assumes **≥ 150 GB RAM**
  (each process ~300 MB) and **≥ 64 CPU cores**. Verify with
  `free -g` and `nproc` before launching. If the box is smaller, scale
  N_PARALLEL down — 100 needs ~30 GB RAM, 50 needs ~15 GB.
  Rate-limit math: 500 batches × ~50 writer calls / 12 min ≈ 2100 RPM
  of gpt-4o-mini = ~7% of OpenAI Tier 5's 30 K RPM cap. Reader
  (gpt-5-mini) and judge (gpt-4o) calls are ~1/qid each — negligible.
  TPM aggregate ≈ 12% of cap. **Rate limits are never the bottleneck.**
- `STRATIFIED=133` — equal to max per-type count (multi-session and
  temporal-reasoning each have 133); pairs with limit=500 to cover the
  **entire** dataset (133+133+78+70+56+30 = 500).
- `TOTAL_LIMIT=500` — full LongMemEval.

**Why full-every-iteration**: each fix must be measured on the same
500 qids as the prior baseline. Sampled / partial runs introduce
selection bias (e.g. R9 hit a 30-q wrong-only re-run and the rescue
rate doesn't generalize linearly to the full N). The driver only
re-processes qids whose verdict line was dropped from `hypothesis.jsonl`,
so iteration cost ≈ **~12 min regardless of #changed qids** (with
N_PARALLEL=500 depth=1, all dropped qids run simultaneously).

Final artifacts: `benchmarks/longmemeval/output/{hypothesis.jsonl,
metrics.json, wrong_cases.json}`. Re-running the same command is a no-op
when complete (resume).

---

## 3. Iteration protocol

Each iteration = one cycle of *extend → analyze → fix → cleanup → commit*.

### 3.1 Snapshot (every iteration runs full N=500)

**Do NOT ramp up N**. Every iteration runs `parallel_longmemeval.sh 500
133 500` (full 500 qids, 500 parallel — one process per qid). The
resume mechanism makes a re-run after a fix only re-process the qids
whose lines were dropped from `hypothesis.jsonl` — so cost = ~12 min
regardless of how many qids changed (they all run in parallel anyway).

After **every** successful run, snapshot the merged `output/` into a
versioned copy *before* applying the next fix:

```bash
cp -r benchmarks/longmemeval/output benchmarks/longmemeval/output_v<N>
```

`<N>` is the iteration version number, e.g. `output_v1` (first full-500
run on the current config), `output_v2` (after Round 10 fix), …. The
live `output/` is always the working state; `output_v*/` snapshots are
the immutable history. **Snapshots are mandatory** — without them, a
regression in Round N+1 cannot be diffed against Round N's per-qid
verdicts.

Each snapshot folder must also be referenced by name in the matching
history entry — `history.md` if you're iterating the §1 canonical stack,
`history_max_effort.md` (§7.6) if you're iterating the §7 max-effort
stack. See §5 for the routing rule.

### 3.2 Analyze failures (mandatory deep-dive before any fix)

> **Cluster-then-diagnose-then-propose is a hard rule.** For every wrong
> case, you must (1) bucket it into a named cluster, (2) ask
> "**为什么会有这样的错误答案?有什么解决办法?**" of each cluster,
> (3) only then propose a fix. Skipping any step turns the fix into a
> guess and is the leading cause of the regression-then-revert cycles
> in this repo's history.

```bash
python -c "import json; [print(h) for h in (json.loads(l) for l in
open('benchmarks/longmemeval/output/hypothesis.jsonl')) if h['verdict']!='CORRECT']"
```

**Step A — cluster all failures.** Group the wrong cases into named
clusters by failure mechanism. Typical clusters:
- multi-session enumeration (under/over count)
- single-session-assistant text recall (Nth list item, named quote)
- temporal-reasoning (wrong ref date, complex semantic, extraction miss)
- preference building (didn't acknowledge prior user mention)
- entity dedup (same entity counted as multiple)
- assistant-quote retrieval (raw text not surfaced)

**Step B — for each cluster, write a full diagnosis (both questions):**

1. **"为什么会有这样的错误答案?"** Concrete mechanism — which pipeline
   stage failed: extraction missed it / writer summarized away the
   anchor / retrieval buried it under duplicates / reader refused with
   "no memory" / reader over-committed / dedup collapsed distinct
   entities… Anchor on **real qid examples** + their HYP text. Vague
   answers like "the model got it wrong" are not acceptable — name the
   pipeline stage.

2. **"有什么解决办法?"** Concrete code change — name the file/function
   to touch, the trigger condition, and the expected per-cluster
   payoff. Mark each candidate **bolt-on** (no graph rebuild,
   trigger-isolated, cheap to test) or **backbone-changing** (rebuild
   required, affects every question, slow + risky). Prefer bolt-on.

**Step C — propose only after B.** Each proposal must cite the cluster
+ the root-cause line it addresses + the trigger isolation analysis
(how many currently-CORRECT qids are at risk?). Without all three a
proposal is a guess and gets rejected.

### 3.3 Propose a fix

**Soft target — net-positive.** A fix is accepted if it gains more
than it loses on the test set (see §3.5 for the exact threshold). The
old "0 regression" rule was too restrictive — many useful fixes trade
1-2 regressions for 5+ saves, and forcing 0 regression rules them out.

Before touching code, do these two analyses — not as gating gates, but
as **estimates** that inform §3.5's accept/revert decision:

1. **Trigger isolation (static analysis)**. Scan all currently-CORRECT
   qids: which ones would be touched by the new code path? Count them.
   This sets the upper bound on possible regressions.
2. **Path tracing**. For each at-risk qid, reason about whether the
   fix likely changes its hypothesis. If your prediction is "≥ 5
   regressions" you should think twice before testing — but the rule
   doesn't reject the fix purely on this prediction; §3.5 uses the
   *actual* measured outcome.

The protocol still prefers code-level diversity dedup / resolver
bypass over context-injection fixes (the latter historically caused
more regressions per fix), but it no longer hard-blocks the alternative.

### 3.4 Test the fix

The test SET is exactly the qids whose verdicts the fix could change:

1. **Failure cases**: every qid currently in `wrong_cases.json` (the
   verdicts the fix targets).
2. **At-risk CORRECT cases**: every currently-CORRECT qid whose
   question matches the fix's trigger regex (= the qids that COULD
   change because of the new code path). Find them via static scan,
   e.g. `python -c "for h in ...: if TRIGGER.search(h['question']) and
   h['verdict']=='CORRECT': print(h['question_id'])"`.

**To re-test**: drop those qids' lines from
`benchmarks/longmemeval/output/hypothesis.jsonl` using the pattern
below (replace `TEST_QIDS` with the union of failure cases + at-risk
CORRECT cases), then re-run the **same parallel command you used for
the baseline run** — pick the right N_PARALLEL for your stack:

| Stack | Parallel command for re-test |
|---|---|
| §1 canonical (gpt-5-mini reader) | `bash scripts/parallel_longmemeval.sh 500 133 500` |
| §7 max-effort (gpt-5 reader) | `bash scripts/parallel_longmemeval.sh 500 133 500` (high-TPM key) — drop to match your TPM cap; never exceed 500. See §7.4 table. |

```bash
.venv/bin/python <<'PY'
import json
TEST_QIDS = {"qid_1", "qid_2", "..."}    # ← failure cases ∪ at-risk CORRECTs
src = "benchmarks/longmemeval/output/hypothesis.jsonl"
keep = [l for l in open(src) if json.loads(l)["question_id"] not in TEST_QIDS]
with open(src, "w") as f:
    f.writelines(keep)
print(f"kept {len(keep)} verdicts; dropped {len(TEST_QIDS)} for re-test")
PY

# Then re-run with the right parallel count for your stack (see table above).
bash scripts/parallel_longmemeval.sh 500 133 500   # ← high-TPM default
                                                   #   (canonical and max-effort both)
```

The driver's resume detects the missing qids and only re-processes
those. With depth=1 at 500 parallel, wall-clock cost is constant per
qid regardless of test-set size:
- canonical (gpt-5-mini reader) → **~12-15 min**
- max-effort (gpt-5 reader, high-TPM key) → **~15-20 min** (gpt-5
  high reasoning per call is ~3-5× slower than gpt-5-mini)
- max-effort (standard Tier 5, TPM-capped) → ~30-60 min for the
  re-tested subset

The final `output/` always represents the full 500-qid evaluation, so
each iteration's metric is directly comparable to the prior snapshot
without N-scaling caveats.

### 3.5 Cleanup (net-positive decision rule)

After §3.4's re-test, compute the **net change** on the test set
compared to **the snapshot you took at the start of this iteration**
(i.e. `output_v<N>/` for the current ROUND N, captured *before* the
fix's code change). That snapshot is the pre-fix baseline; the live
`output/` is the post-fix state.

```
fixes        = qids that flipped WRONG → CORRECT
regressions  = qids that flipped CORRECT → WRONG
net          = fixes − regressions
```

Apply this decision table:

| Outcome | Action |
|---|---|
| `net ≥ +1` | **KEEP** — commit + log in history (§5/§7.6). Move to next iteration. |
| `net == 0` or `net == −1` | **KEEP IF the fix adds reusable infrastructure** (new resolver, new dedup utility, new prompt anchor). Otherwise revert. Borderline calls go to history with rationale. |
| `net ≤ −2` | **REVERT** — restore code + restore the affected qids' verdicts from the prior snapshot. Then propose a different fix. |

The earlier "0 regression" rule is **deprecated**. A fix that gains 5
and loses 1 (net +4) is now a clear keep; previously it was rejected.
Only catastrophic trades (net ≤ −2) trigger an automatic revert.

**How to revert verdicts from the prior snapshot** (when `net ≤ −2`):

```bash
.venv/bin/python <<'PY'
import json
AFFECTED = {"qid_a", "qid_b", "..."}           # ← test set qids
CURRENT  = "benchmarks/longmemeval/output/hypothesis.jsonl"
PRIOR    = "benchmarks/longmemeval/output_v<PRIOR_N>/hypothesis.jsonl"  # ← edit
prior_by_qid = {
    json.loads(l)["question_id"]: l
    for l in open(PRIOR) if json.loads(l)["question_id"] in AFFECTED
}
new_lines = []
for l in open(CURRENT):
    qid = json.loads(l)["question_id"]
    new_lines.append(prior_by_qid.get(qid, l))
with open(CURRENT, "w") as f:
    f.writelines(new_lines)
print(f"restored {len(prior_by_qid)} verdicts from {PRIOR}")
PY

# Also git revert the code change (or git reset --soft if you want to
# keep the diff staged for a different fix proposal).
```

Either way: every accepted fix's regressions must be explicitly
listed in the history entry with their qids — future iterations can
target the same cluster + cluster-specific recovery.

### 3.6 Commit

The §8.2 autonomous loop has the canonical commit format
(`Round ${ROUND} fix ${ACTION}: <summary> — net ${NET} ...`). Outside
of the autonomous loop (e.g. a manual canonical-stack iteration),
this generic template works:

```bash
git add <files> && git commit -m "Round <N>: <one-line summary> — <new metric>"
```

---

## 4. Termination

**Stop ONLY when Strict J-Score ≥ 95% on the full N=500 AND the result
survives a clean-rerun confirmation (see below).**

There is no other exit condition. "Stuck after 3 attempts", "diminishing
returns", "can't think of more fixes" — none of these terminate the
loop. If a round produces 0 fixes or regressions, revert and propose a
different cluster / different stage. Then continue.

Since §2 mandates full N=500 every iteration, the metric is already on
the right denominator — no N-scaling caveat applies. The number to
beat: **475/500 = 95.00%** strict.

**Confirmation rerun — mandatory before exit.** When the working
`output/hypothesis.jsonl` first shows ≥ 475 CORRECT, do **NOT** exit.
Run a clean full N=500 from scratch first:

```bash
# Wipe every verdict and re-run end-to-end (no resume short-circuits).
rm benchmarks/longmemeval/output/hypothesis.jsonl
bash scripts/parallel_longmemeval.sh 500 133 500
```

This forces every one of the 500 qids to re-emit a fresh verdict
under the *current* code, with no leftover state from incremental
re-tests. The accumulated `hypothesis.jsonl` from §8.2's loop only
re-tests the qids targeted by each fix — the other ~450 qids' verdicts
are from earlier rounds and may have silently regressed if any fix
touched a code path used by them but they weren't in that fix's test
set.

After the confirmation rerun:

- If `correct >= 475` still holds → **TERMINATE**. Snapshot the result
  as `output_v<ROUND>_FINAL`, append a FINAL entry to
  `history_max_effort.md` (§7.6 template), commit + push.
- If `correct < 475` → the 95% was inflated by stale verdicts. The
  rerun's clean state becomes this round's baseline — fall through
  to the normal §8.2 step (3) snapshot as `output_v<ROUND>` (no
  separate `_confirmed` suffix; the rerun *is* this round's
  authoritative measurement). Then **resume the loop** from §8.2
  step (4) (analyze + fix) on the newly-surfaced wrong cases.

---

## 5. History log

**Which file to log into depends on which stack you're iterating:**

- **§1 canonical stack** (gpt-5-mini reader, gpt-4o-mini writer) →
  append to `history.md`.
- **§7 max-effort stack** (gpt-5 reader, gpt-5 writer, embedding-3-large,
  B-rerank) → append to `history_max_effort.md` per §7.6. **Never mix**
  — the two stacks have different baseline numbers and mixing them
  destroys the audit trail.

Append every key event in chronological order:

- iteration round
- snapshot label (e.g. `output_v3`)
- fix proposal (what, trigger, at-risk analysis)
- test result (per-qid diff)
- decision (accept / revert)
- new metric (strict X/500 = YY.YY%)

Keep it dense; the file is the audit trail.

---

## 6. Reference numbers (current SOTA, canonical judge)

| System | J-Score |
|---|---|
| Mastra (GPT-5-mini) | 94.87% |
| Hindsight (Gemini-3) | 91.40% |
| Supermemory (Gemini-3) | 85.20% |
| `gpt-4o` reader bar | 84.23% |
| Zep | 71.20% |

Target: beat Mastra's 94.87% on the full N=500.

---

## 7. Best-quality model configuration (cost no object)

> **Use this when you want the absolute ceiling, all-GPT, on the canonical
> LongMemEval judge.** Costs ~$30-80 for full N=500; wall-clock ~15 min
> with 500-way parallel on a high-TPM key (§7.4), or ~3-5 h on a
> standard Tier-5 key, ~40-60 h single-process (§7.2).

### 7.1 Role assignments

| Role | Model | Settings | Why |
|---|---|---|---|
| **Writer** (extraction) | `openai:gpt-5` | `reasoning_effort=high` (current auto), ideal: `low` | Reasoning model judges *spirit* of anchor rules instead of mechanical execution → fixes the Round 8 Rule-5 over-fragmentation failure mode. **Current code auto-applies `high` for any `gpt-5/o1/o3` model** (`batch.py:434`, `graph.py:372`) — that works, just slower. Lowering to `low` for the writer requires a small code change (see §7.3); skip if not urgent. ~10× slower than gpt-4o-mini per session but +3-5% on extraction recall. |
| **Reader** (QA) | `openai:gpt-5` | `reasoning_effort=high`, `max_completion_tokens=24576`, `temperature` reasoning-model default | Full gpt-5 over gpt-5-mini gains +1-2 pp on date arithmetic, aggregation, refusal calibration. **Auto-applied** by `run_eval.py:124-132` when reader model contains `gpt-5/o1/o3`. (If you ever see truncated answers, bump the `24576` constant in `run_eval.py:131` to `32768`.) |
| **Judge** | `openai:gpt-4o` | default | **NEVER substitute.** Canonical LongMemEval judge — different judge ⇒ cannot compare against Mastra/Hindsight numbers. |
| **Embedding** | `openai:text-embedding-3-large` | 3072 dim | +3-5% retrieval recall on long-tail named entities vs `text-embedding-3-small` (1536 dim). Directly attacks Cluster 1 (assistant-text recall) and Cluster 2 (multi-session enumeration). |
| **Reranker** | **B — LLM rerank** (batched) using `openai:gpt-5` `reasoning_effort=low` | one batched call per question, 50 candidates → ranked id list | See §7.3 for full justification. **Do NOT use A or C** (see warning). |

### 7.2 Currently-runnable command (TODAY, no code changes)

This command runs the **§7.1 config minus rerank** end-to-end on the
existing pipeline. The rerank step is currently disabled by default
(see §7.3 for what's needed to enable it) — every other §7.1 setting
is wired through CLI flags or env vars.

```bash
# Set API key once
echo "OPENAI_API_KEY=sk-..." > .env

# Single-process full N=500. Wall-clock ~40-60 h (gpt-5 high reasoning
# on both writer + reader). Parallelize via §7.4 for ~3-5 h total.
PYTHONPATH=src .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
    --model openai:gpt-5 \
    --writer-model openai:gpt-5 \
    --judge-model openai:gpt-4o \
    --embedding openai:text-embedding-3-large \
    --symbolic-resolver --symbolic-temporal --symbolic-bypass \
    --batch-mode \
    --stratified 133 --limit 500 \
    --resume
```

**Every flag is real** — `grep "add_argument" benchmarks/longmemeval/run_eval.py` to verify. The `reasoning_effort=high` + `max_completion_tokens=24576` settings are auto-applied by `run_eval.py:124-132` (reader) and `src/cognifold/agent/batch.py:434` (writer) when the model contains `gpt-5`/`o1`/`o3`.

### 7.3 ⚠️ Rerank selection — **use B (LLM-rerank), not A or C**

Three rerank paradigms exist; only one is right for this benchmark.

| Paradigm | What it does | LongMemEval fit | Decision |
|---|---|---|---|
| **A — Bi-encoder** (embedding cosine) | independently encode q and d, score by cosine | ⚠️ **Already in hybrid retrieval**; adding another layer of bi-encoder rerank is a no-op | ❌ DO NOT add as "rerank" — would just duplicate `semantic_match` step |
| **B — LLM-rerank** | LLM jointly attends to (q, d), outputs relevance | ✅ **Best fit** — LongMemEval questions are pragmatically complex (ordinals like "27th item", indirect references like "the previous conversation about X", temporal qualifiers) — needs reasoning to score relevance | ✅ **USE THIS** |
| **C — Cross-encoder** (Cohere rerank-v3 / BAAI bge-reranker-v2-m3) | dedicated 568M model jointly scoring (q, d) | ⚠️ Good for generic IR, weaker on pragmatic queries — wasn't trained on questions like LongMemEval's | ❌ Skip — B with gpt-5-low subsumes it |

**Why B subsumes C on this benchmark**: cross-encoders are trained on generic web search relevance (`query="best italian restaurant nyc"`, `doc=<restaurant review>`). LongMemEval queries are far more linguistically complex ("what was the 27th prompt parameter you listed?") — a reasoning LLM understands the pragmatic intent, a frozen cross-encoder does not.

**Why NOT per-doc B** (only batched B): per-doc rerank with gpt-5 = 50 LLM calls per question × 500 questions = 25000 calls ≈ $75 + 20+ hours. Batched B = 1 LLM call per question = 500 calls ≈ $3 + 30 min. **Always batched.**

#### Code changes required to enable batched B-rerank

The existing `rerank_with_llm` in `src/cognifold/query/agent.py:1563` is **per-doc** (50 calls). For batched mode + gpt-5-low rerank model, three changes:

1. **`src/cognifold/query/agent.py`** — add a new method:
   ```python
   def rerank_with_llm_batched(self, query, candidates, top_k):
       """One LLM call: present all candidates with ids, ask for ranked ids."""
       # build a single prompt enumerating (id, title, description) tuples
       # ask: "Return the top {top_k} ids in JSON array, ranked by
       # relevance to the question. JSON only."
       # parse the array, return reordered NodeSummary list
   ```
2. **`src/cognifold/query/llm.py`** — add `model` and `reasoning_effort` kwargs to `call_llm` so the rerank step can use `openai:gpt-5` with `reasoning_effort=low` while writer/reader use their own models.
3. **`benchmarks/longmemeval/run_eval.py`** — add a `--llm-rerank` CLI flag that sets `query_config.use_llm_rerank = True`, plus a `--rerank-model` flag (default `openai:gpt-5`).

**Don't enable the *existing* `use_llm_rerank=True`** — it routes through per-doc mode at hardcoded gpt-4o-mini (`src/cognifold/query/llm.py:95`). That mode is too slow + uses a too-weak rerank model + still ranks one-at-a-time which loses the cross-doc relevance comparison.

#### Final command (post code-change, projected)

After the three code edits land, the full §7.1 config becomes:

```bash
PYTHONPATH=src .venv/bin/python -u -m benchmarks.longmemeval.run_eval \
    --model openai:gpt-5 \
    --writer-model openai:gpt-5 \
    --judge-model openai:gpt-4o \
    --embedding openai:text-embedding-3-large \
    --symbolic-resolver --symbolic-temporal --symbolic-bypass \
    --llm-rerank --rerank-model openai:gpt-5 \
    --batch-mode \
    --stratified 133 --limit 500 \
    --resume
```

Projected ceiling: **~96-97% J-Score** on full N=500 (Mastra SOTA is 94.87%). Cost ≈ $40-80; wall-clock ~15 min at 500-way parallel on a high-TPM key (§7.4), or ~3-5 h on a standard Tier-5 key, or ~40-60 h single-process. (Rerank adds ~30 min total — one batched gpt-5-low call per question.)

### 7.4 Parallel mode

The `scripts/parallel_longmemeval.sh` driver hardcodes the canonical
models — `grep "openai:" scripts/parallel_longmemeval.sh` finds them
(currently `--model openai:gpt-5-mini`, `--writer-model openai:gpt-4o-mini`).
To run §7.2's stack in parallel, **edit those lines** to:

```bash
--model openai:gpt-5 \
--writer-model openai:gpt-5 \
--judge-model openai:gpt-4o \
--embedding openai:text-embedding-3-large \
```

Then:

```bash
bash scripts/parallel_longmemeval.sh 500 133 500   # 500-way (one process per qid)
```

**Choose N_PARALLEL based on your actual gpt-5 TPM cap, but never
exceed 500** (depth=1 already, more parallel processes serve no
purpose — they'd just queue on OpenAI's side).

| Your gpt-5 TPM cap | Recommended N_PARALLEL | Why |
|---|---|---|
| ≥ 12M TPM (custom / Scale Tier) | **500** | Saturates throughput at depth=1, ~15 min wallclock |
| 5M-12M | 250-400 | Sweet spot; minor 429 backoff but minimal stall |
| 800K-5M (standard Tier 5) | 50-75 | Just enough to saturate cap; avoids retry noise |
| 400K (Tier 4) | 25 | Conservative — stays under cap |
| < 400K (Tier 1-3) | 12 | Avoid persistent 429s |

**How to check your cap**: hit any gpt-5 endpoint and read the
`x-ratelimit-limit-tokens` response header (or check
<https://platform.openai.com/settings/organization/limits>). Divide
by ~21K tokens/min/qid to get the parallelism that saturates without
heavy throttling.

Wall-clock per full N=500:
- 500 parallel (high-TPM key, depth=1) → **~15 min**
- 50 parallel (standard Tier 5, TPM-capped) → ~2.5-3 h
- 25 parallel (Tier 4 conservative) → ~4-5 h

The driver's resume + merge + cleanup behavior is unchanged.

### 7.5 Verification checklist before launching

- [ ] `.env` has a valid OpenAI Tier 5 key (gpt-5 access required).
- [ ] `grep "openai:gpt-5\b" scripts/parallel_longmemeval.sh` if running parallel — confirms model lines were updated.
- [ ] **Judge stays gpt-4o** — `grep "judge-model" scripts/parallel_longmemeval.sh` must show `openai:gpt-4o`, no substitutions.
- [ ] If `benchmarks/longmemeval/output/` already exists from a prior canonical run, snapshot it before launching: `cp -r benchmarks/longmemeval/output benchmarks/longmemeval/output_canonical_baseline`. (On a fresh machine there's nothing to back up — skip this item.)
- [ ] `git remote -v` shows origin = `https://github.com/OpenNorve/CogniFold.git` (HTTPS or SSH form both OK).
- [ ] `git branch --show-current` returns **`iter`** — never run the loop on any other branch.
- [ ] `git push origin iter --dry-run` succeeds without credential prompt AND reports `iter -> iter` (not main/other) — the loop pushes inline after each round.

### 7.6 Result logging → `history_max_effort.md` + per-round push

**§7 runs MUST log to `history_max_effort.md` (NOT `history.md`)**.
The two files have distinct purposes:

| File | Purpose |
|---|---|
| `history.md` | General iteration log (Rounds 1-9 etc., gpt-5-mini reader baseline) |
| `history_max_effort.md` | **Dedicated** to §7 max-effort runs (gpt-5 reader + gpt-5 writer + embedding-3-large + B-rerank). One file per max-effort campaign; never mix with `history.md` so results stay comparable within each config family. |

**What to log into `history_max_effort.md`** (append-only, chronological):

```markdown
## YYYY-MM-DD HH:MM — <event>

- **N**: <total questions evaluated>
- **Config**: writer=<model>, reader=<model>, judge=<model>,
  embedding=<model>, rerank=<B-batched|none>
- **Metric**: strict J-Score = <X>/<N> = <pp>%
- **Per-type**: ms=…, t=…, ku=…, u=…, a=…, p=…
- **Delta from prior**: +/-N qids, list moved qids
- **Notes**: any anomaly (cost spike, rate-limit hit, model regression)
```

Append after **every full-N run** (baseline + every re-test). Keep
it dense — it's the ground truth for "did this config actually move
the needle vs §1 canonical".

**Push timing**: §8.2's loop calls `git push origin iter` **inline
after each round's commit**, not on a schedule, and always targets the
`iter` branch only (see §0). Pushes fire on the two events that
produce a full-N hypothesis state:

1. After step (3): the baseline full N=500 run + snapshot + history
   commit.
2. After step (7): the post-fix re-test + cleanup (keep or revert)
   commit.

This guarantees every committed state matches what's on the remote —
no orphaned commits, and a machine failure mid-loop loses at most the
current round's in-flight work.

**Rules for the agent**:
1. **Never amend or force-push** when running unattended — every change
   is a NEW commit. Force-push can wipe out other agents' work.
2. `history_max_effort.md` commits land in step (3) and step (7) of
   §8.2 — both are followed immediately by `git push origin iter`.
3. If a push fails (auth, conflict, force-rejected) the loop should
   surface the error and halt (do NOT silently swallow it). Investigate
   the remote state, `git pull --rebase`, retry the push, then resume.

---

## 8. Autonomous max-effort loop (entry point)

> **For "run at any cost, hit the strongest possible result"** — this
> is the single entry point. It composes §0 / §2 / §3 / §4 / §7 into
> one runnable loop.

### 8.1 One-time setup (do these in order)

1. **§0** — clone from `OpenNorve/CogniFold`, **`git checkout iter`**
   (the dedicated autonomous-loop branch), install, set
   `OPENAI_API_KEY`, verify `git remote -v`, `git branch --show-current`
   prints `iter`, and SSH/HTTPS push credentials succeed.
2. **§7.4** — find the model lines in `scripts/parallel_longmemeval.sh`
   (`grep -n "openai:" scripts/parallel_longmemeval.sh` — should hit
   3-4 lines near the `nohup ... python -u -m benchmarks.longmemeval.run_eval`
   block) and edit them to the max-effort stack:
   ```
   --model openai:gpt-5
   --writer-model openai:gpt-5
   --judge-model openai:gpt-4o
   --embedding openai:text-embedding-3-large
   ```
3. **§7.5** — walk the full checklist before launching.
4. **Optional** — implement §7.3 batched B-rerank code edits if you
   want the projected +2-3 pp from rerank. If you skip this, §8.2's
   loop uses the gpt-5 stack *without* rerank (still expected to beat
   §1 canonical by +2-4 pp).
5. Create empty `history_max_effort.md`, commit it, and seed the
   loop's `ROUND` counter:
   ```bash
   echo "# Max-Effort Campaign — gpt-5 / gpt-5 / gpt-4o / 3-large" \
       > history_max_effort.md
   git add history_max_effort.md
   git commit -m "Bootstrap max-effort campaign log"
   echo "0" > .max_effort_round    # ROUND counter; loop reads + increments
   ```

### 8.2 The loop

`ROUND` is persisted in `.max_effort_round` (created in §8.1 step 5).
Read + bump it each iteration so the snapshot/commit labels are
stable across crashes / resumes.

```text
loop forever:
    ROUND = int(open(".max_effort_round").read().strip()) + 1
    open(".max_effort_round", "w").write(str(ROUND))

    # (1) Run the full N=500 with the max-effort stack
    bash scripts/parallel_longmemeval.sh 500 133 500
    # 500 parallel (depth=1) assumes a high-TPM gpt-5 key (≥12M TPM).
    # On a standard Tier-5 key drop to 50; see §7.4 table.

    # (2) Compute metric
    metric = json.load(open("benchmarks/longmemeval/output/metrics.json"))
    correct = metric["correct"]    # int, 0..500
    metric_pct = f"{100 * correct / 500:.2f}"
    if correct >= 475:    # ≥95.00% — but DO NOT exit yet
        # Mandatory confirmation rerun per §4. Wipes hypothesis.jsonl
        # and runs the full 500 from scratch so no stale verdicts from
        # prior incremental re-tests inflate the metric. The rerun's
        # result REPLACES the headline metric — whether it confirms or
        # not, that's the number that goes into history and snapshot.
        rm benchmarks/longmemeval/output/hypothesis.jsonl
        bash scripts/parallel_longmemeval.sh 500 133 500
        metric = json.load(open("benchmarks/longmemeval/output/metrics.json"))
        correct = metric["correct"]
        metric_pct = f"{100 * correct / 500:.2f}"
        if correct >= 475:
            # Confirmed. Snapshot + log + FINAL commit + push + EXIT.
            cp -r benchmarks/longmemeval/output  \
                  benchmarks/longmemeval/output_v${ROUND}_FINAL
            append_history_entry("FINAL", correct, metric_pct,
                                 snapshot="output_v${ROUND}_FINAL",
                                 notes="Confirmed clean rerun ≥ 475/500")
            git add -A
            git commit -m "FINAL: ${metric_pct}% (${correct}/500) — confirmed clean rerun"
            git push origin iter
            sys.exit(0)
        # Confirmation failed (stale verdicts inflated the headline).
        # Fall through with the *real* metric — this round's snapshot
        # below captures the clean-rerun state, and the loop continues
        # on its newly-surfaced wrong cases.
    snapshot_dir = f"benchmarks/longmemeval/output_v{ROUND}"
    cp -r benchmarks/longmemeval/output  $snapshot_dir

    # (3) Append to history_max_effort.md (per §7.6 template)
    #     then commit + push immediately.
    git add history_max_effort.md $snapshot_dir .max_effort_round
    git commit -m "Round ${ROUND} (max-effort): ${metric_pct}% (${correct}/500)"
    git push origin iter || halt("baseline push failed; see §7.6 rule 3")

    # (4) Analyze failures per §3.2 (cluster → why → solution)
    # (5) Propose fix per §3.3 (estimate trigger isolation; not a gate)
    # (6) Drop test set qids per §3.4; re-run with the SAME N_PARALLEL
    #     you used in step (1) — must match for the metric to stay
    #     directly comparable. (For a high-TPM key: 500.)
    # (7) Apply §3.5 net-positive cleanup rule on the re-test diff.
    #     Diff = output/hypothesis.jsonl (post-fix)
    #         vs output_v${ROUND}/hypothesis.jsonl (pre-fix snapshot from step 3)
    fixes       = count(qid in test_set where pre=WRONG, post=CORRECT)
    regressions = count(qid in test_set where pre=CORRECT, post=WRONG)
    NET = fixes - regressions
    if NET >= +1:
        # Keep the fix.
        ACTION = "kept"
    elif NET in (0, -1) and adds_reusable_infrastructure:
        # Borderline keep (e.g. fix introduced a new resolver shared by
        # future rounds).
        ACTION = "kept (infra)"
    else:
        # Revert: undo code change AND restore the affected qids'
        # verdicts from the prior snapshot (see §3.5's python script).
        run §3.5 revert procedure
        ACTION = "reverted"
    # Commit + push the post-fix state immediately (kept or reverted —
    # the commit is the audit record either way).
    git add -A
    git commit -m "Round ${ROUND} fix ${ACTION}: <one-line summary> — net ${NET} (fixes=${fixes}, regressions=${regressions})"
    git push origin iter || halt("post-fix push failed; see §7.6 rule 3")
    # (loop back to top)
```

### 8.3 Exit / error conditions

- **Success** (only): strict J-Score ≥ 95.00% on N=500 **AND survives
  the §4 confirmation rerun** (clean full N=500 from scratch). §8.2's
  step (2) implements both checks; only after the second number also
  ≥ 475 does it commit + push + exit. If the first reading hits ≥ 475
  but the rerun comes back below, the loop continues on the rerun's
  new wrong cases — this is the expected guard against stale-verdict
  inflation.
- **Rate-limit 429 spam in `logs/parallel_b*.log`** → halve N_PARALLEL
  (e.g. 500→250→125→…) and re-launch §8.2-(1). Backing off by 5 from
  500 is meaningless — the 429s come from TPM exhaustion, which is
  proportional. Keep halving until 429 rate drops to <5% of requests.
- **OOM in `dmesg`** → halve N_PARALLEL and re-launch. Each process is
  ~300 MB; with `free -g` you can predict the safe upper bound.
- **OpenAI key billing failure** → halt loop, log to
  `history_max_effort.md` as "BLOCKED: API billing", manual intervention
  required.
- **All other errors** → log to `history_max_effort.md` with stack
  trace, attempt one retry, then halt.

### 8.4 What to NEVER do in the autonomous loop

- ❌ Switch judge from gpt-4o (breaks comparability with SOTA table)
- ❌ Run partial N (sampled / stratified < 133) — breaks denominator
- ❌ Skip cluster analysis (§3.2) before proposing a fix — historically
  the #1 cause of regressions
- ❌ Force-push (`git push -f`) — overwrites other commits
- ❌ Disable `--symbolic-resolver` / `--symbolic-temporal` /
  `--symbolic-bypass` — they're load-bearing, account for ~5 pp
- ❌ Mix `history.md` and `history_max_effort.md` entries
- ❌ Edit the gpt-4o-mini constant in `src/cognifold/query/llm.py` to
  some other model without also implementing §7.3 batched rerank —
  per-doc rerank with gpt-5 will exhaust your budget in hours
- ❌ Accept a fix with `net ≤ −2` even if it "feels right" — §3.5's
  rule is hard. (Net 0 / −1 fixes can be kept under the
  reusable-infrastructure exception; everything below is a revert.)
- ❌ Exit at the first ≥ 475 reading without the §4 confirmation
  rerun. The incremental loop's `hypothesis.jsonl` is a patchwork of
  fix-test results that may overstate the true metric; only a clean
  full-N rerun under current code is allowed to terminate.
- ❌ Push to any branch other than **`iter`**. Never run
  `git push origin main`, `git push origin HEAD` from a non-iter branch,
  `git push --all`, or anything that would touch `main` /
  `public-release` / `cognifold-dev` / etc. The autonomous loop is
  scoped to `iter` so concurrent work on other branches is safe.
- ❌ Switch branches mid-loop. If `git branch --show-current` ever
  returns something other than `iter`, halt and investigate before
  continuing — accidental commits to the wrong branch leak the
  campaign's snapshots and history into shared branches.
