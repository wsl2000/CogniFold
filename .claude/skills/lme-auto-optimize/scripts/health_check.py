#!/usr/bin/env python3
"""Liveness + sanity check for an in-progress LongMemEval run.

Designed to be invoked every 10 newly-merged results. If any of
the danger signals fires, prints `STOP` on the last line — the
launching workflow MUST kill workers and inspect.

Danger signals (any → STOP):
1. empty hypothesis rate > 20% (provider 429/timeout cascade)
2. CORRECT rate < (baseline − 10pp) among non-empty hyps
3. graph_node_count median < 300 (writer dropping events)
4. > 5% records with `verdict == "ERROR"`

Usage:
    python health_check.py --run-dir runs/iter31_tr_round1 \\
        --batch-dirs benchmarks/longmemeval/output_i31_b* \\
        --baseline runs/iter27_gpt54mini_full_n500_W1W2 \\
        --type temporal-reasoning
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def load_records(paths: list[Path]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in paths:
        if not p.exists():
            continue
        for line in open(p):
            try:
                r = json.loads(line)
                out[r["question_id"]] = r
            except Exception:
                pass
    return out


def hyp_is_empty(r: dict) -> bool:
    return len(str(r.get("hypothesis", "") or "").strip()) < 5


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--batch-glob", default=None,
                   help="glob for in-progress batch dirs (e.g. benchmarks/longmemeval/output_i31_b*)")
    p.add_argument("--baseline", default=None,
                   help="baseline run dir for accuracy floor; if omitted, accuracy floor disabled")
    p.add_argument("--type", default=None,
                   help="filter to single question_type; reads --data for type lookup")
    p.add_argument("--data", default="benchmarks/longmemeval/data/longmemeval_s_cleaned.json")
    p.add_argument("--empty-threshold", type=float, default=0.20)
    p.add_argument("--acc-floor-pp", type=float, default=10.0)
    p.add_argument("--graph-min", type=int, default=300)
    p.add_argument("--error-threshold", type=float, default=0.05)
    args = p.parse_args()

    paths = [Path(args.run_dir) / "hypothesis.jsonl"]
    if args.batch_glob:
        paths.extend(sorted(Path(".").glob(args.batch_glob + "/hypothesis.jsonl")))
    records = load_records(paths)
    if not records:
        print("no records yet")
        return 0

    # type filter
    if args.type:
        try:
            data = json.load(open(args.data))
            qtype = {q["question_id"]: q.get("question_type") for q in data}
            records = {q: r for q, r in records.items() if qtype.get(q) == args.type}
        except Exception as e:
            print(f"WARN: type filter failed ({e}); skipping")

    total = len(records)
    if not total:
        print("no records of target type yet")
        return 0

    empty = [q for q, r in records.items() if hyp_is_empty(r)]
    non_empty = {q: r for q, r in records.items() if q not in empty}
    verdicts = Counter(r.get("verdict") for r in records.values())
    correct_total = verdicts["CORRECT"]
    errors = verdicts.get("ERROR", 0)
    correct_non_empty = sum(1 for r in non_empty.values() if r.get("verdict") == "CORRECT")
    gn = [r.get("graph_node_count") or r.get("graph_nodes") or 0 for r in records.values()]
    gn_med = int(statistics.median(gn)) if gn else 0

    empty_rate = len(empty) / total
    error_rate = errors / total
    non_empty_acc = (correct_non_empty / len(non_empty) * 100) if non_empty else 0
    total_acc = correct_total / total * 100

    # Baseline accuracy floor (apples-to-apples on common qids)
    baseline_acc = None
    baseline_floor = None
    if args.baseline:
        b = load_records([Path(args.baseline) / "hypothesis.jsonl"])
        common = set(records) & set(b)
        if common:
            b_c = sum(1 for q in common if b[q].get("verdict") == "CORRECT")
            baseline_acc = b_c / len(common) * 100
            baseline_floor = baseline_acc - args.acc_floor_pp

    # Report
    print(f"=== health check @ done={total} ===")
    print(f"  CORRECT  : {correct_total} = {total_acc:.1f}%  "
          f"(non-empty: {correct_non_empty}/{len(non_empty)} = {non_empty_acc:.1f}%)")
    print(f"  EMPTY HY : {len(empty)} = {empty_rate*100:.1f}%")
    print(f"  ERROR    : {errors} = {error_rate*100:.1f}%")
    print(f"  graph_nodes median: {gn_med}")
    if baseline_acc is not None:
        print(f"  baseline same-qids: {baseline_acc:.1f}%  (floor: {baseline_floor:.1f}%)")

    # Verdicts
    stop_reasons = []
    if empty_rate > args.empty_threshold:
        stop_reasons.append(f"empty_rate {empty_rate*100:.1f}% > {args.empty_threshold*100:.0f}%")
    if error_rate > args.error_threshold:
        stop_reasons.append(f"error_rate {error_rate*100:.1f}% > {args.error_threshold*100:.0f}%")
    if gn_med < args.graph_min:
        stop_reasons.append(f"graph_nodes median {gn_med} < {args.graph_min}")
    if baseline_floor is not None and total_acc < baseline_floor:
        stop_reasons.append(f"total_acc {total_acc:.1f}% < baseline_floor {baseline_floor:.1f}%")

    if stop_reasons:
        print(f"STOP — {'; '.join(stop_reasons)}")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
