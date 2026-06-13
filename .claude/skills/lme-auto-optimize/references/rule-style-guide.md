# Rule Style Guide

Rules go into two places — `configs/longmemeval_profile.yaml`
(reader/qa_answer) and `src/cognifold/agent/batch.py` (writer
BATCH_SYSTEM_PROMPT). Both share the same style:

## The 8 principles

### 1. One rule = one cluster

Each rule targets ONE failure cluster from the taxonomy
(`failure-taxonomy.md`). If a single rule body addresses TR-A and
TR-B, split it into two — that way you can measure each cluster's
delta independently in apples-compare.

### 2. Cite the qid

Every rule must end with `(case <qid>)`. The qid is from the iter
that motivated the rule. Without a qid the rule is unfalsifiable —
no way to tell if it's still pulling its weight, no way to delete
when the underlying failure mode has been fixed structurally.

Good: `... and exclude the anchor from the count. (case a3838d2b)`
Bad:  `... and exclude the anchor from the count. (general)`

### 3. Worked example uses real wrong-case data

If the rule has a worked example block, the question + context
fragment must be lifted verbatim from the actual qid's
`full_context`. Synthesized examples ("e.g., you said you started
jogging on 2023-01-01") rot — when the writer prompt or data
distribution shifts, fake examples mislead the reader. Real cases
are anchored to a stable benchmark.

### 4. Hard 12-line limit per rule

iter29a added 7 rules totalling +200 lines to qa_answer; net result
was MS −27pp because the reader started over-applying rules in
spurious contexts. The 12-line ceiling forces compression and
prevents the "rule keyword bleeds into unrelated questions" failure.

If a rule needs more than 12 lines, it usually means:
- It actually contains two rules (split it)
- It is restating background already in the system prompt (delete the restatement)
- It is enumerating cases instead of stating the principle (collapse)

### 5. Negative form preferred for restraint rules

When telling the reader NOT to do X, lead with "DO NOT" /
"NEVER", not "AVOID" / "TRY NOT TO". Soft language gets ignored
under reasoning pressure. Examples:
- ✅ "NEVER answer with 'I don't have a memory of' if the context
  shows X — derive the answer instead. (case ...)"
- ❌ "Try to avoid refusing when X is in context. (case ...)"

### 6. Worked examples come AFTER the rule, not before

Lead with the principle in 1-2 lines, then "Worked example:" with
the qid. Putting the example first makes the reader pattern-match
on surface features of the example rather than apply the
principle.

### 7. Cross-reference clusters when they overlap

Some clusters overlap (TR-A ⊂ TR-E refusal-with-data; MS-B ⊂
MS-A undercount). When that's the case, the rule body should say
"Related: TR-E refusal-with-data" — that way a future iter
considering removing one rule sees the dependency.

### 8. Anti-bloat enforcement

Before adding a new rule, count the existing rules in the file:

```bash
grep -c "^iter[0-9]\+ " configs/longmemeval_profile.yaml
```

If the count is >20, the file is overloaded — strongly prefer
modifying an existing rule (with a justification comment) over
adding a new one. iter27 qa_answer had 12 rules; the iter29a bloat
that broke MS went to 18.

## Forbidden patterns

- **Long preamble**: "Recall that the user has been jogging..." —
  the reader already sees that in the context block. Get to the
  imperative.
- **Multi-paragraph rules**: each rule is one paragraph max.
- **Synonyms as separate rules**: "When the user says 'started'
  X / 'began' X / 'picked up' X..." — collapse into one rule with
  the verb list in a parenthetical.
- **Reasoning hints without the imperative**: "(Note: this is
  because the writer extracts the most recent date)" — explain in
  the commit message, not in the rule.
- **Iter-number references in rule body**: "as in iter27..." — the
  rule must work standalone. Iter context goes in the qid.

## Anti-examples (do not imitate)

- iter29a `qa_answer` lines 88-310 (later reverted in iter29b):
  +200 lines, MS −27pp. The bloat included rules that overlapped
  with iter27's still-active rules, causing double-application.
- iter30 `qa_answer` "compression pass": removed iter02, iter10,
  iter13 worked examples without per-case verification. MS −1.5pp
  because those examples were still firing for unrelated cases.

## When in doubt

Smaller is better. A non-existent rule beats a misleading one. The
reader fails closed (refuses or guesses) when no rule fires; it
fails open (applies wrong rule to wrong case) when a misleading
rule fires. The latter is harder to debug.
