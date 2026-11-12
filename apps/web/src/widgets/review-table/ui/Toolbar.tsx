// 표 위의 띠: 걸러 보기, 요약, 일괄 동작.
import { useState } from 'react';

import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import type { BulkScope, ReviewBoard } from '../hooks/index.ts';
import {
  ACTION_LABEL,
  STATUSES,
  STATUS_LABEL,
  describeSkip,
  skippedCount,
} from '../model/index.ts';
import type { ReviewStatus } from '../model/index.ts';
import { formatEmission } from './format.ts';

export function Toolbar({
  board,
  categories,
}: {
  board: ReviewBoard;
  categories: readonly string[];
}) {
  const [scope, setScope] = useState<BulkScope>('filtered');
  const { table, summary, lastBulk } = board;
  const { filter } = table;
  const selectedShown = table.targetIds('selected').length;
  const skipped = lastBulk ? skippedCount(lastBulk) : 0;

  return (
    <div className="rt-toolbar">
      <div className="rt-toolbar-line">
        <input
          aria-label="글자로 걸러 보기"
          placeholder="글자로 걸러 보기"
          value={filter.text}
          onChange={(event) => table.setFilter({ text: event.target.value })}
        />
        <NativeSelect
          aria-label="상태로 걸러 보기"
          value={filter.statuses[0] ?? ''}
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
          value={filter.category ?? ''}
          onChange={(event) =>
            table.setFilter({ category: event.target.value || null })
          }
        >
          <option value="">모든 카테고리</option>
          {categories.map((category) => (
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </NativeSelect>
        <span data-testid="rt-shown" data-shown={table.rows.length}>
          {table.rows.length.toLocaleString('ko')} /{' '}
          {board.totalRows.toLocaleString('ko')}행
        </span>
      </div>

      <div
        className="rt-toolbar-line rt-summary"
        data-testid="rt-summary"
        data-total={summary.total}
        data-final-total={summary.finalTotal}
        data-provisional-total={summary.provisionalTotal}
        data-recalc-pending={summary.recalcPending}
        data-recalc-failed={summary.recalcFailed}
      >
        {STATUSES.map((status) => (
          <span
            key={status}
            data-status-count={status}
            data-count={summary.byStatus[status]}
          >
            {STATUS_LABEL[status]}{' '}
            {summary.byStatus[status].toLocaleString('ko')}
          </span>
        ))}
        <strong>확정 합계 {formatEmission(summary.finalTotal)}</strong>
        <span>
          임시 합계(반영·수정, 확정 전){' '}
          {formatEmission(summary.provisionalTotal)}
        </span>
        {summary.recalcPending > 0 && (
          <span>재계산 대기 {summary.recalcPending}</span>
        )}
        {summary.recalcFailed > 0 && (
          <span className="rt-error">
            계산 실패 {summary.recalcFailed.toLocaleString('ko')}
          </span>
        )}
      </div>

      <div className="rt-toolbar-line">
        <NativeSelect
          aria-label="일괄 대상"
          value={scope}
          onChange={(event) => setScope(event.target.value as BulkScope)}
        >
          <option value="filtered">
            걸러 본 결과 전체 ({table.rows.length.toLocaleString('ko')})
          </option>
          <option value="selected">
            고른 행 ({selectedShown.toLocaleString('ko')})
          </option>
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
        {lastBulk && (
          <span
            data-testid="rt-bulk-result"
            data-targeted={lastBulk.targeted}
            data-applied={lastBulk.applied}
            data-skipped={skipped}
          >
            일괄 {ACTION_LABEL[lastBulk.action]}: 대상{' '}
            {lastBulk.targeted.toLocaleString('ko')} · 적용{' '}
            {lastBulk.applied.toLocaleString('ko')} · 건너뜀{' '}
            {skipped.toLocaleString('ko')}
            {lastBulk.skipped.length > 0 &&
              ` (${lastBulk.skipped.map(describeSkip).join(' / ')})`}
          </span>
        )}
      </div>
    </div>
  );
}
