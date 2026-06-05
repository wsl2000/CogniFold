#!/usr/bin/env python3
"""Cluster LongMemEval wrong cases by failure pattern.

Reads a run's hypothesis.jsonl + wrong_cases.json and groups the
wrongs by:
1. question_type (KU / MS / SSA / SSP / SSU / TR)
2. failure pattern within the type, using regex + keyword heuristics
   that match the taxonomy in references/failure-taxonomy.md

Usage:
    python cluster_failures.py --base runs/iter27_gpt54mini_full_n500_W1W2
    python cluster_failures.py --base runs/iter32_tr_only --type temporal-reasoning
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def classify_tr(q: str, gt: str, hy: str) -> str:
    """Return the TR cluster letter for a wrong case."""
    ql = q.lower()
    hyl = hy.lower()

    if re.search(r"how\s+long\s+had\s+i\s+been|how\s+many\s+(?:days|weeks|months)\s+had\s+(?:i|passed)", ql):
        return "TR-A duration_since_start"
    if re.search(r"\border\s+(?:of\s+)?the\s+\w+\s+(?:i|of)", ql) or "earliest to latest" in ql:
        return "TR-B order_among"
    if re.search(r"\blast\s+(?:saturday|sunday|monday|tuesday|wednesday|thursday|friday|weekend|week)|valentine|christmas|easter|new\s+year", ql):
        return "TR-C named_day_disambig"
    if re.search(r"how\s+many\s+days\s+(?:passed|between)", ql):
        return "TR-D date_diff_offbyone"
    if re.search(r"what\s+time\s+(?:do|does)", ql) or "wake up" in ql:
        return "TR-F derived_time"
    if "abs" in (q[-10:].lower()) or re.search(r"\b_abs\b", q):
        return "TR-G _abs"
    if "first" in ql and "or" in ql:
        return "TR-G which_first"
    if "don't have" in hyl or "no record" in hyl or "can't determine" in hyl:
        return "TR-E refusal_with_data"
    return "TR-? unclassified"


def classify_ms(q: str, gt: str, hy: str) -> str:
    ql = q.lower()
    hyl = hy.lower()
    if "_abs" in q or "abs" in q[-10:].lower():
        return "MS-D _abs"
    if "don't have" in hyl or "no record" in hyl or "can't" in hyl:
        return "MS-B refusal_with_data"
    if re.search(r"how\s+many", ql) or re.search(r"how\s+much.*total", ql) or "total" in ql:
        return "MS-A undercount"
    if re.search(r"\bwhich\b.*\bmost\b", ql) or re.search(r"the\s+most\s+\w+", ql):
        return "MS-C wrong_winner"
    return "MS-? unclassified"


def classify_ku(q: str, gt: str, hy: str) -> str:
    ql = q.lower()
    if re.search(r"how\s+many\s+(?:times|sessions|days)", ql):
        return "KU-B count_undercount"
    if re.search(r"current(?:ly)?|now\b", ql):
        return "KU-A supersession"
    if "personal best" in ql or "latest" in ql or "most recent" in ql:
        return "KU-C latest_value"
    return "KU-? unclassified"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, help="path to run folder (contains hypothesis.jsonl)")
    p.add_argument("--type", default=None,
                   help="filter to one question_type: knowledge-update / multi-session / "
                        "single-session-assistant / single-session-preference / "
                        "single-session-user / temporal-reasoning")
    p.add_argument("--data", default="benchmarks/longmemeval/data/longmemeval_s_cleaned.json")
    args = p.parse_args()

    base = Path(args.base)
    hyp = base / "hypothesis.jsonl"
    if not hyp.exists():
        print(f"ERROR: {hyp} not found")
        return

    data = json.load(open(args.data))
    qtype = {q["question_id"]: q.get("question_type", "?") for q in data}

    wrongs = []
    for line in open(hyp):
        try:
            r = json.loads(line)
            if r.get("verdict") == "CORRECT":
                continue
            t = qtype.get(r["question_id"], "?")
            if args.type and t != args.type:
                continue
            wrongs.append((r, t))
        except Exception:
            pass

    print(f"# wrong cases in {base.name}: {len(wrongs)}\n")

    by_cluster: dict[str, list] = defaultdict(list)
    for r, t in wrongs:
        q = r["question"]
        gt = str(r.get("ground_truth", ""))
        hy = r.get("hypothesis", "") or ""
        if t == "temporal-reasoning":
            cluster = classify_tr(q, gt, hy)
        elif t == "multi-session":
            cluster = classify_ms(q, gt, hy)
        elif t == "knowledge-update":
            cluster = classify_ku(q, gt, hy)
        else:
            cluster = t.upper() + " — generic"
        by_cluster[cluster].append((r, t))

    print(f"## Cluster summary\n")
    for c in sorted(by_cluster, key=lambda x: -len(by_cluster[x])):
        n = len(by_cluster[c])
        print(f"  {c:<40s} {n:>3d} cases")
    print()

    print(f"## Per-case detail\n")
    for c in sorted(by_cluster, key=lambda x: -len(by_cluster[x])):
        print(f"\n=== {c} ===")
        for r, t in by_cluster[c]:
            print(f"  [{r['question_id']}] (type={t})")
            print(f"    Q : {r['question'][:140]}")
            print(f"    GT: {str(r.get('ground_truth',''))[:120]}")
            print(f"    HY: {(r.get('hypothesis','') or '')[:140]}")


if __name__ == "__main__":
    main()
