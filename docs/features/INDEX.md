# Features Index

Comprehensive documentation for all Nexus AI Backend features.

## Core Features

| Feature | Description | Document |
|--------|-------------|----------|
| **Pipeline** | Unified execution for skills/workflows | [PIPELINE.md](PIPELINE.md) |
| **Memory** | Vector-based long-term memory | [MEMORY.md](MEMORY.md) |
| **Checkpoint** | State snapshots for replay/debug | [CHECKPOINT.md](CHECKPOINT.md) |
| **Sandbox** | Tool permissions and rate limits | [SANDBOX.md](SANDBOX.md) |
| **Multi-Agent** | Planner/Executor/Critic coordination | [MULTI-AGENT.md](MULTI-AGENT.md) |

## Feature Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent OS Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │ Pipeline │───▶│ Memory   │◀───▶│Checkpoint│            │
│  │ System   │    │ System   │    │ System   │            │
│  └──────────┘    └──────────┘    └──────────┘            │
│        ▲              │                ▲                     │
│        │              ▼                │                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │ Multi-   │    │ Sandbox │    │  Agent   │            │
│  │ Agent    │    │ System  │    │ Runtime  │            │
│  └──────────┘    └──────────┘    └──────────┘            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Related Documentation

- [API Reference](../API.md)
- [Architecture](../ARCHITECTURE.md)
- [CLI Reference](../CLI.md)
- [Changelog](../CHANGELOG.md)

## Quick Start

1. **Run Pipeline**: `POST /api/v1/agents/pipelines/execute`
2. **Create Checkpoint**: `POST /api/v1/agents/pipelines/checkpoints`
3. **Execute Multi-Agent**: `POST /api/v1/agents/multi-agent/execute`

## Database Tables

- `agent_memories` - Vector embeddings
- `agent_checkpoints` - Execution snapshots
- `agent_policies` - Tool permissions
- `agent_definitions` - Agent registry
- `skill_definitions` - Skill registry