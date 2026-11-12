// @vitest-environment jsdom
// S2 단추 둘 · S5 다운로드 · S4 양식 받기 · S4 일괄 업로드(밴드 W12-5 ②③ — 발주서 §3 #1~#7). 진짜 입력 실어댑터 + 가짜 온실가스 서버, 값은 지어낸 것.
//   올리기 답은 심는 답(uploadAnswers)으로 꺼낸다. 「올리는 중」만 포트의 upload 를 약속으로 감싼다(폴링·타이머와 겨루지 않게 — 답을 시험이 푼다).
import { useState } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { GhgEntryPort } from '../../../entities/ghg/api/index.ts';
import {
  FAKE_EXPORT_NAME,
  FAKE_TEMPLATE_NAME,
  fakeBranch,
  fakeEntryOptions,
  fakeGhgServer,
  json,
  portsOf,
  refusal,
  unreachable,
} from '../../../entities/ghg/api/testing.ts';
import type { FakeGhgServerOptions } from '../../../entities/ghg/api/testing.ts';
import { GHG_TEXT } from '../../../entities/ghg/config/text.ts';
import { ENTRY_UPLOAD_MAX_BYTES } from '../../../entities/ghg/model/index.ts';
import { InventoryScreen } from './InventoryScreen.tsx';

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

const bulk = GHG_TEXT.inventory.bulk;
const YEARS = [2026, 2025, 2024, 2023, 2022];
const ROWS = 'GET /inventory/scope12/rows';
const UPLOADS = 'POST /inventory/scope12/years/2025/uploads';
const EXPORT = 'GET /inventory/scope12/years/2025/export';
const TEMPLATE = 'GET /inventory/scope12/years/2025/template';
const ok = (filled: number, rest: Partial<Record<string, number>> = {}) =>
  json(200, { added: 0, filled, unchanged: 0, unresolved: 0, ...rest });
const invalid = (fields: Record<string, string[]>) => () =>
  refusal(422, 'INVALID_UPLOAD', fields);

function setup(
  options: FakeGhgServerOptions = {},
  { operator = false, year = 2025, wrap = (port: GhgEntryPort) => port } = {},
) {
  const server = fakeGhgServer({
    thisYear: 2026,
    ...fakeEntryOptions(),
    ...options,
  });
  const ports = portsOf(server);
  const entry = wrap(ports.entry);
  const save = vi.fn();
  function Harness() {
    const [current, setCurrent] = useState(year);
    return (
      <InventoryScreen
        port={entry}
        organization={ports.port}
        year={current}
        years={YEARS}
        operator={operator}
        onYear={setCurrent}
        onIndexSettings={() => {}}
        save={save}
      />
    );
  }
  render(<Harness />);
  return { server, save };
}

const button = (name: string) => screen.findByRole('button', { name });
const readRows = (server: ReturnType<typeof fakeGhgServer>) =>
  server.count(ROWS);

async function openUpload() {
  fireEvent.click(await button(bulk.uploadOpen));
  return screen.findByTestId('entry-upload');
}

