"""Neo4j GraphDB MCP Server - FastMCP 기반 코드 컨텍스트 추출

그래프 스키마 (ast_graphdb 기준):
  노드: JavaFile, Class/Interface, Method, Field, Annotation
  관계: (JavaFile)-[:DECLARES]->(Class)
        (Class)-[:HAS_METHOD]->(Method)
        (Class)-[:HAS_FIELD]->(Field)
        (Class)-[:EXTENDS]->(Class)
        (Class)-[:IMPLEMENTS]->(Interface)
        (Class)-[:DEPENDS_ON]->(Class)
        (Method)-[:CALLS]->(Method)
        (Method)-[:ANNOTATED_WITH]->(Annotation)

주요 프로퍼티:
  JavaFile : id(=path), path, fileName, packageName
  Class    : fqn, name, packageName, filePath, lineStart, lineEnd
  Method   : id(={fqn}#{name}), name, signature, returnType, visibility,
             lineStart, lineEnd, cyclomaticComplexity, sourceCode, classFqn
"""
import sys
import os

_backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_backend_root, "src", "workflow", "v1_0", "code_review"))

from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

mcp = FastMCP("neo4j")

def _get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

@mcp.tool()
def neo4j_get_code_context(file_path: str, line_number: int) -> dict:
    """
    파일명과 라인 번호로 해당 메서드를 찾고,
    그 메서드와 연관된 메서드들(호출하는/호출받는)의 컨텍스트를 반환합니다.

    탐색 순서:
      1. JavaFile 노드에서 파일명으로 탐색
      2. DECLARES 관계로 Class 노드 도달
      3. HAS_METHOD 관계에서 lineStart <= line_number <= lineEnd 인 Method 탐색
      4. 해당 Method가 CALLS 하는 메서드 목록 조회 (outgoing)
      5. 해당 Method를 CALLS 하는 메서드 목록 조회 (incoming / callers)

    Args:
        file_path: SonarQube component 경로 (예: src/main/java/com/example/UserService.java)
        line_number: 이슈 라인 번호

    Returns:
        target_method, callees(호출하는 메서드), callers(호출받는 메서드) 포함 컨텍스트
    """
    driver = None
    try:
        driver = _get_driver()
        file_name = os.path.basename(file_path)

        with driver.session() as session:

            # ── Step 1·2·3: JavaFile → Class → Method (라인 기준) ────────────
            target = session.run(
                """
                MATCH (f:JavaFile)-[:DECLARES]->(c:Class)-[:HAS_METHOD]->(m:Method)
                WHERE (f.fileName = $file_name OR f.path CONTAINS $file_path)
                  AND m.lineStart <= $line_number
                  AND m.lineEnd   >= $line_number
                RETURN
                    f.path                   AS file_path,
                    c.fqn                    AS class_fqn,
                    c.name                   AS class_name,
                    c.packageName            AS package,
                    m.id                     AS method_id,
                    m.name                   AS method_name,
                    m.signature              AS signature,
                    m.returnType             AS return_type,
                    m.visibility             AS visibility,
                    m.isStatic               AS is_static,
                    m.lineStart              AS line_start,
                    m.lineEnd                AS line_end,
                    m.cyclomaticComplexity   AS complexity,
                    m.cognitiveComplexity    AS cognitive_complexity,
                    m.loc                    AS loc,
                    m.annotations            AS annotations,
                    m.sourceCode             AS source_code
                LIMIT 1
                """,
                file_name=file_name,
                file_path=file_path,
                line_number=line_number,
            ).single()

            if not target:
                return {
                    "file_path": file_path,
                    "line_number": line_number,
                    "found": False,
                    "message": (
                        f"'{file_name}'의 {line_number}번 라인을 포함하는 "
                        "메서드를 Neo4j에서 찾을 수 없습니다."
                    ),
                }

            method_id = target["method_id"]

            # ── Step 4: 이 메서드가 호출하는 메서드 목록 (outgoing CALLS) ─────
            callees = session.run(
                """
                MATCH (m:Method)-[:CALLS]->(callee:Method)
                WHERE m.id = $method_id
                RETURN
                    callee.id         AS method_id,
                    callee.name       AS method_name,
                    callee.classFqn   AS class_fqn,
                    callee.signature  AS signature,
                    callee.returnType AS return_type,
                    callee.sourceCode AS source_code
                LIMIT 20
                """,
                method_id=method_id,
            )
            callee_list = [
                {
                    "method_id":   r["method_id"],
                    "method_name": r["method_name"],
                    "class_fqn":   r["class_fqn"],
                    "signature":   r["signature"],
                    "return_type": r["return_type"],
                    "source_code": r["source_code"],
                }
                for r in callees
            ]

            # ── Step 5: 이 메서드를 호출하는 메서드 목록 (incoming CALLS) ─────
            callers = session.run(
                """
                MATCH (caller:Method)-[:CALLS]->(m:Method)
                WHERE m.id = $method_id
                RETURN
                    caller.id         AS method_id,
                    caller.name       AS method_name,
                    caller.classFqn   AS class_fqn,
                    caller.signature  AS signature,
                    caller.returnType AS return_type,
                    caller.sourceCode AS source_code
                LIMIT 20
                """,
                method_id=method_id,
            )
            caller_list = [
                {
                    "method_id":   r["method_id"],
                    "method_name": r["method_name"],
                    "class_fqn":   r["class_fqn"],
                    "signature":   r["signature"],
                    "return_type": r["return_type"],
                    "source_code": r["source_code"],
                }
                for r in callers
            ]

            return {
                "file_path":   file_path,
                "line_number": line_number,
                "found":       True,
                "target_method": {
                    "method_id":          method_id,
                    "method_name":        target["method_name"],
                    "signature":          target["signature"],
                    "return_type":        target["return_type"],
                    "visibility":         target["visibility"],
                    "is_static":          target["is_static"],
                    "line_start":         target["line_start"],
                    "line_end":           target["line_end"],
                    "complexity":         target["complexity"],
                    "cognitive_complexity": target["cognitive_complexity"],
                    "loc":                target["loc"],
                    "annotations":        target["annotations"],
                    "source_code":        target["source_code"],
                    "class_fqn":          target["class_fqn"],
                    "class_name":         target["class_name"],
                    "package":            target["package"],
                },
                "callees": callee_list,   # 이 메서드가 호출하는 메서드들
                "callers": caller_list,   # 이 메서드를 호출하는 메서드들
            }

    except Exception as e:
        return {
            "file_path":   file_path,
            "line_number": line_number,
            "found":       False,
            "error":       str(e),
        }
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    mcp.run(transport="stdio")

