// 확인할 쪽 표 · 단계 줄 · 안내 줄(밴드 TRW0b, 시안 TR-04a). 모양 부품: props 만 받는다.
// - PagesToCheck: 번역·검수가 끝나지 않은 쪽만(줄이 없으면 그리지 않는다 — 판에 빈 꼴 없음).
//   표는 shared DataTable(밴드 TRP2 TC3). 줄 표시 data-row 는 쪽 칸 안 글에 단다. 까닭 칸은 위아래 12 를 두고 줄을 바꾼다.
// - StepLine: 「단계 번역 2쪽 실패 · 용어집 반영 검사 완료 · …」(「단계」 caption-03 · 값 배지 — 밴드 TRP2 TC25) — 단계 이름과 글은 부르는 쪽이 넘긴다(서버 단계 잇기는 어댑터).
// - ResultNotices: 단계 줄 아래 안내 줄(shared PageInfo — 검수 멈춤 error 빨강, 번역 못 한 쪽 important 주황. 밴드 TRP2 TC24). 「주의 n건」 머리는 없다(확정 판 v136).
import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { StatusBadge } from '../../../entities/translation/ui/index.ts';
import type { StatusLook } from '../../../entities/translation/ui/index.ts';
import { Card } from '../../../shared/ui/card/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

const words = TR_TEXT.pagesToCheck;

/** 배지 하나(글과 변형). */
interface BadgeValue {
  text: string;
  look: StatusLook;
}

interface CheckRow {
  pages: string;
  translate: BadgeValue;
  review: BadgeValue;
  reason: string;
}

const badge = ({ text, look }: BadgeValue) => (
  <StatusBadge look={look}>{text}</StatusBadge>
);

// 짧은 칸 폭 = 그 칸 max-content(머리 글 포함) + 좌우 32, 1280 에서 잰 값(밴드 TRW5 — DT1 꼴, layout="fixed"). 긴 글 칸은 남은 폭을 나눈다.
const COLUMNS: DataTableColumnDef<CheckRow>[] = [
  {
    id: 'pages',
    header: words.columns.pages,
    enableSorting: false,
    meta: { align: 'right', width: 75 },
    cell: ({ row }) => (
      <span data-row="check" className="tabular-nums">
        {row.original.pages}
      </span>
    ),
  },
  {
    id: 'translate',
    header: words.columns.translate,
    enableSorting: false,
    meta: { width: 61 },
    cell: ({ row }) => badge(row.original.translate),
  },
  {
    id: 'review',
    header: words.columns.review,
    enableSorting: false,
    meta: { width: 130 },
    cell: ({ row }) => badge(row.original.review),
  },
  {
    id: 'reason',
    header: words.columns.reason,
    enableSorting: false,
    cell: ({ row }) => (
      <span className="block whitespace-normal break-words py-3">
        {row.original.reason}
      </span>
    ),
  },
];

export interface PagesToCheckProps {
  rows: readonly CheckRow[];
}

export function PagesToCheck({ rows }: PagesToCheckProps) {
  const table = useDataTable({ data: rows as CheckRow[], columns: COLUMNS });
  if (rows.length === 0) return null;
  return (
    <Card data-testid="pages-to-check" className="flex flex-col gap-4">
      {/* 머리 한 줄: 제목 왼쪽, 꼬리 글 오른쪽(밴드 TRP3 ② N1 — 시안 TR-04·04a g-between) */}
      <div
        data-testid="pages-to-check-head"
        className="flex flex-wrap items-center justify-between gap-4"
      >
        <h3 className="m-0 text-style-pre-heading-02 text-text-primary">
          {words.title}
        </h3>
        <span className="text-style-pre-caption-03 text-text-tertiary">
          {words.basis}
        </span>
      </div>
      <DataTable table={table} layout="fixed" aria-label={words.title} />
    </Card>
  );
}

export interface StepLineProps {
  steps: readonly ({ name: string } & BadgeValue)[];
}

export function StepLine({ steps }: StepLineProps) {
  return (
    <p
      data-testid="step-line"
      // 단계 이름 400 16 · 「단계」와 세로 가운데(밴드 TRP3 ② N3 — 시안 TR-04a)
      className="m-0 flex flex-wrap items-center gap-x-2 text-style-pre-body-03 text-text-secondary"
    >
      <span className="text-style-pre-caption-03 text-text-tertiary">
        {TR_TEXT.result.stepsLabel}
      </span>
      {steps.map((step, index) => (
        <span key={index} data-step={index}>
          {index > 0 && (
            <span aria-hidden className="mr-2 text-text-quaternary">
              ·
            </span>
          )}
          {step.name} {badge(step)}
        </span>
      ))}
    </p>
  );
}

export interface ResultNoticesProps {
  notices: readonly { tone: 'important' | 'error'; text: string }[];
}

export function ResultNotices({ notices }: ResultNoticesProps) {
  if (notices.length === 0) return null;
  return (
    <div data-testid="result-notices" className="gw-m-rise flex flex-col gap-2">
      {notices.map((notice, index) => (
        <PageInfo key={index} tone={notice.tone} icon={<PageInfoIcon />}>
          {notice.text}
        </PageInfo>
      ))}
    </div>
  );
}
