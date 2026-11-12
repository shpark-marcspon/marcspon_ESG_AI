// AI 설정의 단계 카드(밴드 AD2W ②④ — 디자인 판 AD-02_r3 「단계 카드(고른 칸 하나)」). 도메인을 모른다: 칸 이름·글·메모·안내 글은 모두 props 로 받는다
//   (출력절 띠의 머리 글 OUTPUT_NOTE_HEAD 하나만 모듈 공통이라 여기 둔다 — 밴드 IRW8).
//   짜임은 시안 v148 .e-formrows 세 줄(라벨 칸 | 값 칸 — GW3R B10, 둘레 상자 없음 — 바깥 카드가 감싼다):
//   - 「단계」: 칸 이름(16/700) + KEY 알약(대문자 — lowerKey 면 그대로) + 고침 꼬리표(edited).
//   - 「프롬프트」: 글 칸 위 ⚠ 출력절 띠(출력절이 있는 칸만 — 머리 글 + 모듈 outputNote 두 줄, 경고가 아닌 안내라 role 없음, 디자인 74 · 밴드 IRW8)·
//     글 칸(12) — 아래 글자 수 줄·출력절 바뀜 경고·처음 글 그대로 줄.
//     그 아래 모듈 안내 줄(note — 데이터 검증 입력 글 자리 안내, 밴드 DVA2 K1. 없으면 0).
//   - 「메모」: 두 줄 글 칸(GW3R A12·B15) — 아래 글자 수 줄·안내. 오류 글이 있으면 그 칸 빨강 테두리 + 아래 빨강 줄.
//     ⚠ 아이콘 색은 support-warning-accent(밴드 LK2 §7 B14 — 띠 바탕 그대로).
//   packages/ui Input·Textarea 기본값은 고치지 않고 쓰는 자리 className 으로 덮는다.
//   - readOnly 면 글·메모를 읽기만(칸은 그대로 보이고 고칠 수 없다).
//   - flow(밴드 PF1 — 시안 AD-02_r3 「처리 흐름」 소제목 + 띠): 있으면 줄 묶음(단계 줄) 바로 앞에 그린다 — 바깥 카드의 직속 자식이라 카드 안 간격을 그대로 받는다.
import type { ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Textarea } from '@marcspon/ui/components/textarea';
import { cn } from '@marcspon/ui/lib/utils';

import {
  FORM_LABEL_LOOK,
  FORM_ROWS_LOOK,
  FORM_ROW_LOOK,
  FORM_VALUE_LOOK,
} from './ModelCard.tsx';

/** 출력절 띠의 머리 글(모듈 공통 — 몸 글은 outputNote). */
const OUTPUT_NOTE_HEAD = '출력 형식 절은 고치지 마세요';

export interface PromptCardProps {
  /** 칸 이름(서버 label). */
  title: string;
  /** 칸 KEY(머리 곁 회색 글). */
  tag: string;
  /** KEY 를 소문자 그대로(기본은 대문자). */
  lowerKey?: boolean;
  /** 고친 칸의 꼬리표 글(없으면 null). */
  edited: string | null;
  readOnly: boolean;
  /** 첫 줄 라벨 칸 글(「단계」). */
  stepLabel: string;
  textLabel: string;
  text: string;
  textCount: string;
  textError: string | null;
  /** 글 칸 아래 안내 한 줄(모듈 글 — 없거나 null 이면 줄 0, 밴드 DVA2 K1). */
  note?: string | null;
  /** 출력절 안내(띠의 몸 글 — 출력절이 없는 칸은 null, 띠 0). */
  outputNote: string | null;
  /** 출력절이 글에 없을 때의 경고(없으면 null). */
  outputLost: string | null;
  /** 안 고친 칸의 줄(고쳤으면 null). */
  untouched: string | null;
  memoLabel: string;
  memo: string;
  memoCount: string;
  memoError: string | null;
  memoNote: string;
  /** 머리 아래 자리(판 바탕 줄 등). */
  children?: ReactNode;
  /** 단계 줄 앞 자리(모듈의 처리 흐름 — 없으면 없음). */
  flow?: ReactNode;
  onText?(text: string): void;
  onMemo?(memo: string): void;
}

