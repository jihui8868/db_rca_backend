from pathlib import Path

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from app.agents.base import load_prompt
from app.agents.subagents.info_collector import create_info_collector_subagent
from app.agents.subagents.observability import create_observability_subagent
from app.agents.subagents.anomaly_detection import create_anomaly_detection_subagent
from app.agents.subagents.knowledge_graph import create_knowledge_graph_subagent
from app.agents.subagents.diagnosis_engine import create_diagnosis_engine_subagent
from app.core.config import settings

_agent: CompiledStateGraph | None = None
_checkpointer: InMemorySaver | None = None


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


def create_rca_agent() -> tuple[CompiledStateGraph, InMemorySaver]:
    llm = build_llm()
    checkpointer = InMemorySaver()

    subagents = [
        create_info_collector_subagent(),
        create_observability_subagent(),
        create_anomaly_detection_subagent(),
        create_knowledge_graph_subagent(),
        create_diagnosis_engine_subagent(),
    ]

    agent = create_deep_agent(
        model=llm,
        system_prompt=load_prompt("main_agent.md"),
        subagents=subagents,
        checkpointer=checkpointer,
    )
    return agent, checkpointer


def get_agent() -> tuple[CompiledStateGraph, InMemorySaver]:
    # 返回一个全局的代理,解决多个进程使用代理的问题
    global _agent, _checkpointer
    if _agent is None:
        _agent, _checkpointer = create_rca_agent()
    return _agent, _checkpointer
