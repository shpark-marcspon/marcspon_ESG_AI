// @vitest-environment jsdom
// 파트 탭(밴드 TRW0b, 발주서 §3-2): 탭 넷 · ←/→ 로 옮겨 aria-selected · 파트 하나면 tablist 0·children 보임 · 탭 상태 글.
//   키트 Tabs(radix)는 click 이 아니라 mouseDown·키보드로 바뀐다.
import { useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { act } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { PartTabs } from './PartTabs.tsx';
import type { PartTab, PartTabKey } from './PartTabs.tsx';

afterEach(cleanup);

const TABS: PartTab[] = [
  { key: 'all', label: '전체', note: '2 / 3 완료' },
  { key: 'ceo', label: 'CEO 메시지', state: 'done' },
  { key: 'story', label: '스토리', state: 'failed_partial' },
  { key: 'general', label: '일반', state: 'done' },
];

function Harness({
  tabs = TABS,
  onChange = () => {},
}: {
  tabs?: PartTab[];
  onChange?(key: PartTabKey): void;
}) {
  const [value, setValue] = useState<PartTabKey>(tabs[0]!.key);
  return (
    <PartTabs
      tabs={tabs}
      value={value}
      onChange={(key) => {
        onChange(key);
        setValue(key);
      }}
      aria-label="파트"
    >
      <p data-testid="panel">{value}</p>
    </PartTabs>
  );
}

describe('PartTabs', () => {
  it('탭 넷, 처음은 [전체] 가 aria-selected', () => {
    render(<Harness />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(4);
    expect(tabs[0]!.getAttribute('aria-selected')).toBe('true');
    expect(screen.getByTestId('panel').textContent).toBe('all');
  });

  it('→ 로 옮겨 고르면 aria-selected 가 옮고 onChange(키)', async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const tabs = screen.getAllByRole('tab');
    tabs[0]!.focus();
    // radix 는 다음 틱에 초점을 옮기고 초점이 고른다(자동 활성)
    fireEvent.keyDown(tabs[0]!, { key: 'ArrowRight' });
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith('ceo'));
    expect(screen.getAllByRole('tab')[1]!.getAttribute('aria-selected')).toBe(
      'true',
    );
    fireEvent.keyDown(screen.getAllByRole('tab')[1]!, { key: 'ArrowLeft' });
    await waitFor(() => expect(onChange).toHaveBeenLastCalledWith('all'));
  });

  it('mouseDown 으로 끝나지 않은 탭도 고른다', () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    fireEvent.mouseDown(screen.getAllByRole('tab')[2]!);
    expect(onChange).toHaveBeenCalledWith('story');
    expect(screen.getByTestId('panel').textContent).toBe('story');
  });

  it('탭 상태 글: 완료·실패 · 일부 쪽, [전체] 는 note', () => {
    render(<Harness />);
    const tabs = screen.getAllByRole('tab');
    expect(tabs[0]!.textContent).toBe('전체2 / 3 완료');
    expect(tabs[1]!.querySelector('[data-state="done"]')?.textContent).toBe(
      '완료',
    );
    expect(tabs[2]!.querySelector('[data-state]')?.textContent).toBe(
      '실패 · 일부 페이지',
    );
  });

  it('파트 탭이 하나뿐이면 tablist 없이 children 만', () => {
    render(
      <Harness
        tabs={[
          { key: 'all', label: '전체' },
          { key: 'general', label: '일반', state: 'running' },
        ]}
      />,
    );
    expect(screen.queryByRole('tablist')).toBeNull();
    expect(screen.queryAllByRole('tab')).toHaveLength(0);
    expect(screen.getByTestId('panel')).toBeTruthy();
  });
});

// 밴드 TRP4 ②-4·②-5: 끝난 탭 ✓ 에 gw-m-pop · 탭 내용 감싸개 gw-m-fade, 탭을 바꾸면 감싸개가 새 노드(다시 비침)이고 초점은 탭 단추.
describe('PartTabs 움직임(TRP4)', () => {
  it('ⓐ done 탭의 ✓ svg 에 gw-m-pop', () => {
    render(<Harness />);
    const done = document.querySelector('[data-tab="ceo"] svg')!;
    expect(done.classList.contains('gw-m-pop')).toBe(true);
  });

  it('ⓑ 탭 내용 감싸개(tabpanel 의 첫 자식)에 gw-m-fade, 다른 탭을 고르면 새 노드이고 초점은 탭 단추', async () => {
    render(<Harness />);
    const wrap = () => screen.getByRole('tabpanel').firstElementChild!;
    const before = wrap();
    expect(before.classList.contains('gw-m-fade')).toBe(true);
    const all = screen.getByRole('tab', { selected: true });
    act(() => all.focus());
    fireEvent.keyDown(all, { key: 'ArrowRight' });
    await waitFor(() =>
      expect(
        screen.getByRole('tab', { selected: true }).getAttribute('data-tab'),
      ).toBe('ceo'),
    );
    expect(wrap()).not.toBe(before);
    expect(wrap().classList.contains('gw-m-fade')).toBe(true);
    expect(screen.getByTestId('panel').textContent).toBe('ceo');
    expect(document.activeElement?.getAttribute('data-tab')).toBe('ceo');
  });
});
