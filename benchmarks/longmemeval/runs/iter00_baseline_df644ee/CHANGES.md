# iter00 — baseline (commit df644ee on opennorve/longmemeval-iter)

## Score
- **strict: 80.0%** (400/500 correct, 10 partial, 90 incorrect)
- partial: 81.0%
- Total: 500
- Driver: OpenRouter, 100 parallel × 5 qids

## Stack
- Reader: `openai:openai/gpt-5-mini` (reasoning_effort=high auto-applied for substring "gpt-5")
- Writer: `openai:openai/gpt-4o-mini`
- Judge: `openai:openai/gpt-4o`
- Embed: `openai:openai/text-embedding-3-small`
- Reranker: OFF (no `--llm-rerank`)
- Symbolic resolver + temporal + bypass: ON

## Code state
Commit df644ee = TR resolver patterns (already merged). Contains 12 `_try_*` methods:
- date_diff_between, which_first, chronological_order, rank_among
- date_diff_ago, date_diff_since, relative_ago_recall
- diff_since_when, duration_activity, named_day_recall, latest_value, topic_recall

## Wrong-case breakdown
- TR: ~35
- MS: ~30
- KU: ~9
- SSA/SSU: ~16
- Total wrong: 100

## Decision
Reference point. All later iters measured NET vs this.
