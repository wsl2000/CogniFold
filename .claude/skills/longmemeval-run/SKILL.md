---
name: longmemeval-run
description: One-shot LongMemEval benchmark on a fresh CogniFold clone. Verifies env + API endpoints (~30 s, ~$0.01) and then runs the full N=500 benchmark on the recommended gpt-5 stack (~2-4 h wall-clock, ~$80-150 cost). Single command, no parameters to think about. Use after `git clone`, on a new machine, when the recommended stack changes, or when a previous run failed with API or environment errors. SKIP for other benchmarks (LoCoMo, MuSiQue, CogEval-Bench) — those have their own runners.
---

# LongMemEval One-Shot Run

## When to invoke

- User just did `git clone` and asks "how do I run LongMemEval"
- User says "run the benchmark" / "open-box test" / "first run"
- Previous run failed and the user wants to retry from scratch
- A new chat / embed / judge provider was added — verify each endpoint
  then re-run the full benchmark
- After `git pull` brings new code — verify and re-run

Do NOT invoke if the user is asking to iterate on the score (that's
`longmemeval-iterate`) or to run another benchmark (LoCoMo, etc.).

## Recommended stack (defaults)

These are the models the script pings at steps 6-8 and then uses in the
full N=500 run. Defaults live in `scripts/parallel_longmemeval.sh`
(source of truth) and are mirrored in `scripts/run.sh` for the ping
checks.

| Role | Default | Why |
|---|---|---|
| reader | `openai:gpt-5` (reasoning_effort=high auto) | the qa_answer prompt assumes a reasoning model — strongest available reader |
| writer | `openai:gpt-5` (reasoning_effort honored from env) | strongest extractor — preserves attributes the user named verbatim |
| judge | `openai:gpt-4o` | canonical LongMemEval judge; **do not substitute** without re-calibrating against published numbers |
| rerank | `openai:gpt-5` (batched, pool=100) | one batched call per question; handles "27th item" / ordinal references |
| embed | `openai:text-embedding-3-large` (1536 dim via API `dimensions` param) | strongest embedding; cognifold/embeddings/providers.py passes `dimensions=1536` so the graph schema stays compatible |

Override any role by exporting `READER_MODEL` / `WRITER_MODEL` /
`JUDGE_MODEL` / `RERANK_MODEL` / `EMBED_MODEL` before invoking the
script.

Stratified sampling: 133 per question type (one type, `temporal-
reasoning`, has 133 questions — the cap means "take all" for every
type, so the full 500 set is processed). Override with the second
positional arg to `scripts/parallel_longmemeval.sh` if needed.

W1 (`EXTRACT_TYPED_ATTRIBUTES=1`) is enabled by default in `run.sh`.
W2 (`RESOLVE_EVENT_DATES=1`) is **off** by default.

## What it does

Single script `scripts/run.sh` does:

1. **Eight env + API checks** (~10 s, ~$0.001) — halts on any failure:

| # | Check | Failure means |
|---|---|---|
| 1 | working tree at repo root | wrong cwd |
| 2 | Python 3.11+ + `.venv` present | run `make dev` or `python -m venv .venv && pip install -e ".[dev]"` |
| 3 | `cognifold` + benchmark modules importable | venv broken or deps mismatch |
| 4 | dataset file at `benchmarks/longmemeval/data/longmemeval_s_cleaned.json` | dataset not pulled (LFS / submodule) |
| 5 | `.env` has chat key (`OPENROUTER_API_KEY` recommended) | user has to fill `.env` |
| 6 | chat-model ping (1 call) | model name wrong / quota / network |
| 7 | embed ping (1 call) | embed endpoint not available on chat provider, OR returned dim ≠ 1536 (cognifold expects 1536) |
| 8 | judge-model ping — `openai/gpt-4o` (1 call) | judge model not hosted on chosen provider |

2. **Full N=500 benchmark** on the verified provider (auto-tuned
   parallelism: 100 on OpenRouter / OpenAI direct, 10 on commonstack).
   Result lands at `benchmarks/longmemeval/runs/<LABEL>/`.

## How to run

```bash
# Default (verify + run full N=500, label = run_YYYYMMDD_HHMM):
bash .claude/skills/longmemeval-run/scripts/run.sh

# With a custom label:
bash .claude/skills/longmemeval-run/scripts/run.sh my_first_run

# Env checks only, don't launch the full run:
bash .claude/skills/longmemeval-run/scripts/run.sh --check-only
```

Reads `.env` for keys. Honors `OPENROUTER_API_KEY` (recommended),
`COMMONSTACK_API_KEY` (cap-50 RPM — script lowers parallelism to 10),
or `OPENAI_API_KEY` (direct).

Optional environment overrides — set before the script to test
non-default routing:

| env | effect |
|---|---|
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` | route embed to a different provider (e.g. OpenAI direct when chat is commonstack) |
| `JUDGE_API_KEY` / `JUDGE_BASE_URL` | route judge to a different provider (e.g. when chat provider has no gpt-4o) |
| `WRITER_MODEL` / `READER_MODEL` / `JUDGE_MODEL` / `RERANK_MODEL` / `EMBED_MODEL` | override the model names tested |

## After the run completes

Result files at `benchmarks/longmemeval/runs/<LABEL>/`:

- `metrics.json` — strict / partial scores + count by verdict
- `hypothesis.jsonl` — per-question answer + judge verdict + full context
- `wrong_cases.json` — failed cases grouped by type for cluster analysis

Read the metric back to the user as a single line, e.g.:

    strict 86.80% (434/500), partial 86.90% — label: my_first_run

## Hard rules

1. **Do NOT add steps the script doesn't already do** — if a check is
   missing the right move is to edit `run.sh`, not to layer a bespoke
   `curl` / `python` invocation in chat.
2. **Do NOT bypass any check** even if the user pushes. Each step
   catches a real failure mode that has cost a previous user a full run.
3. **Do NOT modify `.env`** without explicit user permission. If a key
   is missing, ask; never paste a key from past conversation memory or
   the codebase.
4. **Do NOT propose iter-level fixes** (revert this resolver, tighten
   that profile rule). That's the `longmemeval-iterate` skill's job.
   This skill only verifies + runs the *current branch state*.

## When checks fail

Each failure prints a single-line diagnosis + recovery command. Read it
verbatim to the user. If the same check fails twice, surface the raw
script output rather than re-summarising — environment debugging is
where Claude misinforms most often.
