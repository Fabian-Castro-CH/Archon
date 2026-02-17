"""
Database Client Factory

Returns the correct DatabaseClient implementation based on DB_PROVIDER env var.

DB_PROVIDER=supabase (default): requires SUPABASE_URL + SUPABASE_SERVICE_KEY
DB_PROVIDER=postgres:           requires POSTGRES_DSN
"""

from __future__ import annotations

import logging
import os

from .protocol import DatabaseClient

logger = logging.getLogger(__name__)

# Module-level singleton — created once at startup
_client: DatabaseClient | None = None


def get_db_client() -> DatabaseClient:
    """
    Returns the active DatabaseClient singleton.

    Reads DB_PROVIDER on first call and initialises the matching adapter.
    Subsequent calls return the cached instance.

    Raises:
        ValueError: on missing or invalid configuration (fail-fast on startup).
    """
    global _client
    if _client is not None:
        return _client

    provider = os.getenv("DB_PROVIDER", "supabase").lower().strip()

    if provider == "supabase":
        _client = _build_supabase_client()
    elif provider == "postgres":
        _client = _build_postgres_client()
    else:
        raise ValueError(
            f"DB_PROVIDER='{provider}' is not supported. "
            "Valid values: 'supabase' (default), 'postgres'."
        )

    logger.info("DatabaseClient initialised (provider=%s)", provider)
    return _client


def _build_supabase_client() -> DatabaseClient:
    """Build SupabaseDatabaseClient from environment variables."""
    import re

    from supabase import create_client

    from .supabase_adapter import SupabaseDatabaseClient

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "DB_PROVIDER=supabase requires SUPABASE_URL and SUPABASE_SERVICE_KEY "
            "to be set in environment variables."
        )

    native = create_client(url, key)
    match = re.match(r"https://([^.]+)\.supabase\.co", url)
    if match:
        logger.debug("Supabase client initialised (project=%s)", match.group(1))
    else:
        logger.debug("Supabase client initialised (self-hosted)")

    return SupabaseDatabaseClient(native)


def _build_postgres_client() -> DatabaseClient:
    """Build PostgresDatabaseClient from POSTGRES_DSN environment variable."""
    from .postgres_adapter import PostgresDatabaseClient

    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        raise ValueError(
            "DB_PROVIDER=postgres requires POSTGRES_DSN to be set. "
            "Example: postgresql://user:password@localhost:5432/archon"
        )

    min_conn = int(os.getenv("POSTGRES_POOL_MIN", "1"))
    max_conn = int(os.getenv("POSTGRES_POOL_MAX", "10"))

    return PostgresDatabaseClient(dsn, min_conn=min_conn, max_conn=max_conn)


def reset_db_client() -> None:
    """
    Reset the cached client (used in tests to re-initialise with different env).
    Not intended for production use.
    """
    global _client
    _client = None
