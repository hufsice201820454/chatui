# thread-list.tsx 변경사항 정리

## 1) 수정 파일 절대 경로

```
c:\workspace\AI\chatui\frontend\components\assistant-ui\thread-list.tsx
```

## 2) 수정 라인 + 수정 전/후 코드

**수정 라인:** 103 ~ 110 (기존 103~105 구간 확장)

### 수정 전

```tsx
  const threadId: string = useAuiState((s: any) => s.thread?.id ?? "");
  const autoTitle: string = useAuiState((s: any) => s.thread?.title ?? "New Chat");
```

### 수정 후

```tsx
  // 각 row는 threadListItem 컨텍스트를 우선 사용하고,
  // 혹시 없으면 fallback 으로 현재 thread 정보를 사용한다.
  const threadId: string = useAuiState(
    (s: any) => s.threadListItem?.id ?? s.thread?.id ?? ""
  );
  const autoTitle: string = useAuiState(
    (s: any) => s.threadListItem?.title ?? s.thread?.title ?? "New Chat"
  );
```

## 변경 요약

사이드바에서 세션 하나의 이름만 변경했을 때 모든 세션 이름이 함께 바뀌던 버그를 수정했습니다. 각 리스트 row가 전역 `thread`가 아니라 **해당 row의 `threadListItem`** 을 우선 참조하도록 변경했고, 없을 때만 `thread`를 fallback으로 사용합니다.
