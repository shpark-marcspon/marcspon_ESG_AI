// @vitest-environment jsdom
// (밴드 FS1 ③: screen-fixes.test.tsx 에서 이 화면·칸의 describe/it 을 그대로 옮겨 왔다.)
// 밴드 FW2 ⓪: FW1b 디자인 대조의 고칠 것과 sid:MARC-ISSUE-99 화면 고침. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
// 실제 크기·색·스크롤은 e2e/greenwash.spec.ts 가 잰다(jsdom 에는 CSS 가 없다).
import { cleanup, render, screen, within } from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import { IntroScreen } from './IntroScreen.tsx';

afterEach(cleanup);

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

/** PDF 를 열지 않는 openPdf(썸네일은 이 시험에서 그리지 않는다). */

describe('GW-00 소개', () => {
  it('점검 과정 목록의 이름은 제목(aria-labelledby), [시작하기]는 md', () => {
    render(<IntroScreen onStart={() => {}} />);
    const list = screen.getByRole('list', {
      name: GW_TEXT.intro.processHeading,
    });
    expect(list.getAttribute('aria-labelledby')).toBeTruthy();
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(
      screen
        .getByRole('button', { name: GW_TEXT.intro.start })
        .className.split(/\s+/),
    ).toContain('h-9');
  });

  it('시작 안내는 점검 과정 목록 아래(같은 카드, 목록 바로 뒤 — 시안 댓글, sid:MARC-ENT-603)', () => {
    render(<IntroScreen onStart={() => {}} />);
    const list = screen.getByRole('list', {
      name: GW_TEXT.intro.processHeading,
    });
    const hint = screen.getByTestId('start-hint');
    expect(hint.textContent).toBe(GW_TEXT.intro.startHint);
    expect(list.nextElementSibling).toBe(hint);
    expect(screen.getAllByText(GW_TEXT.intro.startHint)).toHaveLength(1);
  });
});
