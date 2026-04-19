"""SonarQube MCP Server - FastMCP 기반 SonarQube REST API 연동"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from mcp.server.fastmcp import FastMCP
from config.settings import SONARQUBE_URL, SONARQUBE_TOKEN

mcp = FastMCP("sonarqube")

def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {SONARQUBE_TOKEN}"}

@mcp.tool()
def sonarqube_get_issues(project_key: str, created_after: str) -> dict:
    """
    SonarQube에서 특정 프로젝트의 이슈 목록을 조회합니다.

    Args:
        project_key: SonarQube 프로젝트 키
        created_after: 조회 시작 일시 (ISO 8601 형식, 예: 2024-01-01T00:00:00+0000)

    Returns:
        이슈 목록 (component, line, severity, rule, message 포함)
    """
    url = f"{SONARQUBE_URL}/api/issues/search"
    params = {
        "componentKeys": project_key,
        "createdAfter": created_after,
        "resolved": "false",
        "ps": 500,
        "additionalFields": "rules,comments",
    }

    try:
        response = requests.get(url, params=params, headers=_auth_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        issues = []
        for issue in data.get("issues", []):
            issues.append({
                "key": issue.get("key", ""),
                "rule": issue.get("rule", ""),
                "severity": issue.get("severity", ""),
                "component": issue.get("component", ""),
                "project": issue.get("project", ""),
                "line": issue.get("line", 0),
                "message": issue.get("message", ""),
                "type": issue.get("type", ""),
                "effort": issue.get("effort", ""),
                "debt": issue.get("debt", ""),
                "status": issue.get("status", ""),
            })

        return {
            "total": data.get("total", 0),
            "issues": issues,
            "project_key": project_key,
            "created_after": created_after,
        }

    except requests.exceptions.ConnectionError:
        return {
            "error": f"SonarQube 서버({SONARQUBE_URL})에 연결할 수 없습니다.",
            "issues": [],
            "total": 0,
        }
    except requests.exceptions.HTTPError as e:
        return {
            "error": f"SonarQube API 오류: {e.response.status_code} - {e.response.text}",
            "issues": [],
            "total": 0,
        }
    except Exception as e:
        return {"error": str(e), "issues": [], "total": 0}

@mcp.tool()
def sonarqube_get_rule(rule_key: str) -> dict:
    """
    SonarQube에서 특정 Rule의 상세 정보를 조회합니다.

    Args:
        rule_key: SonarQube Rule 키 (예: java:S1481)

    Returns:
        규칙 이름, 설명, 교정 방법, 태그 등
    """
    url = f"{SONARQUBE_URL}/api/rules/show"
    params = {"key": rule_key}

    try:
        response = requests.get(url, params=params, headers=_auth_headers(), timeout=30)
        response.raise_for_status()
        data = response.json()

        rule = data.get("rule", {})
        return {
            "key": rule.get("key", ""),
            "name": rule.get("name", ""),
            "severity": rule.get("severity", ""),
            "type": rule.get("type", ""),
            "description": rule.get("htmlDesc", ""),
            "remediation_function": rule.get("remFnType", ""),
            "remediation_gap": rule.get("remFnGapMultiplier", ""),
            "tags": rule.get("tags", []),
            "lang_name": rule.get("langName", ""),
        }

    except requests.exceptions.ConnectionError:
        return {"error": f"SonarQube 서버({SONARQUBE_URL})에 연결할 수 없습니다.", "key": rule_key}
    except requests.exceptions.HTTPError as e:
        return {"error": f"Rule 조회 실패: {e.response.status_code}", "key": rule_key}
    except Exception as e:
        return {"error": str(e), "key": rule_key}

if __name__ == "__main__":
    mcp.run(transport="stdio")

