# REQ-001 — Domain Analysis

## RESEARCH SOURCES
- **DeepWiki**: `coleam00/Archon` — Supabase usage map (✅ queried 2026-02-17)
- **Skill**: `.github/skills/pgvector-semantic-search/SKILL.md` — pgvector HNSW + halfvec patterns
- **Static analysis**: `client_manager.py`, `source_management_service.py`, `storage/` services
- **Architecture doc**: `PRPs/ai_docs/ARCHITECTURE.md`

---

## CURRENT STATE ANALYSIS

### Supabase Dependency Map

```
client_manager.py
  └─ get_supabase_client()          ← singleton entry point
       ├── source_management_service.py  (CRUD archon_sources, archon_crawled_pages)
       ├── storage/document_storage_service.py  (INSERT documents + embeddings)
       ├── storage/code_storage_service.py      (INSERT code_examples, batch)
       ├── storage/storage_services.py          (orchestrates above)
       ├── project services (CRUD projects, tasks, versions)
       └── credential_service.py               (archon_settings table)
```

**supabase-py API calls en uso:**
| Pattern | Files |
|---------|-------|
| `.table(X).select("*").execute()` | source_mgmt, project services |
| `.table(X).insert({}).execute()` | storage services |
| `.table(X).update({}).eq().execute()` | source_mgmt, project services |
| `.table(X).delete().eq().execute()` | source_mgmt |
| `.rpc("match_*", params).execute()` | knowledge_service (RAG) |

### Schema Compatibility
- `migration/complete_setup.sql` ya es PostgreSQL estándar + pgvector
- No hay funciones Supabase-specific en schema (no `auth.*`, no `storage.*`)
- RPC calls (`match_documents`, `search_code_examples`) son funciones PL/pgSQL → portables

---

## DESIGN DECISION: Adapter Pattern

### Por qué Adapter y no Repository completo
- Repository requeriría reescribir TODOS los servicios (30+ métodos)
- Adapter wraps el client existente y expone la misma interfaz a los servicios
- **Impacto mínimo**: solo `client_manager.py` + nuevo módulo adapter

### Interface propuesta: `DatabaseClient` (Protocol)

```python
class DatabaseClient(Protocol):
    def table(self, name: str) -> TableQuery: ...
    def rpc(self, name: str, params: dict) -> RpcQuery: ...
```

`TableQuery` y `RpcQuery` son wrappers que exponen `.select()`, `.insert()`, `.update()`, `.delete()`, `.eq()`, `.execute()` → misma cadena fluida que `supabase-py`.

### Supabase Adapter
- Wraps `supabase-py` `Client` — zero behavioral change
- `DB_PROVIDER=supabase` → factory retorna este adapter

### PostgreSQL Adapter
- usa `psycopg2` (sync, para mantener interfaz síncrona existente)
- Implementa misma fluent chain con query builder interno mínimo
- `DB_PROVIDER=postgres` + `POSTGRES_DSN` → factory retorna este adapter

---

## pgvector STANDALONE CONFIGURATION

Basado en skill `pgvector-semantic-search`:

```sql
-- Embedding dimension: 1536 (OpenAI default) configurable via env
-- Index: HNSW con halfvec para 50% menos memoria
CREATE INDEX ON archon_crawled_pages 
  USING hnsw (embedding halfvec_cosine_ops) 
  WITH (m = 16, ef_construction = 64);

-- Query pattern:
SET hnsw.ef_search = 100;
SELECT * FROM archon_crawled_pages 
ORDER BY embedding <=> $1::halfvec(1536) LIMIT 10;
```

**Binary quantization** disponible para datasets grandes (>5M vectores):
- Columna generada `embedding_bq bit(1536)` + re-ranking
- Activable via `PGVECTOR_QUANTIZATION=binary` si se necesita

---

## DOCKER COMPOSE PROFILE

Nuevo profile `postgres-standalone`:
- Servicio: `postgres:16` con extension `pgvector`
- Init: monta `migration/complete_setup.sql`
- No reemplaza el PostgreSQL de Supabase → coexisten por puerto distinto

---

## RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| RPC functions no migradas | HIGH | Crear `migration/postgres_standalone_functions.sql` |
| Comportamiento `.execute()` divergente en error cases | MEDIUM | Tests de integración en cada adapter |
| Sync adapter vs async (credential_service usa async) | LOW | credential_service ya usa `httpx`, no Supabase async |
| Embedding dimension hardcoded | LOW | Env var `EMBEDDING_DIMENSION` default 1536 |

---

## CONCLUSIONS

1. **Adapter Pattern** es el approach de menor riesgo y menor diff de código
2. `supabase-py` fluent API es simulable con un query builder de ~200 líneas
3. El schema es 100% portable — RPC functions incluidas
4. Docker Compose profile aísla el caso standalone sin romper el existente
5. `DB_PROVIDER=supabase` como default garantiza backward compatibility (I-3)
