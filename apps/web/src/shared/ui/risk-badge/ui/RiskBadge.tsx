// 위험 등급 표시(High · Mid · Low). 밴드 FW1 ①, 디자인 시스템 v8 RiskBadge 카드. TRW0a ① 에서 그린워싱에서 shared 로 올림.
//
// 키트 badge 를 변형 표 하나(RISK_BADGE_LOOK)로 고른다. 등급 색은 이 표에만 있다(발주서 §1-4 [R9]).
//   High 빨강 · Mid 노랑 · Low 회색: 우리 쪽 확정(2026-10-16 사용자 결정, sid:MARC-TICK-73 노트), 마크스폰 확인 전.
//   (카드. 「적색/주황/회색」의 주황은 브랜드색과 겹쳐 노랑으로 옮김.)
//   키트 변형 error·yellow·grey 는 시안 gw-r1.css 의 risk-high/mid/low 바탕·글자 값과 같은 토큰이다.
// 색만으로 알리지 않는다: 글자(High·Mid·Low)를 늘 같이 쓰고, 앞에 같은 색 점(6)을 둔다(aria-hidden).
// 시안과 다른 자리: 높이 20(키트 badge sm. 시안 .e-risk 는 22). 좌우는 6(px-1.5, 시안과 같다. 키트 sm 의 4 를 덮어씀).
//   높이 20 은 디자인 대조 물음 4 의 답(상태·딱지·등급을 한 줄 높이로. band-reports/FW1-design-review.md, 밴드 FW1b ⓪). 글자는 Bold 12(pre-caption-01)로 시안과 같다.
//   키트 바탕 굵기(font-medium)·sm 줄 높이(leading-5)를 끔 — size={null} 에 font-bold·h-5 를 우리가 준다(sid:MARC-ISSUE-344 SB1).
// 숫자만 꼴(display="count"): 열 머리가 이미 등급 이름인 표(GW-01·GW-04)에서 쓴다. 0 이면 회색 「0」(디자인 대조 C7, band-reports/FW2-design-review.md).
//   등급 이름은 열 머리가 말한다. 표 밖에서 쓰지 않는다.
import * as React from 'react';

import { Badge } from '@marcspon/ui/components/badge';
import type { BadgeProps } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { PARTS_TEXT } from '../../text.ts';

export const RISK_LEVELS = ['high', 'mid', 'low'] as const;
export type RiskLevel = (typeof RISK_LEVELS)[number];

type BadgeVariant = NonNullable<BadgeProps['variant']>;

/** 등급 → 키트 badge 변형. 등급 색은 여기 한 곳에만 둔다. */
export const RISK_BADGE_LOOK = {
  high: { variant: 'error', label: PARTS_TEXT.risk.high },
  mid: { variant: 'yellow', label: PARTS_TEXT.risk.mid },
  low: { variant: 'grey', label: PARTS_TEXT.risk.low },
} as const satisfies Record<
  RiskLevel,
  { variant: BadgeVariant; label: string }
>;

export interface RiskBadgeProps extends Omit<
  React.HTMLAttributes<HTMLDivElement>,
  'children'
> {
  level: RiskLevel;
  /** 있으면 글자 뒤에 건수를 붙인다(「High 9」). */
  count?: number;
  /** count 면 등급 글자 없이 건수만(없으면 0) 그린다. 0 이면 등급과 상관없이 회색. */
  display?: 'label' | 'count';
}

function RiskBadge({
  level,
  count,
  display = 'label',
  className,
  ...props
}: RiskBadgeProps) {
  const look = RISK_BADGE_LOOK[level];
  const countOnly = display === 'count';
  const zero = countOnly && (count ?? 0) === 0;
  return (
    <Badge
      // 0 의 회색은 Low 의 변형(grey)을 빌린다 — 등급 색 표(RISK_BADGE_LOOK) 밖에 색을 두지 않으려고
      variant={zero ? RISK_BADGE_LOOK.low.variant : look.variant}
      size={null}
      data-level={level}
      className={cn(
        'h-5 gap-1 px-1.5 font-bold text-style-pre-caption-01',
        className,
      )}
      {...props}
    >
      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-current" />
      {countOnly ?
        String(count ?? 0)
      : count === undefined ?
        look.label
      : `${look.label} ${count}`}
    </Badge>
  );
}
RiskBadge.displayName = 'RiskBadge';

export { RiskBadge };
