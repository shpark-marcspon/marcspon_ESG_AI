// 용어집 미반영 표(밴드 TRW0b, 시안 TR-04 「용어집 미반영」). 모양 부품: props 만 받는다. 줄이 없으면 빈 꼴 글.
// 표는 shared DataTable(밴드 TRP2 TC3). 줄 표시 data-row 는 쪽 칸 안 글에 단다(DataTable 은 줄 data-* 를 받지 않는다).
// PDF 파트(밴드 TRW6 ③): 선택 prop placeOf·onRow 를 받으면 「자리」 칸을 더한다(QaIssueTable 과 같은 꼴). 워드 파트는 그대로.
import { useEffect, useMemo, useRef } from 'react';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';

const words = TR_TEXT.glossaryMiss;

export interface MissRow {
  page: number;
  ko: string;
  en: string;
  count: number;
}

// 짧은 칸 폭 = 그 칸 max-content(머리 글 포함) + 좌우 32, 1280 에서 잰 값(밴드 TRW5 — DT1 꼴, layout="fixed"). 긴 글 칸은 남은 폭을 나눈다.
const COLUMNS: DataTableColumnDef<MissRow>[] = [
  {
    id: 'page',
    header: words.columns.page,
    enableSorting: false,
    meta: { align: 'right', width: 68 },
    cell: ({ row }) => (
      <span data-row="miss" className="tabular-nums">
        {row.original.page}
      </span>
    ),
  },
  {
    id: 'ko',
    header: words.columns.ko,
    enableSorting: false,
    // 원문 용어는 짧은 국문 낱말 — 영문 칸이 남은 폭을 갖게 잰 값(104)을 준다.
    meta: { width: 104 },
    cell: ({ row }) => row.original.ko,
  },
  {
    id: 'en',
    header: words.columns.en,
    enableSorting: false,
    cell: ({ row }) => row.original.en,
  },
  {
    id: 'count',
    header: words.columns.count,
    enableSorting: false,
    meta: { align: 'right', width: 84 },
    cell: ({ row }) => TR_TEXT.cells.times(row.original.count),
  },
];

/** 「자리」 칸(PDF 파트만): 쪽 칸 뒤에 둔다. */
function placeColumn(
  placeOf: (row: MissRow) => string,
  onRow: (row: MissRow) => void,
): DataTableColumnDef<MissRow> {
  return {
    id: 'place',
    header: TR_TEXT.pdfView.place,
    enableSorting: false,
    meta: { width: 150 },
    cell: ({ row }) => (
      <button
        type="button"
        data-testid="glossary-miss-place"
        className="cursor-pointer border-0 bg-transparent p-0 text-left text-style-pre-body-06 text-text-brand underline"
        onClick={() => onRow(row.original)}
      >
        {placeOf(row.original)}
      </button>
    ),
  };
}

/** 돌아온 줄(판 .tp-on — blue-100 + 왼쪽 3px blue-600). DataTable 은 줄 클래스를 받지 않아 data-returned 로 고른다. */
const RETURNED_LOOK =
  '[&_tr[data-returned]>td]:bg-blue-100 [&_tr[data-returned]>td:first-child]:shadow-[inset_3px_0_0_theme(colors.blue.600)]';

export interface GlossaryMissTableProps {
  rows: readonly MissRow[];
  /** PDF 파트만: 줄의 자리 글. onRow 와 함께 줘야 칸이 생긴다. */
  placeOf?: (row: MissRow) => string;
  /** PDF 파트만: 「자리」를 누름 → PDF 보기의 그 자리. */
  onRow?(row: MissRow): void;
  /** PDF 파트만: PDF 보기에서 돌아왔을 때 눌렀던 줄(밴드 TRW7 ② — QaIssueTable 과 같은 꼴). */
  returned?: number;
}

export function GlossaryMissTable({
  rows,
  placeOf,
  onRow,
  returned,
}: GlossaryMissTableProps) {
  const columns = useMemo(
    () =>
      placeOf === undefined || onRow === undefined ?
        COLUMNS
      : [COLUMNS[0]!, placeColumn(placeOf, onRow), ...COLUMNS.slice(1)],
    [placeOf, onRow],
  );
  const table = useDataTable({ data: rows as MissRow[], columns });
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (returned === undefined) return;
    bodyRef.current
      ?.querySelector<HTMLElement>('tr[data-returned]')
      ?.scrollIntoView?.({ block: 'center' });
  }, [returned]);
  return (
    <Card data-testid="glossary-miss" className="flex flex-col gap-4">
      {/* 머리 한 줄: 제목 왼쪽, 꼬리 글 오른쪽(밴드 TRP3 ② N1 — 시안 TR-04·04a g-between) */}
      <div
        data-testid="glossary-miss-head"
        className="flex flex-wrap items-center justify-between gap-4"
      >
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.title}
        </h3>
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.basis}
        </span>
      </div>
      {rows.length === 0 ?
        <p
          data-testid="glossary-miss-empty"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {words.empty}
        </p>
      : <>
          {returned === undefined ?
            <DataTable table={table} layout="fixed" aria-label={words.title} />
          : <div ref={bodyRef}>
              <DataTable
                table={table}
                layout="fixed"
                aria-label={words.title}
                rowAttrs={(row) => ({
                  'data-returned':
                    rows.indexOf(row) === returned ? '' : undefined,
                })}
                className={RETURNED_LOOK}
              />
            </div>
          }
          <p className="m-0 text-style-pre-caption-03 text-text-tertiary">
            {words.note}
          </p>
        </>
      }
    </Card>
  );
}
