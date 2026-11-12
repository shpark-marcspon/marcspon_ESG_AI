// @vitest-environment jsdom
// DV-02 새 검증 화면 시험(밴드 DV2a ② — 발주서 §3-2 9). 저장소는 가짜 데이터 검증 서버를 앞에 둔 실어댑터(목 0).
//   입력 JSON 은 시험 안에서 짓는다(model/testing.ts — 「가상건설」 꼴, 저장소에 .json 0). 키트 Tabs(radix)는 mouseDown 으로 누른다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';

import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest';

import {
  FAKE_TEMPLATE_NAME,
  edkRejected,
  fakeDataverifyServer,
  fakeEdkReadOk,
  json,
  refusal,
  serverStoreOf,
  unreachable,
} from '../../../entities/dataverify/api/testing.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  OPTIONS_MAX_OCTETS,
  buildInput,
  buildOptions,
  fileSource,
  pyJsonOctets,
} from '../../../entities/dataverify/model/index.ts';
import type { EdkData } from '../../../entities/dataverify/model/index.ts';
import {
  FAKE_COMPANY,
  edkData,
  edkItem,
  fakeInput,
} from '../../../entities/dataverify/model/testing.ts';
import { NewScreen } from './NewScreen.tsx';

afterEach(cleanup);

const words = DV_TEXT.newCheck;
const GOOD = JSON.stringify(edkData());
/** 2026-10-23 — 보고연도 고르기 2021~2026, 기본 2025. */
const NOW = () => new Date(2026, 9, 23);

function setup() {
  const server = fakeDataverifyServer();
  const store = serverStoreOf(server, { newKey: keys() });
  const onStarted = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewScreen
      store={store}
      now={NOW}
      onStarted={onStarted}
      onCancel={onCancel}
    />,
  );
  return { server, onStarted, onCancel };
}

