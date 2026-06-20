# Codex Round 6 — Regression Debugging (Dialogue Mode)

**THIS IS A DIALOGUE.** Ask me clarifying questions if anything in the
data below is ambiguous or incomplete. I will answer and re-invoke
you. Goal: figure out the smallest change that makes the round-2
ledger actually help instead of hurt.

---

## What happened

Per your round-5 plan, I implemented the deterministic fillers. The
ledger module went from "placeholder slots, always return None" (v1)
to "filled slots with regex extraction" (v2). The intent was the
4-5/6 of failing cases would flip to CORRECT.

**Actual result: v2 = 0/10. v1 was 4/10.** The deterministic ledger
emits confidently-wrong answers that override the good resolver hits
from v1. This is the iter29 disaster pattern.

## v1 → v2 case-by-case (judge=gpt-4o, same context, same stack
otherwise)

| qid | v1 verdict + HY | v2 verdict + HY | what changed |
|---|---|---|---|
| `b46e15ed` (TR) | ✅ "About 2 months have passed (consecutive Feb 14-15 → April 18)" | ❌ "About 1 month has passed" | v1 used `_choose_duration_anchor` and got 2 months; v2 ledger fired `duration_since` and computed 1 month, overriding |
| `gpt4_d6585ce9` (TR named-day) | ✅ "You went with your parents." | ❌ "You likely went with a group of friends." | v1 used `_try_named_day_recall` (which I re-enabled this round) and got it right; v2 ledger ran a generic shape filler over the same context and dropped the parents row |
| `gpt4_f420262d` (TR Valentine airline) | ❌ "JetBlue" | ❌ "Assistant asked for 6 trip details for the user's Boston-to-Miami flight search" | both wrong; v2 got hijacked into a hallucination, ledger didn't fire |
| `08f4fc43` (TR date_diff) | ✅ "31 days (counting both Jan 2 and Feb 1)" | ❌ "0 days" | v1's reader produced the inclusive answer; v2 ledger `_fill_date_diff` found two rows but `best_a is best_b` (same row), returned `0 days` and emitted it |
| `gpt4_f420262c` (TR order airlines, ★ mandatory) | ❌ "Delta → United → AA → JetBlue" | ❌ "First Delta, then Spirit, and finally Jetblue." | v2 ledger `_fill_order` HALLUCINATED Spirit (not in the question or context) and only 3 airlines (GT requires 4); the order ledger emitted the wrong list with confidence |
| `a3838d2b` (TR before-anchor count) | ❌ "1" | ❌ "1" | same wrong; ledger did fire but produced 1 (GT=4) |
| `9ee3ecd6` (MS derived remaining) | ❌ "300 points" | ❌ "You needed 300 Sephora points" | derived_time `remaining_needed` rule did not fire — current=200 (have) and target=300 (need-to-redeem) regex did not match the actual chunks |
| `09ba9854_abs` (MS scope refusal) | ❌ "¥16,800–26,800 hallucinate" | ❌ "$31 — bus ¥3,200 vs taxi $60" | v2 ledger `_fill_derived_time` delta_savings tried to detect dest mismatch but said both rows mention "hotel" or neither — wrongly emitted savings |
| `gpt4_7fce9456` (MS count properties, ★ mandatory) | ❌ "1 property (Brookside)" | ❌ "2" | v2 ledger improvement from 1 → 2 but GT=4; chunk fusion still doesn't surface all 4 prior viewings |
| `81507db6` (MS count graduations) | ✅ "3" | ❌ **"13"** | v2 ledger `_fill_count` overshot dedup: counted 13 candidates because the entity-key heuristic (date+leading-words) split paraphrases into separate entities instead of merging them |

## Pattern across the regressions

Every v2 loss is the same shape: **the deterministic filler fires
with insufficient evidence and emits a wrong answer with apparent
confidence**, overriding either (a) the resolver's correct answer
(b46e15ed, gpt4_d6585ce9, 08f4fc43, 81507db6) or (b) the reader's
correct or partially-correct synthesis.

The four wins in v1 came from:
- `_choose_duration_anchor` → b46e15ed
- `_try_named_day_recall` re-enabled → gpt4_d6585ce9
- reader inclusive judge variance → 08f4fc43
- reader natural language paraphrase dedup → 81507db6

The v1 stack was: ledger ALWAYS returns None for these shapes
(slots placeholder), so the reader saw the fused context AND the
existing resolver hint and picked the right answer.

## My read of the bug

