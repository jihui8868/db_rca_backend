import json
import re
from collections import Counter

from deepagents import SubAgent
from langchain_core.tools import tool

from app.agents.base import load_prompt


# ======================================================================
#  Log analysis tools  (kept from original implementation)
# ======================================================================

_ERROR_LEVELS = re.compile(
    r"\b(ERROR|FATAL|CRITICAL|WARNING|WARN|Exception|Error:)\b", re.IGNORECASE
)


@tool
def filter_error_lines(log_content: str, max_lines: int = 300) -> str:
    """Extract ERROR, WARNING, FATAL, and Exception lines from log content.

    Args:
        log_content: Raw log file text.
        max_lines: Maximum number of lines to return (most recent first).

    Returns a plain-text list of matching lines with their line numbers.
    """
    results = []
    for i, line in enumerate(log_content.splitlines(), start=1):
        if _ERROR_LEVELS.search(line):
            results.append(f"[L{i}] {line.rstrip()}")
    if len(results) > max_lines:
        results = results[-max_lines:]
    if not results:
        return "No ERROR/WARNING/FATAL lines found in the provided log content."
    return "\n".join(results)


@tool
def count_error_patterns(log_content: str) -> str:
    """Count occurrences of common database error patterns in log content.

    Returns a JSON array sorted by frequency (highest first), each item:
    {pattern, count, sample_line}.
    """
    patterns = {
        "too_many_connections":  re.compile(r"too many connections", re.I),
        "connection_refused":    re.compile(r"connection refused|can't connect", re.I),
        "connection_timeout":    re.compile(r"connect(ion)? timed? ?out", re.I),
        "deadlock":              re.compile(r"deadlock found|deadlock detected", re.I),
        "lock_wait_timeout":     re.compile(r"lock wait timeout exceeded", re.I),
        "table_lock":            re.compile(r"waiting for (table|metadata) lock", re.I),
        "out_of_memory":         re.compile(r"out of memory|oom|killed process", re.I),
        "disk_full":             re.compile(r"no space left|disk.*full|out of disk", re.I),
        "slow_query":            re.compile(r"slow query|query.*time.*\d{2,}", re.I),
        "replication_error":     re.compile(r"slave.*error|replica.*error|replication.*stop", re.I),
        "crash_recovery":        re.compile(r"crash recovery|innodb.*recovery|unexpected shutdown", re.I),
        "autovacuum":            re.compile(r"autovacuum.*blocked|vacuum.*taking", re.I),
        "wal_error":             re.compile(r"wal.*error|could not write.*wal", re.I),
        "checkpoint":            re.compile(r"checkpoint.*seconds|checkpoint request", re.I),
        "syntax_error":          re.compile(r"syntax error|you have an error in your sql", re.I),
        "access_denied":         re.compile(r"access denied", re.I),
    }
    counts: Counter = Counter()
    samples: dict[str, str] = {}
    for line in log_content.splitlines():
        for name, pat in patterns.items():
            if pat.search(line):
                counts[name] += 1
                if name not in samples:
                    samples[name] = line.strip()[:200]
    result = [
        {"pattern": k, "count": v, "sample_line": samples.get(k, "")}
        for k, v in counts.most_common()
        if v > 0
    ]
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def parse_slow_query_log(log_content: str, max_queries: int = 20) -> str:
    """Parse MySQL slow query log or PostgreSQL slow statement entries.

    Returns a JSON array of slow queries sorted by execution time (slowest first).
    """
    queries = []
    mysql_block = re.compile(
        r"#\s*Time:\s*(\S+).*?#\s*Query_time:\s*([\d.]+)\s+Lock_time:\s*([\d.]+)"
        r".*?(?:SET timestamp=\d+;)?\s*((?:SELECT|INSERT|UPDATE|DELETE|REPLACE|.*?);)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in mysql_block.finditer(log_content):
        queries.append({
            "db": "mysql",
            "timestamp": m.group(1),
            "query_time": float(m.group(2)),
            "lock_time": float(m.group(3)),
            "query": m.group(4).strip()[:300],
        })
    pg_slow = re.compile(
        r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[^\n]*)duration:\s*([\d.]+)\s*ms\s+statement:\s*([^\n]+)",
        re.IGNORECASE,
    )
    for m in pg_slow.finditer(log_content):
        queries.append({
            "db": "postgresql",
            "timestamp": m.group(1).strip(),
            "query_time": float(m.group(2)) / 1000,
            "query": m.group(3).strip()[:300],
        })
    queries.sort(key=lambda x: x["query_time"], reverse=True)
    return json.dumps(queries[:max_queries], ensure_ascii=False, indent=2)


