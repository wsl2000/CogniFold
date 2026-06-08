# MS Round 9 — Codex review of M1+M2+M3 implementation

R7+R8 plan locked. I implemented per your spec:
- **M1**: 4 new qa_answer rules (NO ROUTINE BACKFILL, CURRENT vs EVER, NEED vs TOTAL, USER-ONLY PROVENANCE)
- **M2**: COUNT_CANDIDATES-lite as context augmentation (NOT direct emit)
  - Gates: is_user_role + completed-action + non-planning + non-negation + distinct lemma
  - Alias map for clothes/jewelry/furniture/albums/doctors/events/parties/subscriptions
- **M3**: ARITH_OPERANDS as context augmentation (NOT direct emit)
  - Operand extraction: AGE=N, YEARS_AGO=N, YEARS_AT_PLACE=N, DAYS=N
  - Requires ≥2 operand-bearing rows to fire (else silent)

## Your specific R7/R8 concerns I addressed

1. **M2 over-counting risk** (your biggest flag, 1-4 regress estimate)
   - Tightened head-noun capture to 1-2 tokens (was 4)
   - Added stopwords: did/do/have/buy/got/get/saw/etc.
   - REQUIRE completed-action verb in row text (drops mere mentions)
   - REQUIRE distinct lemma (32-char head dedupe)
   - Excludes planning + future-commitment + negation rows

2. **M3 spurious risk on partial operands**
   - Hard floor: `len(operand_rows) < 2 → return ""` (silent, no misleading block)
   - Tag-based: only AGE/YEARS_AGO/YEARS_IN/DAYS patterns count

3. **Reader interaction** — both M2 and M3 inject `## COUNT_CANDIDATES`
   / `## ARITH_OPERANDS` blocks AFTER `## EVIDENCE_LEDGER_RAW`. Reader
   sees them in context, decides for itself (no direct answer emit).

## The full diff (358 lines)

```diff
EOF
cat /tmp/m1_m2_m3_diff.patch
EOF
```

(See actual diff at /tmp/m1_m2_m3_diff.patch in run env.)

## Review questions

### Q1: Spurious-fire on iter27-CORRECT N=500 cases?

Per-module honest spurious-fire rate estimate now that you see the
ACTUAL code:
- M1 (4 qa_answer rules): __ cases
- M2 (count candidates block): __ cases
- M3 (arith operands block): __ cases

Worst case: M2 fires on a row that wasn't intended (alias too broad?
completed-action verb matches in wrong context?).

### Q2: Did I tighten M2 enough?

The 1-4 regression you flagged in R7 — does this implementation
keep it under 2? Or is the alias map for clothes (12 items) +
events (7 items) still too broad?

If too broad, what specific narrowing? E.g. drop "watch" from
jewelry (collides with "watch a movie")?

### Q3: M3 coverage of buckets F + part of H?

Per R6 your bucket F (arithmetic composition) had 4 cases:
- MS-10 a1cc6108 (age delta)
- MS-14 c18a7dc8 (age-at-event)
- MS-23 edced276 (trip-duration sum)
- MS-26 ba358f49 (future-age arithmetic)

My ARITH_OPERANDS only fires when 2+ operand rows found.
Realistic — what % of F bucket gets surfaced operands?
(0-100% per case is fine.)

### Q4: Anything dangerously missing?

Critical pieces of R7/R8 lock that I MISSED in this implementation?
- Bucket E (rolling-window): is the in-question window detection
  (_TEMPORAL_WINDOW_RE) actually used downstream? Currently just
  reports yes/no in the block header. Reader sees it but no filtering.
- Bucket D (contamination/dedupe): I do 32-char lemma dedupe.
  Sufficient or need more (e.g. entity-name normalization)?

### Q5: Go / no-go for paid run

Given THIS code (not the abstract plan), final go/no-go on
spending $50-70 on LOW 5p MS=133 run?

- Yes, expected MS 90-94%, ship as-is
- Yes, but FIX [X] first
- No, regression risk too high — what to remove?

Be brutally specific. This is the last review before paid run.
