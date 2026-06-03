# Exp A — Bucket C graph-dump findings

23 qids where iter02 reader refused with "I don't have memory of X". For each, we dumped the full graph (writer output, before retrieval) and grep'd for the GT entity + value.

## Final classification (writer-side vs retrieval-side)

| qid | Q | GT | Classification | Evidence |
|---|---|---|---|---|
| 37f165cf | Page count of 2 novels Jan+Mar | 856 | **RETRIEVAL** | Writer has nodes mentioning 416, 440 pages |
| 577d4d32 | Stop checking emails time | 7 pm | **RETRIEVAL** | Writer node: "stopping work emails and messages by 7 pm" |
| 5809eb10 | Bajimaya case construction year | 2014 | **RETRIEVAL** | Writer node: "Bajimaya v Reward Homes ... construction" |
| 59524333 | Gym time | 6:00 pm | **RETRIEVAL** | Writer node: "Gym Session 6:00 PM Mon/Wed/Fri" |
| 75499fd8 | Dog breed | Golden Retriever | **RETRIEVAL** | Writer node mentions "Golden Retriever" |
| 853b0a1d | Age silver necklace | 18 | **RETRIEVAL** | Writer captured both entity and "18" in same node |
| c18a7dc8 | Years older vs college grad | 7 | **RETRIEVAL** | Writer node has graduation + current age |
| c19f7a0b | Home time weeknights | 6:30 pm | **RETRIEVAL** | Writer node has 6:30 + weeknight |
| c9f37c46 | Standup → open mic months | 2 months | **RETRIEVAL** | Writer has standup + open mic nodes |
| d01c6aa8 | Age moved to US | 27 | **RETRIEVAL** | Writer captured age + US move event |
| 51c32626 | Sentiment paper date | Feb 1 | **WRITER paraphrased** | Has "submitted to ACL" but no Feb 1 date |
| 73d42213 | Clinic time Monday | 9:00 AM | **WRITER kept wrong time** | Captured "left home 7 AM Monday" — kept departure, dropped arrival |
| 51b23612 | Soviet cartoon name | Nu, pogodi! | **WRITER missed name** | Has "political humor" but no cartoon name |
| d6233ab6 | HS reunion advice | personalize | **WRITER missed HS history** | No reunion / debate / AP econ nodes |
| edced276 | Hawaii+NYC days total | 15 days | **WRITER partial** | Has "NYC 5 days" but NO Hawaii nodes |
| a1cc6108 | Age when Alex born | 11 | **WRITER ambiguous** | Has "Alex the intern", not "Alex the newborn" (source may have both, writer kept the wrong one) |
| ba358f49 | Age at Rachel's wedding | 33 | **REQUIRES INFERENCE** | Writer has Rachel-engagement but no derived age — needs user_current_age + 1 |
| dcfa8644 | Adidas→Converse days | 14 | **RETRIEVAL + missing resolver** | Writer has both anchor events (Jan 10, Jan 24); needs date_diff resolver to fire on "how many days" with single anchor |
| e4e14d04 | Book Lovers Unite weeks | Two weeks | **RETRIEVAL + computable** | Writer has "joined 3 weeks ago" + "meetup last week" → 2 weeks |
| gpt4_2c50253f | Wake Tue/Thu | 6:45 AM | **WRITER paraphrased** | Has "15 minutes earlier on Tue/Thu" but no baseline 7:00 → 6:45 |
| gpt4_cd90e484 | Binocular → goldfinch weeks | Two weeks | **WRITER partial** | Has "binoculars 3 weeks ago" + birding nodes but no goldfinch sighting node |
| 3c1045c8 | Dept avg age delta | 2.5 years | **INCONCLUSIVE** | Grep too broad (632 nodes match), need targeted source check |
| dd2973ad | Bedtime before doctor | 2 AM | **WRITER partial** | Has "doctor appt 10 AM Thursday" but no "2 AM Wednesday bedtime" node visible |

## Aggregate counts

| Category | Count | Implication |
|---|---|---|
| RETRIEVAL rank-out (writer has full answer) | 10 | retrieval improvements only |
| RETRIEVAL + needs computation (writer has anchors) | 2 | retrieval + new resolver |
| WRITER paraphrased value (entity captured, value dropped) | 4 | writer prompt improvement |
| WRITER missed entity entirely | 3 | writer prompt improvement |
| Requires inference (compute from other facts) | 1 | reader prompt improvement |
| Ambiguous / inconclusive | 3 | need source-level investigation |

**Bottom line**: Bucket C is ~half retrieval + ~half writer extraction. Not predominantly one or the other as initially hypothesized.

## Recommended fix actions

### For RETRIEVAL cluster (10 + 2 = 12 cases)
- **Action R1**: query expansion — for questions like "What time do I X" inject a hint that searches for both verb form and noun ("wake up time", "wake_at", "schedule") and BOOSTS time-of-day concepts to top of retrieval
- **Action R2**: hint block for time-of-day Qs — when question matches `what\s+time\s+do\s+i`, prepend nodes whose description contains a clock-time pattern (e.g., `\d{1,2}:\d{2}\s*(?:am|pm)`)
- **Action R3**: hint block for breed/name/specific-noun Qs — when question asks "what breed / what's the name of X", prepend nodes matching the proper noun

### For WRITER cluster (4 + 3 = 7 cases)
- **Action W1**: SECOND-pass writer that runs ONLY on user-role raw turns and extracts typed attributes (date, time, named entity, quantity) into dedicated nodes — no abstraction or paraphrasing. This sidesteps rule 9+10 failure (which inflated the MAIN extraction prompt). Run as a small follow-up pass.
- **Action W2**: prompt batch_extraction to include a "preserve verbatim" list when the user-turn contains numeric/date/proper-noun tokens.

### For COMPUTABLE cluster (3 cases)
- **Action C1**: Add to qa_answer template: "If retrieved nodes include date anchors and the question asks for a date difference / age inference, compute it before answering."

## Cost summary

- Exp A spend: ~$0.85 (just writer + judge-disabled)
- ROI: 23 cases triaged into 4 clear action buckets — saves $20-30 of guessing on iter05+

## Suggested next iteration plan

1. **iter05** — apply already-done fixes (datetime + R9-A regex + ctx bump). Re-run full N=500. Baseline-check + measure A+B impact.
2. **iter06** — implement R2 (time-of-day hint) and R3 (proper-noun hint) for the retrieval cluster. Implement W1 (second-pass attribute writer) for the writer cluster. Re-run.
3. **iter07** — implement new resolvers `order_among` + `event_by_relative_date` + tighten existing `date_diff_*` to fire on writer-found anchor pairs.