const xlsx = (size = 3, name = '지어낸.xlsx') => {
  const file = new File([new Uint8Array(1)], name);
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

function choose(dialog: HTMLElement, file: File) {
  const input = dialog.querySelector<HTMLInputElement>('input[type="file"]')!;
  fireEvent.change(input, { target: { files: [file] } });
}

async function send(dialog: HTMLElement, file = xlsx()) {
  choose(dialog, file);
  const submit = within(dialog).getByTestId('entry-upload-submit');
  await waitFor(() => expect(submit).toHaveProperty('disabled', false));
  fireEvent.click(submit);
}

describe('#1 S2 단추', () => {
  it.each([false, true])('두 역할 다 보임(operator=%s)', async (operator) => {
    setup({}, { operator });
    expect(await button(bulk.uploadOpen)).toHaveProperty('disabled', false);
    expect(await button(bulk.downloadOpen)).toHaveProperty('disabled', false);
  });

  it('빈 해: 자리는 남고 둘 다 꺼짐', async () => {
    setup({}, { year: 2024 });
    await screen.findByTestId('inventory-empty');
    expect(screen.queryByRole('dialog')).toBeNull(); // S12-02a: 초기 창 없음
    expect(await button(bulk.uploadOpen)).toHaveProperty('disabled', true);
    expect(await button(bulk.downloadOpen)).toHaveProperty('disabled', true);
  });

  it('검색 0 건에도 켜져 있음(base 로 본다)', async () => {
    setup();
    await screen.findByTestId('inventory-row-20');
    fireEvent.change(screen.getByLabelText(GHG_TEXT.inventory.searchLabel), {
      target: { value: '없는 이름' },
    });
    await screen.findByTestId('inventory-search-empty');
    expect(await button(bulk.uploadOpen)).toHaveProperty('disabled', false);
  });

  it('닫히면 초점은 연 단추로', async () => {
    setup();
    const opener = await button(bulk.downloadOpen);
    fireEvent.click(opener);
    const dialog = await screen.findByTestId('entry-download');
    fireEvent.click(within(dialog).getByRole('button', { name: '확인' }));
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });
});

describe('#2 S5 다운로드', () => {
  async function openDownload() {
    fireEvent.click(await button(bulk.downloadOpen));
    return screen.findByTestId('entry-download');
  }

  it('줄 셋의 scope · 서버 이름으로 저장 · 보고서 무리 0', async () => {
    const { server, save } = setup();
    const dialog = await openDownload();
    expect(dialog.textContent).not.toContain('보고서');
    expect(dialog.textContent).not.toContain('pdf');
    // 줄 아이콘(밴드 DB2 ③ — e6 ⑥): ReportXlsxIcon 48 판 · 「XLSX」 글자 패스 · 초록 글자 클래스 뗌.
    for (const scope of ['all', '1', '2']) {
      const icon = within(dialog)
        .getByTestId(`entry-download-${scope}`)
        .querySelector('svg')!;
      expect(icon.getAttribute('viewBox')).toBe('0 0 48 48');
      expect(icon.querySelector('[data-glyphs="XLSX"]')).not.toBeNull();
      expect(icon.getAttribute('class')).not.toContain('text-support-success');
    }
    for (const [index, scope] of (['all', '1', '2'] as const).entries()) {
      fireEvent.click(within(dialog).getByTestId(`entry-download-${scope}`));
      await waitFor(() => expect(save).toHaveBeenCalledTimes(index + 1));
      expect(server.calls.at(-1)!.query.get('scope')).toBe(scope);
    }
    expect(save.mock.calls[0]![1]).toBe(FAKE_EXPORT_NAME);
  });

  it('두 번 눌러도 요청 한 번', async () => {
    const { server, save } = setup();
    const line = within(await openDownload()).getByTestId('entry-download-all');
    fireEvent.click(line);
    fireEvent.click(line);
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(server.count(EXPORT)).toBe(1);
  });

  it('갈래 글: 404 · 끊김 · 회사 거절(운영 관리자 글) — 그 줄 아래', async () => {
    const { server } = setup({}, { operator: true });
    const dialog = await openDownload();
    const line = within(dialog).getByTestId('entry-download-1');
    server.override[EXPORT] = [
      () => refusal(404, 'NOT_FOUND'),
      unreachable,
      () => refusal(400, 'COMPANY_AMBIGUOUS'),
    ];
    const problem = () => screen.findByTestId('entry-download-problem-1');
    fireEvent.click(line);
    expect((await problem()).textContent).toBe(bulk.download.notFound);
    fireEvent.click(line);
    await waitFor(async () =>
      expect((await problem()).textContent).toBe(bulk.download.failed),
    );
    fireEvent.click(line);
    await waitFor(async () =>
      expect((await problem()).textContent).toBe(
        GHG_TEXT.companyOperator.ambiguous,
      ),
    );
  });
});

describe('#3 양식 받기', () => {
  async function openTemplate() {
    const upload = await openUpload();
    const opener = within(upload).getByTestId('entry-template-open');
    fireEvent.click(opener);
    return { opener, dialog: await screen.findByTestId('entry-template') };
  }
  const next = (dialog: HTMLElement) =>
    within(dialog).getByTestId('entry-template-next');
  async function toSites(dialog: HTMLElement, scope = '1') {
    fireEvent.change(within(dialog).getByTestId('entry-template-scope'), {
      target: { value: scope },
    });
    fireEvent.click(next(dialog));
    return (await within(dialog).findByTestId(
      'entry-template-site',
    )) as HTMLSelectElement;
  }

  it('안 고르면 [다음] 꺼짐 · ①②→ siteId 정수로 받고 닫힘 · 초점은 [양식 다운로드]', async () => {
    const { server, save } = setup();
    const { dialog, opener } = await openTemplate();
    expect(next(dialog)).toHaveProperty('disabled', true);
    const site = await toSites(dialog);
    await waitFor(() => expect(site).toHaveProperty('disabled', false));
    expect(next(dialog)).toHaveProperty('disabled', true);
    fireEvent.change(site, { target: { value: '2' } });
    fireEvent.click(next(dialog));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0]![1]).toBe(FAKE_TEMPLATE_NAME);
    expect(Object.fromEntries(server.calls.at(-1)!.query)).toEqual({
      scope: '1',
      siteId: '2',
    });
    await waitFor(() =>
      expect(screen.queryByTestId('entry-template')).toBeNull(),
    );
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it('사업장: 둘째 쪽까지 싣고(21 곳+) 꺼진 사업장은 뺀다', async () => {
    const base = fakeEntryOptions();
    const more = Array.from({ length: 20 }, (_, index) =>
      fakeBranch(100 + index, `지어낸 사업장 ${index}`),
    );
    const off = fakeBranch(200, '지어낸 꺼진 사업장', {
      inventoryEnabled: false,
    });
    setup({ branches: [...base.branches!, ...more, off] });
    const { dialog } = await openTemplate();
    const site = await toSites(dialog);
    await waitFor(() => expect(site.options.length).toBeGreaterThan(21));
    const names = [...site.options].map((option) => option.textContent);
    expect(names).toContain('지어낸 사업장 19');
    expect(names).not.toContain('지어낸 꺼진 사업장');
  });

  it('둘째 쪽 읽기가 끊기면 일부를 보이지 않고 글 · [다음] 꺼짐', async () => {
    const { server } = setup();
    const { dialog } = await openTemplate();
    server.override['GET /branches'] = unreachable;
    await toSites(dialog);
    expect(
      (await screen.findByTestId('entry-template-problem')).textContent,
    ).toBe(bulk.template.sitesFailed);
    expect(next(dialog)).toHaveProperty('disabled', true);
  });

  it('켠 사업장 0 이면 글 · [다음] 꺼짐', async () => {
    const { server } = setup();
    const { dialog } = await openTemplate();
    server.override['GET /branches'] = () =>
      json(200, {
        count: 0,
        totalPages: 1,
        page: 1,
        pageSize: 20,
        hasNext: false,
        hasPrevious: false,
        results: [],
      });
    await toSites(dialog);
    expect(
      (await screen.findByTestId('entry-template-problem')).textContent,
    ).toBe(bulk.template.sitesEmpty);
  });

  it('갈래 글: 404 · 끊김 — 창 그대로', async () => {
    const { server, save } = setup();
    const { dialog } = await openTemplate();
    const site = await toSites(dialog);
    await waitFor(() => expect(site).toHaveProperty('disabled', false));
    fireEvent.change(site, { target: { value: '2' } });
    server.override[TEMPLATE] = [() => refusal(404, 'NOT_FOUND'), unreachable];
    const problem = () => screen.findByTestId('entry-template-problem');
    fireEvent.click(next(dialog));
    expect((await problem()).textContent).toBe(bulk.template.notFound);
    fireEvent.click(next(dialog));
    await waitFor(async () =>
      expect((await problem()).textContent).toBe(bulk.template.failed),
    );
    expect(save).not.toHaveBeenCalled();
  });
});

describe('#3b 양식 창을 닫은 뒤 늦은 답', () => {
  it('받는 중 닫으면 답이 와도 저장하지 않는다', async () => {
    let finish = () => {};
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    let answered = () => {};
    const done = new Promise<void>((resolve) => {
      answered = resolve;
    });
    const { save } = setup(
      {},
      {
        wrap: (port) => ({
          ...port,
          template: async (year, scope, siteId) => {
            await gate;
            const out = await port.template(year, scope, siteId);
            answered();
            return out;
          },
        }),
      },
    );
    const upload = await openUpload();
    fireEvent.click(within(upload).getByTestId('entry-template-open'));
    const dialog = await screen.findByTestId('entry-template');
    const next = within(dialog).getByTestId('entry-template-next');
    fireEvent.change(within(dialog).getByTestId('entry-template-scope'), {
      target: { value: '1' },
    });
    fireEvent.click(next);
    const site = await within(dialog).findByTestId('entry-template-site');
    await waitFor(() => expect(site).toHaveProperty('disabled', false));
    fireEvent.change(site, { target: { value: '2' } });
    fireEvent.click(next);
    fireEvent.click(within(dialog).getByRole('button', { name: '취소' }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-template')).toBeNull(),
    );
    finish();
    await done;
    await act(async () => {
      await Promise.resolve();
    });
    expect(save).not.toHaveBeenCalled();
  });
});

describe('#4 S4 파일', () => {
  const problem = () => screen.queryByTestId('entry-upload-problem');
  const submit = (dialog: HTMLElement) =>
    within(dialog).getByTestId('entry-upload-submit');

  it('파일 없으면 꺼짐 · 딱 상한은 지나감', async () => {
    setup();
    const dialog = await openUpload();
    // 양식 상자 아이콘(밴드 DB2 ③ — e6 ⑥): MyIcons XlsIcon(28 판 · 「XLS」 띠) size-7 초록.
    const template = within(dialog).getByText(
      bulk.upload.templateTitle,
    ).previousElementSibling!;
    expect(template.getAttribute('viewBox')).toBe('0 0 28 28');
    expect(template.querySelector('rect')).not.toBeNull();
    expect(template.getAttribute('class')).toContain('size-7');
    expect(template.getAttribute('class')).toContain('text-support-success');
    expect(submit(dialog)).toHaveProperty('disabled', true);
    choose(dialog, xlsx(ENTRY_UPLOAD_MAX_BYTES));
    await waitFor(() =>
      expect(submit(dialog)).toHaveProperty('disabled', false),
    );
    expect(problem()).toBeNull();
  });

  it('상한 + 1 · .xls 는 거절 글 · 요청 0', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    choose(dialog, xlsx(ENTRY_UPLOAD_MAX_BYTES + 1));
    await waitFor(() => expect(problem()?.textContent).toBe(bulk.upload.size));
    expect(submit(dialog)).toHaveProperty('disabled', true);
    choose(dialog, xlsx(3, '지어낸.xls'));
    await waitFor(() => expect(problem()?.textContent).toBe(bulk.upload.type));
    expect(server.count(UPLOADS)).toBe(0);
  });

  it('안내·까닭 글의 상한이 ENTRY_UPLOAD_MAX_BYTES 와 같다(20MB — MARC-ENT-593, Scope 3 창의 꼴)', () => {
    const mb = ENTRY_UPLOAD_MAX_BYTES / (1024 * 1024);
    expect(bulk.upload.formats).toBe(`${mb}MB 이내 첨부 가능 파일 형식: xlsx`);
    expect(bulk.upload.size).toBe(`${mb}MB 이하 파일만 올릴 수 있어요`);
  });

  it('파일을 바꾸면 글을 지운다', async () => {
    setup({ uploadAnswers: [invalid({ '월!C3': ['지어낸 칸 글'] })] });
    const dialog = await openUpload();
    await send(dialog);
    await screen.findByTestId('entry-upload-lines');
    fireEvent.click(within(dialog).getByRole('button', { name: /지우기/ }));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-upload-lines')).toBeNull(),
    );
  });
});

