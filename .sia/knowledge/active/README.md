# Archon Active Knowledge Base

This directory stores project-specific operational knowledge used by SIA agents.

## Project Overview
Archon provides a shared knowledge and execution platform for AI coding assistants through:
- Knowledge ingestion (crawl/upload) and semantic retrieval
- Project/task management workflows
- MCP server tools for IDE agents
- Optional agent work-orders execution service

## Domain Glossary
- **Source**: Original crawled/uploaded material tracked for ingestion.
- **Document**: Processed chunk with embeddings for retrieval.
- **Project**: Top-level work container with feature settings and linked tasks.
- **Task**: Unit of work with status lifecycle and assignee.
- **MCP Tool**: Action/query endpoint exposed to external coding assistants.
- **Agent Work Order**: Executable workflow item handled by dedicated service.

## Key Architectural Decisions
- Service layer pattern in backend: route handlers delegate to services.
- Vertical-slice frontend architecture in `archon-ui-main/src/features/`.
- Configurable database backend via `DB_PROVIDER` (`supabase` default, `postgres` standalone) with SQL-based migrations.
- MCP capabilities organized by feature under `python/src/mcp_server/features/`.

## Research Cache Pointers
- `PRPs/ai_docs/ARCHITECTURE.md`
- `PRPs/ai_docs/DATA_FETCHING_ARCHITECTURE.md`
- `PRPs/ai_docs/QUERY_PATTERNS.md`
- `PRPs/ai_docs/ETAG_IMPLEMENTATION.md`

## Document Lifecycle
Move stale notes to `.sia/knowledge/_archive/` after major milestones; keep active notes concise and decision-oriented.
