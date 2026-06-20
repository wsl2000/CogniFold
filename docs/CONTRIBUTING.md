# Contributing to Cognifold

Guidelines for contributing code to the Cognifold project.

---

## Quick Start

1. Read `CLAUDE.md` for project overview
2. Read `docs/AGENT_PROTOCOL.md` for workflow rules
3. Read `docs/RESUME.md` for current state
4. Run `make check` to verify setup

---

## Language & Tooling

| Aspect | Requirement |
|--------|-------------|
| Language | Python 3.9+ (target 3.11+) |
| Package Manager | `uv` (preferred) or `pip` |
| Type Hints | Required on all public functions |
| Linting | `ruff` (lint + format) |
| Type Checking | `pyright` |
| Testing | `pytest` |

---

## Code Quality Gates

**Every change MUST pass before committing:**

```bash
# Format
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type check
pyright src/

# Tests
pytest tests/ -v
```

Or use the shortcut:
```bash
make check
```

---

## Testing Requirements

**Every feature or bug fix MUST include tests.**

### When to Write Tests
- **New feature**: Write tests BEFORE or ALONGSIDE implementation
- **Bug fix**: Write a failing test that reproduces the bug FIRST
- **Refactor**: Ensure existing tests pass; add tests for coverage gaps

### Test Structure (AAA Pattern)

```python
def test_<unit>_<scenario>_<expected_result>():
    # Arrange - Set up test data
    graph = Graph()
    node = Node(id="n-001", type="event", data={"title": "Test"})

    # Act - Execute behavior
    graph.add_node(node)

    # Assert - Verify outcome
    assert graph.has_node("n-001")
    assert graph.get_node("n-001").data["title"] == "Test"
```

### Test Organization

```
tests/
├── unit/           # Fast, isolated tests (mock external dependencies)
├── integration/    # Tests with real dependencies (graph + scoring)
├── fixtures/       # Shared test data and factories
└── conftest.py     # Shared fixtures
```

### Coverage Expectations
- **Minimum**: All public functions have at least one test
- **Target**: Happy path + 2 edge cases per function
- **Critical**: Graph operations, scoring, executor need thorough coverage

### Test Quality Checklist
- [ ] Tests are deterministic (no flaky tests)
- [ ] Tests are independent (can run in any order)
- [ ] Tests are fast (mock external services)
- [ ] Test names clearly describe what is tested
- [ ] Edge cases covered (empty input, None, boundaries)
- [ ] Error cases tested (invalid input, missing data)

---

## Code Style

### Formatting
- Line length: 100 characters max
- Use `ruff format` for consistent formatting
- Double quotes for strings

### Type Hints
```python
# Good
def process_event(event: Event, config: Config | None = None) -> ProcessResult:
    ...

# Bad - missing types
def process_event(event, config=None):
    ...
```

### Documentation
- Brief docstrings for public functions
- Comments only where logic isn't self-evident
- NO auto-generated READMEs or markdown files

### Principles
- **Minimal changes**: Only change what's needed for the task
- **No over-engineering**: Simple solutions preferred
- **No speculation**: Don't add features "for later"
- **Clean deletions**: Remove unused code completely

---

## Git Workflow

### Branch Strategy

```
main              # Stable releases only (never push directly)
cognifold-dev     # Main development branch (PR target)
phase<N>          # Phase-specific branches (e.g., phase10, phase11)
```

### Workflow

1. **Create phase branch** from `cognifold-dev`:
   ```bash
   git checkout cognifold-dev
   git pull origin cognifold-dev
   git checkout -b phase10
   ```

2. **Make incremental commits** (see Commit Convention below)

3. **Push regularly**:
   ```bash
   git push -u origin phase10
   ```

4. **Create PR** when phase complete or at logical checkpoints

### PR Requirements
- All quality gates pass (ruff, pyright, pytest)
- Clear description referencing Phase
- Link to related issues if any
- Request review for significant changes

---

## Commit Convention

### Format
```
<type>(<scope>): <what was done>

<why it was done - 1-2 sentences>

Phase: X.Y
```

### Types
| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes nor adds |
| `test` | Adding or updating tests |
| `docs` | Documentation changes |
| `chore` | Maintenance tasks |

### Examples

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

### When to Commit
- After EVERY small, completed task
- Before switching to a different file or component
- After fixing a bug
- Before any risky or experimental change

---

## Project Structure

```
cognifold/
├── CLAUDE.md              # Project entry point (read first)
├── pyproject.toml         # Dependencies and tools
├── Makefile              # Common commands
├── src/
│   └── cognifold/
│       ├── models/        # Pydantic schemas
│       ├── graph/         # Graph operations
│       ├── scoring/       # Relevance scoring
│       ├── agent/         # LangGraph agent
│       ├── executor/      # Plan execution
│       ├── generator/     # Event generation
│       ├── importers/     # Data importers
│       ├── query/         # Query system
│       ├── temporal/      # Temporal extraction
│       ├── embeddings/    # Embedding providers
│       ├── retrieval/     # Hybrid retrieval
│       ├── intent/        # Intent execution
│       ├── replay/        # Replay tool
│       └── simulator/     # Visualization
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/                  # Sample data and generated timelines
├── docs/                  # Documentation
├── configs/               # Configuration files
└── logs/                  # Run logs
```

---

## Documentation Files

| File | Purpose | Update When |
|------|---------|-------------|
| `CLAUDE.md` | Project entry point | Architecture changes |
| `docs/AGENT_PROTOCOL.md` | Agent workflow rules | Process changes |
| `docs/PHASES.md` | Phase specifications | Planning/completing phases |
| `docs/RESUME.md` | Current work state | Every session |
| `docs/CHANGELOG.md` | Change history | Every change |
| `docs/WISHLIST.md` | Deferred work | Deferring tasks |
| `docs/ARCHITECTURE.md` | System design | Architecture changes |
| `docs/PROMPTS.md` | Prompt engineering | Prompt changes |

---

## Common Commands

```bash
# Run all quality checks
make check

# Run tests only
pytest tests/ -v

# Run specific test file
pytest tests/unit/test_query.py -v

# Format code
ruff format src/ tests/

# Lint and fix
ruff check --fix src/ tests/

# Type check
pyright src/

# Run simulation
cognifold run data/generated/timeline.json --agent

# Run with specific steps
cognifold run data/generated/timeline.json --agent --steps 15

# Query the graph
cognifold query "exercise habits" --graph output/graph.json
```

---

## Getting Help

- Read `docs/ARCHITECTURE.md` for system design
- Read `docs/PHASES.md` for current specifications
- Read `docs/CHANGELOG.md` for recent decisions
- Check `docs/WISHLIST.md` for known issues/ideas
