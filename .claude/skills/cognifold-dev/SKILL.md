---
name: cognifold-dev
description: This skill should be used when the user asks to "commit code", "run tests", "check quality", "create a PR", "start development", "fix lint errors", "add tests", or performs any development workflow task on the Cognifold codebase. Provides quality gates, git workflow, testing patterns, and coding standards.
---

# Cognifold Development Workflow

## Quality Gates (MUST PASS before commit)

```bash
make check       # ruff lint + format check
make typecheck   # pyright strict mode
make test        # pytest tests/ -v
make quality     # check + test combined
make fix         # auto-fix lint + format issues
```

Manual equivalents:
```bash
ruff format --check src/ tests/
ruff check src/ tests/
pyright src/
pytest tests/ -v
```

## Git Workflow

1. **Never push directly** to `main` or `cognifold-dev`
2. Create feature branch from `cognifold-dev`
3. Push to origin, create PR via `gh pr create --repo MergeFold/CogniFold`
4. Use `--head branch-name` (not `duanyiqun:branch-name`) for PRs

### Pre-flight Check (before any coding)
```bash
git fetch --all && git branch -r --no-merged origin/cognifold-dev
```
Warn user if unmerged branches exist.

### Commit Protocol
- Commit immediately after each small, working task
- Update `docs/CHANGELOG.md` with changes
- Update `docs/RESUME.md` with current state
- Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

## Coding Standards

| Rule | Detail |
|------|--------|
| Line length | 100 chars (ruff) |
| Python target | 3.9+ |
| Quote style | Double quotes |
| Type checking | pyright strict on `src/` |
| Imports | sorted by ruff (isort rules) |
| Lint rules | E, F, I, N, W, UP, B, C4, SIM, RUF |

### Type Annotation Conventions
- All public functions must have type annotations
- Use `from __future__ import annotations` for forward refs
- NetworkX stubs are incomplete: `reportUnknownMemberType = "warning"`
- pyright excludes `tests/` directory

### Pydantic Patterns
- Use `model_config = ConfigDict(frozen=True)` for immutable models (Event)
- Validation at system boundaries, trust internal code
- `to_dict()` / `from_dict()` for serialization

## Test Structure

**Unit tests** (`tests/unit/` - 25 files):

| Test File | Tests |
|-----------|-------|
| `test_models.py` | Event, Node, Edge, UpdatePlan Pydantic schemas |
| `test_graph.py` | ConceptGraph CRUD, persistence, adjacency |
| `test_graph_validator.py` | Graph integrity validation |
| `test_scoring.py` | PageRank, recency decay, frequency scoring |
| `test_hierarchical.py` | Hierarchical context selection |
| `test_executor.py` | Plan validation + atomic execution |
| `test_embeddings.py` | Embedding providers, NodeEmbedder, SemanticSearch |
| `test_retrieval.py` | BM25 index, hybrid retrieval, RRF fusion |
| `test_agentic_retrieval.py` | AgenticRetriever multi-round search |
| `test_query.py` | MemoryQueryAgent, entry points, traversal |
| `test_intent.py` | Intent selection, action queue |
| `test_temporal.py` | Temporal entity extraction |
| `test_prompt_sections.py` | Modular prompt composition, section registry |
| `test_prompt_profile.py` | YAML prompt profiles, domain configs |
| `test_domain_prompts.py` | Domain-specific prompt generation |
| `test_service_*.py` | Service models, processor, session, tasks |
| `test_cli_client.py` | Interactive client command dispatch |
| `test_replay.py` | Replay logging and playback |
| `test_simulator.py` | Simulation runner, timeline loading |

**Integration tests** (`tests/integration/`):
- `test_pipeline.py` - End-to-end event processing
- `test_service_api.py` - HTTP API endpoints

**Fixtures** (`tests/conftest.py`, `tests/fixtures/`):
- `sample_graph` - Pre-populated ConceptGraph
- `sample_event` - Test Event instance

### Writing New Tests
- Mirror source structure: `src/cognifold/foo/bar.py` → `tests/unit/test_bar.py`
- Use `MockEmbeddingProvider` for embedding tests (no API key needed)
- Mock LLM calls with `unittest.mock.patch`

## Additional Resources

### Reference Files
- **`references/test-patterns.md`** - Common test patterns and mock setups
