# Tier 3 Design — Mastra-OM-style for LongMemEval, on our concept graph

> Goal: beat Mastra (94.87% N=500 strict on gpt-5-mini reader) by reusing
> our 3-layer event/concept/intent graph as the substrate and adopting
> Mastra's read paradigm (all observations in static context, no retrieval).
> Hard budget: $100.

## Phase 0 findings — what Mastra actually does

Read from `mastra-ai/mastra` packages/memory/src/processors/observational-memory/.

### Observer (their writer)

- **Model**: `google/gemini-2.5-flash` with thinking budget 215 tokens.
- **Trigger**: when raw messages hit `messageTokens=30000`.
- **Output format** (exact lines, no XML):
  ```
  Date: Jun 4, 2026

  * 🔴 (09:15) User stated has two kids.
  * 🟡 (09:16) User's friend had birthday party in March. (meaning March 2026)
  * 🔴 (10:30) User will visit parents this weekend. (meaning June 7-8, 2026)
  ```
- **4 priority levels**: 🔴 high, 🟡 medium, 🟢 low, ✅ completed.
- **Temporal anchoring**: BEGIN time `(HH:MM)` always; END `(meaning DATE)`
  only when statement references a different past/future date.
- **Multi-event split**: one observation per line, each gets its own date.
- **Sub-bullet groups** (with `* -> `): for tool sequences in agentic
  contexts. **Not applicable to LongMemEval** (no tools).
- **State changes**: framed as natural-language supersession
  ("changing from Y", "no longer at previous location", "replacing the old").
- **Verb precision**: must use specific verbs ("purchased", "subscribed"
  not "got") — pulls from assistant's clarifying language when available.
- **Identifier preservation**: names, handles, IDs, distinguishing details
  for list items.

### Reflector (their consolidator)

- **Model**: same gemini-2.5-flash, temperature 0.
- **Trigger**: when observations hit `observationTokens=40000`.
- **Behavior**: reorganize + supersede outdated + preserve ✅ markers.
- **Output**: XML-wrapped — `<observations>`, `<current-task>`,
  `<suggested-response>`. The last two are agent-loop-only, not relevant
  to LongMemEval.
- **Retry mechanism**: 5 compression levels (0=none, 4=extreme), retry
  if output didn't compress.

### Reader (their actor)

- **Sees** in system prompt:
  ```
  The following observations block contains your memory of past
  conversations with this user.

  <observations>
  Date: Apr 23, 2023 (412 days ago)
  * 🔴 (09:15) User stated has a Golden Retriever named Max.
  ...
  Date: Jun 4, 2026 (TODAY)
  * 🔴 (08:00) User asked about hotel recommendations.
  </observations>

  IMPORTANT: When responding, reference specific details ...
  KNOWLEDGE UPDATES: prefer the MOST RECENT information ...
  PLANNED ACTIONS: if planned date is in past, assume completed ...

  <current-task>...</current-task>     (N/A for us)
  <suggested-response>...</suggested-response>  (N/A for us)
  ```
- **Prompt cache**: multiple system messages, one per chunk, separated
  by `--- message boundary (ISO_TIMESTAMP) ---` so old chunks stay
  byte-stable across turns. **Not relevant for LongMemEval** (single
  query per qid, no cache reuse).
- **`addRelativeTimeToObservations`**: appends "(N days ago)" / "(TODAY)"
  hints to each `Date:` header relative to the message time.

### Reader instructions verbatim (the rules)

After the `<observations>` block, Mastra appends:

> IMPORTANT: When responding, reference specific details from these
> observations. Do not give generic advice ... personalize ...
>
> **KNOWLEDGE UPDATES**: When asked about current state ... always
> prefer the MOST RECENT information. Observations include dates — if
> you see conflicting information, the newer observation supersedes the
> older one. Look for phrases like "will start", "is switching",
> "changed to", "moved to" as indicators that previous information has
> been updated.
>
> **PLANNED ACTIONS**: If the user stated they planned to do something
> (e.g., "I'm going to...", "I'm looking forward to...", "I will...")
> and the date they planned to do it is now in the past (check the
> relative time like "3 weeks ago"), assume they completed the action
> unless there's evidence they didn't.
>
> **MOST RECENT USER INPUT**: Treat the most recent user message as
> the highest-priority signal for what to do next ...

