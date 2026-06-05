---
name: doc-guard
description: >
  Documentation completeness checker for Cognifold PRs. Analyzes git diff
  to determine which docs need updating. Use when creating a pull request,
  before merging, or when making significant code changes.
argument-hint: "[check]"
---

# Doc-Guard: Documentation Completeness Checker

Ensures all documentation stays in sync with code changes before PR creation.

## Mode

- `/doc-guard` — Full mode: analyze, report, and fix any documentation gaps
- `/doc-guard check` — Check-only mode: analyze and report without making changes

## Current Branch Analysis

!`bash .claude/skills/doc-guard/scripts/check_docs.sh`

## Instructions

Follow these phases in order. Read [references/DOC_RULES.md](references/DOC_RULES.md) for the complete change-to-doc mapping rules.

### Phase 1: Analyze

The shell output above shows:
- Base branch and commit range
- Changed files categorized by type (source, tests, config, docs)
- Which doc files are already modified vs unchanged
- Detected patterns (new modules, CLI changes, API changes, etc.)
- Recent commit messages

### Phase 2: Evaluate

Apply the rules from DOC_RULES.md to determine which docs need updates:

1. **Always required**: Check if RESUME.md and CHANGELOG.md reflect the changes
2. **Conditional**: Match changed file paths against the mapping table
3. **Phase changes**: If commits reference a phase, check PHASES.md status
4. **New patterns**: If new modules/dirs appear under `src/cognifold/`, check CLAUDE.md Module Structure and ARCHITECTURE.md

### Phase 3: Report

Output a checklist. Use this exact format:

```
## Doc-Guard Report

**Branch**: <current> -> <base>
**Commits**: <count> commits analyzed

### Documentation Status
- [x] `RESUME.md` — up to date
- [ ] `CHANGELOG.md` — NEEDS UPDATE (missing entries for: <summary>)
- [x] `ARCHITECTURE.md` — no update needed
- [ ] `SERVICE_API.md` — NEEDS UPDATE (new endpoint added in service/)
...

### Summary
<N> of <total> docs need attention.
```

Mark a doc as `[x]` if:
- It was already modified in the branch AND the modifications cover the changes, OR
- No rules from DOC_RULES.md require it to be updated

Mark a doc as `[ ] NEEDS UPDATE` if:
- Rules require an update but the file is unchanged, OR
- The file was modified but doesn't cover all required changes

If `$ARGUMENTS` contains "check", **stop here** and do not proceed to Phase 4.

### Phase 4: Fix

For each doc marked `[ ] NEEDS UPDATE`:

1. Read the current file content
2. Determine what needs to be added or changed based on the code diff
3. Apply the edits using the Edit tool
4. Follow the format requirements specified in DOC_RULES.md

**Important**: Make minimal, targeted edits. Do not rewrite sections that are already correct.

### Phase 5: Verify

After fixes:
1. Re-run the analysis: `bash .claude/skills/doc-guard/scripts/check_docs.sh`
2. Confirm all items now show `[x]`
3. Output the final updated checklist
4. Write sentinel to allow commits: `date +%s > .claude/docguard_last_run`
