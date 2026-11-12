// @vitest-environment jsdom
// 용어집 칸(밴드 TRW0a ②, 발주서 §3-3-3): 빈 꼴(파일 칸)·있는 꼴(이름·「국문 → 영문 n개」·[바꾸기]·[양식 내려받기])·필수 표시·오류 줄·양식 받기.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { GlossaryField } from './GlossaryField.tsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const words = TR_TEXT.glossary;
const template = async () => ({
  blob: new Blob(['x']),
  fileName: 'glossary_template.xlsx',
});

describe('GlossaryField', () => {
  it('빈 꼴: 파일 칸(button), [바꾸기] 없음, [양식 내려받기] 있음', () => {
    render(
      <GlossaryField
        title={words.client.title}
        required
        onPick={vi.fn()}
        loadTemplate={template}
      />,
    );
    expect(document.querySelector('[role="button"][tabindex]')).not.toBeNull();
    expect(screen.queryByRole('button', { name: words.replace })).toBeNull();
    expect(screen.getByText(words.template)).toBeTruthy();
  });

  it('있는 꼴: 이름·「국문 → 영문 3개」·[바꾸기]·[양식 내려받기], [바꾸기] 로 고른 파일 → onPick', () => {
    const onPick = vi.fn();
    render(
      <GlossaryField
        title={words.client.title}
        required
        file={{ name: 'glossary_sample.xlsx', pairCount: 3 }}
        onPick={onPick}
        loadTemplate={template}
        testId="gl"
      />,
    );
    expect(screen.getByText('glossary_sample.xlsx')).toBeTruthy();
    expect(screen.getByText('국문 → 영문 3개')).toBeTruthy();
    expect(screen.getByRole('button', { name: words.replace })).toBeTruthy();
    const picked = new File(['x'], 'next.xlsx');
    fireEvent.change(screen.getByTestId('gl-input'), {
      target: { files: [picked] },
    });
    expect(onPick).toHaveBeenCalledWith(picked);
  });

  it('필수면 필수 표시, 아니면 「선택」', () => {
    const { container, rerender } = render(
      <GlossaryField
        title="t"
        required
        onPick={vi.fn()}
        loadTemplate={template}
      />,
    );
    expect(container.querySelector('[data-required-mark]')).not.toBeNull();
    expect(screen.queryByText(words.evaluation.optional)).toBeNull();
    rerender(
      <GlossaryField
        title="t"
        required={false}
        onPick={vi.fn()}
        loadTemplate={template}
      />,
    );
    expect(container.querySelector('[data-required-mark]')).toBeNull();
    expect(screen.getByText(words.evaluation.optional)).toBeTruthy();
  });

  it('오류 줄 셋은 받은 글 그대로 한 줄씩', () => {
    render(
      <GlossaryField
        title="t"
        required
        file={{ name: 'g.xlsx', pairCount: 2 }}
        errors={['가 오류', '나 오류', '다 오류']}
        onPick={vi.fn()}
        loadTemplate={template}
      />,
    );
    const items = document.querySelectorAll('ul[role="alert"] li');
    expect([...items].map((item) => item.textContent)).toEqual([
      '가 오류',
      '나 오류',
      '다 오류',
    ]);
  });

  it('[양식 내려받기] → loadTemplate 한 번', async () => {
    URL.createObjectURL = vi.fn(() => 'blob:fake');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const loadTemplate = vi.fn(template);
    render(
      <GlossaryField
        title="t"
        required
        onPick={vi.fn()}
        loadTemplate={loadTemplate}
        testId="gl"
      />,
    );
    await act(async () => fireEvent.click(screen.getByTestId('gl-template')));
    expect(loadTemplate).toHaveBeenCalledTimes(1);
  });

  // sid:MARC-ISSUE-307 2·3(TRW0b)
  it('[바꾸기] 로 고른 파일도 드롭존과 같은 꼴 검사 — .xlsx 가 아니면 onPick 0', () => {
    const onPick = vi.fn();
    render(
      <GlossaryField
        title={words.client.title}
        required
        file={{ name: 'glossary_sample.xlsx', pairCount: 3 }}
        onPick={onPick}
        loadTemplate={template}
        testId="gl"
      />,
    );
    fireEvent.change(screen.getByTestId('gl-input'), {
      target: { files: [new File(['x'], 'next.pdf')] },
    });
    expect(onPick).not.toHaveBeenCalled();
    const ok = new File(['x'], 'NEXT.XLSX');
    fireEvent.change(screen.getByTestId('gl-input'), {
      target: { files: [ok] },
    });
    expect(onPick).toHaveBeenCalledExactlyOnceWith(ok);
  });

  it('칸 둘의 같은 이름 단추는 칸 제목이 이름인 묶음으로 갈린다', () => {
    render(
      <>
        <GlossaryField
          title={words.evaluation.title}
          required={false}
          file={{ name: 'a.xlsx', pairCount: 1 }}
          onPick={vi.fn()}
          loadTemplate={template}
        />
        <GlossaryField
          title={words.client.title}
          required
          file={{ name: 'b.xlsx', pairCount: 2 }}
          onPick={vi.fn()}
          loadTemplate={template}
        />
      </>,
    );
    for (const title of [words.evaluation.title, words.client.title]) {
      const group = within(screen.getByRole('group', { name: title }));
      expect(
        group.getAllByRole('button', { name: words.replace }),
      ).toHaveLength(1);
      expect(
        group.getAllByRole('button', { name: words.template }),
      ).toHaveLength(1);
    }
  });

  // 밴드 TRP3 TB2(시안 TR-02 e-btn--sm e-btn--outline-grey, round 없음).
  it('[양식 내려받기]는 square sm — h-7·rounded-component·px-2, rounded-full 아님', () => {
    render(
      <GlossaryField
        title="t"
        required
        onPick={vi.fn()}
        loadTemplate={template}
        testId="gl"
      />,
    );
    const classes = screen.getByTestId('gl-template').classList;
    expect(classes.contains('h-7')).toBe(true);
    expect(classes.contains('rounded-component')).toBe(true);
    expect(classes.contains('px-2')).toBe(true);
    expect(classes.contains('rounded-full')).toBe(false);
  });
});
