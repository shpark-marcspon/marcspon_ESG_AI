// S2 배출범위 표 하나(밴드 W12-1a ③ — 발주서 2-3, 시안 28535:7000). 공용 DataTable + rowSpanOf(배출원 유형·배출활동 세로 합침 —
//   model listSpans, 서버 차례 그대로). 머리: 배출원 유형 · 배출활동 · 자산/시설 유형 · 서버 years 세 해 · 단위 · 메모 · 추정치 · 잠금
//   (담당자·참고자료 열은 1차 숨김). 3개년 머리는 서버 years 그대로 — 웹이 셈하지 않는다.
//   - 값 칸: formatAmount(서버 글자, decimals) — null 「-」. 단위 칸은 행 칸이 없어 응답 unit 하나를 모든 행에.
//   - 디자인 대조(밴드 W12-1b ③): 메모 칩 「내용」(있으면 진하게) · 추정 열은 모든 행 물결 상자(행 바탕 칠 없음) · 잠금 열은 모든 행 자물쇠(보기만). 뜻은 aria-label.
//   - 줄 전체 + 자산/시설 단추(같은 상세 — Q3 화면 안 상태로 S3, 밴드 W12-1b ①, sid:MARC-ENT-599) · 묶인 칸은 열지 않음(밴드 RC1).
//   - GX2 S12-02: 묶음 칸 폭 150 고정 · 오른쪽 선(두 표 열 맞춤).
import { useMemo } from 'react';
import type { ReactNode } from 'react';

import { LockIcon } from '@marcspon/common/generated/icons/MyIcons';

import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { formatAmount, listSpans } from '../../../entities/ghg/model/index.ts';
import type {
  EntryListRow,
  EntryScope,
  ListSpan,
} from '../../../entities/ghg/model/index.ts';
import {
  DataTable,
  useDataTable,
} from '../../../shared/ui/data-table/index.ts';
import type { DataTableColumnDef } from '../../../shared/ui/data-table/index.ts';
import { EstimatedWave, estimatedBox } from './EstimatedMark.tsx';

const words = GHG_TEXT.inventory;
/** 디자인 대조 1 — 추정 열 칸 폭(px). */
const ESTIMATED_WIDTH = 92;

/**
 * GX2 S12-02(판 `.f12a-mc`): 묶음 칸(배출원 유형·배출활동) 폭 150 고정 — 글 상자를 150 − 좌우 여백 32 로 박아
 * 자동 표 짜임에서도 두 표(Scope 1·2)의 열이 맞는다. 긴 이름은 그 안에서 접는다.
 */
const GROUP_WIDTH = 150;
function Group({ text }: { text: string }) {
  return <span className="block w-[118px] break-words">{text}</span>;
}
/**
 * 묶음 칸(배출원 유형·배출활동 — rowSpanOf 가 준 칸 전부, span 1 포함). shared/ui/data-table/ui/DataTable.tsx 가
 * 묶음 칸(span !== undefined)에만 SPAN_TOP 의 align-top 을 단다 — 그 클래스에 기댄다.
 */
const GROUP_CELL = 'td.align-top';
/**
 * 묶음 칸의 오른쪽 선(판 `.f12a-mc` border-right) · 묶음 칸은 줄을 열지 않으므로(sid:MARC-ENT-599 규칙 6, 밴드 RC1) 손가락 커서를 끄고
 * 줄 hover·초점 바탕이 칠하지 않게 Card 바탕(shared/ui/card/ui/Card.tsx 와 같은 토큰)을 둔다. 묶인 칸 위에 올리면 그 칸을 품은
 * 첫 줄 <tr> 이 hover 로 잡히므로 그 줄 바탕도 끈다(감독 판단 7 B2).
 */
const GROUP_LINE =
  '[&_td.align-top]:border-r [&_td.align-top]:border-solid [&_td.align-top]:border-border-tertiary [&_td.align-top]:cursor-default [&_td.align-top]:bg-background-primary [&_tr:has(>td.align-top:hover)]:bg-transparent';

interface Line {
  row: EntryListRow;
  span: ListSpan;
}

