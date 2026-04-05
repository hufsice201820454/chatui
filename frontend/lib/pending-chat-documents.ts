/**
 * Composer에 붙은 문서(PDF/DOCX/Excel)를 전송 직전에 캡처해 두었다가
 * prepareSendMessagesRequest에서 body.documents로 사용하기 위한 모듈 저장소.
 */

export type PendingDocument = { mime: string; data: string; filename?: string };

let pending: PendingDocument[] = [];

export function setPendingChatDocuments(docs: PendingDocument[]): void {
  pending = docs;
}

export function getAndClearPendingChatDocuments(): PendingDocument[] {
  const out = pending;
  pending = [];
  return out;
}

export function getPendingChatDocuments(): PendingDocument[] {
  return [...pending];
}
