"""
Client Manager Service

Manages database client connections.
Backing implementation is controlled by DB_PROVIDER env var (default: supabase).
"""

from ..db.factory import get_db_client, reset_db_client
from ..db.protocol import DatabaseClient


def get_supabase_client() -> DatabaseClient:
    """
    Backward-compatible alias for get_db_client().
    Returns the active DatabaseClient as configured by DB_PROVIDER.
    """
    return get_db_client()


__all__ = ["get_supabase_client", "get_db_client", "reset_db_client", "DatabaseClient"]
