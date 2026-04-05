"use client";

/**
 * FE-HIS-02: 대화 CRUD – New + Rename + Archive
 * FE-HIS-04: 검색 필터 – SearchContext 에서 받은 query 로 title 필터링
 */

import { createContext, useContext, useRef, useState, type FC } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AssistantIf,
  ThreadListItemMorePrimitive,
  ThreadListItemPrimitive,
  ThreadListPrimitive,
  useAui,
  useAuiState,
} from "@assistant-ui/react";
import {
  ArchiveIcon,
  CheckIcon,
  MoreHorizontalIcon,
  PencilIcon,
  PlusIcon,
} from "lucide-react";
import { useSessionStore } from "@/stores/session-store";
import { sessionsApi } from "@/lib/api-client";

// ── 검색어 컨텍스트 (threadlist-sidebar 에서 주입) ─────────────────────
const SearchContext = createContext("");
export const SearchProvider = SearchContext.Provider;
function useSearch() {
  return useContext(SearchContext);
}

// ── 새 스레드 한 줄 (라이브러리는 newThreadId를 threadIds에 넣지 않아서 수동 표시) ──
const NewThreadRow: FC = () => {
  const aui = useAui();
  const threadIds = useAuiState((s) => s.threads.threadIds);
  const newThreadId = useAuiState((s) => s.threads.newThreadId);
  const mainThreadId = useAuiState((s) => s.threads.mainThreadId);
  if (!newThreadId || threadIds.includes(newThreadId)) return null;
  const isActive = mainThreadId === newThreadId;
  return (
    <button
      type="button"
      onClick={() => aui.threads().switchToThread(newThreadId)}
      className="aui-thread-list-item group flex h-9 w-full cursor-pointer items-center rounded-lg px-3 text-start text-sm transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none data-[active=true]:bg-muted"
      data-active={isActive ? "true" : undefined}
    >
      <span className="min-w-0 flex-1 truncate text-muted-foreground">
        New Chat
      </span>
    </button>
  );
};

// ── 루트 ──────────────────────────────────────────────────────────────────
export const ThreadList: FC = () => (
  <ThreadListPrimitive.Root className="aui-root aui-thread-list-root flex flex-col gap-1">
    <ThreadListNew />
    <AssistantIf condition={({ threads }) => threads.isLoading}>
      <ThreadListSkeleton />
    </AssistantIf>
    <AssistantIf condition={({ threads }) => !threads.isLoading}>
      <NewThreadRow />
      <ThreadListPrimitive.Items components={{ ThreadListItem }} />
    </AssistantIf>
  </ThreadListPrimitive.Root>
);

const ThreadListNew: FC = () => (
  <ThreadListPrimitive.New asChild>
    <Button
      variant="outline"
      className="aui-thread-list-new h-9 justify-start gap-2 rounded-lg px-3 text-sm hover:bg-muted data-active:bg-muted"
    >
      <PlusIcon className="size-4" />
      New Thread
    </Button>
  </ThreadListPrimitive.New>
);

const ThreadListSkeleton: FC = () => (
  <div className="flex flex-col gap-1">
    {Array.from({ length: 5 }, (_, i) => (
      <div key={i} role="status" aria-label="Loading" className="flex h-9 items-center px-3">
        <Skeleton className="h-4 w-full" />
      </div>
    ))}
  </div>
);

// ── 아이템 ────────────────────────────────────────────────────────────────
const ThreadListItem: FC = () => {
  const searchQuery = useSearch();
  const { customTitles, setCustomTitle, threadSessions } = useSessionStore();
  const [renaming, setRenaming] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // 각 row는 threadListItem 컨텍스트를 우선 사용하고,
  // 혹시 없으면 fallback 으로 현재 thread 정보를 사용한다.
  const threadId: string = useAuiState(
    (s: any) => s.threadListItem?.id ?? s.thread?.id ?? ""
  );
  const autoTitle: string = useAuiState(
    (s: any) => s.threadListItem?.title ?? s.thread?.title ?? "New Chat"
  );
  const displayTitle = customTitles[threadId] || autoTitle;

  // FE-HIS-04: 검색 필터
  if (searchQuery && !displayTitle.toLowerCase().includes(searchQuery.toLowerCase())) {
    return null;
  }

  const startRename = () => {
    setInputVal(displayTitle);
    setRenaming(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const commitRename = async () => {
    const trimmed = inputVal.trim();
    if (trimmed && trimmed !== displayTitle) {
      setCustomTitle(threadId, trimmed);
      const sessionId = threadSessions[threadId];
      if (sessionId) {
        sessionsApi.update(sessionId, { title: trimmed }).catch(console.error);
      }
    }
    setRenaming(false);
  };

  return (
    <ThreadListItemPrimitive.Root className="aui-thread-list-item group flex h-9 items-center gap-2 rounded-lg transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none data-active:bg-muted">
      {renaming ? (
        <div className="flex flex-1 items-center gap-1 px-2">
          <Input
            ref={inputRef}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitRename();
              if (e.key === "Escape") setRenaming(false);
            }}
            onBlur={commitRename}
            className="h-6 flex-1 border-0 bg-transparent p-0 text-sm focus-visible:ring-0"
          />
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0"
            onMouseDown={(e) => { e.preventDefault(); commitRename(); }}
          >
            <CheckIcon className="size-3" />
          </Button>
        </div>
      ) : (
        <ThreadListItemPrimitive.Trigger className="aui-thread-list-item-trigger flex h-full min-w-0 flex-1 items-center truncate px-3 text-start text-sm">
          {displayTitle}
        </ThreadListItemPrimitive.Trigger>
      )}
      {!renaming && <ThreadListItemMore onRename={startRename} />}
    </ThreadListItemPrimitive.Root>
  );
};

// ── 컨텍스트 메뉴 ─────────────────────────────────────────────────────────
const ThreadListItemMore: FC<{ onRename: () => void }> = ({ onRename }) => (
  <ThreadListItemMorePrimitive.Root>
    <ThreadListItemMorePrimitive.Trigger asChild>
      <Button
        variant="ghost"
        size="icon"
        className="aui-thread-list-item-more mr-2 size-7 p-0 opacity-0 transition-opacity group-hover:opacity-100 data-[state=open]:bg-accent data-[state=open]:opacity-100 group-data-active:opacity-100"
      >
        <MoreHorizontalIcon className="size-4" />
        <span className="sr-only">More options</span>
      </Button>
    </ThreadListItemMorePrimitive.Trigger>
    <ThreadListItemMorePrimitive.Content
      side="bottom"
      align="start"
      className="aui-thread-list-item-more-content z-50 min-w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
    >
      <ThreadListItemMorePrimitive.Item
        className="aui-thread-list-item-more-item flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground"
        onSelect={onRename}
      >
        <PencilIcon className="size-4" />
        Rename
      </ThreadListItemMorePrimitive.Item>
      <ThreadListItemPrimitive.Archive asChild>
        <ThreadListItemMorePrimitive.Item className="aui-thread-list-item-more-item flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground">
          <ArchiveIcon className="size-4" />
          Archive
        </ThreadListItemMorePrimitive.Item>
      </ThreadListItemPrimitive.Archive>
    </ThreadListItemMorePrimitive.Content>
  </ThreadListItemMorePrimitive.Root>
);
