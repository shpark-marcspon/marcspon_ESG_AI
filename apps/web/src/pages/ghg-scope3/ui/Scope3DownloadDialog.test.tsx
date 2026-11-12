// @vitest-environment jsdom
// S3-15 데이터 다운로드(밴드 S3D1 ②): 결과 화면 [데이터 다운로드] 단추(ok 갈래에만 · [데이터 업로드] 오른쪽 끝 · btn--sm black) ·
// 창(글 · 줄 하나 · 받는 동안 도는 표시 · 다시 눌러도 한 번 · 실패 셋 role=alert · [취소]·[확인] 닫기 · 닫히면 초점은 연 단추) ·
// 포트 exportFile(GET …/years/{y}/export blob · Content-Disposition 이름 · 404 notFound). 값·이름은 지어낸 것이다.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { EXPORT_FILE_NAME } from '../../../entities/ghg-scope3/api/index.ts';
import {
  XLSX_MEDIA_TYPE,
  fakeDoneResult,
  fakeRejectedResult,
  fakeScope3Server,
  portOf,
  processedSheet,
  purchaseRow,
  refusal,
} from '../../../entities/ghg-scope3/api/testing.ts';
import type { FakeScope3Server } from '../../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { buttonVariants } from '../../../shared/ui/button/index.ts';
import { ResultView } from './ResultView.tsx';
import { Scope3DownloadDialog } from './Scope3DownloadDialog.tsx';

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

const words = S3_TEXT.download;
const EXPORT = 'GET /inventory/scope3/years/2025/export';
const FILE_NAME = '2025_가상회사_Scope3_데이터.xlsx';
const BYTES = new Uint8Array([0x50, 0x4b, 3, 4]);

