# Model Configuration (Recommended Stack)

## Role assignments

| Role | Model | Settings | Why |
|---|---|---|---|
| **Writer** (extraction) | `openai:gpt-5` | `reasoning_effort=low` default (override via `WRITER_REASONING_EFFORT` env) | Strongest extractor; low effort matches mechanical-JSON nature and keeps full N=500 wall-clock tractable. |
| **Reader** (QA) | `openai:gpt-5` | `reasoning_effort=high`, `max_completion_tokens=24576` | Auto-applied by `run_eval.py` when model name contains `gpt-5`/`o1`/`o3`. Reasoning chain handles derived dates, age inference, multi-fact synthesis. |
| **Judge** | `openai:gpt-4o` | default | **NEVER substitute.** Canonical LongMemEval judge — different judge breaks comparability with published numbers. |
| **Embedding** | `openai:text-embedding-3-large` | 1536 dim via API `dimensions` param | `cognifold/embeddings/providers.py` passes `dimensions=self.config.dimensions` so the graph schema stays at 1536. |
| **Reranker** | `openai:gpt-5` `reasoning_effort=low` (batched) | `--llm-rerank`, `--rerank-pool 100` | One batched call per question. Handles ordinals ("27th item") and indirect references. |

## ⚠️ Rerank paradigm — use B (LLM-rerank), not A or C

| Paradigm | Decision |
|---|---|
| **A** — Bi-encoder (embedding cosine) | ❌ Already in hybrid retrieval; adding it as "rerank" is a no-op |
| **B** — LLM-rerank (batched, `--llm-rerank` flag) | ✅ **USE** — handles ordinals like "27th item", indirect references |
| **C** — Cross-encoder (Cohere/BGE) | ❌ Generic-IR trained; weaker on pragmatic queries |

**Always batched B.** Per-doc rerank explodes to 25,000 calls (~10 h);
batched is 500 calls (~15 min). Wired via:

    --llm-rerank --rerank-model openai:gpt-5 --rerank-reasoning-effort low --rerank-pool 100

**Do NOT enable the legacy `use_llm_rerank=True`** — that flag routes
through per-doc mode at a hardcoded model in
`src/cognifold/query/llm.py:95`. 50× more calls, lower quality.

## Provider routing

Default is OpenRouter (chat + embed + judge via one gateway). The
launcher (`scripts/parallel_longmemeval.sh`) routes whichever key is
set:

| Key in `.env` | Effect |
|---|---|
| `OPENROUTER_API_KEY` | chat / writer / reader / rerank / embed / judge all via OpenRouter (recommended default) |
| `OPENAI_API_KEY` | all via OpenAI direct (requires tier with `gpt-5` access + embed dimensions support) |
| `COMMONSTACK_API_KEY` | chat via commonstack; the launcher auto-routes embed + judge to a caller-supplied `EMBEDDING_API_KEY` / `JUDGE_API_KEY` (since commonstack typically lacks `/embeddings` and `gpt-4o`) |

Per-role override env vars:

    READER_MODEL / WRITER_MODEL / JUDGE_MODEL / RERANK_MODEL / EMBED_MODEL
    EMBEDDING_API_KEY  / EMBEDDING_BASE_URL  (separate embed provider)
    JUDGE_API_KEY      / JUDGE_BASE_URL      (separate judge provider)
    WRITER_REASONING_EFFORT                  (writer-only reasoning effort)
    EXTRACT_TYPED_ATTRIBUTES                 (W1 verbatim-attribute pass)
    RESOLVE_EVENT_DATES                      (W2 event_date pass; not recommended for full-N=500 runs)

## Balance check on OpenRouter

OpenRouter exposes credits unlike OpenAI direct:

    curl -sS https://openrouter.ai/api/v1/credits \
         -H "Authorization: Bearer $OPENROUTER_API_KEY"
    # → {"data": {"total_credits": N, "total_usage": M}}; balance = N − M

## Judge integrity

The judge call is the only one whose model identity matters for
benchmark comparability. `openai/gpt-4o` via OpenRouter is the same
gpt-4o model from OpenAI — numbers stay comparable to Mastra / Hindsight.
