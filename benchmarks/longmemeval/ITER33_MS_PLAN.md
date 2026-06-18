# iter33-MS — failure-driven MS improvement plan (2026-06-18)

## Source studies

### COUNT/AGG failures
Important data point: most retrieval-miss cases already retrieved the **max (50 nodes)** at iter19 (the aggregation path was already firing on these — gpt4_59c863d7, 88432d0a, d23cf73b, gpt4_194be4b3, gpt4_ab202e7f, 2ce6a0f2 all at 50; the eeda8a6d/a9f6b44c/3a704032/gpt4_7fce9456 at 30). So for the cases already at 50 nodes where the item is still absent, bumping to 50 (iter31) wouldn't have helped — the off-topic session scored below the top-50 cutoff in a ~45-50 session haystack (each session yields ~25 nodes → ~1150 total nodes, retrieving 50 = top ~4%). The missing items are in lexically-dissimilar sessions (tank vs "model kits", espresso vs "kitchen items", pleco buried in a quantity sentence).

I now have all evidence needed. Let me compile the final per-qid analysis.

## COUNT/AGGREGATION FAILURE ANALYSIS — iter19 MS (12 qids)

Reference date for all relative-time = each example's `## TODAY`. Every claim below cites the qid + the exact full_context (fc) snippet that is present or absent.

### Per-qid table

