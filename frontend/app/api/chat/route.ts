/**
 * /api/chat  –  Next.js API Route
 *
 * 역할: AssistantChatTransport(AI SDK 포맷) ↔ FastAPI SSE 포맷 변환 프록시
 *
 * 흐름:
 *  1. AI SDK 형식 요청 수신 (messages 배열 + thread id)
 *  2. thread id → FastAPI session id 매핑 (메모리 캐시)
 *     - 최초 요청 시 FastAPI /api/v1/sessions 에서 세션 생성
 *  3. 마지막 사용자 메시지를 FastAPI SSE 엔드포인트로 전송
 *  4. FastAPI SSE 이벤트 → AI SDK 데이터 스트림으로 변환하여 응답
 *
 * FastAPI SSE 이벤트 형식:
 *   {"type":"start"}
 *   {"type":"text","content":"..."}
 *   {"type":"tool_start","name":"...","id":"..."}
 *   {"type":"tool_end","name":"...","id":"...","result":...}
 *   {"type":"end","usage":{...}}
 *   {"type":"error","message":"..."}
 *
 * 클라이언트(DefaultChatTransport)는 parseJsonEventStream + uiMessageChunkSchema 사용.
 * SSE "data: <JSON>\n\n" 형식, JSON은 text-start / text-delta / text-end / finish 등.
 */

import { hitlStateMap } from "@/lib/hitl-state";

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";

// thread id → FastAPI session id  (프로세스 메모리 – 재시작 시 초기화)
const threadSessions = new Map<string, string>();

type MessagePart = {
  type: string;
  text?: string;
  image?: string;
  url?: string;
  data?: string;
  mediaType?: string;
  mimeType?: string;
};
type AiMessage = {
  role: string;
  parts?: MessagePart[];
  content?: string | MessagePart[];
};

function extractText(msg: AiMessage): string {
  if (Array.isArray(msg.parts) && msg.parts.length > 0) {
    return msg.parts
      .filter((p) => p.type === "text")
      .map((p) => p.text ?? "")
      .join("");
  }
  const content = msg.content;
  if (!content) return "";
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return String(content);
  return content
    .filter((p) => p.type === "text")
    .map((p) => p.text ?? "")
    .join("");
}

const DOCUMENT_MIMES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]);

/** data URL "data:image/jpeg;base64,XXXX" -> { mime, data } (images only) */
function parseDataUrl(dataUrl: string): { mime: string; data: string } | null {
  const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
  if (!match || !match[1].startsWith("image/")) return null;
  return { mime: match[1].trim(), data: match[2].trim() };
}

/** data URL -> { mime, data } for PDF/DOCX/XLSX (document 분석용) */
function parseAttachmentDataUrl(dataUrl: string): { mime: string; data: string } | null {
  const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
  if (!match) return null;
  const mime = match[1].trim();
  if (!DOCUMENT_MIMES.has(mime)) return null;
  return { mime, data: match[2].trim() };
}

function extractImages(msg: AiMessage): { mime: string; data: string }[] {
  const out: { mime: string; data: string }[] = [];
  const parts = Array.isArray(msg.parts) ? msg.parts : Array.isArray(msg.content) ? msg.content : [];
  for (const p of parts) {
    const part = p as MessagePart;
    if (part.type !== "file" && part.type !== "image") continue;
    const url = part.image ?? part.url ?? part.data;
    const mime = part.mediaType ?? part.mimeType ?? "image/png";
    if (!url || typeof url !== "string") continue;
    const parsed = parseDataUrl(url);
    if (parsed) out.push(parsed);
    else if (mime.startsWith("image/") && url.startsWith("data:")) {
      const m = url.match(/;base64,(.+)$/);
      if (m) out.push({ mime, data: m[1].trim() });
    }
  }
  return out;
}

type DocumentPayload = { mime: string; data: string; filename?: string };

function extractDocuments(msg: AiMessage): DocumentPayload[] {
  const out: DocumentPayload[] = [];
  const parts = Array.isArray(msg.parts) ? msg.parts : Array.isArray(msg.content) ? msg.content : [];
  for (const p of parts) {
    const part = p as MessagePart & { filename?: string };
    if (part.type !== "file") continue;
    const url = part.url ?? part.data;
    const mime = part.mediaType ?? part.mimeType ?? "";
    if (!url || typeof url !== "string") continue;
    if (!DOCUMENT_MIMES.has(mime)) continue;
    const parsed = parseAttachmentDataUrl(url);
    if (parsed) out.push({ ...parsed, filename: part.filename ?? "" });
    else if (url.startsWith("data:")) {
      const m = url.match(/^data:([^;]+);base64,(.+)$/);
      if (m && DOCUMENT_MIMES.has(m[1].trim())) out.push({ mime: m[1].trim(), data: m[2].trim(), filename: part.filename ?? "" });
    }
  }
  return out;
}

