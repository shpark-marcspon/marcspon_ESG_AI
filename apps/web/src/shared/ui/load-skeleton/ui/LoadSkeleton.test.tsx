// @vitest-environment jsdom
// 불러오기 스켈레톤(밴드 LE1 ①·LA1 ①): role="status"·숨긴 글(기본 PARTS_TEXT.loading), 블록은 보조기기에서 숨긴다.
// aria-busy 는 카드에 없다(쓰는 쪽의 화면 바깥 틀이 단다).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { PARTS_TEXT } from '../../text.ts';
import { LoadSkeleton } from './LoadSkeleton.tsx';

afterEach(cleanup);

describe('LoadSkeleton', () => {
  it('status 카드에 aria-busy 없음. 숨긴 글은 기본 「불러오는 중」', () => {
    render(<LoadSkeleton />);
    const box = screen.getByRole('status');
    expect(box.getAttribute('aria-busy')).toBeNull();
    expect(box.getAttribute('data-testid')).toBe('load-skeleton');
    expect(box.textContent).toBe(PARTS_TEXT.loading);
    expect(box.querySelector('.sr-only')?.textContent).toBe(PARTS_TEXT.loading);
  });

  it('숨긴 글을 받는다. 회색 블록(제목 하나·칸 넷·큰 칸 하나)은 aria-hidden', () => {
    render(<LoadSkeleton label="결과를 불러오는 중이에요" />);
    const box = screen.getByRole('status');
    expect(box.textContent).toBe('결과를 불러오는 중이에요');
    const hidden = [...box.children].filter(
      (child) => child.getAttribute('aria-hidden') === 'true',
    );
    expect(hidden).toHaveLength(3);
    expect(hidden[1]!.children).toHaveLength(4);
  });

  it('카드 이름(aria-label) = label. 수 칸은 900 아래 2열·위 4열, 블록은 움직임 없음(밴드 LD1, 6c)', () => {
    render(<LoadSkeleton label="결과를 불러오는 중이에요" />);
    const box = screen.getByRole('status', {
      name: '결과를 불러오는 중이에요',
    });
    expect(box.getAttribute('aria-label')).toBe('결과를 불러오는 중이에요');
    const hidden = [...box.children].filter(
      (child) => child.getAttribute('aria-hidden') === 'true',
    );
    expect(hidden[1]!.className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        'grid-cols-2',
        'min-[900px]:grid-cols-4',
        'gap-4',
      ]),
    );
    for (const block of box.querySelectorAll('[data-skeleton-bar]')) {
      expect(block.className).not.toMatch(/animate/);
      expect(block.className.split(/\s+/)).toContain('bg-background-tertiary');
    }
    expect(hidden[0]!.className.split(/\s+/)).toContain('rounded-[6px]');
    expect(hidden[2]!.className.split(/\s+/)).toContain('rounded-component');
  });
});

// 공개 표면은 ui/ 에서 가져오지 못해(layers.test 칸 규칙) 원문을 Vite 의 ?raw 로 읽는다(skeleton-bar 고리 가드와 같은 꼴).
const FOLDER = import.meta.glob<string>('../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
});

describe('load-skeleton 공개 표면', () => {
  it('SkeletonBar 옛 자리는 걷혔다(막대 하나의 정본은 shared/ui/skeleton-bar — 밴드 RL1, sid:MARC-ISSUE-400)', () => {
    const surface = FOLDER['../index.ts'];
    expect(surface).toMatch(/\bLoadSkeleton\b/);
    expect(surface).not.toMatch(/export[^;]*\bSkeletonBar/);
    // 같은 폴더(ui/)의 원문은 ./ 로 잡힌다(이 시험 파일 자신은 빠진다).
    expect(Object.keys(FOLDER)).toContain('./LoadSkeleton.tsx');
    expect(Object.keys(FOLDER)).not.toContain('./SkeletonBar.ts');
  });
});
