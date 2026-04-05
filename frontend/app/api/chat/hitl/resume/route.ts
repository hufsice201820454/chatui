/**
 * /api/chat/hitl/resume
 *
 * POST { thread_id, action, edited? }
 * → FastAPI POST /api/v1/chat/hitl/resume 프록시 (SSE 스트림 패스스루)
 */
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  try {
    const body = await req.json();

    const res = await fetch(`${BACKEND}/api/v1/chat/hitl/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      return new Response(`Backend error: ${res.status}`, { status: 502 });
    }

    // SSE 스트림을 그대로 클라이언트에 패스스루
    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    console.error("[/api/chat/hitl/resume]", err);
    return Response.json({ error: "Internal server error" }, { status: 500 });
  }
}
