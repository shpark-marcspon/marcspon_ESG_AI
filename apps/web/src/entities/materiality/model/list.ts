// 평가 목록의 거르기·다음 할 일(밴드 IRW1 ③ — 판 IR-01·01a, 발주서 §2-3). 순수 함수와 타입.
// 상태 탭 넷(전체 · 대기·처리 중 · 완료 · 실패) → 서버 status 인자(「대기·처리 중」은 queued·processing 한 요청 — 데이터 검증 QB3 꼴).
// 다음 할 일: done [결과 보기] · queued·processing [진행 보기] · failed [다시 실행]. 줄 누름은 done → IR-04, 그 밖 → 그 실행의 IR-03
//   (failed 줄 누름으로 새 실행을 만들지 않는다 — 비용 0, DV2b 선례).
import type { RunStatus } from './result.ts';

export type ListTab = 'all' | 'active' | 'done' | 'failed';
export const LIST_TABS: readonly ListTab[] = [
  'all',
  'active',
  'done',
  'failed',
];

/** 탭 → 서버 status 인자(전체는 없음). */
export function statusesOf(tab: ListTab): readonly RunStatus[] | undefined {
  switch (tab) {
    case 'all':
      return undefined;
    case 'active':
      return ['queued', 'processing'];
    case 'done':
      return ['done'];
    case 'failed':
      return ['failed'];
  }
}

export type NextAction = 'result' | 'progress' | 'rerun';
export const nextOf = (status: RunStatus): NextAction =>
  status === 'done' ? 'result'
  : status === 'failed' ? 'rerun'
  : 'progress';

/** 줄 누름이 가는 곳: done → 결과, 그 밖(failed 포함) → 그 실행의 처리 상태. */
export type RowTarget = 'result' | 'status';
export const rowTargetOf = (status: RunStatus): RowTarget =>
  status === 'done' ? 'result' : 'status';
