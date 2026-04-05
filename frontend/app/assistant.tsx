"use client";

import { AssistantRuntimeProvider, useAuiState } from "@assistant-ui/react";
import type { AppendMessage } from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { lastAssistantMessageIsCompleteWithToolCalls } from "ai";
import type { CreateUIMessage, UIMessage, UIMessagePart } from "ai";
import { Thread } from "@/components/assistant-ui/thread";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { ThreadListSidebar } from "@/components/assistant-ui/threadlist-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { MessageSearch } from "@/components/chat/message-search";
import { useSessionStore } from "@/stores/session-store";
import { setPendingChatImages, getAndClearPendingChatImages } from "@/lib/pending-chat-images";
import { setPendingChatDocuments, getAndClearPendingChatDocuments } from "@/lib/pending-chat-documents";
import { extendedAttachmentAdapter } from "@/lib/attachment-adapter";
import { useEffect } from "react";

/**
 * 전송 시 attachment.content가 비어 있어도 attachment.file이 있으면
 * blob URL 파트를 만들어 메시지에 포함시킴 → 이후 prepareSendMessagesRequest에서 data URL로 변환해 백엔드로 전달
 */
function toCreateMessageWithFileParts<UI_MESSAGE extends UIMessage = UIMessage>(
  message: AppendMessage,
): CreateUIMessage<UI_MESSAGE> {
  const fromContent = message.content.filter((c) => c.type !== "file");
  const fromAttachments = (message.attachments ?? []).flatMap((a) => {
    if (a.content && a.content.length > 0) {
      return a.content.map((c) => ({ ...c, filename: a.name }));
    }
    if (a.file && typeof URL !== "undefined" && URL.createObjectURL) {
      return [
        {
          type: "file" as const,
          data: URL.createObjectURL(a.file),
          mimeType: a.contentType ?? "image/png",
          filename: a.name,
        },
      ];
    }
    return [];
  });
  const inputParts = [...fromContent, ...fromAttachments];

  const parts: UIMessagePart[] = inputParts.map((part: any) => {
    switch (part.type) {
      case "text":
        return { type: "text", text: part.text ?? "" };
      case "image":
        return {
          type: "file",
          url: part.image,
          ...(part.filename && { filename: part.filename }),
          mediaType: "image/png",
        };
      case "file":
        return {
          type: "file",
          url: part.data ?? part.url,
          mediaType: part.mimeType ?? "image/png",
          ...(part.filename && { filename: part.filename }),
        };
      default:
        return { type: "text", text: String(part?.text ?? "") };
    }
  });

  return {
    role: message.role ?? "user",
    parts,
    metadata: message.metadata,
  } as CreateUIMessage<UI_MESSAGE>;
}

/** blob URL을 data URL로 변환 (이미지 분석 시 서버로 전달하기 위함) */
async function blobUrlToDataUrl(blobUrl: string): Promise<string> {
  const res = await fetch(blobUrl);
  const blob = await res.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

const DOCUMENT_MIMES = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]);

/** data URL에서 mime + base64 추출 (이미지 전용) */
function parseDataUrl(dataUrl: string): { mime: string; data: string } | null {
  const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
  if (!match || !match[1].startsWith("image/")) return null;
  return { mime: match[1].trim(), data: match[2].trim() };
}

/** data URL에서 mime + base64 추출 (PDF/DOCX/XLSX 문서용) */
function parseAttachmentDataUrl(dataUrl: string): { mime: string; data: string } | null {
  const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
  if (!match || !DOCUMENT_MIMES.has(match[1].trim())) return null;
  return { mime: match[1].trim(), data: match[2].trim() };
}

type ConvertResult = {
  messages: unknown[];
  images: { mime: string; data: string }[];
  documents: { mime: string; data: string; filename?: string }[];
};

/** 메시지 배열에서 마지막 user 메시지의 file 파트 blob URL을 data URL로 치환하고, 이미지/문서 payload 목록 반환 */
async function convertBlobUrlsInMessages(messages: unknown[]): Promise<ConvertResult> {
  const empty: ConvertResult = { messages, images: [], documents: [] };
  if (!Array.isArray(messages) || messages.length === 0) return empty;
  const lastUserIndex = messages.findLastIndex((m: any) => m?.role === "user");
  if (lastUserIndex === -1) return empty;

  const out = messages.map((m, i) => {
    if (i !== lastUserIndex) return m;
    const parts = (m as any).parts ?? (m as any).content;
    if (!Array.isArray(parts)) return m;
    return { ...m, parts: [...parts] };
  });

  const lastMsg = out[lastUserIndex] as any;
  const parts = lastMsg?.parts ?? lastMsg?.content;
  if (!Array.isArray(parts)) return { ...empty, messages: out };

  const images: { mime: string; data: string }[] = [];
  const documents: { mime: string; data: string; filename?: string }[] = [];
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    if (p?.type !== "file" && p?.type !== "image") continue;
    const url = p.url ?? p.image ?? p.data;
    const mime = p.mediaType ?? p.mimeType ?? "";
    if (typeof url !== "string") continue;
    if (url.startsWith("blob:")) {
      try {
        const dataUrl = await blobUrlToDataUrl(url);
        parts[i] = { ...p, url: dataUrl, mediaType: p.mediaType ?? p.mimeType ?? "image/png" };
        const imgParsed = parseDataUrl(dataUrl);
        if (imgParsed) images.push(imgParsed);
        else {
          const docParsed = parseAttachmentDataUrl(dataUrl);
          if (docParsed) documents.push({ ...docParsed, filename: p.filename });
        }
      } catch {
        // 변환 실패 시 원본 유지
      }
    } else {
      const imgParsed = parseDataUrl(url);
      if (imgParsed) images.push(imgParsed);
      else {
        const docParsed = parseAttachmentDataUrl(url);
        if (docParsed) documents.push({ ...docParsed, filename: p.filename });
      }
    }
  }
  return { messages: out, images, documents };
}

