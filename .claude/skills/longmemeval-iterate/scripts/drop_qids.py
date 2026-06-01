#!/usr/bin/env python3
"""Drop the listed qids' lines from output/hypothesis.jsonl so the
parallel driver re-processes them. Used by both:
- §3.4 re-test (drop failure set ∪ at-risk CORRECT set)
- §4 confirmation rerun (drop ALL — but for that just `rm` the file)

Usage:
    .venv/bin/python .claude/skills/longmemeval-iterate/scripts/drop_qids.py \\
        qid_a qid_b qid_c ...
"""
import json
import sys
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit("Usage: drop_qids.py <qid> [<qid> ...]")

drop = set(sys.argv[1:])
hyp = Path("benchmarks/longmemeval/output/hypothesis.jsonl")
if not hyp.exists():
    sys.exit(f"Not found: {hyp}")

kept = []
dropped = []
for line in hyp.open():
    qid = json.loads(line)["question_id"]
    (dropped if qid in drop else kept).append(line)

hyp.write_text("".join(kept))
print(f"kept {len(kept)} verdicts; dropped {len(dropped)} for re-test")
missed = drop - {json.loads(d)['question_id'] for d in dropped}
if missed:
    print(f"WARNING: requested qids not found in hypothesis.jsonl: {sorted(missed)}",
          file=sys.stderr)
