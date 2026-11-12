// 스켈레톤 막대 하나(밴드 LD1, sid:MARC-ENT-443, 6c cm-sk). 바탕 background-tertiary · 모서리 6(block 이면 rounded-component) · 움직임 없음(반짝임 금지 —
//   키트 Skeleton 의 animate-skeleton-bg-fade 를 쓰지 않는다) · max-width 100%. 폭·높이는 쓰는 쪽이 className·style 로 준다.
// 보조기기에는 숨긴다(aria-hidden). 「불러오는 중」은 감싼 쪽(role="status" 카드·aria-busy 표)이 말한다.
import * as React from 'react';

import { cn } from '@marcspon/ui/lib/utils';

export interface SkeletonBarProps {
  /** line(기본) = 글 줄 막대, 모서리 6. block = 결과 카드의 칸, 모서리 rounded-component(8 — 6c). */
  shape?: 'line' | 'block';
  className?: string;
  style?: React.CSSProperties;
}

// 모서리는 둘 중 하나만 단다 — tailwind-merge 가 키트 모서리 토큰을 rounded-[6px] 와 한 무리로 모른다(둘 다 남으면 CSS 차례가 정한다).
const SHAPE = { line: 'rounded-[6px]', block: 'rounded-component' } as const;

function SkeletonBar({ shape = 'line', className, style }: SkeletonBarProps) {
  return (
    <span
      aria-hidden
      data-skeleton-bar=""
      className={cn(
        'block max-w-full bg-background-tertiary',
        SHAPE[shape],
        className,
      )}
      style={style}
    />
  );
}
SkeletonBar.displayName = 'SkeletonBar';

export { SkeletonBar };
