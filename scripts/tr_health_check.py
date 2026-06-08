#!/usr/bin/env python3
"""TR-only health check: compare running accuracy vs iter31 r1 baseline.

Auto-kill criteria (any → STOP):
1. Empty hypothesis rate > 20% (provider down)
2. Accuracy on common qids below iter31 r1 - 5pp
3. Graph nodes median < 300 (writer broken)
4. ERROR verdict > 5%

Usage:
    python scripts/tr_health_check.py --run-dir runs/iter32_tr_v4 \
        --batch-glob "benchmarks/longmemeval/output_i32_b*"
"""
import argparse, json, statistics, sys
from collections import Counter
from pathlib import Path


def load(paths):
    out = {}
    for p in paths:
        if not p.exists(): continue
        for line in open(p):
            try:
                r = json.loads(line); out[r["question_id"]] = r
            except: pass
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--batch-glob", default=None)
    p.add_argument("--baseline", default="benchmarks/longmemeval/runs/iter31_tr_round1")
    p.add_argument("--data", default="benchmarks/longmemeval/data/longmemeval_s_cleaned.json")
    p.add_argument("--regression-pp", type=float, default=5.0,
                   help="if running acc drops > N pp below iter31 r1 baseline → STOP")
    p.add_argument("--empty-threshold", type=float, default=0.20)
    p.add_argument("--graph-min", type=int, default=300)
    p.add_argument("--error-threshold", type=float, default=0.05)
    args = p.parse_args()

    paths = [Path(args.run_dir) / "hypothesis.jsonl"]
    if args.batch_glob:
        paths.extend(sorted(Path(".").glob(args.batch_glob + "/hypothesis.jsonl")))
    records = load(paths)
    if not records:
        print("no records yet")
        return 0

    # Filter to TR-only
    data = json.load(open(args.data))
    qtype = {q["question_id"]: q.get("question_type") for q in data}
    records = {q: r for q, r in records.items()
               if qtype.get(q) == "temporal-reasoning"}
    if not records:
        print("no TR records yet")
        return 0
    total = len(records)

    empty = [q for q, r in records.items()
             if len(str(r.get("hypothesis","") or "").strip()) < 5]
    verdicts = Counter(r.get("verdict") for r in records.values())
    correct = verdicts["CORRECT"]
    errors = verdicts.get("ERROR", 0)
    acc = correct / total * 100
    empty_rate = len(empty) / total

    gn = [r.get("graph_node_count") or r.get("graph_nodes") or 0
          for r in records.values()]
    gn_med = int(statistics.median(gn)) if gn else 0

    # Baseline comparison on common qids
    baseline = load([Path(args.baseline) / "hypothesis.jsonl"])
    common = set(records) & set(baseline)
    base_acc = None
    floor = None
    if common:
        # Exclude empty-HY records from accuracy floor check (provider-induced, not reasoning regression).
        common_healthy = [q for q in common if len(str(records[q].get("hypothesis","") or "").strip()) >= 5]
        if common_healthy:
            b_c = sum(1 for q in common_healthy if baseline[q].get("verdict") == "CORRECT")
            c_c = sum(1 for q in common_healthy if records[q].get("verdict") == "CORRECT")
            base_acc = b_c / len(common_healthy) * 100
            cur_acc_on_common = c_c / len(common_healthy) * 100
            floor = base_acc - args.regression_pp
        else:
            base_acc = None

    print(f"=== TR health @ done={total} ===")
    print(f"  CORRECT  : {correct}/{total} = {acc:.1f}%")
    print(f"  EMPTY HY : {len(empty)} = {empty_rate*100:.1f}%")
    print(f"  ERROR    : {errors} = {errors/total*100:.1f}%")
    print(f"  graph_nodes median: {gn_med}")
    if base_acc is not None:
        print(f"  baseline (iter31 r1) on {len(common)} common: {base_acc:.1f}%")
        print(f"  current on common: {cur_acc_on_common:.1f}%  (floor: {floor:.1f}%)")

    stops = []
    if empty_rate > args.empty_threshold:
        stops.append(f"empty_rate {empty_rate*100:.1f}% > {args.empty_threshold*100:.0f}%")
    if errors/total > args.error_threshold:
        stops.append(f"error_rate > {args.error_threshold*100:.0f}%")
    if gn_med < args.graph_min:
        stops.append(f"graph_nodes median {gn_med} < {args.graph_min}")
    if floor is not None and cur_acc_on_common < floor:
        stops.append(f"acc_on_common {cur_acc_on_common:.1f}% < floor {floor:.1f}%")
    if stops:
        print(f"STOP — {'; '.join(stops)}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
