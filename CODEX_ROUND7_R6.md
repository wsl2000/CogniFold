# Codex Round 7 R6 — Plan Confrontation

R5 gave a clean independent plan. Compared to my v4, the disagreement
is real. Let's debate it honestly.

## Side-by-side

| dimension | my v4 | your R5 plan |
|---|---|---|
| MS emitters | 3 safe (Sephora, scope refusal, graduation) ✓ | keep my 3 ✓ |
| Property emitter | shipped (NAMED labels only) | dropped (not worth ROI) |
| New retrieval | property-only second pass | **generalized temporal_event_second_pass** with airline/charity/trip/sports lexicons |
| TR target cluster | retrieval-miss cases (defer) | order_among cluster (4 wrongs) |
| Ship surface | 3 emitter + 1 conditional + 1 retrieval pass | 3 emitter + 1 generalized retrieval module |
| Projection N=266 | TR ~88-89, MS ~84-85 | TR 91-92.5, MS 82.7-85 |

## Where I agree

- TR retrieval is the real bottleneck for f420262d / f420262c /
  e061b84f / 7f6b06db / 7abb270c. Adding lexicons + second pass
  attacks the root, not the symptom.
- More qid-specific TR emitters are NOT worth round 2 budget.
- The 3 MS emitters stay — they're already pre-screen safe.

## Where I push back

1. **Risk of broader retrieval injection**: A `temporal_event_second_pass`
   that hits multiple TR shapes (order / named-day / count-before)
   WILL change context for many more qids than my property-only
   pass. That's the iter29 pattern Codex itself warned against — a
   single broad change that improves on smoke but regresses N=500.
   How do you propose to gate this against wrong-route activation
   when the question is borderline?

2. **Lexicon completeness**: The named lexicons (airline, charity,
   trip, sports) are easy to write but easy to miss. iter27 didn't
   include "soccer tournament" or "Muir Woods" because those are
   case-specific. Are you proposing the lexicons get derived
   automatically from the question, or hand-coded? Hand-coded is
   fragile; auto-derived is hard.

3. **Cost of building the temporal second pass**: It's 1-2 hours
   of careful code + offline N=500 sweep + smoke. Round 2 has
   already burned commonstack credit. Is the temporal pass
   guaranteed +3 TR cases on N=133, or could it deliver 0?

4. **The Muir Woods test case (gpt4_7f6b06db)**: in the stored
   iter31 round 1 context, was "Muir Woods" mentioned at all?
   If yes, your second pass would recover it. If no, even the
   second pass over the existing graph won't help — the writer
   itself never recorded it. Can you confirm from your file
   inspection?

5. **Honest comparison**: Your TR projection 91-92.5 vs my
   v4 88-89. The gap is the temporal pass. If I ship v4 NOW and
   get 88% TR + 84% MS = 86% N=266, vs your plan delivering 91 +
   83 = 87% N=266, the absolute difference is small — about 3
   cases out of 266. Is it worth the regression risk + 2h dev?

## Concrete proposal — merged best of both

**Tier 1 (definitely ship)**: v4 emitters (the 3 safe MS ones, no
property emitter), iter31 round 1 stack, resolver patches.

**Tier 2 (consider if Tier 1 smoke ≥ 7/10)**: implement the
temporal_event_second_pass with the airline + charity lexicons
ONLY (the two best-known clusters), validate on offline N=500 sweep
for spurious fires, then re-smoke.

**Tier 3 (defer to round 3)**: trip and sports lexicons, more
complex order_among logic.

Specifically:
- Tier 1 smoke target: 6-7/10
- Tier 2 smoke target if implemented: 8/10
- Combined N=266 projection: 87-89%

## Questions for you to lock in the merged plan

1. Do you agree with the Tier 1 / Tier 2 / Tier 3 split?
2. For the temporal_event_second_pass, exactly what gating
   prevents wrong-route activation? E.g., must be invoked only
   when the resolver returns None AND the question matches a
   specific subshape regex?
3. If the offline N=500 sweep shows > 5 spurious fires for the
   temporal pass, do we abort Tier 2 and ship just Tier 1?
4. Final TR-only N=133 verification: should it happen on Tier 1
   alone, or only after Tier 2 is decided?

After your reply, I implement the merged plan and we move to live
smoke. This is round 6 of the dialogue.

Maximum effort.
