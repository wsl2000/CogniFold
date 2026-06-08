# MS Round 8 R8 — FINAL Sanity Check

7 rounds done. User wants final confirmation: **is this plan
reasonable + credible?** Brutal honest go/no-go.

## R7 lock summary

3 modules, 6-7h dev, expected 22-24 wins, MS projection 94-95.5%.

| Module | Target | Wins | Risk |
|---|---|---|---|
| M1 Constraint/Semantics gate | A+H | 7-8 | 0-2 regress |
| M2 COUNT_CANDIDATES-lite | B+D+E | 8-10 | 1-4 regress ← biggest |
| M3 Numeric composer | F | 2-3 | 0-2 regress |
| Aliases | scatter | 1-2 | 0-1 regress |
| **Total** | | **22-24** | **2-8** |

Net (after regression): 14-22 → MS 87-94%.

## R8 final-confirm questions

### Q1: How confident are you this lands ≥94%?

Not "could land there" — actual **probability**:
- P(MS ≥ 94%): __%
- P(MS in 90-94%): __%
- P(MS < 90%): __%
- P(MS regresses below iter27 77.4%): __%

### Q2: What's the MOST likely failure mode?

Pick ONE:
- a) M2 over-counts → multiple iter27-CORRECT cases regress
- b) Modules don't fire on intended targets (under-utilization)
- c) Reader confused by candidate blocks (context bloat)
- d) Dev time blowup (8-12h not 6-7h)
- e) Other (specify)

Realistic worst case scenario in 1-2 sentences.

### Q3: Compare to alternative — "do nothing more"

Just run iter31 stack with existing 3 emitters on MS=133. What's
the expected MS %? If it's 84-86%, my marginal gain from the plan
is +8-10pp. If it's 82-84%, marginal gain is +10-12pp.

What's your honest base rate estimate?

### Q4: Is this credible enough to spend the $100?

Yes/no. If no, what's the alternative use of the budget?

### Q5: Sign off

Final lock list, ordered by build priority:
1. ___
2. ___
3. ___
N. STOP HERE

Be brutally specific. No more iteration after this.

User just asked "你俩确认一下方案合理吗 可信吗".
