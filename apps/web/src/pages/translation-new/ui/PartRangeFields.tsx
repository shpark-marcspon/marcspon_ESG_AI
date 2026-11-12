// 파트별 쪽 범위의 칸들(밴드 TRW0a ②, 시안 TR-02·02a 「2. 파트별 쪽 범위」, 결정 sid:MARC-ENT-392). 모양 부품: props 만 받는다.
// - 칠할 파트 고르기: role="radiogroup" + role="radio"·aria-checked 의 알약 셋(그린워싱 PartRanges 꼴을 따라 지음 — 가져오지 않는다).
//   방향키(←↑ 앞, →↓ 뒤, Home·End)로 고르며 초점을 옮긴다(roving tabindex). 알약 옆 글자는 그 파트의 쪽 수.
// - 차례(밴드 TRP2 TE7, 시안 TR-02): 칩 줄 → grid(쪽 칸·범례, 부르는 쪽이 넘김) → 글자 칸(양식 줄 셋, 이름 160 · 값 Input 180 + 아래 한 줄).
// - 파트마다 글자 칸 하나(「1~3」). 칸 아래 한 줄: 오류(aria-invalid + aria-describedby) > CEO 한도 넘음(6쪽 고정 — 쪽 범위 오류 갈래) > 겹침 > 쪽 수 > 빈 칸 안내.
//   오류 글은 갈래마다 config/text.ts(TR-02a · e9 답).
// - 「번역할 쪽: n쪽 / 마지막 쪽 · 파트 k개라 번역을 k번 해요(…)」는 쪽을 넣은 파트가 있을 때만.
// - [TRW1a ② 감독 판단 1] 쪽 수를 모르면(pageCount null — 태그 없음·못 셈, TRP6) 「/ 마지막 쪽」을 빼고, 칸 아래에 「쪽 번호는 추출본의 [PAGE n] 기준이에요」.
// - [TRW6 ②] input="pdf" 면 칸 아래 안내 글이 PDF 기준(「[PAGE n]」 글 0 — 페이지 번호는 PDF 뷰어 순서).
import { useId, useRef } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';

import { CircleWarningIcon } from '@marcspon/common/generated/icons/MyIcons';
import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  PART_KEYS,
  ceoError,
  formatRange,
  intersectRange,
  overlapOf,
  pageCountOf,
} from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
  RangeError,
} from '../../../entities/translation/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { PART_LOOK } from './partLook.ts';

const words = TR_TEXT.range;

/** 구간들을 앞에서부터 늘어놓고 겹치거나 맞닿은 것을 하나로 잇는다. */
function mergeRanges(list: readonly Range[]): Range[] {
  const sorted = [...list].sort((a, b) => a.from - b.from);
  const merged: Range[] = [];
  for (const range of sorted) {
    const last = merged.at(-1);
    if (last && range.from <= last.to + 1)
      merged[merged.length - 1] = {
        from: last.from,
        to: Math.max(last.to, range.to),
      };
    else merged.push({ ...range });
  }
  return merged;
}
const names = TR_TEXT.parts.names;

export interface PartRangeFieldsProps {
  /** 추출본의 쪽 수(「번역할 쪽: 41쪽 / 64쪽」의 64). 모르면 null(docx·txt — 서버가 PDF 만 잰다). */
  pageCount: number | null;
  ranges: Readonly<Record<PartKey, Range | null>>;
  texts: Readonly<Record<PartKey, string>>;
  errors: Readonly<Partial<Record<PartKey, RangeError>>>;
  active: PartKey;
  onText(part: PartKey, text: string): void;
  onActive(part: PartKey): void;
  /** 칩 줄과 글자 칸 사이에 둘 것(쪽 칸 + 범례 — 쪽 수를 알 때만. 밴드 TRP2 TE7). */
  grid?: ReactNode;
  /** 입력 꼴(기본 word). pdf 면 help·pageBasis 가 PDF 글(밴드 TRW6 ②). */
  input?: 'word' | 'pdf';
}

/** 오류 글. */
function errorText(error: RangeError): string {
  switch (error.code) {
    case 'comma':
      return words.errors.comma;
    case 'over_last':
      return words.errors.overLast(error.page, error.last);
    case 'order':
      return words.errors.order(error.from, error.to);
    case 'zero':
      return words.errors.zero;
    case 'not_number':
      return words.errors.notNumber(error.token);
    case 'ceo_over_limit':
      return words.errors.ceoOverLimit(error.limit);
  }
}

