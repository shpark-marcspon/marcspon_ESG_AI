// @vitest-environment jsdom
// PDF 쪽 칸(밴드 TRW9): 파일 → object URL → 열기 한 번 · 파일 바꿈 → 앞 URL 닫고 새로 열기 · 내려감 → 닫기 · 열기 실패 → 칸 그대로. 값은 지어낸 것이다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { PdfPageGrid } from './PdfPageGrid.tsx';

const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
beforeEach(() => {
  let n = 0;
  URL.createObjectURL = vi.fn(() => `blob:made-up-${++n}`);
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  cleanup();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

const flush = () => act(async () => {});
const FILE = new File([new Uint8Array([37, 80, 68, 70])], 'made_up_a.pdf');
const OTHER = new File([new Uint8Array([37, 80, 68, 70])], 'made_up_b.pdf');

function fakeOpen() {
  return vi.fn<OpenPdf>(async () => ({
    renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
    close() {},
  }));
}
const grid = (file: File, openPdf: OpenPdf) => (
  <PdfPageGrid
    file={file}
    openPdf={openPdf}
    pageCount={3}
    ranges={{ ceo: null, story: null, general: null }}
    active="ceo"
    onPaint={vi.fn()}
  />
);
const state = () =>
  screen.getByTestId('page-grid').getAttribute('data-pdf-state');

describe('PdfPageGrid', () => {
  it('처음 → 그 url 로 한 번 열어 ready · 칸마다 캔버스', async () => {
    const openPdf = fakeOpen();
    render(grid(FILE, openPdf));
    await flush();
    expect(openPdf).toHaveBeenCalledTimes(1);
    expect(openPdf).toHaveBeenCalledWith('blob:made-up-1');
    expect(state()).toBe('ready');
    expect(document.querySelectorAll('canvas')).toHaveLength(3);
  });

  it('다른 파일 → 앞 url 닫고 새 url 로 연다 · 내려가면 닫는다', async () => {
    const openPdf = fakeOpen();
    const view = render(grid(FILE, openPdf));
    await flush();
    view.rerender(grid(OTHER, openPdf));
    await flush();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:made-up-1');
    expect(openPdf).toHaveBeenCalledTimes(2);
    expect(openPdf).toHaveBeenLastCalledWith('blob:made-up-2');
    view.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:made-up-2');
  });

  it('다른 파일 → [더 보기]로 늘린 칸도 처음으로(url 이 열쇠)', async () => {
    const openPdf = fakeOpen();
    const many = (file: File) => (
      <PdfPageGrid
        file={file}
        openPdf={openPdf}
        pageCount={45}
        ranges={{ ceo: null, story: null, general: null }}
        active="ceo"
        onPaint={vi.fn()}
      />
    );
    const view = render(many(FILE));
    await flush();
    fireEvent.click(screen.getByRole('button', { name: /^더 보기/ }));
    expect(document.querySelectorAll('[data-page]')).toHaveLength(45);
    view.rerender(many(OTHER));
    await flush();
    expect(document.querySelectorAll('[data-page]')).toHaveLength(40);
  });

  it('파일이 바뀌면 앞 PDF 를 닫는다', async () => {
    const close = vi.fn();
    const openPdf = vi.fn<OpenPdf>(async () => ({
      renderPage: () => ({ done: Promise.resolve(), cancel() {} }),
      close,
    }));
    const view = render(grid(FILE, openPdf));
    await flush();
    view.rerender(grid(OTHER, openPdf));
    await flush();
    expect(close).toHaveBeenCalledTimes(1);
  });

  it('열기 실패 → error · 칸 그대로 · 캔버스 0', async () => {
    const openPdf = vi.fn<OpenPdf>(() =>
      Promise.reject(new Error('지어낸 열기 실패')),
    );
    render(grid(FILE, openPdf));
    await flush();
    expect(state()).toBe('error');
    expect(document.querySelectorAll('[data-page]')).toHaveLength(3);
    expect(document.querySelectorAll('canvas')).toHaveLength(0);
  });
});
