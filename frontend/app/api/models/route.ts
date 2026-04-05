/**
 * GET /api/models – 백엔드에서 선택 가능한 LLM 모델 목록 반환
 */
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/v1/models`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return new Response(JSON.stringify({ error: "Models fetch failed" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      });
    }
    const data = await res.json();
    const models: string[] = data?.data?.models ?? [];
    return Response.json({ models });
  } catch (err) {
    console.error("[/api/models]", err);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
