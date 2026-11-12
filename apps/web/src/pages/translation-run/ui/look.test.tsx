// @vitest-environment jsdom
// 결과 표 넷의 꼴(밴드 TRP2 TC3·TC2): shared DataTable(머리 #FAFBFB·몸 56) · 수 열 오른쪽 · 긴 글 칸 위아래 12 + 줄바꿈 ·
// 확인할 쪽·단계 줄 값은 배지. jsdom 은 tailwind 를 계산하지 못해 클래스로 단언한다(계산 값은 e2e).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import {
  SAMPLE_ISSUES,
  SAMPLE_MISSES,
} from '../../../entities/translation/model/testing.ts';
import { AllSummary } from './AllSummary.tsx';
import { GlossaryMissTable } from './GlossaryMissTable.tsx';
import { PagesToCheck, StepLine } from './PagesToCheck.tsx';
import { PartResultHeader } from './PartResultHeader.tsx';
import { QaIssueTable } from './QaIssueTable.tsx';

afterEach(cleanup);

const classesOf = (element: Element) => element.className.split(/\s+/);
function hasClasses(element: Element, ...names: string[]) {
  for (const name of names) expect(classesOf(element)).toContain(name);
}
/** 열 이름 → 그 열의 첫 줄 칸. */
function cellUnder(table: HTMLElement, header: string) {
  const heads = [...table.querySelectorAll('th')];
  const index = heads.findIndex((head) => head.textContent === header);
  expect(index).toBeGreaterThanOrEqual(0);
  return table.querySelectorAll('tbody tr')[0]!.querySelectorAll('td')[index]!;
}

describe('결과 표(DataTable)', () => {
  it('검수 이슈: 머리 칸 DataTable 꼴, 쪽 열 오른쪽, 고칠 부분·제안·까닭 칸 py-3 + 줄바꿈', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES.slice(0, 2)} />);
    const table = screen.getByRole('table', { name: TR_TEXT.issues.title });
    for (const head of table.querySelectorAll('th'))
      hasClasses(head, 'h-10', 'bg-support-grey-subtle', 'border-y');
    hasClasses(cellUnder(table, '페이지'), 'text-right', 'h-14');
    for (const header of ['고칠 부분', '제안', '까닭'])
      hasClasses(
        cellUnder(table, header).firstElementChild!,
        'py-3',
        'whitespace-normal',
      );
  });

  it('용어집 미반영: 쪽·등장 열 오른쪽', () => {
    render(<GlossaryMissTable rows={SAMPLE_MISSES} />);
    const table = screen.getByRole('table');
    hasClasses(cellUnder(table, '페이지'), 'text-right');
    hasClasses(cellUnder(table, '원문 등장'), 'text-right');
  });

  it('확인할 쪽: 번역·검수 값은 배지(실패 orange · 검수함 success), 까닭 칸 py-3', () => {
    render(
      <PagesToCheck
        rows={[
          {
            pages: '27',
            translate: { text: '실패', look: 'orange' },
            review: { text: '검수함', look: 'success' },
            reason: 'AI 호출이 실패했어요.',
          },
        ]}
      />,
    );
    const table = screen.getByRole('table');
    hasClasses(screen.getByText('실패'), 'bg-support-orange-subtle', 'h-5');
    hasClasses(screen.getByText('검수함'), 'bg-support-success-subtle');
    hasClasses(cellUnder(table, '까닭').firstElementChild!, 'py-3');
  });

  it('단계 줄: 값마다 배지(멈춤 error · 돌리지 않음 grey)', () => {
    render(
      <StepLine
        steps={[
          { name: '번역 검수', text: '30페이지에서 멈춤', look: 'error' },
          { name: '자동 수정', text: '돌리지 않음', look: 'grey' },
        ]}
      />,
    );
    hasClasses(
      screen.getByText('30페이지에서 멈춤'),
      'bg-support-error-subtle',
    );
    hasClasses(screen.getByText('돌리지 않음'), 'bg-background-tertiary');
  });
});

