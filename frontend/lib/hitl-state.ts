/**
 * 서버-사이드 HITL 상태 싱글톤
 *
 * Next.js API Route 간 메모리 공유용.
 * global 객체를 사용해 HMR(개발 모드)에서도 Map이 재생성되지 않도록 함.
 *
 * key: AUI thread_id (body.id from /api/chat)
 */

export type HitlStateEntry = {
  /** LangGraph 체크포인터 thread_id */
  thread_id: string;
  /** 현재 검토 대기 중인 초안 응대문 */
  draft_response: string;
  status: "interrupted";
  reject_count: number;
};

declare global {
  // eslint-disable-next-line no-var
  var __hitlStateMap: Map<string, HitlStateEntry> | undefined;
}

if (!global.__hitlStateMap) {
  global.__hitlStateMap = new Map<string, HitlStateEntry>();
}

export const hitlStateMap = global.__hitlStateMap;
