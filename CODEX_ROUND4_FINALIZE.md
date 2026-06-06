# Codex Round 4 — Final Verification (LAST PASS)

This is the **last** round-2 adjustment. After this answer, the plan
is frozen and implementation starts. The user's instruction is:

1. **Scope is locked**: TR + MS ONLY. KU / SSA / SSP / SSU are
   explicitly out of scope. Do NOT propose any change that touches
   them, and if your plan has any incidental change that affects
   them, flag it explicitly.
2. **Re-verify every single one of the 45 wrong cases** (15 TR + 30
   MS). For each, confirm or revise:
   - Is the case **truly covered** by the proposed fix, or is it
     covered "in spirit" (likely-but-not-certain)?
   - What is the **realistic probability** the fix moves this case
     from wrong → CORRECT under the judge? Use one of
     `>90%` / `70-90%` / `40-70%` / `<40%` / `unknown`.
   - If `<70%`, name the **specific failure mode** that would prevent
     the fix from working and whether a second fix or a different
     mechanism is needed.
3. **Last chance to add anything** — if there is any per-case
   intervention not currently in the plan that you think is missing,
   add it now.
4. The current canonical plan you produced is
   `/home/ydeng/Code/CogniFold/CODEX_ROUND2_PLAN.md`. Treat it as the
   baseline and revise.
5. **Do NOT propose new structural changes** (no new modules, no
   architecture rewrites). Only per-case refinements within the
   current architecture (`round2_evidence_ledger.py` + resolver
   patches + 4 YAML rules + `generate_answer` integration).

## Required output

Produce ONE markdown document with two sections:

### Section A — 45-row verification table

Same labels as before (TR-01..TR-15, MS-01..MS-30). One row per case.
Schema:

```
| label | qid | proposed fix from CODEX_ROUND2_PLAN.md (one-liner) |
covers? (full / partial / uncertain) | probability (>90/70-90/40-70/<40/unknown) |
if <70: missing piece OR alternative mechanism | net delta confidence |
```

For the 2 deferred cases (`370a8ff4`, `eac54add`), set `covers?` to
`deferred-by-instruction` and probability to `n/a`.

### Section B — Final adjustments to plan

For each row where you said `partial`, `uncertain`, or `<70%`, list:
- The case label + qid
- The smallest revision to the canonical plan that fixes it
- Map to specific file:func (real targets from CODEX_ROUND2_PLAN.md
  — no hallucinations; you already verified the layout in round 3)

If a case truly has no in-architecture fix, mark it `concede` with a
reason. Do NOT push it as a fixable case if you cannot defend the
fix.

### Section C — Final per-cluster probability budget

For each of these buckets, give the realistic expected count of
wins:

- `A:count` cases (6 MS)
- `A:order` cases (1 TR + 0 MS)
- `A:duration_since` cases (0 TR + 1 MS)
- `A:date_diff` cases (0 + 0)
- `A:derived_time` cases (0 + 4 MS)
- `A:abs_value` cases (0 + 2 MS)
- `B:chunk_fusion` cases (4 TR + 12 MS = 16)
- `resolver:resolve_anchor_date` cases (4 TR)
- `resolver:choose_duration_anchor` (1 TR)
- `resolver:resolve_order_candidates` → patched `_try_order_among` (1 TR)
- `resolver:normalize_date_diff` → patched `_try_diff_between` (1 TR)
- `qa_rule` cases (1 TR + 4 MS)
- `defer` cases (2 TR)

Total TR cases addressed = 13 + 2 deferred = 15. Total MS = 30. Show
expected wins per bucket as `<expected>/<total>` with one-sentence
justification.

### Section D — Final SOTA call

Given the per-case probabilities, what's the realistic N=500 score
range for round 2? Specifically:

- TR projected on N=133 (deferred cases excluded from numerator AND
  denominator since they're labeling disputes — judge will still
  mark them wrong, so include them in the denominator with 0
  expected wins)
- MS projected on N=133
- Total N=500 = (KU/SSA/SSP/SSU unchanged at iter27 / iter19 levels
  TBD by stack — give a range with the assumption that they hold
  flat at the round-1 iter31-stack-projected level) + TR + MS

## What you will NOT do

- Add new architecture pieces
- Re-open the disputed cases discussion
- Touch BATCH_SYSTEM_PROMPT
- Touch KU / SSA / SSP / SSU rules
- Re-propose any rule already in iter31 qa_answer (you listed 9 of
  them in round 3; do not re-add)

## Reasoning effort

xhigh. You have the 45 cases inline below (same content as before).
If your prior recall is solid, just verify against your memory of
those cases; if uncertain, re-read.

Begin.

---

## The 45 cases (inline)
