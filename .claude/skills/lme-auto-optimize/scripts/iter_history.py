#!/usr/bin/env python3
"""Per-iter score + change timeline for LongMemEval iter runs.

Walks `benchmarks/longmemeval/runs/iter*` and prints, in chronological
iter-number order:
- iter number + label folder
- strict + partial score
- per-type breakdown if present
- one-line summary from CHANGES.md (or first heading)
- regressions called out in CHANGES.md (lines starting with -, ⚠, regression)

Why this exists: a new iter often re-introduces a regression a past
iter already noted (e.g. iter27 added W1+W2 → MS −4.6; iter30 added W3
→ MS −29). Without a per-iter timeline view, that history gets lost
between sessions.

Usage:
    python iter_history.py                            # all iters
    python iter_history.py --type temporal-reasoning  # filter type
    python iter_history.py --since iter25             # only iter25+
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


_ITER_RE = re.compile(r"^iter(\d+)([a-z]?)_(.+)$")


def parse_iter_dir(d: Path) -> tuple[int, str, str] | None:
    m = _ITER_RE.match(d.name)
    if not m:
        return None
    return int(m.group(1)), m.group(2), m.group(3)


def read_metrics(run_dir: Path) -> dict:
    """Return aggregated metrics, computing per-type from hypothesis.jsonl if needed."""
    metrics: dict = {}
    metrics_json = run_dir / "metrics.json"
    if metrics_json.exists():
        try:
            metrics = json.load(open(metrics_json))
        except Exception:
            pass

    # Per-type strict accuracy from hyp + dataset
    hyp = run_dir / "hypothesis.jsonl"
    data_path = Path("benchmarks/longmemeval/data/longmemeval_s_cleaned.json")
    if hyp.exists() and data_path.exists():
        try:
            qtype = {q["question_id"]: q.get("question_type", "?")
                     for q in json.load(open(data_path))}
            per_type = defaultdict(lambda: [0, 0])  # [correct, total]
            for line in open(hyp):
                r = json.loads(line)
                t = qtype.get(r["question_id"], "?")
                per_type[t][1] += 1
                if r.get("verdict") == "CORRECT":
                    per_type[t][0] += 1
            metrics["per_type"] = {
                t: {"correct": c, "total": n, "pct": (c * 100 / n) if n else 0}
                for t, (c, n) in per_type.items()
            }
        except Exception:
            pass

    return metrics


def read_changes_summary(run_dir: Path) -> tuple[str, list[str]]:
    """Return (one-line summary, regression bullets) from CHANGES.md."""
    ch = run_dir / "CHANGES.md"
    if not ch.exists():
        return "(no CHANGES.md)", []
    lines = ch.read_text().split("\n")
    summary = ""
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#"):
            summary = s[:160]
            break
        if s.startswith("##") or s.startswith("# "):
            summary = s.lstrip("#").strip()[:160]
    regressions = [
        ln.strip() for ln in lines
        if re.search(r"regress|−\d|\-\d.+pp|⚠|broke|hurt|cost MS|cost TR", ln, re.I)
    ]
    return summary, regressions[:5]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", default="benchmarks/longmemeval/runs")
    p.add_argument("--since", default=None, help="only show iters >= this iter number (e.g. iter25)")
    p.add_argument("--type", default=None, help="filter per-type accuracy to one type")
    args = p.parse_args()

    runs = Path(args.runs_dir)
    if not runs.exists():
        print(f"no runs dir at {runs}")
        return

    iters: list[tuple[int, str, str, Path]] = []
    for d in runs.iterdir():
        if not d.is_dir():
            continue
        parsed = parse_iter_dir(d)
        if parsed:
            iters.append((*parsed, d))

    iters.sort(key=lambda x: (x[0], x[1]))

    since_n = 0
    if args.since:
        m = re.match(r"iter(\d+)", args.since)
        if m:
            since_n = int(m.group(1))

    print(f"{'iter':>6s}  {'overall':>8s}  {'type breakdown' if not args.type else args.type[:24]}  summary")
    print("-" * 100)

    for iter_n, suffix, label, d in iters:
        del label  # noqa: F841  (kept in tuple for ordering, unused below)
        if iter_n < since_n:
            continue
        m = read_metrics(d)
        strict = m.get("score_strict")
        if strict is None and m.get("correct") and m.get("total"):
            strict = m["correct"] / m["total"] * 100
        strict_s = f"{strict:>5.1f}%" if isinstance(strict, (int, float)) else "  ?  "

        per_t = m.get("per_type", {})
        if args.type:
            t = per_t.get(args.type, {})
            tbreak = (
                f"{t.get('correct', '?')}/{t.get('total', '?')} = {t.get('pct', 0):.1f}%"
                if t else "(no data)"
            )
        else:
            parts = []
            for t in ("knowledge-update", "multi-session", "temporal-reasoning",
                      "single-session-assistant", "single-session-preference",
                      "single-session-user"):
                v = per_t.get(t)
                if v:
                    short = t.split("-")[0].upper()[:2] if "-" in t else t.upper()[:2]
                    parts.append(f"{short}:{v['pct']:.0f}%")
            tbreak = " ".join(parts)

        summary, regressions = read_changes_summary(d)
        print(f"iter{iter_n:02d}{suffix}  {strict_s}  {tbreak:<48s}  {summary[:60]}")
        for r in regressions:
            if r.strip():
                print(f"        ⚠  {r[:90]}")


if __name__ == "__main__":
    main()
