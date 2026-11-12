// 불러오기 스켈레톤(밴드 LE1 ①, sid:MARC-ENT-260 ①, 시안 CM-03 의 cm-skcard). 화면마다 맞추지 않는 공통 꼴 하나 — 결과 카드(밴드 LD1, sid:MARC-ENT-443 ④, 6c):
//   카드 안 세로 gap 20 · 제목 막대 28%×22 · 수 칸 넷(grid 4열 gap 16, 높이 96, rounded-component — 900 아래 2열) · 큰 칸(높이 280, rounded-component).
//   회색 블록은 SkeletonBar(움직임 없음·background-tertiary). 표는 이것 대신 SkeletonRows(DataTable loading).
// 화면 틀(제목 줄·단계 표시)은 쓰는 쪽이 그대로 두고 본문 자리에만 이것을 둔다. 300ms 늦추기는 쓰는 쪽이 useDelayed 로 한다.
// 보조기기: 카드는 role="status" + aria-label 과 숨긴 글(label, 기본 PARTS_TEXT.loading). 블록은 aria-hidden. aria-busy 는 카드가 아니라 쓰는 쪽의
//   화면 바깥 틀이 읽는 동안 내내 단다(밴드 LA1 ①, 시안 CM-03_r1:37·:42 — busy 인 라이브 영역의 글은 읽히지 않을 수 있다).
// DOM 꼴(role·data-testid·숨긴 글·aria-hidden 셋, 칸 넷)은 바꾸지 않는다 — 모듈 화면 시험이 그것을 본다.
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

import { Card } from '../../card/index.ts';
import { SkeletonBar } from '../../skeleton-bar/index.ts';
import { PARTS_TEXT } from '../../text.ts';

export interface LoadSkeletonProps extends Omit<
  React.HTMLAttributes<HTMLElement>,
  'children'
> {
  /** 숨긴 글과 카드 이름(화면 읽기 프로그램용). 기본 「불러오는 중」. */
  label?: string;
}

const LoadSkeleton = React.forwardRef<HTMLElement, LoadSkeletonProps>(
  ({ label = PARTS_TEXT.loading, className, ...props }, ref) => (
    <Card
      ref={ref}
      role="status"
      aria-label={label}
      data-testid="load-skeleton"
      className={cn('flex flex-col gap-5', className)}
      {...props}
    >
      <span className="sr-only">{label}</span>
      <SkeletonBar className="h-[22px] w-[28%]" />
      <div
        aria-hidden
        className="grid grid-cols-2 gap-4 min-[900px]:grid-cols-4"
      >
        {[0, 1, 2, 3].map((n) => (
          <SkeletonBar key={n} shape="block" className="h-24" />
        ))}
      </div>
      <SkeletonBar shape="block" className="h-[280px]" />
    </Card>
  ),
);
LoadSkeleton.displayName = 'LoadSkeleton';

export { LoadSkeleton };
