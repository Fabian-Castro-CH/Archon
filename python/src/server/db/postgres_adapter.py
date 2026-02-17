"""
PostgreSQL Database Client Adapter

Direct psycopg2-based implementation of DatabaseClient.
Implements the same fluent query builder API as supabase-py so all existing
service code works without modification.

Active when DB_PROVIDER=postgres + POSTGRES_DSN is set.
"""

from __future__ import annotations

import json
import logging
from enum import Enum, auto
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _Op(Enum):
    SELECT = auto()
    INSERT = auto()
    UPDATE = auto()
    DELETE = auto()
    UPSERT = auto()


class _Filter:
    __slots__ = ("kind", "column", "value")

    def __init__(self, kind: str, column: str, value: Any) -> None:
        self.kind = kind  # "eq" | "neq" | "in" | "gte" | "lte" | "ilike"
        self.column = column
        self.value = value


def _adapt_value(v: Any) -> Any:
    """Convert Python objects to psycopg2-compatible types."""
    if isinstance(v, dict) or isinstance(v, list):
        return psycopg2.extras.Json(v)
    return v


def _build_where(filters: list[_Filter]) -> tuple[str, list[Any]]:
    """Build WHERE clause and parameters list from filters."""
    if not filters:
        return "", []
    clauses: list[str] = []
    params: list[Any] = []
    for f in filters:
        col = psycopg2.extensions.quote_ident(f.column, None)  # type: ignore[arg-type]
        if f.kind == "eq":
            clauses.append(f"{col} = %s")
            params.append(_adapt_value(f.value))
        elif f.kind == "neq":
            clauses.append(f"{col} != %s")
            params.append(_adapt_value(f.value))
        elif f.kind == "in":
            placeholders = ",".join(["%s"] * len(f.value))
            clauses.append(f"{col} = ANY(ARRAY[{placeholders}])")
            params.extend(_adapt_value(item) for item in f.value)
        elif f.kind == "gte":
            clauses.append(f"{col} >= %s")
            params.append(_adapt_value(f.value))
        elif f.kind == "lte":
            clauses.append(f"{col} <= %s")
            params.append(_adapt_value(f.value))
        elif f.kind == "ilike":
            clauses.append(f"{col} ILIKE %s")
            params.append(f.value)
    return "WHERE " + " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# Table Query Builder
# ---------------------------------------------------------------------------


