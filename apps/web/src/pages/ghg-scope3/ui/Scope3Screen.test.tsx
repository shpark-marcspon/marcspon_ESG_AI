// @vitest-environment jsdom
// Scope 3 첫 화면과 창 셋(밴드 S3W1 ② — 발주서 §3 의 4·5·6·7). 진짜 Scope 3 실어댑터 + 가짜 서버(api/testing.ts — S3K1·BASE 두 판).
//   연도는 바깥 상태(경로 흉내 Harness)가 쥔다. 폴링은 짧게(pollMs 5).
//   4 화면: 마지막 실행 넷 갈래·재접속·다른 해만 → 없음·첫 읽기 실패·다시 읽기 실패 notice(앞 해 0)·회사 거절·운영 관리자 같은 흐름·403 글
//   5 카테고리: C10 끔·까닭·0 이면 [확인] 끔·Enter·첫 초점·담당자 열 0
//   6 올리기: 고른 수·양식·형식·크기 까닭(요청 0)·413·invalid_options·flow_not_runnable(문서 남음 — 다시 누르면 실행만)·회사 거절
//   7 진행: 폴링·실패·다시 계산(새 POST)·닫음 → 화면 안 진행 글·[진행 보기]
//   (4 에 ④ 몫: 첫 읽기 실패 셈·잃음 → [다음] 막음·[다시 확인] · 다시 계산 중 연도 바꿈 → 옛 답 버림)
//   8 S3-08(밴드 S3W2a ②): 카드 표기·단위·1000배 안 함·C10·빈·실패·생물기원 · C10 빼고 단추(S3W2b ② — 상세는 CategoryDetail.test) · 실패 수 줄 · 서버 글 0 · rejected · 읽기 실패·늦은 답 ·
//     [데이터 업로드] · 실패 갈래 넷(화면 줄·창)
import { useState } from 'react';

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  FAKE_ERROR_MESSAGE,
  FAKE_REJECT_DETAIL,
  FAKE_SHEET_ERROR,
  FAKE_TEMPLATE_NAME,
  activityRow,
  energyRow,
  failedSheet,
  fakeDoneResult,
  fakeRejectedResult,
  fakeRowFactor,
  fakeScope3Server,
  json,
  portOf,
  processedSheet,
  purchaseRow,
  refusal,
  unreachable,
} from '../../../entities/ghg-scope3/api/testing.ts';
import type { FakeScope3ServerOptions } from '../../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { Scope3Screen } from './Scope3Screen.tsx';

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

const t = S3_TEXT;
const YEARS = [2025, 2024, 2023, 2022, 2021];
const MB = 1024 * 1024;

function xlsx(name = '지어낸 입력.xlsx', size = 4) {
  const file = new File([new Uint8Array(4).fill(1)], name);
  if (size !== 4) Object.defineProperty(file, 'size', { value: size });
  return file;
}

function setup(
  options: FakeScope3ServerOptions = {},
  { operator = false, year = 2025 } = {},
) {
  const server = fakeScope3Server({ thisYear: 2026, ...options });
  const port = portOf(server);
  function Harness() {
    const [current, setCurrent] = useState(year);
    return (
      <Scope3Screen
        port={port}
        year={current}
        years={YEARS}
        operator={operator}
        pollMs={5}
        onYear={setCurrent}
      />
    );
  }
  render(<Harness />);
  return { server };
}

const ready = () => screen.findByRole('button', { name: t.screen.start });
const doneSteps = () =>
  [...screen.getByTestId('s3-steps').querySelectorAll('li')].map(
    (li) => li.getAttribute('data-done') === 'true',
  );
const pick = (file: File) => {
  const input = screen
    .getByTestId('s3-upload-dialog')
    .querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
};
const postRuns = (server: ReturnType<typeof fakeScope3Server>) =>
  server.calls.filter((c) => c.method === 'POST' && c.path === '/runs');

async function openUpload(chosen = ['C1', 'C3']) {
  fireEvent.click(await ready());
  const dialog = await screen.findByTestId('s3-category-dialog');
  for (const id of chosen)
    fireEvent.click(
      within(
        dialog.querySelector(`[data-category="${id}"]`) as HTMLElement,
      ).getByRole('checkbox'),
    );
  fireEvent.click(
    within(dialog).getByRole('button', { name: t.categoryDialog.confirm }),
  );
  return screen.findByTestId('s3-upload-dialog');
}

describe('4 Scope3Screen — 그 해 마지막 실행', () => {
  it('없음 → 기본(Step 다 안 끝남, 상태 줄 0) — 다른 해 실행만 있어도 없음', async () => {
    setup({
      runs: [{ id: 5, status: 'done', reportYear: 2024, documentId: 1 }],
    });
    await ready();
    expect(doneSteps()).toEqual([false, false, false, false]);
    expect(screen.queryByTestId('s3-done')).toBeNull();
    expect(screen.queryByTestId('s3-failed')).toBeNull();
    expect(screen.getByRole('heading', { name: t.screen.title })).toBeTruthy();
  });

  it('끝남 → 소개·Step·[다음] 대신 S3-08 카드 15장(결과 경로 한 번)', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'done', reportYear: 2025, documentId: 1 }],
    });
    const done = await screen.findByTestId('s3-done');
    await within(done).findByTestId('s3-result');
    expect(within(done).getAllByTestId('s3-result-card')).toHaveLength(15);
    expect(screen.queryByTestId('s3-steps')).toBeNull();
    expect(screen.queryByText(t.screen.introTitle)).toBeNull();
    expect(screen.queryByRole('button', { name: t.screen.start })).toBeNull();
    expect(server.count('GET /inventory/scope3/runs/5/result')).toBe(1);
  });

  it('진행 중 → 계산 창을 다시 띄움(재접속) → 끝나면 닫히고 완료', async () => {
    setup({
      runs: [
        {
          id: 5,
          status: 'processing',
          reportYear: 2025,
          documentId: 1,
          script: ['processing', 'processing', 'done'],
        },
      ],
    });
    const dialog = await screen.findByTestId('s3-progress-dialog');
    expect(dialog.getAttribute('data-view')).toBe('running');
    expect(
      within(dialog).getByText(t.progressDialog.runningTitle),
    ).toBeTruthy();
    await screen.findByTestId('s3-done');
    // 닫힘은 다음 그림에서 — 한 번 보고 끝내지 않고 기다린다(sid:MARC-ISSUE-526, 부하에서 한 번 빨강).
    await waitFor(() =>
      expect(screen.queryByTestId('s3-progress-dialog')).toBeNull(),
    );
  });

  it('끝난 뒤 다시 읽기 실패 → 완료 그대로 + notice(진행으로 돌아가지 않음) · 폴링 한 번 실패는 견딤', async () => {
    const { server } = setup({
      runs: [
        {
          id: 5,
          status: 'processing',
          reportYear: 2025,
          documentId: 1,
          script: ['processing', 'processing', 'done'],
        },
      ],
    });
    await screen.findByTestId('s3-progress-dialog');
    server.override['GET /runs/5'] = [unreachable];
    server.override['GET /inventory/scope3/years/2025'] = unreachable;
    await screen.findByTestId('s3-done');
    await screen.findByTestId('s3-notice');
    expect(screen.queryByTestId('s3-running')).toBeNull();
    // 끝남은 [다음] 대신 S3-08 의 [데이터 업로드](막히지 않음).
    expect(
      (
        await within(screen.getByTestId('s3-done')).findByRole('button', {
          name: t.result.upload,
        })
      ).hasAttribute('disabled'),
    ).toBe(false);
  });

  it('실패 → 한 줄 + [배출량 재계산하기] → 같은 문서·연도로 새 POST(resumeFromRunId 0), 창이 진행으로', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'failed', reportYear: 2025, documentId: 1 }],
      runScripts: [['queued', 'processing', 'processing']],
    });
    const line = await screen.findByTestId('s3-failed');
    expect(line.textContent).toContain(t.screen.failedLine);
    expect(doneSteps()).toEqual([true, true, true, false]);
    fireEvent.click(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    );
    const dialog = await screen.findByTestId('s3-progress-dialog');
    expect(dialog.getAttribute('data-view')).toBe('running');
    const [body] = postRuns(server).map(
      (c) => c.body as Record<string, unknown>,
    );
    expect(body).toMatchObject({
      documentId: 1,
      flowId: 'scope3.colab@157',
      options: { reportYear: 2025 },
    });
    expect(body).not.toHaveProperty('resumeFromRunId');
  });

  it('새 실행 첫 읽기 한 번 실패 → 진행 그대로(잃음 0) → 완료', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'failed', reportYear: 2025, documentId: 1 }],
      runScripts: [['processing', 'done']],
    });
    server.override['GET /runs/501'] = [unreachable];
    const line = await screen.findByTestId('s3-failed');
    fireEvent.click(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    );
    await screen.findByTestId('s3-done');
    expect(screen.queryByTestId('s3-unknown')).toBeNull();
    expect(
      server.calls.filter((c) => c.method === 'GET' && c.path === '/runs/501')
        .length,
    ).toBeGreaterThanOrEqual(2);
  });

  it('새 실행 첫 읽기 세 번 실패 → 잃음 · [다음] 막음(두 번째 실행 0) → [다시 확인]으로 회복(그사이 끝남)', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'failed', reportYear: 2025, documentId: 1 }],
      runScripts: [['done']],
    });
    server.override['GET /runs/501'] = [unreachable, unreachable, unreachable];
    const line = await screen.findByTestId('s3-failed');
    fireEvent.click(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    );
    const dialog = await screen.findByTestId('s3-progress-dialog');
    await waitFor(() => expect(dialog.getAttribute('data-view')).toBe('lost'));
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.progressDialog.close }),
    );
    const lost = await screen.findByTestId('s3-unknown');
    expect(lost.textContent).toContain(t.progressDialog.pollFailed);
    const start = screen.getByRole('button', { name: t.screen.start });
    expect(start.hasAttribute('disabled')).toBe(true);
    fireEvent.click(start);
    expect(screen.queryByTestId('s3-category-dialog')).toBeNull();
    expect(postRuns(server)).toHaveLength(1);
    fireEvent.click(
      within(lost).getByRole('button', { name: t.screen.recheck }),
    );
    await screen.findByTestId('s3-done');
    expect(screen.queryByTestId('s3-unknown')).toBeNull();
    // 끝남은 [다음] 대신 S3-08 의 [데이터 업로드](막히지 않음).
    expect(
      (
        await within(screen.getByTestId('s3-done')).findByRole('button', {
          name: t.result.upload,
        })
      ).hasAttribute('disabled'),
    ).toBe(false);
    expect(postRuns(server)).toHaveLength(1);
  });

  it('다시 계산 중 연도를 바꿈 → 옛 해 실행의 답은 버림(새 해 화면에 창·폴링 0)', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'failed', reportYear: 2025, documentId: 1 }],
    });
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override['POST /runs'] = [
      () => gate.then(() => json(201, { id: 777, status: 'queued' })),
    ];
    const line = await screen.findByTestId('s3-failed');
    fireEvent.click(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    );
    await waitFor(() => expect(postRuns(server)).toHaveLength(1));
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      { target: { value: '2024' } },
    );
    await ready();
    await waitFor(() => expect(screen.queryByTestId('s3-failed')).toBeNull());
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.queryByTestId('s3-progress-dialog')).toBeNull();
    expect(screen.queryByTestId('s3-running')).toBeNull();
    expect(server.calls.some((c) => c.path === '/runs/777')).toBe(false);
  });

  it('첫 읽기 실패 → 화면 자리 + [다시 시도]', async () => {
    const { server } = setup();
    server.override['GET /inventory/scope3/years/2025'] = [unreachable];
    await screen.findByTestId('load-failure');
    fireEvent.click(screen.getByRole('button', { name: t.screen.retryLoad }));
    await ready();
  });

  it('다시 읽기(연도 바꿈) 실패 → notice 한 줄, 앞 해의 실행은 보이지 않음', async () => {
    const { server } = setup({
      runs: [{ id: 5, status: 'done', reportYear: 2025, documentId: 1 }],
    });
    await screen.findByTestId('s3-done');
    server.override['GET /inventory/scope3/years/2024'] = [unreachable];
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      { target: { value: '2024' } },
    );
    await screen.findByTestId('s3-notice');
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(screen.queryByTestId('s3-done')).toBeNull();
  });

  it('회사 거절(첫 읽기) → 그 글', async () => {
    setup({ company: 'ambiguous' });
    expect(
      (await screen.findByTestId('company-refusal')).textContent,
    ).toContain(t.company.ambiguous);
  });
});