describe('GX2 L-7 둘째 파일', () => {
  it('파일이 있는데 둘째 파일을 고르면 앞 파일을 바꿔 끼움 · 앞 오류 글 지움 · 개수 거절 글 0 · 올리면 둘째 파일', async () => {
    const { server } = setup({
      uploadAnswers: [
        invalid({ '월!C3': ['지어낸 칸 글'] }),
        () => ok(3, { added: 1 }),
      ],
    });
    const dialog = await openUpload();
    await send(dialog, new File([new Uint8Array([1])], '지어낸-앞.xlsx'));
    await screen.findByTestId('entry-upload-lines');
    choose(dialog, new File([new Uint8Array([9, 9])], '지어낸-뒤.xlsx'));
    await waitFor(() =>
      expect(screen.queryByTestId('entry-upload-lines')).toBeNull(),
    );
    expect(dialog.textContent).toContain('지어낸-뒤.xlsx');
    expect(dialog.textContent).not.toContain('지어낸-앞.xlsx');
    expect(dialog.textContent).not.toContain('개까지');
    const submit = within(dialog).getByTestId('entry-upload-submit');
    await waitFor(() => expect(submit).toHaveProperty('disabled', false));
    fireEvent.click(submit);
    await waitFor(() => expect(server.count(UPLOADS)).toBe(2));
    const sent = server.calls.filter((call) => call.bytes);
    expect([...sent.at(-1)!.bytes!]).toEqual([9, 9]);
  });
});

