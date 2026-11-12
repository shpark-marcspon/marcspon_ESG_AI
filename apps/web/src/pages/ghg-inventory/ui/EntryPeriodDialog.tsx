// S7 「데이터 입력 주기」 창(밴드 W12-2 ② — Figma 28556:29293 열림 · 28556:29335 닫힘, 디자인 e6 11-03 값). 블록 머리 [입력 주기 변경] 이 연다.
//   흰 판 420(sm)·모서리·안쪽 32·그림자는 DialogContent 그대로 · 세로 간격 24 · 제목 heading-02 · 아래 8 에 안내 줄(아이콘 16 · brand 14) —
//   안내 줄이 확인 글을 겸한다(둘째 확인 창 0, 감독 C0 통과). 그 블록이 고쳐졌으면 「저장하지 않은 입력은 사라져요.」 한 줄 더(Q4).
//   고르기: 높이 36 · 모서리 8 · 테두리 tertiary · 자리글 quaternary · ▾(열리면 ▴) · 목록 「년도」「분기」「월」(고른 줄 바탕 secondary + 오른쪽 체크).
//   [취소] 흰 바탕 검정 테두리 · [선택 완료] 검정 — 고르지 않았거나 지금 주기와 같으면 끔. 쓰기·응답 처리는 부르는 쪽(EntryDetailDialog).
import { useState } from 'react';

import {
  CheckIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  InfoIcon,
} from '@marcspon/common/generated/icons/MyIcons';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@marcspon/ui/components/dropdown-menu';
import { cn } from '@marcspon/ui/lib/utils';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import type { EntryPeriod } from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';

const text = GHG_TEXT.entry.periodChange;

export interface EntryPeriodDialogProps {
  /** 지금 블록 주기(같은 값을 고르면 [선택 완료] 끔). */
  current: string;
  /** 그 블록에 저장 안 한 고침이 있다(Q4 한 줄). */
  dirty: boolean;
  onPick(period: EntryPeriod): void;
  onClose(): void;
}

export function EntryPeriodDialog({
  current,
  dirty,
  onPick,
  onClose,
}: EntryPeriodDialogProps) {
  const [chosen, setChosen] = useState<EntryPeriod | null>(null);
  const [open, setOpen] = useState(false);
  const label = text.options.find((o) => o.value === chosen)?.label ?? null;
  const ready = chosen !== null && chosen !== current;
  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent size="sm" data-testid="entry-period" className="gap-6">
        <div className="flex flex-col gap-2">
          <DialogTitle className="flex h-10 items-center text-style-pre-heading-02 text-text-secondary">
            {text.title}
          </DialogTitle>
          <p
            data-testid="entry-period-notice"
            className="m-0 flex gap-1 text-style-pre-body-06 text-text-brand [&_svg]:mt-1 [&_svg]:size-4 [&_svg]:shrink-0"
          >
            <InfoIcon aria-hidden />
            <span>
              {text.notice}
              {dirty && (
                <>
                  {' '}
                  <span data-testid="entry-period-dirty">{text.dirty}</span>
                </>
              )}
            </span>
          </p>
        </div>
        <DropdownMenu open={open} onOpenChange={setOpen}>
          <DropdownMenuTrigger
            aria-label={text.title}
            data-testid="entry-period-select"
            className="box-border flex h-9 w-full cursor-pointer items-center justify-between rounded-component border border-solid border-border-tertiary bg-background-primary px-3 text-style-pre-body-06 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary [&_svg]:size-4"
          >
            <span
              className={
                label === null ? 'text-text-quaternary' : 'text-text-secondary'
              }
            >
              {label ?? text.placeholder}
            </span>
            {open ?
              <ChevronUpIcon aria-hidden className="text-text-tertiary" />
            : <ChevronDownIcon aria-hidden className="text-text-tertiary" />}
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="flex w-[var(--radix-dropdown-menu-trigger-width)] flex-col gap-2 rounded-component border border-solid border-border-tertiary py-4"
          >
            {text.options.map((option) => (
              <DropdownMenuItem
                key={option.value}
                role="menuitemradio"
                aria-checked={option.value === chosen}
                data-testid={`entry-period-option-${option.value}`}
                onSelect={() => setChosen(option.value)}
                className={cn(
                  'justify-between px-4 py-3 text-style-pre-body-05 text-text-secondary [&_svg]:size-6',
                  option.value === chosen && 'bg-background-secondary',
                )}
              >
                {option.label}
                {option.value === chosen && <CheckIcon aria-hidden />}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DialogFooter className="justify-center gap-2 pt-0 sm:justify-center">
          <Button
            variant="outlineBlack"
            shape="round"
            size="md"
            className="min-w-20"
            onClick={onClose}
          >
            {text.cancel}
          </Button>
          <Button
            variant="solidBlack"
            shape="round"
            size="md"
            className="min-w-20"
            data-testid="entry-period-submit"
            disabled={!ready}
            onClick={() => {
              if (chosen !== null && ready) onPick(chosen);
            }}
          >
            {text.submit}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
