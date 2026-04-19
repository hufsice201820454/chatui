import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from "@/components/assistant-ui/attachment";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";
import { Reasoning, ReasoningGroup } from "@/components/assistant-ui/reasoning";
import { ToolFallback } from "@/components/assistant-ui/tool-fallback";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  SuggestionPrimitive,
  ThreadPrimitive,
  useAuiEvent,
} from "@assistant-ui/react";
import { useSessionStore } from "@/stores/session-store";
import { HitlPanel } from "@/components/chat/hitl-panel";
import { useEffect, useRef, useState } from "react";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  DownloadIcon,
  MoreHorizontalIcon,
  PencilIcon,
  RefreshCwIcon,
  SquareIcon,
} from "lucide-react";
import type { FC } from "react";

/**
 * thread.runEnd 이벤트로 런 종료를 감지해 서버-사이드 hitlStateMap을 폴링.
 * hitl 상태가 있으면 Zustand setHitlInterrupted 호출.
 *
 * NOTE: ThreadState에는 id 필드가 없어서 useAuiState(s => s.thread?.id)는
 * 항상 ""를 반환한다. 대신 thread.runEnd 이벤트 payload의 threadId를 사용한다.
 */
const HitlPoller: FC = () => {
  const { setHitlInterrupted, setCurrentAuiThreadId } = useSessionStore();
  const hitlStateRef = useRef(useSessionStore.getState().hitlState);

  // hitlState 변경 시 ref 갱신 (이벤트 클로저에서 최신 값 참조용)
  useEffect(() => {
    return useSessionStore.subscribe((s) => {
      hitlStateRef.current = s.hitlState;
    });
  }, []);

  useAuiEvent("thread.runEnd", async ({ threadId }) => {
    // 현재 thread ID를 store에 저장 (HitlPanel의 DELETE 요청에 활용)
    if (threadId) setCurrentAuiThreadId(threadId);

    // 이미 검토 대기 중(interrupted)이면 폴링 생략 (completed는 새 HITL 감지 허용)
    if (hitlStateRef.current?.status === "interrupted" || !threadId) return;

    try {
      const data = await fetch(
        `/api/hitl-state?thread_id=${encodeURIComponent(threadId)}`,
      ).then((r) => r.json());

      if (data && data.status === "interrupted") {
        setHitlInterrupted({
          thread_id: data.thread_id,
          draft_response: data.draft_response,
          final_response: "",
          reject_count: data.reject_count ?? 0,
        });
      }
    } catch {
      // 폴링 실패 무시
    }
  });

  return null;
};

/**
 * thread.initialize 이벤트로 새 채팅 감지 → HITL 상태 초기화.
 */
const ThreadChangeWatcher: FC = () => {
  const { clearHitlState, setCurrentAuiThreadId } = useSessionStore();
  const prevIdRef = useRef("");

  useAuiEvent("thread.initialize", ({ threadId }) => {
    setCurrentAuiThreadId(threadId);
    if (prevIdRef.current && prevIdRef.current !== threadId) {
      // 스레드가 바뀌면 HITL 상태 초기화
      if (useSessionStore.getState().hitlState) {
        clearHitlState();
      }
    }
    prevIdRef.current = threadId;
  });

  return null;
};

/**
 * AssistantBubble – MessagePrimitive 컨텍스트 없이 사용할 수 있는 assistant 말풍선.
 * AssistantMessage 와 동일한 CSS 구조를 사용하며 react-markdown 으로 렌더링.
 */
