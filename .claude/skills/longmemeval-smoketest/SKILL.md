---
name: longmemeval-smoketest
description: Verify a fresh clone of CogniFold is ready to run the LongMemEval benchmark before kicking off a full N=500 run (~60 min, ~$25). Use after `git clone`, on a new machine, when the recommended stack changes, or when a previous run failed with API or environment errors. Walks env probe → API smoke (chat, embed, judge) → tiny N=6 benchmark → sanity check → prints the canonical full-run launch command. SKIP for other benchmarks (LoCoMo, MuSiQue, CogEval-Bench) — those have their own runners.
---

# LongMemEval Smoketest

## When to invoke

- User just did `git clone` and asks "how do I run LongMemEval"
- User says "smoke test" / "open-box test" / "first run" / "verify env"
- Previous full N=500 run failed; need to root-cause environment vs code
- A new chat / embed / judge provider was added — verify each endpoint
- After `git pull` brings new code — verify stack still wires up

Do NOT invoke if the user is asking to iterate on the score (that's
`longmemeval-iterate`) or to run another benchmark (LoCoMo, etc.).

## What the smoketest does

Single script `scripts/smoketest.sh` runs nine checks in order; any
failure halts with an actionable message:

| # | Check | Failure means |
|---|---|---|
| 1 | working tree at repo root | wrong cwd |
| 2 | Python 3.11+ + `.venv` present | run `make dev` or `python -m venv .venv && pip install -e ".[dev]"` |
| 3 | `cognifold` + benchmark modules importable | venv broken or deps mismatch |
| 4 | dataset file at `benchmarks/longmemeval/data/longmemeval_s_cleaned.json` | dataset not pulled (LFS / submodule) |
| 5 | `.env` has chat key (`OPENROUTER_API_KEY` recommended) | user has to fill `.env` |
| 6 | chat-model smoke (1 call) | model name wrong / quota / network |
| 7 | embed smoke (1 call) | embed endpoint not available on chat provider |
| 8 | judge-model smoke — `openai/gpt-4o` (1 call) | judge model not hosted on chosen provider |
| 9 | tiny N=6 benchmark (1 qid per question type, ~3 min, ~$0.20) | full pipeline broken |

After all nine pass, the script prints the canonical full-run command.

## How to run

```bash
bash .claude/skills/longmemeval-smoketest/scripts/smoketest.sh
```

Reads `.env` for keys. Honors `OPENROUTER_API_KEY` (recommended),
`COMMONSTACK_API_KEY` (cap-50 RPM — fine for the smoketest itself, but
flag at end if user wants full run), or `OPENAI_API_KEY` (direct).

Optional environment overrides — pass before the script to test
non-default routing:

| env | effect |
|---|---|
| `SMOKETEST_SKIP_TINY=1` | skip step 9 (API smoke only, ~10 s, ~$0.001) |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` | route embed to a different provider (e.g. OpenAI direct when chat is commonstack) |
| `JUDGE_API_KEY` / `JUDGE_BASE_URL` | route judge to a different provider (e.g. when chat provider has no gpt-4o) |
| `WRITER_MODEL` / `READER_MODEL` / `JUDGE_MODEL` / `RERANK_MODEL` / `EMBED_MODEL` | override the model names tested |

## After it passes

The script prints the canonical full-N=500 launch line tuned to the
provider it just verified. **Read it back to the user verbatim** — do
not invent a different command. A typical output ends with:

```
✓ ALL CHECKS PASSED.

To run the full N=500 benchmark with the verified stack:

    bash scripts/parallel_longmemeval.sh 100 200 500 my_first_run

Expected cost: ~$15–25, wall-clock ~60–90 min on the verified provider.
Result will land at benchmarks/longmemeval/runs/my_first_run/
```

## Hard rules

1. **Do NOT add steps the script doesn't already do** — if a check is
   missing the right move is to edit `smoketest.sh`, not to layer a
   bespoke `curl` / `python` invocation in chat.
2. **Do NOT bypass any check** even if the user pushes. Each step
   catches a real failure mode that has cost a previous user a full run.
3. **Do NOT modify `.env`** without explicit user permission. If a key
   is missing, ask; never paste a key from past conversation memory or
   the codebase.
4. **Do NOT propose iter-level fixes** (revert this resolver, tighten
   that profile rule). That's the `longmemeval-iterate` skill's job.
   The smoketest only verifies the *current branch state* runs.

## When checks fail

Each failure prints a single-line diagnosis + recovery command. Read it
verbatim to the user. If the same check fails twice, surface the raw
script output rather than re-summarising — environment debugging is
where Claude misinforms most often.
