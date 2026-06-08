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


class MySQLMonitor(BaseDBMonitor):
    """MySQL / MariaDB monitoring metrics collector."""

    def __init__(self, connection_string: str):
        super().__init__(connection_string)
        self._engine = create_engine(connection_string, pool_pre_ping=True)

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _global_status(self, *names: str) -> dict[str, str]:
        placeholders = ", ".join(f"'{n}'" for n in names)
        sql = f"SHOW GLOBAL STATUS WHERE Variable_name IN ({placeholders})"
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return {row[0].lower(): row[1] for row in rows}

    def _global_variables(self, *names: str) -> dict[str, str]:
        placeholders = ", ".join(f"'{n}'" for n in names)
        sql = f"SHOW GLOBAL VARIABLES WHERE Variable_name IN ({placeholders})"
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return {row[0].lower(): row[1] for row in rows}

    def _float(self, d: dict, key: str, default: float = 0.0) -> float:
        try:
            return float(d.get(key, default))
        except (ValueError, TypeError):
            return default

    def _int(self, d: dict, key: str, default: int = 0) -> int:
        try:
            return int(d.get(key, default))
        except (ValueError, TypeError):
            return default

    # ------------------------------------------------------------------ #
    #  BaseDBMonitor interface
    # ------------------------------------------------------------------ #

    def get_version(self) -> str:
        with self._engine.connect() as conn:
            return conn.execute(text("SELECT VERSION()")).scalar() or ""

    def get_qps_tps(self) -> QPSTpsMetrics:
        status = self._global_status(
            "Questions", "Com_select", "Com_insert", "Com_update", "Com_delete",
            "Com_commit", "Com_rollback", "Uptime",
        )
        uptime = max(self._float(status, "uptime"), 1)
        return QPSTpsMetrics(
            qps=round(self._float(status, "questions") / uptime, 2),
            tps=round(
                (self._float(status, "com_commit") + self._float(status, "com_rollback")) / uptime, 2
            ),
            commit_ps=round(self._float(status, "com_commit") / uptime, 2),
            rollback_ps=round(self._float(status, "com_rollback") / uptime, 2),
            select_ps=round(self._float(status, "com_select") / uptime, 2),
            insert_ps=round(self._float(status, "com_insert") / uptime, 2),
            update_ps=round(self._float(status, "com_update") / uptime, 2),
            delete_ps=round(self._float(status, "com_delete") / uptime, 2),
            uptime_seconds=int(uptime),
        )

    def get_connections(self) -> ConnectionMetrics:
        status = self._global_status(
            "Threads_connected", "Threads_running",
            "Max_used_connections",
        )
        variables = self._global_variables("max_connections")
        max_conn = self._int(variables, "max_connections", 1)
        threads_connected = self._int(status, "threads_connected")
        return ConnectionMetrics(
            total=threads_connected,
            active=self._int(status, "threads_running"),
            idle=max(threads_connected - self._int(status, "threads_running"), 0),
            max_connections=max_conn,
            usage_pct=round(threads_connected / max_conn * 100, 2) if max_conn else 0.0,
        )

    def get_locks(self) -> LockMetrics:
        metrics = LockMetrics()

        # Active lock waits
        try:
            with self._engine.connect() as conn:
                waits = conn.execute(text(
                    "SELECT COUNT(*) FROM performance_schema.data_lock_waits"
                )).scalar()
                metrics.lock_waits = int(waits or 0)
        except Exception:
            try:
                with self._engine.connect() as conn:
                    waits = conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS"
                    )).scalar()
                    metrics.lock_waits = int(waits or 0)
            except Exception:
                pass

        # Deadlock count from InnoDB metrics
        try:
            with self._engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT COUNT_STAR FROM performance_schema.events_statements_summary_global_by_event_name "
                    "WHERE EVENT_NAME = 'statement/sql/deadlock'"
                )).fetchone()
                if row:
                    metrics.deadlocks = int(row[0])
        except Exception:
            pass

        # Blocked queries (trx waiting for lock)
        try:
            with self._engine.connect() as conn:
                blocked = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.INNODB_TRX "
                    "WHERE trx_state = 'LOCK WAIT'"
                )).scalar()
                metrics.blocked_queries = int(blocked or 0)
        except Exception:
            pass

        # Longest wait
        try:
            with self._engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT trx_id, trx_state, trx_started, "
                    "TIMESTAMPDIFF(SECOND, trx_started, NOW()) AS wait_seconds, "
                    "LEFT(trx_query, 200) AS query "
                    "FROM information_schema.INNODB_TRX "
                    "WHERE trx_state = 'LOCK WAIT' "
                    "ORDER BY wait_seconds DESC LIMIT 5"
                )).mappings().all()
                if rows:
                    metrics.longest_wait_seconds = float(rows[0].get("wait_seconds", 0) or 0)
                    metrics.details = [dict(r) for r in rows]
        except Exception:
            pass

        return metrics

    def get_replication(self) -> ReplicationMetrics:
        with self._engine.connect() as conn:
            try:
                rows = conn.execute(text("SHOW REPLICA STATUS")).mappings().all()
            except Exception:
                try:
                    rows = conn.execute(text("SHOW SLAVE STATUS")).mappings().all()
                except Exception:
                    return ReplicationMetrics(is_replica=False)

        if not rows:
            return ReplicationMetrics(is_replica=False)

        row = dict(rows[0])
        delay_raw = row.get("Seconds_Behind_Source") or row.get("Seconds_Behind_Master")
        try:
            delay = float(delay_raw) if delay_raw is not None else 0.0
        except (ValueError, TypeError):
            delay = 0.0

        io_key = next((k for k in row if "io_running" in k.lower()), None)
        sql_key = next((k for k in row if "sql_running" in k.lower()), None)

        return ReplicationMetrics(
            is_replica=True,
            delay_seconds=delay,
            io_running=str(row.get(io_key, "")).upper() == "YES" if io_key else False,
            sql_running=str(row.get(sql_key, "")).upper() == "YES" if sql_key else False,
            error_message=str(row.get("Last_Error", "") or row.get("Last_SQL_Error", "")),
            details={k: str(v) for k, v in row.items() if v is not None},
        )

    def get_slow_queries(self) -> SlowQueryMetrics:
        metrics = SlowQueryMetrics()
        try:
            status = self._global_status("Slow_queries")
            metrics.total_slow_queries = self._int(status, "slow_queries")
        except Exception:
            pass

        try:
            with self._engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT DIGEST_TEXT, COUNT_STAR, "
                    "ROUND(AVG_TIMER_WAIT / 1e12, 3) AS avg_sec, "
                    "ROUND(MAX_TIMER_WAIT / 1e12, 3) AS max_sec, "
                    "SUM_ROWS_EXAMINED, SUM_NO_INDEX_USED "
                    "FROM performance_schema.events_statements_summary_by_digest "
                    "WHERE AVG_TIMER_WAIT / 1e12 >= 1 "
                    "ORDER BY AVG_TIMER_WAIT DESC LIMIT 10"
                )).mappings().all()
                metrics.top_queries = [dict(r) for r in rows]
        except Exception:
            pass

        return metrics

    def get_extra_metrics(self) -> dict[str, Any]:
        """Collect MySQL-specific metrics: InnoDB buffer pool and threads detail."""
        extra: dict[str, Any] = {}

        # InnoDB buffer pool
        status = self._global_status(
            "Innodb_buffer_pool_read_requests",
            "Innodb_buffer_pool_reads",
            "Innodb_buffer_pool_pages_total",
            "Innodb_buffer_pool_pages_free",
            "Innodb_buffer_pool_pages_dirty",
            "Innodb_buffer_pool_bytes_data",
        )
        variables = self._global_variables("innodb_buffer_pool_size")

        read_requests = self._float(status, "innodb_buffer_pool_read_requests")
        physical_reads = self._float(status, "innodb_buffer_pool_reads")
        hit_rate = (
            round((read_requests - physical_reads) / read_requests * 100, 2)
            if read_requests > 0
            else 0.0
        )
        pages_total = self._int(status, "innodb_buffer_pool_pages_total")
        pages_free = self._int(status, "innodb_buffer_pool_pages_free")

        extra["innodb_buffer_pool"] = {
            "size_bytes": self._int(variables, "innodb_buffer_pool_size"),
            "hit_rate_pct": hit_rate,
            "pages_total": pages_total,
            "pages_free": pages_free,
            "pages_dirty": self._int(status, "innodb_buffer_pool_pages_dirty"),
            "pages_used": pages_total - pages_free,
            "usage_pct": round((pages_total - pages_free) / max(pages_total, 1) * 100, 2),
        }

        # Thread cache & created threads
        thread_status = self._global_status("Threads_cached", "Threads_created")
        thread_vars = self._global_variables("thread_cache_size")
        extra["threads"] = {
            "threads_running": self._int(
                self._global_status("Threads_running"), "threads_running"
            ),
            "threads_connected": self._int(
                self._global_status("Threads_connected"), "threads_connected"
            ),
            "threads_cached": self._int(thread_status, "threads_cached"),
            "threads_created": self._int(thread_status, "threads_created"),
            "thread_cache_size": self._int(thread_vars, "thread_cache_size"),
        }

        return extra
