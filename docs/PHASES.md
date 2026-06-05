# Development Phases

This document contains all phase specifications - completed, in-progress, and planned.

---

## Phase Status Overview

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation | ✅ Complete |
| 2 | Scoring & Context Window | ✅ Complete |
| 3 | Simulator MVP | ✅ Complete |
| 4 | Agent Integration | ✅ Complete |
| 5 | End-to-End Pipeline | ✅ Complete |
| 5.1 | Event Generator | ✅ Complete |
| 5.2 | Prompt Engineering & Concept Hierarchy | ✅ Complete |
| 5.3 | Proactive Action Generation & Temporal Urgency | ✅ Complete |
| 5.4 | Graph Evolution Replay Tool | ✅ Complete |
| 5.5 | Node Explainability & Event Grounding | ✅ Complete |
| 5.6 | Graph Integrity & Prompt Optimization | ✅ Complete |
| 6 | Generalization & Multi-Domain Support | ✅ Complete |
| 6.1 | Wiki Integration & Importer Architecture | ✅ Complete |
| 6.2 | Engineering Cleanup & Code Quality | ✅ Complete |
| 7 | Memory Query Interface | ✅ Complete |
| 8 | Intent Execution System | ✅ Complete |
| 9 | System Quality Improvements | ✅ Complete |
| 9.1 | Typed/Weighted Edges | ✅ Complete |
| 9.2 | Hierarchical Context Windows | ✅ Complete |
| 9.3 | Context-Aware Plan Refinement | ✅ Complete |
| 10 | Advanced Retrieval & Query System | 🔄 In Progress |
| 10.2 | Enhanced Temporal Extraction | ✅ Complete |
| 10.3 | Embedding-based Semantic Search | ✅ Complete |
| 10.4 | Hybrid Retrieval (BM25 + Embeddings) | ✅ Complete |
| 10.5 | LLM-powered Query Understanding | 📋 Planned |
| 11 | Service Layer & HTTP API | ✅ Complete |
| 11.1 | Query Memory Improvements | ✅ Complete |
| 12 | Benchmark Evaluation | 🔄 In Progress |
| 13 | Modular System Prompt Composition | ✅ Complete |
| 14.1 | Intent Personalization | ✅ Complete |
| 15 | Production Deployment & Observability | 🔄 In Progress |
| 15.5 | Horizontal Scaling & Auto-Deploy | 🔄 In Progress |

---

# Current & Planned Phases

## Phase 10: Advanced Retrieval & Query System 🔄

**Goal**: Significantly improve retrieval/query capabilities with semantic search, hybrid retrieval, and LLM-powered query understanding