function columns(
  years: readonly number[],
  decimals: number,
  unit: string,
  onOpen: (nodeId: string) => void,
): DataTableColumnDef<Line>[] {
  const column = (
    id: string,
    header: string,
    cell: (line: Line) => ReactNode,
    align?: 'right' | 'center',
    width?: number,
  ): DataTableColumnDef<Line> => ({
    id,
    header,
    enableSorting: false,
    meta: {
      ...(align === undefined ? {} : { align }),
      ...(width === undefined ? {} : { width }),
    },
    cell: ({ row }) => cell(row.original),
  });
  const head = words.head;
  return [
    column(
      'source',
      head.source,
      (line) => <Group text={line.row.path[1] ?? ''} />,
      undefined,
      GROUP_WIDTH,
    ),
    column(
      'activity',
      head.activity,
      (line) => <Group text={line.row.path[2] ?? ''} />,
      undefined,
      GROUP_WIDTH,
    ),
    column('facility', head.facility, (line) => (
      <button
        type="button"
        data-testid={`inventory-open-${line.row.nodeId}`}
        aria-label={line.row.path[3] ? undefined : words.openUnnamed}
        className="cursor-pointer border-0 bg-transparent p-0 text-left text-text-primary hover:underline focus-visible:outline-2"
        onClick={() => onOpen(line.row.nodeId)}
      >
        {line.row.path[3] ?? ''}
      </button>
    )),
    ...years.map((year) =>
      column(
        `y${year}`,
        `${year}`,
        (line) => (
          <span className="tabular-nums">
            {formatAmount(line.row.values[`${year}`] ?? null, decimals)}
          </span>
        ),
        'right',
      ),
    ),
    column('unit', head.unit, () => unit),
    column(
      'memo',
      head.memo,
      (line) => (
        <span
          role="img"
          aria-label={line.row.hasMemo ? words.memoOn : words.memoOff}
          data-memo={line.row.hasMemo}
          className={`inline-flex h-7 min-w-14 items-center justify-center rounded-full border border-solid border-button-grey bg-button-white px-2.5 text-style-pre-caption-02 ${
            line.row.hasMemo ? 'text-text-secondary' : 'text-text-quaternary'
          }`}
        >
          {words.memoChip}
        </span>
      ),
      'center',
    ),
    column(
      'estimated',
      head.estimated,
      (line) => (
        <span
          role="img"
          aria-label={
            line.row.estimated ? words.estimatedLabel : words.estimatedOff
          }
          data-testid={line.row.estimated ? 'row-estimated' : undefined}
          data-estimated={line.row.estimated}
          className={estimatedBox(line.row.estimated)}
        >
          <EstimatedWave />
        </span>
      ),
      'center',
      ESTIMATED_WIDTH,
    ),
    column(
      'locked',
      head.locked,
      (line) => (
        <span
          role="img"
          aria-label={line.row.locked ? words.lockedLabel : words.unlockedLabel}
          data-testid={line.row.locked ? 'row-locked' : undefined}
          data-locked={line.row.locked}
          className={`inline-flex rounded-control p-0.5 ${
            line.row.locked ?
              'bg-background-brand text-text-brand'
            : 'text-text-tertiary'
          }`}
        >
          <LockIcon aria-hidden className="size-4" />
        </span>
      ),
      'center',
    ),
  ];
}

export function InventoryTable({
  scope,
  years,
  decimals,
  unit,
  onOpen,
}: {
  scope: EntryScope;
  years: readonly number[];
  decimals: number;
  unit: string;
  onOpen: (nodeId: string) => void;
}) {
  // 열 정의가 그릴 때마다 새로우면 칸 그리는 함수가 새 컴포넌트가 되어 칸 단추가 다시 만들어진다(모달을 닫으면 초점을 돌릴 단추가 없어진다).
  const data = useMemo(() => {
    const spans = listSpans(scope.rows);
    return scope.rows.map((row, index) => ({ row, span: spans[index]! }));
  }, [scope.rows]);
  const lines = useMemo(
    () => columns(years, decimals, unit, onOpen),
    [years, decimals, unit, onOpen],
  );
  const table = useDataTable({
    data,
    columns: lines,
    getRowId: (line) => line.row.nodeId,
  });
  return (
    <section
      data-testid={`inventory-scope-${scope.scopeId}`}
      className="flex flex-col gap-3"
      onClickCapture={(event) => {
        // 묶인 칸은 묶음 첫 줄의 <tr> 안에 그려진다 — 줄 클릭(첫 줄 상세)까지 가지 않게 여기서 멈춘다.
        if (event.target instanceof Element && event.target.closest(GROUP_CELL))
          event.stopPropagation();
      }}
    >
      <h3 className="m-0 text-style-pre-heading-02">{scope.scopeName}</h3>
      <DataTable
        table={table}
        className={GROUP_LINE}
        aria-label={words.tableLabel(scope.scopeName)}
        rowSpanOf={(line, column) =>
          column === 'source' ? line.span.source
          : column === 'activity' ? line.span.activity
          : undefined
        }
        onClickRow={(line) => onOpen(line.row.nodeId)}
        rowLabel={(line) => line.row.path[3] || words.openUnnamed}
        rowAttrs={(line) => ({
          'data-testid': `inventory-row-${line.row.nodeId}`,
        })}
      />
    </section>
  );
}