class PostgresTableQueryBuilder:
    """
    Fluent query builder that mirrors supabase-py's QueryRequestBuilder interface.
    Builds and executes a single SQL statement per execute() call.
    """

    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool, table: str) -> None:
        self._pool = pool
        self._table = table
        self._op: _Op | None = None
        self._columns: str = "*"
        self._data: dict[str, Any] | list[dict[str, Any]] | None = None
        self._on_conflict: str = ""
        self._filters: list[_Filter] = []
        self._orders: list[tuple[str, bool]] = []  # (column, desc)
        self._limit_val: int | None = None

    # --- Column selection ---

    def select(self, columns: str = "*") -> "PostgresTableQueryBuilder":
        self._op = _Op.SELECT
        self._columns = columns
        return self

    # --- Mutations ---

    def insert(
        self, data: dict[str, Any] | list[dict[str, Any]]
    ) -> "PostgresTableQueryBuilder":
        self._op = _Op.INSERT
        self._data = data
        return self

    def update(self, data: dict[str, Any]) -> "PostgresTableQueryBuilder":
        self._op = _Op.UPDATE
        self._data = data
        return self

    def delete(self) -> "PostgresTableQueryBuilder":
        self._op = _Op.DELETE
        return self

    def upsert(
        self,
        data: dict[str, Any] | list[dict[str, Any]],
        on_conflict: str = "",
    ) -> "PostgresTableQueryBuilder":
        self._op = _Op.UPSERT
        self._data = data
        self._on_conflict = on_conflict
        return self

    # --- Filters ---

    def eq(self, column: str, value: Any) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("eq", column, value))
        return self

    def neq(self, column: str, value: Any) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("neq", column, value))
        return self

    def in_(self, column: str, values: list[Any]) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("in", column, values))
        return self

    def gte(self, column: str, value: Any) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("gte", column, value))
        return self

    def lte(self, column: str, value: Any) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("lte", column, value))
        return self

    def ilike(self, column: str, pattern: str) -> "PostgresTableQueryBuilder":
        self._filters.append(_Filter("ilike", column, pattern))
        return self

    # --- Ordering / pagination ---

    def order(self, column: str, *, desc: bool = False) -> "PostgresTableQueryBuilder":
        self._orders.append((column, desc))
        return self

    def limit(self, count: int) -> "PostgresTableQueryBuilder":
        self._limit_val = count
        return self

    # --- Execution ---

    def execute(self) -> "APIResponse":  # noqa: F821
        from .protocol import APIResponse

        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                sql, params = self._build_sql()
                logger.debug("PostgreSQL execute: %s | params=%s", sql, params)
                cur.execute(sql, params)
                conn.commit()
                rows = cur.fetchall() if cur.description else []
                data = [dict(r) for r in rows]
                return APIResponse(data=data)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # --- Internal SQL builder ---

    def _build_sql(self) -> tuple[str, list[Any]]:
        tbl = self._table  # already sanitized by caller via psycopg2 quoting
        where_clause, where_params = _build_where(self._filters)

        if self._op is _Op.SELECT:
            cols = self._columns if self._columns != "*" else "*"
            sql = f"SELECT {cols} FROM {tbl}"
            params = []
            if where_clause:
                sql += " " + where_clause
                params.extend(where_params)
            if self._orders:
                order_parts = [
                    f"{col} {'DESC' if d else 'ASC'}" for col, d in self._orders
                ]
                sql += " ORDER BY " + ", ".join(order_parts)
            if self._limit_val is not None:
                sql += f" LIMIT {int(self._limit_val)}"
            return sql, params

        if self._op is _Op.INSERT:
            rows = self._data if isinstance(self._data, list) else [self._data]
            if not rows:
                return f"SELECT * FROM {tbl} WHERE FALSE", []
            cols = list(rows[0].keys())
            col_sql = ", ".join(cols)
            row_placeholders = "(" + ", ".join(["%s"] * len(cols)) + ")"
            all_placeholders = ", ".join([row_placeholders] * len(rows))
            params: list[Any] = []
            for row in rows:
                for col in cols:
                    params.append(_adapt_value(row[col]))
            sql = f"INSERT INTO {tbl} ({col_sql}) VALUES {all_placeholders} RETURNING *"
            return sql, params

        if self._op is _Op.UPDATE:
            data = self._data or {}
            set_parts = [f"{k} = %s" for k in data]
            set_params = [_adapt_value(v) for v in data.values()]
            sql = f"UPDATE {tbl} SET {', '.join(set_parts)}"
            all_params = set_params
            if where_clause:
                sql += " " + where_clause
                all_params = set_params + where_params
            sql += " RETURNING *"
            return sql, all_params

        if self._op is _Op.DELETE:
            sql = f"DELETE FROM {tbl}"
            params = []
            if where_clause:
                sql += " " + where_clause
                params = where_params
            sql += " RETURNING *"
            return sql, params

        if self._op is _Op.UPSERT:
            rows = self._data if isinstance(self._data, list) else [self._data]
            if not rows:
                return f"SELECT * FROM {tbl} WHERE FALSE", []
            cols = list(rows[0].keys())
            col_sql = ", ".join(cols)
            row_placeholders = "(" + ", ".join(["%s"] * len(cols)) + ")"
            all_placeholders = ", ".join([row_placeholders] * len(rows))
            params = []
            for row in rows:
                for col in cols:
                    params.append(_adapt_value(row[col]))
            # Determine conflict target
            conflict_target = self._on_conflict if self._on_conflict else self._infer_conflict_column()
            # Build SET clause (exclude conflict column and created_at)
            exclude_cols = {conflict_target, "created_at", "id"} if conflict_target else {"id", "created_at"}
            update_parts = [f"{k} = EXCLUDED.{k}" for k in cols if k not in exclude_cols]
            if conflict_target and update_parts:
                conflict_sql = (
                    f" ON CONFLICT ({conflict_target}) DO UPDATE SET {', '.join(update_parts)}"
                )
            elif update_parts:
                conflict_sql = " ON CONFLICT DO NOTHING"
            else:
                conflict_sql = " ON CONFLICT DO NOTHING"
            sql = f"INSERT INTO {tbl} ({col_sql}) VALUES {all_placeholders}{conflict_sql} RETURNING *"
            return sql, params

        raise ValueError(f"No operation set on query builder for table {tbl}")

    def _infer_conflict_column(self) -> str:
        """Infer the ON CONFLICT column from known table schemas."""
        known = {
            "archon_sources": "source_id",
            "archon_settings": "key",
            "archon_projects": "id",
            "archon_tasks": "id",
        }
        return known.get(self._table, "")