These rules directly address two of LongMemEval's hard clusters:
- KU (knowledge-update): the supersession rule.
- Forward-looking → backward-looking statement bridge: planned-actions rule.

## Phase 1 — implementation plan for our adaptation

### Stack (fits $100 budget after my fix)

| Role | Model | Why |
|---|---|---|
| Writer (observer) | `openai:gpt-4o-mini` | Mechanical observation extraction; **NOT** gpt-5-mini — that's what blew the budget today |
| Reader (actor) | `openai:gpt-5-mini` (reasoning_effort=high) | Match Mastra's fair-comparison reader |
| Reflector | **skip in Phase 1** | Our N=500 max observations ≈ 50 sessions × 15 concepts = ~750 lines × 80 chars ≈ 60KB — handle directly without consolidation. Reflector goes into Phase 4 ablation if Phase 3 hits ceiling |
| Judge | `openai:gpt-4o` | Canonical |
| Embedding | **none / dormant** | No retrieval in Tier 3 |
| Rerank | **none** | No retrieval in Tier 3 |

### File-level changes

1. **`benchmarks/longmemeval/run_eval.py`**:
   - **NEW** `build_observation_block(graph, question_date)`: render every CONCEPT node as a Mastra-style observation line. Format:
     ```
     Date: <session date>, <N> days ago

     * 🔴 (HH:MM) <concept title>. (meaning <event_date>)   ← if event_date present + different
     * 🟡 (HH:MM) <concept title>.
     * 🟢 (HH:MM) <concept description first sentence>.
     ```
   - Group by session date, descending (newest at bottom — matches Mastra "older first").
   - Priority derivation (already in iter28b code):
     - 🔴 high: `concept_type` in `{user_fact, preference, relationship, identity}`
     - 🟡 medium: default (`event`, `temporal`, etc.)
     - 🟢 low: `concept_type` in `{planning, intent, hypothetical, agent_belief, world_state, ongoing}`
   - Add `(N days ago)` / `(TODAY)` annotation to each `Date:` header.
   - **REMOVE** all retrieval-side blocks for Tier 3 mode:
     - `## CONCEPTS_NEAR_TARGET_DATE`, `## RECALL_TARGET_DATE`, proper-noun block, build_temporal_block — all skip when in Tier 3 mode.
   - **KEEP** at top:
     - `## TODAY` (today block, unchanged)
     - `## SYMBOLIC_ANSWER` (resolver hint, bypass=False — let reader override if wrong)
   - Add Mastra-verbatim reader instructions block after observations.

2. **`benchmarks/longmemeval/run_eval.py` writer side**:
   - Existing main extractor stays — produces concepts as before.
   - W1 typed_attr ON (already validated).
   - W2 off (already off).
   - **NEW lightweight reflector pass** (deferred to Phase 4 ablation): N=500 doesn't need it; skip.

3. **`benchmarks/longmemeval/symbolic_resolver.py`**: NO CHANGES.
   - Resolver runs as before, output goes into `SYMBOLIC_ANSWER` block.
   - Reader rule: "use SYMBOLIC_ANSWER as hint, may override based on observation chronology".

4. **`configs/longmemeval_profile.yaml`** qa_answer:
   - **NEW rule TIER3_OBSERVATIONS**: appended at end of qa_answer.
   - Copy Mastra's KNOWLEDGE UPDATES + PLANNED ACTIONS rules verbatim.
   - Add LongMemEval-specific scan instruction:
     > "Scan the `<observations>` block fully before answering. Observations are in chronological order (oldest first). For 'when' / 'how long ago' questions, search by topic in the observations and use the `(HH:MM)` time and `(meaning DATE)` suffix as your temporal anchor. For 'currently' / 'now' questions, use the LATEST observation that references the topic, ignoring earlier-stated information that has since been superseded."

