# Round 5 Ledger Debug Response

## Section 1 — Per-shape `build_evidence_ledger` fill algorithm

First normalize `graph_hits` and `raw_hits` into one row stream. For each `NodeSummary` in `graph_hits`, emit `{source:"graph", node_id, node_type, role:data.role, date:best_date(node), text:title + " " + description, grounded_in, score}`. For each raw hit, emit `{source:"raw", node_id, node_type:"event", role, date, text, grounded_in:[node_id], score}`. `best_date()` should prefer an explicit inline date in `text` such as `on October 15th` or `in June`; only fall back to the node/session date if no event date is stated. Before any shape logic, drop rows that are pure planning/advice/list content unless they also contain a completion verb such as `booked`, `flew`, `attended`, `participated`, `viewed`, `saw`, `put in an offer`, `earned`.

For `count`, parse `(topic, action, temporal_bound, anchor_phrase)`. Resolve the anchor date if the question says `before/after/since/until`. Keep rows where `topic_match(row.text)` and `action_match(row.text)` are both true, reject planning/comparison rows, then apply the temporal filter against the resolved anchor. Dedupe by an entity key, not by noun alone: `airline`, `property label`, `event name`, or `(date, label)` for repeatable events. Exclude the anchor row itself and any row whose entity matches the target entity named in the anchor clause. If the question needs a temporal bound and no anchor resolves, set `missing_required_anchor`; otherwise set `final_count = len(candidates)`.

For `order`, use the same candidate extraction as `count`, but keep the earliest dated row for each normalized entity key and sort ascending by date. For airline-like questions, the entity key is the airline name; for museums/properties/trips it is the normalized title/location span. Reject `considering`, `comparing`, `partner`, `miles card`, and other non-event rows even if the noun matches. Fill `ordered` with the display label of each surviving entity in chronological order.

For `duration_since`, resolve a single anchor date or a dated cluster. If the question encodes a cluster such as `two charity events in a row, on consecutive days`, first run the `count` candidate extraction, sort the dated rows, detect the qualifying streak, and use the last date in the streak as the anchor. Otherwise resolve one anchor row from the phrase after `since/after/before`. Compute `question_date - anchor_date` in the requested unit and fill `value` and `unit`. If the anchor is unresolved or only session dates exist where the event date matters, leave the slot empty.

For `date_diff`, resolve both endpoints with the same anchor resolver, again preferring inline event dates over session dates. Support `between X and Y`, `how many days before X did I Y`, and `how many days after X did I Y`. If both endpoints resolve, compute the absolute or directed difference in the requested unit; stay exclusive unless the question explicitly says `inclusive` or `including`. Fill `answer` with the rendered string; otherwise leave empty.

For `derived_time`, build numeric facts first: `{kind, value, unit, label, date, source}` extracted from the normalized rows. Supported deterministic patterns should be only:
`remaining_needed`: `need to earn`, `how many points do I need`, `how much more`, where `result = target_total - current_total`;
`combined_total`: `in total`, `combined`, `altogether`, where `result = sum(operands)`;
`age_gap`: current age plus/minus years-since-event or explicit age-at-event facts;
`delta_savings`: `save by taking X instead of Y`, where `result = cost(Y) - cost(X)` only if both operands share the same route scope.
If a target total exists on-topic, prefer it over generic catalog values. If operand scopes conflict, set `operand_mismatch`.

For `abs_value`, do direct lookup only. Parse the requested attribute class: airline, person, venue, date, time, price, route endpoint, or other literal attribute. Keep only rows that mention both the object/topic and an action verb that makes the attribute real, not hypothetical. If there is exactly one scoped candidate, fill `answer` from that row. If the question implies subtraction or comparison but one side is missing or mismatched, set `operand_mismatch` instead of guessing.

## Section 2 — Whether to make an internal LLM sub-call

No.

The smallest defensible version is a pure deterministic ledger. The current misses are not failing because the model cannot sum or sort; they are failing because retrieval is surfacing the wrong rows, and because the ledger does not enforce action/scope filters. An internal sub-call would add variance, cost, and another prompt surface right where iter29/30 already showed prompt-burial regressions.

The only acceptable fallback would be a feature-flagged JSON extractor used after retrieval has already produced candidate rows, but I would not ship it in Round 2. For this round, `build_evidence_ledger` should fill slots only when the retrieved rows contain explicit grounded anchors after deterministic filtering.

## Section 3 — `late_fusion_retrieve` chunk pool

Yes: union `EVENT` and `CONCEPT`, but not as one undifferentiated top-k.

Use two reservoirs before merge: `top_event_k` from raw user/assistant event text and `top_concept_k` from concept `title + description`. Score them with the same lexical core, but apply different priors: boost user-event rows and user-grounded concept rows; penalize assistant recommendation lists, planning language, and generic explanatory concepts. Then merge, dedupe by `(grounded_in/date/normalized_text)`, and keep a mixed final pool.

The line to draw on `CONCEPT` bodies is simple: keep concept rows that encode a user action/fact with a date or a completion verb, plus typed date/quantity/name anchors. Drop concept rows that are obviously generic advice, option lists, or narrative summaries with no action predicate. This is enough to help `gpt4_7fce9456` without letting broad summaries swamp the pool.

## Section 4 — Per-failing-case fix mapping

`gpt4_f420262d`: in the Valentine ledger row filter, require an actual-flight verb or experience predicate for airline answers. `American Airlines flight from LAX to JFK` passes; `booked JetBlue` and `open to any airline` do not.

`gpt4_f420262c`: `shape="order"` should emit earliest unique airline occurrences, not most recent mentions and not flight options. With concept+event fusion, keep the earliest dated row for each airline and sort: `JetBlue`, `Delta`, `United`, `American Airlines`.

`a3838d2b`: this flips if chunk fusion surfaces all charity-event rows and the count ledger uses `event_date < anchor_date`, not session date, with explicit anchor exclusion. The required fill rule is `charity synonym + participation verb + before Run for the Cure event-date`.

`9ee3ecd6`: the derived-time ledger needs a `remaining_needed` rule. Extract `target_total=300` from the user’s goal row and `current_total=200` from the prior balance row, then return `100`, not the target total.

`09ba9854_abs`: refusal should come from a hard same-scope check. The bus and taxi numbers are to `Shinjuku Station`, while the question is about `my hotel`; one operand also comes from a generic option list, not a confirmed hotel route. Set `operand_mismatch=True` and refuse.

`gpt4_7fce9456`: this only flips if late fusion surfaces the pre-offer property-view rows. Once they are present, `shape="count"` should resolve `offer_date=2023-02-25`, exclude the Brookside townhouse itself, dedupe by normalized property label, and count the four earlier properties with their rejection reasons preserved in `candidates`.

## Section 5 — Re-smoke prediction

Honest call: I would bet on 4 of the 6 flipping, with upside to 5.

The strong four are `gpt4_f420262d`, `gpt4_f420262c`, `9ee3ecd6`, and `09ba9854_abs`. `a3838d2b` is plausible if you promote inline event-date extraction and keep a separate event reservoir. `gpt4_7fce9456` is still the riskiest one because the stored smoke context does not currently expose the four prior property rows at all; if those rows are not recoverable from raw events or grounded concept bodies, no ledger logic will save it.
