# MS Round 8 R5 — Fresh Plan (User Refused R4)

User REFUSED R4's "86-89% MS realistic" ceiling. Constraints:

- **Budget**: $100 commonstack
- **Parallel**: 3p (slower but minimal 429 risk)
- **Target**: 94% MS on N=133 = 125/133 = +22 wins from iter27
- **Last paid run** — must make it count

User wants YOU to lead with a FRESH plan. Forget R1-R4. Brainstorm
ALL angles to push MS higher. I'll critique + we iterate ≥3 rounds.

## Fresh thinking — angles you haven't explored

### Angle 1: Property second-pass pattern transferred to MS

Round 7's property_second_pass for gpt4_7fce9456 (TR) was the
template:
1. Question matches narrow shape regex
2. Lexicon-expanded BM25 over EVENT + CONCEPT graph reservoirs
3. Boost completed-action verbs, penalize advice/planning
4. Inject rows that the baseline retrieval missed

Could you implement **N similar "second pass" retrieval expansions
for the MS-A undercount cluster**? E.g.:
- `count_items_second_pass` for clothing/jewelry/furniture/album
  undercount cases — wider chunk extraction with class lexicons
- `count_events_second_pass` for dinner parties / art events /
  graduations — narrower than property, but same shape

Would this help recover the MS-A cases we currently can't fix
via direct emitters?

### Angle 2: Question-shape COUNT_CANDIDATES helper

You mentioned in R5 (TR): "the middle ground I do like is a generic
COUNT_CANDIDATES helper that augments context, but not a generic
direct-answer emitter."

For MS specifically: when shape is `count`, surface ALL candidate
rows that contain the asked entity-class in user-role + completed-
action context. This is a context augmentation — reader still
answers. Lower regression risk than direct emit.

Would this fire on most MS-A undercount cases? What's the design?

### Angle 3: Reader prompt micro-rules — are we sure they're poison?

iter29 disaster was +200 lines of qa_answer rules causing MS -27pp.
But iter32 R7 added 4 narrow rules with NO observed regression (we
ran 42 qids R7 TR-only with various rules in place).

Could we add 5-8 NARROW one-liner MS rules that target specific
clusters? E.g.:
- "When question asks 'how many X in Y window', count ONLY explicit
  user-role X mentions with date in Y window"
- "When question asks about 'currently' active subscription/service/
  membership, exclude items with cancellation in user-role rows"
- "When question asks for total Z, sum ALL explicit user-stated Z
  values; do not estimate"

Even 2-3 high-precision rules might lift 3-5 cases. Risk vs upside?

### Angle 4: Per-qid LIVE inspection emitter

Instead of writing N emitters, write ONE LLM-assisted emitter:
- For shape=count questions, BEFORE the main reader, do a
  short LLM call to a CHEAP model (gpt-5.4-mini at LOW effort)
  asking "list each X in the context with its date"
- Parse the response
- Count distinct items
- Cap N=500 spurious risk by only emitting if confidence is iron-clad

You said in R5 (TR): "no internal LLM sub-call". But maybe for MS
the trade-off is different — MS is heterogeneous and per-case
emitters can't cover all 22 needed flips. An LLM-extract sub-call
is the "PAL with reject" approach.

What's the catch?

### Angle 5: Stack rollback to iter19's writer prompt

iter27 had MS 77.4% — iter19 had MS 82%. The difference is W1+W2.
We've turned W1/W2 OFF in iter31 stack, but the WRITER PROMPT
itself is from iter27 (with iter31's rule 4 added). Did iter19's
writer prompt extract MS-relevant entities BETTER than iter27's?

Could we revert iter27 writer prompt changes (keeping only iter31
rule 4) and gain MS quality? Or is that out of scope?

### Angle 6: Anything else?

What angle have I NOT mentioned that you think could lift MS by
3-5 more cases?

## Ask

Forget R4's ship list. Give me your **fresh plan with budget
$100, 3p constraint, 94% aspirational**.

Output sections:
1. **Architecture decision**: which of the 6 angles to use (or new
   angles you propose)
2. **Per-case fix map**: 30 MS wrongs, what each is targeted by
3. **Realistic projection**: honest MS % with all proposed changes
4. **Implementation order**: most impactful first
5. **Risk assessment**: where regressions could come from

I will critique and we iterate. ≥3 more rounds before sign-off.

Be brutal. We have one shot. User's not accepting "86%".

Max effort.
