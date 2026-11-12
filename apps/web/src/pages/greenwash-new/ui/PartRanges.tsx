// 파트별 쪽 범위 카드의 몸(밴드 FW1b ②, 시안 GW-02_r1 카드 2): 칠할 파트 고르기, 썸네일, 범례, 파트마다 글자 칸, 점검할 쪽 안내.
// 칠할 파트 고르기(밴드 FW2 ⓪, 디자인 대조 물음 3·sid:MARC-ISSUE-99 6): 시안처럼 role="radiogroup" + role="radio"·aria-checked 의 알약 셋(md 36).
//   키트 radio-group 은 동그라미 꼴이라 role 만 빌려 쓴다. 방향키(←↑ 앞, →↓ 뒤, Home·End)로 고르며 초점을 옮긴다(roving tabindex:
//   고른 것만 Tab 으로 닿는다). 고른 것은 outlineBlack 1px + 글자 Bold.
// 파트 칸은 하나 이상이면 된다(2026-10-16 사용자 결정): 필수 점·aria-required 가 없고, 셋 다 빈 채 시작하면 묶음 아래에 오류.
// 칸 id 는 쓰는 쪽이 useId 로 지은 idBase 에서 나온다(고정 id 를 쓰지 않는다). 시험 표지 data-testid 는 그대로다.
import { useRef } from 'react';
import type { KeyboardEvent } from 'react';

import { Input } from '@marcspon/ui/components/input';
import { cn } from '@marcspon/ui/lib/utils';

import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import {
  PART_KEYS,
  formatPageRange,
  overlapOf,
  partsOfPage,
} from '../../../entities/greenwash/model/index.ts';
import type {
  PageRangeError,
  PartKey,
} from '../../../entities/greenwash/model/index.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import type { NewCheckForm } from '../hooks/index.ts';
import { PageThumbnails } from './PageThumbnails.tsx';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from './formRows.ts';
import { OVERLAP_LOOK, PART_LOOK } from './partLook.ts';

const words = GW_TEXT.newCheck.parts;

export function PartRanges({
  form,
  openPdf,
  idBase,
}: {
  form: NewCheckForm;
  openPdf: OpenPdf;
  /** 칸 id 의 앞(쓰는 쪽이 useId 로 짓는다). 칸 id 는 `${idBase}-${파트}`. */
  idBase: string;
}) {
  const document = form.document;
  const pills = useRef<Partial<Record<PartKey, HTMLButtonElement | null>>>({});
  const noParts = form.problems.some((problem) => problem.code === 'no_parts');
  const noPartsId = `${idBase}-no-parts`;
  const onPillKey = (event: KeyboardEvent<HTMLButtonElement>) => {
    const at = PART_KEYS.indexOf(form.activePart);
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
    const key = PART_KEYS[next]!;
    form.setActivePart(key);
    pills.current[key]?.focus();
  };
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <div
          role="radiogroup"
          aria-label={words.groupLabel}
          className="flex flex-wrap items-center gap-2"
        >
          {PART_KEYS.map((key) => {
            const checked = form.activePart === key;
            return (
              <Button
                key={key}
                ref={(element) => {
                  pills.current[key] = element;
                }}
                role="radio"
                aria-checked={checked}
                tabIndex={checked ? 0 : -1}
                variant={checked ? 'outlineBlack' : 'outlineGrey'}
                shape="round"
                size="md"
                data-part-key={key}
                // 안 고른 칩: 1px border-tertiary · 좌우 14(시안 .g-part, GW3R2 SC4 — 키트 outlineGrey 의 10% 회색 틀보다 짙다)
                className={
                  checked ? 'font-bold px-3.5' : 'border-border-tertiary px-3.5'
                }
                onClick={() => form.setActivePart(key)}
                onKeyDown={onPillKey}
              >
                <span
                  aria-hidden
                  className={cn(
                    'mr-1 size-2 shrink-0 rounded-full',
                    PART_LOOK[key].swatch,
                  )}
                />
                {words.names[key]}
                <span className="ml-1 text-text-tertiary">
                  {words.pageCount(form.fields[key].pages.length)}
                </span>
              </Button>
            );
          })}
        </div>
        <span className="ml-auto text-style-pre-caption-03 text-text-tertiary">
          {words.activeHint(words.names[form.activePart])}
        </span>
      </div>
      {document?.hasText && (
        <PageThumbnails
          file={document.file}
          pageCount={document.pageCount}
          form={form}
          openPdf={openPdf}
        />
      )}
      {/* 범례: 이름을 따로 달지 않는다(파트 고르기 묶음과 같은 이름이 겹쳤다. sid:MARC-ISSUE-99 6). */}
      <ul className="m-0 flex list-none flex-wrap gap-4 p-0 text-style-pre-caption-03 text-text-tertiary">
        {PART_KEYS.map((key) => (
          <li key={key} className="flex items-center gap-1.5">
            <span
              aria-hidden
              className={cn('size-3 rounded-sm', PART_LOOK[key].swatch)}
            />
            {words.names[key]}
          </li>
        ))}
        <li className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn('box-border size-3 rounded-sm', OVERLAP_LOOK.swatch)}
          />
          {words.legendOverlap}
        </li>
      </ul>
      {/* 파트 없음 오류는 초점이 가는 첫 칸(CEO)의 aria-describedby 에 잇는다(감독 R2). */}
      <div className={FORM_ROWS_CLASS}>
        {PART_KEYS.map((key) => (
          <PartField
            key={key}
            part={key}
            form={form}
            id={`${idBase}-${key}`}
            extraDescribedBy={
              noParts && key === PART_KEYS[0] ? noPartsId : undefined
            }
          />
        ))}
      </div>
      {noParts && (
        <p
          id={noPartsId}
          data-testid="no-parts"
          className="m-0 text-style-pre-caption-03 text-support-error"
        >
          {GW_TEXT.newCheck.problems.no_parts}
        </p>
      )}
      <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
        {words.rangeHelp}
      </p>
      {document && (
        <PageInfo icon={<PageInfoIcon />} data-testid="checked-pages">
          {words.checked(form.checkedPages, document.pageCount)}
        </PageInfo>
      )}
    </>
  );
}

