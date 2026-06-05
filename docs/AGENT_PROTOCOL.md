# Agent Collaboration Protocol

This document defines **strict rules** for all AI agents (Claude Code, etc.) working on the Cognifold codebase. Following this protocol ensures consistent quality and enables seamless collaboration.

---

## Pre-Flight Checklist (MANDATORY)

Before writing ANY code, agents MUST:

### 1. Check for Unmerged Remote Branches

Run this check before starting any coding work:

```bash
# Fetch all remote branches
git fetch --all

# List remote branches ahead of cognifold-dev (not yet merged)
git branch -r --no-merged origin/cognifold-dev
```

**If unmerged branches exist:**
- List them to the user with their last commit info
- **ASK FOR CONFIRMATION** before proceeding
- User may want to review/merge those branches first to avoid duplicate work or conflicts

Example warning:
```
⚠️ Found unmerged branches ahead of cognifold-dev:
  - origin/phase9 (3 commits ahead, last: "feat(intent): add action queue")
  - origin/feature-xyz (1 commit ahead, last: "fix: typo in query")

These may contain work that should be merged first.
Do you want to proceed anyway? [y/N]
```

### 2. Read Required Files (in order)

| Order | File | Purpose |
|-------|------|---------|
| 1 | `CLAUDE.md` | Project overview and file references |
| 2 | `docs/AGENT_PROTOCOL.md` | **This file** - Strict rules for all agents |
| 3 | `docs/RESUME.md` | Current work-in-progress and next steps |
| 4 | `docs/CHANGELOG.md` (last 50 lines) | Recent changes and context |
| 5 | `docs/PHASES.md` | Current phase specifications |

**Skip reading full files if resuming an active session where context is already loaded.**

---

## Quality Gates (MUST PASS)

Every code change MUST pass these checks before committing:

```bash
# 1. Format check
ruff format --check src/ tests/

# 2. Lint check
ruff check src/ tests/

# 3. Type check
pyright src/

# 4. Tests
pytest tests/ -v
```

**If any check fails, fix before proceeding. NEVER commit broken code.**

Quick commands:
```bash
make check       # Runs ruff lint + format check only
make typecheck   # Runs pyright
make test        # Runs pytest
make quality     # Runs check + test (but not pyright)

# Or run all four checks manually:
ruff format --check src/ tests/ && ruff check src/ tests/ && pyright src/ && pytest tests/ -v
```

---

## Commit Protocol

### When to Commit
- After EVERY small, completed task (one feature, one fix, one test addition)
- Before switching to a different file or component
- After fixing a bug or issue
- Before any risky or experimental change

### Commit Message Format
```
<type>(<scope>): <what was done>

<why it was done - 1-2 sentences>

Phase: X.Y
```

**Types**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

**Examples**:
```
feat(retrieval): add BM25 keyword scoring

Implement BM25 algorithm with inverted index for keyword-based
document retrieval. Supports term frequency and IDF weighting.

Phase: 10.4
```

```
fix(embeddings): resolve numerical overflow in mock provider

MockEmbeddingProvider was producing inf values due to exp() overflow.
Fixed by using numpy random generator with bounded values.

Phase: 10.3
```

### Git Safety Rules
- **NEVER** push directly to `main` or `cognifold-dev`
- **NEVER** use `--force` push unless explicitly asked
- **NEVER** skip hooks (`--no-verify`) unless explicitly asked
- **NEVER** amend commits after push
- **ALWAYS** use phase branches (e.g., `phase10`, `phase11`)

---

## Progress Tracking

### During Work
1. Use `TodoWrite` to track multi-step tasks
2. Mark todos as completed immediately when done
3. Keep only ONE todo as `in_progress` at a time

### Before Context Compression or Session End

**IMMEDIATELY update these files**:

1. **`docs/RESUME.md`** - Current state:
   ```markdown
   # Resume Point

   ## Last Updated
   YYYY-MM-DD

   ## Current Phase
   Phase X.Y: [Name]

   ## Completed in This Session
   - Task 1
   - Task 2

   ## In Progress
   - Current task and exact state
   - File being worked on

   ## Next Steps
   1. Immediate next task
   2. Following task

   ## Quick Commands
   # Commands to resume or test
   ```

2. **`docs/CHANGELOG.md`** - Append entry:
   ```markdown
   ## [YYYY-MM-DD HH:MM] - Brief Title

   ### Changes
   - What was added/modified/removed

   ### Files Modified
   - `path/to/file.py` - description

   ### Tests
   - Added/updated tests: yes/no
   - All tests passing: yes/no
   ```

