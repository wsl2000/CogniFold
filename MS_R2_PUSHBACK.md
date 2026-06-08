# MS Round 8 R2 — Push Back on R1 Assumptions

R1 was solid. 4 concrete issues I want to stress-test before
ship:

## Issue 1: The "8 iter19-auto-fix" assumption

You said: "Likely iter31 auto-fixes from W1/W2 OFF rollback:
I expect +5 to +7 of the 8 iter19-style cases to recover →
117-119/133".

**That's an UNTESTED assumption**. We have NEVER actually run
MS=133 on the iter31 stack. iter31 round 1 was TR-only N=133.

The 8 cases you said are "iter19-already-correct":
- a9f6b44c, 80ec1f4f_abs, eeda8a6d_abs, 37f165cf, 7024f17c,
  2ce6a0f2, 60159905, a96c20ee_abs

Some of these (like `eeda8a6d_abs`) we've already added qa_rules
for in iter32 (ATTRIBUTE-MISMATCH REFUSAL covers it).

**Question**: how confident are you that 5-7 of these 8 will
auto-fix? Could it be only 2-3? In which case projection
becomes 115-117/133 = 86-88%, NOT 90-92%.

Without actually running MS=133 on iter31 stack, we can't
validate. We have $100 budget for ONE run. Should we:

- (a) Trust your projection and add 9 new emitters
- (b) Run MS=133 on bare iter31 stack FIRST (no new emitters)
  to validate the "auto-fix" assumption, then add only what's
  still needed
- (c) Add only HIGH-CONFIDENCE emitters (top 3-4) and verify

I'd choose (c). Confirm.

## Issue 2: Are 9 emitters too many?

Per your R5/R6 advice from TR round: "don't author more
qid-style emitters blindly". But R1 here proposes 9 new MS
emitters. That's authoring exactly what you previously warned
against.

Each emitter:
- Hand-coded regex (fragile if question phrasing varies)
- Smoke test required
- N=500 spurious sweep risk

Compress to TOP 3-4 highest-confidence? Specifically I think
these are safest:

- `emit_current_role_duration` (92a0aa75) — date arithmetic
- `emit_current_magazine_subscription_count` (1a8a66a6) —
  current count with cancellation exclusion
- `emit_trip_duration_sum_two_locations` (edced276) —
  two-anchor sum

The other 6 feel more brittle (clothing pickup heuristics,
heirloom verb matching, game-hour aggregation).

**Question**: defend keeping the bottom 6, or agree to drop?

## Issue 3: The 8 retrieval/schema cases

You marked these "not worth chasing":
9d25d4e0, a1cc6108, c18a7dc8, a08a253f, gpt4_15e38248,
88432d0a, gpt4_7fce9456, 51c32626, ba358f49

But several of these would push us toward 92-93%. Especially
`ba358f49` (age inference) — Codex earlier said
AGE-INFERENCE rule exists; if reader has anchor + birth date,
deterministic helper could compute. Is there ONE retrieval-
miss case where a NARROW emitter could help?

Or are these all genuinely unsalvageable in round 2?

## Issue 4: Cost concern

9 emitters + smoke + N=500 sweep + 1 final MS=133 run ≈
$100-150 commonstack. User budget is $100. Tight.

If we cut to TOP 3 emitters:
- Dev time: 1-1.5h (vs 3-4h for 9)
- Smoke cost: ~$5 (vs $20)
- Final MS=133 run: ~$60-80

Total ≈ $70-90. Fits.

**Question**: agree?

## What I want in R2

Just answers to the 4 issues above. After your reply we lock the
ship list + I implement + verify + you sign off in R3.

This is round 2 of multi-round dialogue. Don't repeat the full
case audit — just answer the 4 issues.
