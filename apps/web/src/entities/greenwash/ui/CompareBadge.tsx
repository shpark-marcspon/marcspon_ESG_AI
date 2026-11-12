// 수정본 비교 분류 배지(밴드 FW1 ②, 시안 GW-06_r1). 분류 일곱, 글자를 늘 같이 쓴다.
//
// 분류 → 키트 badge 변형은 표 하나(COMPARE_LOOK)에 둔다(발주서 §1-4 [R9]). 색은 시안 GW-06_r1 의 배지를 따랐다:
//   해소 셋 success · 남음 orange · 등급 바뀜 blue(+ support-blue-dark 글자, Badge 카드) · 새로 생김 error · 범위 밖 grey.
// 해소 갈래 셋은 배지 「해소」 한 장 + 그 아래 작은 글(「문장 삭제」·「더는 지적 안 됨」. 갈래 없는 해소는 작은 글 없음)이다.
//   시안 GW-06 표 칸 꼴이고, 배지 폭을 같게 해 열을 가지런히 둔다(디자인 대조 물음 9, 밴드 FW1b ⓪).
// 글자 표는 셋이다:
//   - label: 한 줄 글자(「해소 · 문장 삭제」). 엑셀처럼 한 줄이 필요한 곳에 쓴다. 이 부품은 그리지 않는다
//     (접근성 이름을 따로 달지 않는다: 읽는 글은 배지 글자 + 갈래 글 그대로다).
//   - badge: 배지에 쓰는 글자(「해소」).
//   - note: 배지 아래 갈래 글(해소 둘에만).
// className 은 바깥 칸(data-compare-cell)에 붙는다. 배지의 색·글자는 덮어쓸 수 없다(COMPARE_LOOK 에서만 바꾼다).
// 값 이름은 GC1(검증 감독과 합의한 계약) 초안 전이다(무효 조건: GC1 초안이 값을 바꾸면 COMPARE_KINDS 와 문구 표를 바꾼다).
import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../config/text.ts';

export const COMPARE_KINDS = [
  'resolved_deleted',
  'resolved_not_flagged',
  'resolved_undetermined',
  'remaining',
  'level_changed',
  'new',
  'out_of_scope',
] as const;
export type CompareKind = (typeof COMPARE_KINDS)[number];

type BadgeVariant = NonNullable<BadgeProps['variant']>;

interface CompareLook {
  variant: BadgeVariant;
  /** 한 줄 글자. */
  label: string;
  /** 배지 글자. */
  badge: string;
  /** 배지 아래 갈래 글. */
  note?: string;
  className?: string;
}

/** 비교 분류 → 키트 badge 변형과 글자. 비교 색은 여기 한 곳에만 둔다. */
export const COMPARE_LOOK = {
  resolved_deleted: {
    variant: 'success',
    label: GW_TEXT.compare.resolved_deleted,
    badge: GW_TEXT.compareBadge.resolved_deleted,
    note: GW_TEXT.compareNote.resolved_deleted,
  },
  resolved_not_flagged: {
    variant: 'success',
    label: GW_TEXT.compare.resolved_not_flagged,
    badge: GW_TEXT.compareBadge.resolved_not_flagged,
    note: GW_TEXT.compareNote.resolved_not_flagged,
  },
  resolved_undetermined: {
    variant: 'success',
    label: GW_TEXT.compare.resolved_undetermined,
    badge: GW_TEXT.compareBadge.resolved_undetermined,
  },
  remaining: {
    variant: 'orange',
    label: GW_TEXT.compare.remaining,
    badge: GW_TEXT.compareBadge.remaining,
  },
  level_changed: {
    variant: 'blue',
    className: 'text-support-blue-dark',
    label: GW_TEXT.compare.level_changed,
    badge: GW_TEXT.compareBadge.level_changed,
  },
  new: {
    variant: 'error',
    label: GW_TEXT.compare.new,
    badge: GW_TEXT.compareBadge.new,
  },
  out_of_scope: {
    variant: 'grey',
    label: GW_TEXT.compare.out_of_scope,
    badge: GW_TEXT.compareBadge.out_of_scope,
  },
} as const satisfies Record<CompareKind, CompareLook>;

export interface CompareBadgeProps {
  kind: CompareKind;
  /** 바깥 칸(배지 + 갈래 글을 세로로 쌓은 것)에 붙는다. 배지 자체에는 닿지 않는다. */
  className?: string;
}

function CompareBadge({ kind, className }: CompareBadgeProps) {
  const look: CompareLook = COMPARE_LOOK[kind];
  return (
    <span
      data-compare-cell={kind}
      className={cn('inline-flex flex-col items-start gap-0.5', className)}
    >
      <Badge
        variant={look.variant}
        size="sm"
        data-compare={kind}
        className={look.className}
      >
        {look.badge}
      </Badge>
      {look.note === undefined ? null : (
        <span
          data-compare-note={kind}
          className="text-style-pre-caption-03 text-text-tertiary"
        >
          {look.note}
        </span>
      )}
    </span>
  );
}
CompareBadge.displayName = 'CompareBadge';

export { CompareBadge };
