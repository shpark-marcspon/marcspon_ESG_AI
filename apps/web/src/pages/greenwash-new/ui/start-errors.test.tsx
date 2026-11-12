// @vitest-environment jsdom
// 밴드 FW2 ① 의 화면 쪽(sid:MARC-ISSUE-99 1·3): 실행 시작·[다시 실행]이 거절되면 role="alert" 안내, 시작 시각은 ISO 를 꾸며 보인다,
// 쪽 수를 아직 모르면 「문서에서」. 글자는 문구 표(GW_TEXT) 값으로 단언한다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { StoreError } from '../../../entities/greenwash/api/index.ts';
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import {
  MOCK_FILES,
  createMockStore,
} from '../../../entities/greenwash/api/mock/index.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { NewCheckScreen } from './NewCheckScreen.tsx';

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

const words = GW_TEXT.newCheck;

/** 목 저장소가 받는 파일 이름(쪽 수·글자 층이 정해진 것). */
const MOCK_PDF = Object.keys(MOCK_FILES).find(
  (name) => MOCK_FILES[name]!.hasText,
)!;

const neverOpen: OpenPdf = () => new Promise(() => {});

function store(overrides: Partial<GreenwashStore> = {}): GreenwashStore {
  const unused = () =>
    vi.fn(async () => {
      throw new StoreError('rejected', '쓰지 않음');
    });
  return {
    createDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      pageCount: 60,
      hasText: true,
    })),
    createRun: vi.fn(async () => {
      throw new StoreError('rejected', '서버 오류');
    }),
    getRun: unused(),
    subscribeRun: vi.fn(() => () => {}),
    rerun: vi.fn(async () => {
      throw new StoreError('rejected', '서버 오류');
    }),
    listDocuments: vi.fn(async () => []),
    listDefaultTerms: vi.fn(async () => []),
    getDocument: vi.fn(async () => ({
      documentId: 'doc-1',
      fileName: 'a.pdf',
      pageCount: 88,
    })),
    listCheckRows: unused(),
    getResult: unused(),
    getReview: unused(),
    putReview: unused(),
    rejudge: unused(),
    openDocumentPdf: vi.fn(async () => null),
    getReport: vi.fn(async () => {
      throw new Error('쓰지 않음');
    }),
    ...overrides,
  };
}

describe('GW-02 시작 거절', () => {
  it('createRun 이 거절되면 GW-03 으로 가지 않고 role="alert" 안내', async () => {
    const onStarted = vi.fn();
    const fake = store();
    render(
      <NewCheckScreen
        store={fake}
        openPdf={neverOpen}
        onCancel={() => {}}
        onStarted={onStarted}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], 'a.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta');
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    fireEvent.change(ceo, { target: { value: '2' } });
    fireEvent.blur(ceo);
    expect(screen.queryByTestId('start-error')).toBeNull();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    expect(fake.createRun).toHaveBeenCalledTimes(1);
    expect(onStarted).not.toHaveBeenCalled();
    const alert = screen.getByTestId('start-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toContain(words.startRejected);
  });
});