describe('5 CategoryDialog — S3-02', () => {
  it('C10 끔 + 까닭 · 담당자 열 0 · 첫 초점 C1 · 0 이면 [확인] 끔 · Enter 로 다음', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    const c10 = within(
      dialog.querySelector('[data-category="C10"]') as HTMLElement,
    ).getByRole('checkbox');
    expect(c10.hasAttribute('disabled')).toBe(true);
    expect(dialog.textContent).toContain(t.disabledReason);
    expect(dialog.textContent).not.toContain('담당자');
    expect(dialog.textContent).toContain('C1. 구매 상품 및 서비스');
    await waitFor(() =>
      expect(document.activeElement).toBe(
        within(
          dialog.querySelector('[data-category="C1"]') as HTMLElement,
        ).getByRole('checkbox'),
      ),
    );
    const confirm = within(dialog).getByRole('button', {
      name: t.categoryDialog.confirm,
    });
    expect(confirm.hasAttribute('disabled')).toBe(true);
    fireEvent.click(c10);
    expect(confirm.hasAttribute('disabled')).toBe(true);
    fireEvent.click(
      within(
        dialog.querySelector('[data-category="C2"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    fireEvent.submit(dialog.querySelector('form') as HTMLFormElement);
    expect((await screen.findByTestId('s3-chosen-count')).textContent).toBe(
      t.uploadDialog.chosen(1),
    );
  });

  it('꼴(GX3 ② 6~8): 창 960 · 안내 PageInfo · 머리 고정·목록 360 · 체크 20 · C10 까닭은 이름 옆', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    expect(dialog.className).toContain('w-[960px]');
    expect(within(dialog).getByTestId('s3-category-guide').textContent).toBe(
      `${t.categoryDialog.guideLead}${t.categoryDialog.guideStrong}${t.categoryDialog.guideTail}`,
    );
    const list = within(dialog).getByTestId('s3-category-list');
    expect(list.className).toContain('max-h-[360px]');
    expect(list.contains(within(dialog).getByTestId('s3-category-head'))).toBe(
      false,
    );
    const c1 = within(
      dialog.querySelector('[data-category="C1"]') as HTMLElement,
    ).getByRole('checkbox');
    expect(c1.className).toContain('h-5');
    const reason = dialog.querySelector('#s3-reason-C10') as HTMLElement;
    expect(reason.className).toContain('ml-2');
    expect(reason.className).not.toContain('ml-auto');
  });

  it('전체 고름: C10 빼고 다 · 일부면 indeterminate · 다 골랐으면 다 풂', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    const all = within(dialog).getByRole('checkbox', {
      name: t.categoryDialog.selectAll,
    });
    const checkedIds = () =>
      [...dialog.querySelectorAll('[data-category]')]
        .filter(
          (row) =>
            row
              .querySelector('[role="checkbox"]')
              ?.getAttribute('data-state') === 'checked',
        )
        .map((row) => row.getAttribute('data-category'));
    expect(all.getAttribute('data-state')).toBe('unchecked');
    fireEvent.click(
      within(
        dialog.querySelector('[data-category="C2"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    expect(all.getAttribute('data-state')).toBe('indeterminate');
    fireEvent.click(all);
    expect(checkedIds()).toHaveLength(14);
    expect(checkedIds()).not.toContain('C10');
    expect(all.getAttribute('data-state')).toBe('checked');
    fireEvent.click(all);
    expect(checkedIds()).toEqual([]);
  });

  it('S3-02a 설명 창: 머리 (?) 로 엶 · 설명 15(Figma 글) · 초점 [확인] · [확인]이면 닫고 (?) 로 · 고른 값 그대로', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(
        dialog.querySelector('[data-category="C3"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    const open = within(dialog).getByRole('button', {
      name: t.categoryDialog.infoOpen,
    });
    fireEvent.click(open);
    const info = await screen.findByTestId('s3-category-info');
    expect(within(info).getByRole('heading').textContent).toBe(
      t.categoryInfo.title,
    );
    const rows = info.querySelectorAll('[role="row"][data-category]');
    expect(rows).toHaveLength(15);
    expect(info.querySelector('[data-category="C10"]')?.textContent).toContain(
      '우리가 만든 중간재(부품, 원단 등)를 사간 다른 기업이 완성품으로 조립·가공할 때 쓰는 탄소',
    );
    expect(info.querySelector('[data-category="C1"]')?.textContent).toContain(
      'C1. 구매 상품 및 서비스',
    );
    const confirm = within(info).getByRole('button', {
      name: t.categoryInfo.confirm,
    });
    await waitFor(() => expect(document.activeElement).toBe(confirm));
    expect(within(info).getAllByRole('button')).toHaveLength(1);
    fireEvent.click(confirm);
    await waitFor(() =>
      expect(screen.queryByTestId('s3-category-info')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(open));
    expect(screen.getByTestId('s3-category-dialog')).toBeTruthy();
    expect(
      within(dialog.querySelector('[data-category="C3"]') as HTMLElement)
        .getByRole('checkbox')
        .getAttribute('data-state'),
    ).toBe('checked');
  });

  it('설명 창 Esc 는 설명 창만 닫는다', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.categoryDialog.infoOpen }),
    );
    const info = await screen.findByTestId('s3-category-info');
    fireEvent.keyDown(info, { key: 'Escape' });
    await waitFor(() =>
      expect(screen.queryByTestId('s3-category-info')).toBeNull(),
    );
    expect(screen.getByTestId('s3-category-dialog')).toBeTruthy();
  });

  it('줄마다 (?) 는 장식(aria-hidden) · 15 줄 · 체크 이름에 섞이지 않음', async () => {
    setup();
    fireEvent.click(await ready());
    const dialog = await screen.findByTestId('s3-category-dialog');
    const tips = within(dialog).getAllByTestId('s3-category-tip');
    expect(tips).toHaveLength(15);
    for (const tip of tips)
      expect(tip.getAttribute('aria-hidden')).toBe('true');
    expect(
      within(dialog).getByRole('checkbox', {
        name: t.categoryDialog.item(1, t.categories.C1),
      }),
    ).toBeTruthy();
  });
});

