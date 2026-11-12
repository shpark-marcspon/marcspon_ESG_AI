// 버전 흐름 띠(밴드 FW1 ②, 시안 GW-06_r1 의 g-vflow). 버전마다 High·Mid 건수, 고른 두 버전(비교 대상·이번)을 표시한다.
//
// 버전 칸: 1px border-tertiary 테두리, 모서리 8, 흰 바탕, 안쪽 16, 사이 6. 고른 두 버전은 테두리 border-secondary.
//   머리 줄(이름 + 배지) pre-body-04 text-primary, 날짜·회차 pre-caption-03 text-tertiary, 건수는 RiskBadge(High n · Mid n).
// 고른 표시는 색만으로 알리지 않는다: 「비교 대상」·「이번」 글자 배지를 같이 단다(시안과 같음. 비교 대상 blue, 이번 grey).
// 순서 있는 목록(ol)이고 칸 사이 화살표는 꾸밈이라 aria-hidden.
// 이 부품은 고르는 동작을 모른다(비교 대상 고르기는 쓰는 화면 FW2 의 몫). 확정·미확정 배지는 badges 로 받는다.
import type * as React from 'react';

import { ChevronRightIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Badge } from '@marcspon/ui/components/badge';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../config/text.ts';
import { RiskBadge } from './RiskBadge.tsx';

export interface VersionFlowItem {
  id: string;
  /** 버전 이름(「v3」). */
  name: string;
  /** 날짜·회차 글자(「2026-10-08 · 1회차」). */
  meta?: string;
  high: number;
  mid: number;
  /** 고른 두 버전의 자리: 비교 대상(base)·이번(current). 없으면 고르지 않은 버전. */
  pick?: 'base' | 'current';
  /** 이름 옆 배지(확정·미확정·검토 중 등. 쓰는 쪽이 RunStatusBadge 나 키트 Badge 를 넘긴다). */
  badges?: React.ReactNode;
}

export interface VersionFlowStripProps {
  versions: readonly VersionFlowItem[];
  /** 목록 이름. 기본 「버전 흐름」. */
  label?: string;
  /** 고른 표시의 글자. 기본 「비교 대상」·「이번」. */
  pickText?: { base: string; current: string };
  className?: string;
}

const PICK_LOOK = {
  base: { variant: 'blue', className: 'text-support-blue-dark' },
  current: { variant: 'grey', className: undefined },
} as const;

function VersionFlowStrip({
  versions,
  label = GW_TEXT.versionFlow.label,
  pickText = {
    base: GW_TEXT.versionFlow.base,
    current: GW_TEXT.versionFlow.current,
  },
  className,
}: VersionFlowStripProps) {
  return (
    <ol
      aria-label={label}
      className={cn(
        'm-0 flex list-none flex-wrap items-stretch gap-2 p-0',
        className,
      )}
    >
      {versions.map((version, index) => (
        <li
          key={version.id}
          data-pick={version.pick}
          className="flex min-w-0 flex-[1_1_180px] items-stretch gap-2"
        >
          <div
            className={cn(
              'box-border flex min-w-0 flex-1 flex-col gap-1.5 rounded-component border border-solid bg-background-primary p-4',
              version.pick ?
                'border-border-secondary'
              : 'border-border-tertiary',
            )}
          >
            <span className="flex flex-wrap items-center gap-1.5 text-style-pre-body-04 text-text-primary">
              <span>{version.name}</span>
              {version.badges}
              {version.pick && (
                <Badge
                  variant={PICK_LOOK[version.pick].variant}
                  size="sm"
                  className={PICK_LOOK[version.pick].className}
                >
                  {pickText[version.pick]}
                </Badge>
              )}
            </span>
            {version.meta != null && (
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {version.meta}
              </span>
            )}
            <span className="flex flex-wrap gap-1.5">
              <RiskBadge level="high" count={version.high} />
              <RiskBadge level="mid" count={version.mid} />
            </span>
          </div>
          {index < versions.length - 1 && (
            <ChevronRightIcon
              aria-hidden
              className="size-4 shrink-0 self-center text-text-quaternary"
            />
          )}
        </li>
      ))}
    </ol>
  );
}
VersionFlowStrip.displayName = 'VersionFlowStrip';

export { VersionFlowStrip };
