"use client";

/**
 * FE-HIS-04: 현재 대화 내 메시지 검색 (키워드 하이라이팅)
 * 상단 툴바에서 검색 아이콘 클릭 시 표시되는 슬라이드 인 패널
 */

import { useState, type FC } from "react";
import { SearchIcon, XIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { sessionsApi } from "@/lib/api-client";

type SearchResult = {
  id: string;
  role: string;
  content: string;
  created_at: string;
};

type Props = {
  sessionId: string | undefined;
  className?: string;
};

function highlight(text: string, query: string) {
  if (!query) return text;
  const parts = text.split(new RegExp(`(${query})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={i} className="rounded bg-yellow-200 px-0.5 dark:bg-yellow-800">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

export const MessageSearch: FC<Props> = ({ sessionId, className }) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  const search = async (q: string) => {
    setQuery(q);
    if (!q.trim() || !sessionId) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await sessionsApi.searchMessages(sessionId, q);
      setResults((res.data as SearchResult[]) ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const close = () => {
    setOpen(false);
    setQuery("");
    setResults([]);
  };

  if (!open) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className={cn("size-8", className)}
        onClick={() => setOpen(true)}
        aria-label="대화 내 검색"
      >
        <SearchIcon className="size-4" />
      </Button>
    );
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {/* 검색 입력 */}
      <div className="flex items-center gap-2">
        <SearchIcon className="size-4 shrink-0 text-muted-foreground" />
        <Input
          autoFocus
          placeholder="메시지 검색..."
          value={query}
          onChange={(e) => search(e.target.value)}
          className="h-7 flex-1 text-sm"
        />
        <Button variant="ghost" size="icon" className="size-7" onClick={close}>
          <XIcon className="size-4" />
        </Button>
      </div>

      {/* 결과 */}
      {loading && (
        <p className="px-1 text-xs text-muted-foreground">검색 중...</p>
      )}
      {!loading && query && results.length === 0 && (
        <p className="px-1 text-xs text-muted-foreground">결과 없음</p>
      )}
      {results.length > 0 && (
        <div className="max-h-60 overflow-y-auto rounded-lg border bg-background p-1">
          {results.map((r) => (
            <div
              key={r.id}
              className="rounded-md px-3 py-2 text-sm hover:bg-muted"
            >
              <p className="mb-0.5 text-xs font-medium capitalize text-muted-foreground">
                {r.role}
              </p>
              <p className="line-clamp-3 text-foreground">
                {highlight(r.content ?? "", query)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
