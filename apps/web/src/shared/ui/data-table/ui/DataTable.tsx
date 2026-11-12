// 목록 표. 키트 tanstack-table-renderer 대신 다시 만들었다(밴드 FK2, FV3 4.1·7.2).
//
// 키트와 다른 자리:
//   - 진짜 <table>·<thead>·<tbody> 의미를 지킨다(display 를 바꾸지 않는다).
//   - 정렬할 수 있는 머리 칸에 aria-sort 를 달고, 머리 글자를 button 으로 감싼다. 표시는 키트 SortIndicator.
//   - 칸 정렬은 기본 왼쪽. 열 정의의 meta.align 으로 바꾼다(키트는 모두 가운데로 박았다).
//   - onClickRow 가 있을 때만 줄이 초점을 받고 Enter·Space 로 눌린다. hover 바탕은 토큰(bg-background-secondary).
//     rowHover="none" 이면 hover 바탕 없음, 초점 표시(바탕·테두리)는 늘 남음(밴드 DT3).
//   - 열 너비는 열 정의의 meta.width(px)로 머리 칸에 단다. 누를 수 있는 줄은 rowLabel 로 이름을 받는다(밴드 FW2 ②).
//   - 줄 사이 선은 칸(<td>)에 단다. border-collapse 표에서 <tr> 에 달면 칸의 계산값이 0px 이다. 색은 #D1D5D9(border-tertiary. 2026-10-15 사용자 결정).
// 로딩(밴드 LD1 ②, sid:MARC-ENT-443): loading 은 날 값(status.state === 'loading' 그대로)이고 300ms 늦추기는 표가 한다(SkeletonRows 기본 delayed).
//   쓰는 쪽이 늦춘 값을 받던 옛 prop 은 모듈이 모두 loading 으로 옮긴 뒤 걷었다(밴드 DT1, sid:MARC-ISSUE-373).
//   로딩 중 empty 는 절대 그리지 않는다. 머리줄은 늘 그대로, 몸은 첫 그림부터 자리 잡은 줄 5(막대는 300ms 뒤). 막대 폭은 열 meta.skeleton.
// 열 폭 고정(밴드 DT1 ②, J3·sid:MARC-ISSUE-374): layout="fixed" 면 table-fixed + 첫 자식 <colgroup>(열마다 <col>, meta.width 있으면 그 폭, 없으면 남은 폭 나눔).
//   스켈레톤·빈 줄·진짜 줄이 같은 colgroup 을 써서 받기 전후 칸 폭이 같다. 긴 글 칸은 줄바꿈(넘치면 다음 줄 — 옆 칸을 덮지 않음). 기본 auto 는 지금 DOM 그대로.
// 스켈레톤 줄 수(밴드 DT1): skeletonRows 를 주면 로딩 줄 수(양의 정수만, 아니면 기본 5). 줄이 적게 오는 목록이 아래 띠를 당기지 않게 — 쓰는 쪽이 예상 줄 수를 안다면.
// 묶음 줄(밴드 DT1 ③, sid:MARC-ISSUE-384 — DV3 결과 표의 사본을 걷게): 셋 다 없으면 지금 DOM 그대로.
//   rowSpanOf(row, columnId) — undefined(기본) 그냥 칸, n≥1 이면 묶음 칸(n 줄을 덮음, align-top — 1 도 묶음이라 펼침 줄이 끼면 그것까지 덮는다.
//     밴드 DVW1 · 71 허락), 0 이면 그 칸을 그리지 않음(위 줄의 span 안). rowSpan 속성은 덮는 줄이 둘 이상일 때만.
//     span 안에 펼침 줄이 끼면 표가 rowSpan 에 펼침 줄 수를 더한다(쓰는 쪽은 데이터 줄 수만 센다).
//     rowSpan 표는 정렬을 끈다(열마다 enableSorting false) — 표는 줄 차례를 바꾸지 않고 받은 차례대로 묶으므로 정렬하면 묶음이 깨진다.
//   renderExpanded(row) — null 아니면 그 줄 바로 아래 <tr data-expanded-row> 하나. 칸 하나가 그 자리에서 rowSpan 으로 덮이지 않은 열 전부를
//     colSpan 한다. 칸 꼴은 진짜 칸과 같고 위아래 12. 누를 수 있는 줄이 아니다(onClickRow 가 있어도). 열림 상태는 쓰는 쪽이 갖는다.
//   rowAttrs(row) — data-* 만 데이터 줄 <tr> 에(타입이 다른 키를 막는다). rowAttrs 는 펼침 줄에 달지 않는다 — 펼침 줄은 expandedRowAttrs.
// 줄 id·줄 바탕·묶음 tbody(밴드 DT2, sid:MARC-ISSUE-415 — 영문번역 BatchTable 을 옮길 수 있게): 셋 다 없으면 지금 DOM 그대로.
//   rowId(row) — 데이터 줄 <tr> 의 DOM id(aria-controls 대상). undefined 면 달지 않음. TanStack 줄 id 와 다르고, 겹침은 쓰는 쪽 몫(표는 검사하지 않는다).
//   rowTone(row) — 'subtle' 이면 그 데이터 줄의 <td> 전부에 바탕(줄 선과 같은 까닭으로 td 에). rowSpan 칸은 시작한 줄의 바탕, 펼침 줄은 바탕 없음.
//     누를 수 있는 줄의 hover 바탕은 같은 색이라 subtle 줄에서는 안 보인다.
//   groupOf(row) — 받은 차례에서 이어진 같은 값끼리 <tbody data-group> 하나(떨어진 같은 값은 새 tbody — 줄 차례를 바꾸지 않는다). 펼침 줄은 그 줄의 tbody.
//     rowSpan 은 묶음 끝에서 자른다(rowspan 은 행 묶음을 넘지 못함). 묶음 밖으로 새는 0 칸은 되살리지 않는다(쓰는 쪽 몫).
//     loading·줄 0 은 tbody 하나 그대로. 묶음 표도 정렬을 끈다 — 정렬하면 묶음이 쪼개진다.
// 줄 열림·펼침 줄 data-*·누름 줄 hover(밴드 DT3, sid:MARC-ISSUE-402 — 중대성평가 결과 2-2 를 옮길 수 있게): 셋 다 없으면 지금 DOM 그대로.
//   rowExpanded(row) — 데이터 줄 <tr> 의 aria-expanded(false 도 단다, undefined 면 달지 않음). 값은 쓰는 쪽이 주고 renderExpanded 와 맞추는 것도 쓰는 쪽.
//     누를 수 없는 줄에 값을 주면 그대로 단다 — 그 줄을 무엇이 여닫는지는 쓰는 쪽 몫. 펼침·스켈레톤·빈 줄에는 달지 않는다.
//   expandedRowAttrs(row) — data-* 만 펼침 줄 <tr> 에. data-expanded-row="" 는 늘 남고 쓰는 쪽이 덮지 못한다. 펼침 줄이 없는 줄에는 부르지 않는다.
//   rowHover — 'background'(기본) 누름 줄 hover 바탕 · 'none' hover 바탕만 뺀다(cursor·초점 바탕·테두리는 그대로). 표 단위.
// 하지 않는 것: 가상화, 묶음 머리글(2단), 가로 스크롤 표시줄·세로 위치 표시, 칸마다 클래스·자유 줄 클래스(DT2 Q1 — 표 꼴의 주인은 여기),
//   rowAttrs 의 자유 aria(DT3 — 줄의 aria·tabIndex 는 표가 정한다. 열면 앞에 펼쳐진 rowAttrs 가 표의 값과 조용히 겹친다 — aria 는 뜻 하나에 칸 하나).
//   가로로 넘치면 바깥 div 가 overflow-x-auto 로 스크롤한다.
import * as React from 'react';

