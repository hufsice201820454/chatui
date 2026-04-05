"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * 클라이언트 사이드 세션 상태
 * - customTitles: thread id → 사용자가 직접 지정한 제목
 * - threadSessions: thread id → FastAPI session id
 * - searchQuery: 사이드바 검색어
 * - hitlState: ITSM Agent HITL 상태 (비-영속)
 */

export type HitlResumeMessage = {
  type: "draft" | "final";
  content: string;
};

export type HitlState = {
  /** LangGraph 체크포인터 thread_id */
  thread_id: string;
  status: "interrupted" | "completed";
  draft_response: string;
  final_response: string;
  reject_count: number;
  /** resume 이후 새로 생성된 초안/최종 말풍선 목록 (첫 초안은 @assistant-ui 메시지로 표시되므로 제외) */
  resume_messages: HitlResumeMessage[];
};

type SessionStore = {
  customTitles: Record<string, string>;
  threadSessions: Record<string, string>;
  searchQuery: string;
  /** 선택된 LLM 모델 (프론트 선택용) */
  selectedModel: string;

  /** 현재 활성 AUI thread_id (thread.runEnd / thread.initialize 이벤트에서 갱신) */
  currentAuiThreadId: string;

  /** ITSM Agent HITL 상태 (비-영속) */
  hitlState: HitlState | null;

  setCustomTitle: (threadId: string, title: string) => void;
  setThreadSession: (threadId: string, sessionId: string) => void;
  setSearchQuery: (q: string) => void;
  setSelectedModel: (model: string) => void;
  getSessionId: (threadId: string) => string | undefined;
  setCurrentAuiThreadId: (id: string) => void;

  /** HITL 상태 설정 (interrupted 단계) */
  setHitlInterrupted: (state: Omit<HitlState, "status" | "resume_messages">) => void;
  /** HITL 완료 처리 및 resume_messages에 최종 응대문 추가 */
  setHitlCompleted: (finalResponse: string) => void;
  /** resume 이후 새 초안 말풍선 추가 */
  addHitlResumeMessage: (msg: HitlResumeMessage) => void;
  /** HITL 상태 초기화 (새 채팅 시작 시) */
  clearHitlState: () => void;
};

export const useSessionStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      customTitles: {},
      threadSessions: {},
      searchQuery: "",
      selectedModel: "",
      currentAuiThreadId: "",
      hitlState: null,

      setCustomTitle: (threadId, title) =>
        set((s) => ({
          customTitles: { ...s.customTitles, [threadId]: title },
        })),

      setThreadSession: (threadId, sessionId) =>
        set((s) => ({
          threadSessions: { ...s.threadSessions, [threadId]: sessionId },
        })),

      setSearchQuery: (q) => set({ searchQuery: q }),

      setSelectedModel: (model) => set({ selectedModel: model }),

      getSessionId: (threadId) => get().threadSessions[threadId],

      setCurrentAuiThreadId: (id) => set({ currentAuiThreadId: id }),

      setHitlInterrupted: (state) =>
        set({
          hitlState: {
            ...state,
            status: "interrupted",
            resume_messages: get().hitlState?.resume_messages ?? [],
          },
        }),

      setHitlCompleted: (finalResponse) =>
        set((s) => ({
          hitlState: s.hitlState
            ? {
                ...s.hitlState,
                status: "completed",
                final_response: finalResponse,
                resume_messages: [
                  ...s.hitlState.resume_messages,
                  { type: "final", content: finalResponse },
                ],
              }
            : null,
        })),

      addHitlResumeMessage: (msg) =>
        set((s) => ({
          hitlState: s.hitlState
            ? {
                ...s.hitlState,
                resume_messages: [...s.hitlState.resume_messages, msg],
              }
            : null,
        })),

      clearHitlState: () => set({ hitlState: null }),
    }),
    {
      name: "chatui-session-store",
      // hitlState는 영속화 제외 (페이지 리로드 시 초기화)
      partialize: (s) => ({
        customTitles: s.customTitles,
        threadSessions: s.threadSessions,
        selectedModel: s.selectedModel,
        searchQuery: s.searchQuery,
      }),
    }
  )
);
