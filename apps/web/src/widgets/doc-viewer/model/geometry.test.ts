import { describe, expect, it } from 'vitest';

import {
  PAGE_GAP,
  boxToScreenRect,
  pageAtScroll,
  pageOffsets,
  pageScreenSize,
  scrollLeftForBox,
  scrollTopAfterResize,
  scrollTopForBox,
  totalHeight,
  visiblePageRange,
} from './geometry.ts';
import type { Box } from './geometry.ts';

const page = { width: 600, height: 800 };
// 왼쪽 위 구석 가까이에 있는 상자. 뒤집히거나 돌면 어디로 가는지 알아보기 쉽다.
const box: Box = [100, 50, 300, 90];

describe('boxToScreenRect', () => {
  it('배율 1, 회전 없음: 좌표가 그대로 화면 자리다(왼쪽 위 원점, 뒤집지 않는다)', () => {
    expect(boxToScreenRect(box, page, 1)).toEqual({
      left: 100,
      top: 50,
      width: 200,
      height: 40,
    });
  });

  it('배율을 곱한다', () => {
    expect(boxToScreenRect(box, page, 1.5)).toEqual({
      left: 150,
      top: 75,
      width: 300,
      height: 60,
    });
    expect(boxToScreenRect(box, page, 0.5)).toEqual({
      left: 50,
      top: 25,
      width: 100,
      height: 20,
    });
  });

  it('90도: 쪽의 위쪽이 화면의 오른쪽으로 간다', () => {
    // 돌린 쪽은 800×600. 위에서 50~90 이던 것이 오른쪽에서 50~90, 곧 왼쪽에서 710~750.
    expect(boxToScreenRect(box, page, 1, 90)).toEqual({
      left: 710,
      top: 100,
      width: 40,
      height: 200,
    });
  });

  it('180도: 왼쪽 위가 오른쪽 아래로 간다', () => {
    expect(boxToScreenRect(box, page, 1, 180)).toEqual({
      left: 300,
      top: 710,
      width: 200,
      height: 40,
    });
  });

  it('270도: 쪽의 위쪽이 화면의 왼쪽으로 간다', () => {
    // 돌린 쪽은 800×600. 왼쪽에서 100~300 이던 것이 아래에서 100~300, 곧 위에서 300~500.
    expect(boxToScreenRect(box, page, 1, 270)).toEqual({
      left: 50,
      top: 300,
      width: 40,
      height: 200,
    });
  });

  it('회전과 배율을 같이', () => {
    expect(boxToScreenRect(box, page, 2, 90)).toEqual({
      left: 1420,
      top: 200,
      width: 80,
      height: 400,
    });
  });

  it('네 번 돌리면 제자리다(상자가 늘 쪽 안에 있다)', () => {
    for (const rotation of [0, 90, 180, 270] as const) {
      const rect = boxToScreenRect(box, page, 1, rotation);
      const size = pageScreenSize(page, 1, rotation);
      expect(rect.left).toBeGreaterThanOrEqual(0);
      expect(rect.top).toBeGreaterThanOrEqual(0);
      expect(rect.left + rect.width).toBeLessThanOrEqual(size.width);
      expect(rect.top + rect.height).toBeLessThanOrEqual(size.height);
    }
  });
});

