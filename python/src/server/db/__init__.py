"""
Database abstraction layer.

Provides a unified interface for Supabase and standalone PostgreSQL backends.
Controlled by DB_PROVIDER environment variable (default: supabase).
"""

from .factory import get_db_client
from .protocol import APIResponse, DatabaseClient

__all__ = ["get_db_client", "DatabaseClient", "APIResponse"]
