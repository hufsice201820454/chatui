# PDF/Word/Excel 첨부·드래그앤드롭 변경사항 정리

## 1) 수정/추가된 파일 절대 경로

| 구분 | 절대 경로 |
|------|-----------|
| **신규** | `c:\workspace\AI\chatui\frontend\lib\attachment-adapter.ts` |
| **수정** | `c:\workspace\AI\chatui\frontend\app\assistant.tsx` |

---

## 2) 파일별 수정 위치 + 변경 전/후 코드

### (1) `c:\workspace\AI\chatui\frontend\lib\attachment-adapter.ts`

**구분:** 신규 파일

**변경 전:** (해당 없음 – 신규 추가)

**변경 후:** (파일 전체)

```ts
"use client";

import type { AttachmentAdapter } from "@assistant-ui/react";
import { generateId } from "ai";

const getFileDataURL = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(file);
  });

/**
 * PDF, Word(.docx), Excel(.xlsx) 및 기존 이미지/텍스트를 허용하는 첨부 어댑터.
 * 드래그앤드롭 및 파일 첨부 버튼에서 사용되는 accept 값에 문서 MIME을 포함한다.
 */
export const extendedAttachmentAdapter: AttachmentAdapter = {
  accept:
    "image/*, text/plain, text/html, text/markdown, text/csv, text/xml, text/json, text/css, application/pdf, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  async add({ file }) {
    return {
      id: generateId(),
      type: file.type.startsWith("image/") ? "image" : "file",
      name: file.name,
      file,
      contentType: file.type,
      content: [],
      status: { type: "requires-action", reason: "composer-send" },
    };
  },
  async send(attachment) {
    return {
      ...attachment,
      status: { type: "complete" },
      content: [
        {
          type: "file",
          mimeType: attachment.contentType ?? "",
          filename: attachment.name,
          data: await getFileDataURL(attachment.file),
        },
      ],
    };
  },
  async remove() {
    // noop
  },
};
```

---

### (2) `c:\workspace\AI\chatui\frontend\app\assistant.tsx`

#### 수정 1 – import 추가 (라인 24~25)

**수정 라인:** 24 ~ 25 (추가)

**변경 전:**

```ts
import { setPendingChatImages, getAndClearPendingChatImages } from "@/lib/pending-chat-images";
import { useEffect } from "react";
```

**변경 후:**

```ts
import { setPendingChatImages, getAndClearPendingChatImages } from "@/lib/pending-chat-images";
import { extendedAttachmentAdapter } from "@/lib/attachment-adapter";
import { useEffect } from "react";
```

---

#### 수정 2 – useChatRuntime에 adapters 추가 (라인 213~217)

**수정 라인:** 216 (추가)

**변경 전:**

```ts
  const runtime = useChatRuntime({
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    toCreateMessage: toCreateMessageWithFileParts,
    transport: new AssistantChatTransport({
```

**변경 후:**

```ts
  const runtime = useChatRuntime({
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    toCreateMessage: toCreateMessageWithFileParts,
    adapters: { attachments: extendedAttachmentAdapter },
    transport: new AssistantChatTransport({
```

---

## 변경 요약

- **attachment-adapter.ts**: PDF(`application/pdf`), Word(.docx), Excel(.xlsx) MIME을 `accept`에 포함한 `extendedAttachmentAdapter`를 신규 추가.
- **assistant.tsx**: 해당 어댑터를 import하고 `useChatRuntime`의 `adapters.attachments`로 지정하여, 채팅에서 PDF/Word/Excel 파일 선택 및 드래그앤드롭 첨부가 가능하도록 함.
