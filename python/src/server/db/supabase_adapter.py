"""
Supabase Database Client Adapter

Wraps the supabase-py Client and exposes the DatabaseClient interface.
Zero behavioral change — all calls are forwarded to the native supabase-py client.
Active when DB_PROVIDER=supabase (default).
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from .protocol import APIResponse


class _SupabaseTableQueryBuilder:
    """
    Forwards all query builder calls to the supabase-py QueryRequestBuilder,
    converting the supabase APIResponse to our internal APIResponse.
    """

    def __init__(self, native_builder: Any) -> None:
        self._b = native_builder

    # --- Column selection ---

    def select(self, columns: str = "*") -> "_SupabaseTableQueryBuilder":
        self._b = self._b.select(columns)
        return self

    # --- Mutations ---

    def insert(
        self, data: dict[str, Any] | list[dict[str, Any]]
    ) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.insert(data)
        return self

    def update(self, data: dict[str, Any]) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.update(data)
        return self

    def delete(self) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.delete()
        return self

    def upsert(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        on_conflict: str = "",
    ) -> "_SupabaseTableQueryBuilder":
        if on_conflict:
            self._b = self._b.upsert(data, on_conflict=on_conflict)
        else:
            self._b = self._b.upsert(data)
        return self

    # --- Filters ---

    def eq(self, column: str, value: Any) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.eq(column, value)
        return self

    def neq(self, column: str, value: Any) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.neq(column, value)
        return self

    def in_(self, column: str, values: list[Any]) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.in_(column, values)
        return self

    def gte(self, column: str, value: Any) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.gte(column, value)
        return self

    def lte(self, column: str, value: Any) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.lte(column, value)
        return self

    def ilike(self, column: str, pattern: str) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.ilike(column, pattern)
        return self

    # --- Ordering / pagination ---

    def order(self, column: str, *, desc: bool = False) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.order(column, desc=desc)
        return self

    def limit(self, count: int) -> "_SupabaseTableQueryBuilder":
        self._b = self._b.limit(count)
        return self

    # --- Execution ---

    def execute(self) -> APIResponse:
        native_response = self._b.execute()
        return APIResponse(data=native_response.data, count=getattr(native_response, "count", None))


class _SupabaseRpcQueryBuilder:
    """Wraps a supabase-py RPC call and exposes execute()."""

    def __init__(self, native_builder: Any) -> None:
        self._b = native_builder

    def execute(self) -> APIResponse:
        native_response = self._b.execute()
        return APIResponse(data=native_response.data, count=getattr(native_response, "count", None))


class SupabaseDatabaseClient:
    """
    Supabase-backed implementation of DatabaseClient.
    Wraps a supabase-py Client instance and delegates all operations.
    """

    def __init__(self, native_client: Client) -> None:
        self._client = native_client

    def table(self, name: str) -> _SupabaseTableQueryBuilder:
        return _SupabaseTableQueryBuilder(self._client.table(name))

    def rpc(self, name: str, params: dict[str, Any]) -> _SupabaseRpcQueryBuilder:
        return _SupabaseRpcQueryBuilder(self._client.rpc(name, params))