function Line({
  text,
  tone = 'quiet',
  testId,
}: {
  text: string | null;
  tone?: 'quiet' | 'error' | 'warn';
  testId?: string;
}) {
  if (text === null) return null;
  return (
    <p
      role={tone === 'error' ? 'alert' : undefined}
      data-testid={testId}
      className={cn(
        'm-0 text-style-pre-caption-03',
        tone === 'error' ? 'text-support-error-accent'
        : tone === 'warn' ? 'text-support-orange-dark'
        : 'text-text-tertiary',
      )}
    >
      {text}
    </p>
  );
}

export function PromptCard({
  title,
  tag,
  lowerKey = false,
  edited,
  readOnly,
  stepLabel,
  textLabel,
  text,
  textCount,
  textError,
  note = null,
  outputNote,
  outputLost,
  untouched,
  memoLabel,
  memo,
  memoCount,
  memoError,
  memoNote,
  children,
  flow,
  onText,
  onMemo,
}: PromptCardProps) {
  const rows = (
    <section
      aria-label={title}
      data-card="prompt-slot"
      className={FORM_ROWS_LOOK}
    >
      <div className={FORM_ROW_LOOK}>
        <span className={FORM_LABEL_LOOK}>{stepLabel}</span>
        <div className={FORM_VALUE_LOOK}>
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="m-0 text-style-pre-body-01 text-text-primary">
              {title}
            </h4>
            <span
              data-testid="slot-key"
              className={cn(
                'rounded-control bg-background-secondary px-1 text-style-pre-caption-02 text-text-tertiary',
                !lowerKey && 'uppercase',
              )}
            >
              {tag}
            </span>
            {edited !== null && (
              <span
                data-testid="slot-edited"
                className="text-style-pre-caption-02 text-support-orange"
              >
                {edited}
              </span>
            )}
          </div>
          {children}
        </div>
      </div>
      <div className={FORM_ROW_LOOK}>
        <span className={cn(FORM_LABEL_LOOK, 'items-start pt-6')}>
          {textLabel}
        </span>
        <div className={FORM_VALUE_LOOK}>
          {outputNote !== null && (
            <div className="flex items-start gap-2 rounded-component bg-support-warning-subtle px-4 py-3">
              <CircleWarningIcon
                aria-hidden
                className="size-5 shrink-0 text-support-warning-accent"
              />
              <div className="flex min-w-0 flex-col gap-0.5">
                <p className="m-0 text-style-pre-body-05 text-text-primary">
                  {OUTPUT_NOTE_HEAD}
                </p>
                <p
                  data-testid="output-note"
                  className="m-0 text-style-pre-med-04 text-text-secondary"
                >
                  {outputNote}
                </p>
              </div>
            </div>
          )}
          <Textarea
            aria-label={`${title} ${textLabel}`}
            aria-invalid={textError ? true : undefined}
            readOnly={readOnly}
            value={text}
            rows={12}
            onChange={(event) => onText?.(event.target.value)}
            className={cn(
              'w-full px-4 py-3 font-body text-style-pre-caption-03',
              textError && 'border-support-error-accent',
            )}
          />
          <div className="flex flex-col gap-0.5">
            <Line text={textCount} testId="text-count" />
            <Line text={textError} tone="error" testId="text-error" />
            <Line text={outputLost} tone="warn" testId="output-lost" />
            <Line text={untouched} />
            <Line text={note} testId="prompt-note" />
          </div>
        </div>
      </div>
      <div className={FORM_ROW_LOOK}>
        <span className={cn(FORM_LABEL_LOOK, 'items-start pt-6')}>
          {memoLabel}
        </span>
        <div className={FORM_VALUE_LOOK}>
          <Textarea
            aria-label={`${title} ${memoLabel}`}
            aria-invalid={memoError ? true : undefined}
            readOnly={readOnly}
            value={memo}
            rows={2}
            onChange={(event) => onMemo?.(event.target.value)}
            className={cn(
              'min-h-16 w-full px-4 py-2',
              memoError && 'border-support-error-accent',
            )}
          />
          <div className="flex flex-col gap-0.5">
            <Line text={memoCount} testId="memo-count" />
            <Line text={memoError} tone="error" testId="memo-error" />
            <Line text={memoNote} />
          </div>
        </div>
      </div>
    </section>
  );
  return (
    <>
      {flow}
      {rows}
    </>
  );
}
