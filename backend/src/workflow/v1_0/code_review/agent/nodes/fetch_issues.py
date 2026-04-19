"""노드 2: SonarQube 이슈 목록 및 Rule 정보 조회

오류 처리:
  - SonarQube API 오류 : HTTP 상태코드와 함께 오류 로그 기록, 재시도 1회 후 → END
  - 이슈 0건 조회      : "조회된 이슈가 없습니다..." → END
  - Rule 조회 실패     : 해당 Rule 빈 정보로 대체, 분석 계속 진행
"""
import logging
import time

from agent.state import AgentState
from agent.nodes.helpers import call_mcp

logger = logging.getLogger(__name__)

_RETRY_DELAY = 2  # 재시도 대기 시간(초)


def _fetch_issues_once(project_key: str, created_after: str) -> dict:
    """SonarQube 이슈 목록을 1회 조회합니다."""
    return call_mcp(
        "../../../../mcp_service/mcp_servers/sonarqube_server.py",
        "sonarqube_get_issues",
        {"project_key": project_key, "created_after": created_after},
    )


def fetch_issues(state: AgentState) -> AgentState:
    """
    SonarQube MCP Tool을 통해 이슈 목록과 Rule 상세 정보를 조회합니다.
    """
    project_key = state["project_key"]
    analysis_date = state["analysis_date"]
    created_after = f"{analysis_date}T00:00:00+0000"

    # ── SonarQube 이슈 목록 조회 (실패 시 1회 재시도) ────────────────────────
    issues_result = _fetch_issues_once(project_key, created_after)

    if "error" in issues_result:
        logger.warning(
            "[Node2] SonarQube 조회 실패 (1차 시도) — 프로젝트: %s, 오류: %s",
            project_key, issues_result["error"],
        )
        logger.info("[Node2] %d초 후 재시도합니다.", _RETRY_DELAY)
        time.sleep(_RETRY_DELAY)

        issues_result = _fetch_issues_once(project_key, created_after)

        if "error" in issues_result:
            logger.error(
                "[Node2] SonarQube 조회 최종 실패 — 프로젝트: %s, 오류: %s",
                project_key, issues_result["error"],
            )
            return {
                **state,
                "issues": [],
                "rules": {},
                "validation_message": (
                    f"SonarQube API 오류: {issues_result['error']}\n"
                    "프로젝트 코드와 SonarQube 연결 상태를 확인해 주세요."
                ),
            }

    issues = issues_result.get("issues", [])

    # ── 이슈 0건 처리 ────────────────────────────────────────────────────────
    if not issues:
        logger.info(
            "[Node2] 조회된 이슈 없음 — 프로젝트: %s, 날짜: %s",
            project_key, analysis_date,
        )
        return {
            **state,
            "issues": [],
            "rules": {},
            "validation_message": (
                f"[{project_key}] 프로젝트에서 {analysis_date} 이후 조회된 이슈가 없습니다. "
                "프로젝트 코드와 날짜를 확인해 주세요."
            ),
        }

    logger.info("[Node2] 이슈 %d건 조회 완료 — 프로젝트: %s", len(issues), project_key)

    # ── 고유 Rule 키 추출 후 Rule 상세 조회 ──────────────────────────────────
    unique_rule_keys = list({issue["rule"] for issue in issues if issue.get("rule")})
    rules = {}
    for rule_key in unique_rule_keys:
        rule_result = call_mcp(
            "../../../../mcp_service/mcp_servers/sonarqube_server.py",
            "sonarqube_get_rule",
            {"rule_key": rule_key},
        )
        if "error" not in rule_result:
            rules[rule_key] = rule_result
        else:
            # Rule 조회 실패 시 빈 정보로 대체하고 분석 계속 진행
            logger.warning(
                "[Node2] Rule 조회 실패 [%s]: %s — 빈 정보로 대체합니다.",
                rule_key, rule_result.get("error"),
            )
            rules[rule_key] = {"key": rule_key, "name": rule_key, "description": ""}

    return {**state, "issues": issues, "rules": rules, "validation_message": None}
