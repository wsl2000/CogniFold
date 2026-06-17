#!/usr/bin/env python3
"""Spurious-fire sweep for the unified LongMemEval evidence ledger.

Loads the SINGLE merged ledger (round2_evidence_ledger.py) and, for every
``emit_*`` function, extracts its first question-gate regex
(``_NAME.search(question)`` / ``_NAME.match(question)``) and runs that gate
over all 500 LongMemEval questions.

Asserts the best-of-breed merge invariant:
  * exactly 42 emitters are present,
  * every emitter fires on >= 1 question (no DEAD gates),
  * no emitter fires across more than one question category (no XCAT bleed).

Prints a clean summary line ``XCAT=0 dead=0`` on success and exits non-zero
on any violation.

Usage:
    PYTHONPATH=/home/ydeng/Code/CogniFold/src python3 scripts/ledger_spurious_sweep.py
"""

from __future__ import annotations

import collections
import importlib.util
import inspect
import json
import os
import re
import sys

# cognifold (ConceptGraph / NodeType / NodeSummary) lives in the main checkout.
_COGNIFOLD_SRC = os.environ.get(
    "COGNIFOLD_SRC", "/home/ydeng/Code/CogniFold/src"
)
if _COGNIFOLD_SRC not in sys.path:
    sys.path.insert(0, _COGNIFOLD_SRC)

_HERE = os.path.dirname(os.path.abspath(__file__))
_LEDGER_PATH = os.path.join(
    _HERE, "..", "benchmarks", "longmemeval", "round2_evidence_ledger.py"
)
_DATASET_PATH = os.environ.get(
    "LME_DATASET",
    "/home/ydeng/Code/CogniFold/benchmarks/longmemeval/data/longmemeval_s_cleaned.json",
)

_EXPECTED_EMITTERS = 42

_SHORT = {
    "single-session-user": "SSU",
    "single-session-assistant": "SSA",
    "single-session-preference": "SSP",
    "multi-session": "MS",
    "knowledge-update": "KU",
    "temporal-reasoning": "TR",
}

# First question-gate regex inside an emitter body.
_GATE_RE = re.compile(r"(_[A-Za-z0-9_]+)\.(?:search|match)\(\s*question\s*\)")


def _load_ledger():
    spec = importlib.util.spec_from_file_location("merged_ledger", _LEDGER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _emitters(module) -> dict:
    return {
        name: fn
        for name, fn in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("emit_") and fn.__module__ == module.__name__
    }


def _gate_for(fn, module):
    """Return the (name, compiled_pattern) of the emitter's FIRST question gate."""
    src = inspect.getsource(fn)
    match = _GATE_RE.search(src)
    if not match:
        return None
    name = match.group(1)
    return name, getattr(module, name, None)


def main() -> int:
    module = _load_ledger()
    with open(_DATASET_PATH) as fh:
        dataset = json.load(fh)
    questions = [
        (entry["question_id"], _SHORT[entry["question_type"]], entry["question"])
        for entry in dataset
    ]

    emitters = _emitters(module)
    n_emitters = len(emitters)

    dead: list[str] = []
    xcat: list[tuple[str, dict]] = []
    no_gate: list[str] = []
    rows: list[tuple[str, int, dict]] = []

    for name, fn in sorted(emitters.items()):
        gate = _gate_for(fn, module)
        if gate is None or gate[1] is None:
            no_gate.append(name)
            rows.append((name, 0, {}))
            continue
        _gate_name, pattern = gate
        fired = [
            cat for qid, cat, q in questions if pattern.search(q)
        ]
        cats = collections.Counter(fired)
        rows.append((name, len(fired), dict(cats)))
        if len(fired) == 0:
            dead.append(name)
        elif len(cats) > 1:
            xcat.append((name, dict(cats)))

    for name, n_fire, cats in rows:
        cat_str = ",".join(f"{c}:{n}" for c, n in cats.items()) or "-"
        flag = ""
        if name in no_gate:
            flag = "[NO GATE]"
        elif n_fire == 0:
            flag = "[DEAD]"
        elif len(cats) > 1:
            flag = f"[XCAT {cats}]"
        print(f"  {name:46s} fires={n_fire:2d} [{cat_str:10s}] {flag}")

    print()
    print(f"emitters={n_emitters} (expected {_EXPECTED_EMITTERS})")
    print(f"XCAT={len(xcat)} dead={len(dead)} no_gate={len(no_gate)}")

    ok = (
        n_emitters == _EXPECTED_EMITTERS
        and not xcat
        and not dead
        and not no_gate
    )
    if not ok:
        print("FAIL: merge invariant violated")
        for name, cats in xcat:
            print("  XCAT:", name, cats)
        for name in dead:
            print("  DEAD:", name)
        for name in no_gate:
            print("  NO GATE:", name)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
