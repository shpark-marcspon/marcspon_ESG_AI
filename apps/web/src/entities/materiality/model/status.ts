// 실행 상태 배지·시각 글(밴드 IRW1 ① — 발주서 §2-1). 배지 글은 문구 표(IR_TEXT.badge)가 갈래 열쇠로 고른다:
//   queued 대기 · processing 처리 중 · done 완료 · failed 실패. 목록의 「처리 중 · <판 줄 이름>」은 ③ 이 currentLine 으로 짓는다.
import { formatKst } from '../../../shared/lib/time.ts';
import type { RunStatus } from './result.ts';

export const RUN_STATUSES: readonly RunStatus[] = [
  'queued',
  'processing',
  'done',
  'failed',
];

/** 실행 시각 글(한국 시각 「2026-10-19 14:02」 — 화면은 shared/lib 을 직접 부르지 않는다). 읽을 수 없으면 받은 글자 그대로. */
export const atText = (iso: string) => formatKst(iso);
