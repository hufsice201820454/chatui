/**
 * /api/agent/chat/resume
 *
 * POST { thread_id, action, edited? }
 * → FastAPI POST /api/v1/agent/chat/resume 프록시
 */
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND}/api/v1/agent/chat/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      return new Response(`Backend error: ${res.status}`, { status: 502 });
    }

    const data = await res.json();
    return Response.json(data);
  } catch (err) {
    console.error("[/api/agent/chat/resume]", err);
    return Response.json({ error: "Internal server error" }, { status: 500 });
  }
}
