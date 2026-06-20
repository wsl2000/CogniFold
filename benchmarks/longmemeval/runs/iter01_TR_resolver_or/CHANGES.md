# iter01 — TR resolver expansion

## Score
- **strict: 83.0%** (415/500)
- partial: ~83.6%
- NET vs iter00: **+15 correct (+3.0 pts)**

## What changed vs iter00
- `symbolic_resolver.py`: added/strengthened TR patterns (date_diff_between, rank_among, named_day_recall variants)
- `run_eval.py`: refined `_ASSISTANT_RECALL_TRIGGER` regex (narrow form requiring past-conversation anchor)
- `run_eval.py`: added `build_assistant_recall_block`, `build_temporal_block`, `build_recency_block`
- `configs/longmemeval_profile.yaml`: minor anchor rule tweaks (rules 1-8 only; rules 9+10 NOT touched yet)

## Target failure cluster
TR ago-questions ("how many days ago…", "how long ago…") that resolver was missing.

## Decision
**Keep** — pushed as part of iter2 commit f5ec922.
