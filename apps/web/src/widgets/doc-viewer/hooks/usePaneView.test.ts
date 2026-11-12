// @vitest-environment jsdom
// 문서 칸의 보기 상태를 화면 없이 본다. 스크롤 상자가 없다: 훅이 「어디로 가라」고 한 값(scrollRequest)만 읽는다.
import { act, renderHook } from '@testing-library/react';

import { describe, expect, it } from 'vitest';

import { PAGE_GAP, pageOffsets } from '../model/index.ts';
import { TEST_PAGES as pages } from '../model/testing.ts';
import { usePaneView } from './usePaneView.ts';

function setup() {
  const hook = renderHook(() => usePaneView(pages));
  return () => hook.result.current;
}

describe('usePaneView', () => {
  it('처음: 배율 1, 회전 0, 1쪽. 화면 높이를 모르면(0) 첫 쪽과 다음 쪽을 그린다', () => {
    const pane = setup();
    expect([pane().scale, pane().rotation, pane().currentPage]).toEqual([
      1, 0, 1,
    ]);
    expect(pane().visiblePages).toEqual([1, 2]);
    expect(pane().scrollRequest).toBeNull();
    expect(pane().offsets).toEqual(pageOffsets(pages, 1));
    expect(pane().stackMinWidth).toBe(600 + 2 * PAGE_GAP);
  });

  it('스크롤을 알려 주면 지금 쪽과 그릴 쪽이 따라간다', () => {
    const pane = setup();
    act(() => pane().reportViewportHeight(900));
    act(() => pane().reportScroll(pageOffsets(pages, 1)[3]!));
    expect(pane().currentPage).toBe(4);
    expect(pane().visiblePages).toEqual([3, 4, 5]);
    // 사람이 스크롤한 것이다. 훅이 가라고 한 것이 아니다.
    expect(pane().scrollRequest).toBeNull();
  });

  it('쪽 이동: 그 쪽의 맨 위(쪽 사이 틈이 보이는 자리)로 가라고 하고, 지금 쪽이 바로 바뀐다', () => {
    const pane = setup();
    act(() => pane().reportViewportHeight(900));
    act(() => pane().goToPage(2));
    expect(pane().scrollRequest).toEqual({
      top: pageOffsets(pages, 1)[1]! - PAGE_GAP,
      seq: 1,
    });
    expect(pane().currentPage).toBe(2);
  });

  it('쪽 이동: 범위를 벗어난 번호는 끝 쪽으로 끌어온다. 같은 쪽으로 다시 가도 seq 가 올라간다', () => {
    const pane = setup();
    act(() => pane().goToPage(99));
    expect(pane().scrollRequest).toEqual({
      top: pageOffsets(pages, 1)[4]! - PAGE_GAP,
      seq: 1,
    });
    act(() => pane().goToPage(0));
    expect(pane().scrollRequest).toEqual({ top: 0, seq: 2 });
    act(() => pane().goToPage(1));
    expect(pane().scrollRequest).toEqual({ top: 0, seq: 3 });
  });

  it('확대·축소는 정해진 단계를 밟고, 끝에서는 더 가지 않는다', () => {
    const pane = setup();
    const scales: number[] = [];
    for (let i = 0; i < 6; i++) {
      act(() => pane().zoomIn());
      scales.push(pane().scale);
    }
    expect(scales).toEqual([1.25, 1.5, 2, 3, 3, 3]);
    expect([pane().canZoomIn, pane().canZoomOut]).toEqual([false, true]);
    for (let i = 0; i < 8; i++) act(() => pane().zoomOut());
    expect(pane().scale).toBe(0.5);
    expect([pane().canZoomIn, pane().canZoomOut]).toEqual([true, false]);
  });

  it('확대해도 보던 자리에 머문다: 2쪽의 맨 위에서 확대하면 새 배율의 2쪽 맨 위로 가라고 한다', () => {
    const pane = setup();
    act(() => pane().reportViewportHeight(900));
    act(() => pane().goToPage(2));
    act(() => pane().zoomIn());
    expect(pane().scale).toBe(1.25);
    expect(pane().scrollRequest).toEqual({
      top: pageOffsets(pages, 1.25)[1]! - PAGE_GAP,
      seq: 2,
    });
    expect(pane().currentPage).toBe(2);
  });

  it('돌리면 90도씩 돌고 네 번이면 제자리다. 쪽의 폭과 높이가 바뀐다', () => {
    const pane = setup();
    const seen: number[] = [];
    for (let i = 0; i < 4; i++) {
      act(() => pane().rotate());
      seen.push(pane().rotation);
    }
    expect(seen).toEqual([90, 180, 270, 0]);
    act(() => pane().rotate());
    expect(pane().stackMinWidth).toBe(800 + 2 * PAGE_GAP);
  });

  it('폭 맞춤: 컴포넌트가 맡긴 함수로 스크롤 상자의 폭을 물어 배율을 정한다(소수 둘째 자리까지)', () => {
    const pane = setup();
    act(() => pane().attachViewport(() => ({ width: 1000, height: 700 })));
    act(() => pane().fitWidth());
    // (1000 - 양옆 틈 24 - 스크롤 막대 몫 16) / 600 = 1.6
    expect(pane().scale).toBe(1.6);
    act(() => pane().attachViewport(() => ({ width: 777, height: 700 })));
    act(() => pane().fitWidth());
    expect(pane().scale).toBe(1.22); // 737 / 600 = 1.2283…
  });

  it('폭 맞춤: 쪽마다 폭이 다르면 지금 보고 있는 쪽의 폭에 맞춘다(첫 쪽이 아니다)', () => {
    // 1쪽은 세로(폭 600), 2쪽은 가로로 넓은 쪽(폭 900), 3쪽은 그 사이(폭 700).
    const mixed = [
      { width: 600, height: 800 },
      { width: 900, height: 600 },
      { width: 700, height: 800 },
    ];
    const hook = renderHook(() => usePaneView(mixed));
    const pane = () => hook.result.current;
    act(() => pane().attachViewport(() => ({ width: 1000, height: 700 })));
    act(() => pane().reportViewportHeight(700));
    act(() => pane().goToPage(2));
    expect(pane().currentPage).toBe(2);
    act(() => pane().fitWidth());
    // (1000 - 양옆 틈 24 - 스크롤 막대 몫 16) / 900 = 1.0666…  (1쪽에 맞추면 1.6, 3쪽에 맞추면 1.37 이 되어 2쪽이 칸 밖으로 넘친다)
    expect(pane().scale).toBe(1.06);
  });

  it('폭 맞춤: 폭을 물을 데가 없거나 폭이 0 이면 아무 일도 없다', () => {
    const pane = setup();
    act(() => pane().fitWidth());
    act(() => pane().attachViewport(() => ({ width: 0, height: 0 })));
    act(() => pane().fitWidth());
    expect(pane().scale).toBe(1);
    expect(pane().scrollRequest).toBeNull();
  });
});
