#!/usr/bin/env python3
"""MS run health check + cost monitor.

Runs as a long-lived watcher:
- Watches batch output dirs for new hypothesis.jsonl entries
- Aggregates: done count, accuracy (CORRECT + 0.5*PARTIAL), cost from call_stats
- Logs HC every 10 newly-merged results
- Kills workers when estimated cost exceeds COST_CAP

Cost estimation (gpt-5.4-mini commonstack rough):
- input:  $0.30 per 1M tokens
- output: $1.20 per 1M tokens (incl reasoning_tokens)
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path

LABEL = sys.argv[1] if len(sys.argv) > 1 else "iter32_ms_v1"
COST_CAP = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
HC_INTERVAL = int(sys.argv[3]) if len(sys.argv) > 3 else 10

BASE = Path("benchmarks/longmemeval")
FINAL_DIR = BASE / "runs" / LABEL
BATCH_GLOB = "output_i32ms_b*"
BATCH_DIRS_FILE = FINAL_DIR / "batch_dirs.txt"
LOG_FILES_FILE = FINAL_DIR / "log_files.txt"
PIDS_FILE = FINAL_DIR / "workers.pids"
HC_LOG = FINAL_DIR / "hc.log"

PRICE_IN = 0.30 / 1_000_000
PRICE_OUT = 1.20 / 1_000_000


def load_path_list(path: Path) -> list[Path]:
    if not path.exists():
        return []
    items: list[Path] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if s:
            items.append(Path(s))
    return items


def batch_dirs() -> list[Path]:
    scoped = load_path_list(BATCH_DIRS_FILE)
    if scoped:
        return scoped
    return sorted(BASE.glob(BATCH_GLOB))


def log_files() -> list[Path]:
    scoped = load_path_list(LOG_FILES_FILE)
    if scoped:
        return scoped
    return sorted(Path("logs").glob("iter32ms_b*.log"))


def load_records() -> dict[str, dict]:
    records: dict[str, dict] = {}
    final_hyp = FINAL_DIR / "hypothesis.jsonl"
    if final_hyp.exists():
        for line in open(final_hyp):
            try:
                r = json.loads(line); records[r["question_id"]] = r
            except Exception:
                pass
    for batch in batch_dirs():
        hp = batch / "hypothesis.jsonl"
        if not hp.exists():
            continue
        for line in open(hp):
            try:
                r = json.loads(line); records[r["question_id"]] = r
            except Exception:
                pass
    return records


def write_merged_records(records: dict[str, dict]) -> None:
    if not records:
        return
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    final_hyp = FINAL_DIR / "hypothesis.jsonl"
    with open(final_hyp, "w") as f:
        for qid in sorted(records):
            f.write(json.dumps(records[qid]) + "\n")


def aggregate_cost() -> tuple[int, int, int, float]:
    """Sum tokens + cost across batch call_stats.json (if present) +
    fallback to log POST-line estimation since run_eval.py only dumps
    call_stats at batch end (we'd see $0 mid-run otherwise)."""
    total_in = total_out = total_calls = 0
    total_cost = 0.0
    have_stats = False
    for batch in batch_dirs():
        cs = batch / "call_stats.json"
        if not cs.exists():
            continue
        try:
            data = json.loads(cs.read_text())
            have_stats = True
        except Exception:
            continue
        for _model, b in data.items():
            in_tok = int(b.get("input_tokens", 0))
            out_tok = int(b.get("output_tokens", 0)) + int(b.get("reasoning_tokens", 0))
            calls = int(b.get("calls", 0))
            reported_cost = float(b.get("cost_usd", 0.0))
            total_in += in_tok
            total_out += out_tok
            total_calls += calls
            if reported_cost > 0:
                total_cost += reported_cost
            else:
                total_cost += in_tok * PRICE_IN + out_tok * PRICE_OUT
    # Fallback: count POST lines in active logs; estimate from average call cost
    if not have_stats:
        import subprocess
        for log in log_files():
            try:
                r = subprocess.run(
                    ["grep", "-c", "POST https://api.commonstack.ai", str(log)],
                    capture_output=True, text=True, timeout=5,
                )
                n = int(r.stdout.strip() or 0)
                total_calls += n
            except Exception:
                pass
        # Per-call avg estimate. iter31 mix:
        # - ~95% writer/rerank calls (medium/low effort): ~5k in, 5k out (with reasoning)
        # - ~5% reader calls (HIGH effort default): ~15k in, 25k out (heavy reasoning)
        # Blended weighted average:
        AVG_IN_PER_CALL = 5500   # mostly writer at 5k + small reader hit
        AVG_OUT_PER_CALL = 6000  # writer 5k reasoning + reader's 25k weighted 5% = 6.5k
        total_in = total_calls * AVG_IN_PER_CALL
        total_out = total_calls * AVG_OUT_PER_CALL
        total_cost = total_calls * (
            AVG_IN_PER_CALL * PRICE_IN + AVG_OUT_PER_CALL * PRICE_OUT
        )
    return total_calls, total_in, total_out, total_cost


def log_hc(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    HC_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(HC_LOG, "a") as f:
        f.write(line + "\n")


def kill_workers() -> None:
    if not PIDS_FILE.exists():
        log_hc("WARN: workers.pids not found, cannot kill")
        return
    pids = PIDS_FILE.read_text().split()
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
            log_hc(f"KILLED pid={pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            log_hc(f"failed to kill {pid}: {e}")


def workers_alive() -> bool:
    if not PIDS_FILE.exists():
        return False
    for pid in PIDS_FILE.read_text().split():
        try:
            os.kill(int(pid), 0)
            return True
        except (ProcessLookupError, ValueError):
            continue
    return False


def count_429_errors() -> int:
    """Count 429 / rate-limit error lines in worker logs."""
    n = 0
    import subprocess
    for log in log_files():
        try:
            r = subprocess.run(
                ["grep", "-cE", "429|rate.limit|RateLimit|TooManyRequests", str(log)],
                capture_output=True, text=True, timeout=5,
            )
            n += int(r.stdout.strip() or 0)
        except Exception:
            pass
    return n


def detect_anomalies(
    done: int, nonempty: int, strict: float, c: Counter, proj_cost: float, n_429: int
) -> list[str]:
    """Return list of human-readable anomaly reasons; empty if all OK.

    Auto-halt triggers (per user: 'unusual → halt + wait for decision'):
    - strict accuracy below iter27 baseline (77.4%) by >5pp = catastrophic
      regression (at done>=10)
    - empty hypothesis ratio > 15% at done >= 10 (commonstack failures)
    - 429 storm > 50 errors
    - projected cost > cost_cap*0.95 (auto-cap is COST_CAP, but warn early)
    """
    anomalies: list[str] = []
    if done >= 10:
        empty_rate = (done - nonempty) / done if done else 0
        # Floor: iter27 baseline was 77.4%; 72% is a soft floor.
        # At done=10, accept some noise; at done=20+ tighten.
        if done >= 20 and strict < 65.0:
            anomalies.append(
                f"strict={strict:.1f}% below soft floor 65% at done={done} "
                f"(iter27 baseline 77.4%; regression > 12pp)"
            )
        elif done >= 10 and strict < 55.0:
            anomalies.append(
                f"strict={strict:.1f}% below hard floor 55% at done={done} "
                f"(suspected catastrophic regression)"
            )
        if empty_rate > 0.15:
            anomalies.append(
                f"empty_hy_rate={empty_rate:.0%} > 15% at done={done} "
                f"(commonstack failures)"
            )
    if n_429 > 50:
        anomalies.append(f"429 storm: {n_429} rate-limit errors in logs")
    if proj_cost > COST_CAP * 0.95:
        anomalies.append(
            f"projected cost ${proj_cost:.0f} > 95% of cap ${COST_CAP:.0f}"
        )
    return anomalies


def main() -> None:
    log_hc(
        f"== iter32 MS HC monitor START label={LABEL} cap=${COST_CAP:.0f} "
        f"interval={HC_INTERVAL} auto-halt on anomaly ==")
    last_done = 0
    last_hc_done = 0
    halted = False
    while True:
        time.sleep(30)
        records = load_records()
        done = len(records)
        if done > 0 and (done != last_done or not (FINAL_DIR / "hypothesis.jsonl").exists()):
            write_merged_records(records)
        if done == 0 and not workers_alive():
            log_hc("no records and workers gone — exiting")
            break
        c = Counter(r.get("verdict") for r in records.values())
        nonempty = sum(1 for r in records.values() if (r.get("hypothesis") or "").strip())
        strict = c["CORRECT"] / nonempty * 100 if nonempty else 0.0
        partial = (c["CORRECT"] + 0.5 * c["PARTIAL"]) / nonempty * 100 if nonempty else 0.0
        calls, in_tok, out_tok, cost = aggregate_cost()
        proj_cost = cost / done * 133 if done > 0 else 0.0
        n_429 = count_429_errors()
        log_hc(
            f"done={done}/133 | strict={strict:.1f}% partial={partial:.1f}% | "
            f"C={c['CORRECT']} P={c['PARTIAL']} I={c['INCORRECT']} "
            f"EmptyHY={done-nonempty} | "
            f"calls={calls} in={in_tok//1000}k out={out_tok//1000}k | "
            f"cost=${cost:.2f} (proj=${proj_cost:.2f}) | 429={n_429}"
        )
        # HC checkpoint every HC_INTERVAL new results
        if done - last_hc_done >= HC_INTERVAL:
            log_hc(f"  >>> HC #{done // HC_INTERVAL} at done={done}")
            # Anomaly check ONLY at HC checkpoints (not every 30s)
            anomalies = detect_anomalies(done, nonempty, strict, c, proj_cost, n_429)
            if anomalies:
                log_hc(f"  !!! ANOMALY DETECTED at done={done}:")
                for a in anomalies:
                    log_hc(f"      - {a}")
                log_hc("  !!! AUTO-HALT — killing workers; user decides resume/fix")
                kill_workers()
                halted = True
                log_hc("  !!! HALTED — monitor exits after 30s grace")
                time.sleep(30)
                break
            last_hc_done = done - (done % HC_INTERVAL)
        # Hard cost cap (separate from anomaly)
        if cost >= COST_CAP:
            log_hc(f"!!! COST CAP HIT cost=${cost:.2f} >= ${COST_CAP:.0f} — killing workers")
            kill_workers()
            log_hc("HALTED on cost cap")
            time.sleep(30)
            break
        # Done
        if done >= 133:
            log_hc("FINISHED done=133")
            break
        if done > last_done and not workers_alive():
            log_hc(f"workers exited at done={done} — assumed complete")
            break
        last_done = done

    if halted:
        log_hc("== HALTED. Waiting for user decision (resume vs fix vs abandon) ==")


if __name__ == "__main__":
    main()
