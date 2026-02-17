# REQ-001 — QUANT Breakdown

## SUMMARY
**Total**: 7 QUANTs | **AI est.**: ~18h | **Human review**: ~4h  
**Critical path**: Q-001 → Q-002 → Q-003 → Q-004 → Q-005 → Q-006 (Q-007 independiente)

---

## DEPENDENCY DAG

```
Q-001 (Interface)
  └── Q-002 (Supabase Adapter)
        └── Q-004 (Factory + Config)
  └── Q-003 (PostgreSQL Adapter)
        └── Q-004
              └── Q-005 (Standalone Migration SQL)
                    └── Q-006 (Docker Compose profile)
Q-007 (Docs/Env) ── independiente, puede ir al final
```

---

## QUANT-001: DatabaseClient Protocol + Query Builder Interface
**~3h AI | ~0.5h Human**

### Description
Crear el módulo `python/src/server/db/` con:
- `protocol.py`: `DatabaseClient`, `TableQuery`, `RpcQuery` como `typing.Protocol`
- La interface debe cubrir la cadena fluida: `.table(x).select().eq().execute()`
- `__init__.py` exporta el protocolo

### Acceptance
- [ ] `Protocol` definido con type hints completos
- [ ] Cubre: `select`, `insert`, `update`, `delete`, `eq`, `neq`, `in_`, `order`, `limit`, `execute`, `rpc`
- [ ] Mypy válida sin errores
- [ ] No importa `supabase` ni `psycopg2`

### Files
```
python/src/server/db/__init__.py   (nuevo)
python/src/server/db/protocol.py   (nuevo)
```

### Dependencies: ninguna

---

## QUANT-002: SupabaseDatabaseClient Adapter
**~2h AI | ~0.5h Human**

### Description
Adapter que wraps `supabase-py` `Client` e implementa `DatabaseClient` Protocol.
- Delega todas las llamadas al cliente nativo de Supabase
- Zero behavioral change respecto al código actual

### Acceptance
- [ ] Implementa `DatabaseClient` Protocol (mypy satisfecho)
- [ ] Tests: igual comportamiento que llamada directa a supabase-py
- [ ] `get_supabase_client()` retorna este adapter (retypado)

### Files
```
python/src/server/db/supabase_adapter.py   (nuevo)
python/src/server/services/client_manager.py  (modificar: retornar SupabaseDatabaseClient)
```

### Dependencies: QUANT-001

---

## QUANT-003: PostgresDatabaseClient Adapter
**~5h AI | ~1h Human**

### Description
Adapter que implementa `DatabaseClient` usando `psycopg2` + `pgvector`.
- Query builder interno mínimo que construye SQL desde la cadena fluida
- Soporta todas las operaciones usadas en el codebase (ver domain_analysis.md)
- Soporta `.rpc()` para las funciones `match_documents`, `search_code_examples`

### Acceptance
- [ ] Implementa `DatabaseClient` Protocol
- [ ] `table().select("*").execute()` → `SELECT * FROM table`
- [ ] `table().insert({}).execute()` → `INSERT INTO table VALUES (...)`
- [ ] `table().update({}).eq("id", x).execute()` → `UPDATE ... WHERE id = x`
- [ ] `table().delete().eq("id", x).execute()` → `DELETE FROM ... WHERE id = x`
- [ ] `.rpc("match_documents", params).execute()` → `SELECT * FROM match_documents(...)`
- [ ] Maneja `pgvector` con cast `::halfvec(N)`
- [ ] Tests de integración contra PostgreSQL real (via pytest fixture)
- [ ] Errores reportados como excepciones con contexto (no retorna None)

### Files
```
python/src/server/db/postgres_adapter.py   (nuevo)
python/tests/test_postgres_adapter.py      (nuevo)
```

### Dependencies: QUANT-001

---

## QUANT-004: DatabaseClient Factory + ENV Configuration
**~2h AI | ~0.5h Human**

### Description
Factory function `get_db_client()` que retorna el adapter correcto basado en `DB_PROVIDER`:
- `DB_PROVIDER=supabase` (default): retorna `SupabaseDatabaseClient` usando `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`
- `DB_PROVIDER=postgres`: retorna `PostgresDatabaseClient` usando `POSTGRES_DSN`
- Reemplaza `get_supabase_client()` en todos los consumer services
- Fail-fast en misconfiguration

### Acceptance
- [ ] `DB_PROVIDER` no definido → usa `supabase` (backward compat, I-3)
- [ ] `DB_PROVIDER=postgres` sin `POSTGRES_DSN` → `ValueError` con mensaje claro
- [ ] Todos los servicios migrados de `get_supabase_client()` a `get_db_client()`
- [ ] `from supabase import ...` eliminados de todos los servicios (solo en `supabase_adapter.py`)
- [ ] Mypy + Ruff sin errores

