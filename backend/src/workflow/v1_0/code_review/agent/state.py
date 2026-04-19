"""LangGraph AgentState 정의"""
from typing import Optional, List, Dict, Any
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # 사용자 입력
    query: str

    # 의도 분류 결과
    intent: str                        # "static_analysis" | "unknown"
    project_key: Optional[str]
    analysis_date: Optional[str]
    validation_message: Optional[str]  # 검증/오류 안내 메시지 → END 분기 조건

    # SonarQube 조회 결과
    issues: List[Dict[str, Any]]
    rules: Dict[str, Dict[str, Any]]   # rule_key → rule 상세정보

    # Neo4j 코드 컨텍스트
    code_contexts: List[Dict[str, Any]]

    # LLM 최종 분석 결과
    final_answer: str

    # Cube 채널 전송 (Human-in-the-loop)
    cube_channel: Optional[str]        # 사용자가 입력한 Cube 채널 번호
    excel_file_path: Optional[str]     # 생성된 엑셀 파일 로컬 경로
    cdn_url: Optional[str]             # CDN 업로드 후 반환된 URL
    cube_send_result: Optional[Dict[str, Any]]  # Cube 채널 전송 결과
