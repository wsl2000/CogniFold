# Cognifold

A dynamic concept graph system that processes real-time event streams and maintains an evolving knowledge representation.

**101 source files | 27k LOC | 717 tests | 16 modules**

## Overview

Cognifold ingests a stream of events (activities, observations, interactions) and builds a concept graph that:
- Captures patterns and higher-level concepts from raw events
- Generates actionable intents grounded in observed behavior
- Uses PageRank-inspired scoring to maintain a hierarchical context window
- Provides 5 retrieval strategies from keyword to agentic multi-round search
- Exposes a REST API for session-based graph management and querying

## Architecture

```
                                  COGNIFOLD SYSTEM

  WRITE PATH (Event Processing)              READ PATH (Query & Retrieval)
  ==============================             ==============================

  ┌──────────┐   ┌──────────┐               ┌──────────────────┐
  │Generator │   │ Importer │               │ Natural Language  │
  │  (LLM)   │   │  (Data)  │               │     Query         │
  └────┬─────┘   └────┬─────┘               └────────┬─────────┘
       └──────┬───────┘                               │
              ▼                                       ▼
     ┌──────────────┐                      ┌─────────────────────┐
     │ Event Stream │                      │  MemoryQueryAgent    │
     └──────┬───────┘                      │                     │
            ▼                              │  Entry Point Selection
  ┌──────────────────┐                     │  ┌─────┬────┬──────┐│
  │ Context Selector │                     │  │BM25 │Sem │Hybrid││
  │  • PageRank      │◄──┐                │  └─────┴────┴──┬───┘│
  │  • Recency       │   │                │  ┌─────────────┘    │
  │  • Urgency       │   │                │  │ AGENTIC          │
  └────────┬─────────┘   │                │  │ R1→sufficiency   │
           ▼             │                │  │ R2→expansion+RRF │
  ┌──────────────────┐   │                │  └──────────────────┘│
  │  LangGraph Agent │   │                │         │            │
  │  (Gemini/OpenAI) │   │                │         ▼            │
  │                  │   │                │  Traverse → Score     │
  │  Event +         │   │                │         → Assemble   │
  │  Hierarchical    │   │                └──────────┬──────────┘
  │  Context Window  │   │                           ▼
  │       ↓          │   │                ┌──────────────────┐
  │  UpdatePlan      │   │                │   QueryResult    │
  └────────┬─────────┘   │                │  • context text  │
           ▼             │                │  • ranked nodes  │
  ┌──────────────────┐   │                │  • metadata      │
  │    Executor      │───┘                └──────────────────┘
  │  • Validate      │
  │  • Apply atomic  │         ┌───────────────────────────┐
  │  • Rollback      │────────►│     CONCEPT GRAPH         │
  └──────────────────┘         │  Nodes: event, concept,   │
                               │         intent, time      │
   HTTP SERVICE                │  Edges: 8 typed, weighted │
   ============                │  Storage: NetworkX + JSON  │
  ┌──────────────────┐         └───────────────────────────┘
  │  FastAPI Server   │
  │  • Sessions       │   ┌─────────────────────────┐
  │  • Event ingest   │   │   Replay System          │
  │  • Query API      │   │   JSONL → interactive    │
  │  • Graph state    │   │   HTML visualization     │
  │  • Auth           │   └─────────────────────────┘
  └──────────────────┘
```

---

## Quick Start

```bash
# Clone the repository
git clone git@github.com:MergeFold/CogniFold.git
cd CogniFold

# Install dependencies
uv sync  # or: pip install -e .

# Set API key (required for LLM features)
export GOOGLE_API_KEY='your-api-key'

# Run tests to verify setup
pytest tests/ -v
```

### Generate Events

```bash
cognifold generate --domain personal-timeline --persona software_engineer --events 50 --days 2
```

### Run Simulation

```bash
cognifold run data/generated/alex_chen_timeline.json --agent --save-graph output/graph.json -o output/
```

### Replay & Visualize

```bash
cognifold replay logs/replay_alex_chen_timeline_*.jsonl -o output/replay.html --open
```

### Query the Graph

```bash
# BM25 (fast, no API key needed)
cognifold query --graph output/graph.json --retrieval bm25 "morning routine"

# Hybrid (default, best general quality)
cognifold query --graph output/graph.json --retrieval hybrid "exercise habits"

# Agentic multi-round (complex queries, requires LLM API key)
cognifold query --graph output/graph.json --retrieval agentic "connections between diet and exercise"

# Interactive mode
cognifold query --graph output/graph.json --retrieval bm25 --interactive
```

