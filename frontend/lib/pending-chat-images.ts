/**
 * Composer에 붙은 이미지를 전송 직전에 캡처해 두었다가
 * prepareSendMessagesRequest에서 body.images로 사용하기 위한 모듈 저장소.
 * (메시지 parts에 이미지가 안 들어가는 경우 대비)
 */

export type PendingImage = { mime: string; data: string };

let pending: PendingImage[] = [];

export function setPendingChatImages(images: PendingImage[]): void {
  pending = images;
}

export function getAndClearPendingChatImages(): PendingImage[] {
  const out = pending;
  pending = [];
  return out;
}

export function getPendingChatImages(): PendingImage[] {
  return [...pending];
}
