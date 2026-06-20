# iter02 — qa_answer distinct-entity anti-confab + rerank ON (best so far)

## Score
- **strict: 83.2%** (416/500)
- partial: ~83.8%
- NET vs iter01: **+1 correct (+0.2 pts)**
- NET vs iter00: **+16 correct (+3.2 pts)**

## What changed vs iter01
- `configs/longmemeval_profile.yaml` (`qa_answer` template):
  - Added P1 distinct-entity anti-confabulation rule (instructs reader to NOT merge or substitute different named entities/dates when confidence is low)
- `scripts/parallel_longmemeval.sh`: turned `--llm-rerank` ON (reranker model: gpt-5-mini, reasoning_effort=low, pool=100)

## Target failure cluster
- Reader confabulation when two similar entities appeared in context
- Recall noise on MS questions (rerank tightens the top-K)

## Pushed
- Commit `f5ec922` on `opennorve/longmemeval-iter` (current HEAD on that branch)
- PR #2 to OpenNorve/CogniFold (base=main head=longmemeval-iter, reviewer=duanyiqun)

## Decision
**Keep, current best.** Any future iter must beat 83.2% to be pushed.

## Hardcore floor exposed (intersection of iter1 ∩ iter2 ∩ iter4 wrongs)
49 cases wrong in all 3 → theoretical ceiling with current stack = 90.2%.
See `RUNS_INDEX.md` for breakdown.
