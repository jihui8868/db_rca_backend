import json
import re

from deepagents import SubAgent
from langchain_core.tools import tool

from app.agents.base import load_prompt

_CAUSAL_PATTERNS = {
    "mysql": [
        {
            "id": "mysql-conn-exhaustion",
            "name": "连接耗尽链",
            "chain": ["慢查询增多", "连接未及时释放", "连接数堆积", "达到max_connections上限", "新连接请求失败"],
            "trigger_categories": ["slow_query", "connection_exhaustion"],
            "keywords": ["too many connections", "max_connections", "slow query"],
        },
        {
            "id": "mysql-lock-cascade",
            "name": "锁竞争级联",
            "chain": ["长事务持锁", "其他事务等待行锁", "锁等待超时", "事务回滚增多", "重试风暴"],
            "trigger_categories": ["lock_contention"],
            "keywords": ["deadlock", "lock wait timeout", "innodb lock"],
        },
        {
            "id": "mysql-io-pressure",
            "name": "InnoDB I/O 压力链",
            "chain": ["大量写入操作", "Buffer Pool 写压力", "Checkpoint 频率上升", "I/O 延迟增大", "所有操作变慢"],
            "trigger_categories": ["slow_query", "storage_pressure"],
            "keywords": ["innodb", "checkpoint", "buffer pool", "flush"],
        },
        {
            "id": "mysql-replication-lag",
            "name": "主从复制延迟链",
            "chain": ["主库大事务/高并发写入", "Binlog 同步延迟", "从库数据滞后", "读从库出现脏读", "应用逻辑错误"],
            "trigger_categories": ["replication_issue"],
            "keywords": ["slave", "replica", "binlog", "relay log"],
        },
        {
            "id": "mysql-crash-recovery",
            "name": "崩溃恢复链",
            "chain": ["异常关闭/OOM Kill", "InnoDB 崩溃恢复启动", "Redo Log 重放", "数据库恢复完成", "可能存在数据不一致"],
            "trigger_categories": ["crash_recovery", "memory_pressure"],
            "keywords": ["crash recovery", "unexpected shutdown", "redo log"],
        },
    ],
    "postgresql": [
        {
            "id": "pg-conn-exhaustion",
            "name": "连接池耗尽链",
            "chain": ["慢查询/长事务", "连接不释放", "连接数逼近max_connections", "新连接被拒绝", "应用报错"],
            "trigger_categories": ["slow_query", "connection_exhaustion"],
            "keywords": ["too many connections", "max_connections", "pg_stat_activity"],
        },
        {
            "id": "pg-vacuum-bloat",
            "name": "Autovacuum 积压膨胀链",
            "chain": ["大量UPDATE/DELETE", "Dead tuples 积累", "Autovacuum 处理不及时", "表膨胀", "顺序扫描变慢"],
            "trigger_categories": ["vacuum_bloat", "slow_query"],
            "keywords": ["autovacuum", "dead tuples", "vacuum", "bloat"],
        },
        {
            "id": "pg-lock-contention",
            "name": "锁等待链",
            "chain": ["长事务持有行锁/表锁", "其他事务等待", "pg_locks 积压", "查询超时", "应用报错"],
            "trigger_categories": ["lock_contention"],
            "keywords": ["lock", "deadlock", "blocking", "pg_locks"],
        },
        {
            "id": "pg-wal-pressure",
            "name": "WAL/Checkpoint 压力链",
            "chain": ["高写入速率", "WAL 生成速率过高", "Checkpoint 频繁触发", "I/O 抖动", "查询延迟上升"],
            "trigger_categories": ["wal_checkpoint", "slow_query"],
            "keywords": ["checkpoint", "wal", "bgwriter", "fsync"],
        },
        {
            "id": "pg-replication-lag",
            "name": "流复制延迟链",
            "chain": ["主库写入压力大", "WAL 发送延迟", "从库 replay_lag 增大", "读从库数据滞后", "应用逻辑错误"],
            "trigger_categories": ["replication_issue"],
            "keywords": ["replication", "standby", "wal sender", "replay_lag"],
        },
    ],
    "common": [
        {
            "id": "common-oom",
            "name": "OOM 连锁",
            "chain": ["内存配置过高或连接数过多", "系统内存耗尽", "OOM Killer 触发", "数据库进程被杀", "服务中断"],
            "trigger_categories": ["memory_pressure", "crash_recovery"],
            "keywords": ["out of memory", "oom", "killed"],
        },
        {
            "id": "common-disk-full",
            "name": "磁盘满导致服务中断",
            "chain": ["磁盘写入持续增长", "磁盘空间耗尽", "数据库无法写入日志/数据", "写操作全部失败", "服务不可用"],
            "trigger_categories": ["storage_pressure"],
            "keywords": ["no space left", "disk full", "errno 28"],
        },
    ],
}