### Start the HTTP Service

```bash
# Quick start
./scripts/start_server.sh

# Or manually
cognifold serve --host 127.0.0.1 --port 8000

# Interactive client
cognifold client --url http://localhost:8000
```

---

## Core Concepts

### Node Types

| Type | Description | ID Prefix |
|------|-------------|-----------|
| `event` | Direct representation of input events | `e-` |
| `concept` | Higher-level patterns from multiple events | `c-` |
| `intent` | Goals/desires that emerge from patterns | `i-` |
| `time` | Temporal anchors (deadlines, schedules) | `t-` |

### Edge Types

| Type | Weight | Usage |
|------|--------|-------|
| `GROUNDS` | 0.9 | Event grounds Concept/Intent |
| `CAUSES` | 0.9 | Event causes Event |
| `TRIGGERS` | 0.8 | Concept triggers Intent |
| `REINFORCES` | 0.7 | Event reinforces Concept |
| `PART_OF` | 0.7 | Sub-concept of parent |
| `DERIVED_FROM` | 0.6 | Concept derived from another |
| `DEADLINE_FOR` | 0.6 | Time is deadline for Intent |
| `RELATED_TO` | 0.5 | Generic relationship |

### Context Window Scoring

Nodes are scored using a composite formula:
```
Score = alpha * StructuralRank + beta * RecencyScore + gamma * AccessScore
```

| Component | Weight | Calculation |
|-----------|--------|-------------|
| StructuralRank | 0.4 | PageRank on graph topology |
| RecencyScore | 0.4 | `exp(-lambda * hours_since_update)` |
| AccessScore | 0.2 | Normalized usage frequency |

The context window is organized into three hierarchical levels:

| Level | Budget | Focus |
|-------|--------|-------|
| Immediate | 10% | Recent events, urgent intents |
| Working | 30% | Active concepts, patterns |
| Background | 50% | Historical context, weak signals |

### Retrieval Modes

| Mode | Description | Dependencies |
|------|-------------|-------------|
| `legacy` | Simple keyword matching | None |
| `bm25` | BM25 inverted index | None |
| `semantic` | Embedding cosine similarity (optional FAISS ANN) | Embedder |
| `hybrid` | BM25 + semantic with RRF fusion **(default)** | Embedder (degrades to BM25) |
| `agentic` | Multi-round: hybrid + LLM sufficiency check + query expansion | Embedder + LLM |

The **agentic** retriever runs two rounds:
1. Hybrid search + LLM judges whether results are sufficient
2. If insufficient: LLM generates complementary queries, runs parallel hybrid searches, fuses all results with multi-list RRF

---

## HTTP Service

Cognifold runs as a stateful REST API. Each client creates a **session** that owns an isolated concept graph, ranker, and optional LLM agent.

### Endpoints

All routes prefixed with `/api/v1`. OpenAPI docs at `/docs`.

| Category | Method | Path | Description |
|----------|--------|------|-------------|
| Health | GET | `/health` | Health check |
| Health | GET | `/ready` | Readiness + active sessions |
| Sessions | POST | `/sessions` | Create session |
| Sessions | GET | `/sessions/{id}` | Get session info |
| Sessions | DELETE | `/sessions/{id}` | Delete session |
| Sessions | POST | `/sessions/{id}/load` | Load graph file |
| Events | POST | `/sessions/{id}/events` | Ingest event (sync/async) |
| Events | POST | `/sessions/{id}/events/batch` | Batch ingest |
| Events | GET | `/sessions/{id}/tasks/{task_id}` | Poll async task |
| Query | POST | `/sessions/{id}/query` | Natural language query |
| Graph | GET | `/sessions/{id}/graph` | Graph state |
| Graph | GET | `/sessions/{id}/graph/stats` | Statistics |
| Graph | GET | `/sessions/{id}/graph/concepts` | Top concepts |
| Graph | GET | `/sessions/{id}/graph/intents` | Recent intents |
| Graph | GET | `/sessions/{id}/graph/events` | Recent events |
| Graph | GET | `/sessions/{id}/graph/nodes/{node_id}` | Node detail |
| Graph | GET | `/sessions/{id}/graph/nodes/{node_id}/expand` | BFS expand |

See [docs/SERVICE_API.md](docs/SERVICE_API.md) for full request/response schemas.

### Interactive CLI Client

```bash
cognifold client --url http://localhost:8000 --api-key secret \
  --google-api-key "$GOOGLE_API_KEY" --model "gemini-2.5-flash"
```

