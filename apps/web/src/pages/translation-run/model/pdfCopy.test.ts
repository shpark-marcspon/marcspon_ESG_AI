// 밴드 TRW14 ③: PDF 보기 「번역 복사」 글(copyTextOf). 값은 지어낸 것.
import { describe, expect, it } from 'vitest';

import { copyTextOf } from './pdfCopy.ts';
import type { PdfPair } from './pdfView.ts';

const pair = (rest: Partial<PdfPair> = {}): PdfPair => ({
  unit: 1,
  kind: 'block',
  unitKind: 'block',
  visual: false,
  source: ['지어낸 글'],
  translation: ['Made-up line'],
  ...rest,
});

describe('copyTextOf', () => {
  it('글 줄 하나는 그대로', () => {
    expect(copyTextOf(pair())).toBe('Made-up line');
  });

  it('글 줄 둘은 문단 사이 빈 줄로 잇는다', () => {
    expect(
      copyTextOf(
        pair({
          kind: 'group',
          translation: ['First made-up.', 'Second made-up.'],
        }),
      ),
    ).toBe('First made-up.\n\nSecond made-up.');
  });

  it('글 안 줄바꿈은 그대로 둔다', () => {
    expect(
      copyTextOf(pair({ translation: ['Line one\nline two', 'Next'] })),
    ).toBe('Line one\nline two\n\nNext');
  });

  it('칸을 맞춘 표(grid 2×3, 빈 칸 하나): 칸은 탭, 행은 줄 · 고른 칸과 상관없이 표 전체', () => {
    const grid = {
      rows: 2,
      cols: 3,
      cells: [
        { row: 0, col: 0, source: '가', translation: 'Item' },
        { row: 0, col: 1, source: '나', translation: '2025' },
        { row: 0, col: 2, source: '다', translation: '2026' },
        { row: 1, col: 0, source: '라', translation: 'Fake use' },
        // (1,1) 없음 = 빈 칸
        { row: 1, col: 2, source: '마', translation: '12' },
      ],
    };
    expect(
      copyTextOf(pair({ kind: 'table', grid, translation: ['ignored'] })),
    ).toBe('Item\t2025\t2026\nFake use\t\t12');
  });

  it('pipe 표 글: 머리 + 몸 행을 탭·줄로(나눔 줄 뺌) · 표 아닌 글과 섞이면 문단 사이 빈 줄', () => {
    expect(
      copyTextOf(
        pair({
          kind: 'table',
          translation: [
            '| Item | 2025 |\n| --- | ---: |\n| Fake A | 1,200 |\n| Fake B |  |',
            'Note below.',
          ],
        }),
      ),
    ).toBe('Item\t2025\nFake A\t1,200\nFake B\t\n\nNote below.');
  });

  it('번역 없음(source_only · translation null) → null', () => {
    expect(
      copyTextOf(pair({ kind: 'source_only', translation: null })),
    ).toBeNull();
    expect(copyTextOf(pair({ kind: 'missing', translation: null }))).toBeNull();
  });
});