// [TRP2 ②] 카드 넷 TE11·제목 TC19 · 결과 머리 TC20 · 내려받기 카드 TC21 · 남은 파트 줄 TC23 · 단계 줄 TC25.
describe('TRP2 ② 결과 카드 꼴', () => {
  const file = async () => ({ blob: new Blob(['x']), fileName: 'f.docx' });

  it('TE11·TC19 검수 이슈·용어집 미반영·확인할 쪽은 흰 카드(section) + heading-02 · 기준 글 caption-03 · 멈춤 기준 글', () => {
    render(
      <>
        <QaIssueTable
          issues={SAMPLE_ISSUES}
          basis="4~29페이지 · 7건 · 자동 수정 전 글 기준"
        />
        <GlossaryMissTable rows={SAMPLE_MISSES} />
        <PagesToCheck
          rows={[
            {
              pages: '30',
              translate: { text: '완료', look: 'success' },
              review: { text: '30페이지에서 멈춤', look: 'error' },
              reason: 'r',
            },
          ]}
        />
      </>,
    );
    for (const id of ['qa-issues', 'glossary-miss', 'pages-to-check']) {
      const card = screen.getByTestId(id);
      expect(card.tagName).toBe('SECTION');
      hasClasses(card, 'rounded-dialog', 'bg-background-primary', 'p-8');
      hasClasses(card.querySelector('h3')!, 'text-style-pre-heading-02');
    }
    hasClasses(
      screen.getByText('4~29페이지 · 7건 · 자동 수정 전 글 기준'),
      'text-style-pre-caption-03',
    );
  });

  it('TC25 「단계」 caption-03 tertiary', () => {
    render(
      <StepLine steps={[{ name: '번역', text: '완료', look: 'success' }]} />,
    );
    hasClasses(
      screen.getByText(TR_TEXT.result.stepsLabel),
      'text-style-pre-caption-03',
      'text-text-tertiary',
    );
  });

  // [TRW14 ①] TC21 내려받기 카드는 받기 모달로 옮겨갔다(TR-04a r2): 머리 heading-02 · 이름 body-05 secondary · 설명 body-06 tertiary · 각주 하나.
  it('TC20 제목 body-01 · 회차 회색 배지 · meta caption-03 · [내려받기] 오른쪽 · 받기 모달 머리 heading-02, 이름 body-05, 설명 body-06 tertiary', () => {
    render(
      <PartResultHeader
        part="story"
        range={{ from: 4, to: 41 }}
        state="done"
        round={2}
        style="B"
        glossaryCount={164}
        started="14:10"
        files={{ bilingual: file }}
      />,
    );
    hasClasses(
      screen.getByRole('heading', { name: /스토리 4~41페이지/ }),
      'text-style-pre-body-01',
      'text-text-primary',
    );
    hasClasses(screen.getByText('회차 2'), 'bg-background-tertiary');
    const opener = screen.getByTestId('part-downloads');
    hasClasses(opener.closest('div')!, 'ml-auto');
    fireEvent.click(opener);
    const dialog = screen.getByTestId('part-download-dialog');
    // Word 안내 글은 모달 각주 하나뿐(결과 아래에는 없음 — 감독 허락 10-25).
    expect(dialog.textContent).toContain(TR_TEXT.result.wordNote);
    expect(screen.getAllByText(TR_TEXT.result.wordNote)).toHaveLength(1);
    hasClasses(
      screen.getByRole('heading', { name: TR_TEXT.result.downloadsTitle }),
      'text-style-pre-heading-02',
    );
    const group = dialog.querySelector('[data-file="bilingual"]')!;
    hasClasses(
      screen.getByText(TR_TEXT.result.files.bilingual, { selector: 'p' }),
      'text-style-pre-body-05',
      'text-text-secondary',
    );
    hasClasses(
      screen.getByText(TR_TEXT.result.fileNotes.bilingual),
      'text-style-pre-body-06',
      'text-text-tertiary',
    );
    hasClasses(
      group.querySelector('button[data-testid$="-file-bilingual"]')!,
      'h-16',
      'border-button-grey',
      'rounded-component',
      'text-style-pre-body-02',
    );
  });

  it('TC23 남은 파트 줄은 기본 톤 PageInfo · TE11 파트별 표는 흰 카드 + heading-02', () => {
    render(
      <AllSummary
        stats={[]}
        rows={[]}
        remainingLine="3파트 중 1파트 완료"
        onOpenPart={() => {}}
      />,
    );
    expect(screen.getByTestId('remaining-line').getAttribute('data-tone')).toBe(
      'default',
    );
    const title = screen.getByRole('heading', { name: TR_TEXT.all.tableTitle });
    hasClasses(title, 'text-style-pre-heading-02');
    hasClasses(title.closest('section')!, 'rounded-dialog', 'p-8');
  });
});

