# Termination & Exit Conditions

## The ONE exit condition

Strict J-Score **≥ 475 / 500 = 95.00%** on the full N=500, AND survives
a clean-rerun confirmation. No other condition terminates the loop.
"Stuck after N attempts", "diminishing returns", "can't think of more
fixes" — none of these exit. Revert, propose a different cluster,
continue.

## Confirmation rerun — mandatory before exit

When the working `output/hypothesis.jsonl` first shows ≥ 475 CORRECT,
do **NOT** exit. Run a clean full N=500 from scratch first:

```bash
rm benchmarks/longmemeval/output/hypothesis.jsonl
bash scripts/parallel_longmemeval.sh <N_PARALLEL> 133 500
```

This forces every one of the 500 qids to re-emit a fresh verdict
under the *current* code, with no leftover state from incremental
re-tests. The accumulated `hypothesis.jsonl` from §8.2's loop only
re-tests the qids targeted by each fix — the other ~450 qids' verdicts
are from earlier rounds and may have silently regressed if any fix
touched a code path used by them but they weren't in that fix's test
set.

**After the confirmation rerun**:

- `correct ≥ 475` still holds → **TERMINATE**. Snapshot as
  `output_v<ROUND>_FINAL/`, append FINAL entry to `history_max_effort.md`,
  commit, `git push origin longmemeval-iter`, exit.
- `correct < 475` → the 95% was inflated by stale verdicts. The rerun's
  clean state becomes this round's baseline — fall through to normal
  §8.2 step (3) snapshot as `output_v<ROUND>/`. Then resume the loop
  from step (4) on the newly-surfaced wrong cases.

## Push timing (inline per-round)

`git push origin longmemeval-iter` fires twice per round:

1. After step (3): baseline full N=500 run + snapshot + history commit
2. After step (10): post-fix re-test + cleanup commit

Both with `--force-with-lease` only if needed (regular push by default).

If push fails (auth / conflict / force-rejected) **halt immediately** —
do NOT silently swallow. Inspect remote state, `git pull --rebase`,
retry the push, then resume.

## Error handling

| Error | Action |
|---|---|
| Rate-limit 429 spam in `logs/parallel_b*.log` | Halve N_PARALLEL (e.g. 500 → 250 → 125), relaunch §8.2-(1). 429s come from TPM exhaustion, proportional — backing off by 5 from 500 is meaningless. Keep halving until 429 rate drops to <5%. |
| OOM in `dmesg` | Halve N_PARALLEL. Each process ~300 MB; `free -g` predicts safe upper bound. |
| OpenAI key billing failure | Halt loop, log "BLOCKED: API billing" to `history_max_effort.md`, await human intervention. |
| All other errors | Log to `history_max_effort.md` with stack trace, attempt one retry, then halt. |

## Final exit checklist

When ≥475 confirmed:

- [ ] `output_v<ROUND>_FINAL/` snapshot exists
- [ ] `history_max_effort.md` has FINAL entry with config + per-type scores
- [ ] `git log -1` shows "FINAL: ..." commit message
- [ ] `git push origin longmemeval-iter` succeeded
- [ ] Loop terminated via `sys.exit(0)` — not via crash or interrupt