describe('6 UploadDialog — S3-03', () => {
  it('고른 수 · 양식 내려받기(가짜 바이트·이름) · 올려 계산 → 진행 → 완료, 고른 카테고리는 요청에 0', async () => {
    const created: Blob[] = [];
    vi.stubGlobal(
      'URL',
      Object.assign(URL, {
        createObjectURL: (blob: Blob) => (created.push(blob), 'blob:x'),
        revokeObjectURL: () => {},
      }),
    );
    const { server } = setup({}, {});
    const dialog = await openUpload();
    expect(within(dialog).getByTestId('s3-chosen-count').textContent).toBe(
      t.uploadDialog.chosen(2),
    );
    // 양식 칸(GX3 고침 9): 앞 파일 아이콘 · outline 알약 sm · 단추 안 아이콘 0.
    // 아이콘 꼴(밴드 DB2 ③ — e6 ⑥): MyIcons XlsIcon 28 판 · 「XLS」 띠.
    expect(
      within(dialog).getByTestId('s3-template-icon').getAttribute('viewBox'),
    ).toBe('0 0 28 28');
    expect(
      within(dialog).getByTestId('s3-template').querySelector('svg'),
    ).toBeNull();
    fireEvent.click(within(dialog).getByTestId('s3-template'));
    await waitFor(() => expect(created).toHaveLength(1));
    expect(server.count('GET /inventory/scope3/template')).toBe(1);
    expect(FAKE_TEMPLATE_NAME).toContain('.xlsx');
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    await screen.findByTestId('s3-progress-dialog');
    await screen.findByTestId('s3-done');
    const body = postRuns(server)[0]!.body as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual([
      'documentId',
      'flowId',
      'launchKey',
      'module',
      'options',
    ]);
    expect(JSON.stringify({ ...body, launchKey: null })).not.toMatch(
      /"C[0-9]+"|categor/i,
    );
    expect(server.bodies('POST /documents')).toEqual([
      { fileName: '지어낸 입력.xlsx', sizeBytes: 4, reportYear: 2025 },
    ]);
  });

  it('양식 실패 → 단추 옆 한 줄', async () => {
    setup({ server: 'base' });
    const dialog = await openUpload();
    fireEvent.click(within(dialog).getByTestId('s3-template'));
    expect(
      (await within(dialog).findByTestId('s3-template-error')).textContent,
    ).toContain(t.uploadDialog.templateFailed);
  });

  it('형식·크기 까닭(20MB 같음은 받음, 넘음은 거절) — 요청 0', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    const before = server.calls.length;
    pick(xlsx('a.csv'));
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain(t.fileProblem.type);
    pick(xlsx('a.xlsx', 20 * MB + 1));
    expect(
      within(dialog).getByTestId('s3-upload-problem').textContent,
    ).toContain(t.fileProblem.size);
    expect(
      within(dialog)
        .getByRole('button', { name: t.uploadDialog.submit })
        .hasAttribute('disabled'),
    ).toBe(true);
    pick(xlsx('a.xlsx', 20 * MB));
    expect(within(dialog).queryByTestId('s3-upload-problem')).toBeNull();
    expect(server.calls.length).toBe(before);
  });

  it('0바이트 파일 → 파일 거절 글, 요청 0(GX1 M-5)', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    const before = server.calls.length;
    pick(xlsx('a.xlsx', 0));
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain('파일을 읽지 못했어요. 파일을 다시 골라 주세요');
    expect(
      within(dialog)
        .getByRole('button', { name: t.uploadDialog.submit })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(server.calls.length).toBe(before);
  });

  it.each([
    [
      '413',
      () => refusal(413, 'upload_too_large'),
      'POST /documents',
      S3_TEXT.fileProblem.size,
    ],
    [
      'invalid_options',
      () => refusal(400, 'INVALID_OPTIONS'),
      'POST /runs',
      S3_TEXT.uploadDialog.invalidOptions,
    ],
    [
      '문서 만들기 validation_error(GX1 M-5)',
      () => refusal(422, 'VALIDATION_ERROR', { sizeBytes: ['지어낸 칸 글'] }),
      'POST /documents',
      '파일을 읽지 못했어요. 파일을 다시 골라 주세요',
    ],
    ['그 밖', () => json(500, {}), 'POST /runs', S3_TEXT.uploadDialog.failed],
  ] as const)('거절 %s → 그 글', async (_, answer, key, text) => {
    const { server } = setup();
    server.override[key] = answer;
    const dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain(text);
  });

  it('BASE 판 flow_not_runnable → 그 글, 문서는 남고 다시 누르면 실행만 다시', async () => {
    const { server } = setup({ server: 'base' });
    const dialog = await openUpload();
    pick(xlsx());
    const submit = within(dialog).getByRole('button', {
      name: t.uploadDialog.submit,
    });
    fireEvent.click(submit);
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain(t.uploadDialog.flowNotRunnable);
    fireEvent.click(submit);
    await waitFor(() => expect(postRuns(server)).toHaveLength(2));
    expect(server.count('POST /documents')).toBe(1);
  });

  it('운영 관리자: BASE 판 403 → 운영 관리자 글 · S3K1 판은 같은 흐름으로 계산', async () => {
    setup({ server: 'base', operator: true }, { operator: true });
    let dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain(t.uploadDialog.operatorForbidden);
    cleanup();
    setup({ operator: true }, { operator: true });
    dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    await screen.findByTestId('s3-done');
  });

  it('회사 거절 → 그 글', async () => {
    const { server } = setup();
    server.override['POST /documents'] = () =>
      refusal(404, 'COMPANY_NOT_FOUND');
    const dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    expect(
      (await within(dialog).findByTestId('s3-upload-problem')).textContent,
    ).toContain(t.company.not_found);
  });
});

