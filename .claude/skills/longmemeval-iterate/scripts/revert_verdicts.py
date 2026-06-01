#!/usr/bin/env python3
"""Restore the affected qids' verdicts from the prior snapshot.
Used when §3.5 decision = REVERT (net ≤ -2). Run BEFORE git-reverting
the code change so hypothesis.jsonl returns to the pre-fix state.

Usage:
    .venv/bin/python .claude/skills/longmemeval-iterate/scripts/revert_verdicts.py \\
        <prior_snapshot_dir> <qid_a> <qid_b> ...
"""
import json
import sys
from pathlib import Path

if len(sys.argv) < 3:
    sys.exit("Usage: revert_verdicts.py <prior_snapshot_dir> <qid> [qid ...]")

prior_dir = Path(sys.argv[1])
affected = set(sys.argv[2:])

prior_hyp = prior_dir / "hypothesis.jsonl"
curr_hyp  = Path("benchmarks/longmemeval/output/hypothesis.jsonl")
for p in (prior_hyp, curr_hyp):
    if not p.exists():
        sys.exit(f"Not found: {p}")

prior_by_qid = {
    json.loads(l)["question_id"]: l
    for l in prior_hyp.open()
    if json.loads(l)["question_id"] in affected
}

new_lines = []
restored = 0
for line in curr_hyp.open():
    qid = json.loads(line)["question_id"]
    if qid in prior_by_qid:
        new_lines.append(prior_by_qid[qid])
        restored += 1
    else:
        new_lines.append(line)

curr_hyp.write_text("".join(new_lines))
print(f"restored {restored} verdicts from {prior_hyp}")

missing = affected - set(prior_by_qid)
if missing:
    print(f"WARNING: requested qids not in snapshot: {sorted(missing)}",
          file=sys.stderr)

print("Now: git revert / git reset --soft the code change to complete the revert.")
