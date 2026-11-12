// card ↔ load-skeleton 가져오기 고리 가드(밴드 DT1, sid:MARC-ISSUE-373 — LD1 검증 권고 2). 둘 다 막대는 skeleton-bar 에서 가져온다.
// 원문은 Vite 의 ?raw 로 읽는다(모양을 그리지 않는 글자 검사).
import { describe, expect, it } from 'vitest';

const raw = (files: Record<string, unknown>) =>
  Object.entries(files).map(([path, text]) => ({ path, text: String(text) }));
const CARD = raw(
  import.meta.glob('../../card/**/*.{ts,tsx}', {
    query: '?raw',
    import: 'default',
    eager: true,
  }),
);
const LOAD_SKELETON = raw(
  import.meta.glob('../../load-skeleton/**/*.{ts,tsx}', {
    query: '?raw',
    import: 'default',
    eager: true,
  }),
);
/** <part> 폴더를 가져오는 문이 있는 파일(경로에 /<part>/ 가 든 가져오기 — from·맨 가져오기·import() 셋, 검증 권고 R1). */
const importing = (files: { path: string; text: string }[], part: string) =>
  files
    .filter(({ text }) =>
      new RegExp(
        `(?:\\bfrom\\s+|\\bimport\\s*\\(?\\s*)['"][^'"]*/${part}/`,
      ).test(text),
    )
    .map(({ path }) => path);

describe('skeleton-bar 고리 가드', () => {
  it('card 는 load-skeleton 을 가져오지 않는다(load-skeleton 이 Card 를 쓰니 고리 0)', () => {
    expect(CARD.length).toBeGreaterThan(0);
    expect(LOAD_SKELETON.length).toBeGreaterThan(0);
    const both =
      importing(CARD, 'load-skeleton').length > 0 &&
      importing(LOAD_SKELETON, 'card').length > 0;
    expect(both).toBe(false);
    expect(importing(CARD, 'load-skeleton')).toEqual([]);
  });

  it('둘 다 막대는 skeleton-bar 공개 표면에서 가져온다', () => {
    expect(importing(CARD, 'skeleton-bar').length).toBeGreaterThan(0);
    expect(importing(LOAD_SKELETON, 'skeleton-bar').length).toBeGreaterThan(0);
  });
});
