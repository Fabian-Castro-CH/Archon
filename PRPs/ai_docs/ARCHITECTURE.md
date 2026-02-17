# Archon Architecture

## Overview

Archon is a knowledge management system with AI capabilities, built as a monolithic application with vertical slice organization. The frontend uses React with TanStack Query, while the backend runs FastAPI with multiple service components.

## Tech Stack

**Frontend**: React 18, TypeScript 5, TanStack Query v5, Tailwind CSS, Vite
**Backend**: Python 3.12, FastAPI, Supabase/PostgreSQL adapter layer, PydanticAI
**Infrastructure**: Docker, PostgreSQL + pgvector

## Directory Structure

### Backend (`python/src/`)
```text
server/              # Main FastAPI application
├── api_routes/      # HTTP endpoints
├── services/        # Business logic
├── models/          # Data models
├── config/          # Configuration
├── middleware/      # Request processing
└── utils/           # Shared utilities

mcp_server/          # MCP server for IDE integration
└── features/        # MCP tool implementations

agents/              # AI agents (PydanticAI)
└── features/        # Agent capabilities
```

### Frontend (`archon-ui-main/src/`)
```text
features/            # Vertical slice architecture
├── knowledge/       # Knowledge base feature
├── projects/        # Project management
│   ├── tasks/       # Task sub-feature
│   └── documents/   # Document sub-feature
├── progress/        # Operation tracking
├── mcp/             # MCP integration
├── shared/          # Cross-feature utilities
└── ui/              # UI components & hooks

pages/               # Route components
components/          # Legacy components (migrating)
```

## Core Modules

### Knowledge Management
**Backend**: `python/src/server/services/knowledge_service.py`
**Frontend**: `archon-ui-main/src/features/knowledge/`
**Features**: Web crawling, document upload, embeddings, RAG search

### Project Management
**Backend**: `python/src/server/services/project_*_service.py`
**Frontend**: `archon-ui-main/src/features/projects/`
**Features**: Projects, tasks, documents, version history

### MCP Server
**Location**: `python/src/mcp_server/`
**Purpose**: Exposes tools to AI IDEs (Cursor, Windsurf)
**Port**: 8051

### AI Agents
**Location**: `python/src/agents/`
**Purpose**: Document processing, code analysis, project generation
**Port**: 8052

### Agent Work Orders (Optional)
**Location**: `python/src/agent_work_orders/`
**Purpose**: Workflow execution engine using Claude Code CLI
**Port**: 8053

## API Structure

### RESTful Endpoints
Pattern: `{METHOD} /api/{resource}/{id?}/{sub-resource?}`

**Examples from** `python/src/server/api_routes/`:
- `/api/projects` - CRUD operations
- `/api/projects/{id}/tasks` - Nested resources
- `/api/knowledge/search` - RAG search
- `/api/progress/{id}` - Operation status

### Service Layer
**Pattern**: `python/src/server/services/{feature}_service.py`
- Handles business logic
- Database operations via database client abstraction
- Returns typed responses

## Frontend Architecture

### Data Fetching
**Core**: TanStack Query v5
**Configuration**: `archon-ui-main/src/features/shared/config/queryClient.ts`
**Patterns**: `archon-ui-main/src/features/shared/config/queryPatterns.ts`

### State Management
- **Server State**: TanStack Query
- **UI State**: React hooks & context
- **No Redux/Zustand**: Query cache handles all data

### Feature Organization
Each feature follows vertical slice pattern:
```text
features/{feature}/
├── components/      # UI components
├── hooks/           # Query hooks & keys
├── services/        # API calls
└── types/           # TypeScript types
```

### Smart Polling
**Implementation**: `archon-ui-main/src/features/ui/hooks/useSmartPolling.ts`
- Visibility-aware (pauses when tab hidden)
- Variable intervals based on focus state

## Database

**Provider**: Configurable via `DB_PROVIDER`
**Default**: `supabase`
**Alternative**: `postgres` (standalone PostgreSQL + pgvector)

### Database Abstraction Layer
- **Protocol**: `python/src/server/db/protocol.py` (`DatabaseClient`, `TableQueryBuilder`, `RpcQueryBuilder`)
- **Factory**: `python/src/server/db/factory.py` (`get_db_client()` selects provider at startup)
- **Supabase Adapter**: `python/src/server/db/supabase_adapter.py`
- **PostgreSQL Adapter**: `python/src/server/db/postgres_adapter.py`
- **Service Entry Point**: `python/src/server/services/client_manager.py`

