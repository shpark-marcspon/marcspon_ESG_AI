// @vitest-environment jsdom
// 검수 이슈 표(밴드 TRW0b, 발주서 §3-10): 심각도 탭 수 = 자료 셈(유형 거르기와 상관없이) · High 탭 → High 줄만 · 유형 거르기 · 빈 꼴 ·
// 심각도 칸이 RiskBadge(data-level). 키트 Tabs 는 mouseDown 으로 누른다.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import { TR_TEXT } from '../../../entities/translation/config/text.ts';
import { SAMPLE_ISSUES } from '../../../entities/translation/model/testing.ts';
import { QaIssueTable } from './QaIssueTable.tsx';

afterEach(cleanup);

const rows = () => document.querySelectorAll('[data-issue]');
const tab = (severity: string) =>
  document.querySelector<HTMLElement>(`[data-severity="${severity}"]`)!;

describe('QaIssueTable', () => {
  it('심각도 탭 수 = 자료 셈(전체 11 · High 1 · Mid 4 · Low 6), 처음은 전체 줄', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES} />);
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      '전체 11',
      'High 1',
      'Mid 4',
      'Low 6',
    ]);
    expect(rows()).toHaveLength(11);
  });

  it('High 탭 → High 줄만, Low → Low 여섯', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES} />);
    fireEvent.mouseDown(tab('high'));
    expect(tab('high').getAttribute('aria-selected')).toBe('true');
    expect([...rows()].map((r) => r.getAttribute('data-issue'))).toEqual([
      'high',
    ]);
    fireEvent.mouseDown(tab('low'));
    expect(rows()).toHaveLength(6);
  });

  it('유형 거르기(문법) → 두 줄, 심각도 탭 수는 그대로', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES} />);
    // 키트 dropdown-menu(radix)는 키보드로 연다
    fireEvent.keyDown(
      screen.getByRole('button', { name: TR_TEXT.issues.typeFilter }),
      { key: 'Enter' },
    );
    fireEvent.click(
      screen.getByRole('menuitemradio', { name: TR_TEXT.issues.types.grammar }),
    );
    expect(rows()).toHaveLength(2);
    expect(tab('all').textContent).toBe('전체 11');
    // 겹침: 문법 + High = 0 → 빈 꼴
    fireEvent.mouseDown(tab('high'));
    expect(rows()).toHaveLength(0);
    expect(screen.getByTestId('qa-issues-empty').textContent).toBe(
      TR_TEXT.issues.empty,
    );
  });

  it('이슈가 없으면 빈 꼴 글, 탭 수는 0', () => {
    render(<QaIssueTable issues={[]} />);
    expect(screen.getByTestId('qa-issues-empty').textContent).toBe(
      '검수에서 찾은 이슈가 없어요',
    );
    expect(tab('all').textContent).toBe('전체 0');
  });

  it('심각도 칸은 RiskBadge(data-level), 유형은 한국어 이름', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES.slice(0, 2)} />);
    // data-issue 는 쪽 칸 글에 있다(밴드 TRP2 TC3). 줄은 그 위 tr.
    const first = rows()[0]!.closest('tr')!;
    expect(first.querySelector('[data-level="high"]')?.textContent).toBe(
      'High',
    );
    expect(first.textContent).toContain('숫자·단위 오류');
  });
});

// 밴드 TRP4 ②-8: 표 감싸개(qa-issues-body)에 gw-m-fade, 심각도 탭을 바꾸면 감싸개가 새 노드(다시 비침), 줄 수는 그대로.
describe('QaIssueTable 움직임(TRP4)', () => {
  it('감싸개 gw-m-fade, 탭을 바꾸면 새 노드', () => {
    render(<QaIssueTable issues={SAMPLE_ISSUES} />);
    const before = screen.getByTestId('qa-issues-body');
    expect(before.classList.contains('gw-m-fade')).toBe(true);
    expect(before.contains(document.querySelector('table'))).toBe(true);
    fireEvent.mouseDown(tab('low'));
    const after = screen.getByTestId('qa-issues-body');
    expect(after).not.toBe(before);
    expect(after.classList.contains('gw-m-fade')).toBe(true);
    expect(rows()).toHaveLength(6);
  });
});
