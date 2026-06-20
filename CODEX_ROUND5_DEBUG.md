# Codex Round 5 — Smoke Failure Debug

Round 2 implemented per your CODEX_ROUND2_PLAN.md + CODEX_ROUND4_FINAL
guidance. Smoke results from the 10-qid set you specified:

```
4/10 = 40% CORRECT — BELOW the 8/10 pass threshold
mandatory passes: 1/3 (b46e15ed ✓, gpt4_f420262c ✗, gpt4_7fce9456 ✗)
```

Per-case:

| # | qid | result | sym | note |
|---|---|---|---|---|
| 1 | `b46e15ed` | ✅ "About 2 months" | — | `_choose_duration_anchor` works |
| 2 | `gpt4_d6585ce9` | ✅ "your parents" | named_day_recall | re-enabled path |
| 3 | `gpt4_f420262d` | ❌ JetBlue (GT: AA) | — | ATTRIBUTE-MISMATCH didn't fire |
| 4 | `08f4fc43` | ✅ "31 days (inclusive)" | — | judge accepted; likely variance |
| 5 | `gpt4_f420262c` | ❌ Delta→…→JetBlue (GT: JetBlue→Delta→United→AA) | — | order ledger empty |
| 6 | `a3838d2b` | ❌ 1 vs GT 4 | — | A:count didn't fire |
| 7 | `9ee3ecd6` | ❌ 300 vs GT 100 | — | A:derived_time didn't fire |
| 8 | `09ba9854_abs` | ❌ ¥16,800 hallucinate (GT: refuse) | — | SAME-SCOPE didn't fire |
| 9 | `gpt4_7fce9456` | ❌ 1 vs GT 4 | — | B:chunk_fusion didn't surface property views |
| 10 | `81507db6` | ✅ "3 graduation" | — | passing case, likely natural |

## Root cause (Claude's diagnosis)

The shipped ledger module (`benchmarks/longmemeval/round2_evidence_ledger.py`)
is **structurally incomplete**:

- `build_evidence_ledger` only initializes shape-specific SLOTS (e.g.
  `ledger["final_count"] = None`, `ledger["ordered"] = []`) but
  **never fills them**.
- `answer_from_ledger` therefore **always returns None** for every
  shape, because every slot is None/empty.
- Result: the ledger route runs `late_fusion_retrieve` to pull raw
  chunks and prepends them as a context block via
  `assemble_ledger_context`, but never actually emits a deterministic
  answer. It just enriches context.
- The 4 new qa_rules also don't fire (the reader pattern-matches
  weakly when rules are buried in a 290-line qa_answer prompt — the
  iter29/30 lesson you flagged).

The only round-2 wins came from **resolver patches**, not the ledger:
- `_choose_duration_anchor` (b46e15ed) ✓
- `named_day_recall` re-enabled with `_resolve_anchor_date` indirectly
  helping (gpt4_d6585ce9) ✓

## What you need to give us

You constrained us: "If `gpt4_7fce9456` still fails, debug late-fusion
scoring/chunk assembly first; do not add more prompt text." So we are
NOT adding rules.

