#!/usr/bin/env python3
"""Compute net = fixes - regressions on the re-test set, compared to
the pre-fix snapshot. Used after §3.4 re-test to drive §3.5 decision.

Usage:
    .venv/bin/python .claude/skills/longmemeval-iterate/scripts/compute_net.py \\
        <prior_snapshot_dir> [<test_qid> <test_qid> ...]

  prior_snapshot_dir: e.g. benchmarks/longmemeval/output_v7
  test_qids        : optional; if omitted, diff over ALL qids

Prints:
  fixes=N  regressions=M  net=K
  fixed_qids = [...]
  regressed_qids = [...]
"""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit("Usage: compute_net.py <prior_snapshot_dir> [test_qid ...]")

prior_dir = Path(sys.argv[1])
test_qids = set(sys.argv[2:]) if len(sys.argv) > 2 else None

prior_hyp = prior_dir / "hypothesis.jsonl"
curr_hyp  = Path("benchmarks/longmemeval/output/hypothesis.jsonl")
for p in (prior_hyp, curr_hyp):
    if not p.exists():
        sys.exit(f"Not found: {p}")

def load_verdicts(path: Path) -> dict[str, str]:
    return {json.loads(l)["question_id"]: json.loads(l)["verdict"] for l in path.open()}

prior = load_verdicts(prior_hyp)
curr  = load_verdicts(curr_hyp)

fixed = []
regressed = []
for qid, pre in prior.items():
    if test_qids and qid not in test_qids:
        continue
    post = curr.get(qid)
    if post is None:
        continue
    if pre != "CORRECT" and post == "CORRECT":
        fixed.append(qid)
    elif pre == "CORRECT" and post != "CORRECT":
        regressed.append(qid)

net = len(fixed) - len(regressed)
print(f"fixes={len(fixed)}  regressions={len(regressed)}  net={net:+d}")
print(f"fixed_qids = {sorted(fixed)}")
print(f"regressed_qids = {sorted(regressed)}")

# §3.5 decision hint
if net >= 1:
    print("DECISION: KEEP (net-positive)")
elif net in (0, -1):
    print("DECISION: KEEP IF reusable-infra; else REVERT (borderline)")
else:
    print("DECISION: REVERT (net ≤ -2)")
