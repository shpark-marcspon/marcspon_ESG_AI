// @vitest-environment jsdom
// 파트별 쪽 범위 칸(밴드 TRW0a ②, 발주서 §3-3-2): 알약 radiogroup·방향키, 글자 → onText, 오류 → aria-invalid + 글,
// CEO 한도(6쪽 고정) 오류 글, 글자 칸 셋뿐(한도 칸 없음), 겹침 줄, 「번역할 쪽」 합.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import type {
  PartKey,
  Range,
  RangeError,
} from '../../../entities/translation/model/index.ts';
import { PartRangeFields } from './PartRangeFields.tsx';
import type { PartRangeFieldsProps } from './PartRangeFields.tsx';

afterEach(cleanup);

const RANGES: Record<PartKey, Range | null> = {
  ceo: { from: 1, to: 3 },
  story: { from: 4, to: 41 },
  general: null,
};
const TEXTS: Record<PartKey, string> = {
  ceo: '1~3',
  story: '4~41',
  general: '',
};

function draw(props: Partial<PartRangeFieldsProps> = {}) {
  const calls = {
    onText: vi.fn(),
    onActive: vi.fn(),
  };
  render(
    <PartRangeFields
      pageCount={64}
      ranges={RANGES}
      texts={TEXTS}
      errors={{}}
      active="story"
      {...calls}
      {...props}
    />,
  );
  return calls;
}
const field = (part: PartKey) =>
  document.querySelector<HTMLInputElement>(`[data-part-field="${part}"]`)!;
const below = (part: PartKey) => {
  const id = field(part).getAttribute('aria-describedby');
  return id ? document.getElementById(id) : null;
};

