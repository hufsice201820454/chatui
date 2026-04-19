"""Code Review AI Agent - 터미널 채팅 인터페이스 (Human-in-the-loop)

실행 흐름:
  1. 사용자 질의 입력
  2. LangGraph 실행 → ask_cube_channel 노드에서 interrupt (일시 중단)
  3. 분석 결과 출력 + Cube 채널 번호 입력 요청
  4. 채널 번호 입력 시 → Excel 생성 → CDN 업로드(Mock) → Cube 전송(Mock)
  5. 엔터(빈 입력) 시 → 전송 없이 종료
"""
import sys
from uuid import uuid4

from langgraph.types import Command

from agent.graph import compiled_graph

BANNER = """
╔══════════════════════════════════════════════════════╗
║          Code Review AI Agent                        ║
║  SonarQube 정적분석 결과의 이슈별 원인/수정방안 분석   ║
╚══════════════════════════════════════════════════════╝
입력 형식: <프로젝트코드> <YYYY-MM-DD> 분석결과 알려줘
명령어   : /help  도움말 | /clear  화면 초기화 | /quit  종료
"""

HELP_TEXT = """
[사용 방법]
  필수 정보: 프로젝트 코드(SonarQube project key), 분석 일시(YYYY-MM-DD)

  질의 예시:
    my-project 2024-03-15 정적분석 결과 알려줘
    프로젝트 petclinic의 2024-01-01 분석결과 조회해줘

  분석 결과 컬럼:
    Project | Source File | Line | Issue Detail | Reason | Recommended Solution

  분석 후 Cube 채널 전송:
    채널 번호 입력 → Excel 생성 → CDN 업로드 → Cube 채널 전송
    엔터(빈 입력)  → 전송 없이 종료

  명령어:
    /help   이 도움말 표시
    /clear  화면 초기화
    /quit   프로그램 종료
"""

SEP = "─" * 64


def _print_sep():
    print(SEP)


def _initial_state(query: str) -> dict:
    return {
        "query": query,
        "intent": "",
        "project_key": None,
        "analysis_date": None,
        "validation_message": None,
        "issues": [],
        "rules": {},
        "code_contexts": [],
        "final_answer": "",
        "cube_channel": None,
        "excel_file_path": None,
        "cdn_url": None,
        "cube_send_result": None,
    }


def _show_analysis_result(state_values: dict) -> None:
    """분석 결과를 터미널에 출력합니다."""
    _print_sep()
    issues_count = len(state_values.get("issues", []))
    print(
        f"프로젝트: {state_values.get('project_key', '-')}  "
        f"분석일시: {state_values.get('analysis_date', '-')}  "
        f"총 이슈: {issues_count}건\n"
    )
    print(state_values.get("final_answer", ""))
    _print_sep()


def _show_send_result(state_values: dict) -> None:
    """Cube 채널 전송 결과를 출력합니다."""
    result = state_values.get("cube_send_result", {})
    _print_sep()
    if result and result.get("success"):
        print(f"✔  Cube 채널 [{result['channel']}] 전송 완료")
        print(f"   메시지 ID : {result['message_id']}")
        print(f"   CDN URL   : {state_values.get('cdn_url', '-')}")
        print(f"   Excel 파일: {state_values.get('excel_file_path', '-')}")
        print(f"   전송 시각 : {result['sent_at']}")
    elif result:
        print(f"✘  Cube 전송 실패: {result.get('error', '알 수 없는 오류')}")
    _print_sep()


def _invoke(query: str) -> None:
    """
    LangGraph를 실행하고 Human-in-the-loop (interrupt) 를 처리합니다.
    """
    print("\n분석 중...\n")

    # 세션별 고유 thread_id (MemorySaver 체크포인터에서 상태 격리)
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # ── 1단계: 그래프 실행 (ask_cube_channel 노드에서 interrupt로 일시 중단) ──
    try:
        compiled_graph.invoke(_initial_state(query), config=config)
    except Exception as e:
        print(f"[오류] {e}")
        return

    # ── 2단계: 현재 그래프 상태 확인 ─────────────────────────────────────────
    snapshot = compiled_graph.get_state(config)
    state_values = snapshot.values

    # 검증/오류로 END에 도달한 경우
    if state_values.get("validation_message"):
        _print_sep()
        print(f"⚠  {state_values['validation_message']}")
        _print_sep()
        return

    # 분석 결과가 없는 경우 (예외적 상황)
    if not state_values.get("final_answer"):
        print("분석 결과를 생성할 수 없습니다. 다시 시도해 주세요.")
        return

    # ── 3단계: 분석 결과 출력 ─────────────────────────────────────────────────
    _show_analysis_result(state_values)

    # interrupt가 없어 이미 END에 도달한 경우 (정상 종료, 전송 없음)
    if not snapshot.next:
        return

    # ── 4단계: Cube 채널 번호 입력 요청 (Human-in-the-loop) ──────────────────
    print("\nCube 채널로 분석 결과를 전송할까요?")
    print("전송을 원하시면 Cube 채널 번호를 입력해 주세요.")
    print("(건너뛰려면 엔터를 누르세요)")
    try:
        channel_input = input("Cube 채널 번호> ").strip()
    except (EOFError, KeyboardInterrupt):
        channel_input = ""

    # ── 5단계: 그래프 재개 (Command(resume=채널번호)) ─────────────────────────
    try:
        compiled_graph.invoke(Command(resume=channel_input), config=config)
    except Exception as e:
        print(f"[오류] Cube 전송 중 오류가 발생했습니다: {e}")
        return

    # ── 6단계: 전송 결과 출력 ─────────────────────────────────────────────────
    final_snapshot = compiled_graph.get_state(config)
    final_values = final_snapshot.values

    if not channel_input:
        print("\nCube 채널 전송을 건너뜁니다.")
    else:
        _show_send_result(final_values)


def main():
    print(BANNER)

    while True:
        try:
            query = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            sys.exit(0)

        if not query:
            continue

        if query == "/quit":
            print("종료합니다.")
            sys.exit(0)
        elif query == "/help":
            print(HELP_TEXT)
        elif query == "/clear":
            print("\033[2J\033[H", end="")
            print(BANNER)
        else:
            _invoke(query)


if __name__ == "__main__":
    main()
