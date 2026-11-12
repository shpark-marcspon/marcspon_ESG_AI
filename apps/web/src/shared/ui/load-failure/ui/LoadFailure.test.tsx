// @vitest-environment jsdom
// 불러오기 실패·없음 상자(밴드 TRW0a ① — 그린워싱에서 shared 로 올림): failed 는 단추 둘, missing 은 [목록으로] 하나,
// 콜백이 없으면 단추 0, actionRef 는 첫 단추. 단추 이름의 기본은 PARTS_TEXT.load.
import { createRef } from 'react';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { LoadFailure } from './LoadFailure.tsx';

afterEach(cleanup);

describe('LoadFailure', () => {
  it('failed: 기본 이름의 단추 둘, 누르면 각 콜백, actionRef 는 [다시 시도]', () => {
    const onRetry = vi.fn();
    const onList = vi.fn();
    const ref = createRef<HTMLButtonElement>();
    render(
      <LoadFailure
        kind="failed"
        message="못 불러옴"
        onRetry={onRetry}
        onList={onList}
        actionRef={ref}
      />,
    );
    expect(screen.getByRole('alert').getAttribute('data-kind')).toBe('failed');
    expect(screen.getAllByRole('button')).toHaveLength(2);
    const retry = screen.getByRole('button', { name: PARTS_TEXT.load.retry });
    expect(ref.current).toBe(retry);
    fireEvent.click(retry);
    fireEvent.click(
      screen.getByRole('button', { name: PARTS_TEXT.load.toList }),
    );
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onList).toHaveBeenCalledTimes(1);
  });

  it('missing: [목록으로] 하나(다시 시도 콜백이 있어도), actionRef 는 그 단추', () => {
    const ref = createRef<HTMLButtonElement>();
    render(
      <LoadFailure
        kind="missing"
        message="없음"
        onRetry={vi.fn()}
        onList={vi.fn()}
        actionRef={ref}
      />,
    );
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]!.textContent).toBe(PARTS_TEXT.load.toList);
    expect(ref.current).toBe(buttons[0]);
  });

  it('콜백이 없으면 단추 0, 받은 이름을 쓴다', () => {
    const { rerender } = render(
      <LoadFailure kind="failed" message="못 불러옴" />,
    );
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    rerender(
      <LoadFailure
        kind="failed"
        message="못 불러옴"
        onRetry={vi.fn()}
        retryLabel="다시"
      />,
    );
    expect(screen.getByRole('button').textContent).toBe('다시');
  });
});
