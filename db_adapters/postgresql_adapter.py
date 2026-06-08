from sqlalchemy import create_engine, text

from db_adapters.base import BaseDBAdapter


class PostgreSQLAdapter(BaseDBAdapter):
    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self._engine = create_engine(connection_string)

    def test_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_db_version(self) -> str:
        with self._engine.connect() as conn:
            return conn.execute(text("SELECT version()")).scalar()

    def get_active_connections(self) -> list[dict]:
        query = text(
            "SELECT pid, usename, application_name, client_addr, state, "
            "wait_event_type, wait_event, "
            "EXTRACT(EPOCH FROM (now() - query_start))::int AS query_seconds, "
            "left(query, 200) AS query "
            "FROM pg_stat_activity "
            "WHERE state != 'idle' AND pid != pg_backend_pid() "
            "ORDER BY query_start ASC NULLS LAST LIMIT 50"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]

    def get_slow_queries(self, threshold_seconds: float = 1.0) -> list[dict]:
        query = text(
            "SELECT query, calls, total_exec_time/1000 AS total_seconds, "
            "mean_exec_time/1000 AS mean_seconds, rows, "
            "shared_blks_hit, shared_blks_read "
            "FROM pg_stat_statements "
            "WHERE mean_exec_time/1000 >= :threshold "
            "ORDER BY mean_exec_time DESC LIMIT 20"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"threshold": threshold_seconds}).mappings().all()
        return [dict(row) for row in rows]

    def get_error_logs(self, limit: int = 100) -> list[dict]:
        # PostgreSQL does not expose error logs via SQL by default.
        # Return pg_stat_activity entries in error states as a proxy.
        query = text(
            "SELECT pid, usename, state, wait_event_type, wait_event, "
            "left(query, 300) AS query, query_start "
            "FROM pg_stat_activity "
            "WHERE state = 'active' AND wait_event_type = 'Lock' "
            "ORDER BY query_start ASC LIMIT :limit"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_table_stats(self, schema: str | None = None) -> list[dict]:
        where = "WHERE schemaname NOT IN ('pg_catalog','information_schema')"
        params: dict = {}
        if schema:
            where += " AND schemaname = :schema"
            params["schema"] = schema
        query = text(
            f"SELECT schemaname, relname AS table_name, n_live_tup AS row_count, "
            f"pg_size_pretty(pg_total_relation_size(relid)) AS total_size, "
            f"n_dead_tup AS dead_tuples, last_vacuum, last_autovacuum, "
            f"last_analyze, last_autoanalyze "
            f"FROM pg_stat_user_tables {where} "
            f"ORDER BY n_live_tup DESC LIMIT 30"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_index_stats(self, schema: str | None = None) -> list[dict]:
        where = "WHERE schemaname NOT IN ('pg_catalog','information_schema')"
        params: dict = {}
        if schema:
            where += " AND schemaname = :schema"
            params["schema"] = schema
        query = text(
            f"SELECT schemaname, relname AS table_name, indexrelname AS index_name, "
            f"idx_scan, idx_tup_read, idx_tup_fetch, "
            f"pg_size_pretty(pg_relation_size(indexrelid)) AS index_size "
            f"FROM pg_stat_user_indexes {where} "
            f"ORDER BY idx_scan ASC LIMIT 50"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_lock_info(self) -> list[dict]:
        query = text(
            "SELECT blocked.pid AS blocked_pid, blocked.usename AS blocked_user, "
            "left(blocked.query, 200) AS blocked_query, "
            "blocking.pid AS blocking_pid, blocking.usename AS blocking_user, "
            "left(blocking.query, 200) AS blocking_query, "
            "now() - blocked.query_start AS wait_duration "
            "FROM pg_stat_activity blocked "
            "JOIN pg_stat_activity blocking "
            "  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid)) "
            "WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0 "
            "LIMIT 20"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]

    def get_replication_status(self) -> list[dict]:
        query = text(
            "SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn, "
            "write_lag, flush_lag, replay_lag, sync_state "
            "FROM pg_stat_replication LIMIT 10"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]
