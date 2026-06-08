from sqlalchemy import create_engine, text

from db_adapters.base import BaseDBAdapter


class MySQLAdapter(BaseDBAdapter):
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
            result = conn.execute(text("SELECT VERSION()"))
            return result.scalar()

    def get_active_connections(self) -> list[dict]:
        query = text(
            "SELECT ID, USER, HOST, DB, COMMAND, TIME, STATE, INFO "
            "FROM INFORMATION_SCHEMA.PROCESSLIST "
            "WHERE COMMAND != 'Sleep' ORDER BY TIME DESC LIMIT 50"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]

    def get_slow_queries(self, threshold_seconds: float = 1.0) -> list[dict]:
        query = text(
            "SELECT DIGEST_TEXT, COUNT_STAR, AVG_TIMER_WAIT/1e12 AS avg_seconds, "
            "MAX_TIMER_WAIT/1e12 AS max_seconds, SUM_ERRORS, FIRST_SEEN, LAST_SEEN "
            "FROM performance_schema.events_statements_summary_by_digest "
            "WHERE AVG_TIMER_WAIT/1e12 >= :threshold "
            "ORDER BY AVG_TIMER_WAIT DESC LIMIT 20"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"threshold": threshold_seconds}).mappings().all()
        return [dict(row) for row in rows]

    def get_error_logs(self, limit: int = 100) -> list[dict]:
        # MySQL error log via performance_schema if available
        query = text(
            "SELECT LOGGED, THREAD_ID, PRIO, ERROR_CODE, SUBSYSTEM, DATA "
            "FROM performance_schema.error_log "
            "WHERE PRIO IN ('Error', 'Warning') "
            "ORDER BY LOGGED DESC LIMIT :limit"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]

    def get_table_stats(self, schema: str | None = None) -> list[dict]:
        where = "WHERE TABLE_TYPE = 'BASE TABLE'"
        params: dict = {}
        if schema:
            where += " AND TABLE_SCHEMA = :schema"
            params["schema"] = schema
        query = text(
            f"SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_ROWS, "
            f"ROUND(DATA_LENGTH/1024/1024, 2) AS data_mb, "
            f"ROUND(INDEX_LENGTH/1024/1024, 2) AS index_mb, "
            f"CREATE_TIME, UPDATE_TIME "
            f"FROM INFORMATION_SCHEMA.TABLES {where} "
            f"ORDER BY DATA_LENGTH DESC LIMIT 30"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_index_stats(self, schema: str | None = None) -> list[dict]:
        where = "WHERE s.NON_UNIQUE = 1"
        params: dict = {}
        if schema:
            where += " AND s.TABLE_SCHEMA = :schema"
            params["schema"] = schema
        query = text(
            f"SELECT s.TABLE_SCHEMA, s.TABLE_NAME, s.INDEX_NAME, s.COLUMN_NAME, "
            f"s.CARDINALITY, s.INDEX_TYPE "
            f"FROM INFORMATION_SCHEMA.STATISTICS s {where} "
            f"ORDER BY s.TABLE_SCHEMA, s.TABLE_NAME, s.INDEX_NAME LIMIT 50"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query, params).mappings().all()
        return [dict(row) for row in rows]

    def get_lock_info(self) -> list[dict]:
        query = text(
            "SELECT r.trx_id AS waiting_trx, r.trx_mysql_thread_id AS waiting_thread, "
            "r.trx_query AS waiting_query, b.trx_id AS blocking_trx, "
            "b.trx_mysql_thread_id AS blocking_thread, b.trx_query AS blocking_query "
            "FROM information_schema.innodb_lock_waits w "
            "JOIN information_schema.innodb_trx b ON b.trx_id = w.blocking_trx_id "
            "JOIN information_schema.innodb_trx r ON r.trx_id = w.requesting_trx_id "
            "LIMIT 20"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [dict(row) for row in rows]

    def get_replication_status(self) -> list[dict]:
        with self._engine.connect() as conn:
            try:
                rows = conn.execute(text("SHOW REPLICA STATUS")).mappings().all()
                if not rows:
                    rows = conn.execute(text("SHOW SLAVE STATUS")).mappings().all()
            except Exception:
                rows = []
        return [dict(row) for row in rows]
