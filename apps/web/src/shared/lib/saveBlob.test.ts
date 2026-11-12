// @vitest-environment jsdom
// 받은 파일 내려받기(밴드 AD4X ②): object URL 로 <a download> 를 잠깐 붙여 한 번 누르고 떼고, URL 은 타이머 뒤에 놓는다.
import { afterEach, describe, expect, it, vi } from 'vitest';

import { saveBlob } from './saveBlob.ts';

// jsdom 의 URL 에는 createObjectURL·revokeObjectURL 이 없다 — 시험 동안만 가짜를 달고 끝나면 원래대로.
const original = {
  create: URL.createObjectURL,
  revoke: URL.revokeObjectURL,
};
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

describe('saveBlob', () => {
  it('<a> 의 download·href, 누름 한 번, 뗌, revoke 는 타이머 뒤', () => {
    vi.useFakeTimers();
    const create = vi.fn(() => 'blob:fake-1');
    const revoke = vi.fn();
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
    const clicks: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicks.push(this);
      expect(document.body.contains(this)).toBe(true);
    });
    const blob = new Blob(['x']);
    saveBlob(blob, '실행기록_2026-10-22_1430.xlsx');
    expect(create).toHaveBeenCalledWith(blob);
    expect(clicks).toHaveLength(1);
    expect(clicks[0]!.download).toBe('실행기록_2026-10-22_1430.xlsx');
    expect(clicks[0]!.getAttribute('href')).toBe('blob:fake-1');
    expect(document.body.contains(clicks[0]!)).toBe(false);
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith('blob:fake-1');
  });
});
