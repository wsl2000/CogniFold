# iter27_gpt54mini_full_n500_W1W2

## Score
- **strict: 86.80%** (434/500), partial: 86.90%
- run date: 2026-06-03
- Reader: `openai:openai/gpt-5.4-mini` (reasoning_effort=high, auto-applied for "gpt-5" substring)
- Writer: `openai:openai/gpt-5.4-mini` (reasoning_effort=low via WRITER_REASONING_EFFORT)
- Judge: `openai:openai/gpt-4o`
- Rerank: `openai:openai/gpt-5.4-mini` (effort=low)
- Embedding: `openai:text-embedding-3-small` via OpenAI direct (EMBEDDING_API_KEY=sk-proj-*)
- Chat routing: OpenRouter (`openai/gpt-5.4-mini` → `gpt-5.4-mini-20260317`)
- W1 (typed-attributes): ON via EXTRACT_TYPED_ATTRIBUTES=1
- W2 (event_date resolution): ON via RESOLVE_EVENT_DATES=1
- AGG_MAX_CONTEXT_CHARS=15000

## What changed vs iter19
- Reader/writer/rerank: gpt-5-mini → **gpt-5.4-mini-2026-03-17** (newer model in same family)
- Writer reasoning_effort: high → **low** (cost optimisation, no quality penalty observed in TR-only runs)
- W1 typed-attribute extraction: **ON** (was OFF in iter19)
- W2 event_date pass: **ON** (was OFF in iter19; opt-in since iter18)
- Symbolic stack: iter25 (count_among verb-hard + opinion filter + lowercase-title filter for order_among)
- Embedding routing: OpenAI direct (NOT through OpenRouter) — new EMBEDDING_API_KEY / EMBEDDING_BASE_URL plumbing

## Why (target)
Validate that the theoretical-best configuration (newest gpt-5 family + W1 + W2 writer passes + iter25 resolver stack) lifts TR past the iter19 baseline of 78.9% and pushes overall past 87%.

## By-type vs iter19

| type | iter27 | iter19 | Δ |
|---|---|---|---|
| single-session-assistant | 56/56 (100.0%) | 51/56 (91.1%) | **+8.9** |
| single-session-preference | 28/30 (93.3%) | 27/30 (90.0%) | +3.3 |
| temporal-reasoning | 107/133 (80.5%) | 105/133 (78.9%) | +1.5 |
| knowledge-update | 73/78 (93.6%) | 74/78 (94.9%) | -1.3 |
| single-session-user | 67/70 (95.7%) | 68/70 (97.1%) | -1.4 |
| multi-session | 103/133 (77.4%) | 109/133 (82.0%) | **-4.5** |

## NET vs iter02 (bar = 83.2%)
- delta correct: +18 (434 vs 416)
- delta strict pts: +3.60

## NET vs iter19 (bar = 86.72%)
- delta correct: 0 (434 = 434)
- delta strict pts: +0.08

## Key observations

1. **Net zero vs iter19** — Despite model upgrade (gpt-5-mini → gpt-5.4-mini) and adding two writer passes (W1 + W2), overall score is identical to iter19. The expected +2-5pp TR lift did not materialise; TR moved +1.5pp, within the ±7pp stochasticity band.

2. **MS regression real (-4.5pp)** — Multi-session is the only large by-type movement, and it's negative. Hypothesis: W2 (event_date resolution) adds noisy absolute date anchors to MS questions where the GT depends on session-relative ordering, conflicting with reader reasoning. Need targeted on/off control per question_type.

3. **SSA perfect (56/56)** — W1 typed-attribute extraction appears highly effective on single-session-assistant questions; reader finds structured fields cleanly. +8.9pp over iter19.

4. **gpt-5.4-mini ≈ gpt-5-mini** — In this pipeline, the newer model variant gives no measurable advantage. Cost/latency similar.

5. **W2 net effect is negative or neutral** — TR gain (+1.5pp on 133 = ~2 cases) doesn't offset MS loss (-4.5pp on 133 = ~6 cases). Should not enable W2 globally.

## Resume operational notes

- First launch (100-way) hit embedding TPM 429 (OpenAI text-embedding-3-small @ 1M TPM); 55 of 100 batches failed. 225/500 captured.
- Second launch (55-way) resumed 275 missing; 12 more batches failed on embedding 429. Reached 440/500.
- Third launch (12-way) cleared the last 60 with no failures. Reached 500/500.
- Lesson: with 100 batches × W1+W2 writer + per-session embedding, OpenAI embed TPM is the bottleneck. Cap at ≤30 concurrent for full N=500 if using OpenAI direct.

## Decision
- **REJECT for default stack.** iter19 remains the PR-quality baseline.
- **W1 typed-attribute extraction**: KEEP as opt-in (helps SSA materially). Not promotion to default — needs orthogonal validation.
- **W2 event_date resolution**: REJECT for global use. Keep opt-in. Investigate if it can be conditioned on question type or pattern.
- **gpt-5.4-mini**: NEUTRAL. Use whichever is cheaper / available.

## Next iteration plan
- **iter28**: Borrow Mastra triple-date observation format (creation_date, referenced_date, relative_offset_days) on EVENT / CONCEPT nodes. Replace W2 with the triple-date writer pass. Expected TR +2-4pp on derived-date patterns (date_diff_ago, diff_since_when, relative_ago_recall) without the MS regression.
- Alternative iter28: priority tagging (🔴🟡🟢) on writer output + use in AGG_MAX_CONTEXT_CHARS truncation. Expected MS +1-2pp.

## Commit
- local only — not pushed (experimental branch `longmemeval-iter-experimental`)
- iter19 (86.72%) still represents the public-release-ready stack via PR #3
