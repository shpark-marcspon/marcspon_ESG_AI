// 실행 상태 배지: AI 점검 중(진행률) · 멈춤 · 검토 대기 · 검토 중(n/m — 목록은 셈 없이) · 검토 완료(잠금 + 확정한 사람·날짜). 밴드 FW1 ①.
//
// 상태 → 키트 badge 변형은 표 하나(RUN_STATUS_LOOK)에 둔다(발주서 §1-4 [R9]·[R7]). 색은 시안 GW-01_r1 의 배지를 따랐다:
//   AI 점검 중 orange · 멈춤 error · 검토 대기 grey · 검토 중 blue · 검토 완료 success.
//   초록·빨강은 키트 green·red 가 아니라 success·error(FV3-FG 결정, 디자인 시스템 Badge 카드).
//   파랑은 키트 blue(글자 support-blue)에 support-blue-dark 글자를 덮는다(Badge 카드: 감싸개에서 blue-dark 글자 변형 하나를 더한다).
// 이 부품은 상태를 받아 그리기만 한다. 상태가 어떻게 바뀌는지는 모른다(발주서 §1-5).
import * as React from 'react';

import { LockIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../config/text.ts';

export const RUN_STATUS_KINDS = [
  'analyzing',
  'failed',
  'pending',
  'reviewing',
  'confirmed',
] as const;
export type RunStatusKind = (typeof RUN_STATUS_KINDS)[number];

/** 그릴 상태. 종류마다 붙는 값이 다르다. */
export type RunStatus =
  | { kind: 'analyzing'; /** 0~100. 없으면 글자만. */ progress?: number }
  | { kind: 'failed' }
  | { kind: 'pending' }
  | { kind: 'reviewing'; reviewed: number; total: number }
  | {
      kind: 'confirmed';
      /** 확정한 사람(가정 칸. 인계 v56 덧붙임 4절). */
      by?: string;
      /** 확정한 날짜 글자(쓰는 쪽이 꼴을 정한다. 예: 「10-06」). */
      at?: string;
    };

type BadgeVariant = NonNullable<BadgeProps['variant']>;

/** 상태 → 키트 badge 변형과 글자. 상태 색은 여기 한 곳에만 둔다. */
export const RUN_STATUS_LOOK = {
  analyzing: { variant: 'orange', label: GW_TEXT.runStatus.analyzing },
  failed: { variant: 'error', label: GW_TEXT.runStatus.failed },
  pending: { variant: 'grey', label: GW_TEXT.runStatus.pending },
  reviewing: {
    variant: 'blue',
    className: 'text-support-blue-dark',
    label: GW_TEXT.runStatus.reviewing,
  },
  confirmed: { variant: 'success', label: GW_TEXT.runStatus.confirmed },
} as const satisfies Record<
  RunStatusKind,
  { variant: BadgeVariant; label: string; className?: string }
>;

function badgeText(status: RunStatus, showCount: boolean): string {
  const { label } = RUN_STATUS_LOOK[status.kind];
  switch (status.kind) {
    case 'analyzing':
      return status.progress === undefined ?
          label
        : `${label} ${Math.round(status.progress)}%`;
    case 'reviewing':
      return showCount ? `${label} ${status.reviewed}/${status.total}` : label;
    default:
      return label;
  }
}

export interface RunStatusBadgeProps {
  status: RunStatus;
  /** 검토 중의 n/전체를 붙일지. 상세 화면(GW-04·05)은 n 을 meta·진행에 두고 배지에서 뺀다(디자인 대조 C6). */
  showCount?: boolean;
  className?: string;
}

function RunStatusBadge({
  status,
  showCount = true,
  className,
}: RunStatusBadgeProps) {
  const look: { variant: BadgeVariant; className?: string } =
    RUN_STATUS_LOOK[status.kind];
  const confirmed = status.kind === 'confirmed';
  const badge = (
    <Badge
      variant={look.variant}
      size="sm"
      data-status={status.kind}
      className={cn(look.className, !confirmed && className)}
    >
      {badgeText(status, showCount)}
    </Badge>
  );
  if (status.kind !== 'confirmed') return badge;
  // 확정은 자물쇠를 늘 그린다(시안 GW-06_r1 의 버전 카드는 사람·날짜 없이 「확정 🔒」).
  // 사람·날짜 글자 칸은 at·by 가 둘 다 비면 그리지 않는다(빈 칸을 남기지 않게).
  const who = [status.at, status.by].filter(Boolean).join(' ');
  return (
    <span className={cn('inline-flex items-center gap-1.5', className)}>
      {badge}
      <span className="inline-flex items-center gap-1 whitespace-nowrap text-style-pre-caption-02 text-text-tertiary">
        <LockIcon aria-hidden className="size-3 shrink-0" />
        {who !== '' && <span data-confirmed-by="">{who}</span>}
      </span>
    </span>
  );
}
RunStatusBadge.displayName = 'RunStatusBadge';

export { RunStatusBadge };
