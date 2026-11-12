// 기본 select 한 꼴(sid:MARC-ENT-430, 202 2번): 네이티브 <select> 를 그대로 두고(역할 combobox·펼친 목록은 브라우저) 꼴만 selectLook 으로 입힌다.
// OS 화살표는 지우고(appearance-none) 오른쪽 끝 안쪽 16 에 ▾ 를 그린다 — 글 자리는 오른쪽 40(▾ 16 + 끝 16 + 사이 8).
// className 은 감싼 쪽에 간다(폭 — 폼 안은 w-full). 키트 packages/ui 의 select 는 쓰지 않는다(역할이 바뀌어 combobox·selectOption 이 깨진다).
import type { ComponentPropsWithoutRef } from 'react';

import { ChevronDownIcon } from '@marcspon/common/generated/icons/MyIcons';
import { cn } from '@marcspon/ui/lib/utils';

import { SELECT_CHEVRON, SELECT_LOOK, SELECT_MIN_WIDTH } from './selectLook.ts';

export type NativeSelectProps = ComponentPropsWithoutRef<'select'>;

export function NativeSelect({ className, ...props }: NativeSelectProps) {
  return (
    <span className={cn('relative inline-flex', SELECT_MIN_WIDTH, className)}>
      <select
        {...props}
        className={cn('w-full appearance-none', SELECT_LOOK, 'pr-10')}
      />
      <ChevronDownIcon
        aria-hidden
        className={cn(
          'pointer-events-none absolute right-4 top-1/2 -translate-y-1/2',
          SELECT_CHEVRON,
        )}
      />
    </span>
  );
}