/** Composer에 붙은 이미지 파일을 data URL로 바꿔 pending-chat-images에 넣어 둠 (전송 시 body.images로 사용) */
function SyncComposerImagesToPending() {
  const attachments = useAuiState((s: any) => (s.composer ?? s.thread?.composer)?.attachments ?? []) as { file?: File; contentType?: string }[];

  useEffect(() => {
    const imageAttachments = attachments.filter((a) => a.file && (a.contentType?.startsWith("image/") ?? true));
    if (imageAttachments.length === 0) {
      setPendingChatImages([]);
      return;
    }
    let cancelled = false;
    const run = async () => {
      const results: { mime: string; data: string }[] = [];
      for (const a of imageAttachments) {
        if (!a.file || cancelled) continue;
        try {
          const dataUrl = await new Promise<string>((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result as string);
            r.onerror = () => reject(r.error);
            r.readAsDataURL(a.file!);
          });
          const parsed = parseDataUrl(dataUrl);
          if (parsed) results.push(parsed);
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setPendingChatImages(results);
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [attachments]);

  return null;
}

/** Composer에 붙은 문서(PDF/DOCX/Excel)를 data URL로 바꿔 pending-chat-documents에 넣어 둠 */
function SyncComposerDocumentsToPending() {
  const attachments = useAuiState((s: any) => (s.composer ?? s.thread?.composer)?.attachments ?? []) as {
    file?: File;
    contentType?: string;
    name?: string;
  }[];

  useEffect(() => {
    const docAttachments = attachments.filter(
      (a) =>
        a.file &&
        a.contentType &&
        DOCUMENT_MIMES.has(a.contentType)
    );
    if (docAttachments.length === 0) {
      setPendingChatDocuments([]);
      return;
    }
    let cancelled = false;
    const run = async () => {
      const results: { mime: string; data: string; filename?: string }[] = [];
      for (const a of docAttachments) {
        if (!a.file || cancelled) continue;
        try {
          const dataUrl = await new Promise<string>((resolve, reject) => {
            const r = new FileReader();
            r.onload = () => resolve(r.result as string);
            r.onerror = () => reject(r.error);
            r.readAsDataURL(a.file!);
          });
          const parsed = parseAttachmentDataUrl(dataUrl);
          if (parsed) results.push({ ...parsed, filename: a.name });
        } catch {
          /* ignore */
        }
      }
      if (!cancelled) setPendingChatDocuments(results);
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [attachments]);

  return null;
}

// 헤더 내부 – 현재 thread id 에 매핑된 FastAPI session id 노출
function HeaderContent() {
  const { threadSessions } = useSessionStore();
  const threadId: string = useAuiState((s: any) => s.thread?.id ?? "");
  const sessionId = threadSessions[threadId];

  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
      <Breadcrumb className="flex-1">
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">ChatUI</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>AI Assistant</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      {/* FE-HIS-04: 대화 내 메시지 검색 */}
      <MessageSearch sessionId={sessionId} />
    </header>
  );
}

export const Assistant = () => {
  const { setThreadSession } = useSessionStore();

  const runtime = useChatRuntime({
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    toCreateMessage: toCreateMessageWithFileParts,
    adapters: { attachments: extendedAttachmentAdapter },
    transport: new AssistantChatTransport({
      api: "/api/chat",
      // 선택한 모델 + 이미지 blob URL → data URL 변환 후 body에 반영 (이미지 분석용)
      prepareSendMessagesRequest: async (optionsEx: any) => {
        const model = useSessionStore.getState().selectedModel;
        const { messages, images: imagesFromParts, documents: documentsFromParts } = await convertBlobUrlsInMessages(optionsEx.messages ?? []);
        let images = imagesFromParts;
        if (images.length === 0) images = getAndClearPendingChatImages();
        let documents = documentsFromParts;
        if (documents.length === 0) documents = getAndClearPendingChatDocuments();
        const body = {
          ...optionsEx.body,
          ...(model ? { model } : {}),
          id: optionsEx.id,
          messages,
          trigger: optionsEx.trigger,
          messageId: optionsEx.messageId,
          metadata: optionsEx.requestMetadata,
          ...(images.length > 0 ? { images } : {}),
          ...(documents.length > 0 ? { documents } : {}),
        };
        return { ...optionsEx, body };
      },
      // AI SDK data part (2:[...]) 수신 시 session id 저장
      onData: (data: unknown) => {
        const items = Array.isArray(data) ? data : [];
        for (const item of items) {
          if (
            item &&
            typeof item === "object" &&
            "chatui_session_id" in item &&
            "thread_id" in item
          ) {
            setThreadSession(
              String((item as any).thread_id),
              String((item as any).chatui_session_id)
            );
          }
        }
      },
    } as any),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SyncComposerImagesToPending />
      <SyncComposerDocumentsToPending />
      <SidebarProvider>
        <div className="flex h-dvh w-full pr-0.5">
          <ThreadListSidebar />
          <SidebarInset>
            <HeaderContent />
            <div className="flex-1 overflow-hidden">
              <Thread />
            </div>
          </SidebarInset>
        </div>
      </SidebarProvider>
    </AssistantRuntimeProvider>
  );
};
