#!/usr/bin/env python3
"""Apples-to-apples score comparison between two LME runs.

Restricts the comparison to qids that BOTH runs processed, then
reports per-type strict accuracy, the regression list (baseline ✓
→ current ✗), the improvement list (baseline ✗ → current ✓), and
net Δ in percentage points.

Usage:
    python apples_compare.py \\
        --current runs/iter32_tr_only \\
        --baseline runs/iter27_gpt54mini_full_n500_W1W2
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in open(path):
        try:
            r = json.loads(line)
            out[r["question_id"]] = r
        except Exception:
            pass
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--current", required=True)
    p.add_argument("--baseline", required=True)
    p.add_argument("--data", default="benchmarks/longmemeval/data/longmemeval_s_cleaned.json")
    args = p.parse_args()

    data = json.load(open(args.data))
    qtype = {q["question_id"]: q.get("question_type", "?") for q in data}

    cur = load(Path(args.current) / "hypothesis.jsonl")
    base = load(Path(args.baseline) / "hypothesis.jsonl")
    common = set(cur) & set(base)
    print(f"current:  {len(cur)} qids   ({args.current})")
    print(f"baseline: {len(base)} qids   ({args.baseline})")
    print(f"common:   {len(common)} qids\n")
    if not common:
        return

    by_t: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "bc": 0, "cc": 0})
    regressions = []
    improvements = []
    for q in common:
        t = qtype.get(q, "?")
        bv = base[q].get("verdict")
        cv = cur[q].get("verdict")
        by_t[t]["n"] += 1
        if bv == "CORRECT":
            by_t[t]["bc"] += 1
        if cv == "CORRECT":
            by_t[t]["cc"] += 1
        if bv == "CORRECT" and cv != "CORRECT":
            regressions.append((q, t, base[q], cur[q]))
        elif bv != "CORRECT" and cv == "CORRECT":
            improvements.append((q, t, base[q], cur[q]))

    print("=== per-type strict accuracy (common qids) ===\n")
    print(f"{'type':28s} {'baseline':>10s} {'current':>10s} {'Δ':>8s}")
    total_b = sum(s["bc"] for s in by_t.values())
    total_c = sum(s["cc"] for s in by_t.values())
    total_n = sum(s["n"] for s in by_t.values())
    for t in sorted(by_t):
        n, bc, cc = by_t[t]["n"], by_t[t]["bc"], by_t[t]["cc"]
        if not n:
            continue
        br, cr = bc * 100 / n, cc * 100 / n
        print(f"  {t:26s} {bc:>3d}/{n:<3d} {br:>5.1f}%  {cc:>3d}/{n:<3d} {cr:>5.1f}%  {cr-br:+5.1f}pp")
    print()
    print(
        f"  {'overall':26s} {total_b:>3d}/{total_n:<3d} "
        f"{total_b*100/total_n:>5.1f}%  {total_c:>3d}/{total_n:<3d} "
        f"{total_c*100/total_n:>5.1f}%  "
        f"{(total_c-total_b)*100/total_n:+5.1f}pp\n"
    )
    print(f"=== regressions (baseline ✓ → current ✗) — {len(regressions)} ===")
    for q, t, b, c in regressions:
        print(f"\n[{q}] type={t}")
        print(f"  Q : {b['question'][:140]}")
        print(f"  GT: {str(b.get('ground_truth',''))[:120]}")
        print(f"  base ✓: {b['hypothesis'][:140]}")
        print(f"  curr ✗: {(c.get('hypothesis','') or '')[:140]}")
    print(f"\n=== improvements (baseline ✗ → current ✓) — {len(improvements)} ===")
    for q, t, b, c in improvements:
        print(f"\n[{q}] type={t}")
        print(f"  Q : {b['question'][:140]}")
        print(f"  GT: {str(b.get('ground_truth',''))[:120]}")
        print(f"  base ✗: {(b.get('hypothesis','') or '')[:140]}")
        print(f"  curr ✓: {c['hypothesis'][:140]}")
    print(f"\nnet: improvements − regressions = {len(improvements)-len(regressions):+d}")


if __name__ == "__main__":
    main()
