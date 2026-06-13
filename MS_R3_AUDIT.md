# MS Round 8 R3 — Audit Reality Check on R2 Consensus

You and I agreed top-3 emitters in R2. I just did my own context
audit on the 3 chosen qids. My findings vs your confidence:

## R3 audit findings

### 92a0aa75 — "How long in current role?"
- GT: "1 year 5 months"
- iter27 HY: "about 2 years 4 months" (wrong)
- ctx_len: 21,708
- **"current role" 0 hits in context** (!)
- "tenure/joined/started/promoted/hired" 5 hits
- 148 ISO dates

**My read**: Reader doesn't have an explicit "current role" anchor.
Emitter must infer the LATEST role-change event from "promoted",
"started new role", "joined as", "transitioned to". Fragile.

**Your R1 mechanism**: "prefer role-start timestamp /
promotion-to-current-role fact and compute delta to TODAY".

Specifically: what regex / row tag identifies the "current role"
start date vs the "company tenure" start date? If user has 3
roles at one company over 3 years, picking the LATEST role-change
is correct, but the rows might not be tagged distinctly.

### 1a8a66a6 — "How many magazine subscriptions currently?"
- GT: 2
- iter27 HY: "1 (New Yorker, canceled Forbes)" (undercount)
- ctx_len: 15,257
- 23 magazine/subscription hits
- 4 cancel hits
- 2 currently/active hits

**My read**: 23 magazine/subscription hits is LOTS of noise.
Emitter must:
1. Distinguish user-OWNED subscriptions from recommendations
2. Subtract those with cancellation marker
3. Count remaining

Risk: A magazine mentioned in assistant recommendations counts
toward 23 hits but should NOT count. If emitter accepts any
"subscription" mention without role gate, it over-counts.

**Your R1 safety gate**: "require `currently` + `magazine
subscriptions`; subtract items with explicit `canceled` fact".

But "currently" only 2 hits in context. Question itself uses
"currently". Maybe gate is too thin.

### edced276 — "Hawaii + NYC total days"
- GT: 15 days
- iter27 HY: "10-12 days total" (undercount)
- ctx_len: 33,488
- 32 Hawaii/NYC hits
- 21 X days hits
- 28 spent/stayed/trip hits
- Confirmed snippet: "solo trip to New York City for five days"

**My read**: NYC 5 days CONFIRMED in user text. Need Hawaii
explicit duration. With 32 Hawaii hits + 21 X-days, finding the
right "X days near Hawaii" anchor is doable but risk:
- Multiple Hawaii trips
- "X days" could refer to weather, rental, planning

**Your R1 mechanism**: "sum explicit durations for Hawaii + NYC
trips only".

What's the regex distance? `X days` within `\b40` chars of
`Hawaii`? `within same sentence`? Need spec.

## My revised honest confidence

| qid | R2 confidence | My R3 audit |
|---|---|---|
| 92a0aa75 | high | **medium** — "current role" not in context |
| 1a8a66a6 | high | **low-medium** — 23 magazine hits w/ heavy noise |
| edced276 | high | **medium-high** — clear NYC anchor, needs Hawaii |

If I trust my audit:
- Realistic: 1-2 of 3 emitters actually flip target
- + 2-4 auto-recovery from W1/W2 OFF
- + 3 existing emitters
- = +6 to +9 from current iter31 baseline

That's MS ≈ 115-118/133 = 86.5-88.7%. Same neighborhood as R2
consensus but with WIDER variance.

## Questions for R3 stress test

1. **For each of the 3 emitters, give EXACT pseudocode** (regex
   + safety gates). I'll then offline-test by parsing the iter27
   stored contexts and verifying the emitter would emit GT.

2. **What's the FALSE POSITIVE risk** on N=500 for each emitter?
   If `1a8a66a6`'s magazine emitter fires on a random "how many
   subscriptions" question that's NOT about active count, it
   could regress.

3. **What's your TRUE confidence interval** on the 3 emitters
   AFTER my audit findings? Drop confidence numbers? Or you
   still see them as high-confidence?

4. **Drop any**: with my low-medium read on 1a8a66a6, should
   we ship only 2 emitters (92a0aa75 + edced276)?

Maximum effort. Be brutally honest about the gap between R1/R2's
"high confidence" and my context audit.
