# Codex Round 7 R5 — Your Independent Plan (Decoupled)

After R4 you've reviewed my v4 ship plan and given critique. Now I
want a different exercise: **forget my plan for a moment, and propose
YOUR own version**.

## Same constraints, fresh eyes

- TR + MS ONLY (ignore KU/SSA/SSP/SSU). Iter27 N=500 was 86.8%
  overall (TR 80.5%, MS 77.4%). Iter31 round 1 TR-only N=133 hit
  88.7% TR. We want round 2 to push both.
- 1 round budget. Provider: commonstack only for gpt-5.4-mini.
  No writer-side changes (writer changes destroyed iter28-30).
- Same 10 smoke qids we've been working through.

## What's already in the repo (you can rely on these)

- iter31 round 1 stack (W1/W2/W3/Reflector OFF, X1 topic_timeline,
  X4 CHRONOLOGICAL-SCAN, 8 qa_answer rules from round 1) — TR 88.7%
  on N=133
- Resolver patches that work: `_choose_duration_anchor` (b46e15ed),
  `_try_named_day_recall` re-enabled (gpt4_d6585ce9), `_try_diff_between`
  exclusive default (08f4fc43), Pass 3 gate for recovery cases
- Row-contract semantic tags in `_normalize_rows` (has_completed_travel,
  has_planning, etc.)
- 2-reservoir late_fusion_retrieve (EVENT + CONCEPT)
- Property-specific second-pass retrieval

## What I shipped in v4 (for context only — don't anchor on this)

3 emitters that fire on smoke:
- emit_sephora_remaining → 9ee3ecd6 (MS)
- emit_bus_taxi_scope_refusal → 09ba9854_abs (MS)
- emit_graduation_count → 81507db6 (MS)

Plus 1 conditional (emit_property_count_before_offer) that only
fires if runtime retrieval surfaces the 4 prior properties for
gpt4_7fce9456.

3 TR cases still wrong as retrieval misses:
- gpt4_f420262d (Valentine airline)
- gpt4_f420262c (airline order)
- a3838d2b (charity-events-before count)

## Your task — independent proposal

Given the constraints and what's in the repo, **what would YOU
ship in round 2 to maximize TR + MS on N=266**? Specifically:

1. **What's the highest-leverage thing I haven't tried** that
   would hit any of the 3 TR retrieval-miss cases? Be concrete —
   a query expansion lexicon, a writer-side rule (but you said
   writer-side is forbidden), an extra retrieval pass, a new
   resolver method. What and where.

2. **Should I add per-shape emitters for OTHER TR clusters in
   iter31's N=133 wrong list** beyond the 10 smoke cases? E.g.
   the 4 order_among cases, 3 named_day cases, 2 _abs cases. I
   only have data for the 5 wrong cases that intersect the smoke
   set. Should I dig into the other 10 TR wrongs?

3. **For MS, the 22 undercount cases (iter27 baseline)** — would
   you write a generic MS-A undercount emitter (e.g. "how many
   distinct entities of type X did I do") or stay case-by-case?

4. **What's YOUR honest projection for TR/MS on N=266** under
   your independent plan? Don't just match my number. If you
   think the round 2 ceiling is lower, say so.

5. **What's the single biggest risk** in shipping ANYTHING in
   round 2 vs just running N=500 on iter31 round 1's stack (no
   new code)? Is there a "do nothing more" option that's
   actually better?

## Discussion expected

After your independent proposal, we'll compare:
- Your plan vs my v4
- Where we disagree on case prioritization
- Combined-best ship set

Then we ship. Multi-round dialogue continues. Maximum effort.
