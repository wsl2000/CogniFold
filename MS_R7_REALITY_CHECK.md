# MS Round 8 R7 — Reality Check on R6 Plan

R6 had two issues. Address before lock.

## Issue 1: Math error in R6 projection

You wrote: "If baseline on 500 had 30 wrong, then baseline correct
= 470/500 = 94.0%; Fixing 26 yields 496/500 = 99.2%".

**Wrong denominator**. The 30 wrongs are MS-only from iter27 N=500.
We're targeting **MS-only N=133**, NOT N=500.

Real math:
- iter27 MS baseline: 103/133 = 77.4%
- Fix 26 MS wrongs → 129/133 = **96.9% MS**
- Fix 20 → 123/133 = **92.5%**
- Fix 15 → 118/133 = **88.7%**

So your bucket hit rate sums to ≈ 25 wins expected → MS 96%.
That MEETS 94% target.

Reconfirm — were you actually projecting 96% MS on N=133, or did
you mean something else?

## Issue 2: Bucket hit rates are optimistic

Your stated:
- A: 5/6 = 83% (abstention rules)
- B: 2/2 = 100%
- C: 3/4 = 75% (hyponym expansion)
- D: 4/5 = 80% (topic dedupe)
- E: 4/5 = 80% (rolling window)
- F: 4/5 = 80% (numeric composition)
- G: 3/4 = 75% (chain linking)
- H: 6/6 = 100%

That sums to **30 (your bucket size mismatch)**. Recount:
- A: 5 cases, expect 4 wins
- B: 2 cases, expect 2 wins (100% claim is optimistic)
- C: 3 cases, expect 2.25 wins
- D: 4 cases, expect 3.2 wins
- E: 4 cases, expect 3.2 wins
- F: 4 cases, expect 3.2 wins
- G: 3 cases, expect 2.25 wins
- H: 5 cases, expect 5 wins (100% claim is optimistic)
- = **25 expected wins** → MS 96%

**100% hit rate on B and H is highly optimistic**. Plus your earlier
R3/R4 audit found:
- B[MS-04] 28dc39ac (gaming hours sum) — risky
- H[MS-12] 92a0aa75 (current role) — 40-60% confidence (I audited)
- H[MS-24] 1a8a66a6 (magazine subscriptions) — 20-40% per R3
- H[MS-11] 9ee3ecd6 (Sephora) — already shipped, works
- H[MS-13] 73d42213 (clinic time) — explicit beats inferred, OK

Realistic hit on H: 4/5 = 80% (not 100%).

Revised expected wins:
- A 4, B 1.5, C 2.25, D 3.2, E 3.2, F 3.2, G 2.25, H 4 = **23.6**
- → MS = 103 + 23.6 = 126.6/133 = **95.2% MS**

Still above 94%! Even with this haircut.

## Issue 3: Architecture complexity vs $100 / 3p constraint

R6 proposes:
1. `COUNT_CANDIDATES` module (Layer A)
2. 4 second-pass modules (`count_items`, `count_events`,
   `count_financial`, `current_status`)
3. Normalization layer (alias collapse, date window, dedup)
4. 5-8 reader micro-rules
5. Orchestrator that decides which to fire

Dev time honest estimate:
- COUNT_CANDIDATES: 1-2h (must reuse property_second_pass pattern)
- 4 second-pass modules: 0.5-1h each = 2-4h
- Normalization layer: 1-2h (alias + date + dedupe)
- 5-8 micro-rules: 0.5h (YAML edits)
- Orchestrator + integration in run_eval: 1h
- Offline pre-screen on 30 cases: 1h
- N=500 spurious sweep: 30 min

**Total: 7-12h dev work BEFORE paid run.**

Plus regression risk: each module is a new code path that affects
context. iter29's failure mode was complexity → MS −27pp.

## R7 Questions

### Q1: Confirm projection corrected

If my math is right (96% best, 95% realistic), confirm. Or
recalculate.

### Q2: Realistic per-bucket hit rate

Drop the 100% rates. Give honest range per bucket. After my haircut,
am I being too pessimistic? Too generous?

### Q3: MINIMUM viable implementation that still hits 94%

If we have 6-8h dev budget (not 12h), what subset can we ship to
still reach 94% (=125/133 = need 22 wins)?

Specifically: do we need ALL 4 second-pass + COUNT_CANDIDATES +
normalization, or can we ship just COUNT_CANDIDATES + 1-2 second
passes for ~20 wins?

### Q4: Regression risk on N=500

R6 hit rates assume "covers iter27 wrong cases". What's the
spurious-fire rate on the 103 iter27 CORRECT cases? If any second-
pass module fires on a non-target and emits wrong, we lose ground.

What's your honest spurious-fire estimate per module?

### Q5: Implementation order with 6-8h budget

Drop the "build everything" plan. Give the MINIMUM critical path:
1. Module A → fixes M cases
2. Module B → fixes N cases
...
Stop when projected wins ≥ 22.

What order maximizes ROI per dev hour?

## Lock

After your R7 reply, I will:
- Either implement (if plan is clear + projection holds)
- Or iterate R8 if regression risk too high

User wants 94%, $100 budget, 3p. We've discussed 6 rounds.

Be brutally specific.