describe('#5 S4 성공', () => {
  it('바이트 그대로 · load 한 번 · 창 닫음 · 알림 줄 · 초점 복귀', async () => {
    const { server } = setup({ uploadAnswers: [() => ok(3, { added: 1 })] });
    const dialog = await openUpload();
    const before = readRows(server);
    const file = new File([new Uint8Array([7, 7, 7])], '지어낸.xlsx');
    await send(dialog, file);
    const line = await screen.findByTestId('inventory-uploaded');
    expect(line.textContent).toBe(bulk.filled(3));
    expect(line.getAttribute('role')).toBe('status');
    expect(screen.queryByTestId('entry-upload')).toBeNull();
    expect([...server.calls.find((c) => c.bytes)!.bytes!]).toEqual([7, 7, 7]);
    await waitFor(() => expect(readRows(server)).toBe(before + 1));
    const opener = await button(bulk.uploadOpen);
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it('unresolved 덧글에 「이번」·「올린 행 중」 없음', async () => {
    setup({ uploadAnswers: [() => ok(1, { unresolved: 4 })] });
    await send(await openUpload());
    const text = (await screen.findByTestId('inventory-uploaded')).textContent!;
    expect(text).toContain(bulk.unresolved(4));
    expect(text).not.toContain('이번');
    expect(text).not.toContain('올린 행');
  });

  it('연도를 바꾸면 알림 줄을 걷고, 다음 올리기를 열어도 걷는다', async () => {
    setup({ uploadAnswers: [() => ok(1), () => ok(1)] });
    await send(await openUpload());
    await screen.findByTestId('inventory-uploaded');
    fireEvent.change(
      screen.getByRole('combobox', { name: GHG_TEXT.inventory.yearLabel }),
      { target: { value: '2023' } },
    );
    await waitFor(() =>
      expect(screen.queryByTestId('inventory-uploaded')).toBeNull(),
    );
  });

  it('다음 올리기를 열면 걷는다', async () => {
    setup({ uploadAnswers: [() => ok(1)] });
    await send(await openUpload());
    await screen.findByTestId('inventory-uploaded');
    await openUpload();
    expect(screen.queryByTestId('inventory-uploaded')).toBeNull();
  });
});

describe('#6 S4 답의 갈래', () => {
  const problem = () => screen.findByTestId('entry-upload-problem');

  it('값 찬 칸 0(넷 다 0): 창 그대로 · load 안 함', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    const before = readRows(server);
    await send(dialog);
    expect((await problem()).textContent).toBe(bulk.upload.noValues);
    expect(screen.getByTestId('entry-upload')).toBeTruthy();
    expect(readRows(server)).toBe(before);
  });

  it('같은 값만: 창 그대로 · 그 글 · 알림 줄 0', async () => {
    setup({ uploadAnswers: [() => ok(0, { unchanged: 5 })] });
    await send(await openUpload());
    expect((await problem()).textContent).toBe(bulk.upload.sameValues);
    expect(screen.queryByTestId('inventory-uploaded')).toBeNull();
  });

  it.each([
    [
      '#N/A 칸(시트 이름 없음)',
      'C7 칸을 읽지 못했어요 — 값을 고쳐 다시 올려 주세요',
    ],
    ['일의 양', '한 번에 올리기에 줄이 많아요 — 나눠서 올려 주세요'],
    ['그 밖 file', '엑셀 파일(.xlsx)을 읽지 못했어요'],
  ])('%s: 서버 글 그대로 · 자리 지어내지 않음 · 창 유지', async (_, text) => {
    setup({ uploadAnswers: [invalid({ file: [text] })] });
    await send(await openUpload());
    const lines = await screen.findByTestId('entry-upload-lines');
    expect(within(lines).getByRole('list').textContent).toBe(text);
    expect(lines.textContent).not.toContain('시트');
    expect(screen.getByTestId('entry-upload')).toBeTruthy();
  });

  it('줄·칸 오류: 머리 한 줄 · 받은 차례 · 「<시트> 시트 <칸>」 · more 맨 끝 · 파일은 그대로', async () => {
    setup({
      uploadAnswers: [
        invalid({
          '년도!A2': ['지어낸 줄 글'],
          '월!C3': ['지어낸 칸 글'],
          more: ['그 밖에 1개가 더 있어요'],
        }),
      ],
    });
    const dialog = await openUpload();
    await send(dialog);
    const lines = await screen.findByTestId('entry-upload-lines');
    expect(lines.getAttribute('role')).toBe('alert');
    expect(lines.textContent).toContain(bulk.upload.linesHead);
    expect(
      within(lines)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      '년도 시트 A2 지어낸 줄 글',
      '월 시트 C3 지어낸 칸 글',
      '그 밖에 1개가 더 있어요',
    ]);
    expect(within(dialog).getByTestId('entry-upload-submit')).toHaveProperty(
      'disabled',
      false,
    );
  });

  it('413 크기 글 · 회사 거절 글', async () => {
    setup({
      uploadAnswers: [
        () => refusal(413, 'BODY_TOO_LARGE'),
        () => refusal(400, 'COMPANY_AMBIGUOUS'),
      ],
    });
    const dialog = await openUpload();
    await send(dialog);
    expect((await problem()).textContent).toBe(bulk.upload.size);
    fireEvent.click(within(dialog).getByTestId('entry-upload-submit'));
    await waitFor(async () =>
      expect((await problem()).textContent).toBe(GHG_TEXT.company.ambiguous),
    );
  });

  it.each([
    ['잠김 409', () => refusal(409, 'LOCKED'), bulk.upload.locked],
    ['없음 404', () => refusal(404, 'NOT_FOUND'), bulk.upload.notFound],
  ])('%s: 글 · 표를 다시 읽음 · 창 유지', async (_, answer, text) => {
    const { server } = setup({ uploadAnswers: [answer] });
    const dialog = await openUpload();
    const before = readRows(server);
    await send(dialog);
    expect((await problem()).textContent).toBe(text);
    await waitFor(() => expect(readRows(server)).toBe(before + 1));
    expect(screen.getByTestId('entry-upload')).toBeTruthy();
  });
});