All application services depend on the shared database client interface, so business logic does not change when switching providers.

### Runtime Configuration
- `DB_PROVIDER=supabase` uses Supabase settings (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)
- `DB_PROVIDER=postgres` requires `POSTGRES_DSN`
- `POSTGRES_POOL_MIN` and `POSTGRES_POOL_MAX` control connection pool size for standalone mode
- `DB_ENCRYPTION_SEED` can be used for credential encryption when not using Supabase keys

### Local Standalone PostgreSQL
- Docker profile: `postgres-standalone`
- Service: `archon-postgres` (`pgvector/pgvector:pg16`)
- Bootstrap script: `migration/postgres_standalone/01_setup.sh`
- Setup docs: `migration/postgres_standalone/README.md`

### Main Tables
- `sources` - Knowledge sources
- `documents` - Document chunks with embeddings
- `code_examples` - Extracted code
- `archon_projects` - Projects
- `archon_tasks` - Tasks
- `archon_document_versions` - Version history

## Key Architectural Decisions

### Vertical Slices
Features own their entire stack (UI → API → DB). See any `features/{feature}/` directory.

### No WebSockets
HTTP polling with smart intervals. ETag caching reduces bandwidth by ~70%.

### Query-First State
TanStack Query is the single source of truth. No separate state management needed.

### Direct Database Values
No translation layers. Database values (e.g., `"todo"`, `"doing"`) used directly in UI.

### Browser-Native Caching
ETags handled by browser, not JavaScript. See `archon-ui-main/src/features/shared/api/apiClient.ts`.

## Deployment

### Development
```bash
# Backend
docker compose up -d
# or
cd python && uv run python -m src.server.main

# Frontend
cd archon-ui-main && npm run dev
```

### Production
Single Docker Compose deployment with all services.

## Configuration

### Environment Variables
**Required**:
- `DB_PROVIDER=supabase`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- `DB_PROVIDER=postgres`: `POSTGRES_DSN`

**Common Optional**: `POSTGRES_POOL_MIN`, `POSTGRES_POOL_MAX`, `DB_ENCRYPTION_SEED`
**Optional**: See `.env.example`

### Feature Flags
Controlled via Settings UI. Projects feature can be disabled.

### LLM Provider Configuration
Provider selection and model are stored in the `archon_settings` DB table (category: `rag_strategy`). All providers share the same routing layer in `python/src/server/services/llm_provider_service.py`.

| Provider | Chat | Embeddings | Auth | URL |
|---|---|---|---|---|
| `openai` | ✅ | ✅ | `OPENAI_API_KEY` | Default |
| `google` | ✅ | ✅ | `GOOGLE_API_KEY` | Default |
| `anthropic` | ✅ | — | `ANTHROPIC_API_KEY` | Default |
| `openrouter` | ✅ | — | `OPENROUTER_API_KEY` | Default |
| `grok` | ✅ | — | `GROK_API_KEY` | Default |
| `ollama` | ✅ | ✅ | None | `LLM_BASE_URL` / `OLLAMA_EMBEDDING_URL` |
| `vllm` | ✅ | ✅ | `VLLM_API_KEY` (optional) | `VLLM_BASE_URL` / `VLLM_EMBEDDING_URL` |

vLLM exposes an OpenAI-compatible REST API; set `VLLM_BASE_URL` (e.g., `http://localhost:8000`) in Settings to point Archon at your running vLLM server.

## Recent Refactors (Phases 1-5)

1. **Removed ETag cache layer** - Browser handles HTTP caching
2. **Standardized query keys** - Each feature owns its keys
3. **Fixed optimistic updates** - UUID-based with nanoid
4. **Configured deduplication** - Centralized QueryClient
5. **Removed manual invalidations** - Trust backend consistency

## Performance Optimizations

- **Request Deduplication**: Same query key = one request
- **Smart Polling**: Adapts to tab visibility
- **ETag Caching**: 70% bandwidth reduction
- **Optimistic Updates**: Instant UI feedback

## Testing

**Frontend Tests**: `archon-ui-main/src/features/*/tests/`
**Backend Tests**: `python/tests/`
**Patterns**: Mock services and query patterns, not implementation

## Future Considerations

- Server-Sent Events for real-time updates
- GraphQL for selective field queries
- Separate databases per bounded context
- Multi-tenant support