describe('7 ProgressDialog — S3-07', () => {
  it('실패 창 → [배출량 재계산하기](Enter) → 새 실행 진행', async () => {
    const { server } = setup({
      runScripts: [
        ['queued', 'failed'],
        ['queued', 'processing', 'processing'],
      ],
    });
    const dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    const progress = await screen.findByTestId('s3-progress-dialog');
    await waitFor(() =>
      expect(progress.getAttribute('data-view')).toBe('failed'),
    );
    expect(progress.textContent).toContain(t.progressDialog.failedTitle);
    fireEvent.submit(progress.querySelector('form') as HTMLFormElement);
    await waitFor(() => expect(postRuns(server)).toHaveLength(2));
    await waitFor(() =>
      expect(
        screen.getByTestId('s3-progress-dialog').getAttribute('data-view'),
      ).toBe('running'),
    );
    expect(postRuns(server)[1]!.body).not.toHaveProperty('resumeFromRunId');
  });

  it('닫음 → 화면 안 진행 글 + [진행 보기] 로 다시 엶', async () => {
    setup({
      runScripts: [['queued', ...Array<'processing'>(500).fill('processing')]],
    });
    const dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    const progress = await screen.findByTestId('s3-progress-dialog');
    fireEvent.click(
      within(progress).getByRole('button', { name: t.progressDialog.close }),
    );
    const running = await screen.findByTestId('s3-running');
    expect(
      screen
        .getByRole('button', { name: t.screen.start })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(running.textContent).toContain(t.screen.runningTitle);
    // 두 줄(GX3 고침 12) · 계산 중에도 Step 1~3 완료(GX3 s2).
    expect(running.querySelectorAll('br')).toHaveLength(1);
    expect(running.textContent).toContain(t.screen.runningBody[1]);
    expect(doneSteps()).toEqual([true, true, true, false]);
    fireEvent.click(
      within(running).getByRole('button', { name: t.screen.openProgress }),
    );
    await screen.findByTestId('s3-progress-dialog');
  });
});

describe('8 S3-08 — 카테고리 카드 목록(밴드 S3W2a ②)', () => {
  const doneWith = (result: unknown, extra: object = {}) =>
    setup({
      runs: [
        { id: 5, status: 'done', reportYear: 2025, documentId: 1, result },
      ],
      ...extra,
    });
  const cardOf = (id: string) =>
    screen
      .getAllByTestId('s3-result-card')
      .find((card) => card.getAttribute('data-category') === id)!;
  const totalOf = (id: string) =>
    within(cardOf(id)).getByTestId('s3-card-total').textContent;

  const SAMPLE = fakeDoneResult({
    llmCalls: {
      classify: { success: 3, 'failed:refusal': 2 },
      factor: { 'failed:timeout': 1 },
    },
    sheets: [
      processedSheet('s1', 'Category1', [purchaseRow('1e-05')]),
      processedSheet('s4a', 'Category4', [
        activityRow('transport_distance', '1234.5'),
      ]),
      processedSheet('s4b', 'Category4', [
        activityRow('transport_spend', '0.25'),
      ]),
      processedSheet('s5', 'Category5', [activityRow('waste', '2', '0.5')]),
      processedSheet('s8', 'Category8', [energyRow('leased_asset', '1000')]),
      processedSheet('s12', 'Category12', [
        energyRow('product_eol', '3', null),
      ]),
      processedSheet('s13', 'Category13', [
        energyRow('leased_out_asset', '-0.0'),
      ]),
      { status: 'empty', sheet: 's14', category: 'Category14' },
      failedSheet('s15', 'Category15'),
    ],
  });

  it('표기: 수 글자 → review-table 표기 + tCO2eq · 시트 둘 합 · 1000배 안 함 · 지수 · -0', async () => {
    doneWith(SAMPLE);
    await screen.findByTestId('s3-result');
    expect(totalOf('C1')).toBe('<0.001tCO2eq');
    expect(totalOf('C4')).toBe('1,234.75tCO2eq');
    expect(totalOf('C8')).toBe('1,000tCO2eq');
    expect(totalOf('C13')).toBe('0tCO2eq');
    expect(within(cardOf('C1')).getByText('tCO2eq')).toBeTruthy();
    expect(cardOf('C1').textContent).toContain(t.result.cardTitle(1));
    expect(cardOf('C1').textContent).toContain(t.result.cards.C1);
    expect(cardOf('C1').textContent).toContain(t.result.totalLabel);
  });

  it('합 없음 「-」(C10 끔·빈 시트·시트 없음) · 실패 「계산 실패」 · 생물기원 둘째 줄은 C5·C12 만', async () => {
    doneWith(SAMPLE);
    await screen.findByTestId('s3-result');
    expect(cardOf('C10').getAttribute('data-state')).toBe('off');
    expect(totalOf('C10')).toBe(t.result.empty);
    expect(totalOf('C14')).toBe(t.result.empty);
    expect(totalOf('C2')).toBe(t.result.empty);
    expect(cardOf('C15').getAttribute('data-state')).toBe('failed');
    expect(totalOf('C15')).toBe(t.result.cardFailed);
    expect(
      within(cardOf('C5')).getByTestId('s3-card-biogenic').textContent,
    ).toBe(`${t.result.biogenicLabel} 0.5 tCO2eq`);
    expect(
      within(cardOf('C12')).getByTestId('s3-card-biogenic').textContent,
    ).toBe(`${t.result.biogenicLabel} ${t.result.empty}`);
    expect(screen.getAllByTestId('s3-card-biogenic')).toHaveLength(2);
  });

  it('카드는 C10 빼고 단추 하나(링크 0) — 누르면 상세, [목록] 이면 목록 · S3W3 칸 0 · 08a 띠', async () => {
    doneWith(SAMPLE);
    const view = await screen.findByTestId('s3-result');
    for (const card of within(view).getAllByTestId('s3-result-card')) {
      const off = card.getAttribute('data-category') === 'C10';
      expect(within(card).queryAllByRole('button')).toHaveLength(off ? 0 : 1);
      expect(within(card).queryAllByRole('link')).toEqual([]);
    }
    expect(cardOf('C10').querySelector('[tabindex],button')).toBeNull();
    // 카드 단추 열넷 + [데이터 다운로드]·[데이터 업로드](S3D1).
    expect(within(view).getAllByRole('button')).toHaveLength(16);
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    const detail = await screen.findByTestId('s3-detail');
    expect(detail.getAttribute('data-category')).toBe('C1');
    fireEvent.click(within(detail).getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    // S3D1: [데이터 다운로드]는 1차에 든다(sid:MARC-ENT-592 — 앞의 「0」 단언을 뒤집음).
    expect(within(view).getAllByTestId('s3-download-open')).toHaveLength(1);
    expect(within(view).getByTestId('s3-result-notice').textContent).toBe(
      'AI 제안값은 참고용이에요. 최종 값은 담당자가 직접 확인해 주세요',
    );
  });

  it('done 안의 실패 수 한 줄 · 둘 다 0 이면 줄 0 · 서버 글(시트 error) 0', async () => {
    doneWith(SAMPLE);
    // [e6 대조 — 감독 확정](S3W2c ② 8) AI 호출 수는 말하지 않는다.
    expect((await screen.findByTestId('s3-problems')).textContent).toBe(
      '시트 1개와 일부 줄을 계산하지 못했어요',
    );
    expect(document.body.textContent).not.toContain(FAKE_SHEET_ERROR);
    cleanup();
    doneWith(fakeDoneResult());
    await screen.findByTestId('s3-result');
    expect(screen.queryByTestId('s3-problems')).toBeNull();
    expect(t.result.problems(2, 0)).toBe('시트 2개를 계산하지 못했어요');
    expect(t.result.problems(0, 4)).toBe('일부 줄은 계산하지 못했어요');
    expect(t.result.problems(0, 4)).not.toMatch(/\d/);
  });

  it.each(['reader_problem', 'factor_book', 'legacy_template'] as const)(
    'rejected %s → 카드 0 · 까닭 글(detail 0) · [데이터 업로드] → S3-02',
    async (reason) => {
      doneWith(fakeRejectedResult(reason));
      const box = await screen.findByTestId('s3-rejected');
      expect(box.textContent).toContain(t.result.rejected[reason]);
      expect(screen.queryAllByTestId('s3-result-card')).toEqual([]);
      expect(document.body.textContent).not.toContain(FAKE_REJECT_DETAIL);
      expect(screen.getByTestId('s3-done').contains(box)).toBe(true);
      fireEvent.click(
        within(box).getByRole('button', { name: t.result.upload }),
      );
      await screen.findByTestId('s3-category-dialog');
    },
  );

  it('done 인데 결과 없음(404) → 그 자리에 [데이터 업로드] → S3-02 → 새 계산 → 카드(S3W2a ⑤)', async () => {
    const { server } = doneWith(null, {
      runScripts: [['queued', 'done']],
      runResults: [
        fakeDoneResult({
          sheets: [processedSheet('s', 'Category1', [purchaseRow('3')])],
        }),
      ],
    });
    const failed = await screen.findByTestId('s3-result-failed');
    expect(failed.textContent).toContain(t.result.loadFailed);
    expect(server.count('GET /inventory/scope3/runs/5/result')).toBe(1);
    fireEvent.click(
      within(failed).getByRole('button', { name: t.result.upload }),
    );
    const category = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(
        category.querySelector('[data-category="C1"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    fireEvent.click(
      within(category).getByRole('button', { name: t.categoryDialog.confirm }),
    );
    const dialog = await screen.findByTestId('s3-upload-dialog');
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    await waitFor(() => expect(totalOf('C1')).toBe('3tCO2eq'));
  });

  it('결과 읽기 실패(끊김·409) → 그 자리 + [다시 시도] → 카드 · 회사 거절 글', async () => {
    const { server } = doneWith(SAMPLE);
    server.override['GET /inventory/scope3/runs/5/result'] = [
      unreachable,
      () => refusal(409, 'run_not_done'),
    ];
    const failed = await screen.findByTestId('s3-result-failed');
    expect(screen.getByTestId('s3-done').contains(failed)).toBe(true);
    expect(failed.textContent).toContain(t.result.loadFailed);
    fireEvent.click(
      within(failed).getByRole('button', { name: t.result.retryLoad }),
    );
    fireEvent.click(
      within(await screen.findByTestId('s3-result-failed')).getByRole(
        'button',
        { name: t.result.retryLoad },
      ),
    );
    await screen.findByTestId('s3-result');
    cleanup();
    const other = doneWith(SAMPLE);
    other.server.override['GET /inventory/scope3/runs/5/result'] = () =>
      refusal(400, 'COMPANY_INACTIVE');
    expect(
      (await screen.findByTestId('s3-result-failed')).textContent,
    ).toContain(t.company.inactive);
  });

  it('늦은 답은 버린다 — 2025 결과를 기다리는 동안 2024 로 바꾸면 2024 카드만', async () => {
    const { server } = setup({
      runs: [
        {
          id: 5,
          status: 'done',
          reportYear: 2025,
          documentId: 1,
          result: fakeDoneResult({
            sheets: [processedSheet('s', 'Category1', [purchaseRow('25')])],
          }),
        },
        {
          id: 4,
          status: 'done',
          reportYear: 2024,
          documentId: 1,
          result: fakeDoneResult({
            sheets: [processedSheet('s', 'Category1', [purchaseRow('24')])],
          }),
        },
      ],
    });
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override['GET /inventory/scope3/runs/5/result'] = [
      () =>
        gate.then(() =>
          json(
            200,
            fakeDoneResult({
              sheets: [processedSheet('s', 'Category1', [purchaseRow('25')])],
            }),
          ),
        ),
    ];
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/5/result')).toBe(1),
    );
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      { target: { value: '2024' } },
    );
    await screen.findByTestId('s3-result');
    expect(totalOf('C1')).toBe('24tCO2eq');
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(totalOf('C1')).toBe('24tCO2eq');
  });

  it('[데이터 업로드] → S3-02 → 올림 → 새 실행 → 끝나면 새 결과', async () => {
    const { server } = doneWith(SAMPLE, {
      runScripts: [['queued', 'done']],
      runResults: [
        fakeDoneResult({
          sheets: [processedSheet('s', 'Category1', [purchaseRow('7')])],
        }),
      ],
    });
    const view = await screen.findByTestId('s3-result');
    fireEvent.click(
      within(view).getByRole('button', { name: t.result.upload }),
    );
    const category = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(
        category.querySelector('[data-category="C1"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    fireEvent.click(
      within(category).getByRole('button', { name: t.categoryDialog.confirm }),
    );
    const dialog = await screen.findByTestId('s3-upload-dialog');
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/501/result')).toBe(1),
    );
    await waitFor(() => expect(totalOf('C1')).toBe('7tCO2eq'));
  });
});

describe('8 실패 갈래 넷(errorCode — 발주서 S3W2a §1-6)', () => {
  it.each([
    ['setup_error', 'setup', false, false],
    ['document_missing', 'file', false, true],
    ['object_too_large', 'file', false, true],
    ['internal', 'transient', true, false],
    ['attempts_exhausted', 'transient', true, false],
    ['step_error', 'general', true, false],
    ['storage_denied', 'general', true, false],
  ] as const)(
    '화면 줄: %s → %s 글 · [재계산] %s · [데이터 업로드] %s · 서버 errorMessage 0',
    async (errorCode, kind, retry, upload) => {
      setup({
        runs: [
          {
            id: 5,
            status: 'failed',
            reportYear: 2025,
            documentId: 1,
            errorCode,
          },
        ],
      });
      const line = await screen.findByTestId('s3-failed');
      const body = within(line).getByTestId('s3-failed-body');
      expect(body.getAttribute('data-failure')).toBe(kind);
      expect(body.textContent).toBe(t.progressDialog.failureBody[kind]);
      expect(
        within(line).queryByRole('button', { name: t.progressDialog.retry }),
      ).toEqual(retry ? expect.anything() : null);
      expect(
        within(line).queryByRole('button', { name: t.result.upload }),
      ).toEqual(upload ? expect.anything() : null);
      // setup 은 단추 0(S3W2c ② 11). 실패 줄 제목 글꼴(S3W2c ② 6).
      expect(within(line).queryAllByRole('button')).toHaveLength(
        retry || upload ? 1 : 0,
      );
      expect(
        within(line).getByText(t.screen.failedLine).getAttribute('class'),
      ).toBe('m-0 text-style-pre-body-04 text-text-primary');
      expect(document.body.textContent).not.toContain(FAKE_ERROR_MESSAGE);
    },
  );

  it('실패 본문 글(S3W2c ② 9·10 — e6 대조, 검증 권고 R2): setup·transient 글자 그대로', () => {
    expect(t.progressDialog.failureBody.setup).toBe(
      '지금은 계산할 수 없어요. 운영 관리자에게 알려 주세요',
    );
    expect(t.progressDialog.failureBody.transient).toBe(
      '일시적인 연결 오류로 분석이 중단되었어요. 아래 버튼을 눌러 배출량을 다시 산정해 주세요',
    );
  });

  it('창: setup_error → 설정 글 + [닫기]만(S3W2c ② 11) · file → [재계산] 0 · [데이터 업로드] → S3-02', async () => {
    setup({
      runScripts: [['queued', 'failed']],
      runErrors: ['setup_error'],
    });
    let dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    let progress = await screen.findByTestId('s3-progress-dialog');
    await waitFor(() =>
      expect(progress.getAttribute('data-view')).toBe('failed'),
    );
    expect(progress.textContent).toContain(
      '지금은 계산할 수 없어요. 운영 관리자에게 알려 주세요',
    );
    expect(
      within(progress).queryByRole('button', { name: t.progressDialog.retry }),
    ).toBeNull();
    expect(
      within(progress).queryByRole('button', { name: t.result.upload }),
    ).toBeNull();
    expect(progress.querySelector('form')).toBeNull();
    expect(progress.textContent).not.toContain(FAKE_ERROR_MESSAGE);
    // [닫기] 단추(✕ 단추와 이름이 같다 — 둘 다 닫는다). 본문의 것을 누르면 창이 닫히고 화면 줄에도 단추 0.
    const closes = within(progress).getAllByRole('button', {
      name: t.progressDialog.close,
    });
    expect(closes).toHaveLength(2);
    fireEvent.click(closes[closes.length - 1]!);
    await waitFor(() =>
      expect(screen.queryByTestId('s3-progress-dialog')).toBeNull(),
    );
    expect(
      within(await screen.findByTestId('s3-failed')).queryAllByRole('button'),
    ).toEqual([]);
    cleanup();
    setup({
      runScripts: [['queued', 'failed']],
      runErrors: ['object_missing'],
    });
    dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    progress = await screen.findByTestId('s3-progress-dialog');
    await waitFor(() =>
      expect(progress.getAttribute('data-view')).toBe('failed'),
    );
    expect(progress.textContent).toContain(t.progressDialog.failureBody.file);
    expect(
      within(progress).queryByRole('button', { name: t.progressDialog.retry }),
    ).toBeNull();
    expect(progress.querySelector('form')).toBeNull();
    fireEvent.click(
      within(progress).getByRole('button', { name: t.result.upload }),
    );
    await screen.findByTestId('s3-category-dialog');
    expect(screen.queryByTestId('s3-progress-dialog')).toBeNull();
  });
});

describe('570 문 — 새 실행 길 여섯(S3W3a ③ · 처분 Q6)', () => {
  const words = t.rerunWarning;
  const rows = [
    purchaseRow('1', 'c1_x!2'),
    purchaseRow('2', 'c1_x!3'),
    purchaseRow('4', 'c1_x!4'),
  ];
  const base = (edited = true) => ({
    id: 5,
    status: 'done' as const,
    reportYear: 2025,
    documentId: 1,
    result: fakeDoneResult({
      sheets: [processedSheet('c1_x', 'Category1', rows)],
    }),
    edits:
      edited ?
        [
          { rowId: 'c1_x!2', category: 'C1', excluded: true },
          { rowId: 'c1_x!3', category: 'C1', factor: fakeRowFactor() },
        ]
      : [],
  });
  const failed = (errorCode: string) => ({
    id: 6,
    status: 'failed' as const,
    reportYear: 2025,
    documentId: 1,
    errorCode,
  });
  const YEAR = 'GET /inventory/scope3/years/2025';
  const button = (area: string, name: string) => async () =>
    within(await screen.findByTestId(area)).findByRole('button', { name });

  /** 길 넷(창 없이 바로 눌리는 길). */
  const paths = [
    {
      way: '① 결과 [데이터 업로드]',
      seeds: (edited: boolean) => [base(edited)],
      press: button('s3-done', t.result.upload),
      opensCategories: true,
      problem: 's3-gate-problem',
    },
    {
      way: '② 실패 줄 file [데이터 업로드]',
      seeds: (edited: boolean) => [base(edited), failed('object_missing')],
      press: button('s3-failed', t.result.upload),
      opensCategories: true,
      problem: 's3-retry-problem',
    },
    {
      way: '③ 실패 줄 [배출량 재계산하기]',
      seeds: (edited: boolean) => [base(edited), failed('internal')],
      press: button('s3-failed', t.progressDialog.retry),
      opensCategories: false,
      problem: 's3-retry-problem',
    },
    {
      // H-3(GX3 ④): 마지막이 setup 실패여도 그 해 지금 결과가 있으면 카드 + 실패 띠 — 길은 결과 [데이터 업로드](앞 판의 첫 화면 [다음] 자리).
      way: '⑥ setup 실패 뒤 결과 [데이터 업로드](H-3)',
      seeds: (edited: boolean) => [base(edited), failed('setup_error')],
      press: button('s3-done', t.result.upload),
      opensCategories: true,
      problem: 's3-gate-problem',
    },
    {
      // 결과 없는 해의 첫 화면 [다음](gate 'start') — 지금 결과가 없으면 고친 행도 0 이라 경고 길은 닿지 않는다(GX3 검증 B1).
      way: '⑦ 첫 화면 [다음](결과 없는 해)',
      seeds: () => [failed('setup_error')],
      press: ready,
      opensCategories: true,
      problem: 's3-gate-problem',
      warns: false,
    },
  ];
  const warnPaths = paths.filter((one) => one.warns !== false);
  const started = async (
    server: ReturnType<typeof fakeScope3Server>,
    opensCategories: boolean,
  ) => {
    if (opensCategories) await screen.findByTestId('s3-category-dialog');
    else await waitFor(() => expect(postRuns(server)).toHaveLength(1));
  };

  it.each(warnPaths)(
    '$way: 고친 행이 있으면 경고(n · 초점 취소) · 취소면 안 간다 · 계속이면 간다',
    async ({ seeds, press, opensCategories }) => {
      const { server } = setup({
        runs: seeds(true),
        runScripts: [['processing', 'processing']],
      });
      fireEvent.click(await press());
      const warning = await screen.findByTestId('s3-rerun-warning');
      expect(warning.textContent).toContain(words.title(2));
      await waitFor(() =>
        expect(document.activeElement?.textContent).toBe(words.cancel),
      );
      expect(screen.queryByTestId('s3-category-dialog')).toBeNull();
      expect(postRuns(server)).toHaveLength(0);
      fireEvent.click(
        within(warning).getByRole('button', { name: words.cancel }),
      );
      await waitFor(() =>
        expect(screen.queryByTestId('s3-rerun-warning')).toBeNull(),
      );
      expect(screen.queryByTestId('s3-category-dialog')).toBeNull();
      expect(postRuns(server)).toHaveLength(0);
      fireEvent.click(await press());
      fireEvent.click(
        within(await screen.findByTestId('s3-rerun-warning')).getByRole(
          'button',
          { name: words.confirm },
        ),
      );
      await started(server, opensCategories);
    },
  );

  it('경고 취소: 눌러도 초점이 안 가 pressed 가 body 면 backFocus 로 물러선다 · 초점이 갔으면 그 단추로', async () => {
    setup({ runs: [base(true), failed('setup_error')] });
    const next = await button('s3-done', t.result.upload)();
    const cancelWarning = async () => {
      fireEvent.click(
        within(await screen.findByTestId('s3-rerun-warning')).getByRole(
          'button',
          { name: words.cancel },
        ),
      );
      await waitFor(() =>
        expect(screen.queryByTestId('s3-rerun-warning')).toBeNull(),
      );
    };
    expect(document.activeElement).toBe(document.body);
    fireEvent.click(next);
    await cancelWarning();
    await waitFor(() => expect(document.activeElement).toBe(next));
    const other = screen.getByRole('combobox');
    other.focus();
    fireEvent.click(next);
    await cancelWarning();
    await waitFor(() => expect(document.activeElement).toBe(other));
  });

  it.each(paths)(
    '$way: 고친 행이 0 이면 창 없이 바로',
    async ({ seeds, press, opensCategories }) => {
      const { server } = setup({
        runs: seeds(false),
        runScripts: [['processing', 'processing']],
      });
      fireEvent.click(await press());
      await started(server, opensCategories);
      expect(screen.queryByTestId('s3-rerun-warning')).toBeNull();
    },
  );

  it.each(paths)(
    '$way: 연도 읽기 실패면 넘어가지 않고 그 단추 옆 한 줄',
    async ({ seeds, press, problem }) => {
      const { server } = setup({ runs: seeds(true) });
      const pressed = await press();
      await waitFor(() =>
        expect(screen.queryByTestId('s3-result-failed')).toBeNull(),
      );
      server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
      fireEvent.click(pressed);
      expect((await screen.findByTestId(problem)).textContent).toBe(
        words.readFailed,
      );
      expect(screen.queryByTestId('s3-rerun-warning')).toBeNull();
      expect(screen.queryByTestId('s3-category-dialog')).toBeNull();
      expect(postRuns(server)).toHaveLength(0);
    },
  );

  /** 진행 창의 실패 보기까지 간다(앞 실행은 실패, 다시 계산도 실패). */
  const toFailedWindow = async (
    errorCode: string,
    edited = true,
    readYear = true,
  ) => {
    const made = setup({
      runs: [base(edited), failed('internal')],
      runScripts: [['failed'], ['processing', 'processing']],
      runErrors: [errorCode],
    });
    fireEvent.click(await button('s3-failed', t.progressDialog.retry)());
    if (edited)
      fireEvent.click(
        within(await screen.findByTestId('s3-rerun-warning')).getByRole(
          'button',
          { name: words.confirm },
        ),
      );
    await waitFor(() =>
      expect(
        screen.getByTestId('s3-progress-dialog').getAttribute('data-view'),
      ).toBe('failed'),
    );
    if (!readYear)
      made.server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
    return made;
  };

  it('④ 진행 창 [배출량 재계산하기]: 창을 먼저 닫고 경고 · 취소면 진행 창으로 · 계속이면 새 POST', async () => {
    const { server } = await toFailedWindow('internal');
    const press = () =>
      fireEvent.click(
        within(screen.getByTestId('s3-progress-dialog')).getByRole('button', {
          name: t.progressDialog.retry,
        }),
      );
    press();
    const warning = await screen.findByTestId('s3-rerun-warning');
    expect(screen.queryByTestId('s3-progress-dialog')).toBeNull();
    fireEvent.click(
      within(warning).getByRole('button', { name: words.cancel }),
    );
    await screen.findByTestId('s3-progress-dialog');
    expect(postRuns(server)).toHaveLength(1);
    press();
    fireEvent.click(
      within(await screen.findByTestId('s3-rerun-warning')).getByRole(
        'button',
        { name: words.confirm },
      ),
    );
    await waitFor(() => expect(postRuns(server)).toHaveLength(2));
    await screen.findByTestId('s3-progress-dialog');
  });

  it('⑤ 진행 창 [데이터 업로드]: 창을 먼저 닫고 경고 · 계속이면 카테고리 창', async () => {
    const { server } = await toFailedWindow('object_missing');
    fireEvent.click(
      within(screen.getByTestId('s3-progress-dialog')).getByRole('button', {
        name: t.result.upload,
      }),
    );
    const warning = await screen.findByTestId('s3-rerun-warning');
    expect(screen.queryByTestId('s3-progress-dialog')).toBeNull();
    fireEvent.click(
      within(warning).getByRole('button', { name: words.confirm }),
    );
    await screen.findByTestId('s3-category-dialog');
    expect(postRuns(server)).toHaveLength(1);
  });

  it('④ 고친 행 0: 진행 창에서 바로 새 POST · 창은 그대로', async () => {
    const { server } = await toFailedWindow('internal', false);
    fireEvent.click(
      within(screen.getByTestId('s3-progress-dialog')).getByRole('button', {
        name: t.progressDialog.retry,
      }),
    );
    await waitFor(() => expect(postRuns(server)).toHaveLength(2));
    expect(screen.queryByTestId('s3-rerun-warning')).toBeNull();
    await screen.findByTestId('s3-progress-dialog');
  });

  it('④ 연도 읽기 실패: 진행 창으로 돌아와 창 안 한 줄 · 새 POST 0', async () => {
    const { server } = await toFailedWindow('internal', true, false);
    fireEvent.click(
      within(screen.getByTestId('s3-progress-dialog')).getByRole('button', {
        name: t.progressDialog.retry,
      }),
    );
    await waitFor(async () =>
      expect(
        (await screen.findByTestId('s3-progress-dialog')).textContent,
      ).toContain(words.readFailed),
    );
    expect(postRuns(server)).toHaveLength(1);
  });

  it('수는 누른 때 새로 읽은 값(화면이 쥔 값이 아니다) · 다른 사람이 더 고친 뒤', async () => {
    const { server } = setup({ runs: [base()] });
    const press = button('s3-done', t.result.upload);
    const pressed = await press();
    fireEvent.click(pressed);
    fireEvent.click(
      within(await screen.findByTestId('s3-rerun-warning')).getByRole(
        'button',
        { name: words.cancel },
      ),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('s3-rerun-warning')).toBeNull(),
    );
    await server.send(
      new Request(
        'http://test.local/api/inventory/scope3/runs/5/categories/C1/exclusions',
        {
          method: 'POST',
          body: JSON.stringify({ rowIds: ['c1_x!4'], reason: '지어낸' }),
        },
      ),
    );
    fireEvent.click(pressed);
    expect(
      (await screen.findByTestId('s3-rerun-warning')).textContent,
    ).toContain(words.title(3));
  });

  it('답을 기다리는 사이 두 번 눌러도 읽기 하나 · 경고 하나', async () => {
    const { server } = setup({ runs: [base()] });
    const pressed = await button('s3-done', t.result.upload)();
    const before = server.count(YEAR);
    fireEvent.click(pressed);
    fireEvent.click(pressed);
    await screen.findByTestId('s3-rerun-warning');
    expect(server.count(YEAR)).toBe(before + 1);
    expect(screen.getAllByTestId('s3-rerun-warning')).toHaveLength(1);
  });

  it('답을 기다리는 사이 해를 바꾸면 늦은 답은 버린다(경고·창 0)', async () => {
    const { server } = setup({ runs: [base()] });
    const pressed = await button('s3-done', t.result.upload)();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[YEAR] = [
      () =>
        gate.then(() =>
          json(200, {
            year: 2025,
            baseRunId: '5',
            latest: null,
            categories: [],
            editedRowsUnlocked: 2,
          }),
        ),
    ];
    fireEvent.click(pressed);
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      {
        target: { value: '2024' },
      },
    );
    await ready();
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(screen.queryByTestId('s3-rerun-warning')).toBeNull();
    expect(screen.queryByTestId('s3-category-dialog')).toBeNull();
  });

  it('옛 해 답을 기다리는 사이 해를 바꿔도 새 해의 단추는 눌린다', async () => {
    const { server } = setup({ runs: [base()] });
    const pressed = await button('s3-done', t.result.upload)();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[YEAR] = [() => gate.then(() => refusal(500, 'INTERNAL'))];
    fireEvent.click(pressed);
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      {
        target: { value: '2024' },
      },
    );
    const year2024 = 'GET /inventory/scope3/years/2024';
    const next = await ready();
    // 빈 해 안내·물러섬 읽기가 끝난 뒤의 수에서 문의 읽기 하나만 는다.
    await screen.findByTestId('s3-year-hint');
    const before = server.count(year2024);
    fireEvent.click(next);
    await screen.findByTestId('s3-category-dialog');
    expect(server.count(year2024)).toBe(before + 1);
    release();
  });

  it.each(paths.filter((one) => one.problem === 's3-retry-problem'))(
    '$way: 경고를 취소하면 초점은 누른 단추로',
    async ({ seeds, press }) => {
      setup({ runs: seeds(true) });
      const pressed = await press();
      pressed.focus();
      fireEvent.click(pressed);
      const warning = await screen.findByTestId('s3-rerun-warning');
      fireEvent.click(
        within(warning).getByRole('button', { name: words.cancel }),
      );
      await waitFor(() => expect(document.activeElement).toBe(pressed));
    },
  );

  it('해가 바뀌면 띄운 경고는 닫힌다', async () => {
    setup({ runs: [base()] });
    fireEvent.click(await button('s3-done', t.result.upload)());
    await screen.findByTestId('s3-rerun-warning');
    fireEvent.change(
      screen.getByRole('combobox', {
        name: t.screen.yearLabel,
        hidden: true,
      }),
      { target: { value: '2024' } },
    );
    await waitFor(() =>
      expect(screen.queryByTestId('s3-rerun-warning')).toBeNull(),
    );
  });

  it('문 실패 줄: 해를 바꾸면 지워진다 · 다시 누르면 지워진다', async () => {
    const { server } = setup({ runs: [base(false), failed('setup_error')] });
    const upload = button('s3-done', t.result.upload);
    const fail = async () => {
      const next = await upload();
      // 빈 해 안내 읽기가 이 거절을 먼저 먹지 않게 끝나길 기다린다.
      await waitFor(() =>
        expect(
          server.count('GET /inventory/scope3/years/2021'),
        ).toBeGreaterThan(0),
      );
      server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
      fireEvent.click(next);
      await screen.findByTestId('s3-gate-problem');
    };
    await fail();
    fireEvent.click(await upload());
    await waitFor(() =>
      expect(screen.queryByTestId('s3-gate-problem')).toBeNull(),
    );
    fireEvent.click(
      within(await screen.findByTestId('s3-category-dialog')).getByRole(
        'button',
        { name: t.categoryDialog.cancel },
      ),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('s3-category-dialog')).toBeNull(),
    );
    await fail();
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      {
        target: { value: '2024' },
      },
    );
    await waitFor(() =>
      expect(screen.queryByTestId('s3-gate-problem')).toBeNull(),
    );
  });

  it('잠근 카테고리의 고친 행은 경고에 안 든다', async () => {
    const { server } = setup({
      runs: [base()],
      locks: [{ year: 2025, category: 'C1', runId: 5 }],
    });
    fireEvent.click(await button('s3-done', t.result.upload)());
    await screen.findByTestId('s3-category-dialog');
    expect(screen.queryByTestId('s3-rerun-warning')).toBeNull();
    expect(server.count(YEAR)).toBeGreaterThan(0);
  });
});

