// 둘째 화면: 같은 헤드리스 훅(useReviewBoard)과 모양 없는 컴포넌트(RowStack) 위에 얹은 카드 목록. 증명용이고 제품이 아니다.
// 보이려는 것: 화면을 통째로 바꿔도 업무 로직과 헤드리스 층은 그대로 쓴다.
// 그래서 review-table/ui 의 것을 하나도 가져오지 않고, 공개 표면(review-table/index.ts)만 쓴다.
// 이 파일에는 구조 코드가 없다: 스크롤 상자의 ref, 높이 잡기, 행 내리기, 높이 재기, 키보드 받기, 행의 상태 표시는 전부 RowStack 이 한다.
// 여기 있는 것은 카드의 생김(조작 띠, 카드의 속, 클래스 이름)뿐이다.
// 같은 동작 테스트(src/pages/demo-table/behavior.test.tsx)가 표와 이 카드 둘 다에서 통과한다.
import { useCallback, useState } from 'react';

import { NativeSelect } from '../../shared/ui/filter-select/index.ts';
import {
  ACTION_ERROR_MESSAGE,
  ACTION_LABEL,
  RowStack,
  STATUSES,
  STATUS_LABEL,
  allowedActions,
  checkAction,
  currentCandidate,
  currentCategory,
  describeSkip,
  isRecalcFailed,
  skippedCount,
  useReviewBoard,
} from '../../widgets/review-table/index.ts';
import type {
  ActionResult,
  ActionType,
  BulkScope,
  ColumnView,
  RenderRow,
  ReviewAction,
  ReviewRow,
  ReviewStatus,
  ReviewTableProps,
} from '../../widgets/review-table/index.ts';
import './cards.css';

/** 접힌 카드의 높이(px). cards.css 의 .rc-card 와 맞춘다. */
const CARD_HEIGHT = 64;
const SIMPLE: readonly ActionType[] = [
  'accept',
  'decline',
  'rerequest',
  'finalize',
  'reopen',
  'unfinalize',
];
const STACK_CLASSES = { scroller: 'rc-scroll', row: 'rc-card' };

