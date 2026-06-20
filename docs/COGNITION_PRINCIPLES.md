# Cognition Principles

Core architectural principles for the Cognifold cognitive infrastructure. These principles guide all design decisions and code reviews.

---

## 1. Event-Driven Cognition Engine

**Principle**: Every piece of information enters the system as a timestamped event. The system processes events in real-time, building understanding incrementally rather than operating on static document collections.

**In code**: Events flow through `Event → Agent → UpdatePlan → Executor → Graph`. No information enters the graph without passing through the event pipeline.

**Violation signals**:
- Direct graph manipulation bypassing the event pipeline
- Batch-loading documents without event decomposition
- Static snapshots treated as ground truth

## 2. Cognitive Folding

**Principle**: Raw events are progressively folded into higher-level abstractions: events → concepts → intentions. Each layer adds semantic compression and enables reasoning that raw events alone cannot support.

**In code**:
- **Events** (blue nodes): Direct representations of input
- **Concepts** (green nodes): Patterns and facts extracted from events
- **Intents** (orange nodes): Goals and desires that emerge from patterns
- **Time** (purple nodes): Temporal anchors connecting everything

**Violation signals**:
- Storing events without concept extraction (flat memory)
- Concepts not linked back to grounding events
- No intent emergence from accumulated concepts

## 3. Intention Emergence

**Principle**: The system proactively identifies emerging intentions from patterns, not just reacting to explicit user requests. Intents follow a lifecycle: `pending → action_scheduled → resolved/rejected/deferred`.

**In code**: Intent nodes are created by the agent when patterns suggest a goal. The intent system (`src/cognifold/intent/`) manages lifecycle, calibration, and feedback loops.

**Violation signals**:
- System only answers queries (purely reactive)
- No intent nodes being created during event processing
- Intents without grounding concept chains

## 4. Cognitive Assets

**Principle**: The graph accumulates judgment over time — not just data. PageRank scores, access frequencies, concept strengths, and calibrated intent profiles represent accumulated cognitive value that improves with use.

**In code**:
- `HierarchicalScorer` computes multi-signal scores (PageRank + recency + access frequency)
- Intent calibration uses EMA-based feedback profiles
- Concept strengths are reinforced by repeated observations

**Violation signals**:
- Treating all nodes as equally important (no scoring)
- Discarding accumulated scores on graph reload
- Static weights that don't adapt to usage patterns

## 5. Open Infrastructure

**Principle**: Cognifold is domain-agnostic cognitive infrastructure, not a learning app or chatbot. Any domain (personal assistant, enterprise knowledge, research analysis) should be able to build on the same engine.

**In code**: Domain-specific behavior is configured through prompt profiles (`configs/`), not hardcoded. The core engine (`src/cognifold/`) contains no domain-specific logic.

**Violation signals**:
- Hardcoded domain terms in core modules (e.g., "study", "quiz", "lesson")
- Domain-specific scoring logic in `src/cognifold/scoring/`
- Business rules in graph operations

---

## Anti-Patterns

### Anti-Pattern 1: Flat Memory Store
**What it looks like**: Storing events as independent records without concept extraction or relationship building. The graph is just a timestamped list.
**Why it's wrong**: Loses the "folding" that gives Cognifold its name. Without concept elevation, the system can't reason beyond keyword matching.
**Fix**: Ensure every event processing cycle generates concepts and edges, not just event nodes.

### Anti-Pattern 2: RAG Wrapper
**What it looks like**: Using the graph only as a document store for retrieval-augmented generation. Query → retrieve chunks → send to LLM.
**Why it's wrong**: Ignores the graph's structural knowledge (edges, PageRank, multi-hop paths). Reduces Cognifold to a vector database with extra steps.
**Fix**: Use graph-aware retrieval that leverages topology (BFS expansion, edge traversal, hierarchical scoring).

### Anti-Pattern 3: Keyword Search Only
**What it looks like**: Retrieval relying solely on BM25 or substring matching, ignoring semantic similarity and graph structure.
**Why it's wrong**: Misses semantically related content, can't handle paraphrasing, and fails on multi-hop questions that require traversing relationships.
**Fix**: Use hybrid retrieval (BM25 + semantic + graph structure). Ensure embedding index is maintained.

### Anti-Pattern 4: Static Snapshot
**What it looks like**: Building the graph once and querying it without updates. No new events, no score recalculation, no intent lifecycle progression.
**Why it's wrong**: Cognifold is designed as a living, evolving system. Static graphs lose temporal relevance and can't accumulate cognitive assets.
**Fix**: Continuous event ingestion, periodic score recalculation, intent lifecycle management.

---

## Alignment Checklist for Code Reviews

Use this checklist when reviewing PRs that touch core modules:

- [ ] **Event pipeline preserved**: Changes don't bypass event → agent → executor flow
- [ ] **Folding maintained**: Events produce concepts; concepts produce intents where appropriate
- [ ] **Graph topology used**: Retrieval and scoring use edges and structure, not just node content
- [ ] **Scores accumulate**: Changes don't reset or ignore accumulated PageRank/strength/frequency
- [ ] **Domain-agnostic**: No domain-specific terms in core modules
- [ ] **Temporal awareness**: Time nodes and recency decay are respected
- [ ] **Intent lifecycle**: Intent state transitions follow the defined lifecycle
- [ ] **No anti-patterns**: Implementation doesn't fall into Flat Memory, RAG Wrapper, Keyword-Only, or Static Snapshot patterns

---

## Module-to-Principle Mapping

| Module | Primary Principle | Key Concern |
|--------|------------------|-------------|
| `agent/` | Cognitive Folding | Must extract concepts and intents, not just echo events |
| `executor/` | Event-Driven Engine | Must validate and atomically apply plans |
| `graph/` | Cognitive Assets | Must preserve accumulated structure and scores |
| `scoring/` | Cognitive Assets | Must use multi-signal scoring, not flat ranking |
| `query/` | Open Infrastructure | Must use graph-aware retrieval, not just keyword search |
| `retrieval/` | Cognitive Folding | Must leverage graph topology in search |
| `intent/` | Intention Emergence | Must support full intent lifecycle |
| `temporal/` | Event-Driven Engine | Must extract and link temporal information |
| `embeddings/` | Open Infrastructure | Must support hybrid retrieval strategies |
| `service/` | Open Infrastructure | Must expose domain-agnostic API |

---

## When to Reference This Document

- **Code reviews**: Check alignment checklist for PRs touching `agent/`, `query/`, `graph/`, `scoring/`, `intent/`
- **Architecture decisions**: Validate new designs against the 5 principles
- **Benchmark analysis**: Map failure modes to principle violations
- **New module design**: Ensure new modules fit the principle framework
