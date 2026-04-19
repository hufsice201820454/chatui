"""LangGraph StateGraph 정의 - Code Review AI Agent 워크플로우

흐름:
  START
    └─► classify_and_validate
          ├─► [validation_message] ─► END
          └─► fetch_issues
                ├─► [validation_message] ─► END  (API 오류 / 이슈 0건)
                └─► extract_code_context         (Neo4j 오류 시 빈 컨텍스트로 계속)
                      └─► analyze_and_respond
                            └─► ask_cube_channel  ← interrupt (Human-in-the-loop)
                                  ├─► [cube_channel 있음] ─► send_to_cube ─► END
                                  └─► [cube_channel 없음] ─► END

Human-in-the-loop:
  - MemorySaver 체크포인터로 그래프 상태 유지
  - ask_cube_channel 노드에서 interrupt() 호출
  - main.py에서 Command(resume=<채널번호>) 로 재개
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState
from agent.nodes import (
    classify_and_validate,
    fetch_issues,
    extract_code_context,
    analyze_and_respond,
    ask_cube_channel,
    send_to_cube,
)


def _route_on_validation(state: AgentState) -> str:
    """validation_message 유무로 END / 다음 노드를 결정하는 공통 라우터."""
    return "stop" if state.get("validation_message") else "continue"


def _route_on_channel(state: AgentState) -> str:
    """cube_channel 유무로 Cube 전송 / END를 결정하는 라우터."""
    return "send" if state.get("cube_channel") else "skip"


def build_graph(checkpointer=None) -> StateGraph:
    """Code Review AI Agent LangGraph를 빌드합니다."""
    graph = StateGraph(AgentState)

    graph.add_node("classify_and_validate", classify_and_validate)
    graph.add_node("fetch_issues", fetch_issues)
    graph.add_node("extract_code_context", extract_code_context)
    graph.add_node("analyze_and_respond", analyze_and_respond)
    graph.add_node("ask_cube_channel", ask_cube_channel)
    graph.add_node("send_to_cube", send_to_cube)

    # START → Node1
    graph.add_edge(START, "classify_and_validate")

    # Node1 → 검증 실패 END / Node2
    graph.add_conditional_edges(
        "classify_and_validate",
        _route_on_validation,
        {"stop": END, "continue": "fetch_issues"},
    )

    # Node2 → 오류/0건 END / Node3
    graph.add_conditional_edges(
        "fetch_issues",
        _route_on_validation,
        {"stop": END, "continue": "extract_code_context"},
    )

    # Node3 → Node4 (Neo4j 오류는 빈 컨텍스트로 계속)
    graph.add_edge("extract_code_context", "analyze_and_respond")

    # Node4 → Node5 (interrupt)
    graph.add_edge("analyze_and_respond", "ask_cube_channel")

    # Node5 → 채널 입력 시 Node6 / 건너뜀 시 END
    graph.add_conditional_edges(
        "ask_cube_channel",
        _route_on_channel,
        {"send": "send_to_cube", "skip": END},
    )

    # Node6 → END
    graph.add_edge("send_to_cube", END)

    return graph.compile(checkpointer=checkpointer)


# MemorySaver 체크포인터 (interrupt 동작에 필수)
_checkpointer = MemorySaver()
compiled_graph = build_graph(checkpointer=_checkpointer)