async function getOrCreateSession(threadId: string, title: string): Promise<string> {
  const cached = threadSessions.get(threadId);
  if (cached) return cached;

  const res = await fetch(`${BACKEND}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: title.slice(0, 80) }),
  });

  if (!res.ok) throw new Error(`Session creation failed: ${res.status}`);

  const data = await res.json();
  const sessionId: string = data.data?.id;
  if (!sessionId) throw new Error("No session ID in response");

  threadSessions.set(threadId, sessionId);
  return sessionId;
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const messages: AiMessage[] = body.messages ?? [];

    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) {
      return new Response("No user message", { status: 400 });
    }

    const userText = extractText(lastUser);
    const extractedImages = extractImages(lastUser);
    const extractedDocuments = extractDocuments(lastUser);
    const images =
      Array.isArray(body.images) && body.images.length > 0
        ? (body.images as { mime: string; data: string }[])
        : extractedImages;
    const documents =
      Array.isArray(body.documents) && body.documents.length > 0
        ? (body.documents as { mime: string; data: string; filename?: string }[])
        : extractedDocuments;
    const threadId: string = body.id ?? "default";

    const sessionId = await getOrCreateSession(threadId, userText || "New Chat");

    const model = body.model as string | undefined;

    const chatBody: {
      message: string;
      model?: string;
      images?: { mime: string; data: string }[];
      documents?: { mime: string; data: string; filename?: string }[];
    } = {
      message: userText,
      ...(model ? { model } : {}),
    };
    if (images.length > 0) chatBody.images = images;
    if (documents.length > 0) chatBody.documents = documents;

    // FastAPI에 스트리밍 요청
    const fastapiRes = await fetch(
      `${BACKEND}/api/v1/chat/${sessionId}/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(chatBody),
      }
    );

    if (!fastapiRes.ok) {
      return new Response(`Backend error: ${fastapiRes.status}`, {
        status: 502,
      });
    }

    const responseHeaders: Record<string, string> = {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
      "X-Chat-Backend": "chatui-fastapi",
      "X-Request-Images-Count": String(images.length),
      "X-Request-Documents-Count": String(documents.length),
    };

    // FastAPI SSE → parseJsonEventStream(uiMessageChunkSchema) 형식: SSE "data: <JSON>\n\n"
    const encoder = new TextEncoder();
    const TEXT_PART_ID = "part_1";

    function sseLine(obj: object): string {
      return `data: ${JSON.stringify(obj)}\n\n`;
    }

    const readable = new ReadableStream({
      async start(controller) {
        // uiMessageChunkSchema: start 먼저
        controller.enqueue(encoder.encode(sseLine({ type: "start" })));

        const reader = fastapiRes.body!.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        let textStarted = false;
        let finished = false;

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buf += decoder.decode(value, { stream: true });
            const chunks = buf.split("\n\n");
            buf = chunks.pop() ?? "";

            for (const chunk of chunks) {
              for (const line of chunk.split("\n")) {
                if (!line.startsWith("data: ")) continue;
                try {
                  const event = JSON.parse(line.slice(6)) as { type: string; content?: string; message?: string; usage?: object };

                  if (event.type === "start") {
                    // 이미 위에서 start 보냄
                  } else if (event.type === "text" && event.content !== undefined) {
                    if (!textStarted) {
                      controller.enqueue(encoder.encode(sseLine({ type: "text-start", id: TEXT_PART_ID })));
                      textStarted = true;
                    }
                    controller.enqueue(encoder.encode(sseLine({ type: "text-delta", id: TEXT_PART_ID, delta: event.content })));
                  } else if (event.type === "hitl_request") {
                    // HITL interrupt: draft_response를 텍스트로 표시하고
                    // 서버-사이드 Map에 HITL 상태 저장 (프론트엔드가 polling으로 감지)
                    const draft = (event as any).draft_response ?? "";
                    const lgThreadId = (event as any).thread_id ?? threadId;
                    const rejectCount = (event as any).reject_count ?? 0;

                    if (draft) {
                      if (!textStarted) {
                        controller.enqueue(encoder.encode(sseLine({ type: "text-start", id: TEXT_PART_ID })));
                        textStarted = true;
                      }
                      controller.enqueue(encoder.encode(sseLine({ type: "text-delta", id: TEXT_PART_ID, delta: draft })));
                    }

                    // AUI thread_id(threadId)를 키로 HITL 상태 저장
                    hitlStateMap.set(threadId, {
                      thread_id: lgThreadId,
                      draft_response: draft,
                      status: "interrupted",
                      reject_count: rejectCount,
                    });
                  } else if (event.type === "end") {
                    if (textStarted) {
                      controller.enqueue(encoder.encode(sseLine({ type: "text-end", id: TEXT_PART_ID })));
                    }
                    controller.enqueue(encoder.encode(sseLine({ type: "finish-step" })));
                    controller.enqueue(encoder.encode(sseLine({ type: "finish", finishReason: "stop" })));
                    finished = true;
                  } else if (event.type === "error") {
                    controller.enqueue(encoder.encode(sseLine({ type: "error", errorText: event.message ?? String(event) })));
                  }
                } catch {
                  // SSE 파싱 실패 무시
                }
              }
            }
          }
          // 백엔드가 end 없이 끊긴 경우에만 마무리 전송 (end 받았으면 중복 전송 방지)
          if (textStarted && !finished) {
            controller.enqueue(encoder.encode(sseLine({ type: "text-end", id: TEXT_PART_ID })));
            controller.enqueue(encoder.encode(sseLine({ type: "finish-step" })));
            controller.enqueue(encoder.encode(sseLine({ type: "finish", finishReason: "stop" })));
          }
        } finally {
          controller.close();
        }
      },
    });

    return new Response(readable, {
      headers: responseHeaders,
    });
  } catch (err) {
    console.error("[/api/chat]", err);
    return new Response(
      JSON.stringify({ error: "Internal server error" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