import { SortIndicator } from '@marcspon/ui/components/sort-indicator';
import { cn } from '@marcspon/ui/lib/utils';

import { SkeletonRows } from '../../load-skeleton/index.ts';
import { clickableRowProps, describeTable } from '../hooks/index.ts';
import type { DataTableInstance, RowData } from '../hooks/index.ts';
import type { CellAlign } from '../model/index.ts';

const ALIGN: Record<CellAlign, string> = {
  left: 'text-left',
  center: 'text-center',
  right: 'text-right',
};
const JUSTIFY: Record<CellAlign, string> = {
  left: 'justify-start',
  center: 'justify-center',
  right: 'justify-end',
};

/** 줄에 다는 data-* 속성(그 밖의 키는 타입이 막는다). */
export type RowDataAttributes = Partial<
  Record<`data-${string}`, string | undefined>
>;

/** 줄 바탕(밴드 DT2). 닫힌 토큰 — 더할 때는 계약(플랫폼-웹 감독 판단). */
export type DataTableRowTone = 'subtle';
const ROW_TONE: Record<DataTableRowTone, string> = {
  subtle: 'bg-background-secondary',
};

const CELL =
  'h-14 border-b border-solid border-border-tertiary px-4 text-style-pre-body-06 text-text-secondary';
/** 누를 수 있는 줄. hover 바탕만 rowHover 로 끈다 — 초점 표시(바탕·테두리)는 늘 남는다(밴드 DT3). */
export const ROW_HOVER = 'hover:bg-background-secondary';
/**
 * 묶음 칸(rowSpanOf n≥1 — align-top)의 위 여백(밴드 TA1, sid:MARC-ISSUE-600). 첫 줄이 옆 한 줄 칸(가운데 정렬) 글과 같은 높이에 서게
 * (줄 높이 h-14 − 칸 글 줄 높이 1lh) / 2 — 둘 다 토큰에서 셈(pre-body-06 14px × 1.6 → (56 − 22.4) / 2 = 16.8px). 여러 줄이어도 첫 줄이 맞는다.
 * 남는 차 0.5px(가운데 칸은 아래 테두리 1px 를 뺀 높이의 가운데)는 받는다.
 * 묶음 칸 내용은 칸 글꼴(pre-body-06)을 물려받는 글이어야 첫 줄이 맞는다(1lh 는 칸 자신의 줄 높이).
 */