describe('PartRangeFields', () => {
  it('알약 셋은 radiogroup, 고른 것만 aria-checked·Tab, ←→ 로 고른다(끝에서 돈다)', () => {
    const { onActive } = draw();
    const group = screen.getByRole('radiogroup', {
      name: TR_TEXT.range.groupLabel,
    });
    const radios = screen.getAllByRole('radio');
    expect(group.contains(radios[0]!)).toBe(true);
    expect(radios.map((radio) => radio.getAttribute('aria-checked'))).toEqual([
      'false',
      'true',
      'false',
    ]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([-1, 0, -1]);
    expect(radios[0]!.textContent).toContain('총 3페이지');
    fireEvent.keyDown(radios[1]!, { key: 'ArrowRight' });
    expect(onActive).toHaveBeenLastCalledWith('general');
    fireEvent.keyDown(radios[1]!, { key: 'ArrowLeft' });
    expect(onActive).toHaveBeenLastCalledWith('ceo');
    fireEvent.click(radios[2]!);
    expect(onActive).toHaveBeenLastCalledWith('general');
  });

  it('글자 → onText(파트, 글)', () => {
    const { onText } = draw();
    fireEvent.change(field('general'), { target: { value: '42~64' } });
    expect(onText).toHaveBeenCalledWith('general', '42~64');
  });

  it('오류 → aria-invalid + 갈래마다의 글', () => {
    const errors: Partial<Record<PartKey, RangeError>> = {
      general: { code: 'over_last', page: 150, last: 64 },
      story: { code: 'comma' },
      ceo: { code: 'order', from: 3, to: 1 },
    };
    draw({ errors, texts: { ceo: '3~1', story: '4~5, 9', general: '150' } });
    expect(field('general').getAttribute('aria-invalid')).toBe('true');
    expect(below('general')?.textContent).toBe(
      TR_TEXT.range.errors.overLast(150, 64),
    );
    expect(below('story')?.textContent).toBe(TR_TEXT.range.errors.comma);
    expect(field('ceo').getAttribute('aria-invalid')).toBe('true');
    expect(below('ceo')?.textContent).toBe(
      '3~1페이지는 앞 페이지 번호가 뒤 페이지보다 커요',
    );
    expect(field('general').getAttribute('aria-describedby')).toBe(
      below('general')?.id,
    );
  });

  // 밴드 TRW5(sid:MARC-ISSUE-398 ① — 시안 TR-02a): 오류일 때만 help 아래 고쳐 넣는 꼴 한 줄, 평시 help 는 그대로.
  it('오류 칸이 있으면 help 아래 「「1-3」은 「1~3」으로…」 줄, 평시(CEO 한도 오류 포함 0)엔 없음', () => {
    const errorHelp = '「1-3」은 「1~3」으로, 페이지 하나는 「5」';
    expect(TR_TEXT.range.errorHelp).toBe(errorHelp);
    draw();
    expect(screen.queryByTestId('range-help-error')).toBeNull();
    expect(screen.queryByText(errorHelp)).toBeNull();
    expect(screen.getByText(TR_TEXT.range.help)).toBeTruthy();
    cleanup();
    draw({
      errors: { story: { code: 'not_number', token: '4-41' } },
      texts: { ...TEXTS, story: '4-41' },
    });
    expect(screen.getByTestId('range-help-error').textContent).toBe(errorHelp);
    expect(screen.getByText(TR_TEXT.range.help)).toBeTruthy();
    cleanup();
    // CEO 한도 오류(errors 에 없고 칸에서 셈)도 오류 꼴이다.
    draw({
      ranges: { ...RANGES, ceo: { from: 1, to: 8 } },
      texts: { ...TEXTS, ceo: '1~8' },
    });
    expect(screen.getByTestId('range-help-error').textContent).toBe(errorHelp);
  });

  it('0·숫자 아님의 글', () => {
    draw({
      errors: {
        ceo: { code: 'zero' },
        story: { code: 'not_number', token: 'abc' },
      },
      texts: { ceo: '0', story: 'abc', general: '' },
    });
    expect(below('ceo')?.textContent).toBe(TR_TEXT.range.errors.zero);
    expect(below('story')?.textContent).toBe(
      '「abc」는 읽을 수 없어요. 숫자와 ~ 로 넣어 주세요',
    );
    expect(field('general').hasAttribute('aria-invalid')).toBe(false);
  });

  it('CEO 8쪽이면 CEO 칸에 한도 오류 글(6쪽 고정), 6쪽이면 오류 없음', () => {
    draw({
      ranges: { ...RANGES, ceo: { from: 1, to: 8 } },
      texts: { ...TEXTS, ceo: '1~8' },
    });
    expect(field('ceo').getAttribute('aria-invalid')).toBe('true');
    expect(below('ceo')?.textContent).toBe(
      TR_TEXT.range.errors.ceoOverLimit(6),
    );
    // 밴드 TRW4(마크스폰 댓글 — 한도는 페이지 수): 입력 오류와 칸 아래 안내 글 둘 다 「최대 6페이지」.
    expect(below('ceo')?.textContent).toContain(
      'CEO 메시지는 최대 6페이지예요.',
    );
    expect(screen.getByText(/CEO 메시지는 최대 6페이지$/)).toBeTruthy();
    // sid:MARC-ISSUE-307 5(TRW0b): 제목의 「6쪽이면 오류 없음」을 몸에서도 잰다.
    cleanup();
    draw({
      ranges: {
        ...RANGES,
        ceo: { from: 1, to: 6 },
        story: { from: 7, to: 41 },
      },
      texts: { ...TEXTS, ceo: '1~6', story: '7~41' },
    });
    expect(field('ceo').hasAttribute('aria-invalid')).toBe(false);
    expect(below('ceo')?.textContent).toBe(TR_TEXT.range.pageCount(6));
  });

  it('글자 칸은 파트마다 하나씩 셋뿐이다(CEO 한도 칸 없음 — 6쪽 고정)', () => {
    draw();
    expect(document.querySelectorAll('input')).toHaveLength(3);
    expect(document.querySelectorAll('[data-part-field]')).toHaveLength(3);
  });

  it('칸 아래: 쪽 수, 빈 칸 안내, 겹침 줄', () => {
    draw({
      ranges: {
        ceo: { from: 3, to: 8 },
        story: { from: 7, to: 41 },
        general: null,
      },
    });
    expect(below('story')?.textContent).toBe(
      '총 35페이지 · 7~8페이지는 CEO 메시지와 겹침',
    );
    expect(below('ceo')?.textContent).toBe(
      '총 6페이지 · 7~8페이지는 스토리와 겹침',
    );
    expect(below('general')?.textContent).toBe(TR_TEXT.range.empty);
    expect(screen.getByText(TR_TEXT.range.overlapNote)).toBeTruthy();
  });

  it('셋이 겹치면 겹친 쪽 하나 + 이름 묶음(그린워싱 꼴): 「…쪽은 CEO 메시지와 일반과 겹침」', () => {
    draw({
      ranges: {
        ceo: { from: 1, to: 5 },
        story: { from: 4, to: 41 },
        general: { from: 40, to: 64 },
      },
      texts: { ceo: '1~5', story: '4~41', general: '40~64' },
    });
    expect(below('story')?.textContent).toBe(
      '총 38페이지 · 4~5, 40~41페이지는 CEO 메시지와 일반과 겹침',
    );
    expect(below('general')?.textContent).toBe(
      '총 25페이지 · 40~41페이지는 스토리와 겹침',
    );
  });

  it('「번역할 쪽」 줄 = 파트별 쪽 수의 합, 쪽을 넣은 파트가 없으면 없음', () => {
    draw();
    expect(screen.getByTestId('range-total').textContent).toBe(
      '번역할 페이지 41개 / 총 64페이지 · 파트 2개라 번역을 2번 해요(CEO 메시지 · 스토리).',
    );
    cleanup();
    draw({
      ranges: { ceo: null, story: null, general: null },
      texts: { ceo: '', story: '', general: '' },
    });
    expect(screen.queryByTestId('range-total')).toBeNull();
  });
});

// [TRW1a ② 감독 판단 1] 쪽 수를 모를 때(docx·txt — pageCount null).
describe('PartRangeFields · pageCount null', () => {
  it('합 줄에 「/ n쪽」 없음, 칸 아래 [PAGE n] 기준 글, 쪽 수 있으면 그 글 없음', () => {
    draw({ pageCount: null });
    expect(screen.getByTestId('range-total').textContent).toBe(
      '번역할 페이지 41개 · 파트 2개라 번역을 2번 해요(CEO 메시지 · 스토리).',
    );
    expect(screen.getByTestId('range-basis').textContent).toBe(
      TR_TEXT.range.pageBasis,
    );
    expect(screen.getByTestId('range-total').textContent).not.toContain('/');
    cleanup();
    draw();
    expect(screen.queryByTestId('range-basis')).toBeNull();
  });

  it('글자 칸 셋은 그대로 쓰고 쪽 수를 보인다', () => {
    draw({ pageCount: null });
    expect(document.querySelectorAll('[data-part-field]').length).toBe(3);
    expect(below('story')?.textContent).toBe('총 38페이지');
  });
});

// 밴드 TRP3 ② TC7(디자인 6c 재대조): 칩 안 사이 8 — 단추 gap-2, 점·쪽 수의 mr-1·ml-1 없음.
describe('PartRangeFields 칩 · TRP3 ②', () => {
  it('칩 단추 gap-2(기본 gap-0.5 아님) · 점에 mr-1 · 쪽 수에 ml-1 없음', () => {
    draw();
    for (const part of ['ceo', 'story', 'general']) {
      const pill = document.querySelector(`[data-part-key="${part}"]`)!;
      const classes = pill.className.split(/\s+/);
      expect(classes, part).toContain('gap-2');
      expect(classes, part).not.toContain('gap-0.5');
      const [dot, count] = [pill.firstElementChild!, pill.lastElementChild!];
      expect(dot.className.split(/\s+/), part).not.toContain('mr-1');
      expect(count.className.split(/\s+/), part).not.toContain('ml-1');
    }
  });
});
