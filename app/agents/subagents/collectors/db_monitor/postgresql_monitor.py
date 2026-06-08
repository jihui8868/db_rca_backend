from typing import Any

from sqlalchemy import create_engine, text

from app.agents.subagents.collectors.db_monitor.base import (
    BaseDBMonitor,
    ConnectionMetrics,
    LockMetrics,
    QPSTpsMetrics,
    ReplicationMetrics,
    SlowQueryMetrics,
)


class PostgreSQLMonitor(BaseDBMonitor):
    """PostgreSQL monitoring metrics collector."""

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self._engine = create_engine(connection_string, pool_pre_ping=True)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _scalar(self, sql: str, params: dict | None = None) -> Any:
        with self._engine.connect() as conn:
            return conn.execute(text(sql), params or {}).scalar()

    def _one(self, sql: str, params: dict | None = None) -> dict:
        with self._engine.connect() as conn:
            row = conn.execute(text(sql), params or {}).mappings().first()
            return dict(row) if row else {}

    def _all(self, sql: str, params: dict | None = None) -> list[dict]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params or {}).mappings().all()
            return [dict(r) for r in rows]

    def _float(self, d: dict, key: str, default: float = 0.0) -> float:
        try:
            return float(d.get(key) or default)
        except (ValueError, TypeError):
            return default

    def _int(self, d: dict, key: str, default: int = 0) -> int:
        try:
            return int(d.get(key) or default)
        except (ValueError, TypeError):
            return default

    # ------------------------------------------------------------------ #
    #  BaseDBMonitor interface
    # ------------------------------------------------------------------ #

    def get_version(self) -> str:
        return self._scalar("SELECT version()") or ""

    def get_qps_tps(self) -> QPSTpsMetrics:
        row = self._one(
            "SELECT xact_commit, xact_rollback, "
            "xact_commit + xact_rollback AS total_xact, "
            "blks_hit, blks_read, "
            "tup_returned, tup_fetched, tup_inserted, tup_updated, tup_deleted "
            "FROM pg_stat_database WHERE datname = current_database()"
        )
        # pg_stat_database values are cumulative; use as-is for trend context
        xact_commit = self._float(row, "xact_commit")
        xact_rollback = self._float(row, "xact_rollback")
        total_xact = self._float(row, "total_xact")

        # Approximate QPS from tup_returned (rows fetched proxy)
        tup_returned = self._float(row, "tup_returned")
        blks_hit = self._float(row, "blks_hit")
        blks_read = self._float(row, "blks_read")
        cache_hit = (
            round(blks_hit / (blks_hit + blks_read) * 100, 2)
            if (blks_hit + blks_read) > 0
            else 0.0
        )

        return QPSTpsMetrics(
            qps=round(self._float(row, "tup_fetched"), 0),  # cumulative fetches as proxy
            tps=round(total_xact, 0),
            commit_ps=round(xact_commit, 0),
            rollback_ps=round(xact_rollback, 0),
            insert_ps=round(self._float(row, "tup_inserted"), 0),
            update_ps=round(self._float(row, "tup_updated"), 0),
            delete_ps=round(self._float(row, "tup_deleted"), 0),
            select_ps=round(tup_returned, 0),
        )

    def get_connections(self) -> ConnectionMetrics:
        row = self._one(
            "SELECT "
            "  count(*)                                                    AS total, "
            "  count(*) FILTER (WHERE state = 'active')                    AS active, "
            "  count(*) FILTER (WHERE state = 'idle')                      AS idle, "
            "  count(*) FILTER (WHERE state LIKE 'idle in transaction%')   AS idle_in_txn, "
            "  count(*) FILTER (WHERE wait_event_type = 'Lock')            AS waiting_for_lock "
            "FROM pg_stat_activity WHERE datname IS NOT NULL"
        )
        max_conn = int(self._scalar("SHOW max_connections") or 100)
        total = self._int(row, "total")
        return ConnectionMetrics(
            total=total,
            active=self._int(row, "active"),
            idle=self._int(row, "idle"),
            idle_in_transaction=self._int(row, "idle_in_txn"),
            waiting_for_lock=self._int(row, "waiting_for_lock"),
            max_connections=max_conn,
            usage_pct=round(total / max_conn * 100, 2) if max_conn else 0.0,
        )

    def get_locks(self) -> LockMetrics:
        metrics = LockMetrics()

        # Deadlocks from pg_stat_database
        row = self._one("SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()")
        metrics.deadlocks = self._int(row, "deadlocks")

        # Blocked queries
        metrics.blocked_queries = int(
            self._scalar(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE cardinality(pg_blocking_pids(pid)) > 0"
            ) or 0
        )

        # Lock waits (requests not yet granted)
        metrics.lock_waits = int(
            self._scalar("SELECT count(*) FROM pg_locks WHERE NOT granted") or 0
        )

        # Longest wait
        details = self._all(
            "SELECT blocked.pid AS blocked_pid, "
            "  blocked.usename AS blocked_user, "
            "  LEFT(blocked.query, 200) AS blocked_query, "
            "  blocking.pid AS blocking_pid, "
            "  EXTRACT(EPOCH FROM (now() - blocked.query_start))::int AS wait_seconds "
            "FROM pg_stat_activity blocked "
            "JOIN pg_stat_activity blocking "
            "  ON blocking.pid = ANY(pg_blocking_pids(blocked.pid)) "
            "ORDER BY wait_seconds DESC LIMIT 5"
        )
        if details:
            metrics.longest_wait_seconds = float(details[0].get("wait_seconds") or 0)
            metrics.details = details

        return metrics

    def get_replication(self) -> ReplicationMetrics:
        # Check if this is a replica
        in_recovery = self._scalar("SELECT pg_is_in_recovery()")
        if not in_recovery:
            return ReplicationMetrics(is_replica=False)

        row = self._one(
            "SELECT "
            "  EXTRACT(EPOCH FROM replay_lag)::float AS replay_lag_seconds, "
            "  EXTRACT(EPOCH FROM write_lag)::float  AS write_lag_seconds, "
            "  state, sync_state, sent_lsn, write_lsn, flush_lsn, replay_lsn "
            "FROM pg_stat_replication LIMIT 1"
        )
        return ReplicationMetrics(
            is_replica=True,
            delay_seconds=float(row.get("replay_lag_seconds") or 0),
            io_running=True,  # pg_is_in_recovery() = True implies WAL receiver is active
            sql_running=True,
            details={k: str(v) for k, v in row.items()},
        )

    def get_slow_queries(self) -> SlowQueryMetrics:
        metrics = SlowQueryMetrics()
        try:
            rows = self._all(
                "SELECT query, calls, "
                "  ROUND(total_exec_time::numeric / 1000, 3) AS total_sec, "
                "  ROUND(mean_exec_time::numeric / 1000, 3)  AS avg_sec, "
                "  ROUND(max_exec_time::numeric / 1000, 3)   AS max_sec, "
                "  rows, shared_blks_hit, shared_blks_read "
                "FROM pg_stat_statements "
                "WHERE mean_exec_time / 1000 >= 1 "
                "ORDER BY mean_exec_time DESC LIMIT 10"
            )
            metrics.total_slow_queries = len(rows)
            metrics.top_queries = rows
        except Exception:
            pass
        return metrics

    def get_extra_metrics(self) -> dict[str, Any]:
        """Collect PostgreSQL-specific metrics: checkpoint, WAL, vacuum."""
        extra: dict[str, Any] = {}

        # Checkpoint stats
        bgwriter = self._one(
            "SELECT checkpoints_timed, checkpoints_req, "
            "  ROUND(checkpoint_write_time / 1000, 2) AS write_time_sec, "
            "  ROUND(checkpoint_sync_time  / 1000, 2) AS sync_time_sec, "
            "  buffers_checkpoint, buffers_clean, buffers_backend, buffers_backend_fsync "
            "FROM pg_stat_bgwriter"
        )
        extra["checkpoint"] = {
            "checkpoints_timed": self._int(bgwriter, "checkpoints_timed"),
            "checkpoints_req": self._int(bgwriter, "checkpoints_req"),
            "write_time_sec": self._float(bgwriter, "write_time_sec"),
            "sync_time_sec": self._float(bgwriter, "sync_time_sec"),
            "buffers_checkpoint": self._int(bgwriter, "buffers_checkpoint"),
            "buffers_backend": self._int(bgwriter, "buffers_backend"),
            "buffers_backend_fsync": self._int(bgwriter, "buffers_backend_fsync"),
        }

        # WAL stats (PostgreSQL 14+)
        try:
            wal = self._one(
                "SELECT wal_records, wal_fpi, wal_bytes, "
                "  wal_buffers_full, wal_write, wal_sync, "
                "  ROUND(wal_write_time, 2) AS write_time_ms, "
                "  ROUND(wal_sync_time,  2) AS sync_time_ms "
                "FROM pg_stat_wal"
            )
            extra["wal"] = {
                "wal_records": self._int(wal, "wal_records"),
                "wal_bytes": self._int(wal, "wal_bytes"),
                "wal_buffers_full": self._int(wal, "wal_buffers_full"),
                "wal_write": self._int(wal, "wal_write"),
                "wal_sync": self._int(wal, "wal_sync"),
                "write_time_ms": self._float(wal, "write_time_ms"),
                "sync_time_ms": self._float(wal, "sync_time_ms"),
            }
        except Exception:
            extra["wal"] = {"note": "pg_stat_wal not available (requires PostgreSQL 14+)"}

        # Vacuum stats — top tables by dead tuples
        vacuum_rows = self._all(
            "SELECT schemaname, relname, n_live_tup, n_dead_tup, "
            "  ROUND(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 2) AS dead_ratio, "
            "  last_vacuum, last_autovacuum, vacuum_count, autovacuum_count "
            "FROM pg_stat_user_tables "
            "WHERE n_dead_tup > 0 "
            "ORDER BY n_dead_tup DESC LIMIT 10"
        )
        # Running vacuums
        running_vacuums = self._all(
            "SELECT pid, relid::regclass AS table_name, phase, "
            "  heap_blks_scanned, heap_blks_vacuumed, heap_blks_total "
            "FROM pg_stat_progress_vacuum"
        )
        extra["vacuum"] = {
            "tables_needing_vacuum": vacuum_rows,
            "running_vacuums": running_vacuums,
        }

        # Lock summary by mode
        lock_summary = self._all(
            "SELECT locktype, mode, granted, count(*) AS count "
            "FROM pg_locks GROUP BY locktype, mode, granted ORDER BY count DESC LIMIT 20"
        )
        extra["lock_summary"] = lock_summary

        return extra
