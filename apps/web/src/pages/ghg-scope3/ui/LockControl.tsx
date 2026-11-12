// Scope 3 카테고리 자물쇠(밴드 S3W3a ③ — 값 파일 E1). 꼴은 S1·2 LockControl(pages/ghg-inventory/ui/EntryDetailDialog.tsx)을 옮겨 적었다(pages 끼리 import 0).
//   16 아이콘 + 안쪽 2 = 20 · 모서리 4. 잠김 = 바탕 background-brand + text-brand, 안 잠김 = 바탕 없음 + text-tertiary.
//   LockMark: 카드 표시(카드가 통째 단추라 단추 안 단추 금지 — 툴팁 0). LockControl: 상세 머리. 고객사·잠김은 누르지 못하는 그림(풀기 0 — sid:MARC-ENT-469 2).
import type { Ref } from 'react';

import {
  LockIcon,
  LockOpenIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';

const words = S3_TEXT.lock;

const boxOf = (locked: boolean) =>
  `inline-flex items-center rounded-control p-0.5 [&_svg]:size-4 ${
    locked ? 'bg-background-brand text-text-brand' : 'text-text-tertiary'
  }`;
const iconOf = (locked: boolean) =>
  locked ? <LockIcon aria-hidden /> : <LockOpenIcon aria-hidden />;

/** 카드의 표시(누를 자리 없음). */
export function LockMark({ locked }: { locked: boolean }) {
  return (
    <span
      role="img"
      data-testid="s3-card-lock"
      data-locked={locked ? 'true' : 'false'}
      aria-label={locked ? words.lockedLabel : words.unlockedLabel}
      className={boxOf(locked)}
    >
      {iconOf(locked)}
    </span>
  );
}

export interface LockControlProps {
  locked: boolean;
  operator: boolean;
  disabled: boolean;
  buttonRef?: Ref<HTMLButtonElement>;
  onLock(): void;
  onUnlock(): void;
}

/** 상세 머리의 자물쇠. 툴팁·aria-label 「잠금」/「잠금 해제」. */
export function LockControl({
  locked,
  operator,
  disabled,
  buttonRef,
  onLock,
  onUnlock,
}: LockControlProps) {
  if (locked && !operator)
    return (
      <span
        role="img"
        data-testid="s3-locked-mark"
        aria-label={words.lockedLabel}
        className={boxOf(true)}
      >
        {iconOf(true)}
      </span>
    );
  const label = locked ? words.unlock : words.lock;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            ref={buttonRef}
            type="button"
            aria-label={label}
            data-testid="s3-lock"
            data-locked={locked ? 'true' : 'false'}
            disabled={disabled}
            className={`${boxOf(locked)} cursor-pointer border-0 focus-visible:outline-2 disabled:cursor-not-allowed disabled:opacity-40 ${
              locked ? '' : 'bg-transparent'
            }`}
            onClick={locked ? onUnlock : onLock}
          >
            {iconOf(locked)}
          </button>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
