# Archon - WORKSPACE NAVIGATION SPR

## CORE MISSION
Archon is an AI-native command center that gives coding assistants a shared knowledge base, project/task management, and MCP-accessible workflows.
It enables teams to ingest docs, index them for retrieval, and orchestrate implementation work through a unified UI and API surface.

---

## ARCHITECTURE PARADIGM

**Pattern**: Multi-service modular monorepo with vertical-slice frontend and service-layer backend

**Key Principles**: Service-layer orchestration, type-safe boundaries, fix-forward iteration, KISS/YAGNI

**Structure**:
```
Archon/
├── archon-ui-main/                  # React + Vite UI, feature slices
├── python/src/server/               # FastAPI API + services + exceptions
├── python/src/mcp_server/           # MCP tool surface
├── python/src/agent_work_orders/    # Agent work orders microservice
├── migration/                       # SQL setup and versioned migrations
├── PRPs/ai_docs/                    # Architecture and implementation standards
└── .sia/                            # Project intelligence and requirements
```

**Bounded Contexts**:
1. **Knowledge Ingestion & Retrieval**: Source crawling/upload, chunking, embeddings, RAG search.
2. **Project & Task Management**: Projects, tasks, assignment and status workflows.
3. **MCP Integration**: Tool endpoints for AI clients (search, project/task/document/version operations).
4. **Agent Work Orders**: Independent workflow execution service.

---

## DOMAIN MODEL

### Knowledge Context

**Aggregate Roots**:
- **Source** (Aggregate Root): Represents crawled/uploaded source; owns crawl metadata and ingestion status.
- **Document** (Entity): Chunked content with embeddings and source relationship.
- **CodeExample** (Entity): Extracted code snippets with language/relevance metadata.

**Aggregate Pattern**: Source lifecycle drives document generation and retrieval readiness.

### Work Management Context

**Aggregate Roots**:
- **Project** (Aggregate Root): Feature settings, linked work and metadata.
- **Task** (Entity): Status workflow (`todo`, `doing`, `review`, `done`) and assignment.

**Aggregate Pattern**: Project is the transactional boundary for grouped tasks.

---

## INFRASTRUCTURE LAYER

### Backend API
- **python/src/server/main.py**: FastAPI app and exception handlers.
- **python/src/server/api_routes/**: HTTP API route modules.
- **python/src/server/services/**: Business orchestration and persistence calls.

### MCP Server
- **python/src/mcp_server/**: Tool registration and feature-specific MCP operations.

### Data & Migrations
- **migration/complete_setup.sql**: Full bootstrap schema.
- **migration/0.1.0/**: Ordered incremental schema changes.

### Frontend
- **archon-ui-main/src/features/**: Vertical slice features with hooks/services/types.
- **archon-ui-main/src/features/ui/primitives/**: UI primitives and design foundation.

---

## APPLICATION LAYER

- Service layer pattern: API Route → Service → Database/external provider.
- Query workflows in frontend via TanStack Query hooks and feature-local services.
- Work-order execution isolated in a dedicated microservice to reduce coupling.

---

## API/CLI LAYER

- **python/src/server/api_routes/**: REST endpoints consumed by UI.
- **python/src/mcp_server/**: MCP tool interface for IDE agents.
- **archon-ui-main/**: Dashboard UI for ingestion, search, and work management.

---

## TECH STACK

**Language**: Python 3.12 + TypeScript

**Backend**: FastAPI, Pydantic, Supabase/Postgres, MCP server modules, uv

**Frontend**: React, Vite, TanStack Query, Tailwind, Radix primitives

**Tools**: Docker Compose, Pytest, Ruff, Mypy, Vitest, Biome, ESLint

---

## KEY WORKFLOWS

### Document-to-RAG Pipeline

1. Source ingestion request enters API route.
2. Service layer crawls/uploads and normalizes content.
3. Documents/chunks + embeddings persist to Supabase tables.
4. Retrieval endpoints and MCP tools expose semantic search.

### Project Task Execution Loop

1. UI/MCP creates or updates project/task entities.
2. Backend service validates and persists state transitions.
3. Agent work orders consume tasks for automated execution.

---

## FILE NAVIGATION PATTERNS

### Backend Core
- `python/src/server/api_routes/`: endpoint contract surface
- `python/src/server/services/`: business use-case orchestration
- `python/src/server/exceptions.py`: typed exception definitions

### MCP Surface
- `python/src/mcp_server/features/`: feature-by-feature MCP tools

### Frontend Features
- `archon-ui-main/src/features/[feature]/components/`
- `archon-ui-main/src/features/[feature]/hooks/`
- `archon-ui-main/src/features/[feature]/services/`

### Architecture Documentation
- `PRPs/ai_docs/ARCHITECTURE.md`
- `PRPs/ai_docs/DATA_FETCHING_ARCHITECTURE.md`
- `PRPs/ai_docs/QUERY_PATTERNS.md`

---

## MENTAL MODEL COMPRESSION

Archon is a multi-service context platform: ingest knowledge, store structured artifacts, and expose those artifacts through a UI + MCP tools that coding agents can act on. Backend services keep domain operations explicit through route/service separation, while frontend feature slices consume typed APIs through TanStack Query. Agent work orders extend the system from passive context retrieval to active execution workflows.

**Critical Path**:
1. Knowledge ingestion: API route → service pipeline → Supabase persistence → RAG retrieval.
2. Task orchestration: UI/MCP command → project/task service update → agent work-order execution.

**Architecture DNA**: Modular services with clear boundaries, project-local documentation intelligence in `.sia/`, and shared operational workflows through MCP.

**Key Invariants**:
- Source/document relationships remain valid and non-corrupt.
- Service layer owns business orchestration, not route handlers.
- Frontend feature slices keep data fetching colocated with feature hooks.
- MCP tools expose domain operations without bypassing backend invariants.

---

## CURRENT STATUS

**Completed**:
- ✅ SIA scaffolding installed in `.sia/`
- ✅ Core architecture and standards docs available in `PRPs/ai_docs/`

**In Progress**:
- 🔄 Continuous iteration on UI, API, and agent work-order capabilities

**Planned**:
- 📋 Additional project-specific SIA skills and archived requirement intelligence

---

**Last Updated**: 2026-02-17
**SIA Version**: 1.1.0
