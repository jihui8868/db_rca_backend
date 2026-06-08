import json
import re

from deepagents import SubAgent
from langchain_core.tools import tool

from app.agents.base import load_prompt

_SEVERITY_RULES = [
    ({"crash_recovery", "memory_pressure", "storage_pressure"}, "critical"),
    ({"connection_exhaustion", "lock_contention", "replication_issue"}, "high"),
    ({"slow_query", "vacuum_bloat", "wal_checkpoint"}, "medium"),
    (set(), "low"),
]

_REMEDIATION_DB: dict[str, dict[str, list[str]]] = {
    "connection_exhaustion": {
        "immediate": [
            "SHOW PROCESSLIST / SELECT * FROM pg_stat_activity — 找出占用连接的长事务并 KILL",
            "临时提高 max_connections（需重启或 SET GLOBAL，注意内存影响）",
            "检查连接池配置，确认 pool_size 和 max_overflow 合理",
        ],
        "short_term": [
            "部署 PgBouncer（PostgreSQL）或 ProxySQL（MySQL）连接池中间件",
            "排查应用侧连接泄漏：未关闭连接、异常未捕获导致连接未归还",
            "设置 wait_timeout / idle_in_transaction_session_timeout 自动回收空闲连接",
        ],
        "long_term": [
            "建立连接数监控告警（阈值 80% max_connections）",
            "评估是否需要水平扩展读副本分担连接压力",
        ],
    },
    "lock_contention": {
        "immediate": [
            "MySQL: SELECT * FROM information_schema.innodb_lock_waits — 找阻塞事务并 KILL",
            "PostgreSQL: SELECT * FROM pg_locks JOIN pg_stat_activity ON ... — 终止阻塞会话",
            "回滚或提交长时间未结束的事务",
        ],
        "short_term": [
            "优化高频更新的事务逻辑，缩短事务持锁时间",
            "调整 innodb_lock_wait_timeout / lock_timeout 避免无限等待",
            "检查是否存在缺少索引导致的全表锁",
        ],
        "long_term": [
            "应用层增加死锁重试机制",
            "对热点数据考虑乐观锁或行级分片策略",
            "定期监控 long_running_transactions",
        ],
    },
    "storage_pressure": {
        "immediate": [
            "df -h 确认磁盘使用率，立即清理 binlog / WAL archive / 旧备份文件",
            "MySQL: PURGE BINARY LOGS BEFORE '...' 清理过期 binlog",
            "PostgreSQL: pg_archivecleanup 清理归档 WAL",
        ],
        "short_term": [
            "扩容磁盘或迁移数据目录到更大磁盘",
            "设置 expire_logs_days / wal_keep_size 控制日志保留量",
            "建立磁盘使用率告警（阈值 85%）",
        ],
        "long_term": [
            "建立定期数据归档和清理策略",
            "评估表分区或历史数据迁移方案",
        ],
    },
    "memory_pressure": {
        "immediate": [
            "检查系统内存使用：free -h，确认是否有 OOM 事件（dmesg | grep oom）",
            "临时降低 innodb_buffer_pool_size / shared_buffers 释放内存",
            "KILL 占用大内存的查询（大排序、大临时表）",
        ],
        "short_term": [
            "优化内存配置：buffer pool 设置为物理内存的 50-70%",
            "检查是否存在内存泄漏（长时间运行的慢查询、临时表过大）",
            "增加物理内存或减少 max_connections（每连接占用线程栈内存）",
        ],
        "long_term": [
            "建立内存使用率监控告警",
            "评估查询优化降低排序/临时表内存消耗",
        ],
    },
    "replication_issue": {
        "immediate": [
            "MySQL: SHOW REPLICA STATUS\\G — 检查 Seconds_Behind_Source 和 Last_Error",
            "PostgreSQL: SELECT * FROM pg_stat_replication — 检查 replay_lag",
            "若复制中断: STOP REPLICA; SET GLOBAL SQL_SLAVE_SKIP_COUNTER=1; START REPLICA;（仅跳过非关键错误）",
        ],
        "short_term": [
            "找出导致大延迟的大事务，优化为小事务分批提交",
            "MySQL: 启用并行复制 slave_parallel_workers",
            "PostgreSQL: 检查 wal_level 和 max_wal_senders 配置",
        ],
        "long_term": [
            "建立复制延迟监控告警（阈值 30s）",
            "评估使用 MHA/Orchestrator（MySQL）或 Patroni（PostgreSQL）提升 HA 能力",
        ],
    },
    "slow_query": {
        "immediate": [
            "KILL 当前正在运行的超长查询",
            "EXPLAIN 分析慢查询执行计划，确认是否全表扫描",
        ],
        "short_term": [
            "为高频慢查询添加合适索引",
            "重写低效 SQL（避免 SELECT *、子查询改 JOIN、减少大 IN 列表）",
            "开启慢查询日志并设置合理 long_query_time 阈值",
        ],
        "long_term": [
            "建立 SQL 性能基线和定期 SQL Review 机制",
            "考虑读写分离减轻主库查询压力",
        ],
    },
    "vacuum_bloat": {
        "immediate": [
            "手动触发: VACUUM ANALYZE <table_name>",
            "检查 autovacuum 是否被阻塞: SELECT * FROM pg_stat_activity WHERE wait_event_type = 'Lock'",
        ],
        "short_term": [
            "调整 autovacuum_vacuum_scale_factor 和 autovacuum_vacuum_cost_delay",
            "对膨胀严重的表执行 VACUUM FULL（需停写，影响业务）或 pg_repack（在线）",
        ],
        "long_term": [
            "监控各表 dead_tup_count，超过阈值告警",
            "减少大批量 UPDATE/DELETE，改为分批操作",
        ],
    },
    "crash_recovery": {
        "immediate": [
            "确认数据库已完成 crash recovery（查看启动日志末尾的 recovery complete 信息）",
            "检查数据一致性（MySQL: CHECK TABLE; PostgreSQL: pg_dump --schema-only 验证）",
            "确认应用可正常连接并执行基本查询",
        ],
        "short_term": [
            "分析崩溃原因（OOM、硬件故障、强制 kill）并针对性解决",
            "MySQL: 确认 innodb_flush_log_at_trx_commit=1 保证持久性",
            "PostgreSQL: 确认 fsync=on",
        ],
        "long_term": [
            "建立自动故障检测和恢复机制（keepalived、Orchestrator、Patroni）",
            "定期进行恢复演练验证备份可用性",
        ],
    },
}


