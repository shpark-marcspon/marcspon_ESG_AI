// 고친 칸 표시(판 IR-04 r3 .d-pen·.d-penmk — 밴드 IRW11): 칸 오른쪽 위 회색 연필 12, 칸 오른쪽 여백 32.
// 공용 td 에 칸 클래스를 달 수 없어(DataTable DT2 Q1) 칸 몸을 relative 로 감싸고 오른쪽 16 을 더 비운다(td px-4 16 + 16 = 32).
// 연필 자리는 td 바깥 기준 위 8·오른쪽 8 = 몸 기준 위 -4(td py-3 12 − 8)·오른쪽 -8(td px-4 16 − 8).
// 연필은 role="img" + aria-label 「고친 칸 · 고친 사람 {이름} · {MM-DD HH:mm}」, 초점(tabIndex 0)·마우스로 공용 툴팁 「고친 사람 … · …」.
import type { ReactNode } from 'react';

import { PenIcon } from '@marcspon/common/generated/icons/MyIcons';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@marcspon/ui/components/tooltip';
import { cn } from '@marcspon/ui/lib/utils';

import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { editedStamp } from '../../../entities/materiality/model/index.ts';
import type { ResultEdit } from '../../../entities/materiality/model/index.ts';

const words = IR_TEXT.result.edit;

export function EditedMark({
  edit,
  className,
  children,
}: {
  edit: ResultEdit | null;
  className?: string;
  children: ReactNode;
}) {
  if (edit === null)
    return className === undefined ? children : (
        <div className={className}>{children}</div>
      );
  const at = editedStamp(edit.editedAt);
  return (
    <div className={cn('relative pr-4', className)} data-edited="">
      {children}
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            role="img"
            tabIndex={0}
            aria-label={words.editedLabel(edit.editedBy.name, at)}
            data-testid="edited-mark"
            className="absolute -right-2 -top-1 inline-flex text-text-quaternary outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-border-secondary"
          >
            <PenIcon aria-hidden className="size-3" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" align="end">
          {words.editedBy(edit.editedBy.name, at)}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
