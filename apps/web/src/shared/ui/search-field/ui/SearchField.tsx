// 검색 칸. 키트 search-input 대신 키트 input 위에 시안 v149 의 꼴을 준다(밴드 AV2, sid:MARC-ISSUE-344 SB4).
//
// 키트 SearchInput 과 다른 것:
//   - 돋보기는 왼쪽(왼 16 · 아이콘 16 · 간격 8 → 글은 40 에서 시작), 오른쪽 안쪽 12. 키트는 오른쪽 돋보기에 pl-2 pr-8.
//   - 돋보기는 그림(aria-hidden)이다. 키트의 「검색」 단추는 누름 동작이 없어 탭 순서에 빈 정거장만 만들었다(AV2 Q6).
//   - 「검색어 지우기」 단추(searchQuery)는 쓰는 곳이 없어 들이지 않았다.
// className 은 겉(칸 전체)에 준다 — 쓰는 쪽이 칸 폭을 정한다(예: w-52). 나머지 props 와 ref 는 input 으로 간다.
import * as React from 'react';

import { SearchIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import type { InputProps } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

export type SearchFieldProps = InputProps;

const SearchField = React.forwardRef<HTMLInputElement, SearchFieldProps>(
  ({ className, ...props }, ref) => (
    <div className={cn('relative h-9', className)}>
      <SearchIcon
        aria-hidden
        className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-text-tertiary"
      />
      <Input ref={ref} className="h-full w-full py-1 pl-10 pr-3" {...props} />
    </div>
  ),
);
SearchField.displayName = 'SearchField';

export { SearchField };
