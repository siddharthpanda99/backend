# Memory System

Vector-based memory for agent long-term storage and semantic search.

## Overview

The Memory System provides pgvector integration for storing and retrieving agent memories with semantic similarity.

## Components

### VectorMemoryStore
```python
class VectorMemoryStore:
    def initialize()           # Create tables
    def add_memory(content, agent_id, session_id, metadata) -> memory_id
    def search(query, agent_id, session_id, limit) -> List[MemorySearchResult]
    def get_memories(agent_id, session_id, limit) -> List[MemoryEntry]
    def delete_memory(memory_id) -> bool
```

### ContextBuilder
```python
class ContextBuilder:
    def build_context(query, agent_id, session_id, max_tokens) -> Dict
```
Builds context from memory for agent consumption.

## Usage

### Initialize
```python
from common_lib.modules.orchestration.memory.vector_store import VectorMemoryStore

store = VectorMemoryStore(
    db_session=session,
    embedding_model=embedding_model
)

await store.initialize()
```

### Add Memory
```python
memory_id = await store.add_memory(
    content="User prefers concise responses",
    agent_id="base_agent",
    session_id="session_123",
    metadata={"preference": "concise"}
)
```

### Search
```python
results = await store.search(
    query="What does user prefer?",
    agent_id="base_agent",
    session_id="session_123",
    limit=5
)

for r in results:
    print(r.entry.content, r.score)
```

### Build Context
```python
from common_lib.modules.orchestration.memory.vector_store import ContextBuilder

builder = ContextBuilder(store)
context = await builder.build_context(
    query="Summarize the conversation",
    agent_id="base_agent",
    session_id="session_123"
)

print(context["relevant_memories"])
print(context["context_summary"])
```

## Database Schema

```sql
CREATE TABLE agent_memories (
    id TEXT PRIMARY KEY,
    agent_id TEXT,
    session_id TEXT,
    content TEXT NOT NULL,
    metadata_json JSONB,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
)
```

## Related Files

- `common_lib/src/.../orchestration/memory/vector_store.py`