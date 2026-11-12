// 시작 전 확인(밴드 TRW0a ②, 시안 TR-02 「시작 전 확인」). 모양 부품: 넘겨받은 화면 값만 보인다(규모 경로를 부르지 않는다).
// 번역할 쪽(합계 · 파트마다 구간과 쪽 수) · 번역 횟수(파트마다 한 번, 스타일 — A·B 견주기면 두 스타일 분량).
// PDF 입력이면 「머리글 · 꼬리말」 줄 하나 더(밴드 TRW6 ②, 6c v174 TR-P02).
import { cn } from '@marcspon/ui/lib/utils';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { formatRange } from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
} from '../../../entities/translation/model/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_CLASS,
} from '../../../shared/ui/form-rows/index.ts';

const words = TR_TEXT.preflight;
const names = TR_TEXT.parts.names;

export interface PreflightCardProps {
  pages: {
    total: number;
    parts: readonly { part: PartKey; range: Range; count: number }[];
  };
  /** 번역 횟수(파트 수). */
  runs: number;
  style: 'A' | 'B' | 'AB';
  /** 참이면 「머리글 · 꼬리말」 줄(PDF 입력). */
  headerFooter?: boolean;
}

export function PreflightCard({
  pages,
  runs,
  style,
  headerFooter = false,
}: PreflightCardProps) {
  const rows: [string, string, string?][] = [
    [
      words.pages,
      words.pagesValue(
        pages.total,
        pages.parts.map(({ part, range, count }) =>
          words.pagesItem(names[part], formatRange(range), count),
        ),
      ),
    ],
    [
      words.runs,
      style === 'AB' ?
        words.runsCompare(runs, pages.total * 2)
      : words.runsValue(runs, style),
      words.runsNote,
    ],
  ];
  if (headerFooter)
    rows.push([
      TR_TEXT.pdfNew.preflight.headerFooter,
      TR_TEXT.pdfNew.preflight.headerFooterValue,
    ]);
  return (
    <Card data-testid="preflight" className="flex flex-col gap-3">
      <div className="flex items-baseline gap-2">
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.title}
        </h3>
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.lead}
        </span>
      </div>
      {/* 양식 줄(이름 칸 160 · #FAFBFB · 500 14 #6F7781, 값 400 16 — 밴드 TRP2 TC11, 시안 TR-02 「시작 전 확인」) */}
      <dl className={cn('m-0', FORM_ROWS_CLASS)}>
        {rows.map(([label, value, note]) => (
          <div key={label} className={FORM_ROW_CLASS}>
            <dt className={FORM_LABEL_CLASS}>{label}</dt>
            <dd
              className={cn(
                'm-0',
                FORM_VALUE_CLASS,
                'flex-col justify-center gap-0.5',
              )}
            >
              <span className="text-style-pre-body-03 text-text-secondary">
                {value}
              </span>
              {note && (
                <span className="text-style-pre-caption-03 text-text-tertiary">
                  {note}
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
