# Codex Round 8 — MS-Only Push to 94% (LAST budget round)

User constraint: only $100 commonstack budget left. Pivot entirely
to MS. **TR is DONE — accept iter31 round 1's 88.7% TR as final SOTA**.

Target: **MS ≥ 94%** on N=133 = **≥ 125/133** = need **+22 cases**
beyond iter27 baseline (103/133 = 77.4%) OR **+16 cases** beyond
iter19 (109/133 = 82.0%).

## Stack rollback decision

We have two MS baselines to choose from:

- **iter19 stack** (W1 OFF, W2 OFF, gpt-5-mini): MS 82.0% on N=500
- **iter27 stack** (W1 ON, W2 ON, gpt-5.4-mini): MS 77.4% on N=500

iter31 round 1 stack (W1/W2 OFF, gpt-5.4-mini) is structurally
closest to iter19. Per Codex earlier: iter31 stack projected MS
~82-84% on N=133 without round 2 work.

**Question 1 for you**: Which base stack should we use for the
MS push?
- (a) iter31 round 1 stack (current, ~82% MS baseline projected,
  matches the TR=88.7% we shipped)
- (b) iter19 stack (need to revert to gpt-5-mini reader/writer,
  but that violates user's "model unchanged" constraint)
- (c) iter27 stack with W1 ON (gives SSA 100, MS hurt to 77.4)
  — bad MS baseline but already-built emitters land on top
- (d) Custom hybrid

I'd default to (a). Confirm.

## What's already implemented for MS

Three MS-target emitters in `round2_evidence_ledger.py` that
pre-screen 10/10 + N=500 spurious sweep 0:
- `emit_sephora_remaining` (9ee3ecd6)
- `emit_bus_taxi_scope_refusal` (09ba9854_abs)
- `emit_graduation_count` (81507db6)

Plus the R7 temporal_event_second_pass that's TR-targeted but the
chunk fusion side effect may help MS retrieval.

These give +3 MS wins (deterministic) on top of baseline iter31
stack.

## The MS gap

iter27 had 30 MS wrongs. Cluster taxonomy from
`.claude/skills/lme-auto-optimize/references/failure-taxonomy.md`:

- **MS-A undercount (22 cases)**: reader stops scanning after 2-3
  hits. "How many" / "total" questions undercount by 1-3.
- **MS-B refusal-with-data (4)**: refuses when answer is derivable.
- **MS-C wrong-winner (2)**: picks wrong of two candidates.
- **MS-D _abs misses refusal (2)**: shouldn't answer but does.

iter19 had ~24 MS wrongs — fewer because W2 was OFF (W2 added
noise that hurt MS in iter27). iter31 stack should match iter19's
MS = 109/133 = 82.0%.

For **94% MS = 125/133**, we need to flip 16 of the 24 wrongs.

That's 67% of the wrong cases. Per your earlier guidance: **MS is
heterogeneous and emitters need to be case-specific**. We can't
write one MS-A undercount emitter to cover all 22 — but maybe we
can cover 10-15 with surgical filters.

## Resources for you

I am attaching **all 30 MS wrongs from iter27 with full_context**
at `/tmp/ms_30_wrongs.md` (102KB). The question + GT + iter27 HY
+ full context for each. Per-case audit is necessary.

Plus you have:
- `benchmarks/longmemeval/round2_evidence_ledger.py` — current code
- `benchmarks/longmemeval/symbolic_resolver.py` — resolver patterns
- `configs/longmemeval_profile.yaml` — qa_answer rules (iter31 has 9
  rules already + iter32 added 4)
- `.claude/skills/lme-auto-optimize/SKILL.md` — workflow + rule
  style guide

## Constraints

- $100 commonstack budget. TR+MS earlier reality was $0.5-1/qid.
  $100 = ~120-180 qid worth of compute. MS=133 alone fits BUT
  need to be efficient. Can afford **MAX 1 N=133 run + smoke**.
- No model swap: gpt-5.4-mini stays on commonstack
- No writer changes that broke iter28-30
- Reader at high effort stays
- The 3 existing MS emitters stay

## What I want from you in R1

This is round 1 of ≥2 dialogue rounds. After your reply I review +
push back + iterate.

### Q1: Stack choice (above)

### Q2: MS achievability honesty

Is **MS 94% (125/133)** plausible in ONE more round on this stack?
If no, what's realistic? 88%? 90%? 92%?

Give honest call. If 94% is structurally unreachable, name the
ceiling.

### Q3: Per-case audit of 30 MS wrongs

For each of the 30 iter27 MS wrongs (data at `/tmp/ms_30_wrongs.md`),
classify:
- **retrieval miss**: GT-supporting evidence not in retrieved
  top-K → emitter can't help without retrieval expansion
- **reasoning miss**: evidence present, reader fails → surgical
  emitter possible
- **judge variance**: stochastic, no fix
- **iter19-already-correct**: iter27 W2 broke this but iter19 had
  it right → iter31 stack should already auto-fix

Give the count breakdown.

### Q4: Per-case fix mapping for the reasoning-miss subset

For each reasoning miss, what's the SMALLEST surgical filler that
would emit correctly? Use the same per-qid format you used for the
R5/R7 TR plan:

```
| qid | cluster | root cause | fix mechanism | safety gate |
```

Lexicon-based, deterministic, NO LLM sub-call (you said no in R5).

### Q5: Implementation order

Once you've identified the fixable cases, give me:
1. Which emitters to ADD beyond the 3 we have
2. Order to implement (highest ROI first)
3. Smoke test plan (specific qids to validate before paid run)
4. Pre-screen + N=500 spurious sweep gate

### Q6: Honest projection after all proposed emitters fire

Sum the case-level lifts:
- +3 from existing (Sephora, scope refusal, graduation)
- + new emitter wins from Q4

What MS % does this realistically deliver on N=133?

## After your reply

I will:
1. Push back on any case I think is misclassified
2. Ask for clarification on any unclear mechanism
3. Stress test the projection
4. We iterate ≥2 rounds before code/run

This is the LAST budget round. Be brutally honest. Don't optimistic-
project.

Maximum effort.

---

## DATA — all 30 MS wrongs (inline below)

