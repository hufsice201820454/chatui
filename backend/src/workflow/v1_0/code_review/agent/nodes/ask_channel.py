"""노드 5: Cube 채널 전송 여부 확인 (Human-in-the-loop interrupt)

LangGraph interrupt()를 사용하여 그래프 실행을 일시 중단하고
사용자로부터 Cube 채널 번호를 입력받습니다.

흐름:
  - 사용자가 채널 번호 입력 → cube_channel 설정 → send_to_cube 노드로 진행
  - 사용자가 엔터(빈 입력)  → cube_channel = None  → END
"""
import logging

from langgraph.types import interrupt

from agent.state import AgentState

logger = logging.getLogger(__name__)

_PROMPT_MESSAGE = (
    "\nCube 채널로 분석 결과를 전송할까요?\n"
    "전송을 원하시면 Cube 채널 번호를 입력해 주세요.\n"
    "(건너뛰려면 엔터를 누르세요)"
)


def ask_cube_channel(state: AgentState) -> AgentState:
    """
    분석 결과 출력 후 Cube 채널 번호 입력을 대기합니다.
    interrupt()로 그래프를 일시 중단하고, 재개 시 사용자 입력값을 받습니다.
    """
    # interrupt() 호출 → 그래프 일시 중단
    # main.py에서 Command(resume=<사용자입력>) 으로 재개
    user_input: str = interrupt(_PROMPT_MESSAGE)

    channel = user_input.strip() if user_input else None

    if channel:
        logger.info("[Node5] Cube 채널 번호 입력됨: %s", channel)
    else:
        logger.info("[Node5] Cube 전송 건너뜀")

    return {**state, "cube_channel": channel}
