"use client";

/**
 * FE-HIS-01: 대화 목록 사이드바
 * FE-HIS-04: 검색 – 검색어를 SearchProvider 로 ThreadList 에 전달
 */

import * as React from "react";
import { MessagesSquare, SearchIcon, XIcon } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ThreadList, SearchProvider } from "@/components/assistant-ui/thread-list";
import { useSessionStore } from "@/stores/session-store";

export function ThreadListSidebar({
  ...props
}: React.ComponentProps<typeof Sidebar>) {
  const { searchQuery, setSearchQuery } = useSessionStore();
  const [showSearch, setShowSearch] = React.useState(false);

  return (
    <Sidebar {...props}>
      {/* ── 헤더 ── */}
      <SidebarHeader className="aui-sidebar-header border-b pb-2">
        <div className="flex items-center justify-between px-2 pt-1">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
              <MessagesSquare className="size-4" />
            </div>
            <span className="font-semibold text-sm">ChatUI</span>
          </div>

          {/* 검색 토글 버튼 */}
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={() => {
              setShowSearch((v) => !v);
              if (showSearch) setSearchQuery("");
            }}
            aria-label={showSearch ? "검색 닫기" : "검색"}
          >
            {showSearch ? <XIcon className="size-4" /> : <SearchIcon className="size-4" />}
          </Button>
        </div>

        {/* FE-HIS-04: 검색 입력창 */}
        {showSearch && (
          <div className="px-2 pt-1">
            <Input
              placeholder="대화 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 text-sm"
              autoFocus
            />
          </div>
        )}
      </SidebarHeader>

      {/* ── 대화 목록 ── */}
      <SidebarContent className="aui-sidebar-content px-2 py-2">
        <SearchProvider value={searchQuery}>
          <ThreadList />
        </SearchProvider>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  );
}
