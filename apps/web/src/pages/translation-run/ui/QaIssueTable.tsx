// 번역 검수(QA) 이슈 표(밴드 TRW0b, 시안 TR-04·04a). 모양 부품: props 만 받는다. 거르기 상태는 안에서.
// - 유형 거르기(shared FilterSelect: 전체 + 열 가지) · 심각도 상자 탭(키트 Tabs box — 전체/High/Mid/Low 와 이 파트 이슈 전체의 수) · 표 · 빈 꼴.
// - 심각도 칸은 shared RiskBadge. 거르기·셈은 model/issues.ts.
// - 표는 shared DataTable(밴드 TRP2 TC3 — 머리 #FAFBFB·몸 56). 줄 표시 data-issue 는 쪽 칸 안 글에 단다(DataTable 은 줄 data-* 를 받지 않는다).
//   긴 글 칸(원문·제안·까닭)은 위아래 12 를 두고 줄을 바꾼다.
// - PDF 파트(밴드 TRW6 ③, 6c v174 TR-P04): 선택 prop placeOf·onRow 를 받으면 「자리」 칸(쪽·문단 단추)을 더한다 — 누르면 PDF 보기의 그 자리로.
//   워드 파트는 넘기지 않아 칸·DOM 이 그대로다.
import { useEffect, useMemo, useRef, useState } from 'react';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  ISSUE_TYPE_KEYS,
  SEVERITIES,
} from '../../../entities/translation/model/index.ts';
import type {
  IssueTypeKey,
  Severity,
} from '../../../entities/translation/model/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import type { FilterOption } from '../../../shared/ui/filter-select/index.ts';
import {
  RISK_BADGE_LOOK,
  RiskBadge,
} from '../../../shared/ui/risk-badge/index.ts';
import { Tabs, TabsList, TabsTrigger } from '../../../shared/ui/tabs/index.ts';
import { filterIssues, severityCounts } from '../model/index.ts';
import type { QaIssue } from '../model/index.ts';

const words = TR_TEXT.issues;

type TypeValue = 'all' | IssueTypeKey;
type SeverityValue = 'all' | Severity;

const TYPE_OPTIONS: readonly FilterOption<TypeValue>[] = [
  { value: 'all', label: words.allTypes },
  ...ISSUE_TYPE_KEYS.map((key) => ({ value: key, label: words.types[key] })),
];

const longText = (text: string) => (
  <span className="block whitespace-normal break-words py-3">{text}</span>
);

// 짧은 칸 폭 = 그 칸 max-content(머리 글 포함) + 좌우 32, 1280 에서 잰 값(밴드 TRW5 — DT1 꼴, layout="fixed"). 긴 글 칸은 남은 폭을 나눈다.
const COLUMNS: DataTableColumnDef<QaIssue>[] = [
  {
    id: 'page',
    header: words.columns.page,
    enableSorting: false,
    meta: { align: 'right', width: 68 },
    cell: ({ row }) => (
      <span data-issue={row.original.severity} className="tabular-nums">
        {row.original.page}
      </span>
    ),
  },
  {
    id: 'type',
    header: words.columns.type,
    enableSorting: false,
    meta: { width: 111 },
    cell: ({ row }) => words.types[row.original.type],
  },
  {
    id: 'severity',
    header: words.columns.severity,
    enableSorting: false,
    meta: { width: 80 },
    cell: ({ row }) => <RiskBadge level={row.original.severity} />,
  },
  {
    id: 'span',
    header: words.columns.span,
    enableSorting: false,
    cell: ({ row }) => longText(row.original.span),
  },
  {
    id: 'suggestion',
    header: words.columns.suggestion,
    enableSorting: false,
    cell: ({ row }) => longText(row.original.suggestion),
  },
  {
    id: 'reason',
    header: words.columns.reason,
    enableSorting: false,
    cell: ({ row }) => longText(row.original.reason),
  },
];

