import json
import re

from deepagents import SubAgent
from langchain_core.tools import tool

from app.agents.base import load_prompt


@tool
def detect_db_type(log_content: str) -> str:
    """Detect the database type (MySQL, PostgreSQL, etc.) from log content patterns.

    Returns a JSON object with keys: db_type, confidence, evidence.
    """
    content_lower = log_content.lower()
    scores: dict[str, int] = {"mysql": 0, "postgresql": 0}

    mysql_patterns = [
        r"innodb", r"mysqld", r"mysql\s+\d+\.\d+", r"binlog", r"relay.log",
        r"table_open_cache", r"innodb_buffer_pool", r"my\.cnf", r"my\.ini",
        r"error.*mysql", r"slave.*thread", r"master.*binlog",
    ]
    pg_patterns = [
        r"postgresql", r"postgres", r"postmaster", r"pg_hba", r"postgresql\.conf",
        r"autovacuum", r"wal\s+writer", r"bgwriter", r"checkpoint", r"pg_ctl",
        r"shared_buffers", r"work_mem", r"pg_log",
    ]

    evidence_mysql = [p for p in mysql_patterns if re.search(p, content_lower)]
    evidence_pg = [p for p in pg_patterns if re.search(p, content_lower)]
    scores["mysql"] = len(evidence_mysql)
    scores["postgresql"] = len(evidence_pg)

    if scores["mysql"] == 0 and scores["postgresql"] == 0:
        result = {"db_type": "unknown", "confidence": "low", "evidence": []}
    elif scores["mysql"] >= scores["postgresql"]:
        confidence = "high" if scores["mysql"] >= 3 else "medium"
        result = {"db_type": "mysql", "confidence": confidence, "evidence": evidence_mysql[:5]}
    else:
        confidence = "high" if scores["postgresql"] >= 3 else "medium"
        result = {"db_type": "postgresql", "confidence": confidence, "evidence": evidence_pg[:5]}

    return json.dumps(result, ensure_ascii=False)


@tool
def extract_config_params(log_content: str) -> str:
    """Extract database configuration parameter values from log content.

    Looks for key=value pairs and common config parameter mentions.
    Returns a JSON object mapping parameter names to their values.
    """
    params: dict[str, str] = {}

    # key = value / key: value patterns
    kv_pattern = re.compile(
        r"\b(max_connections|innodb_buffer_pool_size|work_mem|shared_buffers|"
        r"max_allowed_packet|thread_cache_size|query_cache_size|wal_buffers|"
        r"checkpoint_completion_target|effective_cache_size|log_min_duration_statement|"
        r"slow_query_log|long_query_time|binlog_format|sync_binlog|"
        r"innodb_flush_log_at_trx_commit|innodb_log_file_size)\s*[=:]\s*([^\s,;\n]+)",
        re.IGNORECASE,
    )
    for match in kv_pattern.finditer(log_content):
        key = match.group(1).lower()
        value = match.group(2).strip("'\"")
        params[key] = value

    # Version extraction
    version_match = re.search(
        r"(mysql|postgresql|postgres)\s+(?:server\s+)?version[:\s]+([0-9]+\.[0-9]+[^\s,]*)",
        log_content, re.IGNORECASE
    )
    if not version_match:
        version_match = re.search(r"\b([0-9]+\.[0-9]+\.[0-9]+[-\w]*)\b", log_content)
    if version_match:
        params["detected_version"] = version_match.group(0)

    return json.dumps(params, ensure_ascii=False, indent=2)


def create_info_collector_subagent() -> SubAgent:
    return SubAgent(
        name="info-collector",
        description=(
            "Collects background information: detects database type and version, "
            "extracts configuration parameters (max_connections, buffer sizes, etc.), "
            "and summarizes the operating environment from log files and diagnostics data."
        ),
        system_prompt=load_prompt("info_collector.md"),
        tools=[detect_db_type, extract_config_params],
    )