The ledger emits answers in cases it shouldn't. Two failures:

1. **Insufficient confidence gating**: `answer_from_ledger` emits as
   soon as `final_count is not None`, `ordered is not empty`, etc.
   The fillers don't track confidence — they emit on weak matches.

2. **Filler regex is too eager and too generic**: `_fill_count`
   accepts any row with one completion verb + one topic overlap.
   `_fill_order` picks any noun-sequence as an entity key.
   `_fill_derived_time` only matches narrow regex patterns that
   real data rarely fits.

## My proposed fixes (please critique)

A. **Tighten `answer_from_ledger`**: require candidate count ≥ K
   per shape (K=3 for count, K=3 for order, K=2 for date_diff). If
   below threshold, return None.

B. **Drop `_fill_derived_time` entirely for round 2**. The four
   patterns are too narrow and the misfires (09ba9854_abs +
   9ee3ecd6) cost real cases. Let the reader handle these.

C. **Make `_fill_count` only emit when ≥3 candidates AND anchor
   resolved**. For 81507db6 (3 graduations, judge accepted), v2
   counted 13 — entity key over-split. Either tighten entity key
   or only emit when low cardinality (≤6) and anchored.

D. **`_fill_order` requires len(ordered) == target_count**. If
   target_count is named in the question ("the four trips", "the
   six museums") and we have fewer than target_count, return None.

E. **`_fill_date_diff`: skip emit if `best_a is best_b` OR diff is 0
   days**. (`0 days` answer is the smoking gun for a failed
   resolution.)

F. **`_fill_duration_since`: require anchor overlap ≥ 3 tokens**.
   Current `_resolve_question_anchor` accepts overlap ≥ 2, but for
   b46e15ed the consecutive-day cluster needs the resolver-specific
   `_choose_duration_anchor` which doesn't go through this path.
   Maybe just drop `_fill_duration_since` and rely on resolver for
   TR-A.

G. **`_fill_abs_value` only emits the refusal**, never a positive
   answer. (My current `_fill_abs_value` returns `(None, mismatch,
   [])` always when no specific entity is named — so it actually
   never emits positive. But the refusal path also misfires.)

## Specific questions for you

1. **Is the right architecture to keep the ledger and tighten it, or
   to delete the ledger entirely and rely on the resolver patches +
   chunk fusion only**? The resolver patches gave us 4/10 on v1.
   That's our floor. Should round 2 ship with just (resolver
   patches + 4 YAML rules) and a NULL ledger, and call the ledger
   work technical debt for round 3?

2. For `81507db6` (GT 3, v2 said 13): the question is "how many
   graduation ceremonies in the past three months". Context likely
   has multiple mentions of each ceremony (paraphrases). What's the
   right dedupe key for "graduation ceremonies"? A normalized
   "graduation event name" entity? A (date, person) pair? The 13
   came from over-splitting.

3. For `gpt4_f420262c` (order airlines, mandatory): v2 emitted
   "Delta → Spirit → JetBlue". Spirit is not in the question.
   How did `_fill_order` find a Spirit row to include? Probably
   from the merged chunk pool — maybe the assistant suggested
   Spirit as an alternative airline. How do we filter that out
   without losing legitimate "user flew Spirit" rows?

4. For `gpt4_7fce9456` (mandatory): v1 said "1", v2 said "2". My
   chunk fusion is surfacing more property mentions but still
   missing 2 of the 4 GT properties. Are these properties
   genuinely not in the graph (in which case no ledger logic can
   recover) or are they present but not matching my synonym
   expansion / completion-verb filter?

5. **Should we run a debug pass that dumps the actual rows the
   ledger sees for each smoke case, so you can verify which
   evidence is present?** I can produce `iter32_smoke10_v2_rows.md`
   that shows, per case, the `rows` list that the filler operated
   on, so you can diagnose what was missing or misfiltered. Worth
   the effort?

## Constraints reminder

- TR + MS only; ignore other types
- gpt-5.4-mini → commonstack ONLY (no provider swap)
- No more prompt rules (the prompt-burial pattern from iter29/30)
- 1 round budget left after this; the iter must ship a measurable
  N=500 result

## What to deliver

A markdown document with:
- Your call on questions 1-5 above (with justification)
- A revised ledger fill+emit policy (which fillers stay, which go,
  what thresholds)
- Honest re-smoke prediction with the revised policy

If you need information from me to deliver, ASK and I'll
re-invoke with the answers. Don't guess.

Maximum effort.
