// @vitest-environment jsdom
// 불러오기 실패·없음 상자(밴드 LE1 ①, sid:MARC-ENT-260 ②③): failed = 오류 안내 + [다시 시도] + [목록으로],
// missing = 회색 안내 + [목록으로] 하나(다시 시도 없음). 둘 다 role="alert".
// actionRef 는 첫 단추에 붙는다(밴드 LA1 ①): failed 는 [다시 시도], missing·다시 시도 없는 failed 는 [목록으로].
import { createRef } from 'react';

import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { GW_TEXT } from '../config/text.ts';
import { LoadFailure } from './LoadFailure.tsx';

afterEach(cleanup);

describe('LoadFailure', () => {
  it('failed: 오류 꼴 글 + [다시 시도]·[목록으로], 누르면 각 콜백', () => {
    const onRetry = vi.fn();
    const onList = vi.fn();
    render(
      <LoadFailure
        kind="failed"
        message="결과를 불러오지 못했어요"
        onRetry={onRetry}
        onList={onList}
      />,
    );
    const box = screen.getByRole('alert');
    expect(box.getAttribute('data-kind')).toBe('failed');
    expect(box.querySelector('[data-tone]')?.getAttribute('data-tone')).toBe(
      'error',
    );
    expect(box.textContent).toContain('결과를 불러오지 못했어요');
    const buttons = screen.getAllByRole('button');
    expect(buttons.map((b) => b.textContent)).toEqual([
      GW_TEXT.load.retry,
      GW_TEXT.load.toList,
    ]);
    fireEvent.click(buttons[0]!);
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onList).not.toHaveBeenCalled();
    fireEvent.click(buttons[1]!);
    expect(onList).toHaveBeenCalledTimes(1);
  });

  it('failed 에 onList 가 없으면 [다시 시도] 하나(GW-01 목록 화면의 꼴)', () => {
    render(
      <LoadFailure kind="failed" message="문서 목록을" onRetry={() => {}} />,
    );
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.retry,
    ]);
  });

  it('missing: 회색(기본) 글 + [목록으로] 하나 — onRetry 를 받아도 [다시 시도]는 그리지 않는다', () => {
    render(
      <LoadFailure
        kind="missing"
        message="결과를 찾을 수 없어요"
        onRetry={() => {}}
        onList={() => {}}
      />,
    );
    const box = screen.getByRole('alert');
    expect(box.getAttribute('data-kind')).toBe('missing');
    expect(box.querySelector('[data-tone]')?.getAttribute('data-tone')).toBe(
      'default',
    );
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      GW_TEXT.load.toList,
    ]);
  });

  it('단추 이름을 받는다', () => {
    render(
      <LoadFailure
        kind="failed"
        message="x"
        onRetry={() => {}}
        onList={() => {}}
        retryLabel="또"
        listLabel="뒤로"
      />,
    );
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      '또',
      '뒤로',
    ]);
  });

  it('actionRef 는 첫 단추: failed 는 [다시 시도], missing 은 [목록으로](onRetry 를 받아도), 다시 시도 없는 failed 는 [목록으로]', () => {
    const failed = createRef<HTMLButtonElement>();
    const view = render(
      <LoadFailure
        kind="failed"
        message="x"
        onRetry={() => {}}
        onList={() => {}}
        actionRef={failed}
      />,
    );
    expect(failed.current?.textContent).toBe(GW_TEXT.load.retry);
    view.unmount();

    const missing = createRef<HTMLButtonElement>();
    const second = render(
      <LoadFailure
        kind="missing"
        message="x"
        onRetry={() => {}}
        onList={() => {}}
        actionRef={missing}
      />,
    );
    expect(missing.current?.textContent).toBe(GW_TEXT.load.toList);
    second.unmount();

    const listOnly = createRef<HTMLButtonElement>();
    render(
      <LoadFailure
        kind="failed"
        message="x"
        onList={() => {}}
        actionRef={listOnly}
      />,
    );
    expect(listOnly.current?.textContent).toBe(GW_TEXT.load.toList);
  });

  it('LA1 ② (캔버스 v84 CM-03): 한 문장짜리 불러오기 실패 글은 끝 마침표 없음, 두 문장 글 안의 마침표는 남음', () => {
    const texts = [
      GW_TEXT.list.loadFailed,
      GW_TEXT.result.invalid,
      GW_TEXT.result.failed,
      GW_TEXT.result.missing,
      GW_TEXT.reviewScreen.invalid.result,
      GW_TEXT.reviewScreen.invalid.review,
      GW_TEXT.reviewScreen.failed.result,
      GW_TEXT.reviewScreen.failed.review,
      GW_TEXT.reviewScreen.missing.result,
      GW_TEXT.reviewScreen.missing.review,
      GW_TEXT.status.missing,
    ];
    for (const text of texts) expect(text).not.toMatch(/[.。]$/);
    // 두 문장 글 안의 마침표는 둔다(sid:MARC-ENT-269) — 끝만 뺀다.
    expect(GW_TEXT.reviewScreen.saveRejected).toMatch(/요\. \S.*[^.]$/);
  });
});
