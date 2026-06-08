from abc import ABC, abstractmethod


class BaseDBAdapter(ABC):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    @abstractmethod
    def test_connection(self) -> bool:
        """Test whether the database connection is available."""

    @abstractmethod
    def get_db_version(self) -> str:
        """Return the database version string."""

    @abstractmethod
    def get_active_connections(self) -> list[dict]:
        """Return currently active connections/sessions."""

    @abstractmethod
    def get_slow_queries(self, threshold_seconds: float = 1.0) -> list[dict]:
        """Return queries running longer than threshold_seconds."""

    @abstractmethod
    def get_error_logs(self, limit: int = 100) -> list[dict]:
        """Return recent error log entries from the database."""

    @abstractmethod
    def get_table_stats(self, schema: str | None = None) -> list[dict]:
        """Return table-level statistics (row count, size, etc.)."""

    @abstractmethod
    def get_index_stats(self, schema: str | None = None) -> list[dict]:
        """Return index usage statistics."""

    @abstractmethod
    def get_lock_info(self) -> list[dict]:
        """Return current lock and wait information."""

    @abstractmethod
    def get_replication_status(self) -> list[dict]:
        """Return replication lag and status information."""

    def get_diagnostics_summary(self) -> dict:
        """Collect all diagnostic data into a single dict for agent injection."""
        summary = {
            "db_version": None,
            "active_connections": [],
            "slow_queries": [],
            "table_stats": [],
            "index_stats": [],
            "lock_info": [],
            "replication_status": [],
            "errors": [],
        }
        try:
            summary["db_version"] = self.get_db_version()
        except Exception as e:
            summary["errors"].append(f"db_version: {e}")
        try:
            summary["active_connections"] = self.get_active_connections()
        except Exception as e:
            summary["errors"].append(f"active_connections: {e}")
        try:
            summary["slow_queries"] = self.get_slow_queries()
        except Exception as e:
            summary["errors"].append(f"slow_queries: {e}")
        try:
            summary["table_stats"] = self.get_table_stats()
        except Exception as e:
            summary["errors"].append(f"table_stats: {e}")
        try:
            summary["index_stats"] = self.get_index_stats()
        except Exception as e:
            summary["errors"].append(f"index_stats: {e}")
        try:
            summary["lock_info"] = self.get_lock_info()
        except Exception as e:
            summary["errors"].append(f"lock_info: {e}")
        try:
            summary["replication_status"] = self.get_replication_status()
        except Exception as e:
            summary["errors"].append(f"replication_status: {e}")
        return summary