# ---------------------------------------------------------------------------
# RPC Query Builder
# ---------------------------------------------------------------------------


class PostgresRpcQueryBuilder:
    """
    Executes a stored PostgreSQL function (equivalent to supabase .rpc()).
    All Archon RPC functions follow the convention: return SETOF record.
    """

    def __init__(
        self, pool: psycopg2.pool.ThreadedConnectionPool, func: str, params: dict[str, Any]
    ) -> None:
        self._pool = pool
        self._func = func
        self._params = params

    def execute(self) -> "APIResponse":  # noqa: F821
        from .protocol import APIResponse

        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Build named-parameter function call
                named = ", ".join(f"{k} => %s" for k in self._params)
                sql = f"SELECT * FROM {self._func}({named})"
                # Convert list/dict params to Json for JSONB params
                param_vals = []
                for v in self._params.values():
                    if isinstance(v, (dict, list)):
                        param_vals.append(psycopg2.extras.Json(v))
                    else:
                        param_vals.append(v)
                logger.debug("PostgreSQL RPC: %s | params=%s", sql, list(self._params.keys()))
                cur.execute(sql, param_vals)
                conn.commit()
                rows = cur.fetchall() if cur.description else []
                data = [dict(r) for r in rows]
                return APIResponse(data=data)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)


# ---------------------------------------------------------------------------
# Main adapter class
# ---------------------------------------------------------------------------


class PostgresDatabaseClient:
    """
    PostgreSQL-backed implementation of DatabaseClient.
    Uses psycopg2 with a threaded connection pool.
    Requires pgvector extension installed in target database.
    """

    def __init__(self, dsn: str, min_conn: int = 1, max_conn: int = 10) -> None:
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(min_conn, max_conn, dsn=dsn)
            # Register pgvector type adapters if available
            self._register_vector_types()
            logger.info("PostgresDatabaseClient initialized (pool min=%d max=%d)", min_conn, max_conn)
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to PostgreSQL (DSN={dsn!r}): {e}"
            ) from e

    def _register_vector_types(self) -> None:
        """Register pgvector type adapters for psycopg2."""
        try:
            from pgvector.psycopg2 import register_vector

            conn = self._pool.getconn()
            try:
                register_vector(conn)
            finally:
                self._pool.putconn(conn)
            logger.debug("pgvector type adapters registered")
        except ImportError:
            logger.debug("pgvector Python package not installed; vector columns will use list representation")
        except Exception as e:
            logger.warning("Could not register pgvector adapters: %s", e)

    def table(self, name: str) -> PostgresTableQueryBuilder:
        return PostgresTableQueryBuilder(self._pool, name)

    def rpc(self, name: str, params: dict[str, Any]) -> PostgresRpcQueryBuilder:
        return PostgresRpcQueryBuilder(self._pool, name, params)

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.closeall()
        logger.info("PostgresDatabaseClient pool closed")
