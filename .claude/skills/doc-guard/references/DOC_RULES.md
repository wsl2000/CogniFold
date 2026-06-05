# Doc-Guard: Change-to-Documentation Mapping Rules

This file defines which documentation files must be updated based on code changes.

---

## Always Required

These docs must reflect any meaningful code change in the branch:

| Doc File | What to Update |
|----------|---------------|
| `docs/RESUME.md` | "Completed in This Session" list, "Current Phase", "Next Steps" |
| `docs/CHANGELOG.md` | New entry with date, changes summary, files modified, test status |

### RESUME.md Format

```markdown
## Last Updated
YYYY-MM-DD

## Current Phase
Phase X.Y: [Name]

## Completed in This Session
- Task 1
- Task 2

## In Progress
- Current task description

## Next Steps
1. Next task
2. Following task
```

### CHANGELOG.md Format

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

---

## Conditional Mappings

Update these docs only when the matching change patterns are detected:

### Service & API Changes

| Change Pattern | Required Doc |
|---|---|
| `src/cognifold/service/` | `docs/SERVICE_API.md` |
| New/changed API endpoints | `docs/SERVICE_API.md` — add request/response schemas |
| HTTP status codes changed | `docs/SERVICE_API.md` |

### Agent & Prompt Changes

| Change Pattern | Required Doc |
|---|---|
| `src/cognifold/agent/prompts*` | `docs/PROMPTS.md` |
| `src/cognifold/agent/*.py` (prompt logic) | `docs/PROMPTS.md` |
| New domain configs | `docs/PROMPTS.md` |

### CLI Changes

| Change Pattern | Required Doc |
|---|---|
| `src/cognifold/cli/` | `CLAUDE.md` — CLI Commands section |
| New subcommand added | `CLAUDE.md` — CLI Commands section |
| CLI argument changes | `CLAUDE.md` — CLI Commands section |

### Architecture Changes

| Change Pattern | Required Doc |
|---|---|
| New directory under `src/cognifold/` | `CLAUDE.md` — Module Structure section |
| New directory under `src/cognifold/` | `docs/ARCHITECTURE.md` |
| Major data flow changes | `docs/ARCHITECTURE.md` |
| New node/edge types | `CLAUDE.md` — Core Concepts section |

### Schema Changes

| Change Pattern | Required Doc |
|---|---|
| `src/cognifold/models/` (Event schema) | `CLAUDE.md` — Event Schema section |
| `src/cognifold/models/` (UpdatePlan) | `CLAUDE.md` — Update Plan Schema section |
| New Pydantic models | `docs/ARCHITECTURE.md` |

### Phase & Planning Changes

| Change Pattern | Required Doc |
|---|---|
| Phase status change | `docs/PHASES.md` — Phase Status Overview table |
| Phase completion | `docs/PHASES.md` — move spec to Completed section |
| Phase completion | `CLAUDE.md` — Current Status section |

### Dependency Changes

| Change Pattern | Required Doc |
|---|---|
| `pyproject.toml` (new dependency) | `CLAUDE.md` — Tech Stack section |
| `pyproject.toml` (removed dependency) | `CLAUDE.md` — Tech Stack section |

### Workflow & Standards Changes

| Change Pattern | Required Doc |
|---|---|
| `.claude/commands/` or `.claude/skills/` | `CLAUDE.md` — Slash Commands section |
| `Makefile` changes | `docs/AGENT_PROTOCOL.md` — Quality Gates |
| Test infrastructure changes | `docs/CONTRIBUTING.md` |
| New coding patterns/conventions | `docs/CONTRIBUTING.md` |

### README.md (Public-Facing Overview)

`README.md` is the standalone public-facing documentation. It should be self-contained — a reader should understand the project without needing to open any other file.

| Change Pattern | Required Section | Notes |
|---|---|---|
| Phase completion | Development Status table | Update status to "Complete" |
| New module under `src/cognifold/` | Project Structure tree | Add the directory with one-line description |
| New CLI subcommand | Quick Start examples | Only if it's a primary workflow command |
| New API endpoint category | HTTP Service endpoints table | Only new categories, not every route |
| New retrieval mode | Retrieval Modes table | Add row with description and dependencies |
| New node or edge type | Core Concepts tables | Add row |
| New domain | Supported Domains table | Add row |
| New dependency (major) | Tech Stack table | Only significant additions, not transitive deps |
| Major stats change (files, LOC, tests) | Header stats line | Update `**N source files | Nk LOC | N tests | N modules**` |

**Conciseness rule**: README should be concise but self-contained. Keep each section focused — enough to understand the project fully without opening other files, but no unnecessary verbosity.

### Wishlist & Roadmap

| Change Pattern | Required Doc |
|---|---|
| Wishlist item implemented | `docs/WISHLIST.md` — mark as done or remove |
| Query/memory improvement done | `docs/WISHLIST_QUERY_MEMORY.md` — update status |
| Benchmark work | `docs/BENCHMARK.md` + `docs/benchmark/results.md` |

---

## CLAUDE.md Sections Reference

These specific sections in CLAUDE.md may need updates:

| Section | Trigger |
|---------|---------|
| Module Structure | New/renamed directory under `src/cognifold/` |
| CLI Commands | New subcommand, changed arguments, new examples |
| Event Schema | Changed Event model fields |
| Update Plan Schema | Changed UpdatePlan model fields |
| Core Concepts (Node Types) | New node type added |
| Core Concepts (Edge Types) | New edge type added |
| Core Concepts (Context Window) | Changed context allocation |
| Tech Stack | New/removed dependency |
| Current Status | Phase completion or change |
| Slash Commands | New skill or command added |
| Quick Start for Agents | Changed onboarding files |
| Documentation Index | New doc file added |

### Cognition Principles Alignment

| Change Pattern | Required Doc |
|---|---|
| `src/cognifold/agent/` (non-prompt changes) | `docs/COGNITION_PRINCIPLES.md` — verify Cognitive Folding alignment |
| `src/cognifold/query/` | `docs/COGNITION_PRINCIPLES.md` — verify no RAG Wrapper anti-pattern |
| `src/cognifold/graph/` | `docs/COGNITION_PRINCIPLES.md` — verify Cognitive Assets preserved |
| `src/cognifold/scoring/` | `docs/COGNITION_PRINCIPLES.md` — verify multi-signal scoring |
| `src/cognifold/intent/` | `docs/COGNITION_PRINCIPLES.md` — verify Intention Emergence lifecycle |

---

## Evaluation Guidelines

When deciding if a doc "needs update":

1. **Modified but incomplete**: If a doc file IS in the diff but doesn't cover all required changes, it still needs update
2. **No changes needed**: If the mapping rule triggers but the existing doc content already accurately describes the current state, mark as up-to-date
3. **Test-only changes**: If only test files changed, RESUME.md and CHANGELOG.md are still required, but other docs typically don't need updates
4. **Config-only changes**: Ruff/pyright config changes don't need doc updates beyond CHANGELOG.md
5. **Doc-only changes**: If only docs changed (no code), RESUME.md and CHANGELOG.md still need to reflect the doc work
