# Standalone PostgreSQL Migration

Scripts for running Archon against a self-hosted PostgreSQL + pgvector instance
instead of Supabase.

## How it works

`01_setup.sh` filters `complete_setup.sql` at runtime, stripping Supabase-specific
Row Level Security statements that depend on `auth.role()`. All tables, indexes,
and functions are preserved identically.

## Usage

### Docker (automatic via docker-compose profile)

```bash
docker compose --profile postgres-standalone up -d
```

The init script runs automatically on first start. Data is persisted in the
`archon_pgdata` Docker volume.

### Manual

```bash
# Start PostgreSQL with pgvector (any method)
# Then run:
bash migration/postgres_standalone/01_setup.sh
```

### Environment variables required

```bash
DB_PROVIDER=postgres
POSTGRES_DSN=postgresql://archon:archon@localhost:5433/archon
# Optional encryption seed (replaces SUPABASE_SERVICE_KEY for credential storage)
DB_ENCRYPTION_SEED=your-stable-secret-here
```

## Schema parity

The standalone schema is identical to the Supabase schema:
- Same tables, columns, constraints, indexes
- Same pgvector functions (match_archon_crawled_pages, hybrid_search_*, etc.)
- Same versioned migrations under migration/0.1.0/ apply to both backends

## Versioned migrations

Apply versioned migrations manually after initial setup:

```bash
for f in migration/0.1.0/*.sql; do
    psql "$POSTGRES_DSN" -f "$f"
done
```