| Command | Description |
|---------|-------------|
| `:session create` | Create a new session |
| `:session info` | Session details |
| `:ingest TYPE TITLE [--desc D]` | Ingest an event |
| `:stats` | Graph statistics |
| `:concepts` / `:intents` / `:events` | List nodes by type |
| `:node <ID>` | Inspect a node |
| `:expand <ID> [N]` | BFS expand N layers from node |
| `:graph [N]` | Show graph state |
| `:load <FILE>` | Load graph JSON |
| `any text` | Natural language query |

---

## Supported Domains

| Domain | Description | Command |
|--------|-------------|---------|
| `personal-timeline` | Daily activities | `--persona software_engineer` |
| `computer-activity` | Computer usage | `--profile software_developer` |
| `service-logs` | Microservice events | `--topology ecommerce` |
| `wiki` | Markdown/PDF documents | `cognifold build-timeline` |

---

## Project Structure

```
cognifold/
├── src/cognifold/          # 101 files, 27k LOC
│   ├── models/             # Pydantic schemas (Event, Node, Edge, UpdatePlan)
│   ├── graph/              # NetworkX wrapper, persistence, validation, metrics
│   ├── scoring/            # PageRank, hierarchical context, node ranking
│   ├── agent/              # LangGraph agent, prompts, domain config, sections
│   ├── executor/           # Plan execution with validation and rollback
│   ├── query/              # Query agent, strategies, assembly, LLM utilities
│   ├── retrieval/          # BM25, hybrid, agentic multi-round retrieval
│   ├── embeddings/         # Embedding providers (Gemini/OpenAI), FAISS ANN
│   ├── temporal/           # Temporal entity extraction, date parsing
│   ├── intent/             # Intent-to-action system, queue, executor
│   ├── service/            # HTTP service (FastAPI), sessions, routes, auth
│   ├── generator/          # Event generation (personal, computer, service)
│   ├── importers/          # Data importers (wiki)
│   ├── replay/             # Graph evolution logging and visualization
│   ├── simulator/          # Timeline processing, visualization
│   └── cli/                # CLI commands (generate, run, query, serve, client)
├── tests/                  # 33 files, 717 tests
│   ├── unit/               # Fast isolated tests
│   ├── integration/        # Pipeline + API integration tests
│   └── fixtures/           # Shared test data factories
├── configs/                # Domain-specific prompt profiles (YAML)
├── data/                   # Sample data and generated timelines
├── benchmarks/             # Benchmark evaluation suite
├── scripts/                # Utility scripts
├── docs/                   # Documentation
└── Makefile                # Development commands
```

---

## Tech Stack

| Category | Tools |
|----------|-------|
| Language | Python 3.9+ (target 3.11+) |
| Agent | LangGraph + Google Gemini / OpenAI |
| Graph | NetworkX (MultiDiGraph) |
| Service | FastAPI + uvicorn |
| Search | BM25 (built-in) + FAISS (optional) |
| Validation | Pydantic v2 |
| Embeddings | numpy + optional FAISS ANN |
| Visualization | pyvis (interactive HTML) |
| Quality | ruff + pyright (strict) + pytest |

---

## Development

```bash
# Install with dev dependencies
make dev  # or: pip install -e ".[dev,agent,service]"

# Run all quality checks
make check

# Run tests
make test

# Format + fix lint
make fix
```

### Quality Gates

All must pass before committing:

```bash
ruff format --check src/ tests/   # Formatting
ruff check src/ tests/            # Linting
pyright src/                      # Type checking (strict)
pytest tests/ -v                  # 717 tests
```

### Contributing

1. Create a feature branch from `cognifold-dev`
2. Make changes with tests
3. Ensure all quality gates pass
4. Submit PR to `cognifold-dev`

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

---

## Development Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1-6 | Foundation through Multi-Domain | Complete |
| 7 | Memory Query Interface | Complete |
| 8 | Intent Execution System | Complete |
| 9 | Typed Edges + Hierarchical Context | Complete |
| 10.2-10.4 | Temporal, Embeddings, Hybrid Retrieval | Complete |
| 11 | Service Layer + HTTP API | Complete |
| 11.1 | FAISS ANN, Agentic Retrieval, Unified Embeddings | Complete |
| 13 | Modular System Prompt Composition | Complete |
| 10.5 | LLM-powered Query Understanding | Planned |
| 12 | Benchmark Evaluation (LoCoMo, MSC, BABILong) | Planned |

See [docs/PHASES.md](docs/PHASES.md) for detailed specifications and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for implementation details.

## License

MIT
