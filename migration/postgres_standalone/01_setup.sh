#!/bin/bash
# ===========================================================================
# Archon Standalone PostgreSQL Setup
#
# Runs complete_setup.sql with Supabase-specific RLS statements stripped.
# auth.role() is Supabase-only; in standalone mode the connecting user
# is the sole owner and needs no row-level security.
#
# Docker: mounted at /docker-entrypoint-initdb.d/01_setup.sh
# Manual: bash migration/postgres_standalone/01_setup.sh
# ===========================================================================
set -e

DB="${POSTGRES_DB:-archon}"
USER="${POSTGRES_USER:-archon}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPLETE_SETUP="$SCRIPT_DIR/../complete_setup.sql"

# Resolve path for Docker context (files are copied into container differently)
if [ ! -f "$COMPLETE_SETUP" ]; then
    COMPLETE_SETUP="/migration/complete_setup.sql"
fi
if [ ! -f "$COMPLETE_SETUP" ]; then
    echo "ERROR: complete_setup.sql not found at $COMPLETE_SETUP"
    exit 1
fi

echo "[Archon] Generating standalone schema from complete_setup.sql..."

# Strip Supabase-specific RLS statements:
#   - ALTER TABLE ... ENABLE ROW LEVEL SECURITY
#   - CREATE POLICY ...
#   - Lines containing auth.role() or auth.uid()
# All other DDL (tables, indexes, functions, extensions) is preserved.
FILTERED_SQL=$(grep -v \
    -e "ENABLE ROW LEVEL SECURITY" \
    -e "^CREATE POLICY" \
    -e "auth\.role()" \
    -e "auth\.uid()" \
    "$COMPLETE_SETUP")

echo "[Archon] Applying schema to database: $DB..."
echo "$FILTERED_SQL" | psql -v ON_ERROR_STOP=1 --username "$USER" --dbname "$DB"

echo "[Archon] Granting permissions to $USER..."
psql -v ON_ERROR_STOP=1 --username "$USER" --dbname "$DB" <<-EOSQL
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "$USER";
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "$USER";
    GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO "$USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT ALL ON TABLES TO "$USER";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT ALL ON SEQUENCES TO "$USER";
EOSQL

echo "[Archon] Standalone PostgreSQL setup complete."
