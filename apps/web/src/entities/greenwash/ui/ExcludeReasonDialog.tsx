// 제외 사유 모달(밴드 FW1 ②, 시안 GW-05a). 문장을 제외할 때 사유를 받는다(사유 필수).
//
// - 문장 인용(quote), 사유 라디오 넷(키트 radio-group, 글자는 문구 표), 설명(키트 textarea), 안내 한 줄, [취소]·[제외].
// - 사유 없이 [제외] 를 누르면 사유 칸 아래 오류가 보인다. [제외] 버튼은 꺼 두지 않는다(무엇이 빠졌는지 말해 준다).
// - 값은 onSubmit({ reason, note }) 로만 낸다. 모달을 닫을지는 쓰는 쪽이 open 으로 정한다(저장·흐름을 모른다. 발주서 §1-5).
// - 쓰는 쪽이 사유 글을 짓다 막히면(「기타」 + 빈 설명) noteError 를 주어 설명 칸 아래에 오류를 보인다(밴드 FW2 ④).
// - 닫히면 열기 전 초점 자리로 돌린다: 공용 DialogContent 의 기본 동작(밴드 FW2 ⓪, sid:MARC-ISSUE-97 1번. Trigger 없이 open 으로 열어도).
// - 인용 문장은 DialogDescription 이라 대화 상자의 설명으로 이어진다.
// - 입력 상태는 열려 있는 동안 남는다. 열린 채 다른 문장으로 바뀌면 쓰는 쪽이 key(문장 id)를 주어 새로 그리게 한다.
// - 제목은 일반 모달 꼴(shared/ui/dialog 의 DialogTitle, Bold 24).
// - 버튼은 디자인 시스템 Modal 카드를 따른다: [취소] outlineBlack 알약 + [확인] solidBlack 알약(md).
//   시안 05a 는 [취소] Solid Grey + [제외] Solid Black 각이다 — 어긋남은 보고 「디자인 트랙에 물을 것」.
// - 입력 상태(고른 사유·설명·오류)는 모달 안쪽 부품에 둔다. 닫히면 Radix 가 안쪽을 내려 다음에 열 때 비어 있다.
// 사유 값 이름 not_claim·evidence_in_doc·other 는 GC1 초안 전이다(무효 조건: 계약이 이름을 정하면 바꾼다).
// 「등급이 맞지 않음」(wrong_level)은 고르는 목록에서 뺐다(시안 댓글, sid:MARC-ENT-603). 사유는 글로 저장돼
// (excludeReasonText) 옛 실행의 그 사유 글은 그대로 보인다 — 키로 읽는 자리가 없다.
import * as React from 'react';

import { Label } from '@marcspon/ui/components/label';
import {
  RadioGroup,
  RadioGroupItem,
} from '@marcspon/ui/components/radio-group';
import { Textarea } from '@marcspon/ui/components/textarea';

import { Button } from '../../../shared/ui/button/index.ts';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from '../../../shared/ui/dialog/index.ts';
import { GW_TEXT } from '../config/text.ts';
import type { Wording } from '../config/text.ts';
import { withDefaults } from './withDefaults.ts';

export const EXCLUDE_REASONS = [
  'not_claim',
  'evidence_in_doc',
  'other',
] as const;
export type ExcludeReason = (typeof EXCLUDE_REASONS)[number];

export interface ExcludeReasonValue {
  reason: ExcludeReason;
  /** 설명. 비었으면 빈 글자(앞뒤 공백은 지운다). */
  note: string;
}

type ExcludeText = Wording<(typeof GW_TEXT)['exclude']>;

export interface ExcludeReasonDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 인용할 문장(「…」 꼴은 쓰는 쪽이 정한다). */
  quote: React.ReactNode;
  /** 인용 뒤 붙는 자리 글자(「기후·환경 30쪽 · Mid」). */
  quoteMeta?: React.ReactNode;
  /** 사유를 골라 [제외] 를 눌렀을 때 한 번 부른다. */
  onSubmit: (value: ExcludeReasonValue) => void;
  /**
   * 설명 칸의 오류(밴드 FW2 ④). 쓰는 쪽이 사유 글을 짓다 막히면(「기타」 + 빈 설명) 준다.
   * 주면 설명 칸 아래에 role="alert" 로 보이고 칸에 aria-invalid·aria-describedby 를 단다.
   */
  noteError?: React.ReactNode;
  /** 설명을 고칠 때마다 부른다(쓰는 쪽이 noteError 를 지우는 자리 — 밴드 FW2 ⑤). */
  onNoteChange?: (note: string) => void;
  /** 문구를 바꾼다(문구 표 위에 덮는다). */
  text?: Partial<Omit<ExcludeText, 'reasons'>> & {
    reasons?: Partial<Record<ExcludeReason, string>>;
  };
}

