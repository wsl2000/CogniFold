---
name: longmemeval-iterate
description: Autonomous LongMemEval benchmark iteration toward ≥95% strict J-Score on full N=500. Use when the user asks to run, iterate, improve, or continue the LongMemEval campaign on branch `longmemeval-iter`. Loops baseline → cluster-analyze → propose fix → re-test → net-positive decision → commit → repeat. Terminates only when a clean-rerun confirmation also clears ≥475/500. SKIP for other benchmarks (LoCoMo, MuSiQue, NarrativeQA, etc.) — those have their own runners.
---

# LongMemEval Autonomous Iteration

## When to use

- User says "iterate LongMemEval" / "run the longmemeval loop" / "continue R10"
- After a fresh clone, before any iteration: walk §0 setup
- Any time the autonomous loop is mid-cycle and needs to resume

## Hard rules (never violate)

1. **Branch lock**: only commit/push on `longmemeval-iter`. Verify
   `git branch --show-current` returns `longmemeval-iter` before any
   `git commit`. Never touch `main` / `iter` / `public-release` / etc.
2. **Judge lock**: `--judge-model openai:gpt-4o` always. Substituting
   breaks comparability with Mastra / Hindsight numbers.
3. **Symbolic stack on**: `--symbolic-resolver --symbolic-temporal
   --symbolic-bypass` must all stay enabled (~5 pp on the score).
4. **Full N=500 each round**: no stratified < 133, no sampled subsets.
   Resume makes incremental cost ≈ wall-clock of one batch anyway.
5. **Cluster-then-diagnose-then-propose**: every fix must follow the
   protocol in `references/iteration-rules.md`. Skipping this step is
   the #1 historical cause of regressions.

## Setup (one-time per fresh machine)

Run `scripts/check_setup.sh` — it verifies branch, push credentials,
remote, model config in `scripts/parallel_longmemeval.sh`, and that
`history_max_effort.md` + `.max_effort_round` exist (creates them if
not). Halt and surface any failures.

## The loop

```text
loop forever:
    ROUND = read+bump .max_effort_round

    # (1) Baseline: full N=500 run
    bash scripts/parallel_longmemeval.sh <N_PARALLEL> 133 500
    # N_PARALLEL from references/model-config.md Tier table

    # (2) Measure
    metrics = json.load("benchmarks/longmemeval/output/metrics.json")
    correct = metrics["correct"]

    # (3) Terminate if ≥475 AND confirmation rerun also ≥475
    if correct >= 475:
        run confirmation rerun (rm hypothesis.jsonl, re-run full N)
        if confirmed correct2 >= 475:
            commit FINAL + push + EXIT
        # else fall through with corrected (lower) baseline

    # (4) Snapshot pre-fix state
    cp -r output/ output_v${ROUND}/
    append baseline metric to history_max_effort.md
    git add + commit + git push origin longmemeval-iter

    # (5) Analyze failures per references/iteration-rules.md §A-B-C
    # (6) Propose fix (estimate trigger isolation; not a gate)
    # (7) Drop test_set qids, re-run with SAME N_PARALLEL (see scripts/drop_qids.py)
    # (8) Compute net = fixes - regressions vs output_v${ROUND}/
    # (9) Apply references/iteration-rules.md decision table:
    #     net ≥ +1                   → keep
    #     net ∈ {0, -1} + reusable   → keep (infra)
    #     net ≤ -2                   → revert (restore verdicts + git revert)
    # (10) Commit + push the post-fix state
    # Loop back to (1)
```

## Details (load on demand)

- `references/model-config.md` — model stack (writer/reader/judge/embed/rerank),
  Tier → N_PARALLEL table, why each pick
- `references/iteration-rules.md` — cluster analysis Step A-B-C, soft
  net-positive decision table, revert procedure
- `references/termination.md` — confirmation rerun mechanics, exit
  conditions, error handling (429 spam, OOM, billing failure)

## Error handling

- **429 spam in `logs/parallel_b*.log`** → halve N_PARALLEL, relaunch
- **OOM in `dmesg`** → halve N_PARALLEL, relaunch
- **Billing failure** → halt loop, log "BLOCKED: API billing" to
  `history_max_effort.md`, await human intervention
- **Push fail** → halt immediately, do NOT silently swallow. Inspect
  remote, `git pull --rebase`, retry, resume

## What to NEVER do

- ❌ Switch judge from gpt-4o
- ❌ Run partial N (stratified < 133)
- ❌ Skip cluster analysis before proposing a fix
- ❌ Force-push (`git push -f`)
- ❌ Disable any of `--symbolic-resolver` / `--symbolic-temporal` / `--symbolic-bypass`
- ❌ Mix `history.md` (canonical-stack log) with `history_max_effort.md`
- ❌ Accept a fix with `net ≤ -2` (even if it "feels right")
- ❌ Exit at first ≥475 without the confirmation rerun
- ❌ Push to any branch other than `longmemeval-iter`
- ❌ Switch branches mid-loop