5. **`scripts/parallel_longmemeval.sh`**:
   - **NEW env** `TIER3_OBSERVATIONS=1` toggles the new code path.
   - When set: switches query_mode, skips retrieval/rerank, builds observation block, no embeddings.
   - Default behavior unchanged (so iter19 stack still works for non-Tier-3 comparison).

### Phase 1 dev tasks (in order)

| # | Task | Effort |
|---|---|---|
| T1.1 | Add `build_observation_block` (date grouping, priority emoji, time anchoring, `(meaning DATE)` from event_date) | 0.5 day |
| T1.2 | Wire `TIER3_OBSERVATIONS=1` env in launcher to skip retrieval/rerank/all hint blocks except SYMBOLIC_ANSWER + TODAY | 0.5 day |
| T1.3 | Add reader instruction block (Mastra KNOWLEDGE UPDATES + PLANNED ACTIONS rules + our scan instruction) to qa_answer profile | 0.25 day |
| T1.4 | Smoke test on 1 qid; verify observation format renders correctly | 0.5 day |
| T1.5 | Hard-100 spike (Phase 2 in the plan) | — |

Total Phase 1 effort: ~2 days.

## Phase 2 — hard-100 spike (~$5-8)

Stack as above. Run on `hard100.txt`. Baselines:

| Run | hard-100 strict |
|---|---|
| iter02 | 22% |
| iter19 | 38% |
| **iter27** | **43%** (current best) |
| fork_r1 | 41% |
| **Tier 3 target** | **≥60%** |

If Tier 3 ≥ 50% → continue to Phase 3.
If < 43% → abort; the architecture doesn't help on these cases.

## Phase 3 — full N=500 (~$30-40)

Same stack. Run on canonical 500 qids.

| Threshold | Meaning |
|---|---|
| < 86% | Regression, abort |
| 86-90% | Tier 3 ≈ iter19, no architectural win |
| 90-94% | Real gain, partial Mastra catch-up |
| ≥ 95% | Match or beat Mastra 94.87% |

## Phase 4 — single ablation (~$30, fits remaining budget)

Pick ONE: which component contributes most?

- **Option A**: Tier 3 minus SYMBOLIC_ANSWER block (test whether resolver still adds value when reader has full chronology)
- **Option B**: Tier 3 with reflector pass (test whether KU questions improve when we mark superseded concepts)

I recommend Option A first — cheaper to validate; tells us whether to keep our 12 iters of resolver work or drop it.

## Risk register

| Risk | Probability | Mitigation |
|---|---|---|
| 60K observation context → lost-in-middle | medium | Reader instructions explicitly say "scan fully before answering"; Mastra reader has same context size at 30K+ and works |
| gpt-4o-mini writer's concept JSON doesn't render cleanly as observations | low | We already produce title + description per concept; rendering is just templating |
| Reader confused by chronological-only ordering (no relevance-sorted top-K) | medium-high | This is the experiment — if reader gets confused, Tier 3 doesn't work and we abort |
| Cost over $100 | low | Phase 2-3-4 = $80 hard cap; we have already spent $20 today and stand at $1465 cumulative on OpenRouter |

## Cost summary

| Phase | $ |
|---|---|
| 0 read source | $0 (done) |
| 1 implement | $0 (dev only) |
| 2 hard-100 spike | $5-8 |
| 3 full N=500 | $30-40 |
| 4 single ablation N=500 | $30 |
| Buffer / debug / re-tests | $25-35 |
| **Total in $100 ceiling** | **~$90-115** — tight but workable |

If we skip Phase 4 → ~$60-78 total. Safer.

## Open questions before starting Phase 1

1. **Branch strategy**: new `tier3` branch from `longmemeval-iter@ff91197`? Or inline-toggle in main `longmemeval-iter`?  Recommend new branch.
2. **`<observations>` block size cap**: when graph has > 1000 concepts (rare), do we drop low-priority concepts? Mastra hits this at 40K tokens via reflector; we'd just cap at e.g. 1500 lines and drop 🟢s first.
3. **Skip Phase 4 to save budget?** Recommend yes if Phase 3 ≥ 88% — the result is the result, ablation is nice-to-have.
4. **Confirm we keep `SYMBOLIC_ANSWER` block in Phase 3** (hint mode)? Yes.
