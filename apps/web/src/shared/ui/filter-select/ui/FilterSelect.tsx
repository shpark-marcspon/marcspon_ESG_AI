// 거르기 고르기 칸(밴드 AD2 — 어드민 시안의 e-select 「기간: 이번 주 ▾」 꼴). 키트 dropdown-menu 를 얇게 감싼다(키트는 고치지 않는다).
// 단추 글은 「{label}{separator}{고른 값}」(label 이 없으면 값만 — AD-03 「버전 A · v2 (적용 중)」 꼴은 separator ' · '), 펼치면 값 목록(고른 값 앞에 체크). 값을 고르면 onChange. 보기만 바꾸는 칸이라 쓰기 끔(canWrite)과 상관없다.
// 문구는 받기만 한다(label·option.label). 단추 이름은 aria-label 이 있으면 그것(없으면 보이는 글).
// 단추 꼴은 selectLook.ts 한 자리(sid:MARC-ENT-430 — NativeSelect 와 같은 꼴). 단추 꼴(밴드 AD4R ③ — MARC-ISSUE-197 J2, 디자인 동의): 모서리 8(키트 토큰 component)·좌우 16·최소 너비 140(토큰 없음 — 임의 값).
//   쓰는 쪽 className 이 이긴다(AD-03 시험 세트 칸의 min-w-[280px]).
//   최소 폭보다 글이 짧으면 글은 왼쪽·▾ 는 오른쪽 끝(양끝 정렬), 글과 ▾ 사이 8, ▾ 색 text-tertiary(키트 .e-select 꼴 — 디자인 대조 AD4R B1).
import {
  CheckIcon,
  ChevronDownIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@marcspon/ui/components/dropdown-menu';
import { cn } from '@marcspon/ui/lib/utils';

import { SELECT_CHEVRON, SELECT_LOOK, SELECT_MIN_WIDTH } from './selectLook.ts';

export interface FilterOption<T extends string> {
  value: T;
  label: string;
}

export interface FilterSelectProps<T extends string> {
  /** 단추 앞머리(「기간」). 없으면 값만. */
  label?: string;
  /** 앞머리와 값 사이(기본 「: 」). */
  separator?: string;
  value: T;
  options: readonly FilterOption<T>[];
  onChange(value: T): void;
  'aria-label'?: string;
  className?: string;
}

export function FilterSelect<T extends string>({
  label,
  separator = ': ',
  value,
  options,
  onChange,
  'aria-label': ariaLabel,
  className,
}: FilterSelectProps<T>) {
  const current = options.find((option) => option.value === value);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label={ariaLabel}
        data-filter-value={value}
        className={cn(
          'inline-flex items-center justify-between gap-2 [&_svg]:size-4',
          SELECT_MIN_WIDTH,
          SELECT_LOOK,
          className,
        )}
      >
        {label ?
          `${label}${separator}${current?.label ?? ''}`
        : (current?.label ?? '')}
        <ChevronDownIcon aria-hidden className={SELECT_CHEVRON} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {options.map((option) => (
          <DropdownMenuItem
            key={option.value}
            role="menuitemradio"
            aria-checked={option.value === value}
            onSelect={() => onChange(option.value)}
            className="gap-2 px-3 py-2 text-style-pre-body-06 text-text-secondary [&_svg]:size-4"
          >
            <span className="inline-flex w-4" aria-hidden>
              {option.value === value && <CheckIcon />}
            </span>
            {option.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
