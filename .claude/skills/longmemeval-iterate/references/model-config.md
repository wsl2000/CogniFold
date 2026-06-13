# Model Configuration (Cost-Effective Stack)

## Role assignments

| Role | Model | Settings | Why |
|---|---|---|---|
| **Writer** (extraction) | `openai:gpt-4o-mini` | `temperature=0` | Mechanical JSON transcription; reasoning models add 10-30× latency for no gain. Dominant cost driver (~50 calls/qid × 500 qid). |
| **Reader** (QA) | `openai:gpt-5-mini` | `reasoning_effort=high`, `max_completion_tokens=24576` | Matches Mastra SOTA's reader exactly. Auto-applied by `run_eval.py:124-132` when model contains `gpt-5/o1/o3`. |
| **Judge** | `openai:gpt-4o` | default | **NEVER substitute.** Canonical LongMemEval judge — different judge breaks comparability with published numbers. |
| **Embedding** | `openai:text-embedding-3-small` | 1536 dim | 6× cheaper than 3-large. Rerank step compensates for the ~3-5 pp recall delta. |
| **Reranker** | `openai:gpt-5-mini` `reasoning_effort=low` (batched) | `--llm-rerank`, `--rerank-pool 100` | One batched call per question. ~5× cheaper than `gpt-5`-low with negligible quality drop on short-form ranking. |

Full N=500 cost ≈ **$15-25** on a high-TPM key.

## ⚠️ Rerank paradigm — use B (LLM-rerank), not A or C

| Paradigm | Decision |
|---|---|
| **A** — Bi-encoder (embedding cosine) | ❌ Already in hybrid retrieval; adding it as "rerank" is a no-op |
| **B** — LLM-rerank (batched, `--llm-rerank` flag) | ✅ **USE** — handles ordinals like "27th item", indirect references |
| **C** — Cross-encoder (Cohere/BGE) | ❌ Generic-IR trained; weaker on pragmatic queries |

**Always batched B.** Per-doc rerank with gpt-5-mini = 25,000 calls (≈ $15, 10+ h). Batched = 500 calls (≈ $0.50, 15 min). Wired via:
- `--llm-rerank --rerank-model openai:gpt-5-mini --rerank-reasoning-effort low --rerank-pool 100`

**Do NOT enable the legacy `use_llm_rerank=True`** — that flag routes through per-doc mode at hardcoded `gpt-4o-mini` (`src/cognifold/query/llm.py:95`). 50× more calls, weaker model.

## N_PARALLEL by tier (TPM-derived)

50 parallel needs ~1.04M TPM gpt-4o-mini + 50K TPM gpt-4o → **Tier 2 minimum**, Tier 3 comfortable.

| OpenAI Tier | gpt-4o-mini TPM | gpt-4o TPM | Recommended `N_PARALLEL` | Full N=500 wallclock |
|---|---|---|---|---|
| Tier 1 | 200K | 30K | **10** | ~3-4 h |
| Tier 2 ($50 + 7d) | 2M | 450K | **50** | ~30-45 min |
| Tier 3 ($100 + 7d) | 4M | 800K | 100 | ~15-25 min |
| Tier 4 ($250 + 14d) | 10M | 2M | 250 | ~10-15 min |
| Tier 5 ($1000 + 30d) | 150M | 30M | **500** (depth=1) | ~5-15 min |

**How to check your tier**: hit any model, read `x-ratelimit-limit-tokens` response header, or visit `https://platform.openai.com/settings/organization/limits`.

## Alternative: OpenRouter (when OpenAI quota is exhausted)

If the OpenAI key hits quota or upgrading tiers takes too long, OpenRouter offers a drop-in OpenAI-compatible gateway aggregating 100+ models (including all OpenAI ones via passthrough). Cost: ~5-10% markup over direct OpenAI; no tier waiting period.

**Setup**:
```bash
# .env
OPENROUTER_API_KEY=sk-or-v1-...
```

**Edit `scripts/parallel_longmemeval.sh`** — three diffs:
- prepend `OPENAI_BASE_URL=https://openrouter.ai/api/v1` to the env block
- swap `OPENAI_API_KEY` → `OPENROUTER_API_KEY`
- change every `openai:` → `openai/` in model flags (OpenRouter uses `/` as separator)

So: `--model openai/gpt-5-mini --writer-model openai/gpt-4o-mini --judge-model openai/gpt-4o`.

**Balance check** (OpenRouter exposes this, unlike OpenAI):
```bash
curl -sS https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OPENROUTER_API_KEY"
# returns {"data": {"total_credits": N, "total_usage": M}}; balance = N - M
```

**Judge integrity unchanged**: `openai/gpt-4o` on OpenRouter is the same gpt-4o model from OpenAI, just billed through the gateway. Numbers stay comparable to Mastra/Hindsight.