@tool
def get_causal_patterns(db_type: str) -> str:
    """Retrieve known causal failure patterns for a given database type.

    Args:
        db_type: One of 'mysql', 'postgresql', or 'common'.

    Returns a JSON array of causal pattern objects, each containing:
    id, name, chain (ordered cause→effect list), trigger_categories, keywords.
    """
    db_lower = db_type.lower()
    if "mysql" in db_lower or "mariadb" in db_lower:
        patterns = _CAUSAL_PATTERNS["mysql"] + _CAUSAL_PATTERNS["common"]
    elif "postgres" in db_lower or "pg" in db_lower:
        patterns = _CAUSAL_PATTERNS["postgresql"] + _CAUSAL_PATTERNS["common"]
    else:
        patterns = _CAUSAL_PATTERNS["mysql"] + _CAUSAL_PATTERNS["postgresql"] + _CAUSAL_PATTERNS["common"]

    return json.dumps(patterns, ensure_ascii=False, indent=2)


@tool
def match_anomalies_to_patterns(anomaly_categories_json: str, db_type: str) -> str:
    """Match a list of detected anomaly categories to known causal patterns.

    Args:
        anomaly_categories_json: JSON array of category names detected by anomaly-detection
                                  (e.g. ["lock_contention", "slow_query"]).
        db_type: Database type string ('mysql' or 'postgresql').

    Returns JSON: list of matched patterns with match_score and matched_categories,
    sorted by match_score descending.
    """
    try:
        detected: list[str] = json.loads(anomaly_categories_json)
    except json.JSONDecodeError:
        detected = re.findall(r"\w+", anomaly_categories_json)

    detected_set = set(detected)
    db_lower = db_type.lower()

    if "mysql" in db_lower or "mariadb" in db_lower:
        candidates = _CAUSAL_PATTERNS["mysql"] + _CAUSAL_PATTERNS["common"]
    elif "postgres" in db_lower or "pg" in db_lower:
        candidates = _CAUSAL_PATTERNS["postgresql"] + _CAUSAL_PATTERNS["common"]
    else:
        candidates = (
            _CAUSAL_PATTERNS["mysql"]
            + _CAUSAL_PATTERNS["postgresql"]
            + _CAUSAL_PATTERNS["common"]
        )

    results = []
    for pat in candidates:
        trigger_set = set(pat["trigger_categories"])
        matched = detected_set & trigger_set
        if matched:
            score = len(matched) / len(trigger_set)
            results.append({
                "pattern_id": pat["id"],
                "pattern_name": pat["name"],
                "causal_chain": pat["chain"],
                "match_score": round(score, 2),
                "matched_categories": sorted(matched),
                "unmatched_categories": sorted(trigger_set - matched),
            })

    results.sort(key=lambda x: -x["match_score"])
    return json.dumps(results, ensure_ascii=False, indent=2)


def create_knowledge_graph_subagent() -> SubAgent:
    return SubAgent(
        name="knowledge-graph",
        description=(
            "Builds causal relationship graphs between detected anomalies. "
            "Retrieves known DB failure patterns (MySQL/PostgreSQL) and matches "
            "observed anomaly categories to identify root cause candidates vs. downstream symptoms."
        ),
        system_prompt=load_prompt("knowledge_graph.md"),
        tools=[get_causal_patterns, match_anomalies_to_patterns],
    )
