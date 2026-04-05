"""인텐트 분류 프롬프트 템플릿."""
from langchain_core.prompts import ChatPromptTemplate

# Rule-based 분류 보조용 프롬프트 (LLM fallback 시 사용)
INTENT_SYSTEM_PROMPT = (
    "당신은 ITSM(IT Service Management) 문의 분류 전문가입니다.\n"
    "사용자 문의가 ITSM Agent가 처리해야 하는 IT 관련 문의인지 판단하세요.\n\n"
    "ITSM Agent 대상 문의 예시:\n"
    "- 계정/권한 요청 및 오류\n"
    "- 시스템/서버 장애 및 에러\n"
    "- 배치/인터페이스 오류\n"
    "- 데이터베이스 문제\n"
    "- MES/ERP 시스템 문제\n\n"
    "JSON 형식으로만 응답하세요: {\"intent\": \"agent\" or \"general\", \"confidence\": 0.0~1.0}"
)

INTENT_USER_TEMPLATE = "문의: {user_query}"

INTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", INTENT_SYSTEM_PROMPT),
    ("user", INTENT_USER_TEMPLATE),
])