### Files
```
python/src/server/db/factory.py              (nuevo)
python/src/server/services/client_manager.py (modificar/deprecar get_supabase_client)
python/src/server/services/*.py              (modificar imports)
python/src/server/utils/__init__.py          (actualizar exports)
python/.env.example                          (agregar DB_PROVIDER, POSTGRES_DSN)
```

### Dependencies: QUANT-002, QUANT-003

---

## QUANT-005: Standalone PostgreSQL Migration SQL
**~2h AI | ~0.5h Human**

### Description
SQL de inicialización para PostgreSQL standalone con pgvector:
- `migration/postgres_standalone/001_init.sql`: crea extension vector, schema completo
- `migration/postgres_standalone/002_functions.sql`: RPC functions (`match_documents`, etc.)
- `migration/postgres_standalone/003_indexes.sql`: HNSW indexes con halfvec_cosine_ops
- Basado en `migration/complete_setup.sql` adaptado para standalone (sin `auth.uid()`, etc.)

### Acceptance
- [ ] `psql -f 001_init.sql` ejecuta sin error contra PostgreSQL 16 + pgvector
- [ ] `match_documents` function disponible y funcional
- [ ] HNSW index creado con `m=16, ef_construction=64`
- [ ] Compatible con `migration/0.1.0/` versioned migrations (idempotentes via IF NOT EXISTS)
- [ ] README en `migration/postgres_standalone/README.md`

### Files
```
migration/postgres_standalone/001_init.sql       (nuevo)
migration/postgres_standalone/002_functions.sql  (nuevo)
migration/postgres_standalone/003_indexes.sql    (nuevo)
migration/postgres_standalone/README.md          (nuevo)
```

### Dependencies: QUANT-003 (para saber qué funciones RPC necesita el adapter)

---

## QUANT-006: Docker Compose Profile `postgres-standalone`
**~2h AI | ~0.5h Human**

### Description
Nuevo profile en `docker-compose.yml`:
- Servicio `archon-postgres`: PostgreSQL 16 con pgvector extension
- Init: monta `./migration/postgres_standalone/` en `/docker-entrypoint-initdb.d/`
- `POSTGRES_DSN` auto-configurado para apuntar al contenedor
- Profile `backend` sigue funcionando sin cambios
- `make dev-postgres` en Makefile para workflow híbrido

### Acceptance
- [ ] `docker compose --profile postgres-standalone up -d` levanta y pasa health check
- [ ] `make dev-postgres` arranca backend + postgres standalone + UI
- [ ] `DB_PROVIDER=postgres` + `POSTGRES_DSN=postgresql://...` funcional end-to-end
- [ ] No rompe `docker compose --profile backend up -d` existente
- [ ] `docker-compose.yml` válido (`docker compose config` sin errores)
- [ ] `Makefile` con targets: `dev-postgres`, `dev-postgres-docker`

### Files
```
docker-compose.yml   (modificar: agregar profile postgres-standalone)
Makefile             (agregar targets dev-postgres)
```

### Dependencies: QUANT-005

---

## QUANT-007: Documentación + Env Update
**~2h AI | ~0.5h Human**

### Description
Actualizar documentación para reflejar la nueva configuración:
- `python/.env.example`: sección `## Database Backend` con ambas opciones
- `PRPs/ai_docs/ARCHITECTURE.md`: actualizar stack section con DB abstraction
- `README.md` o wiki: sección "Self-hosted PostgreSQL" setup guide
- `.sia/knowledge/active/README.md`: actualizar "Key Architectural Decisions"

### Acceptance
- [ ] `.env.example` tiene todos los env vars documentados y comentados
- [ ] `PRPs/ai_docs/ARCHITECTURE.md` refleja el Adapter pattern
- [ ] README tiene instrucciones para `DB_PROVIDER=postgres` quickstart

### Files
```
python/.env.example                    (modificar)
PRPs/ai_docs/ARCHITECTURE.md           (modificar)
.sia/knowledge/active/README.md        (modificar)
```

### Dependencies: ninguna (puede ejecutarse en cualquier momento)

---

## ESTIMATES SUMMARY

| QUANT | Title | AI est. | Human est. | Depends on |
|-------|-------|---------|------------|------------|
| Q-001 | Interface Protocol | 2h | 0.5h | — |
| Q-002 | Supabase Adapter | 2h | 0.5h | Q-001 |
| Q-003 | PostgreSQL Adapter | 5h | 1h | Q-001 |
| Q-004 | Factory + Config | 2h | 0.5h | Q-002, Q-003 |
| Q-005 | Standalone SQL | 2h | 0.5h | Q-003 |
| Q-006 | Docker Compose | 2h | 0.5h | Q-005 |
| Q-007 | Docs + Env | 1h | 0.5h | — |
| **TOTAL** | | **16h** | **4h** | |