const xlsx = (name: string | null = FILE_NAME) =>
  new Response(BYTES, {
    status: 200,
    headers: {
      'Content-Type': XLSX_MEDIA_TYPE,
      ...(name === null ?
        {}
      : {
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(name)}`,
        }),
      'X-Content-Type-Options': 'nosniff',
    },
  });

const doneServer = () =>
  fakeScope3Server({
    runs: [
      {
        id: 9,
        status: 'done',
        reportYear: 2025,
        result: fakeDoneResult({
          sheets: [processedSheet('s', 'Category1', [purchaseRow('1.5')])],
        }),
      },
    ],
  });

function drawDialog(server: FakeScope3Server) {
  const save = vi.fn<(blob: Blob, fileName: string) => void>();
  const onClose = vi.fn();
  const opener = document.createElement('button');
  document.body.append(opener);
  render(
    <Scope3DownloadDialog
      port={portOf(server)}
      year={2025}
      returnFocus={() => opener}
      onClose={onClose}
      save={save}
    />,
  );
  return { save, onClose, opener };
}

describe('Scope3DownloadDialog', () => {
  it('글: 제목 · 무리 머리 · 「온실가스 인벤토리에서 관리 중인 데이터예요」 · 줄 하나 · 보고서 무리 0', () => {
    drawDialog(doneServer());
    const box = screen.getByTestId('s3-download');
    expect(within(box).getByRole('heading').textContent).toBe(words.title);
    expect(box.textContent).toContain(words.groupTitle);
    expect(box.textContent).toContain(
      '온실가스 인벤토리에서 관리 중인 데이터예요',
    );
    expect(within(box).getAllByTestId('s3-download-file')).toHaveLength(1);
    // 줄 아이콘(밴드 DB2 ③ — e6 ⑥): ReportXlsxIcon 48 판 · 「XLSX」 글자 패스.
    const icon = screen.getByTestId('s3-download-file').querySelector('svg')!;
    expect(icon.getAttribute('viewBox')).toBe('0 0 48 48');
    expect(icon.querySelector('[data-glyphs="XLSX"]')).not.toBeNull();
    expect(box.textContent).toContain(words.line);
    expect(box.textContent).not.toContain('보고서');
  });

  it('누르면 GET …/years/2025/export 한 번 → 서버 이름으로 저장 · 받는 동안 도는 표시 · 다시 눌러도 한 번', async () => {
    const server = doneServer();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[EXPORT] = [() => gate.then(() => xlsx())];
    const { save } = drawDialog(server);
    const line = screen.getByTestId('s3-download-file');
    fireEvent.click(line);
    fireEvent.click(line);
    await waitFor(() => expect(line.getAttribute('aria-busy')).toBe('true'));
    expect(within(line).getByLabelText(words.busy)).toBeTruthy();
    release();
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(server.count(EXPORT)).toBe(1);
    const [blob, name] = save.mock.calls[0]!;
    expect(name).toBe(FILE_NAME);
    expect(new Uint8Array(await blob.arrayBuffer())).toStrictEqual(BYTES);
    expect(line.getAttribute('aria-busy')).toBeNull();
    expect(screen.queryByTestId('s3-download-problem')).toBeNull();
  });

  it('Content-Disposition 이 없으면 EXPORT_FILE_NAME(해)', async () => {
    const server = doneServer();
    server.override[EXPORT] = () => xlsx(null);
    const { save } = drawDialog(server);
    fireEvent.click(screen.getByTestId('s3-download-file'));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0]![1]).toBe(EXPORT_FILE_NAME(2025));
  });

  it.each([
    ['404 → 받을 데이터 없음', () => refusal(404, 'NOT_FOUND'), words.notFound],
    [
      '회사 거절 → 그 글',
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
      S3_TEXT.company.ambiguous,
    ],
    ['그 밖 → 실패 글', () => refusal(500, 'INTERNAL'), words.failed],
  ])('%s(role=alert · 저장 0)', async (_, answer, text) => {
    const server = doneServer();
    server.override[EXPORT] = answer;
    const { save } = drawDialog(server);
    fireEvent.click(screen.getByTestId('s3-download-file'));
    const problem = await screen.findByRole('alert');
    expect(problem.textContent).toBe(text);
    expect(save).not.toHaveBeenCalled();
  });

  it.each([words.cancel, words.ok])('[%s] 는 닫는다(내려받기 0)', (label) => {
    const server = doneServer();
    const { onClose } = drawDialog(server);
    fireEvent.click(screen.getByRole('button', { name: label }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(server.count(EXPORT)).toBe(0);
  });
});

describe('ResultView — [데이터 다운로드]', () => {
  const draw = (server: FakeScope3Server) =>
    render(
      <ResultView
        port={portOf(server)}
        runId="9"
        year={2025}
        onUpload={() => {}}
      />,
    );

  it('카드 목록 줄에 [데이터 업로드] 오른쪽 끝 · solidBlack sm · 열면 창 · [취소] 뒤 초점은 단추', async () => {
    const server = doneServer();
    draw(server);
    const open = await screen.findByTestId('s3-download-open');
    expect(open.textContent).toBe(S3_TEXT.result.download);
    for (const name of buttonVariants({
      variant: 'solidBlack',
      shape: 'square',
      size: 'sm',
    }).split(' '))
      expect(open.classList).toContain(name);
    const upload = screen.getByRole('button', { name: S3_TEXT.result.upload });
    expect(
      open.compareDocumentPosition(upload) & Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
    expect(open.parentElement).toBe(upload.parentElement?.parentElement);
    expect(open.parentElement!.lastElementChild).toBe(open); // 줄의 오른쪽 끝(Figma 28023:11429)
    fireEvent.click(open);
    const box = await screen.findByTestId('s3-download');
    fireEvent.click(within(box).getByRole('button', { name: words.cancel }));
    await waitFor(() => expect(screen.queryByTestId('s3-download')).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(open));
    expect(server.count(EXPORT)).toBe(0);
  });

  it('rejected(그 해 지금 결과 없음) · 읽기 실패에는 단추가 없다', async () => {
    const rejected = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeRejectedResult(),
        },
      ],
    });
    draw(rejected);
    await screen.findByTestId('s3-rejected');
    expect(screen.queryByTestId('s3-download-open')).toBeNull();
    cleanup();
    const broken = doneServer();
    broken.override['GET /inventory/scope3/runs/9/result'] = () =>
      refusal(500, 'INTERNAL');
    draw(broken);
    await screen.findByTestId('s3-result-failed');
    expect(screen.queryByTestId('s3-download-open')).toBeNull();
  });
});