| qid | GT / reader | present in fc? | root | exact miss (with fc evidence) | generalizable fix |
|---|---|---|---|---|---|
| **gpt4_59c863d7** model kits | 5 / 4 | NO — only 4 of 5 | **R** | 5th kit "1/16 scale German Tiger I tank" ABSENT from fc (grep tiger/1-16/tank = 0 hits). In haystack sess 40: *"a diorama featuring a 1/16 scale German Tiger I tank"*. fc has Revell/Spitfire/B-29/Camaro only. | Retrieval: surface lexically-dissimilar entity sessions (see consolidated R-fix). Reader undercount rule is irrelevant — item not in context. |
| **gpt4_194be4b3** instruments | 4 / 3 | NO — only 3 of 4 | **R** | 4th instrument "Fender Stratocaster electric guitar" ABSENT (grep fender/strat = 0). Haystack sess 1: *"I've had my black Fender Stratocaster electric guitar for about 5 years"*. fc has Yamaha FG800, Korg B1, Pearl drums only. | Retrieval (same R-fix). |
| **gpt4_ab202e7f** kitchen items | 5 / 4 | NO — only 4 of 5 | **R** | 5th item "coffee maker" ABSENT (only "coffee" hit is unrelated espresso-machine sentence, not retrieved as its own node). Haystack sess 43: *"I donated my old coffee maker to Goodwill"* + got espresso machine. fc has shelves/mat/faucet/toaster only. | Retrieval (same R-fix). |
| **gpt4_7fce9456** properties | 4 / 3 | NO — only 3 of 4 | **R** | 4th property "1-bedroom condo (highway noise deal-breaker)" ABSENT (grep 1-bedroom/highway/noise = 0). Haystack sess 35: *"I viewed a 1-bedroom condo on February 10th, but the noise from the highway was a deal-breaker"*. fc has Oakwood bungalow, Cedar Creek, 2-bed condo(rejected). | Retrieval (same R-fix). |
| **2ce6a0f2** art events | 4 / 3 | NO — only 3 of 4 | **R** | 4th event "guided tour at History Museum Feb 24" ABSENT (grep history museum/guided tour/feb 24 = 0). Haystack sess answer_3: *"I recently went on a guided tour at the History Museum on February 24th, and it really sparked my interest in ancient history and art"*. fc has Women-in-Art(Feb10), Art-Afternoon(Feb17), street-art lecture(Mar3). (RECALL_HINT said 15 — reader correctly ignored it; bypass=False.) | Retrieval (same R-fix). |
| **88432d0a** bake | 4 / 2 | NO — only 2 of 4 | **R** (+minor D) | 2 of 4 bakes ABSENT: "chocolate cake for sister's birthday" (grep chocolate/cake/birthday = 0; haystack sess answer_1) and "sourdough bread on Tuesday" (grep sourdough/starter = 0; haystack answer_3). fc has only baguette (line 148) + cookies (line 68). The chicken-wings/focaccia present in fc are *planned/in-progress*, correctly not counted. | Retrieval (same R-fix). Reader rule cannot recover absent bakes. |
| **a9f6b44c** bikes | 2 / 1 | NO — only 1 of 2 | **R** | 2nd bike "commuter/hybrid bike — plan to replace front tire this month before April" ABSENT (grep commuter/tire/hybrid = 0; only "tire" hit is unrelated Toyota Camry). Haystack sess answer_2: *"a new tire for my commuter bike … time to replace it this month, before April comes"*. fc has road bike (Pedal Power Mar 10) only. Note "or plan to service" — but the planned item itself isn't in context, so an include-planned reader rule can't help. | Retrieval (same R-fix). |
| **eeda8a6d** fish | 17 / 16 | NO — pleco absent | **W** | 17 = 10 neon tetras + 5 golden honey gouramis + **1 pleco catfish** + 1 betta. Reader got 16; "pleco"/"catfish" = 0 hits in fc. The session WAS processed (the W1 typed-attr pass made nodes "5 golden honey gouramis" + "10 neon tetras" from the same sentence) but the writer dropped the unquantified singular "*and a small pleco catfish*" (haystack sess 10). Writer extracted only the number-prefixed species. | Writer/consolidation: extract unquantified singular owned entities too (see W-fix). |
| **3a704032** plants | 3 / 2 | **YES — all 3 present** | **D** | All 3 in fc: peace lily + succulent "two weeks ago" (line 93), snake plant (lines 99/103). Reader excluded snake plant: *"got from my sister 'last month' (April), which falls outside the past 30 days."* GT counts all 3 under "last month". Over-strict calendar filter. | Reader temporal-window rule (see D-fix #1). |
| **d23cf73b** cuisines | 4 / 5 OVER | **YES — all present** | **D** | All 4 GT cuisines in fc: vegan lasagna (line 73), Indian tikka masala (line 83), Korean bibimbap (line 68), Ethiopian restaurant (line 153). Reader added 5th = "German (sauerkraut)". But sauerkraut was a *fermentation-workshop technique* (line 11/94), not a cuisine; GT excludes it. Over-count by mis-classifying a borderline item. | Reader dedup/classification rule (see D-fix #2). |
| **60159905** dinner parties | 3 / 9 OVER | **YES — all 3 present** | **D (symbolic)** | All 3 distinct attended parties in fc: Italian feast @Sarah's (line 11/16), potluck @Alex's (line 66), BBQ @Mike's (line 151). Reader returned **9** = the SYMBOLIC_ANSWER block (line 5-8) verbatim. **bypass_taken=True** — LLM reader was SKIPPED; the symbolic `count_among` counted 9 keyword-matched "dinner party" nodes incl. preferences ("prefers Italian cuisine"), menu plans ("plans to make Spaghetti…"), and a paraphrase of the same Sarah party ("played board games at Sarah's dinner party"). | **Symbolic-resolver fix** (NOT a reader rule — reader never ran). See D-fix #3. |
| **7024f17c** jogging+yoga | 0.5h / "0.5h jog + 6h yoga" OVER | **YES — all present** | **D** | Jog = 30 min Saturday (line 224) = 0.5h, the entire GT. Yoga = line 84-85 *"used to practice yoga three times a week, each time for 2 hours, but has been slacking off for this month"* + line 89-90 *"hoping to get back into yoga … one or two sessions a week"*. Reader summed the lapsed habit (3×2h=6h) and aspirational plan into "last week" actuals. 0 yoga actually done last week. | Reader aggregation rule: exclude habitual/aspirational durations (see D-fix #4). |

### Root-layer summary
- **RETRIEVAL (R): 7 cases** — gpt4_59c863d7, gpt4_194be4b3, gpt4_ab202e7f, gpt4_7fce9456, 2ce6a0f2, 88432d0a, a9f6b44c. The qualifying item lives in the haystack but never reached full_context (a lexically-dissimilar single session scored below the retrieval cutoff). These are NOT reader-fixable.
- **WRITER (W): 1 case** — eeda8a6d (pleco catfish dropped because unquantified/singular while its quantified sentence-mates were extracted).
- **READER (D): 4 cases** — 3a704032 (over-strict temporal exclusion), d23cf73b (over-count via borderline mis-classification), 60159905 (verbatim copy of an over-counting symbolic block — actually a *symbolic-resolver* fix since the reader is bypassed), 7024f17c (summed habitual/aspirational duration into "last week").

### Did iter31 catch these?
- **iter31 R9-A (max_nodes 20→50, char-cap 3×, rerank-pool→100)** targets the R cases. **But it would NOT have caught the 50-node R cases**: gpt4_59c863d7, gpt4_194be4b3, gpt4_ab202e7f, 2ce6a0f2, 88432d0a, d23cf73b were ALREADY retrieving 50 nodes at iter19 (aggregation path already firing) and the item was still absent — the off-topic session scores below top-50 of ~1150 nodes. Only the 30-node cases (gpt4_7fce9456, a9f6b44c) might be helped by 50, and only if the distant session ranks in 31-50. iter31's widening is necessary but **insufficient** — the real R fix is entity-aware retrieval, not a bigger flat-k.
- **iter31 MS-EXHAUSTIVE-COUNT (reader "don't stop at 2-3, count UNIQUE by name/kind, count items in descriptions")** assumes UNDERCOUNT-when-present. It helps **none** of the 7 R cases (items absent) and **none** of the 4 D cases — the D cases are *over*-counts (d23cf73b, 60159905) or *temporal/semantic exclusion* (3a704032, 7024f17c), which the rule does not address. It only fits eeda8a6d's symptom but the cause there is writer (W), so it still wouldn't fix it.
- **iter31 SYMBOLIC_ANSWER "copy verbatim" reader rule** is the direct cause-amplifier of 60159905 (and would not have fixed it; the reader is bypassed anyway).
- **ENUMERABLE OWNED ITEMS writer rule (profile rule 5)** targets eeda8a6d (W) conceptually but the pleco still wasn't extracted — the rule needs to explicitly cover *unquantified singular co-mentions* in a quantity-bearing sentence.

### Consolidated proposals

**R-fix (retrieval, 7 cases) — entity-expansion retrieval for count/own questions.** Flat top-k (even 50) cannot surface a lexically-dissimilar single session in a 45-50-session haystack. For questions detected as count/aggregation over an owned-entity *category* ("how many X have I … own/bought/serviced/baked/viewed/attended"), do a **two-stage retrieval**: (1) retrieve the category anchor as usual; (2) issue **expansion sub-queries per candidate sibling entity-type** mined from context (e.g. for "model kits": also query each model/scale token; for "kitchen items": each appliance noun; for "fish": each species/tank). Equivalently, add a **category-membership pass**: tag every concept whose body names an instance of the question's category (a model kit / a kitchen appliance / a fish / a property viewed / a bake / a serviced-or-planned bike) and force-include ALL such tagged nodes regardless of top-k score. This is generalizable (a retrieval/consolidation pass keyed on the question's count-category), not per-qid. Without it, no reader rule can count items it cannot see.

**W-fix (1 case, eeda8a6d) — extract unquantified singular owned entities.** Extend ENUMERABLE OWNED ITEMS (writer rule 5) / the typed-attribute pass: when a sentence enumerates owned entities and some carry a count ("5 gouramis", "10 tetras") while others are bare singulars ("**a** small pleco catfish", "**a** betta"), emit a concept (quantity=1) for EACH bare singular too, with the type keyword in the title (e.g. "User owns 1 pleco catfish in 20-gallon tank"). Generalizable rule wording: *"In a list of owned items, every noun phrase introduced by 'a/an/my/one' counts as quantity 1 and gets its own countable concept — do not drop unnumbered members of a quantified list."*

**D-fix #1 (3a704032) — loose-recency temporal window.** Reader rule: *"For 'in the last month / past month / recently' COUNT questions, an item the USER themselves describes with a matching loose-recency phrase ('last month', 'a few weeks ago') COUNTS, even if a literal calendar boundary would exclude it. Do not apply a strict 30-day cutoff to the user's own 'last month' phrasing."*

**D-fix #2 (d23cf73b) — count by canonical kind, exclude technique/ingredient sub-items.** Reader rule for "how many different X": *"Count UNIQUE X by canonical kind. Do NOT promote a sub-item, technique, ingredient, or single dish into a separate X (a fermentation workshop / one dish is not a cuisine). When two mentions share the same host/place/session, count them ONCE."* (The second clause also de-duplicates "board games at Sarah's" = the Sarah Italian feast, relevant to 60159905's underlying data.)

**D-fix #3 (60159905) — fix the symbolic `count_among`, do not bypass it.** Because **bypass_taken=True**, the reader never saw the context; this is a SYMBOLIC-RESOLVER bug, not a reader-prompt fix. Two generalizable changes: (a) make `count_among` **dedup by distinct event identity** (host+place+date) and **exclude non-event nodes** — preference concepts ("prefers Italian cuisine"), plan/menu concepts ("plans to make Spaghetti…"), and assistant-recommendation lists — counting only nodes with an attended/occurred verb; (b) **disable symbolic-bypass for `count_among`** (keep it as a RECALL_HINT only) so the LLM reader verifies against context — exactly the path that made 2ce6a0f2 (bypass=False) answer correctly-shaped (3, just missing the unretrieved 4th).

**D-fix #4 (7024f17c) — exclude habitual/aspirational durations from windowed sums.** Reader rule for "how many hours of X did I do last week/period": *"SUM only durations of activities the user states they ACTUALLY did within the window. EXCLUDE habitual frequencies ('I used to do X three times a week'), lapsed habits ('I've been slacking off'), and plans/intentions ('hoping to get back into X', 'planning to'). A 'used to … but stopped/getting back into' phrase contributes 0 to the window."*

**Consolidated reader-rule (for the D cases that run the reader — 3a704032, d23cf73b, 7024f17c; NOT 60159905 which bypasses):** add a COUNT/SUM DISCIPLINE block to `qa_answer`:
> *"When answering COUNT or SUM-over-a-window questions: (1) Count/sum ONLY items the user actually did/owns within the asked window; exclude plans/intentions ('planning to', 'hoping to'), lapsed/habitual frequencies ('used to … 3×/week', 'been slacking off'), preferences, and assistant suggestions. (2) Count UNIQUE entities by canonical kind; do NOT split one entity into multiple via a technique/ingredient/sub-item, and merge mentions that share the same host/place/session/date. (3) For loose-recency windows ('last month/past month'), an item the USER labels with the same loose phrase COUNTS — do not apply a strict calendar cutoff to the user's own wording. (4) Show your tally before the number."*

Note: this consolidated reader rule **cannot help the 7 R cases or the W case or 60159905** — those require the retrieval, writer, and symbolic-resolver fixes above respectively. The headline conclusion: **8 of 12 COUNT failures (7 R + 1 W) are upstream of the reader — the needed item is simply not in full_context** — so the iter31 reader-side MS-EXHAUSTIVE-COUNT rule, which assumes "undercount when present", structurally could not have fixed them, matching the observed iter31 MS regression.

All paths cited: per-qid full_context dumps at `/tmp/ms_study/fc_<qid>.txt`; iter19 records `/tmp/ms_study/iter19_hyp.jsonl`; dataset `/home/ydeng/Code/CogniFold/benchmarks/longmemeval/data/longmemeval_s_cleaned.json`; iter31 reader template `configs/longmemeval_profile.yaml` (qa_answer, lines 217-360; ENUMERABLE rule lines 149-165) and `benchmarks/longmemeval/run_eval.py` (R9-A agg-count detection lines 2255-2321; reader prompt lines 968-1000; SYMBOLIC bypass lines 2390-2446) on branch `iter30_cleanup`.

### RETRIEVAL/MULTI-HOP/AGE failures
The duration cases confirm:
- **c9f37c46** & **dcfa8644**: both anchor events ("open mic night", "Adidas purchase / shoelace break") are **ABSENT** from full_context → **RETRIEVAL miss (R)**.
- **b29f3365**: partial — "amp two weeks ago" present, but "guitar lessons" anchor **ABSENT** (only "ukulele lessons" present, a distractor). The "guitar lessons start" anchor wasn't retrieved → **RETRIEVAL miss (R)** on the bridge entity ("guitar lessons").

I now have a complete, evidence-backed picture. Let me compile the final analysis.

## Per-QID Analysis Table

| QID | Question (GT) | Bridge facts needed | In haystack? | In full_context? | Root layer | Why |
|---|---|---|---|---|---|---|
| **a1cc6108** | How old when Alex born? (**11**) | user "just turned 32" (sess `_1`, 05-24) + intern "Alex... just 21" (sess `_2`, 05-21) | YES both | **NO both** (no "Alex"/"21"/"32" in fc) | **R** | Both gold sessions absent; fc filled with 05-30 TODAY-dated skincare/social-media noise |
| **ba358f49** | Age when Rachel marries? (**33**) | "I'm 32" (sess `_2`) + "Rachel's getting married next year" (sess `_1`) | YES both | **NO both** (no "Rachel"/"married"/"32") | **R** | Neither gold session retrieved |
| **c18a7dc8** | Years older than at college grad? (**7**) | "32-year-old" (sess `_2`, 05-25) + "Berkeley... completed at age 25" (sess `_1`, 05-26) | YES both | **NO both** (no "Berkeley"/"25"/"32-year") | **R** | Neither gold session retrieved |
| **37f165cf** | Page count of 2 novels (**856**) | Nightingale 440 + 416-page novel (excl. The Power 341) | YES | **YES all three** (440, 416, 341 all in fc, dated 05-22/05-27/Dec) | **D** | Facts present; reader abstained because question said "January/March" but haystack carries no month labels — over-literal anchor + failed "two most-recent" selection |
| **87f22b4a** | Egg sales this month (**$120**) | "40 dozen" (sess `_2`, 05-22) + "$3 a dozen" (sess `_1`, 05-26) | YES both | **YES both** (TYPED_QUANTITY "40 dozen eggs" + "$3 a dozen" in fc) | **D** (+W mistag) | Both numbers present; reader refused to multiply 40×3. Writer mis-tagged "40 dozen... **in January**" (budget-template column bleed) which collided with "this month" |

### Extended group (same "I don't have a memory/record" symptom)

| QID | Question (GT) | In haystack? | In full_context? | Root layer |
|---|---|---|---|---|
| **853b0a1d** | Age when grandma gave necklace? (**18**) | "necklace... on my 18th birthday" YES | **NO** (only unrelated "college graduates") | **R** (answer literally stated, not even arithmetic) |
| **3c1045c8** | Years older than dept avg age? (**2.5**) | "avg age... 29.5" YES; age 32 YES | age **32 present**, "29.5"/"department avg" **absent** | **R** (2nd-hop miss) |
| **ec81a493** | Copies of debut album? (**500**) | "limited edition of 500 copies worldwide" YES | **YES** (verbatim "500 copies worldwide") | **D** (refused on "poster's 500" vs "album's copies" framing) |
| **c9f37c46** | How long watching stand-up at open-mic? (**2mo**) | YES | anchor "open mic" **absent** | **R** |
| **dcfa8644** | Days since Adidas buy at shoelace break? (**14**) | YES | both anchors **absent** | **R** |
| **b29f3365** | How long guitar lessons at amp buy? (**4wk**) | YES | "amp 2wk ago" present; "guitar lessons" anchor **absent** (only ukulele distractor) | **R** |

**Verdict: 8 of 11 are RETRIEVAL misses (R), 3 are READER failures (D, with 1 compounded by a Writer mistag).** The writer extracted the facts in every R case (the facts exist as nodes — the graph just didn't surface them); the dominant failure is retrieval not surfacing the bridge entity/2nd-hop fact.

---

## Root-cause mechanism (R cases — 8/11)

These are all **named-entity / second-hop questions** where the query embedding is dominated by the *interrogative frame* ("how old was I when X born", "years older than at graduation"), and the bridge entity ("Alex", "Rachel", "college/Berkeley", "necklace", "department avg", "open mic", "Adidas", "guitar lessons") is a low-frequency token that never wins a slot against the ~30 retrieved nodes — which instead fill with recency-biased TODAY-dated noise (a1cc6108's fc is 100% 2023-05-30 skincare/social-media). The needed anchors live in older sessions (05-21/05-24/05-26) and get crowded out. **The writer already extracted these as nodes; retrieval is the bottleneck.**

---

## Generalizable fixes (NOT per-qid emitters)

**FIX 1 — Bridge-entity second retrieval hop (RETRIEVAL).** Generalizes across a1cc6108, ba358f49, c18a7dc8, 853b0a1d, 3c1045c8, c9f37c46, dcfa8644, b29f3365 (8/11). When the question contains a named entity or a "when I [event]" / "than when I [event]" clause, run a *second* retrieval pass keyed on the extracted entity/event noun-phrase ("Alex", "Rachel", "college graduation", "the silver necklace", "average age of department", "open mic night", "Adidas running shoes", "guitar lessons") and force-merge its top-k into the context window. This is the single highest-leverage fix — it directly addresses every R case. Implementable as a query-side NP/NER extraction + a per-entity BM25/embedding sub-query whose top-k are union'd before assembly.

**FIX 2 — Anti-recency budget for "age/duration/comparison" questions (RETRIEVAL).** Generalizes across all R cases. These questions are NOT "current/latest" questions, yet the context is swamped by TODAY-dated nodes (a1cc6108 fc = entirely 05-30). When the question is detected as comparison/arithmetic (regex: "how old (was|am) I when", "how (many years|long) (older|had|have)", "than when I"), down-weight the recency component and reserve context slots for nodes matching the bridge entity rather than the freshest nodes.

**FIX 3 — Age/duration ARITHMETIC reader rule (READER).** Generalizes across a1cc6108, ba358f49, c18a7dc8, 3c1045c8 (and 87f22b4a's spirit). Add a reader directive: *"If the context contains a current age A (or age-at-event-E1) and a second age or date E2, and the question asks an age/duration difference, COMPUTE it (A − age_at_E2, or date arithmetic) — do NOT abstain because the answer isn't stated verbatim."* This converts "I don't have your current age and grad age" (c18a7dc8 had both 32 and would have had 25) into the subtraction. Pairs with FIX 1 (which must first deliver both anchors).

**FIX 4 — "Compute, don't refuse" anti-abstention rule for present-but-reframed facts (READER).** Generalizes across 87f22b4a, ec81a493, 37f165cf (3/11, the D cases). Reader directive: *"If the needed quantities are present but described under a different surface form (the question says 'album copies' but context says 'poster from that album: 500 copies'; question says 'this month' but the dated fact is within the current month; question says 'multiply X by Y' implicitly), use them rather than declaring 'no record'."* Specifically: (a) for 87f22b4a, multiply the two present quantities (40 dozen × $3); (b) for ec81a493, accept the entity-linked 500; (c) for 37f165cf, select the two most-recently-finished novels by completion date rather than requiring literal month words.

**FIX 5 — Writer: don't inject month labels from template/list context (WRITER, narrow but real).** Only 87f22b4a — the writer wrote "User sold 40 dozen eggs **in January**" because the conversation contained a budget template with "January/February/March" column headers; the actual statement was "this month" on 2023-05-22. Generalizable rule: when the source turn uses a relative time word ("this month", "so far", "recently"), the extracted node's date attribute should be the *session date*, never a month name lifted from surrounding boilerplate/tables. This mistag actively caused the retrieval scorer (named_day_recall) to reject the node (score 0.67, target April/May vs "January").

---

## Which fixes generalize across the group

- **FIX 1 (bridge-entity 2nd hop)** is the broadest — fixes the 8 R cases, which are the majority. This is the recommendation to prioritize.
- **FIX 2 (anti-recency for arithmetic questions)** is a complementary retrieval change that protects FIX 1's gains from being crowded out by TODAY-noise.
- **FIX 3 + FIX 4 (reader arithmetic + anti-abstention rules)** are generalizable reader-prompt rules; FIX 3 only pays off *after* FIX 1 delivers both anchors (otherwise the reader correctly lacks data). FIX 4 alone recovers the 3 D cases (87f22b4a, ec81a493, 37f165cf) without any retrieval change, since those facts are already in context.
- **FIX 5 (writer relative-time tagging)** is narrow (1 qid) but is a clean, generalizable consolidation rule, not a per-qid hack.

**Nothing here requires a per-qid emitter.** The brief's flagged anti-pattern (hardcoded per-qid emitters) is avoidable: every fix is a query-side NP/entity extraction (1), a recency-weight toggle keyed on a question-type regex (2), or a reader-prompt directive (3,4), or a writer date-assignment rule (5).

Evidence files written for reference: `/tmp/ms_study/fc_*.txt` (target full_contexts), `/tmp/ms_study/gold_*.txt` (gold-session haystack content), `/tmp/ms_study/fcx_*.txt` (6 extended-group full_contexts). Dataset: `/home/ydeng/Code/CogniFold/benchmarks/longmemeval/data/longmemeval_s_cleaned.json`.

### ABSTENTION/TEMPORAL failures
That clarifies the base-question discrepancy: 20-gallon tank has 10 neon tetras + 5 golden honey gouramis + a small pleco (= 16), PLUS betta Bubbles (1) = 17 = GT. The base reader missed the pleco (writer/reader undercount — a separate count issue, not abstention). The `_abs` "30-gallon tank" is confirmed absent. My analysis is complete. Let me compile the findings.

Research complete. Below is the full per-qid analysis and generalizable rule proposals.

---

## PER-QID TABLE (ROOT LAYER from iter19 full_context evidence)

| qid | Question (key entity/qualifier) | GT | iter19 HYP | Verdict | Should it... | What it did | ROOT LAYER |
|---|---|---|---|---|---|---|---|
| **eeda8a6d_abs** | fish in my **30-gallon tank** | "not enough — no 30-gallon tank" | "I don't have a memory of a 30-gallon tank — my notes only mention your 20-gallon tank, which contains 10 tetras, 5 gouramis, a pleco" | INCORRECT | ABSTAIN | **Abstained correctly**, but appended 20-gallon contents → judge flagged "info not in GT" | **D (over-helpful, not mis-abstain)** |
| **a96c20ee_abs** | poster for my **undergrad course research project** | "not enough — no undergrad-course poster" | "You presented that poster at Harvard University." | INCORRECT | ABSTAIN | **Answered** — matched on head-noun "poster"+"Harvard" (a *thesis* poster), ignored the *undergrad-course* qualifier | **D (true abstention failure)** |
| **09ba9854_abs** | save by **bus** vs taxi | "not enough — bus fare not mentioned (by user)" | "About $31 — $60 taxi − $29 Airport Limousine Bus" | PARTIAL | ABSTAIN (per GT) | **Answered** using an *assistant-suggested* $29 bus price, not a user-asserted fare | **D (borderline; GT itself debatable)** |
| **3c1045c8** | how much older than **dept average age** | 2.5 yrs | "Not enough — I have your age 32 but no record of dept average age" | INCORRECT | ABSTAIN given its context (the 29.5 avg is **absent** from full_context) | Refused — **correct given the context it saw** | **R (retrieval miss → forced refusal)** |
| **92a0aa75** | how long in **current role** | 1y 5m | "About 2y4m … progressed from Coordinator to Senior Specialist" | INCORRECT | ANSWER (both numbers present) | Returned 2y4m (time-to-promotion), didn't subtract: 3y9m total − 2y4m = 1y5m | **D (compositional reasoning)** |
| **73d42213** | time I **reached the clinic** Monday | 9:00 AM | "Around 7:00 AM — you left home at 7 AM" | INCORRECT | ABSTAIN or derive — but the "2 hours travel" fact is **absent** from full_context | Equated departure (7 AM) with arrival | **R (retrieval miss → forced reader error)** |

**Headline:** Only 2 of these 6 are clean reader-abstention failures (a96c20ee_abs, 09ba9854_abs). One is over-helpfulness post-correct-abstention (eeda8a6d_abs). Two are RETRIEVAL misses that *masquerade* as abstention/anchor failures (3c1045c8, 73d42213). One is compositional temporal reasoning (92a0aa75).

---

## KEY EVIDENCE SNIPPETS

- **eeda8a6d_abs** — "30-gallon" is **absent** from full_context (0 hits); only `[2023-05-27] User upgraded old 10-gallon tank … to a 20-gallon tank` and `TYPED_QUANTITY: 20-gallon`. Reader correctly said no 30-gallon; INCORRECT only for volunteering 20-gallon contents.
- **a96c20ee_abs** — full_context grounds `User presented a poster on **thesis** research at their first research conference … at **Harvard University**`. NO "undergrad course research project" anywhere. Reader matched "poster"→Harvard, ignoring the qualifier.
- **09ba9854_abs** — full_context DOES contain `[HIGH] Airport Limousine Bus costs ¥3,200 (around $29 USD) one way` — but it's an **assistant-provided option**, not a `TYPED_QUANTITY: … User stated` node (taxi $60 and train $10 ARE user-stated). GT's "you did not mention" = user never asserted a bus fare.
- **3c1045c8** — full_context has "User is 32" ×8 but **no department average age**. Raw haystack `answer_c8cc60d6_2`: "*the average age of employees in my department is 29.5 years old*" → 32−29.5 = 2.5 = GT. That answer session was **not retrieved**.
- **92a0aa75** — both `TYPED_DURATION: 2 years and 4 months — time in marketing since starting as Marketing Coordinator` and `3 years and 9 months — my experience in the company` are present. GT 1y5m = 3y9m − 2y4m (current Senior-Specialist role = total tenure minus time-as-Coordinator).
- **73d42213** — full_context has `TYPED_TIME: 7 AM — left home for doctor's appointment` but **not** the "two hours to get to the clinic" fact (entire `answer_1881e7db_2` session absent). 7 AM + 2 h = 9 AM = GT.

---

## iter31 RULE ASSESSMENT (over/under-correction)

1. **`_abs-WORKED-EXAMPLES` is NON-GENERALIZABLE.** It says "`_abs`-suffixed questions are intentionally unanswerable, refuse with the template." But I verified the `_abs` suffix is an **eval-side artifact only** (used in `run_eval.py` for `--question-ids`/resume filtering) — it is **never injected into the reader prompt**. The reader cannot see it. This rule is inert at best and a per-qid hack at worst; flag for removal. Abstention must key off the **question text vs grounding**, not the qid.

2. **`NO-REFUSAL-extended` + `TR-NEW-7` directly CONFLICT with calibrated abstention.** "NO REFUSAL when ANY relevant referent appears in context" is exactly what produced a96c20ee_abs (a "poster" referent existed → answered Harvard) and 09ba9854_abs (a "bus" $29 referent existed → answered $31). It **over-corrects toward answering** on the `_abs` class. Applied to 3c1045c8 it would be actively harmful: it would force a fabricated number when the dept-average is genuinely missing (that case needs *retrieval*, and refusal was the only safe behavior given the context).

3. **`DERIVED-TIME-WORKED` cannot fire on 73d42213** because the second operand (the "2 hours" travel time) is absent from full_context. iter31 added a reader rule for a **retrieval-gap** failure — it cannot help. Flag: this case is mislabeled in iter31 as a reader fix.

The net tension: `NO-REFUSAL-extended` (push to answer) vs `_abs-WORKED-EXAMPLES` (push to refuse) are resolved in iter31 only by the invisible qid suffix — which doesn't reach the reader — so in practice the no-refusal bias dominates and the `_abs` class stays wrong.

---

## GENERALIZABLE RULE PROPOSALS

**ABSTENTION RULE A1 — Qualifier-grounding gate (fixes a96c20ee_abs; replaces `_abs-WORKED-EXAMPLES`).**
Refuse iff the question's **specific qualifier/modifier** has no grounding node, even when the head noun is grounded. Decompose the question into (head entity, qualifier): a96c20ee = (poster, *undergrad-course-research-project*); eeda8a6d_abs = (tank, *30-gallon*). Require a node matching the **qualifier**, not just the head. Grounded qualifier ("20-gallon", "thesis") → answer; ungrounded qualifier ("30-gallon", "undergrad course project") → "not enough info, no record of [qualifier]." This distinguishes "30-gallon absent" from "20-gallon present" exactly as the prompt asks, and it is driven by question text alone (production-safe, no qid suffix).

**ABSTENTION RULE A2 — Provenance gate for "did I mention / how much will I" questions (fixes 09ba9854_abs).**
For quantity questions about the *user's* own plans/statements, only count quantities whose grounding node is **user-asserted** (the `TYPED_QUANTITY: … User stated` provenance), not assistant-suggested option lists. The $29 bus came from an assistant menu; the $60 taxi / $10 train are user-stated. Rule: "When the question is 'how much will I save by [doing X]', the cost of X must come from a user-stated figure; an assistant-listed range/estimate does not satisfy it → abstain." This is a provenance check the writer already encodes (User-stated vs assistant), so it is generalizable.

**OVER-HELPFULNESS RULE A3 — Terse abstention (fixes eeda8a6d_abs scoring).**
When abstaining, return ONLY the abstention statement + the missing entity; do NOT volunteer the *near-miss* grounded entity's contents. "No record of a 30-gallon tank." — stop. Do not append the 20-gallon roster. (eeda8a6d_abs abstained correctly but lost the point for adding info the strict judge penalizes.)

**ANCHOR RULE T1 — Duration = total tenure minus prior-role span; current-role measured from latest role transition (fixes 92a0aa75).**
For "how long in my **current** role": if context has total tenure T and a time-to-reach-current-role P (e.g., "worked up to [current title] after P"), current-role duration = T − P. Never report P (time-to-promotion) or T (total tenure) as the current-role answer. Generalizes the existing AGE-INFERENCE subtraction pattern to role tenure. The anchor is the **latest role transition**, not the earliest career event — the opposite of "measure from earliest grounding," so state it explicitly per role-scope.

**ANCHOR RULE T2 — Arrival ≠ departure; derive arrival from departure + travel time, else abstain (relevant to 73d42213 if retrieval is fixed).**
"What time did I **reach/arrive at** X" must NOT be answered with a **departure/leave-home** time. If a travel-duration fact exists, arrival = departure + travel; if it does not, abstain rather than equate the two. NB: in iter19 this case is RETRIEVAL-blocked (the "2 hours" fact wasn't retrieved), so the *primary* fix is retrieval (R); T2 is the reader guard that prevents the departure→arrival conflation once both operands are present.

**RETRIEVAL FIXES (R) — not reader rules:**
- **3c1045c8** and **73d42213** both fail because an answer-bearing session was not pulled into full_context (dept-avg-29.5 session; the "2 hours to clinic" session). These need a retrieval change (multi-hop / answer-session recall for comparison & arrival-time questions), NOT a no-refusal reader rule. A no-refusal rule here would *force hallucination*. This is the false-refuse vs over-answer tradeoff: keep refusal as the safe default whenever the **second operand of a 2-hop computation is absent**, and fix recall instead.

---

## TRADEOFF GUARDRAIL (false-refuse vs over-answer)

The two rule families pull opposite ways. To avoid regression:
- A1/A2 (push to refuse) must fire **only on a failed grounding check of the question's specific qualifier or required user-provenance** — never on mere head-noun absence and never blanket-refuse a class.
- `NO-REFUSAL-extended` should be **narrowed**: "do not refuse when the answer is *derivable* from present operands" is correct (helps 92a0aa75-style), but it must be gated by "all operands present." When an operand is missing (3c1045c8, 73d42213-in-iter19), refusal is correct and the fix belongs in retrieval. Replacing the blanket no-refusal with an **operand-completeness check** resolves the conflict without the invisible `_abs` qid hack.

Relevant artifacts: per-qid records dumped at `/tmp/ms_study/abs_recs/*.json`; iter31 prompt rules at `git show 0cc2779:configs/longmemeval_profile.yaml` (lines 269-362); dataset GT at `/home/ydeng/Code/CogniFold/benchmarks/longmemeval/data/longmemeval_s_cleaned.json`.

### Iteration history (borrow/discard)
This is decisive evidence on the per-qid emitter/ledger approach: it overshoots dedup (graduations 3→13), overrides correct resolver answers (b46e15ed 2mo→1mo), drops correct rows (parents row), and still misses GT (properties 1→2 when GT=4). The emitters are confirmed brittle and net-negative or inert.

I now have complete coverage of iter19→iter32. Let me compile the final report.

---

# ITERATION-HISTORY MINE: iter19 → iter32, MS-relevance

**Anchors (from records):** iter19 MS = **109/133 = 82.0%** (baseline, the canonical stack: gpt-5-mini reader high-effort, gpt-4o-mini writer, W1 ON / W2 OFF, AGG=15K, iter17 resolver). Every "MS effect" below is judged against that 82%. Note a critical confound flagged in `ms-iter19-restart`: a later MS-only rerun on a *swapped cheap stack* got only **100/133 = 75.2%** (`runs/ms_iter19_full133/metrics.json`) and another got 81.95% (`ms_iter19_final_metrics.json`) — i.e. **±7pp MS stochasticity from stack/model alone**, which swamps most single-technique deltas. This is the single most important caveat: most MS "effects" below are inside the noise band unless explicitly large.

## Full technique table (iter20 → iter32)

| iter | technique | what it changes | measured MS effect (cite) | verdict | why |
|---|---|---|---|---|---|
| 20 | round-to-nearest "X weeks ago"; COMPARATIVE-relax (commit one entity vs refuse); named_day object-noun rerank; latest_value prefix | TR resolver + qa_answer | TR-only 81.2%; **MS not measured** (TR-only N=133 loop) | CONDITIONAL | TR-scoped; COMPARATIVE-relax is a no-refusal precursor that later generalized to MS (see iter31 NO-REFUSAL). |
| 21 | `_DIFF_AGO_WHEN_RE` ("how many X ago did I A when I B"); named_day person/entity-class disambig | TR resolver | TR-only **83.5% (peak)**; MS not measured | CONDITIONAL (TR) | Peak TR; entity-class priority *reverted* iter22 (hurt "Valentine American"). The diff_ago_when regex + person/entity disambig kept into iter24-25. Pure TR — no MS lever. |
| 22 | age-inference rule; derived-time rule (7:00−0:15=6:45); named_day "with PERSON" bigram | qa_answer + resolver | TR-only 82.0% (−1.5 vs 21); MS not measured | BORROW (the two reader rules) | age-inference + derived-time are reader rules that **later proved MS-positive** when ported to MS COUNT/AGE in iter31 (`NO-REFUSAL-extended`, `DERIVED-TIME-WORKED-EXAMPLE`). |
| 23A | writer = gpt-4.1-mini; `--writer-reasoning-effort` flag | writer model swap | TR-only 81.2% (wash, 4 gains/5 stochastic regressions) | DISCARD | Writer-model swap is a wash on TR; the stack-swap postmortem shows model swaps move MS ±7pp unpredictably — exactly the danger zone. |
| 24 | count_among `>=`→`>` + exclude-anchor; same-session date collision fix; order_among horizon ±15-day buffer + trip-context exclusion; wider verb_pats; AGE-INFERENCE worked example | resolver (count/order) + qa_answer | folded into iter25; TR-only 83.46%; **MS not isolated** | BORROW (count_among exclude-anchor; AGE worked example) — CONDITIONAL (order_among) | `count_among` exclude-anchor is the deterministic basis for iter31 `EXHAUSTIVE-COUNT exclude-anchor` (a3838d2b). order_among was later **disabled** (iter31/32) as net-negative. |
| 25 | count_among verb-HARD skip; order_among opinion/experience filter + lowercase-title raw-turn-leak filter | resolver (count/order) | TR-only **83.46%** (seeds iter27); MS not isolated | CONDITIONAL | The order_among "opinion/experience" and "raw-turn leak" filters are anti-contamination ideas relevant to MS-window counting (60159905 dinner-party contamination), but order_among itself was later disabled. Borrow the *filters*, not the resolver. |
| 26 | (rolled into iter25 stack; not separately snapshotted) | — | not measured | — | No standalone record. |
| 27 | **gpt-5.4-mini** reader/writer/rerank; writer effort high→low; **W1 ON**; **W2 ON**; iter25 resolver; OpenAI-direct embed | model + both writer passes | **MS −4.5pp = 103/133 (77.4%)** vs iter19 82% (`runs/iter27_*/CHANGES.md` by-type table) | **W1 BORROW; W2 DISCARD; model NEUTRAL** | W2 (event_date pass) writes **noisy absolute dates** that conflict with MS session-relative ordering → −6 MS cases, only offset elsewhere by W1's +8.9pp on SSA. Net MS-negative. |
| 28a | Mastra triple-date format (creation/referenced/relative_offset) replacing W2 | writer date format | regressed: KU −27, MU −25 on partial N=133 (HISTORY iter28 entry) | DISCARD | Catastrophic — triple-date noise broke retrieval/KU. |
| 28b | priority tagging 🔴🟡🟢 + use in AGG truncation; CHRONOLOGICAL_TIMELINE block; structured_fields exposure; priority-sort in `_group_by_type` | writer tags + assembly | TR −70 on partial; all 4 sub-pieces **REVERTED** (commit 700058e "ROLLED BACK") | DISCARD | priority-sort and structured-field exposure neutral-to-harmful; reverted wholesale. The priority field is *inert* (assembly doesn't consume it). |
| 29a | +7 qa_answer rules, ~+200 lines | reader prompt bloat | **MS −27pp on N=500** (HISTORY iter29 entry) — reader over-applied rules to unrelated Qs | DISCARD | Proves the **rule-count ceiling**: beyond ~20 rules in qa_answer, MS collapses from misapplication. Codified in `references/rule-style-guide.md` (12-line/rule, ≤20 rules total). |
| 29c | trimmed rule subset | reader prompt | still **MS 57%** on partial 96/500 | DISCARD | Even trimmed, the over-rule reader stays MS-broken. |
| 30 | **W3 START_EVENT extraction** (3rd writer pass) + qa_answer worked-example compression | writer pass + reader trim | **MS 48% (−29pp vs iter27)**, TR 57% on partial 96/500 (HISTORY iter30) | **DISCARD (both)** | W3 added writer-output noise that **broke retrieval**; the compression *removed* iter02/10/13 worked examples that were actively firing (−1.5pp MS from that alone). |
| 31 | **revert to iter19 writer** (no W1/W2/W3/Reflector) + iter27 reader effort=high + iter25 resolver + TR-α topic-timeline (X1) + **12 qa_answer rules** (8 TR + 4 MS) | reader rules + resolver, writer reverted | TR-only **118/133 = 88.7% (+8.3pp vs iter27)**; **MS not full-N validated** — projection only (~82%, "confirm did not regress") | **BORROW the MS reader rules; DISCARD W1/W2/W3** | The win came from *reverting writers to iter19* + adding **reader rules**, not from any new writer pass. The 4 MS rules (below) are the proven-positive MS toolkit. |
| 32 R2 | gated **evidence-ledger** + `late_fusion_retrieve` (EVENT.content chunk fusion) + shape detector + answer_from_ledger; 4 more qa_answer rules; relative_ago re-enabled, order_among disabled | new ledger module + emitters | ledger **overshoots/overrides**: graduations 3→13, b46e15ed 2mo→1mo override of correct resolver, drops "parents" row, properties still 1→2 vs GT=4 (`CODEX_ROUND6_REGRESSION.md` table) | **DISCARD (ledger + emitters)** | The generic "shape filler" dedup heuristic mis-merges/splits entities and *overrides correct answers*. Net-negative or inert. |
| 32 R7 | **7-route temporal second-pass** + **34 per-qid emitters** (valentine_airline, order_airlines, sephora_remaining, graduation_count, property_count, ipad_refusal, art_venue, …) | per-qid hardcoded emitters | TR subset **36/43 = 83.7%** (`runs/iter32_tr_v4_R7/metrics.json`) vs projected 93-95%; emitters inert/spurious-swept to 0 fires | **DISCARD** | Emitters gate on a single qid each; on the production graph they either don't fire (retrieval doesn't surface the needed row) or wrong-fire. Honest result far below projection. **Confirmed brittle — the approach the HARD RULE forbids.** |

## Resolved questions (the prompt's explicit asks)

**Which reader rules are PROVEN MS-positive (BORROW):**
- **AGG-bump = 15K context for "how many"/"how much" aggregation Qs** — confirmed MS-positive. Default 6000-char cap "visibly regress[es] the aggregation cluster" (= MS); iter05/19/27 all ran 15K (commit 87dcb49). **This is the single highest-confidence MS lever.** BORROW.
- **`MS-EXHAUSTIVE-COUNT`** (iter31) — "dominant MS failure mode is UNDERCOUNT; scan whole context, list every X incl. description-only, show tally before final number." Directly targets the bucket-1/bucket-2 undercounts (gpt4_59c863d7 4→5, ab202e7f 4→5, 194be4b3 3→4). BORROW.
- **`NO-REFUSAL-extended`** (iter31) — extend "no refusal when any referent exists" to MS COUNT + AGE-INFERENCE. Targets the AGE_ARITH cases that iter19 *refused* (3c1045c8, c18a7dc8, ba358f49, a1cc6108 all "HY refused"). BORROW.
- **`_abs`-WORKED-EXAMPLES + ATTRIBUTE-MISMATCH REFUSAL + SAME-SCOPE-DIFFERENCE + ZERO-IN-WINDOW** (iter31/32 reader rules) — the refusal-discipline bucket (SCOPE_REFUSAL): eeda8a6d_abs, a96c20ee_abs, 09ba9854_abs, 80ec1f4f_abs. These are *prompt-only* generalizations of what the emitters tried to hardcode. BORROW (note the rule-count ceiling — keep total ≤20).
- **`EXPLICIT-TIME OVER INFERENCE`** (73d42213) and **`CURRENT vs EVER`** (92a0aa75) and **window-not-routine** (7024f17c) — three rule-level MS fixes the failure-analysis rated "High/Medium-high confidence, rule-only." BORROW.
- **DERIVED-TIME** and **AGE-INFERENCE** worked examples (iter22→iter31) — BORROW (proven by reuse).

**Which writer passes help vs hurt MS:**
- **W1 (typed-attribute pass)**: SSA +8.9pp, **MS roughly neutral** at the iter19/27 level. Keep ON (it's in the iter19 82% baseline). BORROW/keep.
- **W2 (event_date resolution)**: **MS −4.5pp** (iter27). Noisy absolute dates fight MS session-relative ordering. **DISCARD for MS** (keep behind flag for narrow TR only).
- **W3 (START_EVENT extraction)**: **MS −29pp** (iter30). Writer-output noise broke retrieval. **DISCARD.**

**Does AGG-bump help MS aggregation:** **YES — confirmed.** It is the validated-stack default precisely because the aggregation/MS cluster regresses without it.

**Per-qid emitters (iter32):** **DISCARD — confirmed brittle and net-negative/inert.** Evidence: ledger overshoots dedup (graduations 3→13), overrides correct resolver answers (b46e15ed), drops correct rows, still misses GT (properties→2 vs 4); R7's 34 emitters yielded 36/43 (83.7%) vs a 93-95% projection; spurious-fire sweep forced them to gate so narrowly they don't fire on the real graph. This is the exact failure mode the HARD RULE forbids.

## Proven MS toolkit (BORROW)
1. **AGG_MAX_CONTEXT_CHARS=15000** for aggregation Qs (highest-confidence MS lever).
2. **iter19 writer stack** (W1 ON, **W2/W3 OFF**) — the only writer config that held MS at 82%.
3. Reader rules (generalizable, prompt-only): **MS-EXHAUSTIVE-COUNT** (anti-undercount + tally), **NO-REFUSAL-extended** (compute for COUNT/AGE), **DERIVED-TIME**, **AGE-INFERENCE**, **EXPLICIT-TIME-OVER-INFERENCE**, **CURRENT-vs-EVER**, **window-not-routine**, and the refusal-discipline quartet **(_abs worked-example, ATTRIBUTE-MISMATCH, SAME-SCOPE-DIFFERENCE, ZERO-IN-WINDOW)** — subject to the **≤20-rules / ≤12-lines-per-rule ceiling** (iter29 proved exceeding it costs MS −27pp).
4. **count_among exclude-anchor** + **order_among contamination filters** (opinion/experience/raw-turn-leak) — as deterministic backstops, not as bypassing resolvers.
5. **First, reproduce 82% MS on the exact target stack before optimizing** (matches the user's locked memory) — stack swaps alone move MS ±7pp.

## MS dead-ends (DISCARD)
- **W2 event_date pass** (MS −4.5) and **W3 START extraction** (MS −29) — writer date/start noise vs session-relative ordering.
- **28a triple-date format** (KU/MU −25/−27) and **28b priority tagging/sort + structured-field exposure** (reverted, inert).
- **qa_answer rule bloat** (iter29a +200 lines → MS −27; iter29c → MS 57) — over-ruling makes the reader misapply rules.
- **qa_answer worked-example compression** (iter30, removing iter02/10/13 examples → MS −1.5 from that alone).
- **The evidence ledger / `late_fusion_retrieve` generic shape-filler** (iter32 R2) — mis-dedups, overrides correct answers.
- **The 34 per-qid emitters** (iter32 R7) — brittle, inert on the real graph, projection 93-95% → actual 83.7%. The canonical "what not to do."
- **Cheap-stack / writer-model swaps** (iter23A; the 82%→75% regression) — silent MS loss inside the noise band.

**Sources:** `git show longmemeval-iter:benchmarks/longmemeval/HISTORY.md` (iter00-19); `git show tr-only-optimization:.../HISTORY.md` lines 341-520 (iter20-31 backfill); commit messages e45e245 (iter20-23A), 700058e (iter24-25/27), 413118d (iter31 TR), 7e76e33 + cf4b494 (iter32); `runs/iter27_gpt54mini_full_n500_W1W2/CHANGES.md`; `misc/hello:configs/longmemeval_profile.yaml` lines 305-490 (iter31/32 reader rules); `ms-iter19-restart:MS_ITER19_FAILURE_ANALYSIS.md` (24-case / 6-bucket MS root-cause map); `runs/ms_iter19_full133/metrics.json` (75.2% stack-swap), `runs/ms_iter19_final_metrics.json` (81.95%); `misc/hello:CODEX_ROUND6_REGRESSION.md` (ledger/emitter regression table); `runs/iter32_tr_v4_R7/metrics.json` (83.7% vs 93-95% projection).

## SYNTHESIS PLAN
I have full confirmation of every load-bearing claim:
- AGG-count detection is a flat `max_nodes=50` widen with no per-entity expansion hop (confirms the COUNT study's "insufficient at 50" finding).
- `_qa_agg_count_tr` suppresses agg-widen on `ago/since/between/before/after` — which is exactly why the AGE/duration bridge cases (a1cc6108, ba358f49, c18a7dc8) get NO widening and stay retrieval-starved.
- `should_bypass` gates on `symbolic_result.get("bypass", True)` — `count_among` returns bypass=True → caused 60159905. Disabling bypass for `count_among` is a one-flag change.

I have everything. Producing the final plan.

---

# iter33-MS: Failure-Driven, Generalizable MS Improvement Plan

Baseline = **iter19 MS 109/133 = 82.0%** (canonical stack: gpt-5-mini reader high-effort, gpt-4o-mini writer, W1 ON / W2 OFF, AGG=15K, iter17 resolver). **Variance ceiling: ±7pp from stack/model alone** (`ms_iter19_full133` = 75.2%, `ms_iter19_final` = 81.95% — same config, different runs). Honest interpretation: any single fix worth <2 cases (<1.5pp) is inside the noise band. The plan therefore targets **clusters**, not individual qids.

---

## 1. MS Failure Taxonomy (iter19's 24 failures)

The 24 failures decompose into **two question families** (12 COUNT/AGG + 12 RETRIEVAL/AGE/ABSTENTION). Root-layer split:

| Root layer | Count | qids | Reader-fixable? |
|---|---|---|---|
| **RETRIEVAL (R)** | **15** | gpt4_59c863d7, gpt4_194be4b3, gpt4_ab202e7f, gpt4_7fce9456, 2ce6a0f2, 88432d0a, a9f6b44c, a1cc6108, ba358f49, c18a7dc8, 853b0a1d, 3c1045c8, c9f37c46, dcfa8644, b29f3365 | **NO** — item absent from full_context |
| **WRITER (W)** | **1** | eeda8a6d (pleco dropped) | NO — needs extraction fix |
| **READER (D)** | **8** | 3a704032, d23cf73b, 60159905\*, 7024f17c, 37f165cf, 87f22b4a\*\*, ec81a493, 92a0aa75, a96c20ee_abs, 09ba9854_abs, eeda8a6d_abs, 73d42213\*\* | YES (mostly) |

\* 60159905 is **symbolic-resolver bypass**, not reader-prompt (reader never ran).
\*\* 87f22b4a has a compounding W mistag ("in January"); 73d42213 is actually **R** (the "2 hours travel" operand is absent) — listed under D-symptom but root is R. Net: counting 73d42213 as R gives **R=15, the dominant class.**

**Headline: 15 of 24 (62.5%) are RETRIEVAL misses — the needed fact is in the haystack as a written node but never reached full_context.** The iter31 reader-side push (MS-EXHAUSTIVE-COUNT, NO-REFUSAL-extended) *structurally cannot* fix these and, on R cases where the operand is genuinely missing (3c1045c8, 73d42213), NO-REFUSAL **forces hallucination** — this is why iter31 regressed MS. **Retrieval is the highest-leverage lever, not the reader.**

---

## 2. The Fix Plan (ordered by expected MS cases recovered / effort)

### TIER 1 — RETRIEVAL: bridge-entity / category-expansion second hop  (targets 15 R cases)

This is the single highest-leverage change. Two sub-mechanisms share one implementation (query-side NP/entity extraction → per-entity sub-query → union before assembly).

**FIX R1 — Bridge-entity second retrieval hop.** When the question contains a named entity or a `when I [event]` / `than when I [event]` clause, extract the bridge noun-phrase(s) and run a *second* BM25+embedding sub-query keyed on each; force-union its top-k into the context window before reranking.
- **Flips (8):** a1cc6108 ("Alex"), ba358f49 ("Rachel"), c18a7dc8 ("Berkeley/college grad"), 853b0a1d ("necklace"), 3c1045c8 ("department average age"), c9f37c46 ("open mic"), dcfa8644 ("Adidas"), b29f3365 ("guitar lessons" — must beat the "ukulele" distractor).
- **Net delta:** +4 to +6 cases (some bridge sessions may still not rank; b29f3365 needs the sub-query to disambiguate guitar vs ukulele).

**FIX R2 — Category-membership force-include for COUNT-over-owned-category Qs.** Flat top-50 cannot surface a lexically-dissimilar single session in a ~1150-node / ~48-session haystack (top-50 = top ~4%). For questions detected as count/own over a category, tag every concept whose body names an *instance* of the category (a model kit / kitchen appliance / fish / property viewed / bake / serviced bike) and force-include ALL tagged nodes regardless of rerank score. Implement as expansion sub-queries per candidate sibling entity-type mined from the anchor sessions.
- **Flips (7):** gpt4_59c863d7 (Tiger tank), gpt4_194be4b3 (Fender Strat), gpt4_ab202e7f (coffee maker), gpt4_7fce9456 (1-bed condo), 2ce6a0f2 (History Museum tour), 88432d0a (chocolate cake + sourdough), a9f6b44c (commuter bike).
- **Net delta:** +3 to +5 (the 50-node cases were ALREADY at 50 and missed — a bigger flat-k does nothing; only entity-aware force-include helps).

**FIX R3 — Anti-recency budget for arithmetic/comparison Qs (companion to R1/R2).** The agg-count regex currently *suppresses* widening on `ago|since|between|before|after` (`_qa_agg_count_tr`, run_eval.py:2295) — exactly the AGE/duration cases — so they get NO retrieval help and the window fills with TODAY-dated noise (a1cc6108 fc = 100% 2023-05-30). Fix: detect `how old (was/am) I when | how (many years|long) (older|had) | than when I` and **down-weight the recency component**, reserving slots for bridge-entity matches. Critically, **do NOT suppress widening for these** — remove the over-broad `since/before/after` suppression for age/comparison Qs.
- **Protects** R1's gains on a1cc6108, ba358f49, c18a7dc8, 73d42213 from recency crowd-out.

> **Regression risk (Tier 1):** Force-include + union can inject off-topic nodes on non-count Qs → must gate strictly on question-type detection (already have `_qa_agg_count`/bridge regex). Anti-recency must NOT fire on "current/latest" Qs (KU/SSU) — gate on the arithmetic regex only. Net Tier-1 expected: **+7 to +11 cases**, the bulk of the headroom.

### TIER 2 — READER PROMPT: COUNT/SUM discipline + calibrated abstention  (targets 7 D cases)

All subject to the **≤20-rules / ≤12-lines-per-rule ceiling** (iter29 proved exceeding it = MS −27pp). Net rule budget: **replace, don't add.** Borrow the proven ones, swap out the broken `_abs` hack.

**FIX D-CONSOLIDATED — single COUNT/SUM DISCIPLINE block** (NEW wording, replaces nothing but compresses MS-EXHAUSTIVE-COUNT's over-broad "always undercount" framing):
> *"When answering COUNT or SUM-over-a-window questions: (1) Count/sum ONLY items the user actually did/owns within the asked window; EXCLUDE plans ('planning to', 'hoping to'), lapsed/habitual frequencies ('used to … 3×/week', 'been slacking off'), preferences, and assistant suggestions. (2) Count UNIQUE entities by canonical kind; do NOT split one entity via a technique/ingredient/sub-item (a fermentation workshop is not a cuisine), and MERGE mentions sharing the same host/place/session/date. (3) For loose-recency windows ('last month/past month'), an item the USER labels with the same loose phrase COUNTS — do not apply a strict calendar cutoff to the user's own wording. (4) Show your tally before the number."*
- **Flips (4):** 3a704032 (clause 3: snake plant "last month" counts → 2→3), d23cf73b (clause 2: sauerkraut technique excluded → 5→4), 7024f17c (clause 1: lapsed/aspirational yoga excluded → keep 0.5h), and de-dups 60159905's data (but see S1 — reader bypassed there).
- **Borrow status:** iter31's MS-EXHAUSTIVE-COUNT (profile:311) and window-not-routine exist; this **merges + narrows** them (the existing one assumes undercount-when-present, which fits NONE of these D cases). Net rule count: neutral.

**FIX D-COMPUTE — "compute, don't refuse" for present-but-reframed facts** (BORROW iter31 NO-REFUSAL-extended, but **gate on operand-completeness**):
> *"If the needed quantities are present (possibly under a different surface form — 'album copies' vs 'poster: 500 copies'; 'this month' vs a dated fact within the current month; an implicit multiply), USE them rather than declaring 'no record'. COMPUTE age/duration/product when both operands are present. But if a required operand is ABSENT, abstain — do not fabricate."*
- **Flips (3):** 87f22b4a (multiply 40 dozen × $3 = $120), ec81a493 (accept entity-linked 500), 37f165cf (select two most-recently-finished novels by date, not literal month words).
- **Critical gate:** the operand-completeness clause is what prevents the iter31 NO-REFUSAL regression on 3c1045c8/73d42213 (where the 2nd operand is genuinely absent → refusal is correct until R1 delivers it).

**FIX A1 — Qualifier-grounding abstention gate** (NEW; **replaces the inert/leaky `_abs-WORKED-EXAMPLES`** at profile:280):
> *"Decompose the question into (head entity, qualifier). Refuse iff the SPECIFIC qualifier has no grounding node, even when the head noun is grounded. '30-gallon tank' ungrounded while '20-gallon' present → 'No record of a 30-gallon tank.' STOP — do not volunteer the near-miss entity's contents."*
- **Flips (2-3):** a96c20ee_abs (undergrad-course qualifier ungrounded → abstain), eeda8a6d_abs (terse abstention, drop the 20-gallon roster the judge penalizes). Borderline: 09ba9854_abs (provenance, see A2).
- **Why replace `_abs`:** the `_abs` suffix is an eval-side artifact **never injected into the reader prompt** (confirmed: profile:280 keys on `QID ending in _abs` but the reader never sees the qid) — it is inert at best, a per-qid hack at worst. Removing it also kills the conflict where NO-REFUSAL silently dominates the `_abs` class.

**FIX A2 — Provenance gate** (NEW, narrow): *"For 'how much will I save by [X]' Qs, the cost of X must be USER-stated (TYPED_QUANTITY … User stated), not an assistant-suggested option."* Flips 09ba9854_abs.

**FIX T1 — current-role tenure** (NEW): *"'How long in my CURRENT role' = total tenure − time-to-reach-current-role. Never report time-to-promotion or total tenure."* Flips 92a0aa75 (3y9m − 2y4m = 1y5m).

> **Regression risk (Tier 2):** The COUNT-discipline "exclude planned/habitual" clause directly **conflicts** with any include-planned instinct — but the studies confirm GT never counts planned/habitual items in these windows, so it's safe. The biggest risk is the **exhaustive-count vs overcount tradeoff**: iter31's "don't stop, count everything in descriptions" caused d23cf73b's overcount (sauerkraut). The consolidated rule's clause-2 (canonical-kind dedup) is the explicit countermeasure. **Operand-completeness gating** on D-COMPUTE is the countermeasure for the no-refusal-vs-false-answer tradeoff. Net Tier-2 expected: **+3 to +5 cases**, but ~−1 to −2 risk from over-application → realistic net **+2 to +4**.

### TIER 3 — WRITER + SYMBOLIC (targets 1 W + 1 symbolic case)

**FIX W1 — extract unquantified singular owned entities** (extend ENUMERABLE rule, profile:149): *"In a list of owned items, every noun phrase introduced by 'a/an/my/one' counts as quantity 1 and gets its own countable concept — do not drop unnumbered members of a quantified list."* Flips eeda8a6d (pleco → fish 16→17).

**FIX S1 — disable symbolic bypass for `count_among`** (one-line change at run_eval.py:2441): make `count_among` return `bypass=False` (RECALL_HINT only) so the LLM reader verifies against context; AND make `count_among` dedup by distinct event identity (host+place+date) and exclude preference/plan/recommendation nodes. Flips 60159905 (9 → 3). This is the documented iter32-emitter-free fix.

**FIX W2-narrow — relative-time tagging** (NEW, narrow): when a turn uses "this month/so far/recently", the node's date = session date, never a month name lifted from surrounding tables/boilerplate. Fixes 87f22b4a's "in January" mistag (also unblocks its retrieval, score 0.67→pass).

> **Regression risk (Tier 3):** W1 could over-emit on long item lists → cap at quantity-bearing-sentence members only. S1's bypass-disable adds 1 LLM reader call per count_among Q (cost-neutral, ~$0). Net Tier-3 expected: **+2 cases**.

---

## 3. Borrow / Discard from History

### BORROW (proven MS toolkit)
| Item | Evidence | Status in iter33 |
|---|---|---|
| **iter19 writer stack (W1 ON, W2/W3 OFF)** | only config holding MS at 82% | **KEEP — the foundation** |
| **AGG_MAX_CONTEXT_CHARS=15000** | highest-confidence MS lever; default 6K "visibly regresses aggregation cluster" (commit 87dcb49) | **KEEP** |
| **AGE-INFERENCE + DERIVED-TIME worked examples** (profile:258, 263) | proven by reuse iter22→31 | **KEEP** |
| **count_among exclude-anchor** (iter24, a3838d2b) | deterministic backstop | **KEEP** |
| **order_among contamination filters** (opinion/experience/raw-turn-leak, iter25) | anti-contamination, relevant to 60159905 | **BORROW the filters** (not the resolver) |
| **NO-REFUSAL** | helps 92a0aa75-style compute | **BORROW but gate on operand-completeness** |

### DISCARD (dead-ends, with evidence)
| Item | Evidence | Why |
|---|---|---|
| **W2 event_date pass** | MS −4.5pp (iter27) | noisy absolute dates fight session-relative ordering |
| **W3 START_EVENT extraction** | MS −29pp (iter30) | writer noise broke retrieval |
| **28a triple-date / 28b priority tags** | KU/MU −25/−27; reverted (700058e) | inert/harmful |
| **qa_answer rule bloat** | iter29a +200 lines → MS −27pp; iter29c → 57% | rule-count ceiling (≤20 rules / ≤12 lines) |
| **worked-example compression** | iter30 → −1.5pp MS | removes firing examples |
| **evidence ledger / late_fusion** | iter32 R2: graduations 3→13, overrides correct answers | generic shape-filler mis-dedups |
| **34 per-qid emitters** | iter32 R7: 83.7% actual vs 93-95% projected; inert on real graph | **the canonical "what not to do" — HARD RULE forbids** |
| **`_abs`-WORKED-EXAMPLES rule** | keys on qid suffix never seen by reader (profile:280) | inert/leaky per-qid hack → replace with A1 |
| **cheap-stack / writer-model swaps** | 82%→75% silent regression | inside noise band, unpredictable |

---

## 4. Recommended Stack: iter33-MS

**Exact configuration:**
```
Writer:    iter19 pipeline — W1 ON, W2 OFF, W3 OFF, no Reflector  (UNCHANGED foundation)
Reader:    gpt-5-mini, effort=high
Resolver:  iter17/25 base + count_among exclude-anchor + count_among bypass=FALSE (S1)
           + order_among contamination filters
AGG:       AGG_MAX_CONTEXT_CHARS=15000 (unchanged)
```
**Plus, in priority order:**
1. **Retrieval (R1+R2+R3)** — bridge-entity 2nd hop + category-membership force-include + anti-recency for arithmetic Qs; remove the `since/before/after` agg-suppression for age/comparison Qs. *[highest leverage]*
2. **Reader (replace, stay ≤20 rules):** swap `_abs-WORKED-EXAMPLES` → **A1 qualifier-grounding gate**; merge MS-EXHAUSTIVE-COUNT + window-not-routine → **D-CONSOLIDATED COUNT/SUM discipline**; gate NO-REFUSAL → **D-COMPUTE with operand-completeness**; add **A2** (provenance), **T1** (current-role).
3. **Writer (W1-singular + W2-narrow):** extract unquantified singulars; relative-time → session date.

**Projected MS (honest):**
| Component | Cases recoverable | Realistic net (after risk) |
|---|---|---|
| Tier 1 retrieval (15 R) | up to +11 | **+6 to +9** |
| Tier 2 reader (7 D) | up to +5 | **+2 to +4** |
| Tier 3 writer/symbolic (2) | +2 | **+1 to +2** |
| **Raw sum** | | **+9 to +15** |
| **Less reader stochasticity (±5/133)** | | |

**Projected MS range: 116–122 / 133 ≈ 87–92%**, central estimate **~118/133 ≈ 88.7%** (+6.7pp over 82% baseline). **Honest floor: given ±7pp stack variance and ~−2 rule-misapplication risk, a single run could land as low as ~84% or as high as ~92%.** The retrieval tier carries the claim; if R1/R2 underperform (bridge sessions still don't rank), fall back to **~85% (+3pp)** from reader+writer alone, which is still materially above baseline and inside-noise-positive only at 2× confirmation.

**Cheapest validation:**
- **MS-133 strict, ~$4.8/run.** Run **2× minimum** (variance ≥ most single-fix deltas) — budget **~$9.6**. Lock the exact target stack first (per your memory rule: reproduce 82% before optimizing) — if the baseline rerun lands ≠82±2, fix the stack before reading any iter33 delta.
- **Ablation order if budget allows (1 extra run, ~$4.8):** retrieval-only vs retrieval+reader, to attribute the delta and avoid shipping a reader change that's actually noise.
- **Decision gate:** ship iter33 only if **both** MS-133 runs clear **≥114/133 (85.7%)** AND the mean of the two ≥ **86%** — i.e. the gain must survive variance, not ride it.

---

## 5. What is NOT Worth Doing

| Not worth doing | Why (evidence) |
|---|---|
| **Bumping flat max_nodes beyond 50** (iter31 R9-A direction) | 6 of 7 count-R cases were ALREADY at 50 and still missed — the off-topic session scores below top-4% of ~1150 nodes. Bigger flat-k is necessary-but-insufficient; only **entity-aware force-include** (R2) helps. |
| **Reader-side MS-EXHAUSTIVE-COUNT as the primary count fix** | assumes undercount-when-present; fits NONE of the 7 R count cases (item absent) and NONE of the 4 D cases (which are *over*-counts or temporal exclusion). Matches the observed iter31 MS regression. |
| **Blanket NO-REFUSAL on COUNT/AGE** | forces hallucination on 3c1045c8 / 73d42213 where the 2nd operand is genuinely absent. Must gate on operand-completeness. |
| **Keeping `_abs`-WORKED-EXAMPLES** | keys on a qid suffix the reader never sees — inert per-qid hack; replace with A1. |
| **Any per-qid emitter / evidence-ledger / late-fusion shape-filler** | iter32 R7 emitters: 83.7% actual vs 93-95% projected, inert on real graph; ledger overshoots dedup (3→13) and overrides correct answers. **HARD RULE forbidden.** |
| **W2/W3 writer passes, triple-date, priority tagging** | MS −4.5 / −29 / reverted. Writer date/start noise vs session-relative ordering. |
| **Adding rules past ~20 total** | iter29 = MS −27pp from misapplication. iter33 must **replace** (`_abs`→A1, EXHAUSTIVE+routine→D-CONSOLIDATED), not append. |
| **Cheap-stack / writer-model swaps to save cost** | 82%→75% silent regression inside the ±7pp noise band. |
| **Chasing 60159905 via a reader rule** | reader is BYPASSED there; only the symbolic `count_among` bypass-disable (S1) reaches it. |

**Bottom line:** the iter19 baseline was strong *because* it was never reader-over-tuned. The win is **retrofit retrieval (entity-aware 2nd hop, the 62.5%-of-failures lever), surgically replace 2 reader rules (not add), and 2 small writer/symbolic fixes** — projected **~88.7% MS (range 85–92%)**, validated at 2×MS-133 (~$9.6), shipped only if both runs clear 85.7% and survive the variance gate.
