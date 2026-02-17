"""
Database Client Protocol

Defines the structural interface that all database adapters must implement.
Uses Python Protocols for structural subtyping (duck typing) — adapters
do not need to inherit from these classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class APIResponse:
    """
    Response wrapper matching supabase-py APIResponse structure.
    Both adapters return this to guarantee uniform access patterns.
    """

    data: list[dict[str, Any]] | dict[str, Any] | None = None
    count: int | None = None


@runtime_checkable
class TableQueryBuilder(Protocol):
    """Fluent query builder for table operations (mirrors supabase-py QueryRequestBuilder)."""

    # Column selection
    def select(self, columns: str = "*") -> "TableQueryBuilder": ...

    # Mutation
    def insert(self, data: dict[str, Any] | list[dict[str, Any]]) -> "TableQueryBuilder": ...
    def update(self, data: dict[str, Any]) -> "TableQueryBuilder": ...
    def delete(self) -> "TableQueryBuilder": ...
    def upsert(
        self, data: dict[str, Any] | list[dict[str, Any]], on_conflict: str = ""
    ) -> "TableQueryBuilder": ...

    # Filters
    def eq(self, column: str, value: Any) -> "TableQueryBuilder": ...
    def neq(self, column: str, value: Any) -> "TableQueryBuilder": ...
    def in_(self, column: str, values: list[Any]) -> "TableQueryBuilder": ...
    def gte(self, column: str, value: Any) -> "TableQueryBuilder": ...
    def lte(self, column: str, value: Any) -> "TableQueryBuilder": ...
    def ilike(self, column: str, pattern: str) -> "TableQueryBuilder": ...

    # Ordering / pagination
    def order(self, column: str, *, desc: bool = False) -> "TableQueryBuilder": ...
    def limit(self, count: int) -> "TableQueryBuilder": ...

    # Execution
    def execute(self) -> APIResponse: ...


@runtime_checkable
class RpcQueryBuilder(Protocol):
    """Query builder for stored procedure / RPC calls."""

    def execute(self) -> APIResponse: ...


@runtime_checkable
class DatabaseClient(Protocol):
    """
    Unified database client interface.

    Implemented by SupabaseDatabaseClient (wraps supabase-py) and
    PostgresDatabaseClient (direct psycopg2 connection).
    """

    def table(self, name: str) -> TableQueryBuilder: ...
    def rpc(self, name: str, params: dict[str, Any]) -> RpcQueryBuilder: ...