export function PartRangeFields({
  pageCount,
  ranges,
  texts,
  errors,
  active,
  onText,
  onActive,
  grid,
  input = 'word',
}: PartRangeFieldsProps) {
  const idBase = useId();
  const pdf = input === 'pdf';
  const pills = useRef<Partial<Record<PartKey, HTMLButtonElement | null>>>({});
  const onPillKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const at = PART_KEYS.indexOf(active);
    const last = PART_KEYS.length - 1;
    const next =
      event.key === 'ArrowRight' || event.key === 'ArrowDown' ?
        at === last ?
          0
        : at + 1
      : event.key === 'ArrowLeft' || event.key === 'ArrowUp' ?
        at === 0 ?
          last
        : at - 1
      : event.key === 'Home' ? 0
      : event.key === 'End' ? last
      : null;
    if (next === null) return;
    event.preventDefault();
    const part = PART_KEYS[next]!;
    onActive(part);
    pills.current[part]?.focus();
  };
  const overlapping = overlapOf(ranges).length > 0;
  const filled = PART_KEYS.filter((part) => ranges[part] !== null);
  const total = filled.reduce(
    (sum, part) => sum + pageCountOf(ranges[part]),
    0,
  );
  /** 칸 아래 한 줄: 글과 오류 꼴. */
  const below = (part: PartKey): { text: string; error: boolean } => {
    const range = ranges[part];
    const error = errors[part] ?? (part === 'ceo' ? ceoError(range) : null);
    if (error) return { text: errorText(error), error: true };
    if (range === null) return { text: words.empty, error: false };
    // 겹침 줄은 그린워싱 꼴(sid:MARC-ISSUE-307 · TRW0b): 겹친 쪽 하나(다른 파트들과 겹친 쪽의 합) + 이름 묶음 —
    //   「35쪽 · 7~8쪽은 CEO 메시지와 겹침」, 셋이면 「…쪽은 CEO 메시지와 일반과 겹침」.
    const others = PART_KEYS.filter((other) => other !== part).flatMap(
      (other) => {
        const shared = intersectRange(range, ranges[other]);
        return shared ? [{ other, shared }] : [];
      },
    );
    const withOthers =
      others.length === 0 ?
        []
      : [
          words.overlapWith(
            mergeRanges(others.map(({ shared }) => shared))
              .map(formatRange)
              .join(', '),
            TR_TEXT.parts.withNames(
              others.map(({ other }) => TR_TEXT.parts.names[other]),
            ),
          ),
        ];
    const count = pageCountOf(range);
    return {
      text:
        withOthers.length > 0 ?
          words.overlapRow(count, withOthers)
        : words.pageCount(count),
      error: false,
    };
  };
  /** 칸 하나라도 오류면 help 아래에 고쳐 넣는 꼴을 한 줄 더(시안 TR-02a — 밴드 TRW5). */
  const anyError = PART_KEYS.some((part) => below(part).error);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="radiogroup"
          aria-label={words.groupLabel}
          className="flex flex-wrap items-center gap-2"
        >
          {PART_KEYS.map((part) => {
            const checked = active === part;
            return (
              <Button
                key={part}
                ref={(element) => {
                  pills.current[part] = element;
                }}
                role="radio"
                aria-checked={checked}
                tabIndex={checked ? 0 : -1}
                variant={checked ? 'outlineBlack' : 'outlineGrey'}
                shape="round"
                size="md"
                data-part-key={part}
                // 안 고른 칩 테두리 #D1D5D9 · 좌우 14 · 칩 안 사이 8(밴드 TRP2 TC7 · TRP3 ②, 시안 .g-part)
                className={cn(
                  'gap-2 px-3.5',
                  checked ? 'font-bold' : 'border-border-tertiary',
                )}
                onClick={() => onActive(part)}
                onKeyDown={onPillKey}
              >
                <span
                  aria-hidden
                  className={cn(
                    'size-2.5 shrink-0 rounded-full',
                    PART_LOOK[part].swatch,
                  )}
                />
                {names[part]}
                <span className="font-normal text-text-tertiary">
                  {words.pageCount(pageCountOf(ranges[part]))}
                </span>
              </Button>
            );
          })}
        </div>
        <span className="ml-auto text-style-pre-caption-03 text-text-tertiary">
          {words.activeHint(names[active])}
        </span>
      </div>
      {grid}
      <div className={FORM_ROWS_CLASS}>
        {PART_KEYS.map((part) => {
          const id = `${idBase}-${part}`;
          const line = below(part);
          return (
            <div key={part} className={FORM_ROW_CLASS}>
              <label htmlFor={id} className={FORM_LABEL_CLASS}>
                {names[part]}
              </label>
              <div
                className={cn(
                  FORM_VALUE_CLASS,
                  'flex-col justify-center gap-1',
                )}
              >
                <Input
                  className="w-[180px]"
                  id={id}
                  data-part-field={part}
                  value={texts[part]}
                  placeholder={words.placeholder[part]}
                  aria-invalid={line.error || undefined}
                  aria-describedby={`${id}-below`}
                  onChange={(event) => onText(part, event.target.value)}
                />
                <p
                  id={`${id}-below`}
                  data-below={line.error ? 'error' : 'info'}
                  className={cn(
                    'm-0 text-style-pre-caption-03',
                    line.error ?
                      'flex items-start gap-1 [&_svg]:mt-px [&_svg]:size-4 [&_svg]:shrink-0 text-support-error'
                    : 'text-text-tertiary',
                  )}
                >
                  {line.error && <CircleWarningIcon aria-hidden />}
                  {line.text}
                </p>
              </div>
            </div>
          );
        })}
      </div>
      {overlapping && (
        <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
          {words.overlapNote}
        </p>
      )}
      <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
        {pdf ? TR_TEXT.pdfNew.range.help : words.help}
      </p>
      {anyError && (
        <p
          data-testid="range-help-error"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {words.errorHelp}
        </p>
      )}
      {pageCount === null && (
        <p
          data-testid="range-basis"
          className="m-0 text-style-pre-caption-03 text-text-tertiary"
        >
          {pdf ? TR_TEXT.pdfNew.range.basis : words.pageBasis}
        </p>
      )}
      {/* 기본 톤 안내 상자 안 400 14 #6F7781(밴드 TRP2 TC8, 시안 TR-02 e-info) */}
      {filled.length > 0 && (
        <PageInfo data-testid="range-total" icon={<PageInfoIcon />}>
          <span className="text-style-pre-body-06 text-text-tertiary">
            {pageCount === null ?
              words.totalOpen(
                total,
                filled.map((part) => names[part]),
              )
            : words.total(
                total,
                pageCount,
                filled.map((part) => names[part]),
              )
            }
          </span>
        </PageInfo>
      )}
    </div>
  );
}
