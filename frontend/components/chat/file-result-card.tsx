"use client";

/**
 * FE-UI-07: 업로드된 파일의 파싱 결과를 인라인 카드로 표시
 */

import { useState } from "react";
import { FileTextIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UploadedFile } from "@/lib/api-client";

type Props = {
  file: UploadedFile & { parsed_text?: string };
  className?: string;
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileResultCard({ file, className }: Props) {
  const [expanded, setExpanded] = useState(false);

  const preview = file.parsed_text?.slice(0, 500);
  const hasMore = (file.parsed_text?.length ?? 0) > 500;

  return (
    <div
      className={cn(
        "rounded-xl border bg-muted/30 p-3 text-sm",
        className
      )}
    >
      {/* 헤더 */}
      <div className="flex items-center gap-2">
        <FileTextIcon className="size-5 shrink-0 text-muted-foreground" />
        <div className="flex-1 overflow-hidden">
          <p className="truncate font-medium">{file.original_name}</p>
          <p className="text-xs text-muted-foreground">
            {formatBytes(file.size_bytes)} · {file.mime_type}
            {file.chunk_count > 0 && ` · ${file.chunk_count}개 청크`}
          </p>
        </div>
        {preview && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <><ChevronUpIcon className="size-3 mr-1" />접기</>
            ) : (
              <><ChevronDownIcon className="size-3 mr-1" />내용 보기</>
            )}
          </Button>
        )}
      </div>

      {/* 파싱된 텍스트 미리보기 */}
      {expanded && preview && (
        <div className="mt-2 rounded-lg border bg-background p-3">
          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed">
            {preview}
            {hasMore && (
              <span className="text-muted-foreground/60">
                {"\n"}... (총 {file.parsed_text!.length.toLocaleString()}자)
              </span>
            )}
          </pre>
        </div>
      )}
    </div>
  );
}