describe('빈 해 안내 · 20건 밖 물러섬(S3W3d ② — 값 파일 V4·처분 K4)', () => {
  const doneIn = (id: number, reportYear: number) => ({
    id,
    status: 'done' as const,
    reportYear,
    documentId: 1,
  });
  const failedIn = (id: number, reportYear: number) => ({
    id,
    status: 'failed' as const,
    reportYear,
    documentId: 1,
    errorCode: 'internal',
  });
  const yearKey = (year: number) => `GET /inventory/scope3/years/${year}`;
  const hint = () => screen.queryByTestId('s3-year-hint');
  /** 안내 읽기 다섯이 답할 때까지. */
  const readsDone = (server: ReturnType<typeof setup>['server']) =>
    waitFor(() =>
      YEARS.forEach((year) =>
        expect(server.count(yearKey(year))).toBeGreaterThan(0),
      ),
    ).then(() => new Promise((resolve) => setTimeout(resolve, 20)));

  it('빈 해: 결과 있는 가장 최근 해를 알리고 [Y년 보기]가 그 해 결과로 · 초점은 연도 고르기', async () => {
    setup({ runs: [doneIn(1, 2022), doneIn(2, 2023)] });
    const line = await screen.findByTestId('s3-year-hint');
    expect(line.textContent).toContain(t.screen.yearHint(2025, 2023));
    const go = within(line).getByRole('button', {
      name: t.screen.yearHintGo(2023),
    });
    fireEvent.click(go);
    await screen.findByTestId('s3-done');
    expect(hint()).toBeNull();
    const select = screen.getByRole('combobox', { name: t.screen.yearLabel });
    expect((select as HTMLSelectElement).value).toBe('2023');
    expect(document.activeElement).toBe(select);
  });

  it('어느 해에도 결과가 없으면 띠 없음 · 첫 화면 그대로', async () => {
    const { server } = setup();
    await ready();
    await readsDone(server);
    expect(hint()).toBeNull();
  });

  it('결과 있는 해에서는 다른 해를 읽지 않는다', async () => {
    const { server } = setup({ runs: [doneIn(1, 2025), doneIn(2, 2023)] });
    await screen.findByTestId('s3-done');
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(hint()).toBeNull();
    expect(server.count(yearKey(2023))).toBe(0);
  });

  it('실패만 있는 해: 고른 해면 띠가 뜨고, 다른 해면 가리키지 않는다', async () => {
    setup({ runs: [failedIn(1, 2024), doneIn(2, 2022), failedIn(3, 2025)] });
    const line = await screen.findByTestId('s3-year-hint');
    expect(line.textContent).toContain(t.screen.yearHint(2025, 2022));
  });

  it('고른 해가 실패 최신 + 앞에 끝난 결과면 띠 없음', async () => {
    const { server } = setup({
      runs: [doneIn(1, 2025), failedIn(2, 2025), doneIn(3, 2023)],
    });
    await screen.findByTestId('s3-failed');
    await readsDone(server);
    expect(hint()).toBeNull();
  });

  it('진행 중 실행을 지켜보는 동안은 읽지 않고 띠 없음', async () => {
    const { server } = setup({
      runs: [
        { ...doneIn(1, 2025), status: 'processing' as const },
        doneIn(2, 2023),
      ],
    });
    await screen.findByTestId('s3-progress-dialog');
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(hint()).toBeNull();
    expect(server.count(yearKey(2023))).toBe(0);
  });

  it('빈 해에서 새 실행을 시작하면 띠가 사라진다', async () => {
    setup({
      runs: [doneIn(1, 2023)],
      runScripts: [Array(9).fill('processing')],
    });
    await screen.findByTestId('s3-year-hint');
    const dialog = await openUpload();
    pick(xlsx());
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.uploadDialog.submit }),
    );
    await screen.findByTestId('s3-progress-dialog');
    await waitFor(() => expect(hint()).toBeNull());
  });

  it.each([
    ['500', () => refusal(500, 'INTERNAL')],
    ['회사 거절', () => refusal(400, 'COMPANY_INACTIVE')],
  ])(
    '읽기 하나가 실패(%s)면 띠 없음 · 첫 화면은 막지 않는다',
    async (_, no) => {
      const server = fakeScope3Server({
        thisYear: 2026,
        runs: [doneIn(1, 2022)],
      });
      server.override[yearKey(2024)] = no;
      render(
        <Scope3Screen
          port={portOf(server)}
          year={2025}
          years={YEARS}
          pollMs={5}
          onYear={() => {}}
        />,
      );
      await ready();
      await readsDone(server);
      expect(hint()).toBeNull();
    },
  );

  it('해가 바뀌면 앞 해의 늦은 답을 버린다', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const server = fakeScope3Server({
      thisYear: 2026,
      runs: [doneIn(1, 2022)],
    });
    // 2025 판의 안내 읽기 하나만 잡아 둔다. 늦은 답은 정상 답이어야 버림을 잰다(실패 답이면 어차피 띠가 없다).
    server.override[yearKey(2021)] = [
      () =>
        gate.then(() =>
          server.send(
            new Request('http://test.local/api/inventory/scope3/years/2021'),
          ),
        ),
    ];
    function Harness() {
      const [current, setCurrent] = useState(2025);
      return (
        <Scope3Screen
          port={portOf(server)}
          year={current}
          years={YEARS}
          pollMs={5}
          onYear={setCurrent}
        />
      );
    }
    render(<Harness />);
    await waitFor(() => expect(server.count(yearKey(2021))).toBeGreaterThan(0));
    fireEvent.change(
      screen.getByRole('combobox', { name: t.screen.yearLabel }),
      { target: { value: '2024' } },
    );
    const line = await screen.findByTestId('s3-year-hint');
    expect(line.textContent).toContain(t.screen.yearHint(2024, 2022));
    release();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(hint()?.textContent).toContain(t.screen.yearHint(2024, 2022));
  });

  /** 2024 의 실패 실행으로 목록 첫 쪽을 채운다 — 2023 의 끝난 실행은 20건 밖. */
  const crowded = [
    doneIn(1, 2023),
    ...Array.from({ length: 21 }, (_, i) => failedIn(i + 2, 2024)),
  ];

  it('20건 밖: 안내가 가리킨 해로 가면 올리기 화면이 아니라 결과', async () => {
    setup({ runs: crowded });
    const line = await screen.findByTestId('s3-year-hint');
    fireEvent.click(
      within(line).getByRole('button', { name: t.screen.yearHintGo(2023) }),
    );
    await screen.findByTestId('s3-done');
    expect(screen.queryByRole('button', { name: t.screen.start })).toBeNull();
  });

  it('20건 밖: 그 해를 바로 열어도 결과 · 띠 없음', async () => {
    setup({ runs: crowded }, { year: 2023 });
    await screen.findByTestId('s3-done');
    expect(hint()).toBeNull();
  });

  it.each([
    ['연도 500', yearKey(2023), () => refusal(500, 'INTERNAL')],
    ['연도 404', yearKey(2023), () => refusal(404, 'NOT_FOUND')],
    ['실행 500', 'GET /runs/1', () => refusal(500, 'INTERNAL')],
  ])(
    '마지막 실행 읽기(%s)가 실패면 실패 갈래 — 첫 읽기 자리(GX5)',
    async (_, key, answer) => {
      const server = fakeScope3Server({ thisYear: 2026, runs: crowded });
      server.override[key] = [answer];
      render(
        <Scope3Screen
          port={portOf(server)}
          year={2023}
          years={YEARS}
          pollMs={5}
          onYear={() => {}}
        />,
      );
      await screen.findByTestId('load-failure');
      expect(screen.queryByTestId('s3-done')).toBeNull();
    },
  );
});

