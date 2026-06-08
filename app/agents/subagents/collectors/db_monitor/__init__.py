from app.agents.subagents.collectors.db_monitor.base import BaseDBMonitor, DBMonitorResult
from app.agents.subagents.collectors.db_monitor.mysql_monitor import MySQLMonitor
from app.agents.subagents.collectors.db_monitor.postgresql_monitor import PostgreSQLMonitor


def get_db_monitor(db_type: str, connection_string: str) -> BaseDBMonitor | None:
    """Return the appropriate DBMonitor for the given database type."""
    db = db_type.lower()
    if db in ("mysql", "mariadb"):
        return MySQLMonitor(connection_string)
    if db in ("postgresql", "postgres", "pg"):
        return PostgreSQLMonitor(connection_string)
    return None


__all__ = [
    "BaseDBMonitor",
    "DBMonitorResult",
    "MySQLMonitor",
    "PostgreSQLMonitor",
    "get_db_monitor",
]