const SPAN_TOP = 'align-top pt-[calc((theme(spacing.14)-1lh)/2)]';
export const ROW_FOCUS =
  'focus-visible:bg-background-secondary focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-secondary';

/** 줄 차례마다 그 줄이 든 묶음의 마지막 줄 차례(groupOf 가 없으면 모두 끝 줄). */
const groupEnds = <TData,>(
  rows: readonly { original: TData }[],
  groupOf: ((row: TData) => string) | undefined,
) => {
  const ends = rows.map(() => rows.length - 1);
  if (!groupOf) return ends;
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const next = rows[index + 1];
    ends[index] =
      next && groupOf(next.original) === groupOf(rows[index]!.original) ?
        ends[index + 1]!
      : index;
  }
  return ends;
};

/** 0 이상 정수만, 아니면 undefined(그냥 칸). */
const spanValue = (value: number | undefined) =>
  value !== undefined && Number.isInteger(value) && value >= 0 ?
    value
  : undefined;

export interface DataTableProps<TData extends RowData> {
  /** useDataTable 로 만든 표. */
  table: DataTableInstance<TData>;
  /** 첫 응답 전인가(날 값 — 쓰는 쪽이 늦추지 않는다). 참이면 몸 = 스켈레톤 줄 5, 막대는 300ms 뒤. empty 는 그리지 않는다. */
  loading?: boolean;
  /**
   * 표 짜임(밴드 DT1, J3·sid:MARC-ISSUE-374). 'auto'(기본) = 지금 그대로(자동 표 짜임 — 막대·진짜 글이 칸 폭을 정함).
   * 'fixed' = table-fixed + <colgroup>(meta.width 가 있는 열만 그 폭) — 로딩·빈·진짜 줄이 같은 열 폭을 쓴다.
   */
  layout?: 'auto' | 'fixed';
  /** 로딩 줄 수(양의 정수만 — 아니면 기본 5). 줄이 적게 오는 목록이 아래 띠를 당기지 않게 — 쓰는 쪽이 예상 줄 수를 안다면. */
  skeletonRows?: number;
  /**
   * 칸의 rowSpan(데이터 줄 수). undefined 그냥 칸 · n≥1 묶음 칸(n 줄을 덮음, +align-top — 1 도 그 줄의 펼침 줄까지 덮는다) ·
   * 0 그 칸을 그리지 않음(위 줄의 span 안). 펼침 줄은 표가 더한다. rowSpan 표는 정렬을 끈다(enableSorting false).
   * 0 이상 정수가 아니면 그냥 칸.
   */
  rowSpanOf?: (row: TData, columnId: string) => number | undefined;
  /** null 이 아니면 그 줄 바로 아래 펼침 줄(<tr data-expanded-row>, 덮이지 않은 열 전부를 한 칸이). 열림 상태는 쓰는 쪽이 갖는다. */
  renderExpanded?: (row: TData) => React.ReactNode;
  /** 데이터 줄 <tr> 에 다는 data-* 속성(data-testid·data-line 같은 것). undefined 값은 달지 않는다. */
  rowAttrs?: (row: TData) => RowDataAttributes;
  /**
   * 데이터 줄 <tr> 의 aria-expanded(밴드 DT3). false 도 단다, undefined 면 달지 않음. renderExpanded 와 맞추는 것은 쓰는 쪽.
   * 누를 수 없는 줄에 값을 주면 그대로 단다 — 그 줄을 무엇이 여닫는지는 쓰는 쪽 몫.
   */
  rowExpanded?: (row: TData) => boolean | undefined;
  /** 펼침 줄 <tr> 에 다는 data-*(밴드 DT3). data-expanded-row="" 는 늘 남는다(덮지 못함). 펼침 줄이 없는 줄에는 부르지 않는다. */
  expandedRowAttrs?: (row: TData) => RowDataAttributes;
  /** 누를 수 있는 줄의 hover 바탕(표 단위, 밴드 DT3). 'none' 이면 hover 바탕만 없음 — cursor·초점 바탕·테두리는 그대로. 기본 'background'. */
  rowHover?: 'background' | 'none';
  /** 데이터 줄 <tr> 의 DOM id(aria-controls 대상). undefined 면 달지 않음. 겹치지 않게 하는 것은 쓰는 쪽(useId 접두 등). */
  rowId?: (row: TData) => string | undefined;
  /** 데이터 줄 칸 바탕. 'subtle' = 그 줄 <td> 전부 bg-background-secondary. 펼침 줄은 바탕 없음. */
  rowTone?: (row: TData) => DataTableRowTone | undefined;
  /** 있으면 이어진 같은 값의 줄끼리 <tbody data-group={값}> 하나. rowSpan 은 묶음 끝에서 자른다. loading·줄 0 은 tbody 하나. */
  groupOf?: (row: TData) => string;
  /** 줄이 0 일 때 몸 자리에 그린다. 보통 Empty. */
  empty?: React.ReactNode;
  /** 있으면 줄을 누를 수 있다(마우스, Enter·Space). 칸 안의 컨트롤을 누른 것은 줄 클릭으로 치지 않는다. */
  onClickRow?: (row: TData) => void;
  /** 줄마다 누를 수 있는지(없으면 onClickRow 가 있을 때 모두). 거짓인 줄은 초점·이름·hover 를 받지 않는다(밴드 FW2 ③). */
  isRowClickable?: (row: TData) => boolean;
  /** 누를 수 있는 줄의 이름(aria-label). 줄을 누르면 무엇이 일어나는지 말한다(sid:MARC-ISSUE-85 1, 밴드 FW2 ②). */
  rowLabel?: (row: TData) => string;
  /** 바깥 div 의 클래스. */
  className?: string;
  /** <table> 의 이름(caption 대신). */
  'aria-label'?: string;
}

