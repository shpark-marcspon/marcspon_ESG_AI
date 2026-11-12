// 토스트 저장소(밴드 S12Q1 ②). 화면마다 <Toaster> 하나가 이 저장소를 그린다(host 는 화면 — 발주서 Q10).
//   - toast() 는 어디서나(모달 안에서도) 부른다. 새 것이 앞(위) · 최대 TOAST_MAX — 넘으면 가장 오래된 것부터 걷는다(e6 ⑤).
//   - 글은 부르는 쪽이 넘긴다(모듈 text.ts — shared 안 글자 0, permits 4). 실패 톤의 닫기 이름도 prop.
//   - 사라짐(시간·✕)은 <Toaster> 가 정한다: leaving 으로 바꾼 뒤 나가는 움직임이 끝나면 걷는다(움직임 줄임이면 바로).
import type { ReactNode } from 'react';

/** 성공 = role status·polite·시간 뒤 사라짐 · 실패 = role alert·✕ 로 닫을 때까지(e6 ⑤, a8 덧). */
export type ToastTone = 'success' | 'error';

/**
 * 성공 톤은 ✕ 가 없어 이름 0 · 실패 톤은 ✕ 이름(화면 읽기 프로그램용)이 **필수**(디자인 대조 F8 — 이름 없는 ✕ 를 타입으로 막음).
 * 이름 글은 부르는 쪽 모듈 text.ts 에서(shared 안 글 0).
 */
export type ToastInput =
  | { message: ReactNode; tone?: 'success' }
  | { message: ReactNode; tone: 'error'; closeLabel: string };

export interface ToastItem {
  id: number;
  message: ReactNode;
  tone: ToastTone;
  closeLabel: string;
  leaving: boolean;
}

/** 한 번에 보이는 수(e6 ⑤). */
export const MAX = 3;

let items: readonly ToastItem[] = [];
let seq = 0;
const listeners = new Set<() => void>();

const emit = (next: readonly ToastItem[]) => {
  items = next;
  for (const listener of listeners) listener();
};

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const snapshot = (): readonly ToastItem[] => items;

/** 토스트 하나를 띄운다 — 돌려준 id 로 dismissToast. */
export function toast(input: ToastInput): number {
  seq += 1;
  const made: ToastItem = {
    id: seq,
    message: input.message,
    tone: input.tone ?? 'success',
    closeLabel: input.tone === 'error' ? input.closeLabel : '',
    leaving: false,
  };
  // 새 것이 앞. 나가는 중인 것은 셈 밖(곧 걷힌다) — 넘친 것은 바로 걷는다.
  const staying = items.filter((item) => !item.leaving);
  const kept = staying.slice(0, MAX - 1).map((item) => item.id);
  emit([made, ...items.filter((item) => kept.includes(item.id))]);
  return made.id;
}

/** 나가기 시작(움직임 뒤 removeToast). 없거나 이미 나가는 중이면 그대로. */
export function dismissToast(id: number): void {
  if (!items.some((item) => item.id === id && !item.leaving)) return;
  emit(
    items.map((item) => (item.id === id ? { ...item, leaving: true } : item)),
  );
}

/** 바로 걷는다. */
export function removeToast(id: number): void {
  if (!items.some((item) => item.id === id)) return;
  emit(items.filter((item) => item.id !== id));
}

/** 전부 걷는다(host 가 사라질 때 — 다른 화면으로 새지 않게). */
export function clearToasts(): void {
  if (items.length > 0) emit([]);
}
