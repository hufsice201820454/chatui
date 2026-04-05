"""refactor_suggest 도구 — focus별 리팩토링 제안."""

REFACTOR_SUGGEST_SYSTEM = {
    "complexity": """순환 복잡도·중첩을 줄이는 리팩토링을 제안하세요. [컨텍스트]의 메트릭과 코드 구조만 근거로
조기 반환, 메서드 추출, 정책/전략 분리 등을 한국어 단계 목록으로 작성하세요.""",
    "duplication": """중복 제거 리팩토링을 제안하세요. [컨텍스트]에 나타난 유사 호출/패턴만 근거로
공통 메서드, 템플릿 메서드, 유틸 추출을 제안하고 breaking change 가능성을 명시하세요. 한국어.""",
    "coupling": """결합도 완화를 제안하세요. [컨텍스트]의 의존·호출 관계만 사용해
인터페이스 도입, DI, 이벤트/메시지 분리 등을 한국어로 단계별 제시하세요.""",
}


def refactor_suggest_user(assembled_context: str, focus: str) -> str:
    return (
        f"[컨텍스트]\n{assembled_context}\n\n"
        f"focus={focus}\n"
        "실행 가능한 작은 단계로 나누어 제안하세요."
    )
