import json
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage

from app.agents.agent_factory import get_agent
from app.core.config import settings

_MAX_LOG_LINES = 5000


def _read_log_content(log_filepath: str) -> str:
    path = Path(log_filepath)
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) > _MAX_LOG_LINES:
        lines = lines[-_MAX_LOG_LINES:]
    return "\n".join(lines)


def _get_last_ai_message(result: dict) -> str:
    messages = result.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "ai":
            if isinstance(msg.content, str):
                return msg.content
            if isinstance(msg.content, list):
                texts = [b["text"] for b in msg.content if isinstance(b, dict) and b.get("type") == "text"]
                return "\n".join(texts)
    return "分析完成，但未获取到有效响应。"


def chat(
    session_id: str,
    user_message: str,
    log_filepath: Optional[str] = None,
    log_filename: Optional[str] = None,
    db_diagnostics: Optional[dict] = None,
    is_first_message: bool = False,
) -> str:
    agent, _ = get_agent()
    config = {"configurable": {"thread_id": session_id}}

    files: dict = {}

    if is_first_message and log_filepath:
        log_content = _read_log_content(log_filepath)
        if log_content:
            name = log_filename or Path(log_filepath).name
            files[f"/logs/{name}"] = {"content": log_content, "encoding": "utf-8"}

    if is_first_message and db_diagnostics:
        files["/diagnostics/db_diagnostics.json"] = {
            "content": json.dumps(db_diagnostics, ensure_ascii=False, indent=2, default=str),
            "encoding": "utf-8",
        }

    state: dict = {"messages": [HumanMessage(content=user_message)]}
    if files:
        state["files"] = files

    result = agent.invoke(state, config)
    return _get_last_ai_message(result)


def generate_report(session_id: str) -> str:
    report_prompt = (
        "请现在生成完整的故障根因分析报告。"
        "调用 diagnosis-engine 子智能体，基于本次会话中收集到的所有信息，"
        "输出包含执行摘要、根因分析、故障时间线、修复建议的完整 Markdown 报告。"
    )
    agent, _ = get_agent()
    config = {"configurable": {"thread_id": session_id}}
    state = {"messages": [HumanMessage(content=report_prompt)]}
    result = agent.invoke(state, config)
    return _get_last_ai_message(result)
