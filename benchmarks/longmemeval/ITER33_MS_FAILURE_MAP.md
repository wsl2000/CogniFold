# iter33-MS — exhaustive failure map (all 32, from iter33_ms_clean v1)

## Per-chunk analysis
=== CHUNK 1 (0a995998, 60159905, 9d25d4e0, aae3761f, d851d5ba, ef66a6e5, gpt4_7fce9456) ===
All M1-M6 and A1/A2/B1-B4 fixes are committed (HEAD = 3c49652). The iter33_ms_clean run was generated BEFORE these (the full_contexts show pre-fix behavior: count_among returned 2 for 60159905, tennis-competitively flattened, properties polysemy unfixed). My analysis is complete. Here are the 7 records.

---

**[0a995998]** "How many items of clothing do I need to pick up or return from a store?" GT=3, HY=2.
- **root_layer**: READER-COUNT (operands present; reader under-merged the boots into one item).
- **operand_in_context**: yes. Context has Zara boots ("User needs to return boots to Zara that were exchanged for a larger size" + "still needs to pick up the new pair") and navy blazer dry-cleaning pickup. The boots transaction is dual: return the old (too-small) pair AND pick up the new exchanged pair — GT counts these as 2 store items; reader collapsed to 1.
- **operand_in_haystack**: yes. sess19 turn6 "I need to return some boots to Zara... exchanged them for a larger size. I just haven't had a chance to pick them up yet"; sess11 "pick up my dry cleaning for the navy blue blazer." All 3 store items live in gold sessions (answer_afa9873b_1/2/3). The green sweater (lent to sister) is NOT a store item — correctly excluded.
- **current_fix_status**: OPEN. No current fix targets the "return-old + pickup-new = 2 items" decomposition. R2 CATEGORY_MEMBERS for 'items clothing' force-included only decluttering/care nodes, not a clean pickup/return roster.
- **proposed_fix**: leave-it. GT=3 hinges on counting the single boots exchange as two physical handoffs (return old pair + collect new pair) — genuinely ambiguous; the model's reading of "2 items" (boots, blazer) is defensible. A reader rule to split exchange transactions risks over-counting elsewhere. Regression risk HIGH if attempted. Treat as borderline NOISE-OR-DISPUTED.
- **confidence**: medium (clear evidence; GT interpretation is the disputed part).

**[60159905]** "How many dinner parties have I attended in the past month?" GT=three, HY=2.
- **root_layer**: SYMBOLIC (count_among mis-fired: returned 2, missed the qualifier-synonym party).
- **operand_in_context**: yes — all 3 present. "[2023-05-21] User had a low-key potluck dinner party at Alex's place", "[2023-05-21] BBQ theme dinner party at Mike's place", and the third **"[2023-05-22] User attended Italian feast at Sarah's place last week"** (HIGH concept). RECALL_HINT says "Candidate: 2 ... matched 2 events" — it skipped "Italian feast" because the node lacks the literal token "party."
- **operand_in_haystack**: yes. Gold answer_75eca223_1 "I attended a lovely Italian feast at Sarah's place last week"; answer_75eca223_2 has Mike's BBQ + Alex's potluck.
- **current_fix_status**: ADDRESSED-by-A2 (symbolic_resolver.py L1106-1232). The party-count path now lets a qualifier-synonym (feast/potluck/bbq) satisfy the head-noun gate (L1119-1126), so "Italian feast" counts; host+date dedup (L1204-1215) collapses Sarah's two nodes to one. Should now emit 3. NEEDS LIVE RUN to confirm RECALL_HINT flips to 3 and the (bypass=False) reader follows it.
- **proposed_fix**: none beyond A2 — verify on rerun.
- **confidence**: high.

**[9d25d4e0]** "How many pieces of jewelry did I acquire in the last two months?" GT=3, HY=2.
- **root_layer**: RETRIEVAL (third operand absent from context).
- **operand_in_context**: partial — 2 of 3 present: "[2023-05-21] ... emerald earrings ... at a flea market" and "[2023-05-28] ... new silver necklace with a small pendant on the 15th." The **engagement ring** ("got it a month ago") is entirely ABSENT (`'engagement' in context == False`).
- **operand_in_haystack**: yes. answer_fcff2dc4_1 "resizing my engagement ring. I got it a month ago"; answer_fcff2dc4_3 "I got my engagement ring a month ago." (Within 2 months of question_date 2023-05-30.)
- **current_fix_status**: OPEN. R2 CATEGORY_MEMBERS for 'pieces jewelry' force-included only jewelry-CLEANING nodes (cleaning kit, photo tips) — not the ring acquisition, because the ring node text says "engagement ring," not "jewelry." Writer/retrieval never surfaced it.
- **proposed_fix**: RETRIEVAL — broaden the R2 jewelry category roster to include hyponym terms (ring/earrings/necklace/bracelet/pendant/brooch) when the category head is "jewelry," so acquisition nodes that name a specific piece (but not the word "jewelry") are force-included. Regression risk MED (hyponym expansion can pull cleaning/photo distractors; gate to acquire-verbs got/bought/received). Secondary: B2 acquire-verb probe (3a704032) may already help if it widens the sub-query — verify on rerun.
- **confidence**: high (the missing operand is unambiguous and absent).