// 밴드 TRP3 ② — 디자인 6c 재대조(band-reports/TRP2-PD1-design-review.md 감독 답): TC23 · N1 · N3.
describe('결과 화면 꼴 · TRP3 ②', () => {
  const lacks = (element: Element, name: string) =>
    expect(classesOf(element)).not.toContain(name);

  it('TC23 남은 파트 줄은 흰 바탕(bg-background-primary, 회색 bg-background-secondary 아님) · 톤은 기본 그대로', () => {
    render(
      <AllSummary
        stats={[]}
        rows={[]}
        remainingLine="3파트 중 1파트 완료"
        onOpenPart={() => {}}
      />,
    );
    const line = screen.getByTestId('remaining-line');
    hasClasses(line, 'bg-background-primary');
    lacks(line, 'bg-background-secondary');
    expect(line.getAttribute('data-tone')).toBe('default');
  });

  it('N1 검수 이슈 머리: 제목·기준 글과 유형 거르기·심각도 탭이 한 줄(justify-between) 안', () => {
    render(
      <QaIssueTable issues={SAMPLE_ISSUES} basis="자동 수정 전 글 기준" />,
    );
    const head = screen.getByTestId('qa-issues-head');
    hasClasses(head, 'flex', 'items-center', 'justify-between');
    expect(head.querySelector('h3')!.textContent).toBe(TR_TEXT.issues.title);
    expect(head.contains(screen.getByText('자동 수정 전 글 기준'))).toBe(true);
    expect(
      head.contains(
        screen.getByRole('tablist', {
          name: TR_TEXT.issues.severityLabel,
        }),
      ),
    ).toBe(true);
    expect(
      head.querySelector(`[aria-label="${TR_TEXT.issues.typeFilter}"]`),
    ).not.toBeNull();
  });

  it('N1 용어집 미반영·확인할 쪽 머리: 제목 왼쪽 · 꼬리 글 오른쪽 한 줄(justify-between)', () => {
    render(
      <>
        <GlossaryMissTable rows={SAMPLE_MISSES} />
        <PagesToCheck
          rows={[
            {
              pages: '30',
              translate: { text: '완료', look: 'success' },
              review: { text: '30페이지에서 멈춤', look: 'error' },
              reason: 'r',
            },
          ]}
        />
      </>,
    );
    for (const [id, words] of [
      ['glossary-miss-head', TR_TEXT.glossaryMiss],
      ['pages-to-check-head', TR_TEXT.pagesToCheck],
    ] as const) {
      const head = screen.getByTestId(id);
      hasClasses(head, 'flex', 'items-center', 'justify-between');
      lacks(head, 'flex-col');
      expect(head.children[0]!.tagName).toBe('H3');
      expect(head.children[1]!.textContent).toBe(words.basis);
    }
  });

  it('N3 단계 줄: 단계 이름 body-03(400 16) · 세로 가운데(items-center)', () => {
    render(
      <StepLine steps={[{ name: '번역', text: '완료', look: 'success' }]} />,
    );
    const line = screen.getByTestId('step-line');
    hasClasses(line, 'text-style-pre-body-03', 'items-center');
    lacks(line, 'text-style-pre-body-06');
  });
});