**Motivation** (from LoCoMo benchmark findings):
- Temporal queries had lowest accuracy - TIME nodes not consistently created
- Keyword-only matching misses semantic relationships ("exercise" won't find "gym")
- No query expansion or understanding of natural language time references

### Phase 10.2: Enhanced Temporal Extraction ✅

**Goal**: Ensure TIME nodes are consistently created for mentioned dates/times

**Solution Components**:
1. **Pre-processing Temporal Detection** - Regex patterns + `dateparser` for natural language dates
2. **Enhanced Prompts** - Explicit instructions for TIME node creation
3. **Automatic TIME Node Suggestions** - Include detected temporal entities in agent context

**Key Data Structures**:

| Structure | Purpose |
|-----------|---------|
| `TemporalEntity` | Extracted temporal reference (raw text, normalized datetime, confidence, span) |
| `TemporalExtractor` | Extracts temporal references from text using regex + dateparser |

**Module**: `src/cognifold/temporal/`

### Phase 10.3: Embedding-based Semantic Search ✅

**Goal**: Enable semantic similarity search beyond keyword matching

**Solution Components**:
1. **Node Embedding Model** - Optional `embedding` field, provider abstraction
2. **Embedding Generation** - Lazy or eager, with batching
3. **Vector Storage** - numpy arrays in JSON, optional vector DB
4. **Semantic Entry Point Selection** - Cosine similarity search

**Key Data Structures**:

| Structure | Purpose |
|-----------|---------|
| `EmbeddingConfig` | Provider, model, dimensions, batch size, caching settings |
| `EmbeddingProvider` | Abstract interface (Gemini, OpenAI, Mock) |
| `NodeEmbedder` | Generates and caches embeddings for graph nodes |
| `SemanticSearch` | Cosine similarity search over node embeddings |

**Module**: `src/cognifold/embeddings/`

### Phase 10.4: Hybrid Retrieval (BM25 + Embeddings) ✅

**Goal**: Combine lexical (keyword) and semantic (embedding) matching for best results

**Solution Components**:
1. **BM25 Implementation** - Standard BM25 scoring with inverted index
2. **Score Fusion** - Reciprocal Rank Fusion (RRF) to combine rankings
3. **Unified Retrieval Interface** - Strategy selection based on query type

**Key Data Structures**:

| Structure | Purpose |
|-----------|---------|
| `RetrievalStrategy` | Enum: KEYWORD, SEMANTIC, HYBRID, AGENTIC |
| `RetrievalConfig` | Strategy, weights, RRF constant, top-k, min score |
| `BM25Index` | Inverted index with BM25 scoring (k1=1.5, b=0.75) |
| `HybridRetriever` | Combines BM25 and semantic search with RRF fusion |

**Module**: `src/cognifold/retrieval/`

### Phase 10.5: LLM-powered Query Understanding 📋

**Goal**: Use LLM to improve query processing with intent classification, expansion, and temporal parsing

**Solution Components**:
1. **Query Intent Classification** - Classify: factual, temporal, relational, exploratory, listing
2. **Query Expansion** - LLM generates related terms and synonyms
3. **Temporal NLP** - Parse natural language time references using TemporalExtractor
4. **LLM-based Reranking** (optional) - Rerank results for quality

**Query Intent Types**:

| Intent | Example Query | Retrieval Strategy |
|--------|--------------|-------------------|
| FACTUAL | "What is X?" | HYBRID |
| TEMPORAL | "When did X happen?" | KEYWORD (exact match) |
| RELATIONAL | "How is X related to Y?" | HYBRID |
| EXPLORATORY | "Tell me about X" | SEMANTIC (broad) |
| LISTING | "What are all the X?" | KEYWORD |

**Key Data Structures**:

| Structure | Purpose |
|-----------|---------|
| `QueryIntent` | Enum of query intent types |
| `ParsedQuery` | Result of query understanding (intent, entities, expanded terms, time constraint) |
| `QueryUnderstanding` | LLM-powered query parsing and expansion |
| `SmartQueryAgent` | Orchestrates understanding → retrieval → assembly |

**Module**: `src/cognifold/query/understanding.py`

**Tasks**:
- [ ] Create `src/cognifold/query/understanding.py`
- [ ] Implement `QueryIntent` classification
- [ ] Implement `ParsedQuery` with all components
- [ ] Implement `QueryUnderstanding` with LLM calls
- [ ] Integrate temporal extraction from Phase 10.2
- [ ] Implement `SmartQueryAgent` orchestration
- [ ] Add LLM reranking (optional, behind flag)
- [ ] CLI flags for query understanding features
- [ ] Unit tests for query parsing
- [ ] Integration tests for end-to-end query accuracy

**Exit Criteria**:
- Query intent correctly classified
- Temporal references parsed and resolved
- Query expansion improves recall
- End-to-end query accuracy improved on LoCoMo benchmark

---

## Phase 12: Benchmark Evaluation 📋

**Goal**: Systematically evaluate Cognifold against established benchmarks across 5 capability dimensions

**Full details**: See [BENCHMARK.md](BENCHMARK.md) and [benchmark/dataset-catalog.md](benchmark/dataset-catalog.md)

### Evaluation Categories

| # | Category | Datasets | Tests |
|---|----------|----------|-------|
| 1 | Long-Term Conversational Memory | MSC, LoCoMo, LongMem | Multi-session consistency, fact recall, logical connections |
| 2 | Multi-Hop Reasoning | BABILong, MuTual, MuSiQue-Ans | Graph traversal, logical edges, connected reasoning |
| 3 | Streaming & Conflicts (Dynamic Graph) | StreamingQA, RGB, TimeQA | Knowledge updates, noise robustness, temporal reasoning |
| 4 | Long-Form Narrative & Event Understanding | NarrativeQA, QMSum | Stream-adapted narrative comprehension, meeting summarization |
| 5 | Proactive ("The Soul") | SocialIQA, ToMi, SafetyBench | Social reasoning, theory of mind, proactive safety |

---

## Phase 15: Production Deployment & Observability 🔄

**Goal**: Production-ready deployment with Docker, zero-downtime deploys, structured logging, and dual storage backends.

**Full details**: See [DEPLOYMENT.md](DEPLOYMENT.md)

### Key Components

| Component | What |
|-----------|------|
| Structured Logging | structlog + JSON output + request-ID tracking across async calls |
| Session Store Abstraction | Pluggable file/Redis backends via `COGNIFOLD_SESSION_BACKEND` env var |
| Gunicorn + WSGI | Production process manager with uvicorn workers |
| Docker Image | Multi-stage build, non-root user, health checks |
| Blue-Green Deploy | NGINX upstream swap, auto-rollback, deploy/rollback scripts |
| Log Aggregation | Loki + Promtail (Docker SD), queryable via LogCLI |
| CI/CD | GitHub Actions: lint/test on PR, build+push image on merge to main |

### Sub-phases

| # | Name | Scope |
|---|------|-------|
| 15.1 | Logging & Session Store | structlog, file/Redis store abstraction, tests |
| 15.2 | Containerization | Dockerfile, gunicorn, wsgi entrypoint, docker-compose |
| 15.3 | Deployment Infrastructure | NGINX, blue-green scripts, Loki/Promtail, SSL |
| 15.4 | CI/CD | GitHub Actions workflows |
| 15.5 | Horizontal Scaling & Auto-Deploy | Persist-on-mutation, ip_hash affinity, rolling deploy, auto-deploy |

**Exit Criteria**:
- `make quality` + `make typecheck` pass
- Docker image builds and passes health check
- Blue-green deploy script works with zero downtime
- Structured JSON logs visible in Loki via LogCLI
- CI workflow runs on PR

---

## Future Extensions 📋

Planned enhancements (not yet specified):

- Incremental PageRank (performance optimization)
- Streaming event batching (performance optimization)
- Persistence to database (Neo4j)
- Multi-day / long-term memory patterns
- Plugin architecture for custom domains
- Counterfactual reasoning
- Federated multi-graph architecture

See [WISHLIST.md](WISHLIST.md) for deferred work and ideas.

---

# Completed Phases

## Phase 14.1: Intent Personalization ✅

**Goal**: Closed-loop intent calibration — users accept/reject/defer/modify intents, and the system learns from feedback to adjust future scoring and prompt generation.

**Key Changes**:
- `intent/personalization.py` — `FeedbackType` enum (accept, reject, defer, modify), `IntentFeedback`, `CalibrationProfile`, `FeedbackStats` models
- `intent/feedback_store.py` — `FeedbackStore(graph)` with graph-backed persistence (feedback as event nodes + USER_FEEDBACK edges)
- `intent/calibrator.py` — `IntentCalibrator` with EMA-based profiles (alpha=0.3), score multipliers [0.1, 2.0], prompt context generation, adaptive thresholds
- `intent/selector.py` — `IntentSelector` accepts optional `calibrator` for score adjustment
- `service/routes/intents.py` — 3 new HTTP endpoints: submit feedback, get calibration profile, get pending intents
- `cli/client.py` — `:feedback`, `:calibration`, `:intents pending` commands
- `agent/prompt_sections.py` — new `intents.personalization` section (21 total)
- `models/node.py` — `IntentStatus` extended (REJECTED, DEFERRED), `BaseEdgeType` extended (USER_FEEDBACK)

**Tests**: 36 new tests (31 unit + 5 integration)

**Files**: `src/cognifold/intent/personalization.py`, `calibrator.py`, `feedback_store.py`, `selector.py`; `src/cognifold/service/routes/intents.py`; `src/cognifold/cli/client.py`

## Phase 14: Cognition Feedback Core ✅

**Goal**: Add self-organizing feedback mechanisms so the concept graph autonomously strengthens important patterns, weakens stale ones, and surfaces ready-to-act intents.

**Key Changes**:
- New `src/cognifold/feedback/` module with 8 files implementing 6 feedback mechanisms
- **FeedbackConfig** — ~30 tunable parameters with `enabled` master switch
- **Self-Reinforcement** — auto-boost concept strength on plan/query reference; returns actual clamped delta
- **Hierarchical Propagation** — cascade signals up PART_OF/DERIVED_FROM edges
- **Hebbian Plasticity** — co-activated edges strengthen, inactive edges weaken (uses public `ConceptGraph` API). ⚠️ *Status: attempted on `hebbian-dynamics-phase1/phase2` branches (2026-04); not integrated to main — pilot did not show net benefit. Branches preserved in remote for reference.*
- **Decay Sweep** — evict stale concepts below strength + age thresholds
- **Spreading Activation** — BFS activation overlay from current event/query focus
- **Action Potential** — score PENDING intents on support breadth, goal alignment, temporal fitness
- **FeedbackEngine** — coordinator with hooks: `on_plan_executed`, `on_query_retrieved`, `on_event_ingested`, `tick`
- **ConceptGraph** gains `update_edge_attrs()` and `iter_edges_raw()` for safe edge manipulation
- Optional edge pruning (`edge_prune_enabled`, default False)

**Integration**: `PlanExecutor.__init__` accepts optional `feedback_engine` for post-execution feedback loops.

**Tests**: 76+ tests across 6 test files covering strength clamping, type protection, hierarchy propagation, cycle handling, edge decay, activation, and action potential ranking.

**Files**: `src/cognifold/feedback/`, `src/cognifold/graph/store.py`, `src/cognifold/executor/runner.py`

## Phase 13: Modular System Prompt Composition ✅

**Goal**: Break the monolithic ~370-line `SYSTEM_PROMPT_TEMPLATE` into 20 composable, named sections that domains can toggle on/off, override, or extend.

**Key Changes**:
- New `prompt_sections.py` module with 20 section constants, `SECTION_REGISTRY`, `SECTION_GROUPS`, `DEFAULT_SECTION_ORDER`, and `resolve_sections()`
- `DomainConfig` gains `disabled_sections`, `extra_sections`, `extra_section_position` fields
- `format_system_prompt_for_domain()` uses section-based composition (YAML template overrides bypass it)
- `PromptProfile` supports `sections.disabled` and `sections.extra` in YAML
- Benchmark domains (locomo, longmemeval) use `disabled_sections=frozenset({"intents"})` to exclude intent sections
- Concatenation invariant: `"".join(sections) == original_template` — byte-identical output for all existing domains

**Files**: `prompt_sections.py` (new), `prompts.py`, `domain.py`, `prompt_profile.py`, `graph.py`, `test_prompt_sections.py` (new)

## Phase 11.1: Query Memory Improvements ✅

**Goal**: Close the gap with EverMemOS-style retrieval by adding fast vector search, agentic multi-round retrieval, and unified embedding infrastructure.

**Key Changes**:
- **W1: FAISS ANN Index** — Optional `faiss-cpu` backend in `embeddings/search.py` for O(log n) vector search with automatic numpy fallback
- **W2: Agentic Multi-Round Retrieval** — `retrieval/agentic.py` performs hybrid search → LLM sufficiency check → complementary query generation → multi-list RRF fusion
- **W3: Unified Embedding System** — Single embedding pipeline shared by RAG mode and vector search; `query/llm.py` provides cached LLM caller
- **W10: Default Retrieval Upgrade** — Default retrieval mode changed from LEGACY to HYBRID (auto-degrades to BM25 without embeddings)
- New `RetrievalConfig` dataclass with factory methods and `RetrievalStrategy` enum (KEYWORD, SEMANTIC, HYBRID, AGENTIC)
- New `query/prompts.py` with sufficiency check and multi-query prompt templates

**New Modules**: `retrieval/agentic.py`, `retrieval/config.py`, `query/llm.py`, `query/prompts.py`

**Dependencies**: `faiss-cpu>=1.7` (optional, in `[search]` extra)

**Roadmap**: See [WISHLIST_QUERY_MEMORY.md](WISHLIST_QUERY_MEMORY.md) for remaining items (W4-W11)

## Phase 11: Service Layer & HTTP API ✅

**Goal**: Expose Cognifold as an HTTP service with session management, event ingestion, query, and graph state APIs.

**Key Components**:
- FastAPI service with session management, TTL-based eviction (`src/cognifold/service/`)
- RESTful API: sessions, events (sync/async), query, graph state endpoints
- API key authentication (optional)
- CLI `serve` subcommand and interactive REPL client
- LLM execution fixes: `llm_env()` wrapping, operation sorting, robust node ID resolution

**API Reference**: See [SERVICE_API.md](SERVICE_API.md)

**Future enhancements**: WebSocket streaming, batch import, OpenAPI versioning (see [WISHLIST.md](WISHLIST.md))

---

## Phase 1: Foundation ✅

**Goal**: Core data structures and graph operations

- [x] Project setup (pyproject.toml, dependencies, linting)
- [x] Pydantic models for Event, Node, Edge, UpdatePlan
- [x] Graph class wrapping NetworkX
- [x] JSON persistence (save/load)
- [x] Unit tests for graph operations

**Exit Criteria**: Can create, modify, persist, and reload a graph programmatically.

---

## Phase 2: Scoring & Context Window ✅

**Goal**: Implement relevance scoring and context selection

- [x] PageRank computation via NetworkX
- [x] Recency score calculation
- [x] Access frequency tracking
- [x] Composite score function (configurable weights)
- [x] Context window selection (top-k by score)
- [x] Unit tests for scoring

**Scoring Formula**:
```
Score(node) = α × StructuralRank + β × RecencyScore + γ × AccessScore
```

Default weights: α=0.4, β=0.4, γ=0.2

---

## Phase 3: Simulator MVP ✅

**Goal**: Visual debugging tool

- [x] Mock timeline loader
- [x] Basic visualization (pyvis or matplotlib)
- [x] Color coding by node type
- [x] Context window highlighting
- [x] Step-through controls
- [x] Manual "fake agent" mode (human provides update plan via JSON)

---

## Phase 4: Agent Integration ✅

**Goal**: LangGraph agent that generates update plans

- [x] LangGraph setup with Gemini
- [x] Agent prompt design
- [x] Tool definitions for graph traversal
- [x] UpdatePlan generation
- [x] Executor implementation
- [x] Integration tests

---

## Phase 5: End-to-End Pipeline ✅

**Goal**: Full working system

- [x] Wire all components together
- [x] Configuration management (YAML/env)
- [x] Logging and observability
- [x] Run simulator with real agent
- [x] Iterate on prompts and scoring weights

---

## Phase 5.1: Event Generator ✅

**Goal**: Generate rich, realistic event streams using Gemini

- [x] Create event generator module (`src/cognifold/generator/`)
- [x] Define persona schema (name, occupation, habits, interests, lifestyle)
- [x] Implement Gemini-based event generation with persona context
- [x] Generate temporally coherent events (proper timestamps, realistic sequences)
- [x] Support configurable event count (target: 100+ events)
- [x] Include variety across event types (meal, work, exercise, social, etc.)
- [x] Add realistic metadata and descriptions
- [x] Output to mock timeline JSON format
- [x] Create 2-3 sample personas with generated timelines

---

## Phase 5.2: Prompt Engineering & Concept Hierarchy ✅

**Goal**: High-quality agent prompts that produce meaningful concept graphs

- [x] Refine agent system prompt for concept emergence
- [x] Enable hierarchical concepts (concepts derived from other concepts)
- [x] Improve action node generation (actionable insights from patterns)
- [x] Add prompt for recognizing patterns across events (routines, habits)
- [x] Add prompt for identifying anomalies and breaks in patterns
- [x] Implement concept consolidation (merge similar concepts)
- [x] Add strength/confidence scoring for concepts
- [x] Create prompt templates for different reasoning modes
- [x] A/B test prompts with generated event streams
- [x] Document effective prompt patterns in `docs/PROMPTS.md`

---

## Phase 5.3: Proactive Action Generation & Temporal Urgency ✅

**Goal**: Generate actionable recommendations with time-aware context

**Design Principle**: Actions as Actionable Concepts
- Actions are a special type of concept (not a separate category)
- Same PageRank scoring applies to actions and concepts
- Actions naturally rise/fall in importance based on graph connectivity

**New Node Type: Time Nodes**
- [x] Add `time` node type to represent temporal anchors
- [x] Time nodes represent: deadlines, scheduled events, recurring times
- [x] Connect nodes to time nodes for temporal context
- [x] Time nodes influence recency scoring (proximity to "now")

---

## Phase 5.4: Graph Evolution Replay Tool ✅

**Goal**: Visualize how the graph is built over time from event logs

- [x] Define structured log format for graph operations
- [x] Log each event ingestion with timestamp
- [x] Log each UpdatePlan execution (operations applied)
- [x] Parse logs into ordered sequence of graph states
- [x] Interactive HTML player (pyvis or D3.js)
- [x] Play/pause/step controls
- [x] Node colors by type (event/concept/action/time)
- [x] Context window nodes highlighted
- [x] Export as standalone HTML file

**CLI**: `cognifold replay --log run_001.jsonl --output replay.html`

---

## Phase 5.5: Node Explainability & Event Grounding ✅

**Goal**: Every node creation/update must be explainable and grounded in events

**Explainability Requirement**:
- [x] Every node must have a `reasoning` field explaining why it exists
- [x] Every update must include `update_reasoning` explaining the change
- [x] Agent prompt requires reasoning for all operations

**Event Grounding Rule**:
- [x] New `concept` nodes must connect to at least one `event` node
- [x] New `action` nodes must connect to at least one `event` or `concept` node
- [x] New `time` nodes must connect to at least one `event` or `action` node
- [x] Enforce grounding in executor (reject ungrounded nodes)

**Node Schema**:
```json
{
  "id": "c-001",
  "type": "concept",
  "data": {
    "title": "Morning exercise routine",
    "reasoning": "Created because user has gone to gym 3 mornings this week",
    "grounded_in": ["e-003", "e-012", "e-019"]
  }
}
```

---

## Phase 5.6: Graph Integrity & Prompt Optimization ✅

**Goal**: Ensure graph quality through validation and refined prompts

**Graph Integrity Rules**:
- [x] No orphan nodes: every node must have at least one edge
- [x] Connectivity requirements by type enforced
- [x] Validate graph integrity after each UpdatePlan execution
- [x] Auto-cleanup: remove orphaned nodes periodically

**GraphValidator**:
```python
class GraphValidator:
    def validate_no_orphans(self) -> List[str]
    def validate_grounding(self) -> List[str]
    def validate_reasoning(self) -> List[str]
    def validate_all(self) -> ValidationReport
```

---

## Phase 6: Generalization & Multi-Domain Support ✅

**Goal**: Transform from personal timeline tool to general-purpose memory system

**Design Philosophy**:
- System does NOT know what domain it's processing
- Prompts are domain-agnostic (no hardcoded "meal", "work", etc.)
- Same core logic handles any event stream

**Unified Event Schema**:
```json
{
  "event_id": "uuid",
  "timestamp": "ISO 8601 datetime",
  "source": "string (identifies the event source/domain)",
  "event_type": "string (free-form, domain-specific)",
  "title": "short description",
  "description": "detailed description (optional)",
  "context": { /* domain-specific, opaque to system */ },
  "metadata": { /* additional unstructured data */ }
}
```

**Supported Domains**: Personal timeline, Computer activity, Service logs, Wiki

---

## Phase 6.1: Wiki Integration & Importer Architecture ✅

**Goal**: Properly integrate wiki importer as a domain, establish importer patterns

- [x] Wiki importer (`src/cognifold/importers/wiki.py`)
- [x] Prompt profile system (`src/cognifold/agent/prompt_profile.py`)
- [x] Wiki integrated as a proper domain
- [x] BaseImporter architecture documented
- [x] Wiki-specific tests passing

**Importer vs Generator**:
- Generators: Create synthetic events from LLM (personal, computer, service)
- Importers: Convert external data to events (wiki, browser history, logs)

---

## Phase 6.2: Engineering Cleanup & Code Quality ✅

**Goal**: Clean up codebase, improve test coverage, enforce coding standards

- [x] CLI refactored into submodules
- [x] 80%+ test coverage achieved
- [x] All code passes `ruff check`, `ruff format --check`
- [x] Type hints on all functions
- [x] Documentation updated
- [x] Development scripts in place (Makefile)

---

## Phase 7: Memory Query Interface ✅

**Goal**: Create an interface for agents to query the memory system and retrieve relevant context

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                    External Query                                │
│  (User prompt, Agent query, API request)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Memory Query Agent                              │
│  1. Parse query intent                                          │
│  2. Find entry points (text search first, then PageRank)        │
│  3. Traverse graph (BFS with score decay)                       │
│  4. Score and rank nodes                                        │
│  5. Assemble context                                            │
└─────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Concept Graph                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Query Types**: Semantic, Temporal, Structural, Hybrid

**Module**: `src/cognifold/query/`

**CLI**: `cognifold query -g graph.json "What patterns exist?"`

---

## Phase 8: Intent Execution System ✅

**Goal**: Transform intents into executable actions and integrate with the event processing pipeline

### Sub-phases
- **8.1**: Rename action→intent, create Intent-to-Action Agent
- **8.2**: Integrate with event processing pipeline, create action queue
- **8.3**: Simulation mode with action execution

### Key Concepts

| Concept | Description |
|---------|-------------|
| Intent | Goal/desire stored as graph node (status: pending → action_scheduled → resolved) |
| Action | Concrete schedulable step with execution time (stored in ActionQueue, not graph) |
| ActionQueue | Manages scheduled actions, sorted by time, with persistence |
| IntentToActionAgent | Converts intents to concrete actions based on context |
| ActionExecutor | Simulates action execution, generates result events |

### Intent Lifecycle
```
pending → (action registered) → action_scheduled → (result processed) → resolved
```

### Pipeline Flow
```
Event → Memory Agent → Graph Update → Intent Selection → Action Generation → ActionQueue
                                                                              ↓
                                              Action Execution (between events) ←
                                                                              ↓
                                              Result Event → Memory Agent → Intent Resolution
```

**CLI**: `cognifold run --action-mode` enables action execution in simulation

**Module**: `src/cognifold/intent/`

---

## Phase 9: System Quality Improvements ✅

**Goal**: Improve graph semantics, context quality, and plan generation

### Phase 9.1: Typed/Weighted Edges ✅

**Goal**: Rich semantic relationships between nodes

**Edge Types** (BaseEdgeType enum):

| Type | Default Weight | Usage |
|------|----------------|-------|
| GROUNDS | 0.9 | Event grounds Concept/Intent |
| CAUSES | 0.9 | Event causes Event |
| TRIGGERS | 0.8 | Concept triggers Intent |
| REINFORCES | 0.7 | Event reinforces Concept |
| PART_OF | 0.7 | Sub-concept of parent |
| DERIVED_FROM | 0.6 | Concept derived from another |
| DEADLINE_FOR | 0.6 | Time is deadline for Intent |
| RELATED_TO | 0.5 | Generic relationship (default) |

**Key Features**:
- Multiple edges between same node pair (different types)
- Weighted PageRank: `effective_weight = weight × recency_factor`
- Soft constraint validation (warnings only)
- Legacy edges supported (`edge_type=None, weight=1.0`)

**Files**: `src/cognifold/models/node.py` (Edge), `src/cognifold/graph/store.py` (MultiDiGraph)

### Phase 9.2: Hierarchical Context Windows ✅

**Goal**: Multi-level context with different priorities for LLM attention

**Context Levels**:

| Level | % | Content | Scoring |
|-------|---|---------|---------|
| Immediate | 10% | Recent events, urgent intents | 70% recency, 30% urgency |
| Working | 30% | Active concepts, patterns | 50% PageRank, 30% recency, 20% type |
| Background | 50% | Historical context | 80% PageRank, 20% diversity |

**Key Features**:
- Deduplication to highest priority level
- Each level includes Nodes + Relationships sections
- Edges show type, weight, and connected node info
- Relevance threshold filtering
- ContextMetrics tracks which levels contribute to plans

**Files**: `src/cognifold/scoring/hierarchical.py`, `src/cognifold/agent/prompts.py`

### Phase 9.3: Context-Aware Plan Refinement ✅

**Goal**: Improve connectivity and concept hierarchy

**Problem 1 - Missing Retroactive Connections**:
- New concept created but earlier related events not connected
- **Solution**: "Plan Self-Review" prompt section - scan context for ALL related events

**Problem 2 - Flat Concept Structures**:
- Concepts accumulate many connections without sub-structure
- **Solution**: Auto-expand overloaded concepts (5+ connections) to show neighborhood
- Mark as "NEEDS REFINEMENT" with suggestions for sub-concepts

**Files**: `src/cognifold/agent/prompts.py`, `src/cognifold/agent/context.py`