const AssistantBubble: FC<{ content: string }> = ({ content }) => (
  <div
    className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
    data-role="assistant"
  >
    <div className="aui-assistant-message-content aui-md wrap-break-word px-2 text-foreground leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => <h1 className="aui-md-h1 mb-2 font-semibold text-base first:mt-0 last:mb-0" {...props} />,
          h2: ({ ...props }) => <h2 className="aui-md-h2 mt-3 mb-1.5 font-semibold text-sm first:mt-0 last:mb-0" {...props} />,
          h3: ({ ...props }) => <h3 className="aui-md-h3 mt-2.5 mb-1 font-semibold text-sm first:mt-0 last:mb-0" {...props} />,
          p: ({ ...props }) => <p className="aui-md-p my-2.5 leading-normal first:mt-0 last:mb-0" {...props} />,
          ul: ({ ...props }) => <ul className="aui-md-ul my-2 ml-4 list-disc marker:text-muted-foreground [&>li]:mt-1" {...props} />,
          ol: ({ ...props }) => <ol className="aui-md-ol my-2 ml-4 list-decimal marker:text-muted-foreground [&>li]:mt-1" {...props} />,
          li: ({ ...props }) => <li className="aui-md-li leading-normal" {...props} />,
          table: ({ ...props }) => (
            <div className="aui-md-table-wrapper my-2 w-full overflow-x-auto">
              <table className="aui-md-table w-full border-separate border-spacing-0" {...props} />
            </div>
          ),
          th: ({ ...props }) => <th className="aui-md-th bg-muted px-2 py-1 text-left font-medium first:rounded-tl-lg last:rounded-tr-lg" {...props} />,
          td: ({ ...props }) => <td className="aui-md-td border-muted-foreground/20 border-b border-l px-2 py-1 text-left last:border-r" {...props} />,
          tr: ({ ...props }) => <tr className="aui-md-tr m-0 border-b p-0 first:border-t [&:last-child>td:first-child]:rounded-bl-lg [&:last-child>td:last-child]:rounded-br-lg" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  </div>
);

/**
 * HitlMessages – HITL resume_messages 를 AssistantBubble 로 뷰포트 스크롤 영역에 렌더링.
 * ViewportFooter 가 아닌 스크롤 영역에 위치해 일반 채팅 히스토리와 자연스럽게 이어짐.
 */
const HitlMessages: FC = () => {
  const { hitlState } = useSessionStore();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [hitlState?.resume_messages.length]);

  if (!hitlState?.resume_messages.length) return null;

  return (
    <>
      {hitlState.resume_messages.map((msg, i) => (
        <AssistantBubble key={i} content={msg.content} />
      ))}
      <div ref={endRef} />
    </>
  );
};

