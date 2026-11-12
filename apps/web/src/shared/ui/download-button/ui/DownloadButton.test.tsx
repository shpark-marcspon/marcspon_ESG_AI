// @vitest-environment jsdom
// 내려받기 단추(밴드 TRW0a ① — 그린워싱 엑셀 단추에서 shared 로 올림): 누르면 load 한 번, 받은 Blob 을 받은 이름으로 내려받게 한다
// (shared/lib/saveBlob.ts). 꺼진 꼴의 누름·받는 중 두 번째 누름은 load 를 부르지 않는다. 실패면 단추 옆 글, 다시 누르면 지운다.
// [PD1] variant·shape·size 는 공용 Button 에 그대로 간다 — 안 주면 지금 꼴(outlineGrey·round·md).
import { cn } from '@marcspon/ui/lib/utils';
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { buttonVariants } from '../../button/index.ts';
import { DownloadButton } from './DownloadButton.tsx';

// jsdom 의 URL 에는 createObjectURL·revokeObjectURL 이 없다 — 시험 동안만 가짜를 달고 끝나면 원래대로(saveBlob.test.ts 꼴).
const original = {
  create: URL.createObjectURL,
  revoke: URL.revokeObjectURL,
};
let names: string[] = [];
beforeEach(() => {
  names = [];
  URL.createObjectURL = vi.fn(() => 'blob:fake-1');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    names.push(this.download);
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

const FILE = { blob: new Blob(['x']), fileName: 'result_sample.docx' };

/** 끝나지 않은 약속과 그것을 끝낼 손잡이. */
function pending() {
  let finish!: (value: typeof FILE) => void;
  let fail!: (error: Error) => void;
  const promise = new Promise<typeof FILE>((resolve, reject) => {
    finish = resolve;
    fail = reject;
  });
  return { promise, finish, fail };
}

const press = () => fireEvent.click(screen.getByTestId('dl'));

describe('DownloadButton', () => {
  it('누르면 load 한 번, 받은 이름으로 내려받는다', async () => {
    const load = vi.fn(async () => FILE);
    render(
      <DownloadButton label="받기" failedText="실패" load={load} testId="dl" />,
    );
    await act(async () => press());
    expect(load).toHaveBeenCalledTimes(1);
    expect(names).toEqual(['result_sample.docx']);
  });

  it('disabled 면 눌러도 load 0, aria-disabled', async () => {
    const load = vi.fn(async () => FILE);
    render(
      <DownloadButton
        label="받기"
        failedText="실패"
        load={load}
        disabled
        testId="dl"
      />,
    );
    await act(async () => press());
    expect(load).not.toHaveBeenCalled();
    expect(names).toEqual([]);
    expect(screen.getByTestId('dl').getAttribute('aria-disabled')).toBe('true');
  });

  it('받는 중 두 번 눌러도 load 한 번', async () => {
    const wait = pending();
    const load = vi.fn(() => wait.promise);
    render(
      <DownloadButton label="받기" failedText="실패" load={load} testId="dl" />,
    );
    act(() => {
      press();
      press();
    });
    press();
    expect(load).toHaveBeenCalledTimes(1);
    await act(async () => wait.finish(FILE));
    expect(names).toEqual(['result_sample.docx']);
  });

  it('실패면 단추 옆 글, 다시 누르면 지우고 다시 받는다', async () => {
    const first = pending();
    const second = pending();
    const load = vi
      .fn<() => Promise<typeof FILE>>()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    render(
      <DownloadButton
        label="받기"
        failedText="받지 못함"
        load={load}
        testId="dl"
      />,
    );
    const error = () => screen.getByTestId('dl-error');
    act(() => press());
    await act(async () => first.fail(new Error('x')));
    expect(error().textContent).toBe('받지 못함');
    act(() => press());
    expect(error().textContent).toBe('');
    await act(async () => second.finish(FILE));
    expect(load).toHaveBeenCalledTimes(2);
    expect(names).toEqual(['result_sample.docx']);
  });

  // [TRW1a H4] 받는 동안 글 · 화면이 이미 글을 보인 끝(handled).
  it('busyLabel 이 있으면 받는 동안 그 글, 끝나면 label 로 돌아온다', async () => {
    const wait = pending();
    render(
      <DownloadButton
        label="받기"
        busyLabel="받는 중…"
        failedText="실패"
        load={() => wait.promise}
        testId="dl"
      />,
    );
    expect(screen.getByTestId('dl').textContent).toBe('받기');
    act(() => press());
    expect(screen.getByTestId('dl').textContent).toBe('받는 중…');
    await act(async () => wait.finish(FILE));
    expect(screen.getByTestId('dl').textContent).toBe('받기');
  });

  it('busyLabel 이 없으면 받는 동안에도 label 그대로', async () => {
    const wait = pending();
    render(
      <DownloadButton
        label="받기"
        failedText="실패"
        load={() => wait.promise}
        testId="dl"
      />,
    );
    act(() => press());
    expect(screen.getByTestId('dl').textContent).toBe('받기');
    await act(async () => wait.finish(FILE));
  });

  it('load 가 handled 로 끝나면 내려받지 않고 실패 글도 0', async () => {
    const load = vi.fn(async () => ({ kind: 'handled' as const }));
    render(
      <DownloadButton label="받기" failedText="실패" load={load} testId="dl" />,
    );
    await act(async () => press());
    expect(load).toHaveBeenCalledTimes(1);
    expect(names).toEqual([]);
    expect(screen.getByTestId('dl-error').textContent).toBe('');
  });

  it('load 가 거절되면 실패 글(handled 갈래와 가름)', async () => {
    const load = vi.fn(async (): Promise<typeof FILE> => {
      throw new Error('x');
    });
    render(
      <DownloadButton label="받기" failedText="실패" load={load} testId="dl" />,
    );
    await act(async () => press());
    expect(names).toEqual([]);
    expect(screen.getByTestId('dl-error').textContent).toBe('실패');
  });

  it('variant·shape·size 를 안 주면 지금 꼴 outlineGrey·round·md', () => {
    render(
      <DownloadButton
        label="받기"
        failedText="실패"
        load={async () => FILE}
        testId="dl"
      />,
    );
    const button = screen.getByTestId('dl');
    expect(button.className).toBe(
      cn(
        buttonVariants({ variant: 'outlineGrey', shape: 'round', size: 'md' }),
      ),
    );
    expect(button.classList).toContain('border-button-grey');
    expect(button.classList).toContain('rounded-full');
    expect(button.classList).toContain('h-9');
  });

  it('variant="solidBlack" size="sm" shape="square" 를 주면 그 꼴', () => {
    render(
      <DownloadButton
        label="받기"
        failedText="실패"
        load={async () => FILE}
        testId="dl"
        variant="solidBlack"
        size="sm"
        shape="square"
      />,
    );
    const button = screen.getByTestId('dl');
    expect(button.className).toBe(
      cn(
        buttonVariants({ variant: 'solidBlack', shape: 'square', size: 'sm' }),
      ),
    );
    expect(button.classList).toContain('bg-button-black');
    expect(button.classList).toContain('rounded-component');
    expect(button.classList).toContain('h-7');
    expect(button.classList).not.toContain('border-button-grey');
  });
});