function PartField({
  part,
  form,
  id,
  extraDescribedBy,
}: {
  part: PartKey;
  form: NewCheckForm;
  id: string;
  /** 칸 밖 오류(파트 없음)의 id. */
  extraDescribedBy?: string;
}) {
  const field = form.fields[part];
  const errorId = `${id}-error`;
  const overlap = overlapOf(form.parts, part);
  const others = PART_KEYS.filter(
    (key) =>
      key !== part &&
      overlap.some((page) => partsOfPage(form.parts, page).includes(key)),
  ).map((key) => words.names[key]);
  return (
    <div className={FORM_ROW_CLASS}>
      <label htmlFor={id} className={FORM_LABEL_CLASS}>
        {words.names[part]}
      </label>
      <div className={cn(FORM_VALUE_CLASS, 'flex-col justify-center gap-1')}>
        <div className="flex flex-wrap items-center gap-3">
          <Input
            id={id}
            value={field.text}
            onChange={(event) => form.setPartText(part, event.target.value)}
            aria-invalid={field.error ? true : undefined}
            aria-describedby={
              [field.error ? errorId : null, extraDescribedBy ?? null]
                .filter(Boolean)
                .join(' ') || undefined
            }
            className="w-72"
          />
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {words.fieldMeta(
              field.pages.length,
              overlap.length === 0 ? '' : formatPageRange(overlap),
              others,
            )}
          </span>
        </div>
        {field.error && (
          <p
            id={errorId}
            data-testid={`gw-part-${part}-error`}
            className="m-0 text-style-pre-caption-03 text-support-error"
          >
            {rangeErrorText(field.error)}
          </p>
        )}
      </div>
    </div>
  );
}

/** 쪽 범위 오류 → 문구 표의 글. */
export function rangeErrorText(error: PageRangeError): string {
  const text = words.rangeError;
  switch (error.code) {
    case 'over_page_count':
      return error.documentKnown ?
          text.over(error.page, error.pageCount)
        : text.overMax(error.pageCount);
    case 'reversed':
      return text.reversed(error.from, error.to);
    case 'zero':
      return text.zero;
    case 'negative':
      return text.negative;
    case 'not_number':
      return text.not_number(error.token);
  }
}
