// S3-14 수정 사유 작성 — 제외·복구 공용(밴드 S3W3b ② — 값 파일 3절, Figma 29426:48753). pages 끼리 import 0(L 규칙)이라 ghg-inventory 의 EntryReasonDialog 를 옮겨 적었다.
//   폭 640 · 주황 주의 띠 · 안내 글 · 칸 「내용」 · [취소][확인]. 첫 초점은 칸. <form onSubmit> 이라 Enter 가 확인.
//   [확인] 늘 켬 · 누를 때 앞뒤 빈칸을 걷은 글로 검사: 빈 → 칸 글 · ROW_REASON_MAX 넘음 → 칸 글 · 둘 다 요청 0.
//   서버 422 fields.reason 은 problem prop 으로 같은 칸에 돌아온다. 원본에 없는 칸: failure(창 안 단추 위 한 줄 — 값 파일 4절).
//   계수 수정(S3W3c2)이 더한 것 둘: initial(다시 열 때 앞서 쓴 사유 — custom.* 거절 뒤 간직) · returnFocus 가 false 면 초점을 옮기지 않는다(부르는 쪽이 다시 읽은 뒤 옮긴다). 제외·복구는 둘 다 안 쓴다.
import { useRef, useState } from 'react';
import type { FormEvent } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';

import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import {
  ROW_REASON_MAX,
  reasonFault,
} from '../../../entities/ghg-scope3/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { PageInfo } from '../../../shared/ui/page-info/index.ts';

const words = S3_TEXT.rowEdit.reason;
const FIELD = 's3-reason-input';

const faultText = (text: string): string | null => {
  const fault = reasonFault(text);
  if (fault === null) return null;
  return fault === 'required' ? words.required : words.tooLong(ROW_REASON_MAX);
};

export interface RowReasonDialogProps {
  /** 요청을 기다리는 동안(단추·칸 끔, 닫기 막음). */
  busy: boolean;
  /** 서버가 사유를 거절했을 때 칸 아래 글. */
  problem: string | null;
  /** 창 안 실패 한 줄. */
  failure: string | null;
  /** 닫힐 때 초점을 줄 자리(닫힐 때 찾는다). null 이면 공용 기본, false 면 옮기지 않음. */
  returnFocus(): HTMLElement | null | false;
  /** 칸의 처음 글(없으면 빈 칸). */
  initial?: string;
  onConfirm(reason: string): void;
  onClose(): void;
}

export function RowReasonDialog({
  busy,
  problem,
  failure,
  returnFocus,
  initial = '',
  onConfirm,
  onClose,
}: RowReasonDialogProps) {
  const [text, setText] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  /** 서버 글은 고치기 시작하면 걷는다(다시 누르면 부르는 쪽이 새로 준다). */
  const [typed, setTyped] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const shown = error ?? (typed ? null : problem);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (busy) return;
    const why = faultText(text);
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
        data-testid="s3-reason"
        className="w-[640px] max-w-[calc(100vw-64px)]"
        onCloseAutoFocus={(event) => {
          const target = returnFocus();
          if (target === null) return;
          event.preventDefault();
          if (target) target.focus();
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
            data-testid="s3-reason-warning"
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
          {failure !== null && (
            <p
              role="alert"
              data-testid="s3-reason-failed"
              className="m-0 text-center text-style-pre-caption-03 text-support-error-accent"
            >
              {failure}
            </p>
          )}
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