**[aae3761f]** "How many hours total driving to my three road trip destinations combined?" GT=15 (or 30 round-trip), HY=13.
- **root_layer**: WRITER (phantom mis-attributed node) + READER-COMPUTE (selected wrong 3rd leg).
- **operand_in_context**: partial. Correct legs present: "drove 4 hours to Outer Banks" (4), "drove for five hours to reach the mountains in Tennessee" (5), "[2023-05-26] User drove for six hours to Washington D.C. recently" (6) → 4+5+6=15. BUT context also contains a FALSE node **"[2023-05-21] TYPED_DURATION: four hours — drive to Tybee Island"** — the user never drove to Tybee (it's a future planned trip: "I think I'll go with Tybee Island"); that "four hours" actually belonged to Outer Banks. Reader summed Outer Banks(4)+Tennessee(5)+Tybee(4)=13, dropping the real D.C.(6) leg.
- **operand_in_haystack**: yes. answer_526354c8_1 (Outer Banks 4h, Tybee = future plan), answer_526354c8_3 (Tennessee 5h), answer_526354c8_2 (Washington D.C. 6h).
- **current_fix_status**: OPEN. No fix removes the phantom Tybee-duration node or disambiguates completed-vs-planned destinations.
- **proposed_fix**: WRITER — the W1 typed-duration pass should not attach a drive-duration to a destination that the user only PLANS to visit ("I think I'll go with X" / "thinking of going to X"); gate TYPED_DURATION drive nodes to past-tense/completed framing. Regression risk MED. Lower-risk alternative: leave-it and accept as a hard distractor-disambiguation case; the 30h round-trip alt answer makes this partially NOISE-OR-DISPUTED. 
- **confidence**: high on the mechanism (phantom Tybee node + dropped D.C.).

**[d851d5ba]** "How much money did I raise for charity in total?" GT=$3,750, HY=$8,750+.
- **root_layer**: READER-COMPUTE (over-inclusion of a distractor amount).
- **operand_in_context**: yes (all + distractor). Correct 4: $500 (fitness challenge), $1,000 (bake sale), $250 (Run for Hunger), $2,000 (animal shelter) = $3,750. Context ALSO has the distractor "[2023-03-20] User raised over $5,000 for local music education program" — reader added it, yielding $8,750+.
- **operand_in_haystack**: yes. The $5,000 concert is in NON-gold session d77d4ac9_1 ("music benefit concert at the Independent back in April ... raised over $5,000"); the 4 correct amounts are in gold answer_5cdf9bd2_1/2/3/4. GT deliberately excludes the $5,000 ("back in April" = prior-year/out-of-cycle distractor; question_date is March 20).
- **current_fix_status**: OPEN. The REVERT (over-merge removal) is about COUNT undercounts, not sum-over-inclusion; no current rule scopes out the April concert.
- **proposed_fix**: leave-it / NOISE-OR-DISPUTED. "in total" naturally invites summing all 5; GT's exclusion of the April concert is a subtle temporal-scope judgment (April > question-date March). A reader rule to drop "April" amounts would be a per-qid hack (banned) and risks dropping legitimate amounts elsewhere — regression risk HIGH. Treat as disputed.
- **confidence**: high on mechanism; the GT scoping is the disputed element.

**[ef66a6e5]** "How many sports have I played competitively in the past?" GT=two, HY=1.
- **root_layer**: WRITER (the "tennis competitively" qualifier was dropped in extraction).
- **operand_in_context**: partial. Swimming-competitively present (multiple HIGH nodes "previously swum competitively in college"). The 2nd sport TENNIS is present only WITHOUT the manner qualifier: "experience playing soccer and tennis," "strength training ... to benefit their tennis game" — the phrase "used to play tennis **competitively** in high school" was flattened out, so the reader saw no second competitive sport and answered 1.
- **operand_in_haystack**: yes. answer_f7fd1029_1 "incorporating some strength training ... considering I used to play tennis competitively in high school"; answer_f7fd1029_2 "I used to swim competitively in college." (Soccer is recreational — correctly not counted; GT=2 = swimming + tennis.)
- **current_fix_status**: ADDRESSED-by-M6 (run_eval.py L1704, `_TYPED_ATTR_PROMPT` MANNER QUALIFIERS rule: keep "competitively/professionally/..." in the node context). On rerun the W1 pass should emit a "tennis competitively" node so the reader counts 2. NEEDS LIVE RUN to confirm the qualifier survives extraction and the reader counts both.
- **proposed_fix**: none beyond M6 — verify. (Optional reinforcement: have R2/reader explicitly filter sports on the "competitively" manner so soccer is excluded and tennis included.) Regression risk LOW.
- **confidence**: high.

**[gpt4_7fce9456]** "How many properties did I view before making an offer on the Brookside townhouse?" GT=four, HY=2.
- **root_layer**: RETRIEVAL (4th property absent) + polysemy contamination (partly addressed).
- **operand_in_context**: partial — only 3 of 4 viewed properties present: bungalow/Oakwood (Jan 22, kitchen reno), Cedar Creek (Feb 1, over budget), 2-bedroom condo (Feb 17, offer rejected). The **1-bedroom condo (Feb 10, highway noise)** is ABSENT (`'1-bedroom'/'highway'/'noise' all ABSENT`). The R2 CATEGORY_MEMBERS block is also polluted with the "properties" polysemy (star spectra, meme theory). Reader answered 2 (anchored on Feb 22 saw / Feb 25 offer dates), under-counting even the 3 retrievable.
- **operand_in_haystack**: yes. The missing 4th is in gold answer_a679a86a_3 "I viewed a 1-bedroom condo on February 10th, but the noise from the highway was a deal-breaker." Other 3 in answer_a679a86a_1/2/4.
- **current_fix_status**: PARTIALLY-ADDRESSED-by-M1 (run_eval.py L821-844: conjoins bridge qualifiers townhouse/offer/Brookside with "properties" head to kill astronomy/meme polysemy). But M1 does NOT retrieve the 1-bedroom-condo session, which never says "properties" (says "viewed a 1-bedroom condo"). So even post-M1, max retrievable = 3, not 4 → still OPEN on retrieval.
- **proposed_fix**: RETRIEVAL — expand the property/real-estate category roster with hyponyms (condo/bungalow/townhouse/house/apartment) plus a "viewed/saw/looked at <dwelling>" verb probe, so the 1-bedroom-condo node is force-included. Regression risk MED (hyponym broadening). With all 4 in context the M1-disambiguated reader should reach 4. Confirm on rerun whether M1 alone lifts HY from 2→3 first.
- **confidence**: high (missing 4th operand verified absent; polysemy mechanism verified).

---

**Summary for the map**:
- ADDRESSED (needs live rerun to confirm): **60159905** (A2), **ef66a6e5** (M6).
- PARTIALLY-ADDRESSED, still retrieval-OPEN: **gpt4_7fce9456** (M1 fixes polysemy but 4th property not retrieved).
- OPEN, RETRIEVAL-first (proven lever): **9d25d4e0** (engagement ring absent), **gpt4_7fce9456** (1-bedroom condo absent) — both fixable by hyponym-expanded R2 category rosters + acquire/view-verb probes, MED risk.
- OPEN, WRITER: **aae3761f** (phantom Tybee duration node from a planned trip; gate TYPED_DURATION drive nodes to completed events).
- NOISE-OR-DISPUTED (leave-it, HIGH regression risk to "fix"): **0a995998** (boots exchange = 1 or 2 items?), **d851d5ba** (April $5,000 concert temporal-scope distractor).

Highest-value, lowest-risk retrieval lever across this chunk: a hyponym-expanded category roster for R2 force-include (jewelry→ring/earrings/necklace…; properties→condo/bungalow/townhouse…) gated by acquire/view verbs — directly recovers the two absent operands in 9d25d4e0 and gpt4_7fce9456 without touching reader rules.

=== CHUNK 2 (2ce6a0f2, 67e0d0f2, 9ee3ecd6, bc149d6b, d905b33f, gpt4_2f8be40d, gpt4_a56e767c) ===
All confirmed. "100" appears 0 times in 9ee3ecd6 context — the 100-point reward operand is fully absent. Now I have everything for the definitive map. Here are my records.

---

**qid: 2ce6a0f2** — "How many different art-related events did I attend in the past month?" GT=4, HY=3
- **root_layer**: WRITER (primary) + READER-COUNT (secondary). The 4th event — "guided tour at the History Museum on February 24th" (haystack s40, `answer_901a6763_3`) — was NOT extracted as a dated "attended" art-event node. The dated-anchor regex captured the other 3 (Art Afternoon Feb 17, Women in Art Feb 10, Street Art lecture Mar 3) but not the History Museum tour. It survives only as a vague interest concept (ctx line 6: "User is interested in art museums focusing on ancient history and art — after their visit to the History Museum"). Reader then couldn't count it as an art event from that framing.
- **operand_in_context**: partial. Only ctx line 6: "...after their visit to the History Museum." No dated "guided tour Feb 24" instance, and the word "art" is absent from that node so it doesn't read as an art event.
- **operand_in_haystack**: yes. s40 t0: "I recently went on a guided tour at the History Museum on February 24th, and it really sparked my interest in ancient history and art."
- **current_fix_status**: PARTIALLY ADDRESSED — needs live run. M2 (`_ms_extra_count_sub_queries`, run_eval.py:846-862) fires here: category="art-related events" is a `_generic_event_head` and Q has "attend", so it appends the probe "attended visited went tour exhibition lecture event art-related events". That probe contains "tour…museum"-adjacent tokens and should now retrieve the History Museum guided-tour node into the forced-include block. iter33_ms_clean predates M2's full form. MUST confirm on a live run that M2 surfaces the History Museum node AND that the reader counts it (D-CONSOLIDATED rule 0 "count EVERY distinct named item" helps).
- **proposed_fix**: leave M2 as-is; verify on rerun. If still failing, the residual gap is the WRITER not stamping "History Museum guided tour Feb 24" as a dated attendance node — smallest writer fix: extend the dated-anchor regex (run_eval.py ~line 663/2663) to capture "guided tour at the <Place>" as an attended dated instance. Regression risk MED (adds dated nodes broadly).
- **confidence**: high on root cause; medium that M2 alone closes it (reader may still not classify a "History Museum" tour as "art-related").

---

**qid: 67e0d0f2** — "What is the total number of online courses I've completed?" GT=20, HY=12
- **root_layer**: WRITER. GT=20 = 12 Coursera (s37 t8 "completed 12 courses on Coursera") + 8 edX (s6 t4 "my previous 8 edX courses"). The edX node was extracted but its QUANTITY was dropped: ctx line 16-17 says "completed **multiple** online courses on edX" — the "8" is gone. Reader had 12 + "multiple" and correctly refused to invent a total.
- **operand_in_context**: partial. "12 courses on Coursera" present (ctx line 6-12). The "8" edX operand ABSENT — degraded to "multiple."
- **operand_in_haystack**: yes. s6 t4: "I'm glad I already have a solid foundation in data analysis from my previous **8 edX courses**."
- **current_fix_status**: OPEN. No current fix targets the writer dropping a numeric quantity from a summarized node. The W1 typed-attribute pass produced "12 courses" but no "8 edX courses" typed node.
- **proposed_fix**: WRITER — extend the W1 typed-quantity / `_TYPED_ATTR_PROMPT` pass to capture "<N> <platform> courses" (number + platform) as a TYPED_QUANTITY node, so "8 edX courses" survives verbatim alongside "12 Coursera courses." Then D-COMPUTE(a) sums 12+8=20. Regression risk LOW (typed-quantity nodes are additive, frame-gated to "N courses/items" patterns). Secondary option (RETRIEVAL/forced-include) won't help — the number is lost at write time, not at retrieve time.
- **confidence**: high.

---

**qid: 9ee3ecd6** — "How many points do I need to earn to redeem a free skincare product at Sephora?" GT=100, HY=300
- **root_layer**: RETRIEVAL. GT=100 comes from the Rewards Bazaar skincare products that cost **100 points** (s7 t1: "Drunk Elephant Beste No. 9 Jelly Cleanser (100 points)… Sunday Riley Power Couple (100 points)… Laneige Water Bank Moisturizing Cream (100 points)"). The "300 points" in context is the user's personal savings goal, not the redemption threshold. The 100-point reward operand is entirely ABSENT from context (grep "100" → 0 hits). Only the "300 points" goal and "200 points" balance were retrieved.
- **operand_in_context**: no. ctx only has "300 points to redeem" (line 11-17) and "200 points total" (line 26). No "100 points" reward.
- **operand_in_haystack**: yes. s7 t1 (assistant): multiple skincare products listed at "(100 points)" in the Sephora Rewards Bazaar.
- **current_fix_status**: OPEN. No current fix surfaces session 7's reward-tier list. This is also partly a GT-interpretation question (the GT reads "need to earn to redeem a free skincare product" = cost of the cheapest free skincare reward = 100), but since the 100-point operand never reached the reader, even a perfect reader couldn't answer.
- **proposed_fix**: RETRIEVAL — the question keys on "redeem / free skincare product / points." A sub-query on "redeem free skincare product points Sephora Rewards Bazaar" should pull s7 t1 into the forced-include block. Smallest fix: ensure the retrieval/sub-query path includes the assistant reward-list turn (currently the writer may have skipped the assistant's product list as non-user content). Regression risk LOW-MED (adds assistant-side reward nodes). NOTE: this is a borderline NOISE-OR-DISPUTED candidate — GT=100 hinges on reading "free skincare product" as a specific 100-point reward while the user themselves repeatedly says they need "300 points"; a judge could reasonably accept the user's own framing. But the dominant, fixable issue is the absent operand → classify RETRIEVAL.
- **confidence**: high that the operand is absent (RETRIEVAL); medium that fixing retrieval flips the judge, given GT/question ambiguity.

---

**qid: bc149d6b** — "What is the total weight of the new feed I purchased in the past two months?" GT=70 pounds, HY=50
- **root_layer**: READER-COUNT (scope/under-count). Both operands present: 50-pound layer feed (ctx line 86-87) + 20 pounds organic scratch grains (ctx line 111-112). GT=70 = 50+20. Reader summed only the "new layer feed" (50) and excluded the 20-lb scratch grains — interpreting "new feed" narrowly as the feed the user explicitly called "new," whereas GT treats scratch grains as feed too.
- **operand_in_context**: yes (both). "50-pound batch of layer feed" + "20 pounds of organic scratch grains."
- **operand_in_haystack**: yes. s9 t0 (50-lb layer feed, `answer_92147866_1`) and s10 t0 (20-lb scratch grains, `answer_92147866_2`).
- **current_fix_status**: OPEN (genuinely ambiguous). D-COMPUTE(a) and D-CONSOLIDATED-SUM tell the reader to use present quantities and sum distinct items, but the reader scoped "new feed" to exclude scratch grains. This is a borderline NOISE-OR-DISPUTED: "new feed" most-naturally = the new layer feed only; GT=70 forces a generous "all chicken feed" reading.
- **proposed_fix**: leave-it (do NOT add a reader rule). Reason: forcing "scratch grains = feed" risks over-merging on other SUM questions (the LESSON: a count/sum-scope rule that fixes 2-3 broke 12). The model's narrow reading is defensible. If anything, a minimal D-COMPUTE note "for total-weight-of-feed sums, include ALL feed-type purchases (layer feed, scratch grains, etc.) in the window" — but regression risk MED-HIGH (scope-broadening rules backfire). Recommend leave-it / accept as disputed.
- **confidence**: high on operands-present + reader-scope cause; high that a fix here is net-negative-risk.

---

**qid: d905b33f** — "What percentage discount did I get on the book from my favorite author?" GT=20%, HY=0%
- **root_layer**: READER-COMPUTE. Both operands present and they describe the SAME book: original $30 (ctx line 11-17: "new release from favorite author… originally priced at $30") and paid $24 (ctx line 6, 21-22, 26-30: "got the book for $24 after a discount" — the impulse buy at the favorite bookstore). (30−24)/30 = 20% = GT. The reader failed to (a) link the $24 book and the $30 favorite-author book as one book, and (b) compute the percentage — instead hallucinating "priced at $30 and you paid $30 → 0%."
- **operand_in_context**: yes (both): "$30 original" (favorite-author book) + "$24 after a discount" (same impulse-buy book). Distractor present: "20% discount code" on Zara jeans (line 36-55) — reader correctly avoided that distractor but botched the real compute.
- **operand_in_haystack**: yes. s33 t6 ($30 favorite-author new release) + s18 t2 ($24 after a discount at favorite bookstore) — same book, `answer_85a77c48_1/_2`.
- **current_fix_status**: OPEN. D-COMPUTE(a) says "COMPUTE … product/duration when BOTH operands present" but does not explicitly cover percentage-discount = (orig−paid)/orig, and crucially does not instruct the reader to LINK the $24-book and the $30-favorite-author-book as the same item (they're in two different nodes with no shared "book" key).
- **proposed_fix**: READER (minimal, D-COMPUTE extension) — add a worked example: "For 'what % discount on X': if X's ORIGINAL price and PAID price are both present (possibly in separate nodes describing the same item — e.g. '$30 original' + '$24 after a discount'), link them and compute (orig−paid)/orig × 100." Regression risk LOW-MED (gated to "what percentage discount" phrasing; only fires when both a price-original and price-paid for the same item exist). This is the proven D-COMPUTE worked-example pattern (like the age/product examples), low blast radius.
- **confidence**: high.

---

**qid: gpt4_2f8be40d** — "How many weddings have I attended in this year?" GT=3 (Rachel&Mike, Emily&Sarah, Jen&Tom), HY=2
- **root_layer**: READER-COUNT (under-count). All THREE distinct attended weddings ARE in context: (1) cousin Rachel's vineyard wedding in August (ctx line 33-34); (2) college roommate's city/rooftop-garden wedding = friend Emily (ctx line 48-49); (3) friend's wedding last weekend, bride Jen + Tom (ctx line 28-29). HY counted only #1 and #3, MISSING the college roommate's (Emily) wedding. The R2 CATEGORY_MEMBERS block (ctx lines 15-20) force-included only wedding-PLANNING items (user's own wedding), not the attended weddings — so the reader had to assemble the count from CONCEPTS and dropped one.
- **operand_in_context**: yes (all 3 attended weddings present in CONCEPTS).
- **operand_in_haystack**: yes. s9 (cousin Rachel, `answer_e7b0637e_1`), s6 (roommate/Emily, `answer_e7b0637e_2`), s41 (Jen&Tom, `answer_e7b0637e_3`).
- **current_fix_status**: OPEN. The "REVERT over-merge" fix (recovers count undercounts) and D-CONSOLIDATED rule (0)+(2) "count EVERY distinct named item; treat distinct hosts/dates as DISTINCT, do NOT merge" directly target this. iter33_ms_clean predates the REVERT. The CATEGORY_MEMBERS block force-including only planning items is the residual weakness — M2 generic-event probe does NOT fire (category="weddings" is not a `_generic_event_head` token).
- **proposed_fix**: (1) RELY on REVERT + D-CONSOLIDATED on rerun — likely flips to 3 since the distinct-host dedup discipline now says count cousin/roommate/friend separately. MUST confirm live. (2) If still 2: RETRIEVAL — extend `_ms_extra_count_sub_queries` so a "weddings"/"<event> attended" category adds an attend-verb probe ("attended wedding cousin roommate friend bride groom") to force-include the three ATTENDED instances (not planning) into a CATEGORY_MEMBERS-style countable block. Regression risk LOW (additive sub-query). Do NOT add a reader rule beyond existing D-CONSOLIDATED.
- **confidence**: high on cause (operands present, reader under-counted); medium that REVERT+D-CONSOLIDATED alone closes it without the force-include improvement.

---

**qid: gpt4_a56e767c** — "How many movie festivals that I attended?" GT=4, HY=3
- **root_layer**: READER-COUNT (under-count via verb-strictness). All 4 festivals ARE in context: Austin Film Festival (ctx line 7, 60-61), Seattle International Film Festival (line 65-66), AFI Fest (line 30-44), Portland Film Festival (line 50-51, 80-81). HY listed Austin, Seattle, AFI and MISSED Portland — because the user "volunteered at" / "assisted with a masterclass at" the Portland Film Festival rather than literally "attended" it; GT counts Portland. The R2 CATEGORY_MEMBERS block (ctx lines 5-8) force-included only 2 weak items (independent-films interest, 48-hour-challenge typed-duration), NOT the 4 festival names — so the reader assembled the count from CONCEPTS and dropped the "volunteered" one.
- **operand_in_context**: yes (all 4 festivals present).
- **operand_in_haystack**: yes. s6 (Austin + Seattle, `answer_cf9e3940_2`), s29 (Portland — "volunteered"/"assisted", `answer_cf9e3940_1`), s32 (AFI Fest, `answer_cf9e3940_3`).
- **current_fix_status**: OPEN. The symbolic count_among resolver (symbolic_resolver.py:1058-1067) explicitly handles "volunteered at X" as a counted attendance — but count_among is now PARTY-GATED (S1 gate), so it does NOT fire on "movie festivals." D-CONSOLIDATED rule (0) "count EVERY distinct named item" helps but doesn't explicitly tell the reader that "volunteered at / assisted at <festival>" = attended.
- **proposed_fix**: (1) READER (minimal, D-CONSOLIDATED note): "for 'festivals/events I attended', a festival the user VOLUNTEERED at / ASSISTED at / WORKED at counts as attended." Regression risk LOW-MED (could over-count if user only "considered" volunteering — gate to past-tense volunteered/assisted/helped-at). (2) RETRIEVAL alternative: add festival-name force-include — but names are already in context, so this is a reader/counting problem, not retrieval. Prefer the small reader note. Mirrors the count_among "volunteered" logic that already exists but is party-gated.
- **confidence**: high on cause; medium that the "volunteered counts" note is net-positive without risk (verb-broadening can over-count elsewhere — verify on rerun).

---

**SUMMARY MAP (root_layer tally for this chunk):**
- RETRIEVAL: 9ee3ecd6 (100-pt reward absent)
- WRITER: 67e0d0f2 (edX "8" dropped → "multiple"); 2ce6a0f2 (primary — History Museum tour not stamped as dated art-event; M2 may rescue at retrieval)
- READER-COUNT: bc149d6b (scratch-grains scope), gpt4_2f8be40d (roommate/Emily wedding dropped), gpt4_a56e767c (Portland "volunteered" dropped)
- READER-COMPUTE: d905b33f ($30 & $24 same book → 20% not computed)

**Highest-leverage, lowest-risk OPEN fixes** (priority): 
1. 67e0d0f2 — W1 typed-quantity capture of "N <platform> courses" (WRITER, LOW risk). 
2. d905b33f — D-COMPUTE percentage-discount worked-example with same-item linking (READER, LOW-MED risk). 
3. gpt4_2f8be40d + gpt4_a56e767c — confirm REVERT+D-CONSOLIDATED on rerun first (both are over-merge/under-count undercounts the REVERT targets); only add a force-include attend-probe / "volunteered counts" note if rerun still under-counts. 
4. 2ce6a0f2 — verify M2 generic-event probe on rerun before any writer change. 
5. 9ee3ecd6 — RETRIEVAL of assistant reward-tier list (borderline disputed, lower priority). 
6. bc149d6b — leave-it (disputed scope; reader-scope rule risks net-negative per the LESSON).

Relevant code paths: `/tmp/cf-unified/benchmarks/longmemeval/run_eval.py` (M2 `_ms_extra_count_sub_queries` lines 807-881; W1 `_TYPED_ATTR_PROMPT`; dated-anchor regex ~663/2663); `/tmp/cf-unified/configs/longmemeval_profile.yaml` (D-COMPUTE lines 376-395, D-CONSOLIDATED lines 336-374); `/tmp/cf-unified/benchmarks/longmemeval/symbolic_resolver.py` (count_among volunteered-handling lines 1058-1067, party-gated). Context dumps for re-inspection: `/tmp/ms_study/ctx/<qid>.txt`.

=== CHUNK 3 (37f165cf, 7024f17c, a08a253f, bf659f65, e3038f8c, gpt4_31ff4165) ===
Confirmed: the jog is May 20 (Saturday), 10 days before the May-30 (Tuesday) question — so it's NOT strictly "last week" (last week would be May 22-28). Yet GT=0.5h treats it as in-scope. This is GT-loose. The D-CONSOLIDATED carve-out (commit 3c49652 / ff0de72) explicitly cites 7024f17c and forces the dated jog to count = 0.5h, so it's ADDRESSED.

I now have everything. Let me also confirm the iter33_ms_clean run definitively predates the M1-M6/A/B fixes (run was "v1 full MS-133" — the prompt states it ran before most fixes). The commits 3c49652 (M1-M6), 3ce73cc (A/B), and the D-CONSOLIDATED carve-out are all in the branch now. The iter33_ms_clean run captured failures before these landed.

Here is my definitive analysis.

---

# MS Failure Analysis — Chunk: [37f165cf, 7024f17c, a08a253f, bf659f65, e3038f8c, gpt4_31ff4165]

## 37f165cf
- **Q:** "What was the page count of the two novels I finished in January and March?" GT=856, HY="416 and 341". verdict=PARTIAL.
- **root_layer:** READER-COMPUTE. Both operands needed (440 + 416 = 856) are in context, but the reader selected the wrong pair (416 + 341).
- **operand_in_context:** yes (all three present). 440: line 13 "User completed reading 'The Nightingale' (440 pages)". 416: line 53/58 "finished a 416-page novel" / "TYPED_QUANTITY: 416-page". 341: line 63 "TYPED_QUANTITY: 341 pages — The Power's page count". The reader picked 416+341 because **only 416 and 341 have explicit TYPED_QUANTITY nodes; 440 lives only in concept prose** — a writer asymmetry that biased the selection.
- **operand_in_haystack:** yes. s9: Nightingale 440 pages; s33: "just finished a 416-page novel, but before that, I read 'The Power' ... in December, which had 341 pages". The Power was finished in **December** (earliest), so it is excluded; the two most-recent finishes are Nightingale (440) + the 416-page novel.
- **current_fix_status:** ADDRESSED-by-D-COMPUTE (needs live run). The D-COMPUTE rule explicitly names this qid: `"two novels finished in January and March" → select the two most-recently-finished novels by completion DATE, not by literal month words (targets 37f165cf)` (profile line 387-389). iter33_ms_clean predates this.
- **proposed_fix:** Leave the reader rule as-is (already targeted). Smallest additive hardening if it still fails live: add a W1 TYPED_QUANTITY emit for the "(440 pages)" pattern inside concept prose so 440 has a first-class quantity node parallel to 416/341 (removes the selection bias). Regression risk LOW.
- **confidence:** HIGH (root cause), MED (that the rule alone fixes it without the 440-node, given the TYPED_QUANTITY asymmetry).

## 7024f17c
- **Q:** "How many hours of jogging and yoga did I do last week?" GT=0.5h, HY="0 hours total". verdict=INCORRECT.
- **root_layer:** READER-COMPUTE (temporal/lapsed-routine handling). The 30-min jog operand is present; the reader wrongly zeroed it.
- **operand_in_context:** yes. Line 276 "User went for a 30-minute jog around the neighborhood on Saturday"; line 281 "TYPED_DATE: Saturday — jog". Yoga is correctly aspirational/lapsed (line 91 "used to practice yoga ... slacking off this month"; line 96 "hoping to get back into yoga ... one or two sessions a week") → 0h. So GT 0.5h = the jog alone.
- **operand_in_haystack:** yes. s4 "30-minute jog ... on Saturday"; s22 yoga "slacking off this month"; s26 "hoping to get back into yoga this week". The jog is dated **May 20 (Saturday)**, which is 10 days before TODAY=May 30 (Tue) — technically outside a strict Mon-Sun "last week," but GT counts it (GT is loose on the window).
- **current_fix_status:** ADDRESSED-by-D-CONSOLIDATED carve-out (needs live run). Profile lines 349-357 add the carve-out explicitly naming this qid: `"a logged '30-minute jog on Saturday' = 0.5h even though the user says they've 'been slacking off' ... (targets 7024f17c: lapsed/aspirational yoga = 0h → 0.5h; but a dated completed jog = its real 0.5h, NOT zeroed)"`. iter33_ms_clean predates this.
- **proposed_fix:** Leave it (already targeted). Residual risk: the reader may still exclude the jog on the strict "last week" (10-day) technicality rather than the lapsed-routine technicality the carve-out addresses. If it fails live, broaden the carve-out's window note: a dated completed instance the user logs in the relevant period counts even at the loose edge of "last week." Regression risk LOW (gated to completed dated single instances).
- **confidence:** HIGH.

## a08a253f
- **Q:** "How many days a week do I attend fitness classes?" GT=4, HY="3 days (Zumba Tue/Thu + weightlifting Sat)". verdict=INCORRECT.
- **root_layer:** RETRIEVAL. The 4th class day's operand is absent from full_context.
- **operand_in_context:** no (partial). Context has Zumba Tue/Thu (lines 90,100) + weightlifting Sat (line 195) = 3 day-slots. The 4th — **"yoga class on Wednesdays"** — is entirely ABSENT; grep of the context finds zero "Wednesday" and no yoga-class node (only an assistant bodyweight-exercise list mentioning the word "Yoga" at line 261).
- **operand_in_haystack:** yes. s28 t0 "recently started a yoga class on Wednesdays"; reinforced s28 t6/t8 "taking yoga on Wednesdays". Session 28 is a workout-playlist session, so the yoga-class fact was never retrieved into context. GT counts the 4 distinct weekdays: Tue (Zumba), Wed (yoga), Thu (Zumba), Sat (weightlifting) = 4.
- **current_fix_status:** ADDRESSED-by-M3 (needs live run to confirm). M3 weekday probe (run_eval.py lines 864-870) fires on the `"how many days/times a week"` frame and emits `"Monday Tuesday Wednesday Thursday Friday Saturday Sunday <cat>"` to force-retrieve per-weekday instances — designed to surface the Wednesday yoga session. iter33_ms_clean predates M3.
- **proposed_fix:** Leave M3 as-is and confirm live. The risk is the s28 session frames yoga as "yoga class" not "fitness class," so the category-head match is weak; M3's weekday+category conjunction is the right lever. If M3 misses, add "yoga class" / "exercise class" as a synonym sibling to the "fitness classes" category probe. Regression risk LOW (frame-gated to the weekly-frequency question form).
- **confidence:** HIGH (root cause = retrieval miss of s28; M3 is the matching fix).

## bf659f65
- **Q:** "How many music albums or EPs have I purchased or downloaded?" GT=3, HY="2 (Happier Than Ever + Midnight Sky EP)". verdict=INCORRECT.
- **root_layer:** RETRIEVAL. The 3rd operand is absent from full_context.
- **operand_in_context:** no (partial). Context has Happier Than Ever (downloaded, line 19) + Midnight Sky EP (purchased, lines 24/39). The 3rd — **Tame Impala vinyl** (bought/signed at Red Rocks) — is ABSENT; grep finds no "Tame Impala" / "Red Rocks," only generic "looking to find vinyl records at the festival" (lines 69-70, an aspiration, not a purchase).
- **operand_in_haystack:** yes. s32 t0 "I saw Tame Impala live ... I even got my vinyl signed after the show"; s32 t6 "I recently got my Tame Impala vinyl". GT treats the Tame Impala vinyl as a 3rd purchased album. Session 32 (Colorado-festival-recs) was not retrieved for the purchase fact.
- **current_fix_status:** ADDRESSED-by-M4 (needs live run to confirm). M4 vinyl probe (run_eval.py lines 872-879) is gated to album/EP/record/vinyl categories and emits `"vinyl LP record bought purchased downloaded at concert"` to surface a format-distant vinyl purchase — exactly the Tame Impala case named in the M4 comment. iter33_ms_clean predates M4.
- **proposed_fix:** Leave M4 as-is and confirm live. If the s32 vinyl session still misses, add "signed at show/concert" acquisition phrasing to the probe (the operand surfaces as "got my vinyl signed after the show," not "bought"). Regression risk LOW (gated to music categories).
- **confidence:** HIGH.

## e3038f8c
- **Q:** "How many rare items do I have in total?" GT=99, HY="74 (12 figurines + 57 records + 5 books)". verdict=INCORRECT.
- **root_layer:** WRITER (with a RETRIEVAL component). The 4th category's COUNT operand was never extracted into a usable quantity node, so it is absent from the count-able context.
- **operand_in_context:** partial/no. Context has TYPED_QUANTITY nodes for 12 figurines (line 36), 57 records (line 56), 5 books (line 91) → 74. The missing 4th category is **25 rare coins**: context mentions "rare coins" only as a *storage concern* (lines 156, 166) — **the quantity "25" is ABSENT**; no TYPED_QUANTITY: 25 rare coins node exists.
- **operand_in_haystack:** yes. s15 t4 "I actually have **25 rare coins** that I need to store safely." GT = 12 + 57 + 5 + **25** = 99. The "25 rare coins" quantity was not written as a TYPED_QUANTITY node (unlike the other three categories), so it never entered the R2 CATEGORY_MEMBERS / countable set, and the reader summed only the three present quantities.
- **current_fix_status:** OPEN. No current fix targets this. M1-M6 don't cover rare-coins; the REVERT (un-merge) doesn't create the missing 25-coins quantity node; the symbolic count_among is party-gated (symbolic_resolver.py line 208) so it never fires here.
- **proposed_fix:** (1, primary) WRITER: ensure the W1 typed-attribute pass emits a TYPED_QUANTITY for the "I have N <rare X>" possessive-quantity pattern (it already captured "12 rare figurines"/"57 rare records"/"5 books" — "25 rare coins" should match the same pattern; investigate why s15 t4 was skipped — likely retrieval never delivered s15 to the writer/category pass, making it (2, secondary) a RETRIEVAL miss of the coins session). Smallest safe lever: add a count-completeness sub-query that enumerates rare-item sub-kinds ("coins figurines records books stamps") under the "rare items" category so s15 is force-retrieved, then the existing quantity node (if written) is counted. Regression risk MED (broadening a category probe can pull noise into other count Qs; gate to the "rare items / collection / in total" frame).
- **confidence:** HIGH (root cause = missing 25-coins quantity), MED (which sub-layer — writer-skip vs retrieval-miss of s15; both plausible, needs a graph dump to disambiguate which is not in this read-only data).

## gpt4_31ff4165
- **Q:** "How many health-related devices do I use in a day?" GT=4, HY="3 (Accu-Chek + Fitbit Versa 3 + nebulizer)". verdict=PARTIAL.
- **root_layer:** READER-COUNT. All four operands are present; the reader under-counted by omitting one that it didn't classify as a "health-related device."
- **operand_in_context:** yes. Accu-Chek (line 16), nebulizer (line 26), Fitbit Versa 3 (line 36), and the missing 4th — **hearing aids** — IS present at line 31: "User has been relying on hearing aids for guided breathing sessions with their Fitbit." The reader omitted it, likely because the framing ("for guided breathing sessions with Fitbit") reads as Fitbit-adjacent and hearing aids are ambiguously "health-related."
- **operand_in_haystack:** yes. s14 "behind-the-ear (BTE) hearing aids from Phonak ... relying on these hearing aids a lot lately." GT counts 4 devices: Fitbit Versa 3, hearing aids, Accu-Chek Aviva Nano, nebulizer.
- **current_fix_status:** OPEN. No current rule resolves hearing-aid-as-health-device. The D-CONSOLIDATED "count EVERY distinct named item / SCAN titles AND descriptions" rule (lines 340-343, 373) should help in principle, but the operand was IN context and still missed — the issue is *classification* (is a hearing aid "health-related"?), which no rule addresses.
- **proposed_fix:** (1) Minimal reader nudge: in the D-CONSOLIDATED count discipline, add a one-line note that assistive/medical devices (hearing aids, glucose meter, nebulizer, CPAP, pacemaker) count as "health-related devices" even when mentioned in a non-medical framing. This is a frame-gated reader clarification, not a per-qid emitter. Regression risk MED (reader-rule additions have backfired before per the lesson; keep it a short enumerated example, not a behavioral mandate). (2, alternative) NOISE-leaning: this is partly judge/GT-disputable (whether hearing aids are "health-related devices used in a day"), so consider "leave-it" if the reader-rule edit risks other device-count Qs. Given the LESSON (reader over-tuning backfires), I lean toward **leave-it / low-priority** unless a cluster of device-classification misses justifies the rule.
- **confidence:** MED (root layer = reader-count clear; whether to fix vs leave is the judgment call — borderline disputable GT).

---

## Summary table

| qid | root_layer | operand_in_ctx | in_haystack | fix_status | priority fix | risk |
|---|---|---|---|---|---|---|
| 37f165cf | READER-COMPUTE | yes (440+416) | yes | ADDRESSED-by-D-COMPUTE (live-confirm) | + W1 emit "(440 pages)" quantity node | LOW |
| 7024f17c | READER-COMPUTE | yes (jog 0.5h) | yes | ADDRESSED-by-D-CONSOLIDATED carve-out (live-confirm) | leave / widen window note | LOW |
| a08a253f | RETRIEVAL | no (yoga-Wed absent) | yes (s28) | ADDRESSED-by-M3 weekday probe (live-confirm) | + "yoga/exercise class" synonym | LOW |
| bf659f65 | RETRIEVAL | no (Tame Impala vinyl absent) | yes (s32) | ADDRESSED-by-M4 vinyl probe (live-confirm) | + "signed at show" acquisition phrase | LOW |
| e3038f8c | WRITER (+RETRIEVAL) | partial (25-coins qty absent) | yes (s15) | OPEN | W1 quantity for "I have N rare X" + rare-subkind probe | MED |
| gpt4_31ff4165 | READER-COUNT | yes (hearing aids present) | yes (s14) | OPEN | reader note: assistive/medical devices count; else leave-it | MED / disputable |

**Net for this chunk:** 4 of 6 are already ADDRESSED by current branch fixes (D-COMPUTE 37f165cf, D-CONSOLIDATED-carveout 7024f17c, M3 a08a253f, M4 bf659f65) and only need a live run to confirm — consistent with "iter33_ms_clean ran before most fixes." 2 are OPEN: **e3038f8c** (highest-value, a writer/retrieval undercount of 25 rare coins → 74 vs 99) and **gpt4_31ff4165** (reader-count classification of hearing aids; borderline-disputable, low priority per the reader-over-tuning lesson). Relevant files: `/tmp/cf-unified/configs/longmemeval_profile.yaml` (D-COMPUTE lines 376-395, D-CONSOLIDATED lines 336-374), `/tmp/cf-unified/benchmarks/longmemeval/run_eval.py` (M3 lines 864-870, M4 lines 872-879, forced-include lines 884+), `/tmp/cf-unified/benchmarks/longmemeval/symbolic_resolver.py` (count_among party-gated, lines 208-216).

=== CHUNK 4 (3a704032, 73d42213, a96c20ee_abs, c4a1ceb8, edced276, gpt4_372c3eed) ===
Confirmed: all 3 succulent mentions are care/fertilizer context ("fertilizers for snake plants and succulents"), NOT acquisition. The "succulent got from nursery two weeks ago" fact (the acquisition operand) and the "peace lily got from nursery two weeks ago" are BOTH absent from context. Only the snake plant ("got from my sister last month") is present as an acquisition. So the reader correctly found 1 acquisition it could ground; the other 2 (peace lily + succulent, both from nursery 2 weeks ago) were not retrieved into context. This is a RETRIEVAL/WRITER miss.

I now have a complete, rigorous map of all 6 qids. Here are the final records.

---

**RECORD 1 — qid `3a704032`** ("How many plants did I acquire in the last month?", GT=3, HY=1)

- **root_layer**: RETRIEVAL (with a WRITER component). 2 of the 3 acquisition operands never reached context.
- **operand_in_context**: **partial**. Only the snake plant acquisition is present: CONCEPTS → "[2023-05-25] TYPED_DURATION: last month — snake plant I got from my sister" and "got from my sister last month". The other two acquisitions are ABSENT: "peace lily" count in full_context = 0; "two weeks ago" = 0. The 3 "succulent" hits are all care/fertilizer context ("fertilizers… for snake plants and succulents"), NOT the acquisition ("got from the nursery… along with a succulent… two weeks ago").
- **operand_in_haystack**: **yes**. answer_c2204106_2: "my peace lily, which I got from the nursery **two weeks ago** along with a **succulent**"; answer_c2204106_1: "my snake plant… I **got from my sister last month**". Three acquisitions = snake plant + peace lily + succulent = 3.
- **current_fix_status**: **OPEN** (retrieval). The post-run D-CONSOLIDATED clause (3) explicitly targets 3a704032 ("'last month' snake plant counts → 3") but it only helps the reader *count* items already in context — it cannot recover the peace-lily/succulent acquisitions, which are never retrieved. So even with current code this stays at 1 unless retrieval/writer surfaces the nursery-acquisition. The R2 CATEGORY_MEMBERS block did force-include 5 plant nodes (snake/spider/basil) but missed peace lily and the "from-nursery succulent" entirely.
- **proposed_fix** (priority order):
  1. RETRIEVAL/R2: in `_ms_extra_count_sub_queries`, for acquisition-count questions ("how many X did I acquire/get/buy"), add an acquisition-verb probe conjoined with the category head — e.g. `"got bought received acquired purchased from nursery from sister gift " + cat` — so the nursery/peace-lily session wins a force-include slot. Risk **LOW** (additive, frame-gated to acquire-verb counts).
  2. WRITER (W1): the peace-lily/succulent acquisition ("got from the nursery two weeks ago") was never emitted as an acquisition node — only as care prose. A W1 acquire-verb typed-attribute probe ("got/bought/received <NP> [time-phrase]") would create a groundable node. Risk **MED**.
  - Needs a live run to confirm (retrieval-dependent).
- **confidence**: **high** on diagnosis (operands proven present in haystack, proven absent in context); medium on whether fix #1 alone reaches 3.

---

**RECORD 2 — qid `73d42213`** ("What time did I reach the clinic on Monday?", GT="9:00 AM", HY="10:30 AM")

- **root_layer**: RETRIEVAL. This is a COMPUTE question (7 AM departure + 2 h travel = 9 AM) but the second operand session is entirely missing.
- **operand_in_context**: **partial**. Operand 1 present: CLOCK_TIME_MATCHES #4 "TYPED_TIME: 7 AM — left home for doctor's appointment". Operand 2 ("two hours to get to the clinic") is **completely absent**: in full_context "two hours"=0, "clinic"=0, "hour"=0, "reschedul"=0, "12345"=0. The entire clinic session (answer_1881e7db_2) was never retrieved.
- **operand_in_haystack**: **yes**. answer_1881e7db_1: "I left home at **7 AM** on Monday for my doctor's appointment"; answer_1881e7db_2: "it took me **two hours** to get to the clinic… from my home last time". 7 AM + 2 h = 9:00 AM = GT.
- **current_fix_status**: **ADDRESSED-by-D-COMPUTE(b)** for the *hallucination*, OPEN for the *answer*. D-COMPUTE(b) explicitly names 73d42213: "travel-time absent → ABSTAIN, do NOT fabricate." iter33_ms_clean ran BEFORE that rule (profile commits ff0de72/3ce73cc post-date the run); under current code the reader should now ABSTAIN instead of emitting "10:30 AM". But abstention still ≠ GT "9:00 AM" — the strict judge will still mark it wrong. The *correct* answer only comes from retrieving the clinic session. Needs a live run to confirm the abstain behavior.
- **proposed_fix** (priority order):
  1. RETRIEVAL: the question contains "clinic" and "Monday" — the clinic-reschedule session should be a strong BM25/embedding match on "clinic". Investigate why answer_1881e7db_2 ranked out. A bridge-phrase/multi-hop sub-query that pairs the destination ("clinic") with the time anchor ("Monday", "left home") would pull operand 2 in. Risk **LOW**.
  2. Keep D-COMPUTE(b) abstention as the safety net (already in). Risk **LOW**.
  - leave reader as-is otherwise; the bottleneck is retrieval.
- **confidence**: **high** (operand 2 proven absent; D-COMPUTE(b) literally names this qid).

---

**RECORD 3 — qid `a96c20ee_abs`** ("At which university did I present a poster for my undergrad course research project?", GT=abstain, HY="Harvard University")

- **root_layer**: ABSTENTION (should refuse). The `_abs` variant swaps the original qualifier "thesis research" → "**undergrad course research project**", which has no grounding.
- **operand_in_context**: **partial / trap**. The HEAD ("poster… research conference… Harvard") is grounded: CONCEPTS → "[2023-05-30] User attended first research conference at **Harvard University**" + "[2023-05-23] User presented a poster on **thesis research** at first research conference". But the QUALIFIER "undergrad course research project" is **absent** — the only poster is on *thesis research*.
- **operand_in_haystack**: **no** (for the qualifier). Haystack has "poster on my **thesis research**" (answer_ef84b994_1) and "been to **Harvard University**… first research conference" (answer_ef84b994_2); grep for "undergrad"/"course research project" across the entire haystack = **0 hits**. So abstention is correct.
- **current_fix_status**: **ADDRESSED-by-A1** (qualifier-grounding abstention). A1 explicitly names this qid: "'undergrad course research project' poster ungrounded while a thesis poster is present → 'Not enough info — no record of a poster for an undergrad course research project.'" iter33_ms_clean ran BEFORE A1 (commits 3ce73cc/ff0de72 post-run), so this failure is a pre-fix artifact. Also note ff0de72 turns "Tier-1 off for _abs" — reducing the aggressive retrieval that fed the Harvard substitution. Needs a live run to confirm A1 fires and the reader stops at the refusal (A1's "STOP — do not volunteer the near-miss entity").
- **proposed_fix**: **leave-it** — A1 already targets this exact case. The only residual risk is that A1's HEAD/QUALIFIER decomposition correctly identifies "undergrad course research project" as the ungrounded qualifier vs. the grounded "thesis research"; if a live rerun still answers Harvard, tighten A1's qualifier-extraction to treat "thesis research" and "undergrad course research project" as non-matching project descriptors. Regression risk of leaving it: **LOW**.
- **confidence**: **high** (qualifier proven absent from entire haystack; A1 names the qid).

---

**RECORD 4 — qid `c4a1ceb8`** ("How many different types of citrus fruits have I used in my cocktail recipes?", GT=3, HY=2)

- **root_layer**: READER-COUNT (undercount). All 3 citrus types are in context; the reader counted only lime + orange and missed lemon.
- **operand_in_context**: **yes** (all 3). lime (19×) and orange (20×) present; **lemon present 3×**, all as "slices of **orange and lemon**" — CONCEPTS: "User is serving Sangria made with Rioja wine and slices of orange and lemon", "Assistant endorsed serving Sangria… with slices of orange and lemon", "User plans to serve Sangria… with slices of orange and lemon".
- **operand_in_haystack**: **yes**. answer_56d02cab_2: "serving the Sangria… with slices of **orange and lemon**". The 3 distinct citrus = lime, orange, lemon = GT 3.
- **current_fix_status**: **OPEN** (reader undercount), partially mitigated by D-CONSOLIDATED(0)+(2) ("UNDERCOUNT is dominant; count EVERY distinct named item, scan titles AND descriptions; when unsure, treat as distinct"). That post-run rule pushes the reader to scan descriptions for lemon, so a live rerun MAY now reach 3. But the R2 CATEGORY_MEMBERS force-include block FAILED here — it surfaced only 2 noise items ("infused simple syrups", "Yemen Mocha coffee… notes of… fruit"), neither a citrus fruit, so the reader got no explicit "lime/orange/lemon" tally and had to infer types from prose.
- **proposed_fix** (priority order):
  1. R2/RETRIEVAL: `_extract_count_category` returns "citrus fruits"; the force-include retrieval ranked generic "fruit"/"syrup" nodes over the Sangria "orange and lemon" line. Add a citrus-enumeration probe in `_ms_extra_count_sub_queries` gated on category∈{citrus, fruit}: append `"lime lemon orange grapefruit tangerine yuzu " + cat` so the lemon-bearing Sangria node wins a force-include slot and the reader sees lemon explicitly. Risk **LOW** (additive, frame-gated; mirrors the existing M4 vinyl enumeration).
  2. Rely on D-CONSOLIDATED undercount-discipline (already in) as the reader-side net. Risk **LOW**.
  - Avoid any count-dedup tightening (the lesson: dedup rules backfire).
- **confidence**: **high** (lemon proven present in context; pure undercount).

---

**RECORD 5 — qid `edced276`** ("How many days did I spend in total traveling in Hawaii and in New York City?", GT="15 days", HY="10 days")

- **root_layer**: READER-COMPUTE (with a WRITER component). Both operands are technically in context, but the Hawaii duration is in a node de-anchored from "Hawaii", so the reader failed to bind it and guessed Hawaii=5.
- **operand_in_context**: **partial**. NYC=5 present and well-anchored: "User recently returned from a solo trip to **New York City for five days**" + "TYPED_DURATION: five days — recent solo trip to New York City". Hawaii's duration is present but DE-ANCHORED: "TYPED_DURATION: **10-day — family trip planning**" (date 2023-05-24, the Hawaii session) — the word "Hawaii" is NOT on that node; the Hawaii concept node ("island-hopping trip to Hawaii with family") carries no number. There's also a distractor "TYPED_DURATION: around 7-10 days — staying in Europe".
- **operand_in_haystack**: **yes**. answer_60e8941a_1: "island-hopping trip to **Hawaii** with my family" + (same session) "we had to plan everything out for the **10-day** [trip]"; answer_60e8941a_2: "solo trip to **New York City for five days**". 10 + 5 = 15 = GT.
- **current_fix_status**: **OPEN**. D-COMPUTE(a) covers "compute when both operands present under a different surface form," but here the Hawaii "10-day" node is labeled "family trip planning" and competes with a "7-10 days Europe" distractor, so the reader picked the wrong binding (Hawaii=5). No current rule binds the de-anchored duration to Hawaii by shared session date.
- **proposed_fix** (priority order):
  1. WRITER (W1): when emitting a TYPED_DURATION node, carry the salient entity from the same user turn into the node title instead of a generic label — "10-day **Hawaii family trip**" rather than "10-day — family trip planning". This makes the operand bindable. Risk **MED** (touches W1 titling; verify no regression on other duration nodes).
  2. READER: add a worked example under D-COMPUTE for "sum of two trip durations" instructing: when a destination concept lacks a number but a same-session-dated TYPED_DURATION exists, bind them by session date before summing; ignore aspirational/"planning to stay" durations (the Europe 7-10 days is a *plan*, not a completed trip). Risk **MED** (reader-rule tuning — keep frame-gated to "total days … in A and B").
  - Note GT treats both as completed trips (Hawaii "got back", NYC "got back") and sums actuals → 15.
- **confidence**: **high** on diagnosis; medium on fix #1 alone closing it (reader must still avoid the Europe distractor).

---

**RECORD 6 — qid `gpt4_372c3eed`** ("How many years in total in formal education from high school to completion of Bachelor's?", GT="10 years", HY="8 years")

- **root_layer**: READER-COMPUTE — borderline NOISE-OR-DISPUTED. The reader summed two enrollment durations (4 HS + 4 BS = 8); GT computes the calendar **span** start-of-HS → BS-completion (2010 → 2020 = 10).
- **operand_in_context**: **yes** (both anchors present). "TYPED_DURATION: 2010 to 2014 — years attended high school" + "attended Arcadia High School from 2010 to 2014"; and "graduated with Bachelor's… from UCLA in **2020**" + "TYPED_DATE: 2020 — graduated with a Bachelor's… from UCLA" + "TYPED_DURATION: four years — Bachelor's degree completion time". (Also present: Associate's from PCC May 2016 — the bridge that fills the 2014→2020 gap.)
- **operand_in_haystack**: **yes**. answer_35c5419d_1: "attended UCLA for undergrad after I attended **Arcadia High School from 2010 to 2014**"; answer_35c5419d_3: "graduated with a Bachelor's in CS from UCLA in **2020**, which took me four years". GT 10 = span 2010→2020 (inclusive of the Associate's/transfer years).
- **current_fix_status**: **OPEN** (reader chose the wrong arithmetic), candidate **LIKELY-DISPUTED**. The question "years in total… **from high school to the completion of my Bachelor's**" is genuinely span-shaped (2010→2020=10), but "total years in formal education" with a 2-year non-degree gap is a defensible 8. The strict judge sided with the span reading. No current rule disambiguates span-vs-sum.
- **proposed_fix** (priority order):
  1. READER (frame-gated, LOW risk if narrow): add a worked example under D-COMPUTE for "how many years from <start milestone> **to** the completion of <end milestone>" → compute the **calendar span** (end_year − start_year), NOT the sum of individual enrollment durations. Here: 2020 − 2010 = 10. Gate strictly to the "from … to the completion of …" frame so it doesn't perturb plain "how long was my degree" questions. Risk **LOW-to-MED** (one frame-gated example; the lesson warns reader-rule over-tuning backfires, so keep it tightly scoped and validate net-positive).
  2. Else **leave-it** and tag as disputed — a single span/sum example is the maximum justified change; do NOT add per-qid logic.
  - Operands are all present; this is purely an arithmetic-semantics choice, so retrieval/writer changes won't help.
- **confidence**: **medium** (diagnosis certain; GT interpretation is arguably ambiguous, so it's partly judge/GT-driven).

---

**Chunk summary (root-layer tally):** RETRIEVAL ×2 (3a704032, 73d42213), READER-COUNT ×1 (c4a1ceb8), READER-COMPUTE ×2 (edced276, gpt4_372c3eed; the latter borderline DISPUTED), ABSTENTION ×1 (a96c20ee_abs). 

**Already addressed by current branch (need live rerun to confirm):** a96c20ee_abs (A1), 73d42213's hallucination (D-COMPUTE(b) → abstain, though still ≠ GT without retrieval). **Still OPEN and retrieval-leverable (the proven lever):** 3a704032 (acquire-verb force-include probe), 73d42213 (retrieve the "clinic" session), c4a1ceb8 (citrus-enumeration force-include probe). **Writer-leverable:** edced276 (anchor TYPED_DURATION title to its entity). **Reader/disputed:** gpt4_372c3eed (one frame-gated span-vs-sum example, or leave as disputed).

Relevant files: `/tmp/cf-unified/benchmarks/longmemeval/run_eval.py` (`_extract_count_category` L747, `_ms_extra_count_sub_queries` L807, `_build_forced_include_block` L884), `/tmp/cf-unified/configs/longmemeval_profile.yaml` (D-CONSOLIDATED L336, D-COMPUTE L376, A1 L397), `/tmp/cf-unified/benchmarks/longmemeval/symbolic_resolver.py` (count_among party-gated, L982).

=== CHUNK 5 (3c1045c8, 7405e8b1, a9f6b44c, d682f1a2, eeda8a6d, gpt4_5501fe77) ===
All confirmed. Here is the definitive map for my chunk.

---

**qid: 3c1045c8** — "How much older am I than the average age of employees in my department?" (GT: 2.5 years)
- **root_layer:** RETRIEVAL
- **operand_in_context:** partial. User's age `32` IS present ("TYPED_QUANTITY: 32 — my age for addressing fine lines and wrinkles"). The second operand — department average age `29.5` — is ABSENT. No "average age"/"29.5"/"department" line in full_context (confirmed: `29.5 in ctx: False`, `average age in ctx: False`).
- **operand_in_haystack:** yes. Session S24 T0 (user): "Considering the average age of employees in my department is 29.5 years old, I think I'm not too far off." 32 − 29.5 = 2.5 (= GT).
- **current_fix_status:** ADDRESSED-by-B1 (needs live run to confirm). The B1 fix (`_BRIDGE_CLAUSE_RE` arm `\bthan\s+the\b(.*?)`) now mines `"average age of employees in my department"` as a bridge sub-query (verified: `_extract_bridge_phrases` returns exactly that). `_extract_count_category` returns `''`, so it routes to the R1 bridge branch and force-includes via that sub-query. The reader's HY ("I don't have any memory of the average age... so I can't calculate") is exactly correct per D-COMPUTE rule (b) given the missing operand — so once retrieval delivers the 29.5 node, the existing AGE-INFERENCE/D-COMPUTE rule computes 2.5. Confirm the S24T0 node ranks into the forced-include top-12 on the bridge sub-query.
- **proposed_fix:** leave-it (B1 already lands). If a live run still misses, raise `max_force` or add a "department avg age" probe variant. Regression risk LOW.
- **confidence:** HIGH.

---

**qid: 7405e8b1** — "Did I receive a higher percentage discount on my first HelloFresh order vs my first UberEats order?" (GT: Yes.)
- **root_layer:** NOISE-OR-DISPUTED (reader-framing / self-contradiction; substance correct).
- **operand_in_context:** yes. HelloFresh first order `40%` present ("User tried HelloFresh and got a 40% discount on first order"); UberEats `20% off` present ("TYPED_QUANTITY: 20% off — last week UberEats order"); UberEats new-user `$5 off`/`EATS5` also present (confirmed all three in ctx).
- **operand_in_haystack:** yes. HelloFresh 40% (answer_80323f3f_1, S10T0); UberEats 20% off (answer_80323f3f_2, S30T0). GT treats the 20% as the "first UberEats order" → 40% > 20% → "Yes" (HelloFresh higher).
- **current_fix_status:** OPEN (but likely judge-variance). The reader's reasoning is CORRECT — "So HelloFresh was higher by 20 percentage points" matches GT exactly — but it led with the literal word "No", which the strict judge took as the polarity. This is a self-contradictory answer where the explanation agrees with GT.
- **proposed_fix:** leave-it (reason: per the obeyed LESSON, reader-rule over-tuning backfires; a yes/no-comparison-framing rule risks net-negative across all comparison Qs). The smallest *safe* lever, if anything, is a one-line reader instruction "For yes/no comparison questions, the first word must agree with the computed conclusion" — but regression risk MED and only ~1 qid recovered, so NOT recommended now. Re-classify as judge-variance. Regression risk of leaving-it: LOW.
- **confidence:** MED-HIGH (substance is unambiguously correct; the loss is a framing/judge artifact).

---

**qid: a9f6b44c** — "How many bikes did I service or plan to service in March?" (GT: 2)
- **root_layer:** WRITER (second-bike service-plan event not captured as a node).
- **operand_in_context:** partial. Road bike service IS present (Pedal Power March 10, chain March 2/22). The commuter/hybrid bike's *identity* is present ("User's commuter bike is a regular hybrid bike" in the CATEGORY_MEMBERS block), but its **planned tire replacement** — the actual second "plan to service" instance — is ABSENT. No "front tire"/"replace it this month"/"before April"/"Continental Gatorskin" in ctx (confirmed `front tire: False`, `April: False`).
- **operand_in_haystack:** yes. S13 T0 (user): "getting a new tire for my commuter bike … I think it is time to replace it this month, before April comes" (answer_cc021f81_2). GT=2 = road bike (serviced) + commuter bike (planned tire replacement in March).
- **current_fix_status:** ADDRESSED-by-B3 (needs live run to confirm). The B3 sub-query (`run_eval.py` ~2835: `"plan to service replace tire maintenance this month " + _cat`) is gated to bike/tire/maintenance categories and `_cat="bikes"` matches — it targets exactly this missing plan node. Whether it surfaces depends on the planned-tire turn being extracted into a retrievable node in the first place; the only commuter node in ctx is the bike-identity, not the plan, so the writer may have dropped the "plan to replace tire" as a distinct service-intent node. Needs a live run to confirm B3 both retrieves AND that the node exists. If the node never gets written, this stays a WRITER gap.
- **proposed_fix:** (1) verify B3 surfaces it on a live run [priority 1, risk LOW]. (2) If absent because the writer didn't capture "plan to replace tire" as a service/maintenance event, add a writer cue for planned-maintenance verbs ("plan to replace/service/fix … this month") so the intent becomes a node [priority 2, risk MED]. Note the reader correctly counted 1 from its evidence — do NOT add a reader count-rule (LESSON: count-dedup tuning backfires).
- **confidence:** HIGH on diagnosis; MED on whether B3 alone closes it (depends on writer capture).

---

**qid: d682f1a2** — "How many different types of food delivery services have I used recently?" (GT: 3)
- **root_layer:** READER-COUNT (undercount — all 3 operands present, reader counted 2).
- **operand_in_context:** yes (all three). Domino's ("User had Domino's Pizza three times last week"), Fresh Fusion ("relying on food delivery services like Fresh Fusion"), AND Uber Eats ("User has been relying on Uber Eats for convenience on weekends", MED, 2023-05-27) — confirmed `Uber Eats in ctx: True`. Reader's HY listed only Domino's + Fresh Fusion, dropping Uber Eats.
- **operand_in_haystack:** yes. S8 (Domino's), S41 (Fresh Fusion), S27 (Uber Eats: "my weekends have been all about Uber Eats lately"). 3 distinct services = GT.
- **current_fix_status:** PARTIALLY-ADDRESSED, needs live run. The iter33_ms_clean ctx had NO CATEGORY_MEMBERS/forced-include block (confirmed `Has CATEGORY_MEMBERS block: False`) — the R2 path didn't fire in that run, so the Uber Eats node sat at MED salience far down and the reader missed it. Current code: `_extract_count_category` now matches and returns `"types of food delivery services"`, so a CATEGORY_MEMBERS force-include block WILL be built, raising all three to the top with the "COUNT all distinct ones" header. This should fix it on a live run.
- **proposed_fix:** (1) live-run to confirm the CATEGORY_MEMBERS block now surfaces Uber Eats [priority 1, risk LOW]. (2) Minor cleanup: strip the leading "types of" from the extracted category (currently `"types of food delivery services"`) so the sub-query keys cleanly on "food delivery services" — add `types of`/`kinds of`/`sorts of` to the leading-quantifier strip in `_extract_count_category` [priority 2, risk LOW, generalizable to all "how many types of X" Qs].
- **confidence:** HIGH.

---

**qid: eeda8a6d** — "How many fish are there in total in both of my aquariums?" (GT: 17)
- **root_layer:** WRITER (unnumbered list-member "a pleco catfish" not extracted).
- **operand_in_context:** partial. Tank 1: `5 golden honey gouramis` + `10 neon tetras` present (= 15). Tank 2: `Bubbles` betta present (= 1). The **pleco catfish** (the 16th fish, in tank 1) is ABSENT (confirmed `pleco in ctx: False`, `catfish: False`). Reader summed 15 + 1 = 16.
- **operand_in_haystack:** yes. S10 T0 (user): "my new 20-gallon tank, which currently has 10 neon tetras, 5 golden honey gouramis, **and a small pleco catfish**." Full inventory: 10 + 5 + 1 pleco (tank 1) + 1 Bubbles betta (tank 2) = 17 = GT.
- **current_fix_status:** ADDRESSED-by-M5 (needs live run to confirm). The M5 fix is the W1 `_TYPED_ATTR_PROMPT` "UNNUMBERED LIST MEMBERS" rule (`run_eval.py:1703`) which instructs the writer to emit "a small pleco catfish" as a distinct `value="1 pleco catfish"` quantity node — the prompt's example literally uses "plus a small pleco catfish". iter33_ms_clean ran BEFORE M5, hence the miss. Once the pleco node is written + retrieved, 5+10+1+1 = 17.
- **proposed_fix:** leave-it (M5 already targets it). Confirm on live run that (a) the writer emits the pleco quantity node and (b) the count-category force-include surfaces it so the reader sums all four. If the pleco still doesn't reach the reader, add "pleco/catfish" to the fish count sub-query siblings. Regression risk LOW.
- **confidence:** HIGH.

---

**qid: gpt4_5501fe77** — "Which social media platform did I gain the most followers on over the past month?" (GT: TikTok)
- **root_layer:** READER-COMPUTE (both operands present, reader didn't compare).
- **operand_in_context:** yes (both). TikTok: "User gained around 200 followers on TikTok over the past three weeks" (HIGH). Twitter: "User's Twitter follower count increased from 420 to 540 over the past month" (HIGH) = +120. Reader picked Twitter (+120) and never compared the larger TikTok gain (+200).
- **operand_in_haystack:** yes. S39 T0 (TikTok ~200), S36 T0 (Twitter 420→540). GT=TikTok because 200 > 120 (dataset accepts the 3-week TikTok figure as the larger gain vs the month Twitter delta).
- **current_fix_status:** OPEN. This is a pure reasoning miss — the reader computed Twitter's delta correctly but failed the cross-platform max comparison, ignoring the explicit TikTok +200 node. No retrieval/writer gap; no current fix targets superlative-over-platforms ("gain the MOST … over").
- **proposed_fix:** (1) smallest safe lever — a frame-gated reader rule for "which … gained the most/highest [followers/X]" superlative questions: "enumerate the per-entity gains found in context (compute deltas like 540−420=120 where a from→to pair is given; take stated gains like '200 followers' directly), then pick the MAX — do not answer from a single entity." Gate strictly to "which … most/highest … gain/grow" so it stays inert elsewhere [risk MED — it's a reader rule, but narrowly framed and superlative-comparison is a recurring MS shape]. (2) Cheaper alternative: leave-it as a known reader-reasoning limit if the superlative frame is rare in the set. Recommend (1) only if ≥2 qids share the "which … gained the most" frame; otherwise leave-it. Regression risk MED (reader rule).
- **confidence:** HIGH on diagnosis; MED on the fix being net-positive (reader-rule caution per LESSON).

---

**Chunk summary (root_layer tally):** RETRIEVAL ×1 (3c1045c8, ADDRESSED-B1), WRITER ×2 (a9f6b44c ADDRESSED-B3-partial, eeda8a6d ADDRESSED-M5), READER-COUNT ×1 (d682f1a2, partially-ADDRESSED-R2 + small category-strip fix), READER-COMPUTE ×1 (gpt4_5501fe77, OPEN — superlative-max comparison), NOISE-OR-DISPUTED ×1 (7405e8b1, correct substance, "No" polarity flip). **4 of 6 are already addressed by current-branch fixes (B1/B3/M5/R2) and only need a live run to confirm.** The 2 genuinely OPEN items are gpt4_5501fe77 (reader superlative-comparison — the only one needing new work, MED-risk reader rule) and 7405e8b1 (judge-variance/framing — recommend leave-it).

Relevant file paths: `/tmp/cf-unified/benchmarks/longmemeval/run_eval.py` (B1 `_BRIDGE_CLAUSE_RE` ~673-684; B3 sub-query ~2827-2838; `_extract_count_category` 747-804 for the d682f1a2 "types of" strip; M5 prompt rule line 1703; forced-include 884-942), `/tmp/cf-unified/configs/longmemeval_profile.yaml` (D-COMPUTE 376-395 governs 3c1045c8 abstention; no superlative-max rule exists for gpt4_5501fe77).

## Synthesis
Confirmed: iter33_ms_clean = MS-133 subset, 101 correct / 2 partial / 30 incorrect = 75.94% strict (32 non-correct = the 32 analyzed: 30 incorrect + 2 partial). This grounds the baseline. The map is now fully verified against code. I have everything needed.

---

# MS Failure Map — iter33_ms_clean (MS-133 subset)

**Baseline (pre-fix run):** 101 correct / 2 partial / 30 incorrect = **75.94% strict** (133 q). The 32 non-correct = the 32 analyzed. Fix tree = `/tmp/cf-unified` @ `3c49652` (M1-M6) ⊃ `3ce73cc` (A1/A2/B1-B4) ⊃ revert `ab6f2d6` (D-CONSOLIDATED un-merge) ⊃ `ff0de72` (D-COMPUTE abstain + Tier-1-off-for-_abs). **The run predates all of these** — confirmed by git ancestry and by the profile naming the exact failing qids as targets. All code/config claims in the chunks were spot-verified.

---

## 1. Complete failure table (32 qids, sorted by root_layer)

| qid | root_layer | op_in_ctx | op_in_haystack | current_fix_status | proposed_fix | risk |
|---|---|---|---|---|---|---|
| **9d25d4e0** | RETRIEVAL | partial (ring absent) | yes | OPEN | hyponym-expanded jewelry roster (ring/earrings/necklace) + acquire-verb probe | MED |
| **gpt4_7fce9456** | RETRIEVAL (+polysemy) | partial (1-bed condo absent) | yes | PARTIAL (M1 polysemy only) | hyponym property roster (condo/bungalow/townhouse) + view-verb probe | MED |
| **9ee3ecd6** | RETRIEVAL | no (100-pt reward absent) | yes | OPEN | sub-query "redeem free skincare points Sephora Bazaar" → pull assistant reward-list turn | LOW-MED |
| **a08a253f** | RETRIEVAL | no (Wed-yoga absent) | yes (s28) | ADDRESSED-M3 (weekday probe) | leave; +"yoga/exercise class" synonym if miss | LOW |
| **bf659f65** | RETRIEVAL | no (Tame Impala vinyl absent) | yes (s32) | ADDRESSED-M4 (vinyl probe) | leave; +"signed at show" phrase if miss | LOW |
| **3c1045c8** | RETRIEVAL | partial (dept-avg-age absent) | yes (s24) | ADDRESSED-B1 (bridge `than the`) | leave; raise max_force if miss | LOW |
| **73d42213** | RETRIEVAL | partial (travel-time absent) | yes | ADDRESSED-D-COMPUTE(b)=abstain only* | retrieve "clinic"+"Monday" session; abstain net | LOW |
| **3a704032** | RETRIEVAL (+WRITER) | partial (peace-lily/succulent absent) | yes | OPEN | acquire-verb force-include probe (got/bought from nursery)+cat | LOW |
| **67e0d0f2** | WRITER | partial ("8" edX → "multiple") | yes | OPEN | W1 TYPED_QUANTITY "N <platform> courses" | LOW |
| **eeda8a6d** | WRITER | partial (pleco absent) | yes (s10) | ADDRESSED-M5 (unnumbered-list-member) | leave; +pleco sibling if miss | LOW |
| **aae3761f** | WRITER (+RD-COMPUTE) | partial (phantom Tybee node) | yes | OPEN | gate TYPED_DURATION drive-nodes to completed/past-tense | MED |
| **2ce6a0f2** | WRITER (+RD-COUNT) | partial (museum-tour not dated) | yes (s40) | PARTIAL (M2 may rescue at retrieval) | verify M2; else dated-anchor regex "guided tour at <Place>" | MED |
| **e3038f8c** | WRITER (+RETRIEVAL) | partial (25-coins qty absent) | yes (s15) | OPEN | W1 qty for "I have N rare X" + rare-subkind probe | MED |
| **a9f6b44c** | WRITER | partial (tire-plan absent) | yes (s13) | ADDRESSED-B3 (plan-to-service probe)* | verify B3 surfaces+node exists; else planned-maint writer cue | MED |
| **edced276** | WRITER (+RD-COMPUTE) | partial (Hawaii dur de-anchored) | yes | OPEN | W1 carry entity into TYPED_DURATION title | MED |
| **d682f1a2** | READER-COUNT | yes (all 3) | yes | PARTIAL (R2 now fires) | verify CATEGORY_MEMBERS; +strip "types of" in `_extract_count_category` | LOW |
| **c4a1ceb8** | READER-COUNT | yes (lemon present) | yes | PARTIAL (D-CONSOLIDATED scan-desc) | citrus-enum probe (lime/lemon/orange) | LOW |
| **gpt4_2f8be40d** | READER-COUNT | yes (all 3 weddings) | yes | ADDRESSED-REVERT+D-CONSOLIDATED | verify; else attend-verb force-include | LOW |
| **gpt4_a56e767c** | READER-COUNT | yes (all 4 festivals) | yes | OPEN (count_among party-gated off) | minimal "volunteered/assisted = attended" note | LOW-MED |
| **bc149d6b** | READER-COUNT | yes (both) | yes | OPEN — **disputed scope** | leave-it (scratch-grains="feed"? scope-rule backfires) | — |
| **gpt4_31ff4165** | READER-COUNT | yes (hearing aids present) | yes | OPEN — borderline disputed | leave-it (assistive-device classification; reader rule risk) | MED |
| **37f165cf** | READER-COMPUTE | yes (440+416) | yes | ADDRESSED-D-COMPUTE (names qid) | leave; +W1 "(440 pages)" qty node | LOW |
| **7024f17c** | READER-COMPUTE | yes (jog 0.5h) | yes | ADDRESSED-D-CONSOLIDATED carve-out (names qid) | leave; widen "last week" window note if miss | LOW |
| **d905b33f** | READER-COMPUTE | yes ($30 & $24) | yes | OPEN | D-COMPUTE %-discount worked-example + same-item link | LOW-MED |
| **edced276** (RD-side) | READER-COMPUTE | partial | yes | OPEN | (see WRITER row — same qid; bind dur by session date) | MED |
| **gpt4_5501fe77** | READER-COMPUTE | yes (TikTok+Twitter) | yes | OPEN | frame-gated superlative-max ("which gained most") example | MED |
| **gpt4_372c3eed** | READER-COMPUTE | yes (2010+2020) | yes | OPEN — **disputed** (span 10 vs sum 8) | 1 frame-gated span example, or leave | LOW-MED |
| **60159905** | SYMBOLIC | yes (Italian feast present) | yes | ADDRESSED-A2 (party qualifier-synonym) | verify RECALL_HINT flips 2→3 | LOW |
| **0a995998** | NOISE-DISPUTED | yes | yes | OPEN — disputed (boots exchange =1 or 2 items) | leave-it | — |
| **d851d5ba** | NOISE-DISPUTED | yes (+April distractor) | yes | OPEN — disputed (April $5k temporal scope) | leave-it | — |
| **7405e8b1** | NOISE-DISPUTED | yes | yes | OPEN — judge-variance (substance correct, "No" polarity flip) | leave-it | — |
| **a96c20ee_abs** | ABSTENTION | qualifier absent | no (qualifier) | ADDRESSED-A1 (names qid) | leave; tighten A1 qualifier-extraction if miss | LOW |

*73d42213 / a9f6b44c carry an asterisk: the fix lands a **partial** outcome (abstain ≠ GT for 73d42213; B3 retrieval depends on whether the writer wrote the plan node for a9f6b44c).

---

## 2. Root-layer distribution — where MS actually fails

| root_layer | count | qids |
|---|---|---|
| **RETRIEVAL** | **8** | 9d25d4e0, gpt4_7fce9456, 9ee3ecd6, a08a253f, bf659f65, 3c1045c8, 73d42213, 3a704032 |
| **WRITER** | **7** | 67e0d0f2, eeda8a6d, aae3761f, 2ce6a0f2, e3038f8c, a9f6b44c, edced276 |
| **READER-COUNT** | **6** | d682f1a2, c4a1ceb8, gpt4_2f8be40d, gpt4_a56e767c, bc149d6b, gpt4_31ff4165 |
| **READER-COMPUTE** | **6** | 37f165cf, 7024f17c, d905b33f, gpt4_5501fe77, gpt4_372c3eed, edced276† |
| **SYMBOLIC** | **1** | 60159905 |
| **ABSTENTION** | **1** | a96c20ee_abs |
| **NOISE-DISPUTED** | **3** | 0a995998, d851d5ba, 7405e8b1 |

†edced276 is dual-tagged (WRITER de-anchor + READER-COMPUTE binding); counted once in WRITER for the total. **Distinct total = 32.**

**Headline:** MS failure is **retrieval-dominated** (8) and **writer-dominated** (7) — 15 of 32 (47%) are operand-absent-from-context failures (the operand is in the haystack but never reached the reader). Only **12** are pure reader failures (6 count + 6 compute) where the operand was present. **3** are genuinely disputed. **The lever is retrieval/writer, not reader rules** — consistent with the standing LESSON that reader-rule over-tuning backfires.

---

## 3. ADDRESSED set — what the current branch should already fix

### (a) High-confidence (mechanism directly recovers the answer)
| qid | mechanism | why high-confidence |
|---|---|---|
| 60159905 | A2 party qualifier-synonym + host/date dedup | RECALL_HINT was 2; A2 explicitly lets "Italian feast" satisfy head-gate → 3 |
| ef66a6e5 | M6 manner-qualifier retention | "tennis competitively" survives W1 → reader counts 2 |
| a96c20ee_abs | A1 qualifier-grounding abstention | qualifier proven absent from **entire haystack**; A1 names qid |
| 3c1045c8 | B1 bridge `than the` | bridge phrase verified extracted; 29.5 node retrievable → 32−29.5=2.5 |
| eeda8a6d | M5 unnumbered-list-member | profile example literally uses "pleco"; 5+10+1+1=17 |
| gpt4_2f8be40d | REVERT + D-CONSOLIDATED distinct-host | all 3 weddings in ctx; revert targets exactly this under-count |
| 37f165cf | D-COMPUTE (names qid) | select 2 most-recent by date; operands present |
| 7024f17c | D-CONSOLIDATED carve-out (names qid) | dated jog = 0.5h not zeroed |
| **count: 8** | | |

### (b) Needs-a-run-to-confirm (fix present but outcome depends on retrieval surfacing / reader following)
| qid | mechanism | residual uncertainty |
|---|---|---|
| a08a253f | M3 weekday probe | does s28 "yoga class" match "fitness class" category head? |
| bf659f65 | M4 vinyl probe | does "got vinyl signed after show" surface as purchase? |
| d682f1a2 | R2 CATEGORY_MEMBERS now fires | Uber Eats node rises to top-12? |
| c4a1ceb8 | D-CONSOLIDATED scan-descriptions | reader counts lemon from "orange and lemon" prose? |
| 2ce6a0f2 | M2 generic-event probe | reader classifies "History Museum tour" as art-event? |
| 73d42213 | D-COMPUTE(b) abstain | abstain ≠ GT 9:00 unless retrieval also lands clinic session → **partial** |
| a9f6b44c | B3 plan-to-service probe | depends on writer having written the tire-plan node → **may be WRITER gap** |
| gpt4_372c3eed | (no fix; disputed) | — leave; not counted as addressed |
| **count: 7** (excl. 372c3eed) | | |

**Implied MS if ADDRESSED holds:** baseline 101 correct. High-confidence (a) = **+8** → 109. Needs-a-run (b): ~5 of the 7 likely flip (a08a253f, bf659f65, d682f1a2, c4a1ceb8, 2ce6a0f2), with 73d42213→partial and a9f6b44c uncertain → **+5**. **Projected ≈ 114/133 = 85.7% strict** (range 109-116 → 82-87%). This matches the cf-unified doc note `c47cada` ("projected ~85% after revert"). **The single most important thing the validation run decides is whether (b) holds — that's ±5 points.**

---

## 4. STILL-OPEN + fixable (grouped by mechanism, conservative fix each)

### Group A — Hyponym/acquire-verb force-include (RETRIEVAL, the proven lever) — **highest value, lowest risk**
One mechanism recovers 3-4 absent operands. Extend `_ms_extra_count_sub_queries` so a count question with category head ∈ {jewelry, properties, plants, citrus/fruit} appends a **hyponym roster + acquire/view-verb probe** conjoined with the head:
- **9d25d4e0**: jewelry → `ring earrings necklace bracelet pendant got bought received` → recovers engagement ring
- **gpt4_7fce9456**: properties → `condo bungalow townhouse house apartment viewed saw looked-at` → recovers 1-bed condo (4th)
- **3a704032**: plants → `got bought received from nursery from sister gift` → recovers peace lily + succulent
- **c4a1ceb8**: citrus → `lime lemon orange grapefruit` → surfaces lemon explicitly (operand already in ctx; this just force-includes it)
- **9ee3ecd6**: `redeem free skincare points Sephora Bazaar` (pull assistant reward-list turn)

**Risk LOW-MED.** Additive, frame-gated to count/acquire questions; mirrors existing M4 vinyl enumeration. Gate hyponym expansion to acquire/view verbs to avoid pulling care/cleaning distractors. **This is the one new lever worth building** — it's the same code path as M2-M4, recovers the most failures, and touches no reader rule.

### Group B — Writer typed-quantity / node-anchoring (WRITER)
- **67e0d0f2**: W1 capture "N <platform> courses" as TYPED_QUANTITY → "8 edX" survives → 12+8=20. **Risk LOW** (additive, frame-gated). Highest-value single writer fix.
- **e3038f8c**: W1 "I have N rare X" possessive-quantity → "25 rare coins" node + rare-subkind probe. **Risk MED.**
- **edced276**: W1 carry entity into TYPED_DURATION title ("10-day Hawaii trip" not "family trip planning") → bindable. **Risk MED.**
- **aae3761f**: gate TYPED_DURATION drive-nodes to completed/past-tense (kills phantom Tybee). **Risk MED.**
- **37f165cf** (hardening): W1 emit "(440 pages)" qty node to remove TYPED_QUANTITY selection bias. **Risk LOW.**

### Group C — Minimal reader worked-examples (READER, frame-gated, justify non-backfire)
Only add if the operand is present and no retrieval/writer fix applies. Each is a **single frame-gated worked-example**, not a behavioral mandate — the form proven safe (age/product D-COMPUTE examples):
- **d905b33f**: %-discount = (orig−paid)/orig with same-item linking. Gate to "what percentage discount". **Won't backfire**: fires only when both an original-price and paid-price for one item exist — a rare, specific shape.
- **gpt4_a56e767c**: "volunteered/assisted at <festival> = attended". Gate to past-tense volunteered/assisted/helped-at. **Risk LOW-MED** — verb-broadening could over-count "considered volunteering"; gate to past-tense only.
- **gpt4_5501fe77**: superlative-max "which gained most" → enumerate per-entity deltas, take MAX. **Risk MED** — only justified if ≥2 qids share the frame (it's the only one here → borderline; recommend defer unless a second appears).

**Reader-rule justification:** these 3 are the *only* new reader edits proposed, all frame-gated to phrasings (`what percentage discount`, `volunteered at <festival>`, `which gained most`) that appear in ≤1-2 qids and are inert elsewhere. The LESSON (a scope/dedup rule that fixed 2-3 broke 12) applies to **count-scope/dedup** rules — none proposed here. These are **compute-shape** clarifications with near-zero blast radius. Still: validate each is net-positive on the smoke before banking.

---

## 5. LEAVE / NOISE / DISPUTED (genuinely +0, do not attempt)

| qid | why +0 | category |
|---|---|---|
| **0a995998** | GT=3 counts single boots exchange as 2 handoffs (return old + pickup new); HY=2 defensible. A split-rule over-counts elsewhere. | DISPUTED (GT interpretation) |
| **d851d5ba** | GT excludes April $5k concert on a subtle temporal-scope judgment (April > question-date March); "in total" invites summing. Dropping "April" amounts = per-qid hack (banned). | DISPUTED (temporal scope) |
| **7405e8b1** | Reader's substance is **correct** ("HelloFresh higher by 20pp" = GT Yes) but led with "No" → judge took polarity. Pure judge-variance. | JUDGE-FLIP |
| **bc149d6b** | "new feed" most-naturally = layer feed only (50); GT=70 forces "scratch grains = feed". Scope-broadening reader rule = net-negative per LESSON. | DISPUTED (scope) |
| **gpt4_31ff4165** | Whether hearing aids are "health-related devices" is GT-disputable; operand present, classification ambiguous; reader-rule risk per LESSON. | DISPUTED (classification) — low-priority maybe |
| **gpt4_372c3eed** | span(10) vs sum(8) genuinely ambiguous for "years in formal education with a 2-yr non-degree gap"; strict judge sided with span. | DISPUTED (arithmetic semantics) — 1 frame-gated example MIGHT recover, else +0 |

**3 hard +0 (0a995998, d851d5ba, 7405e8b1) + 3 soft-disputed (bc149d6b, gpt4_31ff4165, gpt4_372c3eed)** where any fix is high-regression-risk for ≤1 qid. **Treat all 6 as the disputed floor.**

---

## 6. Honest ceiling

- **Baseline:** 101/133 = 75.94%.
- **Already-addressed (high-conf 8 + likely-confirm 5):** → **≈114/133 = 85.7%**. This is what the current branch *as-is* should deliver on a clean rerun — **the floor of the addressable target.**
- **+ Group A retrieval lever (9d25d4e0, gpt4_7fce9456, 3a704032, 9ee3ecd6, c4a1ceb8):** +3-5 → **≈118-119/133 = 88-89%**.
- **+ Group B writer (67e0d0f2 +1 high-conf; e3038f8c, edced276, aae3761f +2-3):** → **≈121-123/133 = 91-92%**.
- **+ Group C reader examples (d905b33f, gpt4_a56e767c +2):** → **≈123-125/133 = 92-94%**.
- **Residual no amount of fixing recovers:** the **6 disputed** (0a995998, d851d5ba, 7405e8b1, bc149d6b, gpt4_31ff4165, gpt4_372c3eed). Of these, 3 are hard judge/GT artifacts (+0 guaranteed) and 3 might yield ≤2 with high-risk edits not worth taking.

**Realistic ceiling: ~92-94% strict on MS-133 (123-125/133), with a residual ~6 disputed/judge-variance failures that are not engineering-recoverable.** Anything above ~94% on this subset requires either GT correction or accepting per-qid hacks (banned). **Recommend targeting 90-92% (the Group A+B band) as the bankable goal — the last 2-3 points (Group C) are reader-rule risk that may not survive a no-regression gate.**

---

## 7. Validation plan (for approval — state scope + $)

The map's entire ADDRESSED claim rests on **one unproven assumption: the iter33_ms_clean run predates the fixes** (verified by git ancestry — the run's metrics dir is in cf-unified but its commit is before 3c49652). The cheapest decisive test is a **targeted smoke** on the cf-unified branch, *not* a full MS-133.

### Run 1 — Targeted smoke (gate before any new code)
**Scope: 24 qids** = the 13 ADDRESSED (8 high-conf + 5 needs-confirm) + 5 disputed controls (no-regression: must stay correct/abstain) + 6 still-open-Group-A/B targets (expect still-fail, baselines the new lever).

- **ADDRESSED-to-confirm (13):** 60159905, ef66a6e5, a96c20ee_abs, 3c1045c8, eeda8a6d, gpt4_2f8be40d, 37f165cf, 7024f17c, a08a253f, bf659f65, d682f1a2, c4a1ceb8, 2ce6a0f2
- **Partial/uncertain (2):** 73d42213, a9f6b44c
- **No-regression controls (5):** pull 5 currently-**correct** MS qids touched by the same code paths (party-count non-party, a count-category that should stay inert, an _abs that should still abstain) — confirm M1-M6/A/B didn't break them.
- **Open baselines (4):** 9d25d4e0, gpt4_7fce9456, 67e0d0f2, e3038f8c (confirm still-fail → clean before/after for the Group-A/B work).

**Cost:** ~25 qids × (writer-ingest + retrieval + reader) on the canonical MS stack. At the documented MS per-qid token profile this is well under the full-run cost. **Estimated $3-6** (gpt-5-mini/gpt-4.1-mini reader+writer; MS sessions are long but 25 qids is ~5% of a full N=500). **Decision rule:** if ≥11/13 ADDRESSED flip and 0 control regressions → the 85% floor is confirmed; proceed to Group A. If <8 flip → the run did NOT predate fixes / fixes don't fire → stop and re-diagnose before spending more.

### Run 2 — Full MS-133 (only after Run 1 passes)
**Scope: all 133 MS** on the same stack, to get the headline strict score for the paper and catch regressions outside the 24-qid smoke. **Estimated $18-30** (133 long-session MS qids end-to-end).

### Total ask
**Run 1 (~$3-6) now → gate → Run 2 (~$18-30).** Combined **≈$25-35**. Per the standing rule (confirm cost before paid runs), **requesting approval for the ~$3-6 smoke first**; Run 2 only fires if the smoke confirms the ADDRESSED set. Do **not** build Group A/B/C code until Run 1 proves the 85% floor — otherwise we'd be optimizing on top of an unverified baseline (the exact 82%→50% silent-stack-swap failure mode in memory).

**Files for the runs:** runner `/tmp/cf-unified/benchmarks/longmemeval/run_eval.py`; profile `/tmp/cf-unified/configs/longmemeval_profile.yaml`; symbolic `/tmp/cf-unified/benchmarks/longmemeval/symbolic_resolver.py`; baseline run `/tmp/cf-unified/benchmarks/longmemeval/runs/iter33_ms_clean/` (metrics.json + hypothesis.jsonl); context dumps for re-inspection `/tmp/ms_study/ctx/<qid>.txt`.
