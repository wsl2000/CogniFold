# LongMemEval — Hand-off Spec

> The detailed autonomous-iteration narrative this file used to carry
> has moved into the Claude Code skills. Start there.

## Where things live

| You want to … | Look at |
|---|---|
| Run the benchmark on a fresh machine | `.claude/skills/longmemeval-run/SKILL.md` and `scripts/run.sh` |
| Iterate on the score (cluster analysis, fix proposal, net-positive decision loop) | `.claude/skills/longmemeval-iterate/SKILL.md` |
| Recommended model stack + provider routing details | `.claude/skills/longmemeval-iterate/references/model-config.md` |
| The launcher entry point | `scripts/parallel_longmemeval.sh` |

## Recommended stack at a glance

| Role | Model |
|---|---|
| Reader | `openai:gpt-5` (reasoning_effort=high auto) |
| Writer | `openai:gpt-5` (reasoning_effort=low for full N=500 throughput) |
| Judge | `openai:gpt-4o` (canonical, do not substitute) |
| Reranker | `openai:gpt-5` (batched, reasoning_effort=low, pool=100) |
| Embedding | `openai:text-embedding-3-large` (1536 dim via API `dimensions` param) |

W1 typed-attribute pass: ON by default (`EXTRACT_TYPED_ATTRIBUTES=1`).
W2 event_date pass: OFF by default — see iter27 notes in
`benchmarks/longmemeval/HISTORY.md`.

## One-line run

    bash .claude/skills/longmemeval-run/scripts/run.sh

The script verifies env + pings each provider endpoint, then launches
the full N=500 benchmark. Auto-tunes parallelism to the chat provider
(100 on OpenRouter / OpenAI direct, 10 on commonstack).

## Section pointers from earlier code comments

References elsewhere in the codebase to `my_prompt.md §1.2` or similar
sections describe the batched-LLM-rerank paradigm (Paradigm B). That
discussion now lives in
`.claude/skills/longmemeval-iterate/references/model-config.md` under
"Rerank paradigm — use B (LLM-rerank), not A or C".