We want:
1. **`build_evidence_ledger` per-shape fill logic** — for each shape
   (`count`, `order`, `duration_since`, `date_diff`, `derived_time`,
   `abs_value`), what's the smallest deterministic algorithm that
   reads `fused_context` (graph_hits + raw_hits) and fills the slot?

   Example: for `count` on `gpt4_7fce9456` ("how many properties before
   the offer"):
   - input: raw_hits is a list of `{node_id, role, text, date,
     session_index}` dicts (text is the raw EVENT.data["content"]).
   - expected: ledger["final_count"] = 4 if we can extract 4 distinct
     property-view events.

   How do we extract them deterministically without an LLM call? Per
   your prior idea: "let the model emit JSON first and reject any row
   that is not grounded in the retrieved context."
   - Concrete: should the round-2 path make an **LLM sub-call** with a
     "list each candidate with date" prompt, then post-process? If yes,
     what's the prompt, and what's the rejection rule?
   - Or: should `build_evidence_ledger` only fill the slot when the
     fused context has **explicit numeric anchors** (e.g. "viewed N
     properties" already in text), and otherwise return None?

2. **Whether the ledger should make its own LLM sub-call** — Claude
   thinks yes (extract candidates → tally), you may disagree. Your
   prior framing was "deterministic tally helper". Pick one and tell
   us the smallest version.

3. **`late_fusion_retrieve` scoring sanity** — current implementation
   uses synonym-expanded BM25-style token overlap on
   `EVENT.data["content"]`. Failing case: gpt4_7fce9456. Property
   views in the context might be in CONCEPT nodes' descriptions, not
   in EVENT content. Should we union EVENTS + CONCEPTS in the
   chunk pool? If yes, where to draw the line (CONCEPT bodies
   contain narrative summary that may mislead)?

4. **Failing cases analysis**:
   - `gpt4_f420262d` (Valentine airline JetBlue vs AA): the user
     mentioned both. ATTRIBUTE-MISMATCH refusal rule didn't fire
     because the reader had concrete-looking data. What's the
     **deterministic** signal that says "this isn't the right
     mention"?
   - `gpt4_f420262c` (airline order): order ledger is empty, falls
     back to reader. What `build_evidence_ledger(shape="order")`
     should produce here?
   - `09ba9854_abs` (bus to hotel — should refuse): reader confidently
     priced JP travel. What's the deterministic refusal trigger?

## What's in the round-2 module now

```python
# build_evidence_ledger as shipped (truncated)
def build_evidence_ledger(question, shape, fused_context) -> dict:
    ledger = {
        "shape": shape, "question": question,
        "question_date": fused_context.get("question_date"),
        "graph_hits": fused_context.get("graph_hits", []),
        "raw_hits": fused_context.get("raw_hits", []),
        "candidates": [],
    }
    if shape == "count":     ledger["final_count"] = None  # NEVER FILLED
    elif shape == "order":   ledger["ordered"] = []
    elif shape == "duration_since": ledger["value"] = None; ledger["unit"] = None
    elif shape == "date_diff":      ledger["answer"] = None
    elif shape == "derived_time":   ledger["result"] = None; ledger["unit"] = None
    elif shape == "abs_value":      ledger["answer"] = None
    return ledger

# answer_from_ledger reads slots — always None → returns None
```

## Deliverable

ONE markdown doc:

### Section 1 — Per-shape `build_evidence_ledger` fill algorithm

For each of the 6 shapes (`count`, `order`, `duration_since`, `date_diff`,
`derived_time`, `abs_value`), the smallest deterministic algorithm to
fill the slot. Code-level pseudocode is fine; reference the actual
`raw_hits` and `graph_hits` structure shown above.

### Section 2 — Whether to make an internal LLM sub-call

Pick one: yes (deterministic-tally helper that uses LLM extract +
post-process) or no (pure regex/keyword extraction). Justify. If yes,
the exact prompt + post-process logic.

### Section 3 — `late_fusion_retrieve` chunk pool

Should we union EVENT and CONCEPT nodes in the chunk pool? If yes,
how to weight / dedupe. If no, why.

### Section 4 — Per-failing-case fix mapping

For each of the 6 failing smoke cases, the specific fill-rule that
would change the outcome:
- `gpt4_f420262d` Valentine airline
- `gpt4_f420262c` airline order
- `a3838d2b` charity events before X (count)
- `9ee3ecd6` remaining points (derived_time)
- `09ba9854_abs` bus to hotel (abs_value, should refuse)
- `gpt4_7fce9456` property views before offer (count)

### Section 5 — Re-smoke prediction

Given your proposed fixes, how many of the 6 currently-failing
smoke cases would flip to CORRECT? Honest call. If less than 4 of
them, name what's structurally missing.

## Reasoning effort
xhigh. You have the full smoke output above. Don't second-guess the
constraints (provider routing, no writer changes, TR+MS only, no
more prompt text). Begin.
