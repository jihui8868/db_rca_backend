import json
import re
from collections import defaultdict
from datetime import datetime

from deepagents import SubAgent
from langchain_core.tools import tool

from app.agents.base import load_prompt

_TS_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{4}\d{2}\d{2}\s+\d{2}:\d{2}:\d{2})"),
]

_ERROR_CATEGORIES = {
    "connection_exhaustion": [
        r"too many connections", r"connection refused", r"can't connect",
        r"connection timed? ?out", r"max_connections",
    ],
    "lock_contention": [
        r"deadlock", r"lock wait timeout", r"waiting for.*lock",
        r"lock.*held", r"innodb.*lock",
    ],
    "storage_pressure": [
        r"no space left", r"disk.*full", r"out of disk", r"i/o error",
        r"cannot write", r"errno.*28",
    ],
    "memory_pressure": [
        r"out of memory", r"\boom\b", r"killed process", r"cannot allocate",
        r"memory.*exhausted",
    ],
    "replication_issue": [
        r"slave.*error", r"replica.*error", r"replication.*stop",
        r"binlog.*error", r"relay log", r"gtid.*inconsist",
    ],
    "slow_query": [
        r"slow query", r"query.*time.*\d{2,}", r"long.*running.*query",
        r"duration.*ms.*statement",
    ],
    "crash_recovery": [
        r"crash recovery", r"unexpected shutdown", r"innodb.*recovery",
        r"redo log", r"database.*crash",
    ],
    "vacuum_bloat": [
        r"autovacuum", r"dead tuple", r"table.*bloat", r"vacuum.*taking",
        r"could not.*vacuum",
    ],
    "wal_checkpoint": [
        r"wal.*error", r"checkpoint.*second", r"checkpoint.*warning",
        r"wal.*segment", r"archiving.*failed",
    ],
}


def _extract_timestamp(line: str) -> datetime | None:
    for pat in _TS_PATTERNS:
        m = pat.search(line)
        if m:
            raw = m.group(1).replace("T", " ")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d %H:%M:%S"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    pass
    return None


@tool
def detect_error_spike(log_content: str, window_minutes: int = 5) -> str:
    """Detect time windows with abnormally high error frequency in log content.

    Args:
        log_content: Raw log text containing timestamped error lines.
        window_minutes: Size of the sliding window in minutes.

    Returns JSON with: spike_windows (list of {window_start, error_count}),
    baseline_rate, peak_rate, spike_ratio, first_spike_time.
    """
    error_times: list[datetime] = []
    error_re = re.compile(r"\b(ERROR|FATAL|CRITICAL|Exception)\b", re.I)

    for line in log_content.splitlines():
        if error_re.search(line):
            ts = _extract_timestamp(line)
            if ts:
                error_times.append(ts)

    if len(error_times) < 2:
        return json.dumps({
            "spike_windows": [],
            "message": "Not enough timestamped error lines to detect spikes.",
        })

    error_times.sort()
    buckets: dict[str, int] = defaultdict(int)
    for ts in error_times:
        minute_key = ts.strftime("%Y-%m-%d %H:%M")
        buckets[minute_key] += 1

    counts = list(buckets.values())
    avg = sum(counts) / len(counts)
    threshold = max(avg * 3, avg + 2)

    spikes = [
        {"window_start": k, "error_count": v}
        for k, v in sorted(buckets.items())
        if v >= threshold
    ]

    return json.dumps({
        "spike_windows": spikes,
        "baseline_rate_per_minute": round(avg, 2),
        "peak_rate_per_minute": max(counts),
        "spike_threshold": round(threshold, 2),
        "first_spike_time": spikes[0]["window_start"] if spikes else None,
        "total_error_lines_with_ts": len(error_times),
    }, ensure_ascii=False, indent=2)


@tool
def classify_error_categories(log_content: str) -> str:
    """Classify log content into database error categories with evidence.

    Categories: connection_exhaustion, lock_contention, storage_pressure,
    memory_pressure, replication_issue, slow_query, crash_recovery,
    vacuum_bloat, wal_checkpoint.

    Returns JSON: list of {category, hit_count, sample_lines} sorted by hit_count.
    """
    category_hits: dict[str, list[str]] = defaultdict(list)

    for line in log_content.splitlines():
        line_lower = line.lower()
        for category, patterns in _ERROR_CATEGORIES.items():
            for pat in patterns:
                if re.search(pat, line_lower):
                    category_hits[category].append(line.strip()[:200])
                    break

    result = [
        {
            "category": cat,
            "hit_count": len(lines),
            "sample_lines": lines[:3],
        }
        for cat, lines in sorted(category_hits.items(), key=lambda x: -len(x[1]))
        if lines
    ]

    return json.dumps(result, ensure_ascii=False, indent=2)


def create_anomaly_detection_subagent() -> SubAgent:
    return SubAgent(
        name="anomaly-detection",
        description=(
            "Detects anomalies from log data: identifies time-series error spikes, "
            "classifies errors into categories (connection exhaustion, lock contention, "
            "storage pressure, replication issues, etc.), and reconstructs the incident timeline."
        ),
        system_prompt=load_prompt("anomaly_detection.md"),
        tools=[detect_error_spike, classify_error_categories],
    )