describe('그 해 마지막 실행은 그 해 상태의 latest(GX5 · sid:MARC-ISSUE-595)', () => {
  const doneIn = (id: number, reportYear: number) => ({
    id,
    status: 'done' as const,
    reportYear,
    documentId: 1,
  });
  /** 그 해 실행 뒤에 다른 해 실행 25건 — 그 해 것은 목록 첫 쪽(20건) 밖. */
  const buried = (...mine: NonNullable<FakeScope3ServerOptions['runs']>) => [
    ...mine,
    ...Array.from({ length: 25 }, (_, i) => doneIn(i + 10, 2024)),
  ];
  const listReads = (server: ReturnType<typeof setup>['server']) =>
    server.calls.filter((c) => c.method === 'GET' && c.path === '/runs').length;

  it('20건 밖의 진행 중 실행 → 창을 다시 띄움 · 목록 0 · 첫 읽기의 실행 1', async () => {
    const { server } = setup({
      runs: buried({
        id: 5,
        status: 'processing',
        reportYear: 2025,
        documentId: 1,
        script: Array<'processing'>(500).fill('processing'),
      }),
    });
    const dialog = await screen.findByTestId('s3-progress-dialog');
    expect(dialog.getAttribute('data-view')).toBe('running');
    expect(listReads(server)).toBe(0);
    // 첫 읽기는 그 해 상태 → GET /runs/5 하나(그 뒤는 폴링).
    expect(server.calls[0]).toMatchObject({
      path: '/inventory/scope3/years/2025',
    });
    expect(server.calls.find((c) => /^\/runs\/\d+$/.test(c.path))?.path).toBe(
      '/runs/5',
    );
  });

  it('20건 밖의 실패 실행 + 앞의 끝난 결과 → 실패 띠 + 카드 그대로', async () => {
    const { server } = setup({
      runs: buried(
        {
          id: 3,
          status: 'done',
          reportYear: 2025,
          documentId: 1,
          result: fakeDoneResult({
            sheets: [processedSheet('c1_x', 'Category1', [purchaseRow('3')])],
          }),
        },
        {
          id: 5,
          status: 'failed',
          reportYear: 2025,
          documentId: 1,
          errorCode: 'internal',
        },
      ),
    });
    await screen.findByTestId('s3-failed');
    await screen.findByTestId('s3-result');
    expect(screen.getAllByTestId('s3-result-card')).toHaveLength(15);
    expect(screen.queryByTestId('s3-steps')).toBeNull();
    expect(listReads(server)).toBe(0);
    expect(server.count('GET /runs/5')).toBe(1);
  });

  it('latest null(다른 해 실행만 25건) → 첫 화면 · 실행 읽기 0', async () => {
    const { server } = setup({ runs: buried() });
    await ready();
    expect(screen.queryByTestId('s3-done')).toBeNull();
    expect(screen.queryByTestId('s3-failed')).toBeNull();
    expect(listReads(server)).toBe(0);
    expect(server.calls.filter((c) => /^\/runs\/\d+$/.test(c.path))).toEqual(
      [],
    );
  });
});

