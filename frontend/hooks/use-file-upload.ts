"use client";

import { useState, useCallback } from "react";
import type { UploadedFile } from "@/lib/api-client";

// FE-FILE-03: 허용 타입 & 최대 크기
const ALLOWED_MIME = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "text/csv",
  "text/plain",
  "text/markdown",
]);
const ALLOWED_EXT = [".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"];
const MAX_SIZE_MB = 50;

export type UploadState = {
  status: "idle" | "uploading" | "done" | "error";
  progress: number; // 0-100
  result: UploadedFile | null;
  error: string | null;
};

export function useFileUpload() {
  const [state, setState] = useState<UploadState>({
    status: "idle",
    progress: 0,
    result: null,
    error: null,
  });

  const validate = (file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    const mimeOk = ALLOWED_MIME.has(file.type);
    const extOk = ALLOWED_EXT.includes(ext);
    if (!mimeOk && !extOk) {
      return `지원하지 않는 파일 형식입니다. (허용: ${ALLOWED_EXT.join(", ")})`;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      return `파일 크기가 ${MAX_SIZE_MB}MB를 초과합니다.`;
    }
    return null;
  };

  // FE-FILE-02: XMLHttpRequest로 업로드 진행률 추적
  const upload = useCallback(
    (file: File, sessionId?: string): Promise<UploadedFile> => {
      return new Promise((resolve, reject) => {
        const err = validate(file);
        if (err) {
          setState({ status: "error", progress: 0, result: null, error: err });
          reject(new Error(err));
          return;
        }

        setState({ status: "uploading", progress: 0, result: null, error: null });

        const formData = new FormData();
        formData.append("file", file);

        const url = sessionId
          ? `/backend/api/v1/files/upload?session_id=${sessionId}`
          : "/backend/api/v1/files/upload";

        const xhr = new XMLHttpRequest();
        xhr.open("POST", url);

        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            setState((prev) => ({ ...prev, progress: pct }));
          }
        });

        xhr.addEventListener("load", () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const data = JSON.parse(xhr.responseText);
              const result: UploadedFile = data.data;
              setState({ status: "done", progress: 100, result, error: null });
              resolve(result);
            } catch {
              const msg = "응답 파싱 실패";
              setState({ status: "error", progress: 0, result: null, error: msg });
              reject(new Error(msg));
            }
          } else {
            const msg = `업로드 실패: ${xhr.status}`;
            setState({ status: "error", progress: 0, result: null, error: msg });
            reject(new Error(msg));
          }
        });

        xhr.addEventListener("error", () => {
          const msg = "네트워크 오류";
          setState({ status: "error", progress: 0, result: null, error: msg });
          reject(new Error(msg));
        });

        xhr.send(formData);
      });
    },
    []
  );

  const reset = useCallback(() => {
    setState({ status: "idle", progress: 0, result: null, error: null });
  }, []);

  return { ...state, upload, reset, allowedExtensions: ALLOWED_EXT, maxSizeMB: MAX_SIZE_MB };
}
