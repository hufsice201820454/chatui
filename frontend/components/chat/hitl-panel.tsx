"use client";

/**
 * HitlPanel – ITSM Agent HITL (Human-in-the-Loop) 검토 UI (버튼 영역만)
 *
 * 동작:
 * - hitlState.status === "interrupted" 이면 버튼 표시
 * - resume 후 interrupted 반복 가능 (최대 3회 reject)
 * - completed 이후 서버-사이드 hitlStateMap 정리
 *
 * 초안/최종 응대문 말풍선은 thread.tsx HitlMessages 에서 렌더링.
 */

import { useState, useEffect, type FC } from "react";
import { useSessionStore } from "@/stores/session-store";
import { Button } from "@/components/ui/button";
import { CheckIcon, PencilIcon, XIcon, Loader2Icon } from "lucide-react";

interface HitlPanelProps {
  /** AUI thread_id (서버-사이드 Map 정리에 사용) */
  auiThreadId: string;
}

export const HitlPanel: FC<HitlPanelProps> = ({ auiThreadId }) => {
  const { hitlState, setHitlInterrupted, setHitlCompleted, addHitlResumeMessage } =
    useSessionStore();

  const [loading, setLoading] = useState(false);
  const [uiMode, setUiMode] = useState<"buttons" | "edit" | "reject">("buttons");
  const [editText, setEditText] = useState("");
  const [rejectReason, setRejectReason] = useState("");

  // hitlState가 새로운 스레드로 바뀌면 UI 초기화
  const hitlThreadId = hitlState?.thread_id;
  useEffect(() => {
    setUiMode("buttons");
    setEditText("");
    setRejectReason("");
  }, [hitlThreadId]);

  if (!hitlState) return null;

  const isInterrupted = hitlState.status === "interrupted";

  const resume = async (
    action: "approve" | "edit" | "reject",
    edited?: string,
  ) => {
    setLoading(true);
    setUiMode("buttons");
    try {
      const res = await fetch("/api/chat/hitl/resume", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: hitlState.thread_id,
          action,
          ...(edited !== undefined ? { edited } : {}),
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      // SSE 스트림 파싱
      const reader = res.body?.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let finalText = "";
      let newDraft = "";
      let newThreadId = hitlState.thread_id;
      let rejectCount = hitlState.reject_count ?? 0;
      let isInterrupted = false;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop() ?? "";
          for (const part of parts) {
            for (const line of part.split("\n")) {
              if (!line.startsWith("data: ")) continue;
              try {
                const event = JSON.parse(line.slice(6)) as Record<string, unknown>;
                if (event.type === "text") {
                  finalText += (event.content as string) ?? "";
                } else if (event.type === "hitl_request") {
                  isInterrupted = true;
                  newDraft = (event.draft_response as string) ?? "";
                  newThreadId = (event.thread_id as string) ?? newThreadId;
                  rejectCount = (event.reject_count as number) ?? rejectCount + 1;
                }
              } catch { /* 파싱 실패 무시 */ }
            }
          }
        }
      }

      if (isInterrupted) {
        addHitlResumeMessage({ type: "draft", content: newDraft });
        setHitlInterrupted({
          thread_id: newThreadId,
          draft_response: newDraft,
          final_response: "",
          reject_count: rejectCount,
        });
      } else {
        setHitlCompleted(finalText);
        if (auiThreadId) {
          fetch(
            `/api/hitl-state?thread_id=${encodeURIComponent(auiThreadId)}`,
            { method: "DELETE" },
          ).catch(() => {});
        }
      }
    } catch (err) {
      console.error("[HitlPanel] resume error:", err);
    } finally {
      setLoading(false);
      setEditText("");
      setRejectReason("");
    }
  };

  return (
    <div className="mx-auto w-full max-w-[var(--thread-max-width,44rem)] space-y-2 px-2 pb-2">
      {/* HITL 액션 영역 */}
      {isInterrupted && (
        <div className="rounded-xl border bg-background p-3 shadow-sm space-y-2">
          <p className="text-xs text-muted-foreground">
            위 초안을 검토하고 처리 방법을 선택하세요.
            {hitlState.reject_count > 0 && (
              <span className="ml-1 text-amber-500">
                (거부 {hitlState.reject_count}/3회)
              </span>
            )}
          </p>

          {uiMode === "buttons" && (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={loading}
                onClick={() => resume("approve")}
                className="gap-1.5"
              >
                {loading ? (
                  <Loader2Icon className="size-3.5 animate-spin" />
                ) : (
                  <CheckIcon className="size-3.5" />
                )}
                승인
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={loading}
                onClick={() => {
                  setEditText(hitlState.draft_response);
                  setUiMode("edit");
                }}
                className="gap-1.5"
              >
                <PencilIcon className="size-3.5" />
                편집
              </Button>
              <Button
                size="sm"
                variant="destructive"
                disabled={loading}
                onClick={() => setUiMode("reject")}
                className="gap-1.5"
              >
                <XIcon className="size-3.5" />
                거부
              </Button>
            </div>
          )}

          {uiMode === "edit" && (
            <div className="space-y-2">
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                disabled={loading}
                rows={4}
                className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
                placeholder="수정된 응대문을 입력하세요..."
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={loading || !editText.trim()}
                  onClick={() => resume("edit", editText)}
                  className="gap-1.5"
                >
                  {loading && <Loader2Icon className="size-3.5 animate-spin" />}
                  제출
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={() => setUiMode("buttons")}
                >
                  취소
                </Button>
              </div>
            </div>
          )}

          {uiMode === "reject" && (
            <div className="space-y-2">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                disabled={loading}
                placeholder="거부 사유 입력 (선택사항)"
                className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={loading}
                  onClick={() =>
                    resume("reject", rejectReason || undefined)
                  }
                  className="gap-1.5"
                >
                  {loading && <Loader2Icon className="size-3.5 animate-spin" />}
                  거부 확정
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={loading}
                  onClick={() => setUiMode("buttons")}
                >
                  취소
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

    </div>
  );
};
