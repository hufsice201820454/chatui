/**
 * /api/hitl-state
 *
 * GET  ?thread_id=X  – 해당 AUI thread의 HITL 상태 반환 (없으면 null)
 * DELETE ?thread_id=X – HITL 상태 제거 (세션 완료 후 정리)
 */
import { hitlStateMap } from "@/lib/hitl-state";

export async function GET(req: Request) {
  const threadId = new URL(req.url).searchParams.get("thread_id") ?? "";
  const state = hitlStateMap.get(threadId) ?? null;
  return Response.json(state);
}

export async function DELETE(req: Request) {
  const threadId = new URL(req.url).searchParams.get("thread_id") ?? "";
  hitlStateMap.delete(threadId);
  return Response.json({ ok: true });
}