function ExcludeForm({
  quote,
  quoteMeta,
  onSubmit,
  noteError,
  onNoteChange,
  words,
}: Pick<
  ExcludeReasonDialogProps,
  'quote' | 'quoteMeta' | 'onSubmit' | 'noteError' | 'onNoteChange'
> & {
  words: ExcludeText;
}) {
  // 고르기 전은 null(sid:MARC-ISSUE-97 3: '' 갈래를 없애 사유 필수 검사가 빠지면 타입 오류가 나게)
  const [reason, setReason] = React.useState<ExcludeReason | null>(null);
  const [note, setNote] = React.useState('');
  const [missing, setMissing] = React.useState(false);
  const id = React.useId();
  const legendId = `${id}-legend`;
  const errorId = `${id}-error`;
  const noteId = `${id}-note`;
  const noteErrorId = `${id}-note-error`;
  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (reason === null) {
          setMissing(true);
          return;
        }
        onSubmit({ reason, note: note.trim() });
      }}
    >
      {/* 인용 문장이 이 대화 상자의 설명이다(aria-describedby 로 이어진다) */}
      <DialogDescription asChild>
        <p className="m-0 rounded-component bg-background-secondary px-4 py-3 text-style-pre-body-05 text-text-primary">
          {quote}
          {quoteMeta != null && (
            <span className="text-text-tertiary"> · {quoteMeta}</span>
          )}
        </p>
      </DialogDescription>
      <div className="flex flex-col gap-2">
        <span
          id={legendId}
          className="inline-flex items-center gap-1 text-style-pre-body-05 text-text-secondary"
        >
          {words.reasonLegend}
          <span aria-hidden className="size-1 rounded-full bg-text-brand" />
        </span>
        <RadioGroup
          aria-labelledby={legendId}
          aria-required
          aria-invalid={missing || undefined}
          aria-describedby={missing ? errorId : undefined}
          value={reason ?? ''}
          onValueChange={(value) => {
            setReason(value as ExcludeReason);
            setMissing(false);
          }}
        >
          {EXCLUDE_REASONS.map((value) => (
            <div key={value} className="flex items-center gap-2">
              <RadioGroupItem id={`${id}-${value}`} value={value} />
              <Label
                htmlFor={`${id}-${value}`}
                className="cursor-pointer text-style-pre-body-06 text-text-secondary"
              >
                {words.reasons[value]}
              </Label>
            </div>
          ))}
        </RadioGroup>
        {missing && (
          <p
            id={errorId}
            role="alert"
            className="m-0 text-style-pre-caption-02 text-support-error"
          >
            {words.reasonRequired}
          </p>
        )}
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor={noteId} className="text-text-secondary">
          {words.noteLabel}
        </Label>
        <Textarea
          id={noteId}
          value={note}
          aria-invalid={noteError != null || undefined}
          aria-describedby={noteError != null ? noteErrorId : undefined}
          onChange={(event) => {
            setNote(event.target.value);
            onNoteChange?.(event.target.value);
          }}
        />
        {noteError != null && (
          <p
            id={noteErrorId}
            role="alert"
            className="m-0 text-style-pre-caption-02 text-support-error"
          >
            {noteError}
          </p>
        )}
      </div>
      <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
        {words.notice}
      </p>
      <DialogFooter>
        <DialogClose asChild>
          <Button variant="outlineBlack" shape="round" size="md">
            {words.cancel}
          </Button>
        </DialogClose>
        <Button type="submit" variant="solidBlack" shape="round" size="md">
          {words.submit}
        </Button>
      </DialogFooter>
    </form>
  );
}

function ExcludeReasonDialog({
  open,
  onOpenChange,
  quote,
  quoteMeta,
  onSubmit,
  noteError,
  onNoteChange,
  text,
}: ExcludeReasonDialogProps) {
  const base = GW_TEXT.exclude;
  const { reasons: reasonText, ...rest } = text ?? {};
  const words: ExcludeText = {
    ...withDefaults<Omit<ExcludeText, 'reasons'>>(base, rest),
    reasons: withDefaults<ExcludeText['reasons']>(base.reasons, reasonText),
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent size="md">
        <DialogTitle>{words.title}</DialogTitle>
        <ExcludeForm
          quote={quote}
          quoteMeta={quoteMeta}
          onSubmit={onSubmit}
          noteError={noteError}
          onNoteChange={onNoteChange}
          words={words}
        />
      </DialogContent>
    </Dialog>
  );
}
ExcludeReasonDialog.displayName = 'ExcludeReasonDialog';

export { ExcludeReasonDialog };