describe('GW-02 실행 만들기 끊김(밴드 GR1, sid:MARC-ISSUE-225)', () => {
  it('createRun 이 unreachable 이면 e9 글 + [목록으로], [점검 시작]은 켜진 채 — 다시 누르면 같은 열쇠로 보내 목이 같은 실행을 돌려준다(실행 하나)', async () => {
    // 목 저장소: 첫 부름은 실행을 만든 뒤 답이 끊긴 꼴(서버는 만들었다), 둘째부터는 그대로
    const mock = createMockStore();
    const made: string[] = [];
    const createRun = vi.fn<GreenwashStore['createRun']>(
      async (documentId, request, key) => {
        const { runId } = await mock.store.createRun(documentId, request, key);
        made.push(runId);
        if (made.length === 1)
          throw new StoreError('unreachable', '지어낸 끊김');
        return { runId };
      },
    );
    const onCancel = vi.fn();
    const onStarted = vi.fn();
    render(
      <NewCheckScreen
        store={{ ...mock.store, createRun }}
        openPdf={neverOpen}
        onCancel={onCancel}
        onStarted={onStarted}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], MOCK_PDF, {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta');
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    fireEvent.change(ceo, { target: { value: '2' } });
    fireEvent.blur(ceo);
    const start = screen.getByRole('button', { name: words.start });
    await act(async () => {
      fireEvent.click(start);
    });
    expect(createRun).toHaveBeenCalledTimes(1);
    const alert = screen.getByTestId('start-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toBe(GW_TEXT.runUnreachable.start);
    expect(alert.textContent).not.toContain(words.startRejected);
    expect(start.hasAttribute('disabled')).toBe(false);
    expect(onStarted).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: words.cancel })).toBeNull();
    await act(async () => {
      fireEvent.click(start);
    });
    expect(createRun).toHaveBeenCalledTimes(2);
    const [first, second] = createRun.mock.calls;
    expect(second![2]).toBe(first![2]);
    expect(made).toEqual([made[0], made[0]]);
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(onStarted).toHaveBeenCalledWith(made[0]);
  });

  it('끊김 뒤 [목록으로]는 onCancel(열쇠는 화면과 같이 버려진다)', async () => {
    const onCancel = vi.fn();
    const fake = store({
      createRun: vi.fn(async () => {
        throw new StoreError('unreachable', '지어낸 끊김');
      }),
    });
    render(
      <NewCheckScreen
        store={fake}
        openPdf={neverOpen}
        onCancel={onCancel}
        onStarted={() => {}}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], 'a.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta');
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    fireEvent.change(ceo, { target: { value: '2' } });
    fireEvent.blur(ceo);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    fireEvent.click(screen.getByRole('button', { name: GW_TEXT.load.toList }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe('GW-02 실행 만들기 409 키 재사용(sid:MARC-ISSUE-312 — 디자인 74 답 10-29)', () => {
  /** 파일을 올리고 대표이사 파트에 쪽을 넣은 뒤 [점검 시작]을 한 번 누른다. */
  async function pressOnce(createRun: GreenwashStore['createRun']) {
    const onCancel = vi.fn();
    const onStarted = vi.fn();
    render(
      <NewCheckScreen
        store={store({ createRun })}
        openPdf={neverOpen}
        onCancel={onCancel}
        onStarted={onStarted}
      />,
    );
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    await act(async () => {
      fireEvent.change(input, {
        target: {
          files: [
            new File([new Uint8Array([1])], 'a.pdf', {
              type: 'application/pdf',
            }),
          ],
        },
      });
    });
    await screen.findByTestId('file-meta');
    const ceo = screen.getByLabelText(words.parts.names.ceo, {
      selector: 'input',
    });
    const setCeo = (value: string) => {
      fireEvent.change(ceo, { target: { value } });
      fireEvent.blur(ceo);
    };
    setCeo('2');
    const start = screen.getByRole('button', { name: words.start });
    const press = () =>
      act(async () => {
        fireEvent.click(start);
      });
    await press();
    return { onCancel, onStarted, start, press, setCeo };
  }

  it('끊김 뒤 입력을 바꿔 다시 누름 → key_reused: 안내 글 + [목록 보기](onCancel), [점검 시작]은 켜진 채 같은 열쇠로 다시 보낸다', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'))
      .mockRejectedValue(new StoreError('key_reused', '지어낸 409'));
    const { onCancel, onStarted, start, press, setCeo } =
      await pressOnce(createRun);
    expect(screen.queryByTestId('start-error-to-list')).toBeNull();
    setCeo('3');
    await press();
    const alert = screen.getByTestId('start-error');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.getAttribute('data-error')).toBe('key_reused');
    expect(alert.getAttribute('data-tone')).toBe('error');
    expect(alert.textContent).toBe(words.keyReused.message);
    const toList = screen.getByRole('button', {
      name: words.keyReused.toList,
    });
    expect(toList.getAttribute('data-testid')).toBe('start-error-to-list');
    expect(screen.getByRole('button', { name: words.cancel })).toBeTruthy();
    expect(start.hasAttribute('disabled')).toBe(false);
    await press();
    expect(createRun).toHaveBeenCalledTimes(3);
    const keys = createRun.mock.calls.map((call) => call[2]);
    expect(new Set(keys).size).toBe(1);
    expect(screen.getByTestId('start-error').textContent).toBe(
      words.keyReused.message,
    );
    expect(onStarted).not.toHaveBeenCalled();
    fireEvent.click(toList);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('다른 거절(rejected·unreachable)은 [목록 보기] 없음 — 글도 그대로', async () => {
    const createRun = vi
      .fn<GreenwashStore['createRun']>()
      .mockRejectedValueOnce(new StoreError('rejected', '지어낸 거절'))
      .mockRejectedValueOnce(new StoreError('unreachable', '지어낸 끊김'));
    const { press } = await pressOnce(createRun);
    expect(screen.getByTestId('start-error').textContent).toBe(
      words.startRejected,
    );
    expect(screen.queryByTestId('start-error-to-list')).toBeNull();
    await press();
    expect(screen.getByTestId('start-error').textContent).toBe(
      GW_TEXT.runUnreachable.start,
    );
    expect(screen.queryByTestId('start-error-to-list')).toBeNull();
  });
});
