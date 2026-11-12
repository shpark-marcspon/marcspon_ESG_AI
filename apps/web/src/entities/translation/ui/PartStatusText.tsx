// 파트 상태 한 덩이(밴드 TRW0b, 시안 TR-01·04): 「완료」·「진행 중 · 번역 20/38쪽」·「실패」·「실패 · 일부 쪽」. 목록·표가 같이 쓴다.
//   글은 ui/labels.ts(partStatusLabel). 「비용」 말 없음(sid:MARC-ENT-334).
// 꼴은 키트 Badge sm(밴드 TRP2 TC2, 시안 e-badge). 상태 → 변형은 표 하나(PART_STATUS_LOOK)에 둔다:
//   완료 success · 진행 중 orange · 대기 grey · 실패·일부 쪽 error. 확인할 쪽·단계 줄 값도 같은 꼴(StatusBadge)로 그린다.
import type { ReactNode } from 'react';

import { Badge } from '@marcspon/ui/components/badge';

import type { RejectionKey, TabState } from '../model/index.ts';
import { partStatusLabel } from './labels.ts';

/** 상태 배지의 키트 변형(넷만 쓴다). */
export type StatusLook = 'success' | 'orange' | 'error' | 'grey';

/** 파트 상태 → 배지 변형. 상태 색은 여기 한 곳에만 둔다. */
export const PART_STATUS_LOOK: Record<TabState, StatusLook> = {
  done: 'success',
  running: 'orange',
  queued: 'grey',
  failed: 'error',
  failed_partial: 'error',
};

export interface StatusBadgeProps {
  look: StatusLook;
  children: ReactNode;
  /** 파트 상태를 그릴 때 그 상태(시험·e2e 손잡이). */
  state?: TabState;
}

export function StatusBadge({ look, children, state }: StatusBadgeProps) {
  return (
    <Badge variant={look} size="sm" data-state={state} data-look={look}>
      {children}
    </Badge>
  );
}

export interface PartStatusTextProps {
  state: TabState;
  reason?: RejectionKey;
  pages?: { done: number; total: number };
}

export function PartStatusText({ state, reason, pages }: PartStatusTextProps) {
  return (
    <StatusBadge look={PART_STATUS_LOOK[state]} state={state}>
      {partStatusLabel(state, reason, pages)}
    </StatusBadge>
  );
}
