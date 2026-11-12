// AI 설정의 저장 창(밴드 AD2W ③ — 디자인 판 AD-02_r3 모달 ①②③, 입력 있는 모달이라 왼쪽 정렬). 도메인을 모른다: 글·값·오류는 모두 props.
//   - 본문 · 「고친 것」 줄(글 하나, 또는 목록 — 항목마다 한 줄, 밴드 AP1W) · 버전 번호(추정 — 「자동으로 붙어요」) · 버전 이름(칸 아래 오류) · 버전 메모(칸 아래 오류) · 실패 줄 · [취소] [저장].
//   - [저장]은 canSave 가 거짓이거나 보내는 중(pending)이면 꺼진다: aria-disabled 이고 누름·Enter 처리기가 onSave 를 부르지 않는다(네이티브 disabled 0 —
//     Tab 에 남는다, AD-02 의 끈 단추와 같은 꼴). 이름 칸의 Enter 는 form 제출 = [저장] 누름과 같은 길.
//   - 보내는 중에는 창이 닫히지 않는다(덮개 누름·Esc·[취소]).
import type { FormEvent } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import { Button, buttonVariants } from '../../button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../dialog/index.ts';

export interface SaveDialogProps {
  title: string;
  body: string;
  changesLabel: string;
  /** 고친 것(없으면 null — 복제). 글이면 한 줄, 목록이면 항목마다 한 줄. */
  changes: string | readonly string[] | null;
  numberLabel: string;
  number: string;
  numberNote: string;
  nameLabel: string;
  nameNote: string;
  name: string;
  nameError: string | null;
  memoLabel: string;
  memoNote: string;
  memo: string;
  memoError: string | null;
  /** 보내기 실패 줄(없으면 null). */
  failure: string | null;
  cancel: string;
  confirm: string;
  canSave: boolean;
  pending: boolean;
  onName(name: string): void;
  onMemo(memo: string): void;
  onSave(): void;
  onClose(): void;
}

function ErrorLine({ text, testId }: { text: string | null; testId: string }) {
  if (text === null) return null;
  return (
    <p
      role="alert"
      data-testid={testId}
      className="m-0 flex items-center gap-1 text-style-pre-caption-03 text-support-error-accent [&_svg]:size-4 [&_svg]:shrink-0"
    >
      <CircleWarningIcon aria-hidden />
      {text}
    </p>
  );
}

export function SaveDialog({
  title,
  body,
  changesLabel,
  changes,
  numberLabel,
  number,
  numberNote,
  nameLabel,
  nameNote,
  name,
  nameError,
  memoLabel,
  memoNote,
  memo,
  memoError,
  failure,
  cancel,
  confirm,
  canSave,
  pending,
  onName,
  onMemo,
  onSave,
  onClose,
}: SaveDialogProps) {
  const off = !canSave || pending;
  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (off) return;
    onSave();
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !pending) onClose();
      }}
    >
      <DialogContent size="sm" data-testid="save-dialog">
        <form className="flex flex-col gap-4 text-left" onSubmit={submit}>
          <DialogTitle className="text-left text-style-pre-heading-02">
            {title}
          </DialogTitle>
          <DialogDescription className="m-0 text-left text-style-pre-body-06 text-text-secondary">
            {body}
          </DialogDescription>
          {changes !== null && (
            <div className="flex flex-col gap-1">
              <span className="text-style-pre-caption-02 text-text-tertiary">
                {changesLabel}
              </span>
              {typeof changes === 'string' ?
                <p
                  data-testid="save-changes"
                  className="m-0 text-style-pre-body-06 text-text-primary"
                >
                  {changes}
                </p>
              : <ul
                  data-testid="save-changes"
                  className="m-0 flex flex-col gap-1 pl-5 text-style-pre-body-06 text-text-primary"
                >
                  {changes.map((item, index) => (
                    <li key={`${index}:${item}`} data-testid="changed-item">
                      {item}
                    </li>
                  ))}
                </ul>
              }
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className="text-style-pre-caption-02 text-text-tertiary">
              {numberLabel}
            </span>
            <b data-testid="save-number" className="text-style-pre-body-05">
              {number}
            </b>
            <span className="text-style-pre-caption-03 text-text-tertiary">
              {numberNote}
            </span>
          </div>
          <label className="flex flex-col gap-1">
            <span className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary">
              {nameLabel}
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {nameNote}
              </span>
            </span>
            <Input
              aria-label={nameLabel}
              aria-invalid={nameError ? true : undefined}
              value={name}
              onChange={(event) => onName(event.target.value)}
              className={cn(
                'w-full',
                nameError && 'border-support-error-accent',
              )}
            />
          </label>
          <ErrorLine text={nameError} testId="name-error" />
          <label className="flex flex-col gap-1">
            <span className="flex items-center gap-2 text-style-pre-body-06 text-text-secondary">
              {memoLabel}
              <span className="text-style-pre-caption-03 text-text-tertiary">
                {memoNote}
              </span>
            </span>
            <Input
              aria-label={memoLabel}
              aria-invalid={memoError ? true : undefined}
              value={memo}
              onChange={(event) => onMemo(event.target.value)}
              className={cn(
                'w-full',
                memoError && 'border-support-error-accent',
              )}
            />
          </label>
          <ErrorLine text={memoError} testId="memo-error" />
          <ErrorLine text={failure} testId="save-failure" />
          <DialogFooter>
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              onClick={() => {
                if (!pending) onClose();
              }}
            >
              {cancel}
            </Button>
            <button
              type="submit"
              aria-disabled={off || undefined}
              aria-busy={pending || undefined}
              className={cn(
                buttonVariants({
                  variant: 'solidBlack',
                  shape: 'round',
                  size: 'md',
                }),
                off && 'cursor-not-allowed opacity-40',
              )}
              onClick={(event) => {
                event.preventDefault();
                submit();
              }}
            >
              {confirm}
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