@tool
def assess_severity(detected_categories_json: str) -> str:
    """Assess fault severity level based on detected error categories.

    Args:
        detected_categories_json: JSON array of category strings, e.g.
            ["lock_contention", "slow_query"].

    Returns JSON: {severity, level_description, matched_critical_categories}.
    """
    try:
        categories: list[str] = json.loads(detected_categories_json)
    except json.JSONDecodeError:
        categories = re.findall(r"\w+", detected_categories_json)

    cat_set = set(categories)
    for trigger_set, level in _SEVERITY_RULES:
        if not trigger_set or (cat_set & trigger_set):
            descriptions = {
                "critical": "服务中断或数据丢失风险，需立即处理",
                "high": "严重性能降级或数据不一致风险，需在1小时内处理",
                "medium": "性能受损但服务可用，需在24小时内处理",
                "low": "轻微异常，可在正常运维窗口处理",
            }
            return json.dumps({
                "severity": level,
                "level_description": descriptions[level],
                "matched_critical_categories": sorted(cat_set & trigger_set) if trigger_set else [],
            }, ensure_ascii=False)

    return json.dumps({"severity": "low", "level_description": "轻微异常", "matched_critical_categories": []})


@tool
def get_remediation_steps(root_cause_category: str, db_type: str) -> str:
    """Return actionable remediation steps for a known root cause category.

    Args:
        root_cause_category: One of: connection_exhaustion, lock_contention,
            storage_pressure, memory_pressure, replication_issue, slow_query,
            vacuum_bloat, crash_recovery.
        db_type: 'mysql' or 'postgresql' (used to tailor DB-specific commands).

    Returns JSON with keys: immediate, short_term, long_term (each a list of steps).
    """
    steps = _REMEDIATION_DB.get(root_cause_category)
    if not steps:
        available = list(_REMEDIATION_DB.keys())
        return json.dumps({
            "error": f"Unknown category '{root_cause_category}'",
            "available_categories": available,
        })
    return json.dumps(steps, ensure_ascii=False, indent=2)


def create_diagnosis_engine_subagent() -> SubAgent:
    return SubAgent(
        name="diagnosis-engine",
        description=(
            "Synthesizes all analysis results to produce the final root cause diagnosis. "
            "Assesses severity, retrieves remediation steps for identified root causes, "
            "and generates the full structured Markdown analysis report when requested."
        ),
        system_prompt=load_prompt("diagnosis_engine.md"),
        tools=[assess_severity, get_remediation_steps],
    )
