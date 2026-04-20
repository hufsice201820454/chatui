"""노드 3: Neo4j GraphDB 코드 컨텍스트 추출

오류 처리:
  - Neo4j 연결 오류  : 오류 로그 기록 후 code_contexts를 빈 목록으로 설정,
                       Node 4(LLM 분석)는 이슈 정보만으로 계속 진행
  - Neo4j 매핑 실패  : 해당 이슈의 code_context를 None으로 설정,
                       LLM은 이슈 정보만으로 해당 이슈 분석
"""
import logging

from agent.state import AgentState
from agent.nodes.helpers import call_mcp

logger = logging.getLogger(__name__)

_NEO4J_SERVER = "../../../../mcp_service/tools/neo4j_server.py"


def _is_connection_error(result: dict) -> bool:
    """Neo4j 연결 오류 여부를 판단합니다."""
    error_msg = result.get("error", "")
    return any(keyword in str(error_msg).lower() for keyword in (
        "serviceunavailable", "connection", "refused", "timeout", "bolt",
    ))


def extract_code_context(state: AgentState) -> AgentState:
    """
    Neo4j MCP Tool을 통해 이슈별 소스파일/라인 기반 코드 컨텍스트를 추출합니다.
    """
    issues = state.get("issues", [])
    code_contexts = []

    for issue in issues:
        issue_key = issue.get("key", "")
        component = issue.get("component", "")
        line = issue.get("line", 0)

        # component 형식: project_key:src/main/java/com/example/Foo.java
        file_path = component.split(":", 1)[1] if ":" in component else component

        try:
            result = call_mcp(
                _NEO4J_SERVER,
                "neo4j_get_code_context",
                {"file_path": file_path, "line_number": line},
            )
        except BaseException as e:
            # ExceptionGroup(anyio TaskGroup) 내부의 실제 원인을 꺼내 로그
            inner = e
            while hasattr(inner, "exceptions") and getattr(inner, "exceptions", None):
                inner = inner.exceptions[0]
            # Neo4j 연결 자체가 불가능한 경우 — 이후 이슈도 조회 불가이므로 루프 중단
            logger.error(
                "[Node3] Neo4j 연결 오류 — 코드 컨텍스트 없이 분석을 진행합니다. "
                "원인: %s: %s",
                type(inner).__name__, inner,
            )
            # 남은 이슈들도 None 컨텍스트로 채워 Node4로 전달
            code_contexts.append({"issue_key": issue_key, "found": False, "context": None})
            for remaining in issues[issues.index(issue) + 1:]:
                code_contexts.append({
                    "issue_key": remaining.get("key", ""),
                    "found": False,
                    "context": None,
                })
            return {**state, "code_contexts": code_contexts}

        # Neo4j 연결 오류 (MCP 서버가 오류를 dict로 반환한 경우)
        if "error" in result and _is_connection_error(result):
            logger.error(
                "[Node3] Neo4j 연결 오류 — 코드 컨텍스트 없이 분석을 진행합니다. 오류: %s",
                result["error"],
            )
            code_contexts.append({"issue_key": issue_key, "found": False, "context": None})
            for remaining in issues[issues.index(issue) + 1:]:
                code_contexts.append({
                    "issue_key": remaining.get("key", ""),
                    "found": False,
                    "context": None,
                })
            return {**state, "code_contexts": code_contexts}

        # Neo4j 매핑 실패 (노드를 찾지 못한 경우) — 해당 이슈만 None, 계속 진행
        if "error" in result or not result.get("found", True):
            logger.warning(
                "[Node3] 코드 컨텍스트 매핑 실패 — issue: %s, file: %s, line: %d. "
                "이슈 정보만으로 분석합니다.",
                issue_key, file_path, line,
            )
            code_contexts.append({"issue_key": issue_key, "found": False, "context": None})
            continue

        result["issue_key"] = issue_key
        code_contexts.append(result)

    return {**state, "code_contexts": code_contexts}