# ======================================================================
#  Host metrics tool  (via Nightingale)
# ======================================================================

@tool
def get_host_metrics(host: str) -> str:
    """Collect host-level monitoring metrics from Nightingale (夜莺) monitoring system.

    Fetches CPU, memory, disk, network, and load metrics for the given host.

    Args:
        host: The host identifier (ident) registered in Nightingale, e.g. "192.168.1.10"
              or the hostname like "db-server-01".

    Returns JSON with keys: cpu, memory, disk, network, load, errors.

    CPU: usage_active_pct, usage_user_pct, usage_system_pct, usage_iowait_pct
    Memory: used_pct, total_bytes, used_bytes, available_bytes
    Disk: used_pct, total_bytes, used_bytes, free_bytes
    Network: recv_bytes_per_sec, sent_bytes_per_sec, drop_in/out_per_sec
    Load: load1, load5, load15
    """
    from app.agents.subagents.collectors.os_monitor.nightingale import NightingaleCollector
    collector = NightingaleCollector()
    result = collector.collect(host)
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)


# ======================================================================
#  Database metrics tools
# ======================================================================

@tool
def get_mysql_metrics(connection_string: str) -> str:
    """Collect real-time monitoring metrics from a MySQL / MariaDB instance.

    Collects: QPS, TPS, threads_running, threads_connected,
    InnoDB buffer pool (hit rate, pages), lock waits, deadlocks,
    replication delay, connection usage, and top slow queries.

    Args:
        connection_string: SQLAlchemy connection string, e.g.
            "mysql+pymysql://user:password@host:3306/dbname"

    Returns a structured JSON object with all metric categories.
    """
    from app.agents.subagents.collectors.db_monitor import MySQLMonitor
    monitor = MySQLMonitor(connection_string)
    result = monitor.collect_all()
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str)


@tool
def get_postgresql_metrics(connection_string: str) -> str:
    """Collect real-time monitoring metrics from a PostgreSQL instance.

    Collects: TPS, connections (active/idle/idle-in-txn/waiting),
    deadlocks, checkpoint stats (checkpoints_timed/req, write/sync time),
    WAL stats (records, bytes, buffers_full), lock summary,
    vacuum status (top tables by dead tuples, running vacuums),
    and top slow queries via pg_stat_statements.

    Args:
        connection_string: SQLAlchemy connection string, e.g.
            "postgresql+psycopg2://user:password@host:5432/dbname"

    Returns a structured JSON object with all metric categories.
    """
    from app.agents.subagents.collectors.db_monitor import PostgreSQLMonitor
    monitor = PostgreSQLMonitor(connection_string)
    result = monitor.collect_all()
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, default=str)


# ======================================================================
#  SubAgent definition
# ======================================================================

def create_observability_subagent() -> SubAgent:
    return SubAgent(
        name="observability",
        description=(
            "Collects observability and monitoring data for fault analysis. "
            "Can: (1) fetch host metrics (CPU/memory/disk/network/load) from Nightingale; "
            "(2) collect MySQL real-time metrics (QPS/TPS/threads/InnoDB buffer pool/"
            "lock waits/deadlocks/replication delay/connection usage/slow queries); "
            "(3) collect PostgreSQL metrics (TPS/connections/deadlocks/checkpoint/WAL/"
            "locks/vacuum). Also parses uploaded log files for error patterns."
        ),
        system_prompt=load_prompt("observability.md"),
        tools=[
            # Host monitoring
            get_host_metrics,
            # Database monitoring
            get_mysql_metrics,
            get_postgresql_metrics,
            # Log analysis
            filter_error_lines,
            count_error_patterns,
            parse_slow_query_log,
        ],
    )
