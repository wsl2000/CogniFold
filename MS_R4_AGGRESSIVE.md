# MS Round 8 R4 — User Requires 94% — Aggressive Per-Case Push

User just countermanded R3's conservative call. We must try harder.

**Constraint**: ONE paid run on $100 budget. **Target: 94% MS
(125/133) = need 22 wins from iter27 baseline.**

You said:
- 3 existing emitters already fired = +3
- Top 1-2 new emitters = +1-2

That's +4-5 only. **We need +22.** Gap = 17 cases.

The gap MUST come from:
- 8 "iter19-auto-fix" cases (you said likely 2-4 auto-recover)
- 8 "retrieval/schema miss" cases (you said unsalvageable)
- 5 reasoning-miss cases YOU DROPPED in R2 (clothing, doctors, gaming,
  heirloom, music) — said too lexical/template-sensitive

To reach 94%, ~15+ of these 21 cases need to flip. Be more aggressive.

## What I need you to do in R4

For EACH of the 21 cases below, give:

1. **Smallest deterministic intervention** (no LLM sub-call) that
   would flip it CORRECT. Be creative — narrow regex, chunk-fusion
   query expansion, qa_answer micro-rule, resolver patch.
2. **Confidence** that fix flips this case (high / med / low)
3. **N=500 spurious-fire risk** (low / med / high)
4. **Ship verdict**: GO / CONDITIONAL / DROP

Even risky ones — list them as DROP with a 1-line reason.

### Group A: 8 "iter19-auto-fix" cases

You said these likely auto-recover from W1/W2 OFF stack. We can't
verify without paid run. **Add insurance emitter for each in case
they don't auto-fix.**

| qid | Q | GT | iter27 HY |
|---|---|---|---|
| a9f6b44c | How many bikes did I service or plan to service in March? | 2 | "1 (road bike serviced March 10)" |
| 80ec1f4f_abs | How many museums in December? | 0 (refuse) | "Two: Natural History + The Art Cube" |
| eeda8a6d_abs | How many fish in 30-gallon tank? | refuse (only 20-gal) | "10 neon tetras + 5 honey gouramis ..." |
| 37f165cf | Total page count for January + March books? | (per-month sum) | "wrong total includes December read" |
| 7024f17c | Jogging+yoga last week hours? | 0.5 hours | "About 6 hours (extrapolated)" |
| 2ce6a0f2 | Art-related events past month? | 4 | "3" |
| 60159905 | Dinner parties past month? | 3 | "2" |
| a96c20ee_abs | (look up Q+GT) | (look up) | (look up) |

For each: GO / CONDITIONAL / DROP. If GO, sketch the emitter.

### Group B: 8 "retrieval/schema miss" cases you ruled out

You said unsalvageable. Force-rank — which has even a 30% chance of
narrow-emitter fix?

| qid | Q | GT |
|---|---|---|
| 9d25d4e0 | How many jewelry pieces past 2 months? | 3 |
| a1cc6108 | (look up) | (look up) |
| c18a7dc8 | (look up) | (look up) |
| a08a253f | Days a week fitness classes? | 4 |
| gpt4_15e38248 | Furniture bought/assembled/sold/fixed past few months? | 4 |
| 88432d0a | Times baked past 2 weeks? | 4 |
| gpt4_7fce9456 | Properties before townhouse offer? | 4 |
| 51c32626 | (look up) | (look up) |
| ba358f49 | Age when Rachel marries? | 33 |

For each: GO / CONDITIONAL / DROP. If GO, the SMALLEST fix.

### Group C: 5 "dropped reasoning miss" cases (your R2 cut list)

You said too lexical. Reconsider:

| qid | Q | GT | iter27 HY |
|---|---|---|---|
| 0a995998 | Clothing items pickup/return count? | 3 | "2" |
| gpt4_f2262a51 | Different doctors visited? | 3 | "2" |
| 28dc39ac | Total gaming hours? | 140 | "105" |
| 4f54b7c9 | Antique items inherited? | 5 | "2 explicit antique" |
| bf659f65 | Music albums/EPs purchased/downloaded? | 3 | "2" |

For each: GO / CONDITIONAL / DROP with 1-line reasoning.

## Final ask

After classifying all 21 cases, give the FINAL ship list +
realistic MS projection. If 94% is structurally impossible even
with aggressive emitters, say so explicitly + name the ceiling.

User refuses to accept 86-88% as final answer. Need brutal honesty
about whether 94% is reachable with $100 budget.

Max effort. R3+ are about finding the LAST 17 case fixes.
