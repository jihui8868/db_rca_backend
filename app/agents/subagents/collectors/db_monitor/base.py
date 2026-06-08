from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConnectionMetrics:
    total: int = 0
    active: int = 0
    idle: int = 0
    idle_in_transaction: int = 0
    waiting_for_lock: int = 0
    max_connections: int = 0
    usage_pct: float = 0.0


@dataclass
class QPSTpsMetrics:
    qps: float = 0.0          # queries per second
    tps: float = 0.0          # transactions per second (commit + rollback)
    commit_ps: float = 0.0
    rollback_ps: float = 0.0
    select_ps: float = 0.0
    insert_ps: float = 0.0
    update_ps: float = 0.0
    delete_ps: float = 0.0
    uptime_seconds: int = 0


@dataclass
class LockMetrics:
    lock_waits: int = 0
    deadlocks: int = 0
    longest_wait_seconds: float = 0.0
    blocked_queries: int = 0
    details: list[dict] = field(default_factory=list)


@dataclass
class ReplicationMetrics:
    is_replica: bool = False
    delay_seconds: float = 0.0
    io_running: bool = False
    sql_running: bool = False
    error_message: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class SlowQueryMetrics:
    total_slow_queries: int = 0
    top_queries: list[dict] = field(default_factory=list)


@dataclass
class DBMonitorResult:
    db_type: str = ""
    host: str = ""
    version: str = ""
    collected_at: str = ""
    qps_tps: QPSTpsMetrics = field(default_factory=QPSTpsMetrics)
    connections: ConnectionMetrics = field(default_factory=ConnectionMetrics)
    locks: LockMetrics = field(default_factory=LockMetrics)
    replication: ReplicationMetrics = field(default_factory=ReplicationMetrics)
    slow_queries: SlowQueryMetrics = field(default_factory=SlowQueryMetrics)
    extra: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        import dataclasses
        return dataclasses.asdict(self)


class BaseDBMonitor(ABC):
    """Abstract base class for database monitoring metric collection.

    Each database implementation inherits this class and provides
    DB-specific queries for every metric category.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    @abstractmethod
    def get_version(self) -> str:
        """Return the database server version string."""

    @abstractmethod
    def get_qps_tps(self) -> QPSTpsMetrics:
        """Collect QPS (queries/sec) and TPS (transactions/sec) metrics."""

    @abstractmethod
    def get_connections(self) -> ConnectionMetrics:
        """Collect current connection counts and max_connections limit."""

    @abstractmethod
    def get_locks(self) -> LockMetrics:
        """Collect lock waits, deadlocks, and blocked queries."""

    @abstractmethod
    def get_replication(self) -> ReplicationMetrics:
        """Collect replication lag and status (primary returns is_replica=False)."""

    @abstractmethod
    def get_slow_queries(self) -> SlowQueryMetrics:
        """Collect slow query statistics from the DB engine."""

    @abstractmethod
    def get_extra_metrics(self) -> dict[str, Any]:
        """Collect DB-specific metrics (e.g. InnoDB buffer pool, WAL, vacuum)."""

    def collect_all(self) -> DBMonitorResult:
        """Run all metric collectors and return a unified result object."""
        from datetime import datetime, timezone

        result = DBMonitorResult(
            db_type=self.__class__.__name__.replace("Monitor", "").lower(),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

        def _safe(label: str, fn):
            try:
                return fn()
            except Exception as exc:
                result.errors.append(f"{label}: {exc}")
                return None

        result.version = _safe("version", self.get_version) or ""
        result.qps_tps = _safe("qps_tps", self.get_qps_tps) or QPSTpsMetrics()
        result.connections = _safe("connections", self.get_connections) or ConnectionMetrics()
        result.locks = _safe("locks", self.get_locks) or LockMetrics()
        result.replication = _safe("replication", self.get_replication) or ReplicationMetrics()
        result.slow_queries = _safe("slow_queries", self.get_slow_queries) or SlowQueryMetrics()
        result.extra = _safe("extra_metrics", self.get_extra_metrics) or {}
        return result