export function ReviewCards({
  rows,
  categories,
  columns,
  calculate,
  onChange,
  onRenderRow,
}: ReviewTableProps) {
  const board = useReviewBoard({
    rows,
    columns,
    calculate,
    onChange,
    estimateRowHeight: CARD_HEIGHT,
  });
  const { table, window, summary, lastBulk, act, retry } = board;
  const [scope, setScope] = useState<BulkScope>('filtered');
  const skipped = lastBulk ? skippedCount(lastBulk) : 0;

  // 카드 하나의 속. useCallback 으로 감싸야 한 장만 다시 그려진다(review-table/headless/RowFrame.tsx 머리말).
  const tableColumns = table.columns;
  const { toggleSelected } = table;
  const { toggleExpanded } = window;
  const renderRow = useCallback<RenderRow>(
    (row, state) => (
      <Card
        row={row}
        selected={state.selected}
        expanded={state.expanded}
        columns={tableColumns}
        categories={categories}
        act={act}
        retry={retry}
        toggleSelected={toggleSelected}
        toggleExpanded={toggleExpanded}
      />
    ),
    [tableColumns, categories, act, retry, toggleSelected, toggleExpanded],
  );

  return (
    <section className="rc">
      <header className="rc-bar">
        <input
          aria-label="글자로 걸러 보기"
          placeholder="찾기"
          value={table.filter.text}
          onChange={(event) => table.setFilter({ text: event.target.value })}
        />
        <NativeSelect
          aria-label="상태로 걸러 보기"
          value={table.filter.statuses[0] ?? ''}
          onChange={(event) =>
            table.setFilter({
              statuses:
                event.target.value ? [event.target.value as ReviewStatus] : [],
            })
          }
        >
          <option value="">모든 상태</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABEL[status]}
            </option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label="카테고리로 걸러 보기"
          value={table.filter.category ?? ''}
          onChange={(event) =>
            table.setFilter({ category: event.target.value || null })
          }
        >
          <option value="">모든 카테고리</option>
          {categories.map((category) => (
            <option key={category}>{category}</option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label="일괄 대상"
          value={scope}
          onChange={(event) => setScope(event.target.value as BulkScope)}
        >
          <option value="filtered">걸러 본 결과 전체</option>
          <option value="selected">고른 행</option>
        </NativeSelect>
        <button
          type="button"
          onClick={() => board.bulk(scope, { type: 'accept' })}
        >
          일괄 {ACTION_LABEL.accept}
        </button>
        <button
          type="button"
          onClick={() => board.bulk(scope, { type: 'finalize' })}
        >
          일괄 {ACTION_LABEL.finalize}
        </button>
        <span data-testid="rt-shown" data-shown={table.rows.length}>
          {table.rows.length}장
        </span>
        <span
          data-testid="rt-summary"
          data-total={summary.total}
          data-final-total={summary.finalTotal}
          data-provisional-total={summary.provisionalTotal}
          data-recalc-pending={summary.recalcPending}
          data-recalc-failed={summary.recalcFailed}
        >
          {STATUSES.map((status) => (
            <i
              key={status}
              data-status-count={status}
              data-count={summary.byStatus[status]}
            >
              {STATUS_LABEL[status]} {summary.byStatus[status]}{' '}
            </i>
          ))}
          {summary.recalcFailed > 0 && <i>계산 실패 {summary.recalcFailed}</i>}
        </span>
        {lastBulk && (
          <span
            data-testid="rt-bulk-result"
            data-targeted={lastBulk.targeted}
            data-applied={lastBulk.applied}
            data-skipped={skipped}
          >
            적용 {lastBulk.applied}, 건너뜀 {skipped}{' '}
            {lastBulk.skipped.map(describeSkip).join(' / ')}
          </span>
        )}
      </header>

      <RowStack
        window={window}
        rowCount={table.rows.length}
        selectedIds={table.selectedIds}
        classNames={STACK_CLASSES}
        renderRow={renderRow}
        onRenderRow={onRenderRow}
      />
    </section>
  );
}

interface CardProps {
  row: ReviewRow;
  selected: boolean;
  expanded: boolean;
  columns: readonly ColumnView[];
  categories: readonly string[];
  act(rowId: string, action: ReviewAction): ActionResult;
  retry(rowId: string): boolean;
  toggleSelected(rowId: string): void;
  toggleExpanded(rowId: string): void;
}

/** 카드의 속. 바깥 요소(role="row" 와 상태 표시)는 RowStack 이 만든다. 그 안에 칸 하나(role="gridcell")로 넣는다. */
function Card({
  row,
  selected,
  expanded,
  columns,
  categories,
  act,
  retry,
  toggleSelected,
  toggleExpanded,
}: CardProps) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const allowed = allowedActions(row.status);
  const canEdit = allowed.includes('edit');

  function run(action: ReviewAction) {
    const result = act(row.id, action);
    setError(result.ok ? null : ACTION_ERROR_MESSAGE[result.error]);
  }

  return (
    <div role="gridcell">
      <div className="rc-top">
        <input
          type="checkbox"
          aria-label="행 고르기"
          checked={selected}
          onChange={() => toggleSelected(row.id)}
        />
        <button
          type="button"
          aria-label={expanded ? '접기' : '펼치기'}
          aria-expanded={expanded}
          onClick={() => toggleExpanded(row.id)}
        >
          {expanded ? '−' : '+'}
        </button>
        <b>{STATUS_LABEL[row.status]}</b>
        {columns.map((column) => (
          <span key={column.id} data-column={column.id}>
            {column.header}:{' '}
            {column.render ? column.render(row) : (column.value(row) ?? '—')}
          </span>
        ))}
      </div>
      {expanded && (
        <div className="rc-body">
          <NativeSelect
            aria-label="카테고리 수정"
            value={currentCategory(row) ?? ''}
            disabled={!canEdit}
            onChange={(event) =>
              run({ type: 'edit', category: event.target.value })
            }
          >
            {currentCategory(row) === null && <option value="">없음</option>}
            {categories.map((category) => (
              <option key={category}>{category}</option>
            ))}
          </NativeSelect>
          {row.ai.candidates.map((candidate, index) => (
            <label key={candidate.id}>
              <input
                type="radio"
                name={`rc-candidate-${row.id}`}
                aria-label={`후보 ${index + 1} 고르기`}
                checked={currentCandidate(row)?.id === candidate.id}
                disabled={!canEdit}
                onChange={() =>
                  run({ type: 'edit', candidateId: candidate.id })
                }
              />
              {candidate.factorName} ({candidate.reason ?? '이유 없음'})
            </label>
          ))}
          {SIMPLE.filter((type) => allowed.includes(type)).map((type) => (
            <button
              key={type}
              type="button"
              disabled={checkAction(row, { type } as ReviewAction) !== null}
              onClick={() => run({ type } as ReviewAction)}
            >
              {ACTION_LABEL[type]}
            </button>
          ))}
          {allowed.includes('reject') && (
            <>
              <input
                aria-label="반려 사유"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
              <button
                type="button"
                onClick={() => run({ type: 'reject', reason })}
              >
                {ACTION_LABEL.reject}
              </button>
            </>
          )}
          {isRecalcFailed(row) && (
            <span data-testid="rt-calc-failed">
              계산하지 못했다{' '}
              <button type="button" onClick={() => retry(row.id)}>
                다시 계산
              </button>
            </span>
          )}
          {error && <span role="alert">{error}</span>}
        </div>
      )}
    </div>
  );
}