/** 「자리」 칸(PDF 파트만): 쪽 칸 뒤에 둔다. */
function placeColumn(
  placeOf: (issue: QaIssue) => string,
  onRow: (issue: QaIssue) => void,
): DataTableColumnDef<QaIssue> {
  return {
    id: 'place',
    header: TR_TEXT.pdfView.place,
    enableSorting: false,
    meta: { width: 150 },
    cell: ({ row }) => (
      <button
        type="button"
        data-testid="qa-issue-place"
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

export interface QaIssueTableProps {
  issues: readonly QaIssue[];
  /** PDF 파트만: 줄의 자리 글(「12페이지 둘째 문단」). onRow 와 함께 줘야 칸이 생긴다. */
  placeOf?: (issue: QaIssue) => string;
  /** PDF 파트만: 「자리」를 누름 → PDF 보기의 그 자리. */
  onRow?(issue: QaIssue): void;
  /** 머리 아래 기준 글(기본 「자동 수정 전 글 기준」 — TR-04a 는 「4~29쪽 · 7건 · …」 꼴을 부르는 쪽이 짓는다). */
  basis?: string;
  emptyText?: string;
  /** PDF 파트만: PDF 보기에서 돌아왔을 때 눌렀던 줄 — issues 안 차례(밴드 TRW7 ②, 객체가 아니라 차례라 다시 그려도 effect 가 다시 돌지 않는다 — 검증 R5) — 옅은 파랑으로 남고 화면 안으로. 없으면 줄 DOM 그대로. */
  returned?: number;
}

export function QaIssueTable({
  issues,
  basis = words.basis,
  emptyText = words.empty,
  placeOf,
  onRow,
  returned,
}: QaIssueTableProps) {
  const [type, setType] = useState<TypeValue>('all');
  const [severity, setSeverity] = useState<SeverityValue>('all');
  const counts = severityCounts(issues);
  const shown = filterIssues(issues, {
    type: type === 'all' ? undefined : type,
    severity: severity === 'all' ? undefined : severity,
  });
  const columns = useMemo(
    () =>
      placeOf === undefined || onRow === undefined ?
        COLUMNS
      : [COLUMNS[0]!, placeColumn(placeOf, onRow), ...COLUMNS.slice(1)],
    [placeOf, onRow],
  );
  const table = useDataTable({ data: shown as QaIssue[], columns });
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (returned === undefined) return;
    bodyRef.current
      ?.querySelector<HTMLElement>('tr[data-returned]')
      ?.scrollIntoView?.({ block: 'center' });
  }, [returned]);
  return (
    <Card data-testid="qa-issues" className="flex flex-col gap-4">
      {/* 머리 한 줄: 제목·기준 글 왼쪽, 거르기·심각도 탭 오른쪽(밴드 TRP3 ② N1 — 시안 TR-04 g-between) */}
      <div
        data-testid="qa-issues-head"
        className="flex flex-wrap items-center justify-between gap-4"
      >
        <div className="flex flex-wrap items-baseline gap-2">
          <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
            {words.title}
          </h3>
          <span className="text-style-pre-caption-03 text-text-tertiary">
            {basis}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <FilterSelect<TypeValue>
            label={words.typeFilter}
            separator=" "
            value={type}
            options={TYPE_OPTIONS}
            onChange={setType}
            aria-label={words.typeFilter}
          />
          <Tabs
            value={severity}
            onValueChange={(next) => setSeverity(next as SeverityValue)}
            variant="box"
          >
            <TabsList aria-label={words.severityLabel}>
              <TabsTrigger value="all" data-severity="all">
                {`${words.allSeverities} ${counts.all}`}
              </TabsTrigger>
              {SEVERITIES.map((level) => (
                <TabsTrigger key={level} value={level} data-severity={level}>
                  {`${RISK_BADGE_LOOK[level].label} ${counts[level]}`}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      </div>
      {/* 거르기를 바꾸면 표가 새로 붙어 비친다(밴드 TRP4 ②-8) */}
      {shown.length === 0 ?
        <p
          data-testid="qa-issues-empty"
          className="m-0 text-style-pre-body-06 text-text-tertiary"
        >
          {emptyText}
        </p>
      : <div
          key={`${type}:${severity}`}
          ref={bodyRef}
          data-testid="qa-issues-body"
          className="gw-m-fade"
        >
          <DataTable
            table={table}
            layout="fixed"
            aria-label={words.title}
            {...(returned === undefined ?
              {}
            : {
                rowAttrs: (row: QaIssue) => ({
                  'data-returned':
                    issues.indexOf(row) === returned ? '' : undefined,
                }),
                className: RETURNED_LOOK,
              })}
          />
        </div>
      }
    </Card>
  );
}
