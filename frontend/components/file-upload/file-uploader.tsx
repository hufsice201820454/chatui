"use client";

/**
 * FE-FILE-01 드래그 앤 드롭
 * FE-FILE-02 업로드 진행 표시
 * FE-FILE-03 파일 타입 / 용량 검증
 * FE-FILE-04 멀티파일 (한 번에 여러 파일 선택 가능)
 * FE-UI-07  업로드 완료 시 파싱 결과 카드 전달
 */

import { useCallback, useRef, useState, type DragEvent } from "react";
import { UploadIcon, XIcon, FileTextIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useFileUpload } from "@/hooks/use-file-upload";
import type { UploadedFile } from "@/lib/api-client";

type Props = {
  sessionId?: string;
  onUploaded?: (file: UploadedFile) => void;
  className?: string;
};

export function FileUploader({ sessionId, onUploaded, className }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const { status, progress, error, result, upload, reset, allowedExtensions, maxSizeMB } =
    useFileUpload();

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const list = Array.from(files);
      for (const file of list) {
        const uploaded = await upload(file, sessionId).catch(() => null);
        if (uploaded) onUploaded?.(uploaded);
      }
    },
    [upload, sessionId, onUploaded]
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
  };
  const onDragLeave = () => setDragging(false);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      handleFiles(e.target.files);
      e.target.value = "";
    }
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* 드롭존 */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 text-sm transition-colors",
          dragging
            ? "border-ring bg-accent/50"
            : "border-muted-foreground/25 hover:border-muted-foreground/50 hover:bg-accent/20"
        )}
        role="button"
        aria-label="파일 업로드 영역"
      >
        <UploadIcon className="size-8 text-muted-foreground" />
        <p className="text-muted-foreground">
          파일을 여기로 드래그하거나 <span className="font-medium text-foreground">클릭</span>하세요
        </p>
        <p className="text-xs text-muted-foreground">
          {allowedExtensions.join(", ")} · 최대 {maxSizeMB}MB
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        multiple
        accept={allowedExtensions.join(",")}
        className="hidden"
        onChange={onInputChange}
      />

      {/* 진행률 바 */}
      {status === "uploading" && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>업로드 중...</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-200"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 에러 메시지 */}
      {status === "error" && error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <XIcon className="size-4 shrink-0" />
          <span>{error}</span>
          <Button variant="ghost" size="sm" className="ml-auto h-auto p-0" onClick={reset}>
            다시 시도
          </Button>
        </div>
      )}

      {/* 완료 표시 */}
      {status === "done" && result && (
        <div className="flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2 text-sm">
          <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
          <span className="flex-1 truncate">{result.original_name}</span>
          <span className="text-xs text-muted-foreground">
            {result.chunk_count > 0 ? `${result.chunk_count}청크` : "파싱됨"}
          </span>
          <Button variant="ghost" size="sm" className="h-auto p-0 text-xs" onClick={reset}>
            <XIcon className="size-3" />
          </Button>
        </div>
      )}
    </div>
  );
}
