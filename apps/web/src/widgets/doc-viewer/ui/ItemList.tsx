// 항목 목록과, 골라진 항목의 검토 상태를 바꾸는 단추들.
import { useEffect, useRef } from 'react';

import { useReviewDraft } from '../hooks/index.ts';
import type { DocViewer } from '../hooks/index.ts';
import { ERROR_MESSAGE, STATUS_LABEL } from '../model/index.ts';
import type {
  ReviewAction,
  ReviewState,
  TransitionResult,
} from '../model/index.ts';

interface Props {
  viewer: DocViewer;
  onReview(itemId: string, action: ReviewAction): TransitionResult;
}

export function ItemList({ viewer, onReview }: Props) {
  const selectedRef = useRef<HTMLLIElement>(null);

  // 상자를 눌러 골랐을 때 목록도 그 항목이 보이는 데로 간다.
  useEffect(() => {
    selectedRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [viewer.selectedItemId]);

  return (
    <ol className="dv-items">
      {viewer.rows.map(({ item, selected, review, kinds, kindHidden }) => (
        <li
          key={item.id}
          ref={selected ? selectedRef : undefined}
          className="dv-item"
          data-item-id={item.id}
          data-selected={selected}
          // 숨기지 않고 흐리게만 한다. 숨기면 j·k 가 안 보이는 항목을 밟고, 그대로 두면 상자가 왜 안 보이는지 알 수 없다.
          data-kind-hidden={kindHidden}
          onMouseEnter={() => viewer.point('hover', item.id)}
          onMouseLeave={() => viewer.point('hover', null)}
        >
          <button
            type="button"
            className="dv-item-head"
            aria-current={selected}
            title={
              kindHidden ?
                '이 종류는 범례에서 꺼 두었다. 고르거나 가리키면 상자가 보인다'
              : undefined
            }
            onClick={() => viewer.select(item.id)}
            onFocus={() => viewer.point('focus', item.id)}
            onBlur={() => viewer.point('focus', null)}
          >
            <span className="dv-item-title">
              {kinds.map((kind) => (
                <i
                  key={kind}
                  className="dv-dot"
                  style={{ background: viewer.looks.get(kind)?.color }}
                  title={viewer.looks.get(kind)?.label}
                />
              ))}
              {item.title}
            </span>
            <span className="dv-status" data-status={review.status}>
              {STATUS_LABEL[review.status]}
            </span>
            {item.detail && (
              <span className="dv-item-detail">{item.detail}</span>
            )}
            {review.status === 'rejected' && (
              <span className="dv-item-reason">반려 사유: {review.reason}</span>
            )}
          </button>
          {/* 골라진 항목에만 있다. 다른 항목으로 가면 사라지므로 적다 만 사유도 같이 버려진다. */}
          {selected && (
            <ReviewControls
              review={review}
              onAction={(action) => onReview(item.id, action)}
            />
          )}
        </li>
      ))}
    </ol>
  );
}

function ReviewControls({
  review,
  onAction,
}: {
  review: ReviewState;
  onAction(action: ReviewAction): TransitionResult;
}) {
  const draft = useReviewDraft(onAction);
  const error = draft.error && <p role="alert">{ERROR_MESSAGE[draft.error]}</p>;

  if (review.status !== 'pending') {
    return (
      <div className="dv-review">
        <button type="button" onClick={draft.reopen}>
          검토대기로 되돌리기
        </button>
        {error}
      </div>
    );
  }
  return (
    <div className="dv-review">
      <button type="button" onClick={draft.confirm}>
        확정
      </button>
      <textarea
        value={draft.reason}
        onChange={(event) => draft.setReason(event.target.value)}
        placeholder="반려 사유(반려하려면 꼭 적는다)"
        aria-label="반려 사유"
        rows={2}
      />
      <button type="button" onClick={draft.reject}>
        반려
      </button>
      {error}
    </div>
  );
}
