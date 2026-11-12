// 펼친 행의 속. 후보 목록에서 고르기, 카테고리 고치기, 상태를 바꾸는 단추들.
// 어떤 단추가 보이는지는 전이표(model/transitions.ts)가 정한다. 이 파일은 규칙을 모른다.
import { useState } from 'react';

import { NativeSelect } from '../../../shared/ui/filter-select/index.ts';
import {
  ACTION_ERROR_MESSAGE,
  ACTION_LABEL,
  allowedActions,
  checkAction,
  currentCandidate,
  currentCategory,
  currentEmission,
  isRecalcFailed,
  isRecalcPending,
} from '../model/index.ts';
import type {
  ActionResult,
  ActionType,
  ReviewAction,
  ReviewRow,
} from '../model/index.ts';
import { formatEmission } from './format.ts';

interface Props {
  row: ReviewRow;
  categories: readonly string[];
  act(rowId: string, action: ReviewAction): ActionResult;
  retry(rowId: string): boolean;
}

const CONFIDENCE_LABEL = { high: '높음', medium: '중간', low: '낮음' } as const;

/** 단추 하나로 끝나는 동작들. 수정과 반려는 값을 받아야 해서 따로 그린다. */
const SIMPLE: readonly ActionType[] = [
  'accept',
  'decline',
  'rerequest',
  'finalize',
  'reopen',
  'unfinalize',
];

export function RowDetail({ row, categories, act, retry }: Props) {
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  function run(action: ReviewAction) {
    const result = act(row.id, action);
    setError(result.ok ? null : ACTION_ERROR_MESSAGE[result.error]);
    if (result.ok && action.type === 'reject') setReason('');
  }

  const allowed = allowedActions(row.status);
  const canEdit = allowed.includes('edit');
  const picked = currentCandidate(row);
  const representative = row.ai.candidates[0];

  return (
    <div className="rt-detail">
      <div className="rt-detail-line">
        <span data-testid="rt-original">
          AI 원본: 카테고리 {row.ai.category ?? '없음'} · 후보{' '}
          {representative?.factorName ?? '없음'} · 배출량{' '}
          {formatEmission(representative?.emission ?? null)}
        </span>
        {row.edit && (
          <span data-testid="rt-edited" className="rt-edited">
            수정: 카테고리 {currentCategory(row) ?? '없음'} · 후보{' '}
            {picked?.factorName ?? '없음'} · 배출량{' '}
            {isRecalcPending(row) ?
              '재계산 대기'
            : isRecalcFailed(row) ?
              '계산하지 못했다'
            : formatEmission(currentEmission(row))}
          </span>
        )}
      </div>
      {/* 계산 실패는 「배출량 없음」과 다르다. 다시 부를 수 있다. 무엇이 실패인지는 업무 로직(isRecalcFailed)이 안다. */}
      {isRecalcFailed(row) && (
        <div className="rt-detail-line rt-error" data-testid="rt-calc-failed">
          배출량을 계산하지 못했다(계산이 실패했다). 다시 계산하기 전에는 최종
          확정할 수 없다.
          <button type="button" onClick={() => retry(row.id)}>
            다시 계산
          </button>
        </div>
      )}
      {row.ai.categoryNote && (
        <div className="rt-note">분류 이유: {row.ai.categoryNote}</div>
      )}

      <label className="rt-detail-line">
        카테고리{' '}
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
            <option key={category} value={category}>
              {category}
            </option>
          ))}
        </NativeSelect>
      </label>

      {row.ai.candidates.length === 0 ?
        <p className="rt-note">후보가 없다.</p>
      : <ol className="rt-candidates">
          {row.ai.candidates.map((candidate, index) => (
            <li key={candidate.id}>
              <label>
                <input
                  type="radio"
                  name={`rt-candidate-${row.id}`}
                  aria-label={`후보 ${index + 1} 고르기`}
                  checked={picked?.id === candidate.id}
                  disabled={!canEdit}
                  onChange={() =>
                    run({ type: 'edit', candidateId: candidate.id })
                  }
                />{' '}
                {index === 0 && <span className="rt-tag">대표</span>}{' '}
                {candidate.factorName}
              </label>
              <span className="rt-candidate-facts">
                계수 {candidate.factorValue ?? '값 없음'} {candidate.factorUnit}
                {candidate.source && ` · ${candidate.source}`} · 신뢰도{' '}
                {candidate.confidence ?
                  CONFIDENCE_LABEL[candidate.confidence]
                : '없음'}{' '}
                · 계산 결과 {formatEmission(candidate.emission)}
              </span>
              <span className="rt-note">
                적용 기준: {candidate.reason ?? '자료에 없음'}
              </span>
            </li>
          ))}
        </ol>
      }

      <div className="rt-actions">
        {SIMPLE.filter((type) => allowed.includes(type)).map((type) => {
          const blocked = checkAction(row, { type } as ReviewAction);
          return (
            <button
              key={type}
              type="button"
              disabled={blocked !== null}
              title={blocked ? ACTION_ERROR_MESSAGE[blocked] : undefined}
              onClick={() => run({ type } as ReviewAction)}
            >
              {ACTION_LABEL[type]}
            </button>
          );
        })}
        {allowed.includes('reject') && (
          <span className="rt-reject">
            <input
              aria-label="반려 사유"
              placeholder="반려 사유"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
            <button
              type="button"
              onClick={() => run({ type: 'reject', reason })}
            >
              {ACTION_LABEL.reject}
            </button>
          </span>
        )}
      </div>
      {row.status === 'rejected' && (
        <div className="rt-note">반려 사유: {row.rejectReason}</div>
      )}
      {error && (
        <div role="alert" className="rt-error">
          {error}
        </div>
      )}
      <div className="rt-note">
        검토 이력(누가·언제)을 보일 자리. 아직 없다.
      </div>
    </div>
  );
}