/** 차례대로 지은 열쇠(…0001, …0002). */
function keys() {
  let n = 0;
  return () => `00000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
}

async function pick(text: string | Uint8Array, name = 'edk.json') {
  const input = document.querySelector<HTMLInputElement>(
    '[data-card="data"] input[type="file"]',
  )!;
  await act(async () => {
    fireEvent.change(input, { target: { files: [new File([text], name)] } });
  });
  // File.text() 를 기다린다.
  await act(async () => {});
}

async function paste(text: string) {
  fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabPaste }));
  const area = await screen.findByRole('textbox', { name: words.pasteLabel });
  fireEvent.change(area, { target: { value: text } });
}

function fillCompany({
  name = FAKE_COMPANY.name,
  sasb = FAKE_COMPANY.sasbIndustry,
  topics = [...FAKE_COMPANY.materialTopics],
}: { name?: string; sasb?: string; topics?: readonly string[] } = {}) {
  fireEvent.change(screen.getByLabelText(words.name), {
    target: { value: name },
  });
  fireEvent.change(screen.getByLabelText(words.sasb), {
    target: { value: sasb },
  });
  const topic = screen.getByRole('textbox', { name: words.topicAdd });
  for (const each of topics) {
    fireEvent.change(topic, { target: { value: each } });
    fireEvent.keyDown(topic, { key: 'Enter' });
  }
}

const startButton = () => screen.getByTestId('start');
const isOff = () => startButton().getAttribute('aria-disabled') === 'true';
const dataError = () => screen.queryByTestId('data-error')?.textContent;
const settle = () => act(async () => {});

describe('DV-02 데이터 넣기 · 파일', () => {
  it('.txt 는 JSON 파일만 글 · 파일 줄·미리 읽기 0 · 끔', async () => {
    setup();
    await pick(GOOD, 'edk.txt');
    expect(screen.getByText(words.errors.notJsonFile, { exact: false }));
    expect(screen.queryByTestId('file-meta')).toBeNull();
    expect(screen.queryByTestId('preview')).toBeNull();
    expect(isOff()).toBe(true);
  });

  it('256KiB+1 바이트 파일은 크기 글(읽지 않는다)', async () => {
    setup();
    await pick(new Uint8Array(OPTIONS_MAX_OCTETS + 1).fill(32));
    expect(screen.getByText(words.errors.fileTooLarge, { exact: false }));
    expect(screen.queryByTestId('preview')).toBeNull();
    expect(isOff()).toBe(true);
  });

  it('JSON 아님·꼴 틀림(항목 열쇠 빠짐) 파일은 읽지 못함 글', async () => {
    setup();
    await pick('{"환경": [');
    expect(dataError()).toBe(words.errors.fileUnreadable);
    cleanup();
    setup();
    const item = edkItem();
    delete item.단위;
    await pick(JSON.stringify({ 환경: [item] }));
    expect(dataError()).toBe(words.errors.fileUnreadable);
    expect(isOff()).toBe(true);
  });

  it('좋은 파일 → 파일 줄(테마·항목·크기 — 날짜 뺌)·미리 읽기 줄(환경 항목·핵심·연도)', async () => {
    setup();
    await pick(GOOD);
    const bytes = new TextEncoder().encode(GOOD).length;
    expect(screen.getByTestId('file-meta').textContent).toBe(
      words.fileLine(3, 4, `${Math.max(1, Math.round(bytes / 1024))}KB`),
    );
    expect(screen.getByTestId('preview').textContent).toBe(
      words.preview(2, 1, '2022~2024년'),
    );
    expect(dataError()).toBeUndefined();
  });

  it('파일 칸 aria(DV2d): 크기 넘음·읽지 못함·이름 꼴 밖 = aria-invalid·aria-describedby 가 보이는 오류 글 id · 오류 없으면 둘 다 0', async () => {
    const zone = () =>
      document.querySelector<HTMLElement>(
        '[data-card="data"] div[role="button"]',
      )!;
    const cases: [string, () => Promise<void>, string][] = [
      [
        // 파일 자체는 256KiB 안이나 기업 칸을 넣은 options 셈이 넘는 갈래(이 화면의 크기 글 — 256KiB+1 파일은 키트 칸이 먼저 거른다).
        'too_large',
        async () => {
          const dataOf = (memo: string) => ({
            환경: [edkItem({ 메모: memo })],
          });
          const octetsOf = (memo: string) =>
            pyJsonOctets(
              buildOptions(
                buildInput(FAKE_COMPANY, dataOf(memo) as EdkData),
                fileSource('edk.json'),
              ),
            );
          const fill = OPTIONS_MAX_OCTETS + 1 - octetsOf('');
          await pick(JSON.stringify(dataOf('x'.repeat(fill))));
          fillCompany();
        },
        words.errors.fileTooLarge,
      ],
      ['unreadable', () => pick('{"환경": ['), words.errors.fileUnreadable],
      ['bad_name', () => pick(GOOD, 'a/b.json'), words.errors.badName],
    ];
    for (const [name, choose, text] of cases) {
      setup();
      expect(zone().hasAttribute('aria-invalid'), name).toBe(false);
      expect(zone().hasAttribute('aria-describedby'), name).toBe(false);
      await choose();
      const shown = screen.getByTestId('data-error');
      expect(shown.textContent, name).toBe(text);
      expect(zone().getAttribute('aria-invalid'), name).toBe('true');
      expect(shown.id, name).not.toBe('');
      expect(zone().getAttribute('aria-describedby'), name).toBe(shown.id);
      cleanup();
    }
    setup();
    await pick(GOOD);
    expect(screen.queryByTestId('data-error')).toBeNull();
    expect(zone().hasAttribute('aria-invalid')).toBe(false);
    expect(zone().hasAttribute('aria-describedby')).toBe(false);
  });

  it('「환경」 0 항목이어도 막지 않는다(서버가 경고 결과)', async () => {
    const { server } = setup();
    await pick(JSON.stringify({ 사회: [edkItem({ 테마: '사회' })] }));
    expect(screen.getByTestId('preview').textContent).toBe(
      words.preview(0, 0, DV_TEXT.dash),
    );
    fillCompany();
    expect(isOff()).toBe(false);
    fireEvent.click(startButton());
    await settle();
    expect(server.count('POST /runs')).toBe(1);
  });

  it('파일은 256KiB 안이어도 보낼 options 의 서버 셈이 넘으면 크기 글 · 끔(요청 0)', async () => {
    const { server } = setup();
    // 빈 기업 칸으로 지은 options(source 까지 — DV2b)의 서버 셈이 상한 −20 이 되게 메모를 채운다(기업 칸을 넣으면 넘는다).
    const dataOf = (memo: string) => ({ 환경: [edkItem({ 메모: memo })] });
    const empty = {
      name: '',
      sasbIndustry: '',
      materialTopics: [],
      reportingYear: '2025',
    };
    const octetsOf = (memo: string) =>
      pyJsonOctets(
        buildOptions(
          buildInput(empty, dataOf(memo) as EdkData),
          fileSource('edk.json'),
        ),
      );
    const fill = OPTIONS_MAX_OCTETS - 20 - octetsOf('');
    const text = JSON.stringify(dataOf('x'.repeat(fill)));
    expect(octetsOf('x'.repeat(fill))).toBe(OPTIONS_MAX_OCTETS - 20);
    expect(new TextEncoder().encode(text).length).toBeLessThanOrEqual(
      OPTIONS_MAX_OCTETS,
    );
    await pick(text);
    expect(dataError()).toBeUndefined();
    fillCompany();
    expect(dataError()).toBe(words.errors.fileTooLarge);
    expect(isOff()).toBe(true);
    fireEvent.click(startButton());
    await settle();
    expect(server.count('POST /runs')).toBe(0);
  });
});

describe('DV-02 데이터 넣기 · 붙여 넣기', () => {
  it('JSON 아님 → JSON 꼴 글 · 256KiB 넘음 → 크기 글 · 좋은 글 → 미리 읽기', async () => {
    setup();
    await paste('{"환경": [{"항목": ');
    expect(dataError()).toBe(words.errors.pasteNotJson);
    await paste(`"${'x'.repeat(OPTIONS_MAX_OCTETS)}"`);
    expect(dataError()).toBe(words.errors.pasteTooLarge);
    await paste(GOOD);
    expect(dataError()).toBeUndefined();
    expect(screen.getByTestId('preview').textContent).toBe(
      words.preview(2, 1, '2022~2024년'),
    );
  });

  it('붙여 넣은 글로 시작 — 본문은 module·launchKey·options{input} · data 는 읽은 그대로', async () => {
    const { server, onStarted } = setup();
    await paste(GOOD);
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    expect(onStarted).toHaveBeenCalledWith('30');
    const [post] = server.posts();
    const body = post!.body as {
      options: { input: Record<string, unknown>; source: unknown };
    };
    expect(Object.keys(body)).toEqual(['module', 'launchKey', 'options']);
    expect(Object.keys(body.options)).toEqual(['input', 'source']);
    expect(body.options.source).toEqual({ kind: 'paste' });
    expect(body.options.input).toEqual({
      schemaVersion: 'dataverify.input@1',
      company: {
        ...FAKE_COMPANY,
        materialTopics: [...FAKE_COMPANY.materialTopics],
      },
      data: edkData(),
    });
  });
});

describe('DV-02 기업 정보', () => {
  it('데이터 없음·읽는 중은 끔(눌러도 요청 0)', async () => {
    const { server } = setup();
    fillCompany();
    expect(isOff()).toBe(true);
    fireEvent.click(startButton());
    fireEvent.keyDown(startButton(), { key: 'Enter' });
    await settle();
    expect(server.count('POST /runs')).toBe(0);
  });

  it('빈 칸은 [검증 시작]을 누르면 글 셋(기업명·SASB·중대토픽)·첫 오류 칸 초점 · 요청 0(2e ⑤ — 켜 둔다)', async () => {
    const { server } = setup();
    await pick(GOOD);
    // 누르기 전에는 칸 글을 깔지 않는다.
    expect(screen.queryByText(words.required.name)).toBeNull();
    expect(isOff()).toBe(false);
    fireEvent.click(startButton());
    await settle();
    expect(screen.getByText(words.required.name)).toBeTruthy();
    expect(screen.getByText(words.required.sasb)).toBeTruthy();
    expect(screen.getByText(words.required.topics)).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByLabelText(words.name));
    expect(server.count('POST /runs')).toBe(0);
    // 빈칸만인 기업명은 빈 칸 · 기업명·SASB 를 채우면 첫 오류 칸은 중대토픽.
    fillCompany({ name: '   ', topics: [] });
    fireEvent.click(startButton());
    expect(screen.getByText(words.required.name)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(words.name), {
      target: { value: FAKE_COMPANY.name },
    });
    fireEvent.click(startButton());
    expect(screen.queryByText(words.required.name)).toBeNull();
    expect(document.activeElement).toBe(
      screen.getByRole('textbox', { name: words.topicAdd }),
    );
    await settle();
    expect(server.count('POST /runs')).toBe(0);
  });

  it('짝 없는 서로게이트가 든 칸은 누르면 그 칸 빨강·초점 · 요청 0(서버 utf-8 이 실패)', async () => {
    for (const [bad, label] of [
      [{ name: 'a\uD800' }, words.name],
      [{ sasb: 'b\uDC00' }, words.sasb],
      [{ topics: ['c\uD800'] }, words.topicAdd],
    ] as const) {
      const { server } = setup();
      await pick(GOOD);
      fillCompany(bad);
      fireEvent.click(startButton());
      await settle();
      const field = screen.getByLabelText(label);
      expect(field.getAttribute('aria-invalid'), label).toBe('true');
      expect(document.activeElement, label).toBe(field);
      expect(server.count('POST /runs')).toBe(0);
      cleanup();
    }
  });

  it('중대토픽: Enter 로 더하기(빈 글·같은 글은 그대로) · 빼기', async () => {
    setup();
    fillCompany({
      topics: ['기후변화 대응', ' ', '기후변화 대응', '안전보건'],
    });
    expect(
      screen.getAllByTestId('topic').map((chip) => chip.textContent),
    ).toEqual(['기후변화 대응', '안전보건']);
    fireEvent.click(
      screen.getByRole('button', { name: words.topicRemove('기후변화 대응') }),
    );
    expect(
      screen.getAllByTestId('topic').map((chip) => chip.textContent),
    ).toEqual(['안전보건']);
  });

  it('보고연도: 올해~올해−5, 기본 올해−1 · 고른 값이 실린다', async () => {
    const { server } = setup();
    const select = screen.getByLabelText(words.year) as HTMLSelectElement;
    expect(select.value).toBe('2025');
    expect([...select.options].map((option) => option.value)).toEqual([
      '2026',
      '2025',
      '2024',
      '2023',
      '2022',
      '2021',
    ]);
    fireEvent.change(select, { target: { value: '2023' } });
    await pick(GOOD);
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    const body = server.posts()[0]!.body as {
      options: { input: { company: { reportingYear: string } } };
    };
    expect(body.options.input.company.reportingYear).toBe('2023');
  });
});

describe('DV-02 [검증 시작]', () => {
  it('두 번 눌러도 한 번 → onStarted(runId) 한 번', async () => {
    const { server, onStarted } = setup();
    await pick(GOOD);
    fillCompany();
    expect(isOff()).toBe(false);
    fireEvent.click(startButton());
    fireEvent.click(startButton());
    await settle();
    expect(server.count('POST /runs')).toBe(1);
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(onStarted).toHaveBeenCalledWith('30');
  });

  it('거절·끊김 → 시작 실패 글 하나 · 넣은 내용 그대로 · 다시 누르면 같은 열쇠', async () => {
    const { server, onStarted } = setup();
    server.override['POST /runs'] = [
      () => refusal(500, 'INTERNAL'),
      unreachable,
    ];
    await pick(GOOD);
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    // 글이 든 alert 하나(양식 단추의 빈 라이브 영역은 세지 않는다 — DVX1 ② 감독 판단).
    expect(
      screen.getAllByRole('alert').filter((each) => each.textContent !== ''),
    ).toHaveLength(1);
    expect(screen.getByTestId('start-error').textContent).toBe(
      words.errors.startFailed,
    );
    expect((screen.getByLabelText(words.name) as HTMLInputElement).value).toBe(
      FAKE_COMPANY.name,
    );
    expect(screen.getByTestId('file-meta')).toBeTruthy();
    fireEvent.click(startButton());
    await settle();
    expect(screen.getByTestId('start-error')).toBeTruthy();
    fireEvent.click(startButton());
    await settle();
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(
      server.posts().map((call) => call.headers.get('Idempotency-Key')),
    ).toEqual([
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000001',
      '00000000-0000-4000-8000-000000000001',
    ]);
  });

  it('400 INVALID_OPTIONS: 셈이 상한 안이면 읽지 못함 글(message 를 읽지 않는다) · 시작 실패 글 0', async () => {
    const { server, onStarted } = setup();
    server.override['POST /runs'] = [() => refusal(400, 'INVALID_OPTIONS')];
    await pick(GOOD);
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    expect(dataError()).toBe(words.errors.fileUnreadable);
    expect(screen.queryByTestId('start-error')).toBeNull();
    expect(onStarted).not.toHaveBeenCalled();
  });

  it('[취소] → onCancel', () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole('button', { name: words.cancel }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe('DV-02 출처(DV2b) · DV2a 가지 리뷰 후속', () => {
  it('파일로 시작 → options.source = {kind:file, name: 고른 파일 이름 그대로}', async () => {
    const { server } = setup();
    await pick(GOOD, 'EDK_가상데이터 2025 (최종).json');
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    const [post] = server.posts();
    expect(
      (post!.body as { options: { source: unknown } }).options.source,
    ).toEqual({
      kind: 'file',
      name: 'EDK_가상데이터 2025 (최종).json',
    });
  });

  it('크기 셈에 source 가 든다 — 경계: source 없이 상한 −10 이면 파일 출처를 넣어 넘음 → 크기 글 · 끔(요청 0)', async () => {
    const { server } = setup();
    const dataOf = (memo: string) => ({ 환경: [edkItem({ 메모: memo })] });
    const octetsOf = (memo: string) =>
      pyJsonOctets(
        buildOptions(buildInput(FAKE_COMPANY, dataOf(memo) as EdkData)),
      );
    const fill = OPTIONS_MAX_OCTETS - 10 - octetsOf('');
    expect(octetsOf('x'.repeat(fill))).toBe(OPTIONS_MAX_OCTETS - 10);
    await pick(JSON.stringify(dataOf('x'.repeat(fill))));
    fillCompany();
    expect(dataError()).toBe(words.errors.fileTooLarge);
    expect(isOff()).toBe(true);
    fireEvent.click(startButton());
    await settle();
    expect(server.count('POST /runs')).toBe(0);
  });

  it('파일 이름이 서버 꼴 밖(제어 문자·`/`)이면 [검증 시작] 끔 · 요청 0', async () => {
    for (const name of ['edk\u0001.json', 'a/b.json']) {
      const { server } = setup();
      await pick(GOOD, name);
      fillCompany();
      expect(screen.getByTestId('preview')).toBeTruthy();
      expect(isOff(), name).toBe(true);
      fireEvent.click(startButton());
      await settle();
      expect(server.count('POST /runs'), name).toBe(0);
      cleanup();
    }
  });

  it('파일 이름이 꼴 밖(`/`·256자)이면 데이터 칸 오류 글(role=alert) · 끔 · 다시 고르거나 붙여 넣기로 바꾸면 사라짐 · 꼴 안 이름엔 글 0(DV2c)', async () => {
    for (const name of ['a/b.json', `${'a'.repeat(251)}.json`]) {
      setup();
      await pick(GOOD, 'edk.json');
      expect(dataError(), name).toBeUndefined();
      fireEvent.click(screen.getByRole('button', { name: /edk\.json/ }));
      await pick(GOOD, name);
      fillCompany();
      expect(dataError(), name).toBe(words.errors.badName);
      expect(screen.getByTestId('data-error').getAttribute('role')).toBe(
        'alert',
      );
      expect(isOff(), name).toBe(true);
      fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabPaste }));
      await settle();
      expect(dataError(), name).toBeUndefined();
      fireEvent.mouseDown(screen.getByRole('tab', { name: words.tabFile }));
      await settle();
      expect(dataError(), name).toBe(words.errors.badName);
      fireEvent.click(
        screen.getByRole('button', { name: new RegExp(words.removeFile) }),
      );
      await pick(GOOD, 'edk.json');
      expect(dataError(), name).toBeUndefined();
      expect(isOff(), name).toBe(false);
      cleanup();
    }
  });

  it('보내는 동안 [취소] 끔 · 끝나면 다시 켬', async () => {
    const { server, onCancel } = setup();
    let release: (response: Response) => void = () => {};
    server.override['POST /runs'] = () =>
      new Promise<Response>((done) => {
        release = done;
      });
    await pick(GOOD);
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    const cancel = screen.getByRole('button', { name: words.cancel });
    expect(
      cancel.hasAttribute('disabled') ||
        cancel.getAttribute('aria-disabled') === 'true',
    ).toBe(true);
    fireEvent.click(cancel);
    expect(onCancel).not.toHaveBeenCalled();
    await act(async () => release(refusal(500, 'INTERNAL')));
    fireEvent.click(screen.getByRole('button', { name: words.cancel }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('중대토픽 칸은 빈 칸 글을 aria-describedby 로 잇는다 · 첫 오류 칸 초점', async () => {
    setup();
    await pick(GOOD);
    fillCompany({ topics: [] });
    fireEvent.click(startButton());
    await settle();
    const topic = screen.getByRole('textbox', { name: words.topicAdd });
    const described = topic.getAttribute('aria-describedby');
    expect(described).toBeTruthy();
    expect(document.getElementById(described!)!.textContent).toBe(
      words.required.topics,
    );
    expect(document.activeElement).toBe(topic);
  });

  it('화면을 떠나면 저장소의 열쇠를 버린다(forget)', () => {
    const server = fakeDataverifyServer();
    const store = serverStoreOf(server);
    const forget = vi.fn();
    const view = render(
      <NewScreen
        store={{ ...store, forget }}
        now={NOW}
        onStarted={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(forget).not.toHaveBeenCalled();
    view.unmount();
    expect(forget).toHaveBeenCalledTimes(1);
  });
});

describe('DV-02 시안 대조 손질(밴드 DV3 ①)', () => {
  it('W1 검사 내용 표: DataTable 꼴 — 머리 회색 바탕·500 14, 몸 400 14, 700 0', () => {
    setup();
    const table = document.querySelector('[data-card="checks"] table')!;
    const ths = [...table.querySelectorAll('th')];
    const tds = [...table.querySelectorAll('td')];
    expect(ths.length).toBeGreaterThan(1);
    expect(tds.length).toBeGreaterThanOrEqual(words.checks.length * 2);
    for (const th of ths) {
      expect(th.className).toContain('bg-support-grey-subtle');
      expect(th.className).toContain('text-style-pre-body-05');
    }
    for (const td of tds)
      expect(td.className).toContain('text-style-pre-body-06');
    expect(table.outerHTML).not.toContain('text-style-pre-body-04');
    expect(table.getAttribute('aria-label')).toBe(words.checksTitle);
  });

  it('W2 기업 정보: 이름 160 칸 넷(회색 바탕·500 14) · 라벨이 입력을 찾음 · 도움 글 400 12', () => {
    setup();
    const card = document.querySelector('[data-card="company"]')!;
    const heads = [...card.querySelectorAll('.w-40')];
    expect(heads.map((head) => head.textContent)).toEqual([
      words.name,
      words.sasb,
      words.topics,
      words.year,
    ]);
    for (const head of heads) {
      expect(head.className).toContain('bg-support-grey-subtle');
      expect(head.className).toContain('text-style-pre-body-05');
      expect(head.parentElement!.className).toContain('min-h-16');
    }
    expect(screen.getByLabelText(words.name).tagName).toBe('INPUT');
    expect(screen.getByLabelText(words.sasb).tagName).toBe('INPUT');
    expect(
      screen.getByRole('group', { name: words.topics }).querySelector('input'),
    ).not.toBeNull();
    const notes = [...card.querySelectorAll('p')].filter(
      (p) =>
        p.textContent === words.topicsHint ||
        p.textContent === words.companyHint,
    );
    expect(notes).toHaveLength(2);
    for (const note of notes)
      expect(note.className).toContain('text-style-pre-caption-03');
  });

  it('W6 입력 탭은 line 꼴(목록 밑줄 · 칸 최소 96)', () => {
    setup();
    const list = screen.getByRole('tablist', { name: words.tabsLabel });
    expect(list.className).toContain('border-b');
    const tab = screen.getByRole('tab', { name: words.tabFile });
    expect(tab.className).toContain('min-w-24');
    expect(tab.className).toContain('border-b-2');
    expect(tab.className).toContain('data-[state=active]:border-text-brand');
  });

  it('W7 보고연도는 NativeSelect(select + ▾ svg 감싸개) · 값·필수 그대로', () => {
    setup();
    const select = screen.getByLabelText(words.year);
    expect(select.tagName).toBe('SELECT');
    expect(select.className).toContain('appearance-none');
    expect(select.className).toContain('h-9');
    expect(select.hasAttribute('required')).toBe(true);
    expect((select as HTMLSelectElement).value).toBe('2025');
    expect(select.parentElement!.querySelector('svg')).not.toBeNull();
  });
});

describe('DV-02 움직임(밴드 DV3 ②)', () => {
  it('②-7 입력 탭을 바꾸면 칸 감싸개가 새 노드(gw-m-fade) · 초점은 탭 단추', async () => {
    setup();
    const wrap = () => document.querySelector('[data-card="data"] .gw-m-fade')!;
    const before = wrap();
    expect(before.querySelector('input[type="file"]')).not.toBeNull();
    const fileTab = screen.getByRole('tab', { name: words.tabFile });
    act(() => fileTab.focus());
    fireEvent.keyDown(fileTab, { key: 'ArrowRight' });
    const pasteTab = screen.getByRole('tab', { name: words.tabPaste });
    await screen.findByRole('textbox', { name: words.pasteLabel });
    const after = wrap();
    expect(after).not.toBe(before);
    expect(after.querySelector('textarea')).not.toBeNull();
    expect(document.activeElement).toBe(pasteTab);
    expect(after.contains(pasteTab)).toBe(false);
  });
});

describe('DV-02 열 폭 고정(밴드 DVW1 ②-4)', () => {
  /** 고정 짜임 표의 colgroup 폭(px 글, 폭 없으면 ''). */
  const colWidths = (table: Element) => {
    expect(table.className).toContain('table-fixed');
    const cols = [...table.querySelectorAll(':scope > colgroup > col')];
    expect(cols).toHaveLength(table.querySelectorAll('thead th').length);
    return cols.map((col) => (col as HTMLElement).style.width);
  };

  it('검사 내용 표: table-fixed · 단계 열 잰 폭 84 · 하는 일 폭 없음', () => {
    setup();
    const table = document.querySelector('[data-card="checks"] table')!;
    expect(colWidths(table)).toEqual(['84px', '']);
  });
});

describe('DV-02 서버 입력 꼴(dataverify.input@1) 파일·글(밴드 DV5)', () => {
  /** 보고연도 2023(기본 2025 와 다르게 — 채움이 보이게). */
  const INPUT = JSON.stringify({
    ...fakeInput(),
    company: {
      ...FAKE_COMPANY,
      materialTopics: [...FAKE_COMPANY.materialTopics],
      reportingYear: '2023',
    },
  });
  const field = (label: string) =>
    (screen.getByLabelText(label) as HTMLInputElement).value;
  const topics = () =>
    screen.getAllByTestId('topic').map((each) => each.textContent);
  const filledNote = () => screen.getByTestId('company-filled');

  it('파일 → 거절 0 · 미리 읽기가 데이터만 든 꼴과 같음 · 빈 회사 칸 넷이 채워지고 안내(role=status)', async () => {
    setup();
    await pick(GOOD);
    const plain = screen.getByTestId('preview').textContent;
    cleanup();
    setup();
    expect(filledNote().getAttribute('role')).toBe('status');
    expect(filledNote().textContent).toBe('');
    await pick(INPUT);
    expect(dataError()).toBeUndefined();
    expect(screen.getByTestId('preview').textContent).toBe(plain);
    expect(field(words.name)).toBe(FAKE_COMPANY.name);
    expect(field(words.sasb)).toBe(FAKE_COMPANY.sasbIndustry);
    expect(topics()).toEqual([...FAKE_COMPANY.materialTopics]);
    expect(field(words.year)).toBe('2023');
    expect(filledNote().textContent).toBe(words.companyFilled);
  });

  it('먼저 쓴 기업명은 그대로 · 나머지만 채움 · 다시 골라도 쓴 칸 그대로', async () => {
    setup();
    fireEvent.change(screen.getByLabelText(words.name), {
      target: { value: '내가 쓴 이름' },
    });
    await pick(INPUT);
    expect(field(words.name)).toBe('내가 쓴 이름');
    expect(field(words.sasb)).toBe(FAKE_COMPANY.sasbIndustry);
    expect(topics()).toEqual([...FAKE_COMPANY.materialTopics]);
    fireEvent.change(screen.getByLabelText(words.sasb), {
      target: { value: '내가 쓴 산업' },
    });
    await pick(INPUT, 'again.json');
    expect(field(words.name)).toBe('내가 쓴 이름');
    expect(field(words.sasb)).toBe('내가 쓴 산업');
  });

  it('토픽을 먼저 넣었으면 토픽은 그대로(파일 토픽을 더하지 않음) · 나머지만 채움', async () => {
    setup();
    fillCompany({ name: '', sasb: '', topics: ['내 토픽'] });
    await pick(INPUT);
    expect(topics()).toEqual(['내 토픽']);
    expect(field(words.name)).toBe(FAKE_COMPANY.name);
    expect(field(words.sasb)).toBe(FAKE_COMPANY.sasbIndustry);
  });

  it('보고연도를 먼저 골랐으면 덮지 않는다 · 고르기 밖 연도는 채우지 않는다', async () => {
    setup();
    fireEvent.change(screen.getByLabelText(words.year), {
      target: { value: '2024' },
    });
    await pick(INPUT);
    expect(field(words.year)).toBe('2024');
    expect(field(words.name)).toBe(FAKE_COMPANY.name);
    cleanup();
    setup();
    await pick(
      JSON.stringify({
        ...fakeInput(),
        company: { ...FAKE_COMPANY, reportingYear: '2018' },
      }),
    );
    expect(field(words.year)).toBe('2025');
    expect(field(words.name)).toBe(FAKE_COMPANY.name);
  });

  it('붙여 넣기도 같다 — 빈 칸 넷 채움 · 안내', async () => {
    setup();
    await paste(INPUT);
    expect(dataError()).toBeUndefined();
    expect(screen.getByTestId('preview')).toBeTruthy();
    expect(field(words.name)).toBe(FAKE_COMPANY.name);
    expect(field(words.sasb)).toBe(FAKE_COMPANY.sasbIndustry);
    expect(topics()).toEqual([...FAKE_COMPANY.materialTopics]);
    expect(field(words.year)).toBe('2023');
    expect(filledNote().textContent).toBe(words.companyFilled);
  });

  it('데이터만 든 꼴 파일은 회사 칸을 건드리지 않는다 · 안내 0', async () => {
    setup();
    await pick(GOOD);
    expect(field(words.name)).toBe('');
    expect(field(words.sasb)).toBe('');
    expect(screen.queryAllByTestId('topic')).toEqual([]);
    expect(field(words.year)).toBe('2025');
    expect(filledNote().textContent).toBe('');
  });

  it('꼴이 틀린 입력(schemaVersion 다름·data 목록)은 지금처럼 읽지 못함 · 회사 칸 0', async () => {
    for (const bad of [
      { ...fakeInput(), schemaVersion: 'dataverify.input@2' },
      { ...fakeInput(), data: [edkItem()] },
    ]) {
      setup();
      await pick(JSON.stringify(bad));
      expect(dataError()).toBe(words.errors.fileUnreadable);
      expect(field(words.name)).toBe('');
      expect(isOff()).toBe(true);
      cleanup();
    }
  });

  it('채운 뒤 보낸 POST 본문은 데이터만 든 꼴과 같은 열쇠 · input 은 채운 회사와 data', async () => {
    const { server } = setup();
    await pick(INPUT);
    fireEvent.click(startButton());
    await settle();
    const body = server.posts()[0]!.body as {
      options: { input: Record<string, unknown> };
    };
    expect(Object.keys(body)).toEqual(['module', 'launchKey', 'options']);
    expect(Object.keys(body.options)).toEqual(['input', 'source']);
    expect(body.options.input).toEqual({
      schemaVersion: 'dataverify.input@1',
      company: {
        ...FAKE_COMPANY,
        materialTopics: [...FAKE_COMPANY.materialTopics],
        reportingYear: '2023',
      },
      data: edkData(),
    });
  });
});

describe('DV-02 EDK 인벤토리 엑셀(밴드 DVX1 ②)', () => {
  const READ = 'POST /dataverify/edk/read';
  /** 지어낸 엑셀 바이트(「PK」 머리 — 내용은 가짜 서버가 보지 않는다). */
  const XLSX_BYTES = new Uint8Array([80, 75, 3, 4, 1, 2, 3]);
  /** 가짜 서버 기본 ok 답의 data 와 같은 내용의 JSON(그 답은 edkData() 의 환경만). */
  const SAME_JSON = JSON.stringify({
    환경: (edkData() as { 환경: unknown[] }).환경,
  });
  const yearValue = () =>
    (screen.getByLabelText(words.year) as HTMLSelectElement).value;
  const filledNote = () => screen.getByTestId('company-filled');
  /** 엑셀 읽기 왕복(가짜 서버 fetch)을 기다린다. */
  const flush = () =>
    act(async () => {
      for (let n = 0; n < 5; n += 1)
        await new Promise((done) => setTimeout(done, 0));
    });
  async function pickXlsx(name = 'edk.xlsx') {
    await pick(XLSX_BYTES, name);
    await flush();
  }

  const original = {
    create: URL.createObjectURL,
    revoke: URL.revokeObjectURL,
  };
  beforeAll(() => {
    URL.createObjectURL = vi.fn(() => 'blob:fake-1');
    URL.revokeObjectURL = vi.fn();
  });
  afterAll(() => {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  });

  it('.xlsx 는 맨 바이트로 서버 읽기 한 번 · 미리 읽기 줄이 같은 data 의 .json 과 같음 · 뺀 테마 한 줄', async () => {
    setup();
    await pick(SAME_JSON);
    const plain = screen.getByTestId('preview').textContent;
    expect(screen.queryByTestId('skipped-themes')).toBeNull();
    cleanup();
    const { server } = setup();
    await pickXlsx();
    expect(server.count(READ)).toBe(1);
    const [call] = server.calls.filter((c) => `${c.method} ${c.path}` === READ);
    expect(call!.octets).toBe(XLSX_BYTES.length);
    expect(dataError()).toBeUndefined();
    expect(screen.getByTestId('preview').textContent).toBe(plain);
    expect(screen.getByTestId('file-meta').textContent).toBe(
      words.fileLine(1, 2, '1KB'),
    );
    expect(screen.getByTestId('skipped-themes').textContent).toBe(
      words.skippedThemes(2, 2),
    );
  });

  it('[검증 시작]의 POST /runs 본문이 같은 data 의 .json 과 같다(source 이름만 다름 · 보고연도는 둘 다 고른 값)', async () => {
    const bodies: Record<string, unknown>[] = [];
    for (const name of ['edk.json', 'edk.xlsx']) {
      const { server } = setup();
      if (name.endsWith('.xlsx')) await pickXlsx(name);
      else await pick(SAME_JSON, name);
      fillCompany();
      fireEvent.change(screen.getByLabelText(words.year), {
        target: { value: '2023' },
      });
      fireEvent.click(startButton());
      await settle();
      const [post] = server.posts();
      bodies.push((post!.body as { options: Record<string, unknown> }).options);
      cleanup();
    }
    expect(bodies[1]!.input).toEqual(bodies[0]!.input);
    expect(Object.keys(bodies[1]!)).toEqual(Object.keys(bodies[0]!));
    expect(bodies[0]!.source).toEqual({ kind: 'file', name: 'edk.json' });
    expect(bodies[1]!.source).toEqual({ kind: 'file', name: 'edk.xlsx' });
  });

  it('거절 kind 마다 그 글(data-error · 칸 aria) · 서버 message 0 · 끊김·꼴 틀림은 읽지 못함 글 · 끔', async () => {
    const x = words.errors.xlsx;
    const cases: [() => Response, string][] = [
      [() => json(200, edkRejected('too_large')), x.too_large],
      [() => json(200, edkRejected('not_xlsx')), x.not_xlsx],
      [() => json(200, edkRejected('unsafe_xlsx')), x.unsafe_xlsx],
      [() => json(200, edkRejected('bad_header', 1, 3)), x.bad_header],
      [() => json(200, edkRejected('bad_cell', 7, 11)), x.bad_cell(7)],
      [() => json(200, edkRejected('no_theme', 9, 2)), x.no_theme(9)],
      [
        () => json(200, edkRejected('too_many_rows', 2002)),
        x.too_many_rows(2000),
      ],
      [
        () => json(200, edkRejected('too_many_scanned_rows')),
        x.too_many_scanned_rows,
      ],
      [() => json(200, edkRejected('no_rows')), x.no_rows],
      [() => json(200, edkRejected('no_target_theme')), x.no_target_theme],
      [
        () => json(200, edkRejected('long_cell', 7, 3)),
        x.long_cell(7, 3, 2000),
      ],
      [
        () => json(200, edkRejected('converted_too_large', 30)),
        words.errors.convertedTooLarge,
      ],
      [unreachable, words.errors.xlsxUnreachable],
      [() => refusal(500, 'INTERNAL'), words.errors.xlsxUnreachable],
      [() => json(200, { ok: true }), words.errors.xlsxUnreachable],
    ];
    for (const [answer, text] of cases) {
      const { server } = setup();
      server.override[READ] = answer;
      await pickXlsx();
      const shown = screen.getByTestId('data-error');
      expect(shown.textContent, text).toBe(text);
      expect(document.body.textContent).not.toContain('지어낸-');
      expect(screen.queryByTestId('preview'), text).toBeNull();
      expect(isOff(), text).toBe(true);
      const zone = document.querySelector<HTMLElement>(
        '[data-card="data"] div[role="button"]',
      )!;
      expect(zone.getAttribute('aria-describedby')).toBe(shown.id);
      cleanup();
    }
  });

  it('글 표의 거절 글은 서버 kind 열 전부를 덮는다(행 번호 없는 갈래도)', () => {
    const x = words.errors.xlsx;
    expect(Object.keys(x).sort()).toEqual(
      [
        'too_large',
        'not_xlsx',
        'unsafe_xlsx',
        'bad_header',
        'bad_cell',
        'no_theme',
        'too_many_rows',
        'too_many_scanned_rows',
        'no_rows',
        'no_target_theme',
        'long_cell',
        'converted_too_large',
      ].sort(),
    );
    expect(x.bad_cell(null)).not.toContain('null');
    expect(x.no_theme(null)).not.toContain('null');
    expect(x.long_cell(null, null, 2000)).not.toContain('null');
    expect(x.converted_too_large).toBe(words.errors.convertedTooLarge);
  });

  it('보고연도를 고르지 않았으면 파일의 마지막 연도 · 안내 yearFilled(role=status)', async () => {
    setup();
    expect(yearValue()).toBe('2025');
    await pickXlsx();
    expect(yearValue()).toBe('2024');
    expect(filledNote().textContent).toBe(words.yearFilled('2024'));
    // 사용자가 연도를 바꾸면 그 안내는 걷는다
    fireEvent.change(screen.getByLabelText(words.year), {
      target: { value: '2022' },
    });
    expect(filledNote().textContent).toBe('');
  });

  it('먼저 고른 보고연도는 그대로 · 고르기 밖 마지막 연도도 그대로(안내 0)', async () => {
    setup();
    fireEvent.change(screen.getByLabelText(words.year), {
      target: { value: '2023' },
    });
    await pickXlsx();
    expect(yearValue()).toBe('2023');
    expect(filledNote().textContent).toBe('');
    cleanup();
    const { server } = setup();
    server.override[READ] = () =>
      json(200, fakeEdkReadOk({ years: ['2015', '2019'] }));
    await pickXlsx();
    expect(yearValue()).toBe('2025');
    expect(filledNote().textContent).toBe('');
  });

  it('늦게 온 앞 파일의 답은 버린다', async () => {
    const { server } = setup();
    let release: (() => void) | undefined;
    const late = new Promise<Response>((done) => {
      release = () => done(json(200, edkRejected('not_xlsx')));
    });
    server.override[READ] = [() => late];
    await pick(XLSX_BYTES, 'first.xlsx');
    fireEvent.click(screen.getByRole('button', { name: /first\.xlsx/ }));
    await pick(SAME_JSON, 'second.json');
    expect(screen.getByTestId('preview')).toBeTruthy();
    release!();
    await flush();
    expect(dataError()).toBeUndefined();
    expect(screen.getByTestId('preview')).toBeTruthy();
  });

  it('바꾼 data 가 256KiB 를 넘으면 읽은 항목이 너무 많다는 글 · 끔(요청 0)', async () => {
    const { server } = setup();
    server.override[READ] = () =>
      json(
        200,
        fakeEdkReadOk({
          data: { 환경: [edkItem({ 메모: 'x'.repeat(OPTIONS_MAX_OCTETS) })] },
          itemCount: 1,
        }),
      );
    await pickXlsx();
    expect(dataError()).toBe(words.errors.convertedTooLarge);
    expect(screen.queryByTestId('preview')).toBeNull();
    fillCompany();
    fireEvent.click(startButton());
    await settle();
    expect(server.count('POST /runs')).toBe(0);
  });

  it('바꾼 data 는 256KiB 안이나 기업 칸을 넣은 options 셈이 넘으면 같은 글', async () => {
    const { server } = setup();
    const dataOf = (memo: string) => ({ 환경: [edkItem({ 메모: memo })] });
    const empty = {
      name: '',
      sasbIndustry: '',
      materialTopics: [],
      reportingYear: '2024',
    };
    const octetsOf = (memo: string) =>
      pyJsonOctets(
        buildOptions(
          buildInput(empty, dataOf(memo) as EdkData),
          fileSource('edk.xlsx'),
        ),
      );
    const fill = OPTIONS_MAX_OCTETS - 20 - octetsOf('');
    server.override[READ] = () =>
      json(
        200,
        fakeEdkReadOk({ data: dataOf('x'.repeat(fill)), itemCount: 1 }),
      );
    await pickXlsx();
    expect(dataError()).toBeUndefined();
    fillCompany();
    expect(dataError()).toBe(words.errors.convertedTooLarge);
    expect(isOff()).toBe(true);
  });

  it('1MiB 넘는 .xlsx 는 칸이 크기 글(요청 0) · 256KiB 넘고 1MiB 안의 .json 은 읽지 않고 크기 글', async () => {
    const { server } = setup();
    await pick(new Uint8Array(1024 * 1024 + 1).fill(32), 'big.xlsx');
    expect(screen.getByText(words.errors.fileTooLarge, { exact: false }));
    expect(server.count(READ)).toBe(0);
    cleanup();
    setup();
    const text = vi.spyOn(File.prototype, 'text');
    await pick(new Uint8Array(OPTIONS_MAX_OCTETS + 1).fill(32), 'big.json');
    expect(dataError()).toBe(words.errors.fileTooLarge);
    expect(text).not.toHaveBeenCalled();
    text.mockRestore();
  });

  it('확장자는 대소문자 없이 가른다(.XLSX 도 서버 읽기)', async () => {
    const { server } = setup();
    await pickXlsx('EDK.XLSX');
    expect(server.count(READ)).toBe(1);
    expect(screen.getByTestId('preview')).toBeTruthy();
  });

  it('[엑셀 양식 내려받기]는 화면 보고연도로 · 실패면 단추 옆 한 줄', async () => {
    const { server } = setup();
    expect(screen.getByText(words.templateHint)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(words.year), {
      target: { value: '2023' },
    });
    await act(async () => {
      fireEvent.click(screen.getByTestId('template'));
    });
    await flush();
    const calls = server.calls.filter(
      (c) => `${c.method} ${c.path}` === 'GET /dataverify/edk/template',
    );
    expect(calls.map((c) => c.search)).toEqual(['?year=2023']);
    expect(screen.getByTestId('template-error').textContent).toBe('');
    expect(FAKE_TEMPLATE_NAME).toContain('.xlsx');
    server.override['GET /dataverify/edk/template'] = unreachable;
    await act(async () => {
      fireEvent.click(screen.getByTestId('template'));
    });
    await flush();
    expect(screen.getByTestId('template-error').textContent).toBe(
      words.templateFailed,
    );
  });
});