describe('#6c 파일을 못 읽음(검증 B1)', () => {
  it('요청 0 · load 안 함 · 파일을 비움 · 다시 고르라는 글 · 「결과를 확인하지 못했어요」 없음', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    const before = readRows(server);
    const broken = xlsx();
    broken.arrayBuffer = () => Promise.reject(new Error('지어낸 읽기 실패'));
    await send(dialog, broken);
    const problem = await screen.findByTestId('entry-upload-problem');
    expect(problem.textContent).toBe(bulk.upload.unreadable);
    expect(problem.textContent).not.toContain('결과');
    expect(server.count(UPLOADS)).toBe(0);
    expect(readRows(server)).toBe(before);
    const submit = within(dialog).getByTestId('entry-upload-submit');
    await waitFor(() => expect(submit).toHaveProperty('disabled', true));
    expect(dialog.textContent).not.toContain('지어낸.xlsx');
    expect(screen.getByTestId('entry-upload')).toBeTruthy();
  });
});

describe('#6b 올린 창 뒤 — S12-02a 초기 모달 없음', () => {
  it('404 뒤 다시 읽어 해가 비어도 창은 올리기 창 하나 — 닫으면 빈 상태만(초기 모달 0)', async () => {
    const { server } = setup();
    const dialog = await openUpload();
    server.uploadAnswers.push(() => {
      server.override[ROWS] = () =>
        json(200, {
          year: 2025,
          years: [2023, 2024, 2025],
          decimals: 2,
          unit: 'tCO2-eq',
          configured: false,
          scopes: [],
        });
      return refusal(404, 'NOT_FOUND');
    });
    await send(dialog);
    await screen.findByTestId('entry-upload-problem');
    await waitFor(() =>
      expect(screen.queryByTestId('inventory-empty')).not.toBeNull(),
    );
    expect(screen.queryAllByRole('dialog')).toHaveLength(1); // 올리기 창 하나뿐(S12-02a — 초기 세팅 창 0)
    fireEvent.click(within(dialog).getByRole('button', { name: '취소' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(screen.getByTestId('inventory-empty')).toBeTruthy();
  });
});

describe('#7 ★ failed — 결과를 모름', () => {
  const problem = () => screen.findByTestId('entry-upload-problem');

  it('끊김: 창 유지 · 「실패」 글 없음 · load 한 번 · 표에 새 값 · 다시 올리기 됨', async () => {
    const options = fakeEntryOptions();
    const { server } = setup({
      ...options,
      uploadAnswers: [
        () => {
          options.entryValues!['20']!['2025'] = '99.5';
          return unreachable();
        },
        () => ok(0, { unchanged: 1 }),
      ],
    });
    const dialog = await openUpload();
    const before = readRows(server);
    await send(dialog);
    const text = (await problem()).textContent!;
    expect(text).toBe(bulk.upload.unknownRead);
    expect(text).not.toContain('실패');
    expect(text).not.toContain('못 올렸');
    expect(readRows(server)).toBe(before + 1);
    expect(screen.getByTestId('inventory-tables').textContent).toContain(
      '99.5',
    );
    expect(screen.queryByTestId('inventory-uploaded')).toBeNull();
    const submit = within(dialog).getByTestId('entry-upload-submit');
    await waitFor(() => expect(submit).toHaveProperty('disabled', false));
    fireEvent.click(submit);
    await waitFor(async () =>
      expect((await problem()).textContent).toBe(bulk.upload.sameValues),
    );
    expect(server.count(UPLOADS)).toBe(2);
  });

  it('5xx·꼴 틀림도 같은 글', async () => {
    setup({
      uploadAnswers: [
        () => refusal(503, 'SERVICE_UNAVAILABLE'),
        () => json(200, { added: 1, filled: 1, unchanged: 0, skipped: 0 }),
      ],
    });
    const dialog = await openUpload();
    await send(dialog);
    expect((await problem()).textContent).toBe(bulk.upload.unknownRead);
  });

  it('다시 읽기도 실패면 그 글 · 화면에 reloadFailed 한 줄', async () => {
    const { server } = setup({ uploadAnswers: [unreachable] });
    const dialog = await openUpload();
    server.override[ROWS] = unreachable;
    await send(dialog);
    const text = (await problem()).textContent!;
    expect(text).toBe(bulk.upload.unknownUnread);
    expect(text).not.toContain('실패');
    expect(screen.getByTestId('inventory-notice').textContent).toContain(
      GHG_TEXT.inventory.reloadFailed,
    );
  });

  it('올리는 중: Esc·[취소] 로 안 닫힘 · 두 번 눌러 요청 한 번 · 답이 오면 끝남', async () => {
    let finish = () => {};
    const gate = new Promise<void>((resolve) => {
      finish = resolve;
    });
    const upload = vi.fn();
    const { server } = setup(
      { uploadAnswers: [() => ok(2)] },
      {
        wrap: (port) => ({
          ...port,
          upload: async (year, file) => {
            upload();
            await gate;
            return port.upload(year, file);
          },
        }),
      },
    );
    const dialog = await openUpload();
    await send(dialog);
    const submit = within(dialog).getByTestId('entry-upload-submit');
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
    fireEvent.submit(submit.closest('form')!);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(within(dialog).getByRole('button', { name: '취소' })).toHaveProperty(
      'disabled',
      true,
    );
    expect(screen.getByTestId('entry-upload')).toBeTruthy();
    expect(upload).toHaveBeenCalledTimes(1);
    finish();
    await screen.findByTestId('inventory-uploaded');
    expect(server.count(UPLOADS)).toBe(1);
  });
});