export const Thread: FC = () => {
  const { hitlState, currentAuiThreadId } = useSessionStore();
  // 패널 표시: hitlState가 있는 동안 (interrupted + completed 모두)
  const hitlVisible = !!hitlState;
  // Composer 비활성화: 검토 대기 중(interrupted)일 때만
  const hitlBlocking = hitlState?.status === "interrupted";

  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
      style={{
        ["--thread-max-width" as string]: "44rem",
      }}
    >
      <HitlPoller />
      <ThreadChangeWatcher />

      <ThreadPrimitive.Viewport
        turnAnchor="top"
        className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-hidden overflow-y-scroll scroll-smooth px-4 pt-4"
      >
        <AuiIf condition={(s) => s.thread.isEmpty}>
          <ThreadWelcome />
        </AuiIf>

        <ThreadPrimitive.Messages
          components={{
            UserMessage,
            EditComposer,
            AssistantMessage,
          }}
        />

        {/* HITL resume 메시지: 일반 assistant 말풍선으로 스크롤 영역에 렌더링 */}
        {hitlVisible && <HitlMessages />}

        <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-2 overflow-visible rounded-t-3xl bg-background pb-4 md:pb-6">
          <ThreadScrollToBottom />
          {/* HITL 액션 버튼: 검토 대기 중(interrupted)일 때만 표시 */}
          {hitlVisible && <HitlPanel auiThreadId={currentAuiThreadId} />}
          {/* Composer: 검토 대기 중일 때만 비활성화 */}
          <Composer disabled={hitlBlocking} />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const ThreadWelcome: FC = () => {
  return (
    <div className="aui-thread-welcome-root mx-auto my-auto flex w-full max-w-(--thread-max-width) grow flex-col">
      <div className="aui-thread-welcome-center flex w-full grow flex-col items-center justify-center">
        <div className="aui-thread-welcome-message flex size-full flex-col justify-center px-4">
          <h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in fill-mode-both font-semibold text-2xl duration-200">
            Hello there!
          </h1>
          <p className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in fill-mode-both text-muted-foreground text-xl delay-75 duration-200">
            How can I help you today?
          </p>
        </div>
      </div>
      <ThreadSuggestions />
    </div>
  );
};

const ThreadSuggestions: FC = () => {
  return (
    <div className="aui-thread-welcome-suggestions grid w-full @md:grid-cols-2 gap-2 pb-4">
      <ThreadPrimitive.Suggestions
        components={{
          Suggestion: ThreadSuggestionItem,
        }}
      />
    </div>
  );
};

const ThreadSuggestionItem: FC = () => {
  return (
    <div className="aui-thread-welcome-suggestion-display fade-in slide-in-from-bottom-2 @md:nth-[n+3]:block nth-[n+3]:hidden animate-in fill-mode-both duration-200">
      <SuggestionPrimitive.Trigger send asChild>
        <Button
          variant="ghost"
          className="aui-thread-welcome-suggestion h-auto w-full @md:flex-col flex-wrap items-start justify-start gap-1 rounded-2xl border px-4 py-3 text-left text-sm transition-colors hover:bg-muted"
        >
          <span className="aui-thread-welcome-suggestion-text-1 font-medium">
            <SuggestionPrimitive.Title />
          </span>
          <span className="aui-thread-welcome-suggestion-text-2 text-muted-foreground">
            <SuggestionPrimitive.Description />
          </span>
        </Button>
      </SuggestionPrimitive.Trigger>
    </div>
  );
};

const Composer: FC<{ disabled?: boolean }> = ({ disabled = false }) => {
  if (disabled) {
    return (
      <div className="mx-auto w-full max-w-(--thread-max-width) rounded-2xl border bg-muted/50 px-4 py-3 text-center text-sm text-muted-foreground">
        HITL 검토가 진행 중입니다. 위 버튼으로 처리하세요.
      </div>
    );
  }

  return (
    <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
      <ComposerPrimitive.AttachmentDropzone className="aui-composer-attachment-dropzone flex w-full flex-col rounded-2xl border border-input bg-background px-1 pt-2 outline-none transition-shadow has-[textarea:focus-visible]:border-ring has-[textarea:focus-visible]:ring-2 has-[textarea:focus-visible]:ring-ring/20 data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50">
        <ComposerAttachments />
        <ComposerPrimitive.Input
          placeholder="Send a message..."
          className="aui-composer-input mb-1 max-h-32 min-h-14 w-full resize-none bg-transparent px-4 pt-2 pb-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-0"
          rows={1}
          autoFocus
          aria-label="Message input"
        />
        <ComposerAction />
      </ComposerPrimitive.AttachmentDropzone>
    </ComposerPrimitive.Root>
  );
};

const DEFAULT_MODEL = "gpt-4o-mini";

const ComposerAction: FC = () => {
  const { selectedModel, setSelectedModel } = useSessionStore();
  const [models, setModels] = useState<string[]>([DEFAULT_MODEL]);

  useEffect(() => {
    fetch("/api/models")
      .then((r) => r.json())
      .then((d) => {
        const list = (d?.models ?? []) as string[];
        const listOrDefault = list.length > 0 ? list : [DEFAULT_MODEL];
        setModels(listOrDefault);
        if (!selectedModel) {
          setSelectedModel(listOrDefault[0]);
        }
      })
      .catch(() => {
        setModels([DEFAULT_MODEL]);
        if (!selectedModel) setSelectedModel(DEFAULT_MODEL);
      });
  }, []);

  const currentModel = selectedModel || models[0];

  return (
    <div className="aui-composer-action-wrapper relative mx-2 mb-2 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <ComposerAddAttachment />
        <select
          value={currentModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="aui-model-select h-8 min-w-[8rem] rounded-md border border-input bg-background px-2 text-xs text-foreground outline-none focus:ring-2 focus:ring-ring"
          aria-label="모델 선택"
        >
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <AuiIf condition={(s) => !s.thread.isRunning}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            tooltip="Send message"
            side="bottom"
            type="submit"
            variant="default"
            size="icon"
            className="aui-composer-send size-8 rounded-full"
            aria-label="Send message"
          >
            <ArrowUpIcon className="aui-composer-send-icon size-4" />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </AuiIf>
      <AuiIf condition={(s) => s.thread.isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <Button
            type="button"
            variant="default"
            size="icon"
            className="aui-composer-cancel size-8 rounded-full"
            aria-label="Stop generating"
          >
            <SquareIcon className="aui-composer-cancel-icon size-3 fill-current" />
          </Button>
        </ComposerPrimitive.Cancel>
      </AuiIf>
    </div>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
      data-role="assistant"
    >
      <div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
        <MessagePrimitive.Parts
          components={{
            Text: MarkdownText,
            Reasoning,
            ReasoningGroup,
            tools: { Fallback: ToolFallback },
          }}
        />
        <MessageError />
      </div>

      <div className="aui-assistant-message-footer mt-1 ml-2 flex">
        <BranchPicker />
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      autohideFloat="single-branch"
      className="aui-assistant-action-bar-root col-start-3 row-start-2 -ml-1 flex gap-1 text-muted-foreground data-floating:absolute data-floating:rounded-md data-floating:border data-floating:bg-background data-floating:p-1 data-floating:shadow-sm"
    >
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <AuiIf condition={(s) => s.message.isCopied}>
            <CheckIcon />
          </AuiIf>
          <AuiIf condition={(s) => !s.message.isCopied}>
            <CopyIcon />
          </AuiIf>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip="Refresh">
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
      <ActionBarMorePrimitive.Root>
        <ActionBarMorePrimitive.Trigger asChild>
          <TooltipIconButton
            tooltip="More"
            className="data-[state=open]:bg-accent"
          >
            <MoreHorizontalIcon />
          </TooltipIconButton>
        </ActionBarMorePrimitive.Trigger>
        <ActionBarMorePrimitive.Content
          side="bottom"
          align="start"
          className="aui-action-bar-more-content z-50 min-w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          <ActionBarPrimitive.ExportMarkdown asChild>
            <ActionBarMorePrimitive.Item className="aui-action-bar-more-item flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground">
              <DownloadIcon className="size-4" />
              Export as Markdown
            </ActionBarMorePrimitive.Item>
          </ActionBarPrimitive.ExportMarkdown>
        </ActionBarMorePrimitive.Content>
      </ActionBarMorePrimitive.Root>
    </ActionBarPrimitive.Root>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
      data-role="user"
    >
      <UserMessageAttachments />

      <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
        <div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
          <MessagePrimitive.Parts />
        </div>
        <div className="aui-user-action-bar-wrapper absolute top-1/2 left-0 -translate-x-full -translate-y-1/2 pr-2">
          <UserActionBar />
        </div>
      </div>

      <BranchPicker className="aui-user-branch-picker col-span-full col-start-1 row-start-3 -mr-1 justify-end" />
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-user-action-bar-root flex flex-col items-end"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="Edit" className="aui-user-action-edit p-4">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
      <ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-muted">
        <ComposerPrimitive.Input
          className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-foreground text-sm outline-none"
          autoFocus
        />
        <div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
          <ComposerPrimitive.Cancel asChild>
            <Button variant="ghost" size="sm">
              Cancel
            </Button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <Button size="sm">Update</Button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </MessagePrimitive.Root>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({
  className,
  ...rest
}) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn(
        "aui-branch-picker-root mr-2 -ml-2 inline-flex items-center text-muted-foreground text-xs",
        className,
      )}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="aui-branch-picker-state font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};