describe('쪽 쌓기', () => {
  const pages = Array.from({ length: 112 }, () => page);

  it('pageScreenSize: 90·270 도면 가로와 세로가 바뀐다', () => {
    expect(pageScreenSize(page, 2)).toEqual({ width: 1200, height: 1600 });
    expect(pageScreenSize(page, 2, 90)).toEqual({ width: 1600, height: 1200 });
  });

  it('pageOffsets: 쪽마다 틈을 두고 아래로 쌓인다', () => {
    expect(pageOffsets(pages, 1).slice(0, 3)).toEqual([
      PAGE_GAP,
      PAGE_GAP + 800 + PAGE_GAP,
      PAGE_GAP + 2 * (800 + PAGE_GAP),
    ]);
    expect(totalHeight(pages, 1)).toBe(PAGE_GAP + 112 * (800 + PAGE_GAP));
  });

  it('visiblePageRange: 112쪽 가운데 보이는 쪽과 앞뒤 한 쪽만', () => {
    expect(visiblePageRange(0, 900, pages, 1)).toEqual({ first: 1, last: 3 });
    // 50쪽의 한가운데를 보고 있다.
    const top = pageOffsets(pages, 1)[49]! + 100;
    expect(visiblePageRange(top, 600, pages, 1)).toEqual({
      first: 49,
      last: 51,
    });
    // 맨 끝.
    expect(
      visiblePageRange(totalHeight(pages, 1) - 900, 900, pages, 1),
    ).toEqual({ first: 110, last: 112 });
  });

  it('visiblePageRange: 화면 높이를 아직 모를 때(0)는 첫 쪽들', () => {
    expect(visiblePageRange(0, 0, pages, 1)).toEqual({ first: 1, last: 2 });
  });

  it('pageAtScroll: 화면의 보는 줄(위에서 3분의 1)에 걸린 쪽', () => {
    expect(pageAtScroll(0, 900, pages, 1)).toBe(1);
    expect(pageAtScroll(pageOffsets(pages, 1)[9]!, 900, pages, 1)).toBe(10);
    // 줄이 쪽 사이 틈에 있으면 앞 쪽이다. 10쪽의 윗변이 줄에 닿는 순간부터 10쪽이다.
    expect(pageAtScroll(pageOffsets(pages, 1)[9]! - 301, 900, pages, 1)).toBe(
      9,
    );
    expect(pageAtScroll(pageOffsets(pages, 1)[9]! - 300, 900, pages, 1)).toBe(
      10,
    );
  });

  it('강조로 간 뒤의 「지금 쪽」은 그 강조가 있는 쪽이다(상자가 쪽 맨 아래에 있어도)', () => {
    // 쪽 높이 800 의 맨 아래에 붙은 상자. 화면 가운데 줄로 치면 다음 쪽이 나오던 자리다.
    const atBottom: Box = [50, 770, 150, 800];
    for (const scale of [0.75, 1, 2]) {
      for (const viewport of [600, 900, 1400]) {
        expect(
          pageAtScroll(
            scrollTopForBox(5, atBottom, viewport, pages, scale),
            viewport,
            pages,
            scale,
          ),
        ).toBe(5);
      }
    }
  });

  it('scrollTopForBox: 상자가 화면 높이의 3분의 1 지점에 온다', () => {
    const top = scrollTopForBox(10, box, 900, pages, 1);
    expect(top).toBe(pageOffsets(pages, 1)[9]! + 50 - 300);
    // 배율이 바뀌면 쪽의 자리와 상자의 자리가 같이 바뀐다.
    expect(scrollTopForBox(10, box, 900, pages, 2)).toBe(
      pageOffsets(pages, 2)[9]! + 100 - 300,
    );
    // 첫 쪽 맨 위의 상자는 0 아래로 내려가지 않는다.
    expect(scrollTopForBox(1, box, 900, pages, 1)).toBe(0);
    // 없는 쪽이면 0.
    expect(scrollTopForBox(999, box, 900, pages, 1)).toBe(0);
  });

  it('scrollTopAfterResize: 확대해도 보던 쪽의 같은 높이를 본다', () => {
    const before = pageOffsets(pages, 1)[19]! + 400; // 20쪽의 절반
    const after = scrollTopAfterResize(
      before,
      pages,
      { scale: 1, rotation: 0 },
      { scale: 2, rotation: 0 },
    );
    expect(after).toBe(pageOffsets(pages, 2)[19]! + 800);
  });

  it('scrollLeftForBox: 쪽이 화면보다 넓으면 상자의 가운데를 화면 가운데에, 좁으면 0', () => {
    // 배율 1: 쪽 600 이 화면 1000 안에 다 들어온다.
    expect(scrollLeftForBox(1, box, 1000, pages, 1)).toBe(0);
    // 배율 2: 쪽 1200 + 양옆 틈. 상자(화면 좌표 200~600)의 가운데 400 이 화면(폭 500) 가운데에 온다.
    expect(scrollLeftForBox(1, box, 500, pages, 2)).toBe(PAGE_GAP + 400 - 250);
    // 오른쪽 끝의 상자는 끝까지만 간다.
    expect(scrollLeftForBox(1, [560, 50, 600, 90], 500, pages, 2)).toBe(
      1200 + 2 * PAGE_GAP - 500,
    );
  });
});
