// @vitest-environment jsdom
// 그린워싱 움직임(밴드 GA1b): 움직임 줄임이면 숫자는 끝 값 그대로, 움직임 클래스는 모두 no-preference 안, 고리 색은 토큰 변수.
import { cleanup, render, waitFor } from '@testing-library/react';

import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CountUp } from './CountUp.tsx';
import { useCountUp } from './CountUp.tsx';

const CSS = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), 'motion.css'),
  'utf8',
).replace(/\/\*[\s\S]*?\*\//g, '');

/** prefers-reduced-motion: reduce 의 답을 정해 둔 matchMedia. */
function stubMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: query.includes('reduce') ? reduce : !reduce,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('CountUp — 움직임 줄임', () => {
  it('움직임을 줄였으면 처음부터 끝 값이고, 값이 바뀌어도 바로 새 값이다', () => {
    stubMotion(true);
    const { container, rerender } = render(<CountUp value={37} />);
    expect(container.textContent).toBe('37');
    rerender(<CountUp value={52} />);
    expect(container.textContent).toBe('52');
  });

  it('움직임을 켰으면 0 에서 시작해 끝 값까지 굴러가고, 도중의 수는 0~끝 값 안에서 줄지 않는다', async () => {
    stubMotion(false);
    const { container } = render(<CountUp value={37} durationMs={1} />);
    expect(container.textContent).toBe('0');
    // waitFor 는 글자가 바뀔 때마다 부른다 — 그 사이 그린 수를 모두 모은다
    const seen: number[] = [];
    await waitFor(() => {
      seen.push(Number(container.textContent));
      expect(container.textContent).toBe('37');
    });
    expect(seen.every((n) => n >= 0 && n <= 37)).toBe(true);
    expect(seen).toEqual([...seen].sort((a, b) => a - b));
  });
});

describe('useCountUp — 시작 값 from(밴드 TRP5)', () => {
  function Shown({ value, from }: { value: number; from: number }) {
    return <>{useCountUp(value, 1, { from })}</>;
  }

  it('움직임을 켜도 from = value 면 첫 그림부터 value, 그 뒤 바뀜은 앞 값에서 굴러간다', async () => {
    stubMotion(false);
    const { container, rerender } = render(<Shown value={37} from={37} />);
    expect(container.textContent).toBe('37');
    rerender(<Shown value={52} from={37} />);
    // 바뀐 직후는 앞 값 그대로(0 으로 돌아가지 않는다) — 다음 프레임부터 굴러간다
    expect(container.textContent).toBe('37');
    const seen: number[] = [];
    await waitFor(() => {
      seen.push(Number(container.textContent));
      expect(container.textContent).toBe('52');
    });
    expect(seen.every((n) => n >= 37 && n <= 52)).toBe(true);
    expect(seen).toEqual([...seen].sort((a, b) => a - b));
  });
});

describe('motion.css', () => {
  it('gw-m- 클래스 규칙은 모두 prefers-reduced-motion: no-preference 안에만 있다', () => {
    const open = CSS.indexOf('@media (prefers-reduced-motion: no-preference)');
    expect(open).toBeGreaterThanOrEqual(0);
    // 미디어 블록의 끝(괄호 짝)
    let depth = 0;
    let close = -1;
    for (let at = CSS.indexOf('{', open); at < CSS.length; at++) {
      if (CSS[at] === '{') depth++;
      else if (CSS[at] === '}' && --depth === 0) {
        close = at;
        break;
      }
    }
    const inside = CSS.slice(open, close);
    const outside = CSS.slice(0, open) + CSS.slice(close + 1);
    expect(inside).toMatch(/\.gw-m-ring\b/);
    // 온실가스 DB3(sid:MARC-TICK-538): 새 클래스 둘도 no-preference 안 · keyframes 는 블록 밖 끝 줄
    expect(inside).toMatch(/\.gw-m-grow-y\s*\{/);
    expect(inside).toMatch(/\.gw-m-sweep\s*\{/);
    expect(outside).not.toMatch(/\.gw-m-/);
    expect(outside).toMatch(/@keyframes gw-m-grow-y\s*\{/);
    expect(outside).toMatch(/@keyframes gw-m-sweep\s*\{/);
  });

  it('고리 색은 support-orange 토큰 변수이고, 직접 쓴 색은 막대 빛줄기의 흰색뿐이다', () => {
    const ring = /@keyframes gw-m-ring\s*\{[\s\S]*?\n\}/.exec(CSS)?.[0] ?? '';
    expect(ring.match(/var\(--marcspon-token-support-orange\)/g)).toHaveLength(
      2,
    );
    // 알파는 처음 45% → 끝 0%(디자인 6c 값 — 밴드 GP4 R1: 값이 바뀌면 빨강)
    expect(
      [
        ...ring.matchAll(
          /color-mix\(in srgb, var\(--marcspon-token-support-orange\) (\d+)%, transparent\)/g,
        ),
      ].map((m) => m[1]),
    ).toEqual(['45', '0']);
    const literals = CSS.match(
      /#[0-9a-f]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)/gi,
    );
    expect(literals).toEqual(['rgb(255 255 255 / 0.45)']);
  });
});
