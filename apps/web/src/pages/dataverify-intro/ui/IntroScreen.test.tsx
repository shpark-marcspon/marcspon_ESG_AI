// @vitest-environment jsdom
// DV-00 검증 안내 화면 시험(밴드 DV3 ① W3·W4 — 시안 v158 DV-00_r1). jsdom 은 tailwind 를 계산하지 못해 클래스·구조를 잰다(계산값은 e2e).
import { cleanup, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import { IntroScreen } from './IntroScreen.tsx';

afterEach(cleanup);

const words = DV_TEXT.intro;

function setup() {
  const onStart = vi.fn();
  render(<IntroScreen onStart={onStart} />);
  return { onStart };
}

/** 제목이 title 인 카드의 줄 묶음(dl). */
const rowsOf = (title: string) =>
  screen
    .getByRole('heading', { name: title })
    .parentElement!.querySelector('dl')!;

describe('DV-00 시안 대조 손질(밴드 DV3 ①)', () => {
  it('W3 올리는 것·받는 것: 줄 수 = 글 표 줄 수 · 이름 160 회색 바탕 500 14 · 값 400 16 · 700 0', () => {
    setup();
    for (const [title, rows] of [
      [words.give.title, words.give.rows],
      [words.get.title, words.get.rows],
    ] as const) {
      const dl = rowsOf(title);
      const lines = [...dl.children];
      expect(lines).toHaveLength(rows.length);
      lines.forEach((line, index) => {
        expect(line.className).toContain('min-h-16');
        const dt = line.querySelector('dt')!;
        const dd = line.querySelector('dd')!;
        expect(dt.textContent).toBe(rows[index]![0]);
        expect(dd.textContent).toBe(rows[index]![1]);
        expect(dt.className).toContain('w-40');
        expect(dt.className).toContain('bg-support-grey-subtle');
        expect(dt.className).toContain('text-style-pre-body-05');
        expect(dd.className).toContain('text-style-pre-body-03');
      });
      expect(dl.outerHTML).not.toContain('text-style-pre-body-04');
    }
  });

  it('W4 구분 배지 넷은 키트 sm(h-5 · 500 12) — md 꼴 0', () => {
    setup();
    const table = screen.getByRole('table', { name: words.heading });
    const badges = words.table.rows.map(([kind]) =>
      [...table.querySelectorAll('td *')].find(
        (el) => el.textContent === kind && el.children.length === 0,
      )!,
    );
    expect(badges).toHaveLength(4);
    for (const badge of badges) {
      expect(badge.className).toContain('h-5');
      expect(badge.className).toContain('text-style-pre-caption-02');
      expect(badge.className).not.toContain('h-6');
      expect(badge.className).not.toContain('text-style-pre-body-04');
    }
  });
});

describe('DV-00 열 폭 고정(밴드 DVW1 ②-5)', () => {
  /** 고정 짜임 표의 colgroup 폭(px 글, 폭 없으면 ''). */
  const colWidths = (table: Element) => {
    expect(table.className).toContain('table-fixed');
    const cols = [...table.querySelectorAll(':scope > colgroup > col')];
    expect(cols).toHaveLength(table.querySelectorAll('thead th').length);
    return cols.map((col) => (col as HTMLElement).style.width);
  };

  it('구분 표: table-fixed · 구분 120 · 의미 폭 없음 · 예시 420(1280·1440 에서 auto 와 같은 폭)', () => {
    setup();
    const table = screen.getByRole('table', { name: words.heading });
    expect(colWidths(table)).toEqual(['120px', '', '420px']);
  });
});

describe('DV-00 올리는 것은 엑셀로(밴드 DV13 — 컨설턴트 댓글 11-10, sid:MARC-ISSUE-646)', () => {
  it('화면 전체 글에 「JSON」 0 · 「엑셀」 있음', () => {
    setup();
    const text = document.body.textContent ?? '';
    expect(text).not.toMatch(/json/i);
    expect(text).toContain('엑셀');
  });
});
