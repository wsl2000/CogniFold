# Iteration Rules (cluster analysis → propose → test → decide)

## Step A — Cluster all failures

Group wrong cases into named clusters by failure mechanism. Typical clusters:

- **multi-session enumeration** (under/over count)
- **single-session-assistant text recall** (Nth list item, named quote)
- **temporal-reasoning** (wrong ref date, complex semantic, extraction miss)
- **preference building** (didn't acknowledge prior user mention)
- **entity dedup** (same entity counted as multiple)
- **assistant-quote retrieval** (raw text not surfaced)

## Step B — Diagnose each cluster (mandatory)

For **every** cluster, write down both:

1. **"为什么会有这样的错误答案?"** — name the pipeline stage that failed
   (extraction missed it / writer summarized away / retrieval buried it /
   reader refused / reader over-committed / dedup collapsed). Anchor on
   real qid examples + their HYP text. "The model got it wrong" is not
   acceptable.

2. **"有什么解决办法?"** — concrete code change: file/function to
   touch, trigger condition, expected payoff. Mark each candidate as
   **bolt-on** (no graph rebuild, trigger-isolated, cheap) or
   **backbone-changing** (rebuild needed, affects every question, slow
   + risky). Prefer bolt-on.

## Step C — Propose (only after B)

Each proposal must cite the cluster + the root-cause line it addresses
+ the trigger isolation analysis (how many currently-CORRECT qids are
at risk?). Without all three the proposal is a guess and gets rejected.

**Trigger isolation (static analysis)**:
- Scan all currently-CORRECT qids; count which would be touched by the
  new code path. This sets the upper bound on possible regressions.
- For each at-risk qid, reason about whether the fix likely changes
  its hypothesis. If prediction is "≥5 regressions" think twice — but
  it's an estimate, not a gate (§3.5 uses actual measured outcome).

## Net-positive decision table (Step §3.5)

Compute on the re-test set against the snapshot `output_v<ROUND>/`
(captured pre-fix in step 3):

```
fixes       = qids that flipped WRONG → CORRECT
regressions = qids that flipped CORRECT → WRONG
net         = fixes − regressions
```

| Outcome | Action |
|---|---|
| `net ≥ +1` | **KEEP** — commit + log + push |
| `net == 0` or `net == −1` | **KEEP IF reusable infrastructure** (new resolver, new dedup utility, new prompt anchor). Otherwise revert. Borderline calls go to history with rationale. |
| `net ≤ −2` | **REVERT** — restore code + restore qids' verdicts from prior snapshot |

The earlier "0 regression" rule is **deprecated**. A fix that gains 5
and loses 1 (net +4) is a clear keep. Only catastrophic trades
(net ≤ −2) trigger an automatic revert.

## Revert procedure (when net ≤ −2)

Restore the affected qids' verdicts from the prior snapshot, then
git-revert the code change. See `scripts/revert_verdicts.py`.

Either way: every accepted fix's regressions must be explicitly listed
in the history entry with their qids — future iterations can target
the same cluster + cluster-specific recovery.