function DataTable<TData extends RowData>({
  table,
  loading = false,
  layout = 'auto',
  skeletonRows,
  empty,
  onClickRow,
  isRowClickable,
  rowLabel,
  rowSpanOf,
  renderExpanded,
  rowAttrs,
  rowExpanded,
  expandedRowAttrs,
  rowHover = 'background',
  rowId,
  rowTone,
  groupOf,
  className,
  'aria-label': ariaLabel,
}: DataTableProps<TData>) {
  const view = describeTable(table);
  const skeleton = view.headers.map((header) => ({
    width: header.skeleton,
    align: header.align,
  }));
  const fixed = layout === 'fixed';
  const rows =
    (
      skeletonRows !== undefined &&
      Number.isInteger(skeletonRows) &&
      skeletonRows > 0
    ) ?
      skeletonRows
    : undefined;
  /** 데이터 줄과 펼침 줄. 열마다 「이 줄 차례까지 덮임」을 세며 rowSpan·colSpan 을 정한다. */
  const bodyRows = () => {
    const spans = view.rows.map((row) =>
      row.cells.map((cell) =>
        rowSpanOf ?
          spanValue(rowSpanOf(row.original, cell.columnId))
        : undefined,
      ),
    );
    const expanded = view.rows.map((row) => {
      const content = renderExpanded?.(row.original);
      return content === null || content === undefined ? null : content;
    });
    /** 열마다 덮는 칸이 끝나는 데이터 줄 차례(그 줄의 펼침 줄까지 덮는다). 없으면 -1. */
    const coverUntil = view.headers.map(() => -1);
    const ends = groupEnds(view.rows, groupOf);
    return view.rows.map((row, index) => {
      const tone = rowTone?.(row.original);
      const clickable = clickableRowProps(
        row.original,
        isRowClickable && !isRowClickable(row.original) ?
          undefined
        : onClickRow,
      );
      const cells = row.cells.flatMap((cell, column) => {
        const span = spans[index]![column]!;
        if (span === 0) return [];
        let rowSpan: number | undefined;
        if (span !== undefined) {
          const last = Math.min(index + span - 1, ends[index]!);
          let opened = 0;
          for (let at = index; at <= last; at += 1)
            if (expanded[at] !== null) opened += 1;
          const covers = last - index + 1 + opened;
          rowSpan = covers > 1 ? covers : undefined;
          coverUntil[column] = last;
        }
        return [
          <td
            key={cell.id}
            rowSpan={rowSpan}
            className={cn(
              CELL,
              ALIGN[cell.align],
              fixed && 'break-words',
              span !== undefined && SPAN_TOP,
              tone && ROW_TONE[tone],
            )}
          >
            {cell.content}
          </td>,
        ];
      });
      const content = expanded[index];
      const covered = coverUntil.filter((until) => until >= index).length;
      return (
        <React.Fragment key={row.id}>
          <tr
            {...rowAttrs?.(row.original)}
            id={rowId?.(row.original)}
            aria-expanded={rowExpanded?.(row.original)}
            {...clickable}
            aria-label={
              clickable && rowLabel ? rowLabel(row.original) : undefined
            }
            className={cn(
              clickable && [
                'cursor-pointer',
                rowHover !== 'none' && ROW_HOVER,
                ROW_FOCUS,
              ],
            )}
          >
            {cells}
          </tr>
          {content !== null && (
            // 펼침이 앞, 고정이 뒤 — data-expanded-row 는 쓰는 쪽이 덮지 못한다(표 안 셈·시험·감싸개가 기댄다).
            <tr {...expandedRowAttrs?.(row.original)} data-expanded-row="">
              <td
                colSpan={Math.max(view.columnCount - covered, 1)}
                className={cn(CELL, 'py-3', fixed && 'break-words')}
              >
                {content}
              </td>
            </tr>
          )}
        </React.Fragment>
      );
    });
  };
  /** 묶음마다 <tbody data-group>(묶음 첫 줄의 차례에서 끝 줄까지 — 줄과 그 펼침 줄). */
  const groupBodies = (groupOf: (row: TData) => string) => {
    const ends = groupEnds(view.rows, groupOf);
    const drawn = bodyRows();
    const bodies: React.ReactNode[] = [];
    for (let start = 0; start < view.rows.length; start = ends[start]! + 1) {
      const first = view.rows[start]!;
      bodies.push(
        <tbody key={first.id} data-group={groupOf(first.original)}>
          {drawn.slice(start, ends[start]! + 1)}
        </tbody>,
      );
    }
    return bodies;
  };
  const fullRow = (content: React.ReactNode) => (
    <tr>
      <td colSpan={Math.max(view.columnCount, 1)} className="p-0">
        {content}
      </td>
    </tr>
  );
  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table
        aria-label={ariaLabel}
        className={cn('w-full border-collapse', fixed && 'table-fixed')}
        aria-busy={loading || undefined}
      >
        {fixed && (
          <colgroup>
            {view.headers.map((header) => (
              <col
                key={header.id}
                style={
                  header.width === undefined ?
                    undefined
                  : { width: header.width }
                }
              />
            ))}
          </colgroup>
        )}
        <thead>
          <tr>
            {view.headers.map((header) => (
              <th
                key={header.id}
                scope="col"
                aria-sort={header.ariaSort}
                style={
                  header.width === undefined ?
                    undefined
                  : { width: header.width }
                }
                className={cn(
                  'h-10 border-y border-solid border-border-tertiary bg-support-grey-subtle px-4 text-style-pre-body-05 text-text-tertiary',
                  ALIGN[header.align],
                )}
              >
                {header.sortable ?
                  <button
                    type="button"
                    onClick={header.toggleSort}
                    className={cn(
                      'inline-flex w-full items-center gap-0.5 rounded-control focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-secondary',
                      JUSTIFY[header.align],
                    )}
                  >
                    {header.content}
                    <SortIndicator direction={header.sort} />
                  </button>
                : header.content}
              </th>
            ))}
          </tr>
        </thead>
        {groupOf && !loading && view.rows.length > 0 ?
          groupBodies(groupOf)
        : <tbody>
            {loading ?
              <SkeletonRows columns={skeleton} rows={rows} />
            : view.rows.length === 0 ?
              fullRow(empty ?? null)
            : bodyRows()}
          </tbody>
        }
      </table>
    </div>
  );
}
DataTable.displayName = 'DataTable';

export { DataTable };
