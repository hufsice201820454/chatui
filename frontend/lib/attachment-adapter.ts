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
