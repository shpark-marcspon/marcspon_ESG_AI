// S11 수정 사유 작성(밴드 W12-3 ③ — Figma 29426:48839 빈 · 29426:48850 입력 중, e6 11-04). 계수 바꿈(S9 뒤)·계수 줄 복구(S12)가 같이 쓴다(Q6).
//   폭 640 · 안쪽 32 · 구획 사이 24 · 제목 18 Bold · 주황 연한 주의 띠(아이콘 16) · 안내 글 회색 14 · 칸 이름 「내용」 · 한 줄 입력 36 · 모서리 8 ·
//   입력 중 테두리 2px(토큰) · 글자 세기 없음(Figma — 「디자인 확인 거리」) · [취소][확인] 가운데.
//   [확인] 늘 켬 · 누를 때 앞뒤 빈칸을 지운 글로 검사: 빈 → 칸 글 · ENTRY_REASON_MAX 넘음 → 칸 글 「500자까지 쓸 수 있어요」 · 둘 다 요청 0.
//   지난 글은 onConfirm(지운 글) — 부르는 쪽이 요청하고, 서버 422 fields.reason 은 problem prop 으로 같은 칸에 돌아온다.
//   <form onSubmit> 이라 Enter 가 확인. 열 때 초점은 칸.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { ENTRY_REASON_MAX } from '../../../entities/ghg/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';

const words = GHG_TEXT.entry.reason;
const FIELD = 'entry-reason-input';

/** 사유 검사(누를 때) — 앞뒤 빈칸을 지운 글 기준. 지나면 null. */
export function reasonProblem(text: string): string | null {
  const trimmed = text.trim();
  if (trimmed === '') return words.required;
  if (trimmed.length > ENTRY_REASON_MAX) return words.tooLong(ENTRY_REASON_MAX);
  return null;
}

export interface EntryReasonDialogProps {
  /** 요청을 기다리는 동안(단추·칸 끔, 닫기 막음). */
  busy: boolean;
  /** 서버가 사유를 거절했을 때 칸 아래 글(부르는 쪽이 준다). */
  problem?: string | null;
  testId?: string;
  /** 닫힐 때 초점을 줄 칸(찾는 때 부름 — 없으면 Radix 기본: 연 단추로). 548 뒤 S9 칸(W12-3 ③b, Y7). */
  returnFocus?(): HTMLElement | null;
  onConfirm(reason: string): void;
  onClose(): void;
}

export function EntryReasonDialog({
  busy,
  problem = null,
  testId = 'entry-reason',
  returnFocus,
  onConfirm,
  onClose,
}: EntryReasonDialogProps) {
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);
  /** 서버 글은 고치기 시작하면 걷는다(다시 누르면 부르는 쪽이 새로 준다). */
  const [typed, setTyped] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const shown = error ?? (typed ? null : problem);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (busy) return;
    const why = reasonProblem(text);
    if (why) {
      setError(why);
      inputRef.current?.focus();
      return;
    }
    setError(null);
    setTyped(false);
    onConfirm(text.trim());
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose();
      }}
    >
      <DialogContent
        size="sm"
        data-testid={testId}
        className="w-[640px] max-w-[calc(100vw-64px)]"
        onCloseAutoFocus={(event) => {
          const target = returnFocus?.();
          if (!target) return;
          event.preventDefault();
          target.focus();
        }}
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-6">
          <DialogTitle className="text-style-pre-heading-02">
            {words.title}
          </DialogTitle>
          <PageInfo
            tone="important"
            icon={<CircleWarningIcon aria-hidden />}
            data-testid="entry-reason-warning"
          >
            {words.warning}
          </PageInfo>
          <p className="m-0 text-style-pre-body-06 text-text-tertiary">
            {words.guide}
          </p>
          <div className="flex flex-col gap-2">
            <label
              htmlFor={FIELD}
              className="text-style-pre-body-05 text-text-secondary"
            >
              {words.label}
            </label>
            <Input
              ref={inputRef}
              id={FIELD}
              data-testid={FIELD}
              placeholder={words.placeholder}
              className="focus:border-2 focus:border-border-secondary"
              value={text}
              disabled={busy}
              aria-invalid={shown !== null || undefined}
              aria-describedby={shown ? `${FIELD}-error` : undefined}
              onChange={(event) => {
                setText(event.target.value);
                setError(null);
                setTyped(true);
              }}
            />
            {shown && (
              <p
                id={`${FIELD}-error`}
                data-testid={`${FIELD}-error`}
                className="m-0 text-style-pre-caption-03 text-support-error-accent"
              >
                {shown}
              </p>
            )}
          </div>
          <DialogFooter className="pt-0">
            <Button
              variant="outlineBlack"
              shape="round"
              size="md"
              disabled={busy}
              onClick={onClose}
            >
              {words.cancel}
            </Button>
            <Button
              type="submit"
              variant="solidBlack"
              shape="round"
              size="md"
              loading={busy}
            >
              {words.confirm}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
