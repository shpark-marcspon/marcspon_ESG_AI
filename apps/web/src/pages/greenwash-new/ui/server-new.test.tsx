// @vitest-environment jsdom
// 밴드 GW1R ②(발주서 §3 C — GW-02): 진짜 실어댑터 + 거르지 않는 가짜 서버. 7쪽 PDF(쪽 세기는 이 탭) → 썸네일 7·「8」 은 마지막 쪽 넘음,
// 보고연도 칸은 모든 빌드에(밴드 GW2R ③ Q8 — 옛 「실어댑터 빌드엔 없음」을 갈음), 수정본 칸은 없음(밴드 GW2R ①),
// [점검 시작] → 연도 2026 이면 PATCH /documents/12 {reportYear:2026} 뒤 POST /runs 한 번(옵션에 연도 없음), 「선택 안 함」이면 PATCH 0 → 새 실행 '13'.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeGreenwashServer,
  refusal,
  serverStoreOf,
} from '../../../entities/greenwash/api/testing.ts';
import { GW_TEXT } from '../../../entities/greenwash/config/text.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { NewCheckScreen } from './NewCheckScreen.tsx';

afterEach(cleanup);

beforeAll(() => {
  // 썸네일 칸은 파일의 object URL 을 연다(jsdom 에는 없다 — openPdf 는 열리지 않는 가짜).
  Object.assign(URL, {
    createObjectURL: vi.fn(() => 'blob:지어낸'),
    revokeObjectURL: vi.fn(),
  });
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
/** 열리기만 하고 그리지 않는 PDF(썸네일 단추를 셀 수 있게). */
const openBlank: OpenPdf = async () => ({
  renderPage: () => ({ done: new Promise<void>(() => {}), cancel: () => {} }),
  close: () => {},
});

async function drawAndUpload() {
  const server = fakeGreenwashServer();
  const countPages = vi.fn(async () => 7);
  const { store } = serverStoreOf(server, { countPages });
  const onStarted = vi.fn();
  render(
    <NewCheckScreen
      store={store}
      openPdf={openBlank}
      onCancel={() => {}}
      onStarted={onStarted}
      now={() => new Date(2026, 9, 21, 9, 0)}
    />,
  );
  const file = new File([new Uint8Array(3000)], '지어낸 7쪽.pdf', {
    type: 'application/pdf',
  });
  const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
  await act(async () => {
    fireEvent.change(input, { target: { files: [file] } });
  });
  await screen.findByTestId('file-meta');
  return { server, onStarted, countPages, file };
}

const setPart = (name: string, value: string) => {
  const field = screen.getByLabelText(name, { selector: 'input' });
  fireEvent.change(field, { target: { value } });
  fireEvent.blur(field);
};

describe('GW-02 실어댑터(밴드 GW1R ② §3 C)', () => {
  it('7쪽 PDF → 올리기 셋째 걸음, 썸네일 7, 「8」 은 마지막 쪽 넘음, 연도 칸 있음(기본 올해 2026)·수정본 없음, [점검 시작] → PATCH {reportYear:2026} → POST /runs 한 번 → 13', async () => {
    const { server, onStarted, countPages, file } = await drawAndUpload();
    expect(countPages).toHaveBeenCalledWith(file);
    // 「3. 점검 설정」 카드를 지워 기본 단어 목록을 읽지 않는다(sid:MARC-ENT-603)
    expect(server.calls.map((call) => `${call.method} ${call.path}`)).toEqual([
      'POST /documents',
      'POST /documents/12/confirm',
    ]);
    expect(server.uploads).toEqual([
      { url: 'http://test.local/fake-upload/12', method: 'PUT', size: 3000 },
    ]);
    expect(screen.getByTestId('file-meta').textContent).toContain(
      words.upload.pageMeta(7),
    );
    expect(
      screen.getByTestId('thumbnails').querySelectorAll('button[data-page]')
        .length,
    ).toBe(7);
    // 보고연도 칸은 있다(밴드 GW2R ③ — 모든 빌드), 수정본 칸은 없다(그 목록도 읽지 않는다 — checks 0)
    expect(
      (screen.getByLabelText(words.year.label) as HTMLSelectElement).value,
    ).toBe('2026');
    expect(screen.queryByText('수정본 연결')).toBeNull();
    expect(server.count('GET /greenwash/checks')).toBe(0);
    // 대상 단어 칸은 「3. 점검 설정」 카드째 지웠다(sid:MARC-ENT-603). 아래 시작 본문에 extraTerms 키가 없다
    expect(screen.queryByTestId('default-terms')).toBeNull();
    expect(server.count('GET /greenwash/terms/default')).toBe(0);

    setPart(words.parts.names.ceo, '8');
    expect(document.body.textContent).toContain(
      words.parts.rangeError.over(8, 7),
    );
    setPart(words.parts.names.ceo, '1~2');
    setPart(words.parts.names.climate, '2~4');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    expect(
      server.calls.slice(2).map((call) => `${call.method} ${call.path}`),
    ).toEqual(['PATCH /documents/12', 'POST /runs']);
    expect(server.calls[2]!.body).toEqual({ reportYear: 2026 });
    expect(server.calls.at(-1)!.body).toEqual({
      module: 'greenwash',
      documentId: 12,
      launchKey: server.calls.at(-1)!.headers.get('Idempotency-Key'),
      options: { parts: { ceo: [1, 2], company: [], climate: [2, 3, 4] } },
    });
    expect(server.docs.get(12)!.reportYear).toBe(2026);
    expect(onStarted).toHaveBeenCalledWith('13');
  });

  it('연도를 「선택 안 함」으로 바꾸면 PATCH 0, POST /runs 하나(밴드 GW2R ③)', async () => {
    const { server, onStarted } = await drawAndUpload();
    fireEvent.change(screen.getByLabelText(words.year.label), {
      target: { value: '' },
    });
    setPart(words.parts.names.ceo, '1');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    expect(server.count('PATCH /documents/12')).toBe(0);
    expect(server.count('POST /runs')).toBe(1);
    expect(onStarted).toHaveBeenCalledWith('13');
  });

  it('연도 2025 → PATCH 거절(500)이면 POST /runs 0, 「점검을 시작하지 못했어요 …」, onStarted 없음', async () => {
    const { server, onStarted } = await drawAndUpload();
    server.override['PATCH /documents/12'] = () =>
      refusal(500, 'INTERNAL_SERVER_ERROR');
    fireEvent.change(screen.getByLabelText(words.year.label), {
      target: { value: '2025' },
    });
    setPart(words.parts.names.ceo, '1');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: words.start }));
    });
    expect(server.calls.at(-1)!).toMatchObject({
      method: 'PATCH',
      path: '/documents/12',
      body: { reportYear: 2025 },
    });
    expect(server.count('POST /runs')).toBe(0);
    expect(screen.getByTestId('start-error').textContent).toBe(
      words.startRejected,
    );
    expect(onStarted).not.toHaveBeenCalled();
  });
});
