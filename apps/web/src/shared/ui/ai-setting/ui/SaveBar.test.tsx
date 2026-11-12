// @vitest-environment jsdom
// AI 설정 저장 막대(시안 v148 — GW3R B6·B7·A10): 옅은 주황 바탕·사이 16 · [되돌리기] outlineGrey · 글은 「고친 것 n개」 한 줄(셈 줄 0).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { SaveBar } from './SaveBar.tsx';

afterEach(cleanup);

function setup(saveOff = false) {
  const onRevert = vi.fn();
  const onSave = vi.fn();
  render(
    <SaveBar
      count="지어낸 셈"
      revert="되돌림"
      save="저장함"
      saveOff={saveOff}
      onRevert={onRevert}
      onSave={onSave}
    />,
  );
  return { onRevert, onSave, bar: screen.getByTestId('save-bar') };
}

const words = (element: Element) => element.className.split(/\s+/);

describe('SaveBar 꼴', () => {
  it('바탕 orange-subtle · 사이 16 · 글 줄 하나 · [되돌리기] 테두리 button-grey', () => {
    const { bar } = setup();
    expect(words(bar)).toEqual(
      expect.arrayContaining(['bg-support-orange-subtle', 'gap-4']),
    );
    expect(words(bar)).not.toContain('bg-background-primary');
    expect(bar.querySelectorAll('p')).toHaveLength(1);
    expect(bar.querySelector('p')!.textContent).toBe('지어낸 셈');
    const revert = screen.getByRole('button', { name: '되돌림' });
    expect(words(revert)).toContain('border-button-grey');
  });

  it('누름: [되돌리기] → onRevert, saveOff 면 [저장] aria-disabled 이고 onSave 0', () => {
    const on = setup();
    fireEvent.click(screen.getByRole('button', { name: '되돌림' }));
    expect(on.onRevert).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '저장함' }));
    expect(on.onSave).toHaveBeenCalledTimes(1);
    cleanup();
    const off = setup(true);
    const save = screen.getByRole('button', { name: '저장함' });
    expect(save.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(save);
    expect(off.onSave).not.toHaveBeenCalled();
  });
});
