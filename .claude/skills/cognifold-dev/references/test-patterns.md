# Cognifold Test Patterns

## Test Fixture Setup

### conftest.py Fixtures (tests/conftest.py)
- `sample_graph` — Pre-populated ConceptGraph with nodes and edges
- `sample_event` — Standard Event instance for testing

### Mock Embedding Provider
```python
from cognifold.embeddings.providers import MockEmbeddingProvider
from cognifold.embeddings.config import EmbeddingConfig

config = EmbeddingConfig(provider="mock", dimensions=64)
provider = MockEmbeddingProvider(config)
# Returns deterministic hash-based vectors — no API key needed
```

### Mocking LLM Calls
```python
from unittest.mock import patch, MagicMock

# Mock Gemini agent
with patch("cognifold.agent.agent.genai") as mock_genai:
    mock_model = MagicMock()
    mock_genai.GenerativeModel.return_value = mock_model
    mock_model.generate_content.return_value = mock_response
    # ... test agent code
```

### Creating Test Graphs
```python
from cognifold.graph.store import ConceptGraph
from cognifold.models.node import Node
from cognifold.models.plan import Edge

graph = ConceptGraph()
node = Node(id="test-1", node_type="concept", title="Test", description="A test node")
graph.add_node(node)
edge = Edge(source_id="test-1", target_id="test-2", edge_type="RELATED_TO", weight=0.5)
graph.add_edge(edge)
```

## Test Naming Convention

```python
def test_{module}_{feature}_{scenario}():
    """Test that {feature} behaves correctly when {scenario}."""
```

Examples:
- `test_bm25_search_returns_ranked_results`
- `test_hybrid_retriever_falls_back_to_bm25`
- `test_plan_executor_rollback_on_error`

## Running Specific Tests

```bash
# Single file
pytest tests/unit/test_retrieval.py -v

# Single test
pytest tests/unit/test_retrieval.py::test_bm25_search_basic -v

# By keyword
pytest tests/ -v -k "embedding"

# Integration only
pytest tests/integration/ -v

# With coverage
make coverage
```

## Known Test Issues

- 3 BM25 tests were pre-existing failures (tokenization, search_basic, add_document) — fixed in Phase 11.1
- Integration tests may require API keys (GOOGLE_API_KEY or OPENAI_API_KEY)
- Service API tests use TestClient (no real server needed)