describe('진행 셈 한 줄(S3W3d ③ — 값 파일 V1·V3·덧)', () => {
  const words = t.progressDialog;
  const running = (script: ('processing' | 'done')[]) => ({
    id: 5,
    status: 'processing' as const,
    reportYear: 2025,
    documentId: 1,
    script,
  });
  const count = () => screen.findByTestId('s3-progress-count');

  it('폴링마다 수가 따라가고 마무리는 수 없이 · 분모는 서버 단계 수', async () => {
    setup({ runs: [running(Array(40).fill('processing'))] });
    await screen.findByText(words.countDone(14, 3));
    await screen.findByText(words.assembling);
  });

  it('셈 줄만 살아 있는 영역 · 글 둘은 그 밖 · 아이콘은 숨김·움직임 줄이기면 안 돎', async () => {
    setup({ runs: [running(Array(9).fill('processing'))] });
    const line = await count();
    expect(line.getAttribute('aria-live')).toBe('polite');
    expect(line.closest('[role="status"]')).toBeNull();
    const icon = screen.getByTestId('s3-progress-icon');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(icon.querySelector('svg')!.getAttribute('class')).toContain(
      'motion-safe:animate-spin',
    );
  });

  it('진행 창 960 · 큰 글 secondary · 본문 두 줄 tertiary(GX3 고침 12)', async () => {
    setup({ runs: [running(Array(9).fill('processing'))] });
    await count();
    const dialog = screen.getByTestId('s3-progress-dialog');
    expect(dialog.className).toContain('w-[960px]');
    const title = within(dialog).getByText(t.progressDialog.runningTitle);
    expect(title.className).toContain('text-text-secondary');
    const body = [...dialog.querySelectorAll('p')].find(
      (p) => p.textContent === t.progressDialog.runningBody.join(''),
    )!;
    expect(body.className).toContain('text-text-tertiary');
    expect(body.textContent).toBe(t.progressDialog.runningBody.join(''));
    expect(body.querySelectorAll('br')).toHaveLength(1);
  });

  /** 실행 답을 한 값으로 고정해 그린다(폴링 5ms 가 시험을 앞질러 가지 않게). 고정은 delete 로 푼다. */
  const KEY = 'GET /runs/5';
  const drawPinned = async (
    script: ('processing' | 'done')[],
    change: (body: Record<string, unknown>) => Record<string, unknown>,
  ) => {
    const server = fakeScope3Server({
      thisYear: 2026,
      runs: [running(script)],
    });
    const answer = await server.send(
      new Request('http://test.local/api/runs/5'),
    );
    const body = change((await answer.json()) as Record<string, unknown>);
    server.override[KEY] = () => json(200, body);
    render(
      <Scope3Screen
        port={portOf(server)}
        year={2025}
        years={YEARS}
        pollMs={5}
        onYear={() => {}}
      />,
    );
    return server;
  };

  it('창을 닫아도 화면 글 아래에 같은 줄 · 퍼센트 글 0', async () => {
    await drawPinned(['processing'], (body) => body);
    const dialog = await screen.findByTestId('s3-progress-dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: words.close }));
    const box = await screen.findByTestId('s3-running');
    const line = await within(box).findByTestId('s3-progress-count');
    expect(line.textContent).toBe(words.countDone(14, 0));
    expect(box.textContent).not.toContain('%');
  });

  it('단계를 못 읽음(빈 steps): 셈 줄 없음 · 글 둘은 그대로 · 폴링은 산다', async () => {
    const server = await drawPinned(['processing', 'done'], (body) => ({
      ...body,
      steps: [],
    }));
    const dialog = await screen.findByTestId('s3-progress-dialog');
    expect(dialog.textContent).toContain(words.runningTitle);
    const reads = server.count(KEY);
    await waitFor(() => expect(server.count(KEY)).toBeGreaterThan(reads + 2));
    expect(screen.queryByTestId('s3-progress-count')).toBeNull();
    delete server.override[KEY];
    await screen.findByTestId('s3-done');
  });
});

describe('H-3 — 마지막 실행이 실패·거절·진행이어도 그 해 지금 결과(GX3 ④ · sid:MARC-ISSUE-583)', () => {
  const base = {
    id: 5,
    status: 'done' as const,
    reportYear: 2025,
    documentId: 1,
    result: fakeDoneResult({
      sheets: [processedSheet('c1_x', 'Category1', [purchaseRow('3')])],
    }),
  };
  const cardCount = () => screen.getAllByTestId('s3-result-card').length;

  it.each(['reader_problem', 'legacy_template'] as const)(
    '결과 있는 해 → 거절 %s → 카드·총합 그대로 + 카드 위 띠(지금 글) · 첫 화면 0',
    async (reason) => {
      setup({
        runs: [
          base,
          {
            id: 6,
            status: 'done',
            reportYear: 2025,
            documentId: 2,
            result: fakeRejectedResult(reason),
          },
        ],
      });
      const banner = await screen.findByTestId('s3-rejected-banner');
      expect(banner.textContent).toBe(t.result.rejected[reason]);
      expect(banner.getAttribute('role')).toBe('alert');
      expect(cardCount()).toBe(15);
      expect(screen.getByTestId('s3-scope-total').textContent).toContain('3');
      expect(screen.queryByTestId('s3-rejected')).toBeNull();
      expect(screen.queryByTestId('s3-steps')).toBeNull();
      expect(screen.queryByRole('button', { name: t.screen.start })).toBeNull();
      const result = screen.getByTestId('s3-result');
      expect(
        banner.compareDocumentPosition(
          within(result).getAllByTestId('s3-result-card')[0]!,
        ) & Node.DOCUMENT_POSITION_FOLLOWING,
      ).toBeTruthy();
    },
  );

  it('결과 있는 해 → 실패(internal) → 카드 + 실패 줄은 카드 위 · [배출량 재계산하기] 그대로', async () => {
    setup({
      runs: [
        base,
        {
          id: 6,
          status: 'failed',
          reportYear: 2025,
          documentId: 1,
          errorCode: 'internal',
        },
      ],
    });
    const line = await screen.findByTestId('s3-failed');
    await screen.findByTestId('s3-result');
    expect(cardCount()).toBe(15);
    expect(
      line.compareDocumentPosition(screen.getByTestId('s3-done')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    ).toBeTruthy();
    expect(screen.queryByTestId('s3-steps')).toBeNull();
  });

  it('결과 없는 해 → 실패면 앞 갈래 그대로(첫 화면 + 실패 줄, 카드 0)', async () => {
    setup({
      runs: [
        {
          id: 6,
          status: 'failed',
          reportYear: 2025,
          documentId: 1,
          errorCode: 'internal',
        },
      ],
    });
    await screen.findByTestId('s3-failed');
    expect(screen.getByTestId('s3-steps')).toBeTruthy();
    expect(screen.queryByTestId('s3-done')).toBeNull();
  });

  it('결과 있는 해에서 새 계산이 도는 동안 카드는 그대로 · 결과 [데이터 업로드]는 막힘 · 진행 글은 카드 위', async () => {
    setup({
      runs: [base],
      runScripts: [['queued', ...Array<'processing'>(500).fill('processing')]],
    });
    await screen.findByTestId('s3-result');
    fireEvent.click(
      within(screen.getByTestId('s3-done')).getByRole('button', {
        name: t.result.upload,
      }),
    );
    const category = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(
        category.querySelector('[data-category="C1"]') as HTMLElement,
      ).getByRole('checkbox'),
    );
    fireEvent.click(
      within(category).getByRole('button', { name: t.categoryDialog.confirm }),
    );
    const upload = await screen.findByTestId('s3-upload-dialog');
    pick(xlsx());
    fireEvent.click(
      within(upload).getByRole('button', { name: t.uploadDialog.submit }),
    );
    const progress = await screen.findByTestId('s3-progress-dialog');
    fireEvent.click(
      within(progress).getByRole('button', { name: t.progressDialog.close }),
    );
    const running = await screen.findByTestId('s3-running');
    await screen.findByTestId('s3-result');
    expect(cardCount()).toBe(15);
    expect(
      within(screen.getByTestId('s3-done'))
        .getByRole('button', { name: t.result.upload })
        .hasAttribute('disabled'),
    ).toBe(true);
    expect(
      running.compareDocumentPosition(screen.getByTestId('s3-done')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('결과 있는 해에서 진행 상태를 잃으면(폴링 세 번 실패) 결과 [데이터 업로드]도 막힘(GX3 검증 권고 1)', async () => {
    const { server } = setup({
      runs: [
        base,
        {
          id: 6,
          status: 'failed',
          reportYear: 2025,
          documentId: 1,
          errorCode: 'internal',
        },
      ],
      runScripts: [['done']],
    });
    server.override['GET /runs/501'] = [unreachable, unreachable, unreachable];
    const line = await screen.findByTestId('s3-failed');
    await screen.findByTestId('s3-result');
    fireEvent.click(
      within(line).getByRole('button', { name: t.progressDialog.retry }),
    );
    const dialog = await screen.findByTestId('s3-progress-dialog');
    await waitFor(() => expect(dialog.getAttribute('data-view')).toBe('lost'));
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.progressDialog.close }),
    );
    await screen.findByTestId('s3-unknown');
    expect(cardCount()).toBe(15);
    expect(
      within(screen.getByTestId('s3-done'))
        .getByRole('button', { name: t.result.upload })
        .hasAttribute('disabled'),
    ).toBe(true);
  });

  it('결과 있는 해 + 실패 file: 창을 닫으면 초점은 결과 [데이터 업로드]로(실패 줄 단추와 ref 를 나누지 않음 · GX3 검증 권고 3)', async () => {
    setup({
      runs: [
        base,
        {
          id: 6,
          status: 'failed',
          reportYear: 2025,
          documentId: 1,
          errorCode: 'object_missing',
        },
      ],
    });
    const line = await screen.findByTestId('s3-failed');
    await screen.findByTestId('s3-result');
    const resultUpload = within(screen.getByTestId('s3-done')).getByRole(
      'button',
      { name: t.result.upload },
    );
    fireEvent.click(
      within(line).getByRole('button', { name: t.result.upload }),
    );
    const category = await screen.findByTestId('s3-category-dialog');
    fireEvent.click(
      within(category).getByRole('button', { name: t.categoryDialog.cancel }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('s3-category-dialog')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(resultUpload));
  });
});
