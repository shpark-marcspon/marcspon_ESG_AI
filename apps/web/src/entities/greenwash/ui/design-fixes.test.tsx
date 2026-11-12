// @vitest-environment jsdom
// 밴드 FW1b ⓪: FW1 디자인 대조의 고칠 것(band-reports/FW1-design-review.md). 글자는 문구 표(GW_TEXT) 값으로 단언한다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { GW_TEXT } from '../config/text.ts';
import { COMPARE_KINDS, COMPARE_LOOK, CompareBadge } from './CompareBadge.tsx';
import { ExcludeReasonDialog } from './ExcludeReasonDialog.tsx';
import { ReviewChoice } from './ReviewChoice.tsx';
import { RiskBadge } from './RiskBadge.tsx';

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

describe('CompareBadge 의 해소 갈래(물음 9)', () => {
  it('해소 셋은 배지 글자가 모두 「해소」이고, 갈래 글은 배지 아래 작은 글로 따로 낸다', () => {
    const cases = [
      ['resolved_deleted', GW_TEXT.compareNote.resolved_deleted],
      ['resolved_not_flagged', GW_TEXT.compareNote.resolved_not_flagged],
      ['resolved_undetermined', null],
    ] as const;
    for (const [kind, note] of cases) {
      const { container, unmount } = render(<CompareBadge kind={kind} />);
      const badge = container.querySelector(`[data-compare="${kind}"]`)!;
      expect(badge.textContent, kind).toBe(GW_TEXT.compareBadge[kind]);
      expect(badge.textContent, kind).toBe(
        GW_TEXT.compareBadge.resolved_undetermined,
      );
      const small = container.querySelector(`[data-compare-note="${kind}"]`);
      if (note === null) expect(small, kind).toBeNull();
      else {
        expect(small?.textContent, kind).toBe(note);
        expect(small?.className).toContain('text-style-pre-caption-03');
        expect(small?.className).toContain('text-text-tertiary');
        // 갈래 글은 배지 안이 아니다
        expect(badge.contains(small)).toBe(false);
      }
      unmount();
    }
  });

  it('한 줄 글자 표(label)는 「해소 · 문장 삭제」 꼴로 따로 남는다. 해소 밖 분류는 작은 글이 없다', () => {
    expect(COMPARE_LOOK.resolved_deleted.label).toBe(
      GW_TEXT.compare.resolved_deleted,
    );
    expect(COMPARE_LOOK.resolved_deleted.label).not.toBe(
      COMPARE_LOOK.resolved_deleted.badge,
    );
    for (const kind of COMPARE_KINDS) {
      if (kind.startsWith('resolved_')) continue;
      const { container, unmount } = render(<CompareBadge kind={kind} />);
      expect(container.querySelector('[data-compare-note]'), kind).toBeNull();
      expect(container.textContent, kind).toBe(COMPARE_LOOK[kind].label);
      unmount();
    }
  });
});

describe('ReviewChoice 의 차례(물음 6)', () => {
  it('[제외][채택] 차례다(채택이 오른쪽)', () => {
    render(<ReviewChoice value="unreviewed" onChange={() => {}} />);
    const group = screen.getByRole('group', {
      name: GW_TEXT.review.groupLabel,
    });
    expect(
      within(group)
        .getAllByRole('button')
        .map((button) => button.textContent),
    ).toEqual([GW_TEXT.review.excluded, GW_TEXT.review.adopted]);
  });
});

describe('ExcludeReasonDialog 의 오류 문구', () => {
  it('사유 없이 [제외] 면 문구 표의 필수 선택 문구가 보인다', () => {
    render(
      <ExcludeReasonDialog
        open
        onOpenChange={() => {}}
        quote="「문장」"
        onSubmit={vi.fn()}
      />,
    );
    const dialog = screen.getByRole('dialog');
    fireEvent.click(
      within(dialog).getByRole('button', { name: GW_TEXT.exclude.submit }),
    );
    expect(within(dialog).getByRole('alert').textContent).toBe(
      GW_TEXT.exclude.reasonRequired,
    );
  });
});

describe('RiskBadge 의 좌우(물음 4)', () => {
  it('좌우 6(px-1.5)이고 키트 sm 의 px-1 은 남지 않는다', () => {
    render(<RiskBadge level="high" data-testid="risk" />);
    const classes = screen.getByTestId('risk').className.split(/\s+/);
    expect(classes).toContain('px-1.5');
    expect(classes).not.toContain('px-1');
    expect(classes).toContain('h-5');
  });
});