3. **Commit WIP if meaningful uncommitted changes exist**:
   ```bash
   git add -A && git commit -m "wip: <description of current state>"
   ```

---

## Branch Strategy

```
main              # Stable releases only (never push directly)
cognifold-dev     # Main development branch (PR target)
phase<N>          # Phase-specific branches (e.g., phase10, phase11)
```

### Workflow
1. Create/checkout phase branch from `cognifold-dev`
2. Make commits on phase branch (follow commit protocol)
3. Push regularly to remote phase branch
4. Create PR to `cognifold-dev` when phase complete

### PR Requirements
- Run `/doc-guard` before creating a PR to ensure all docs are in sync
- All quality gates must pass
- Clear description referencing Phase
- Link to related issues if any
- Request review for significant changes

---

## Testing Requirements

**Every feature or bug fix MUST include tests.**

### Test Structure (AAA Pattern)
```python
def test_<unit>_<scenario>_<expected_result>():
    # Arrange - Set up test data
    # Act - Execute behavior
    # Assert - Verify outcome
```

### Coverage Expectations
- All public functions have at least one test
- Happy path + 2 edge cases per function
- Error cases are tested

### Test Commands
```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/unit/test_<module>.py -v

# Run with coverage
pytest tests/ --cov=src/cognifold --cov-report=term
```

---

## Code Standards

### Python Requirements
- Python 3.9+ compatibility
- Type hints on ALL public functions
- Pydantic for data validation schemas
- NetworkX for graph operations

### Style
- Line length: 100 chars max
- Use `ruff` for formatting and linting
- Use `pyright` for type checking

### Documentation
- Docstrings for public functions (brief, not verbose)
- Comments only where logic isn't self-evident
- NO auto-generated READMEs or documentation files

### Principles
- **Minimal changes**: Only change what's needed for the task
- **No over-engineering**: Simple solutions preferred
- **No speculation**: Don't add features "for later"
- **Clean deletions**: Remove unused code completely, no `_unused` vars

---

## Deferring Work

If a task cannot be completed or should be postponed:

1. Add to `docs/WISHLIST.md`:
   ```markdown
   ### Feature/Issue Name
   **Problem**: Brief description
   **Proposed Solution**: High-level approach
   **Why Deferred**: Reason for deferral
   **Context**: Any relevant notes or partial work
   ```

2. Note deferral in `docs/RESUME.md` under "Next Steps"

---

## File References

| File | Purpose | When to Read |
|------|---------|--------------|
| `CLAUDE.md` | Project overview, entry point | Always first |
| `docs/AGENT_PROTOCOL.md` | This file - collaboration rules | Always |
| `docs/RESUME.md` | Current work state | Before starting |
| `docs/CHANGELOG.md` | Change history | Before starting |
| `docs/PHASES.md` | Phase specifications (current + completed) | When implementing |
| `docs/ARCHITECTURE.md` | System design | When needed |
| `docs/PROMPTS.md` | Prompt engineering | When needed |
| `docs/WISHLIST.md` | Deferred work | When planning |
| `docs/CONTRIBUTING.md` | Code standards detail | When needed |
| `pyproject.toml` | Dependencies, tools | When needed |

---

## Workflow Summary

```
1. READ: CLAUDE.md -> RESUME.md -> CHANGELOG.md (last 50 lines)
2. UNDERSTAND: Current state and next steps
3. PLAN: Use TodoWrite for multi-step tasks
4. CODE: With types, tests, following standards
5. VERIFY: ruff format, ruff check, pyright, pytest
6. COMMIT: Immediately after each small task
7. LOG: Update CHANGELOG.md (can batch at session end)
8. RESUME: Update RESUME.md with current state
```

---

## Emergency Protocol

If you encounter:
- **Broken tests**: Fix before proceeding, don't skip
- **Merge conflicts**: Ask user for guidance
- **API rate limits**: Note in WISHLIST.md, continue with other tasks
- **Missing dependencies**: Add to pyproject.toml, document in CHANGELOG

---

## Questions?

If unclear about:
- Requirements: Ask the user
- Architecture: Read docs/ARCHITECTURE.md
- Previous decisions: Read docs/CHANGELOG.md
- Phase specs: Read docs/PHASES.md
