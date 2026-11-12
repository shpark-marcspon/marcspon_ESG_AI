// @vitest-environment jsdom
// AD-04 실행 기록·지표 화면(밴드 AD2 ③, 실서버 AD4R ②). 진짜 어댑터(createRunLogServerPort + createApi)에 거르지 않는 가짜 서버를 물리고 고정 시계로 본다.
//   ① 틀: 제목·설명·판 글 바닥글·[엑셀 내보내기] 끔, 예시 데이터 띠 없음, 모의 공급사 안내 띠(켬·끔), 지표 다섯(서버 값, null 은 「–」), 열하나(AD4X ①)
//   ② 줄: 서버 값 그대로(모듈 이름·id, 테스트 배지, 흐름 판, 담당자 대체 글 회색, 처리 시간 「–」, 토큰 쉼표, 비용 <$0.01, 상태 넷), 건수 = 서버 count
//   ③ 거르기 → 요청 URL: 처음(이번 달), 검색(멈춘 뒤 300ms·공백만은 요청 없음), 모듈·상태·기간, 바꾸면 offset 0·지표는 다시 안 부름, 늦은 답은 버림.
//      화면은 받은 줄을 다시 거르지 않는다(가짜 서버가 거르지 않아도 받은 줄이 그대로 그려진다). 모듈 선택지 = 고정 여섯 + 본 id.
//   ④ 0건 꼴(디자인 답 5) ⑤ 더 보기 ⑥ 불러오기·실패(지표만 실패해도 실패 상자, [다시 시도] → 둘 다) ⑦ 표 줄 꼴
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

import { createRunLogServerPort } from '../../../entities/run-log/api/index.ts';
import {
  FAKE_EXPORT_NAME,
  FAKE_EXPORT_TEXT,
  FAKE_FILE_TEXT,
  fakeRunDetail,
  fakeRunLogServer,
  fakeRunMetrics,
  fakeRunRow,
  fakeServedName,
  json,
  refusal,
  runFilePath,
} from '../../../entities/run-log/api/testing.ts';
import { RUN_LOG_TEXT } from '../../../entities/run-log/config/text.ts';
import type {
  RunLogDetail,
  RunLogRow,
  RunMetricsRow,
} from '../../../entities/run-log/model/index.ts';
import { createApi } from '../../../shared/api/index.ts';
import { ROW_FOCUS, ROW_HOVER } from '../../../shared/ui/data-table/index.ts';
import { RunsScreen } from './RunsScreen.tsx';

afterEach(cleanup);
vi.setConfig({ testTimeout: 15_000 });

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

const t = RUN_LOG_TEXT;
const BASE = 'http://test.local/api';
/** 고정 시계: KST 2026-10-15 12:00 — 이번 달 = 10-01 ~ 10-15. */
const NOW = new Date('2026-10-15T03:00:00Z');
const MONTH = { dateFrom: '2026-10-01', dateTo: '2026-10-15' };

/** 지어낸 줄 다섯(새 것 먼저 — 서버 차례). createdAt 은 서버 꼴(+09:00). */
const ROWS: RunLogRow[] = [
  fakeRunRow(5, {
    createdAt: '2026-10-15T15:10:00+09:00',
    documentName: '평가 문서 1.pdf',
    durationSec: 485,
    tokens: 108_100,
    costUsd: 0.58,
    isTest: true,
    review: 'in_review',
    aiSetting: { id: 3, name: 'v3' },
  }),
  fakeRunRow(4, {
    module: 'inventory.scope3',
    flowId: 'inventory.scope3.colab@S3',
    createdAt: '2026-10-15T14:32:00+09:00',
    documentName: '구매 데이터_3분기.xlsx',
    status: 'processing',
    finishedAt: null,
    durationSec: null,
    tokens: 0,
    costUsd: 0,
  }),
  fakeRunRow(3, {
    module: 'dataverify',
    flowId: 'dataverify.colab@156',
    createdAt: '2026-10-14T09:00:00+09:00',
    status: 'failed',
    createdByName: null,
    createdByUsername: 'user13',
    durationSec: 30,
    tokens: 1_234,
    costUsd: 0.004,
    aiSetting: { id: null, name: 'colab-2026-01-15-v1' },
  }),
  fakeRunRow(2, {
    module: 'inventory.scope12',
    flowId: 'inventory.scope12.engine@1',
    createdAt: '2026-10-13T09:00:00+09:00',
    status: 'queued',
    startedAt: null,
    finishedAt: null,
    createdByName: null,
    createdByUsername: null,
    durationSec: null,
    tokens: 0,
    costUsd: 0,
  }),
  fakeRunRow(1, {
    createdAt: '2026-10-02T09:00:00+09:00',
    tokens: 3_150_000,
    costUsd: 12.345,
    review: 'confirmed',
  }),
];
const METRICS = fakeRunMetrics();

type FakeServer = ReturnType<typeof fakeRunLogServer>;

/** prepare 는 그리기 전에 가짜 서버를 손본다(첫 요청의 답을 바꿀 때). */
function setup(
  rows = ROWS,
  metrics: RunMetricsRow = METRICS,
  { prepare = () => {} }: { prepare?: (server: FakeServer) => void } = {},
) {
  const server = fakeRunLogServer(rows, metrics, { baseUrl: BASE });
  prepare(server);
  const port = createRunLogServerPort({
    api: createApi({ baseUrl: BASE, fetch: server.send }),
  });
  render(<RunsScreen port={port} now={() => NOW} />);
  return { server };
}

const rowIds = () =>
  [...document.querySelectorAll('tbody tr[data-run-id]')].map((row) =>
    Number(row.getAttribute('data-run-id')),
  );
const cellsOf = (id: number) =>
  [...document.querySelectorAll(`tr[data-run-id="${id}"] td`)] as HTMLElement[];
const count = () => screen.getByTestId('count').textContent;
const loaded = () => waitFor(() => expect(rowIds().length).toBeGreaterThan(0));

/** 고르기 칸(키트 dropdown-menu)을 열고 값 하나를 고른다. */
function choose(name: string, option: string) {
  fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
  fireEvent.click(screen.getByRole('menuitemradio', { name: option }));
}
/** 고르기 칸의 선택지 글(열고 읽고 닫는다). */
async function optionsOf(name: string) {
  fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
  const labels = screen
    .getAllByRole('menuitemradio')
    .map((item) => item.textContent);
  fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
  await waitFor(() => expect(screen.queryByRole('menu')).toBeNull());
  return labels;
}
const type = (value: string) =>
  fireEvent.change(screen.getByLabelText(t.searchLabel), {
    target: { value },
  });

/** 답을 붙잡아 두는 override(풀면 그때 가짜 서버의 답). */
function hold(server: FakeServer, key: string) {
  let release!: (response: Response) => void;
  const held = new Promise<Response>((done) => (release = done));
  const answers = server.override[key];
  server.override[key] = [
    () => held,
    ...(Array.isArray(answers) ? answers : []),
  ];
  return release;
}

describe('AD-04 ① 틀·지표', () => {
  it('제목·설명·판 글 바닥글·[엑셀 내보내기] 켬·열하나(AI 설정·검토), 예시 데이터 띠는 없다', async () => {
    setup();
    await loaded();
    expect(document.querySelector('[data-screen="admin-runs"]')).not.toBeNull();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(t.title);
    expect(screen.getByText(t.description)).toBeTruthy();
    expect(screen.getByText(t.foot)).toBeTruthy();
    expect(screen.queryByTestId('mock-band')).toBeNull();
    expect(screen.queryByText(/예시 데이터예요/)).toBeNull();
    expect(screen.queryByText(/지어낸 예시/)).toBeNull();
    expect(
      screen
        .getByRole('button', { name: t.export })
        .getAttribute('aria-disabled'),
    ).toBeNull();
    expect(
      screen.getAllByRole('columnheader').map((cell) => cell.textContent),
    ).toEqual([
      '시각',
      '모듈',
      '문서',
      '흐름',
      'AI 설정',
      '담당자',
      '처리 시간',
      '토큰',
      '비용(추정)',
      '상태',
      '검토',
    ]);
    expect(screen.getByRole('button', { name: '검토로 거르기' })).toBeTruthy();
    expect(screen.getByText('AI 설정')).toBeTruthy();
  });

  it('모의 공급사 안내 띠: aiProviderMock 이면 지표 위에 정보 띠 한 줄(흰 바탕·모서리 16)', async () => {
    setup();
    await loaded();
    const notice = screen.getByTestId('ai-mock-notice');
    expect(notice.textContent).toBe(t.aiMockNotice);
    // PageInfo 기본 꼴(글·아이콘 색 — 캔버스 v102), 바탕은 카드와 같은 흰 surface·모서리 16(디자인 대조). 파랑 아님.
    expect(notice.getAttribute('data-tone')).toBe('default');
    const classes = notice.className.split(/\s+/);
    expect(classes).toEqual(
      expect.arrayContaining([
        'bg-background-primary',
        'rounded-dialog',
        'px-4',
        'py-3',
        'text-text-tertiary',
      ]),
    );
    expect(classes).not.toContain('bg-background-secondary');
    // rounded-component(PageInfo 바탕)는 남는다 — cn(tailwind-merge)이 키트 모서리 토큰을 한 무리로 모른다. 프리셋 차례(control·component·dialog)로
    // rounded-dialog 가 이긴다(브라우저 계산값 16px — band-reports/AD4R-look/after-4/AD-04-notice.json).
    expect(notice.className).not.toMatch(/support-blue/);
    expect(
      notice.compareDocumentPosition(screen.getByTestId('metrics')) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it('모의 공급사 안내 띠: aiProviderMock 거짓이면 없다', async () => {
    setup(ROWS, fakeRunMetrics({ aiProviderMock: false }));
    await loaded();
    expect(screen.queryByTestId('ai-mock-notice')).toBeNull();
    expect(screen.queryByText(t.aiMockNotice)).toBeNull();
  });

  // MP1W: 띠의 근거는 서버 지표 하나 — 받는 중·실패엔 띠 없음(실제 비용을 보이는 시연에서 거짓 글보다 없음이 안전).
  it('모의 공급사 안내 띠: 지표를 받는 중엔 없고, 받은 지표가 참이면 그때 띠', async () => {
    let release!: (response: Response) => void;
    setup(ROWS, METRICS, {
      prepare: (server) => {
        release = hold(server, 'GET /run-logs/metrics');
      },
    });
    await waitFor(() =>
      expect(screen.getByRole('table', { name: t.tableLabel })).toBeTruthy(),
    );
    await new Promise((done) => setTimeout(done, 50));
    expect(screen.queryByTestId('ai-mock-notice')).toBeNull();
    await act(async () => {
      release(json(200, fakeRunMetrics({ aiProviderMock: true })));
    });
    await loaded();
    expect(screen.getByTestId('ai-mock-notice').textContent).toBe(
      t.aiMockNotice,
    );
  });

  it('모의 공급사 안내 띠: 지표 실패면 없다(실패 상자만)', async () => {
    setup(ROWS, METRICS, {
      prepare: (server) => {
        server.override['GET /run-logs/metrics'] = [
          () => refusal(403, 'FORBIDDEN'),
        ];
      },
    });
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
    expect(screen.queryByTestId('ai-mock-notice')).toBeNull();
    expect(screen.queryByText(t.aiMockNotice)).toBeNull();
  });

  it('지표 다섯은 서버 값(실행 수·평균 처리 시간·토큰 줄임·비용·실패율 ×100)', async () => {
    setup();
    await loaded();
    expect(screen.getByTestId('metrics').textContent).toBe(
      '이번 달 실행42회평균 처리 시간6분 40초토큰3.1M비용추정$18.40실패율4.8%',
    );
  });

  it('지표 null·0: 평균 처리 시간·실패율 「–」(% 없음), 토큰 「0」, 비용 「$0.00」', async () => {
    setup(
      ROWS,
      fakeRunMetrics({
        runs: 0,
        averageDurationSec: null,
        tokens: 0,
        costUsd: 0,
        failureRate: null,
      }),
    );
    await loaded();
    expect(screen.getByTestId('metrics').textContent).toBe(
      '이번 달 실행0회평균 처리 시간–토큰0비용추정$0.00실패율–',
    );
  });

  it('지표 토큰 1,000,000 아래는 쉼표, 실패율 0 은 「0.0%」', async () => {
    setup(ROWS, fakeRunMetrics({ tokens: 999_999, failureRate: 0 }));
    await loaded();
    const text = screen.getByTestId('metrics').textContent;
    expect(text).toContain('토큰999,999');
    expect(text).toContain('실패율0.0%');
  });
});

describe('AD-04 ② 줄', () => {
  it('줄은 서버 값 그대로(차례·시각·모듈·문서·흐름·담당자·처리 시간·토큰·비용·상태), 건수는 서버 count', async () => {
    setup();
    await loaded();
    expect(rowIds()).toEqual([5, 4, 3, 2, 1]);
    expect(count()).toBe('5건');
    const text = (id: number) => cellsOf(id).map((cell) => cell.textContent);
    expect(text(5)).toEqual([
      '2026-10-15 15:10',
      '그린워싱',
      `${t.test}평가 문서 1.pdf`, // 시험용 배지는 이름 앞(AF1 — Q7)
      'E0',
      'v3',
      '담당자 가',
      '8분 05초',
      '108,100',
      '$0.58',
      '완료',
      '검토 중',
    ]);
    expect(text(4)).toEqual([
      '2026-10-15 14:32',
      '온실가스 Scope 3',
      '구매 데이터_3분기.xlsx',
      'S3',
      '–',
      '담당자 가',
      '–',
      '0',
      '$0.00',
      '처리 중',
      '–',
    ]);
    expect(text(3)).toEqual([
      '2026-10-14 09:00',
      '데이터 검증',
      '지어낸 문서 3.pdf',
      '156',
      '기본 설정',
      'user13',
      '0분 30초',
      '1,234',
      '<$0.01',
      '실패',
      '–',
    ]);
    expect(text(2)).toEqual([
      '2026-10-13 09:00',
      'inventory.scope12',
      '지어낸 문서 2.pdf',
      '1',
      '–',
      '알 수 없는 사람',
      '–', // 대기 줄은 처리 시간·토큰·비용 모두 「–」(디자인 대조 B2)
      '–',
      '–',
      '대기',
      '–',
    ]);
    // 줄의 토큰은 쉼표 전체 수 — 줄임(3.1M)은 지표 카드만(디자인 답 4).
    expect(text(1)[7]).toBe('3,150,000');
    expect(text(1)[8]).toBe('$12.35');
    expect(document.querySelectorAll('[data-test-run]').length).toBe(1);
  });

  it('상태 배지 넷: 대기 grey · 처리 중 orange · 완료 success · 실패 error', async () => {
    setup();
    await loaded();
    const badge = (id: number) =>
      document.querySelector(`tr[data-run-id="${id}"] [data-status]`)!;
    expect(badge(2).getAttribute('data-status')).toBe('queued');
    expect(badge(2).className).toContain('bg-background-tertiary');
    expect(badge(4).className).toContain('support-orange');
    expect(badge(5).className).toContain('support-success');
    expect(badge(3).className).toContain('support-error');
  });

  it('담당자를 찾지 못한 줄의 「알 수 없는 사람」은 회색, 이름·아이디는 회색이 아니다', async () => {
    setup();
    await loaded();
    expect(cellsOf(2)[5]!.className).toContain('text-text-tertiary');
    expect(cellsOf(2)[5]!.hasAttribute('data-uploader-missing')).toBe(true);
    for (const id of [5, 3])
      expect(cellsOf(id)[5]!.className, String(id)).not.toContain(
        'text-text-tertiary',
      );
  });

  it('담당자 칸(KA1): 한 줄 — td 는 줄바꿈 클래스 없음, 안쪽 span 이 block·truncate 에 title = 이름, 「알 수 없는 사람」 줄은 title 없음', async () => {
    setup();
    await loaded();
    const words = (el: Element) => el.className.split(/\s+/);
    for (const id of [5, 3, 2]) {
      const cell = cellsOf(id)[5]!;
      expect(words(cell), String(id)).not.toContain('whitespace-normal');
      expect(words(cell), String(id)).not.toContain('break-words');
      const span = cell.querySelector(':scope > span')!;
      expect(words(span), String(id)).toEqual(
        expect.arrayContaining(['block', 'truncate']),
      );
      expect(span.textContent, String(id)).toBe(cell.textContent);
    }
    expect(cellsOf(5)[5]!.querySelector('span')!.getAttribute('title')).toBe(
      '담당자 가',
    );
    expect(cellsOf(3)[5]!.querySelector('span')!.getAttribute('title')).toBe(
      'user13',
    );
    expect(cellsOf(2)[5]!.querySelector('span')!.hasAttribute('title')).toBe(
      false,
    );
    expect(cellsOf(2)[5]!.hasAttribute('data-uploader-missing')).toBe(true);
  });

  it('AI 설정 칸: 판 이름(v3)·기본 판 「기본 설정」·없음 회색 「–」(missing), 이름·기본은 회색이 아니다', async () => {
    setup();
    await loaded();
    const cell = (id: number) => cellsOf(id)[4]!;
    expect(cell(5).textContent).toBe('v3');
    expect(cell(3).textContent).toBe(t.defaultSetting);
    expect(cell(4).textContent).toBe(t.empty);
    expect(cell(4).className).toContain('text-text-tertiary');
    expect(cell(4).hasAttribute('data-ai-setting-missing')).toBe(true);
    for (const id of [5, 3]) {
      expect(cell(id).className, String(id)).not.toContain(
        'text-text-tertiary',
      );
      expect(cell(id).hasAttribute('data-ai-setting-missing')).toBe(false);
    }
  });

  it('검토 배지 셋: 미검토 grey · 검토 중 blue · 확정 success, null 은 배지 없이 회색 「–」', async () => {
    setup([
      fakeRunRow(3, { review: 'pending' }),
      fakeRunRow(2, { review: 'in_review' }),
      fakeRunRow(1, { review: 'confirmed' }),
      fakeRunRow(0, { review: null }),
    ]);
    await loaded();
    const badge = (id: number) =>
      document.querySelector(`tr[data-run-id="${id}"] [data-review]`);
    expect(badge(3)!.getAttribute('data-review')).toBe('pending');
    expect(badge(3)!.textContent).toBe('미검토');
    expect(badge(3)!.className).toContain('bg-background-tertiary');
    expect(badge(2)!.textContent).toBe('검토 중');
    expect(badge(2)!.className).toContain('support-blue');
    expect(badge(1)!.textContent).toBe('확정');
    expect(badge(1)!.className).toContain('support-success');
    expect(badge(0)).toBeNull();
    const last = cellsOf(0).at(-1)!;
    expect(last.textContent).toBe('–');
    expect(last.querySelector('.text-text-tertiary')).not.toBeNull();
  });

  it('문서 칸: 이름은 120px 한 줄 줄임(truncate)·title 에 전체 이름, 시험용 배지는 줄임 밖', async () => {
    setup();
    await loaded();
    const name = cellsOf(5)[2]!.querySelector('[title]')!;
    expect(name.getAttribute('title')).toBe('평가 문서 1.pdf');
    expect(name.textContent).toBe('평가 문서 1.pdf');
    expect(name.className).toContain('truncate');
    expect(name.className).toContain('max-w-[120px]');
    const badge = cellsOf(5)[2]!.querySelector('[data-test-run]')!;
    expect(badge.textContent).toBe(t.test);
    expect(name.contains(badge)).toBe(false);
  });

  it('시험용 배지(AF1 — 디자인 6c Q7·Q8): 이름 단추 앞 같은 줄 · grey(blue 아님)', async () => {
    setup();
    await loaded();
    const badge = cellsOf(5)[2]!.querySelector<HTMLElement>('[data-test-run]')!;
    const button = cellsOf(5)[2]!.querySelector('[data-run-open]')!;
    expect(badge.parentElement).toBe(button.parentElement);
    expect(
      badge.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(badge.className).toContain('bg-background-tertiary');
    expect(badge.className).not.toContain('blue');
  });

  it('건수 「{n}건」 은 실린 줄 수가 아니라 서버 count', async () => {
    setup(ROWS, METRICS, {
      prepare: (server) => {
        server.override['GET /run-logs'] = () =>
          json(200, { count: 37, isNext: false, results: ROWS.slice(0, 2) });
      },
    });
    await loaded();
    expect(count()).toBe('37건');
    expect(rowIds()).toHaveLength(2);
  });
});

describe('AD-04 ③ 거르기 → 요청 URL', () => {
  it('처음: 줄 한 번(이번 달, 쿼리는 날짜 둘·limit 50·offset 0)과 지표 한 번', async () => {
    const { server } = setup();
    await loaded();
    expect(server.count('GET /run-logs')).toBe(1);
    expect(server.count('GET /run-logs/metrics')).toBe(1);
    expect(server.listQueries()).toEqual([
      { ...MONTH, limit: '50', offset: '0' },
    ]);
    expect(server.calls.some((call) => call.query.has('companyId'))).toBe(
      false,
    );
  });

  it('검색: 멈춘 뒤 300ms 에 한 번(그 안의 두 글자는 요청 하나), 앞뒤 빈칸은 걷고, 입력은 150자', async () => {
    const { server } = setup();
    await loaded();
    expect(screen.getByLabelText(t.searchLabel).getAttribute('maxLength')).toBe(
      '150',
    );
    vi.useFakeTimers();
    try {
      type('평');
      type(' 평가 ');
      await act(() => vi.advanceTimersByTimeAsync(299));
      expect(server.count('GET /run-logs')).toBe(1);
      await act(() => vi.advanceTimersByTimeAsync(1));
      expect(server.count('GET /run-logs')).toBe(2);
      expect(server.listQueries()[1]).toEqual({
        ...MONTH,
        q: '평가',
        limit: '50',
        offset: '0',
      });
      await act(() => vi.advanceTimersByTimeAsync(1_000));
      expect(server.count('GET /run-logs')).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it('공백만·NUL 만 든 검색은 요청을 내지 않고(쿼리가 같다), 그 뒤 거르기를 바꾼 요청에도 q 가 없다', async () => {
    const { server } = setup();
    await loaded();
    vi.useFakeTimers();
    try {
      type('   ');
      await act(() => vi.advanceTimersByTimeAsync(1_000));
      type(' \u0000 ');
      await act(() => vi.advanceTimersByTimeAsync(1_000));
      expect(server.count('GET /run-logs')).toBe(1);
    } finally {
      vi.useRealTimers();
    }
    choose(t.status.name, t.status.options.failed);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(server.calls.at(-1)!.query.has('q')).toBe(false);
    expect(server.calls.at(-1)!.query.get('status')).toBe('failed');
  });

  it('모듈 「데이터 검증」 → module=dataverify, 상태 「대기」 → status=queued, 「지난달」 → 앞 달 범위, 「전체」 → 날짜 키 없음. 지표는 다시 부르지 않는다', async () => {
    const { server } = setup();
    await loaded();
    choose(t.module.name, '데이터 검증');
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(server.listQueries()[1]).toEqual({
      ...MONTH,
      module: 'dataverify',
      limit: '50',
      offset: '0',
    });
    expect(
      screen.getByRole('button', { name: t.module.name }).textContent,
    ).toBe('모듈: 데이터 검증');
    choose(t.status.name, t.status.options.queued);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(3));
    expect(server.listQueries()[2]!.status).toBe('queued');
    choose(t.period.name, t.period.options.lastMonth);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(4));
    expect(server.listQueries()[3]).toEqual({
      dateFrom: '2026-09-01',
      dateTo: '2026-09-30',
      module: 'dataverify',
      status: 'queued',
      limit: '50',
      offset: '0',
    });
    choose(t.period.name, t.period.options.all);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(5));
    expect(server.listQueries()[4]).toEqual({
      module: 'dataverify',
      status: 'queued',
      limit: '50',
      offset: '0',
    });
    expect(server.count('GET /run-logs/metrics')).toBe(1);
  });

  it('화면은 받은 줄을 다시 거르지 않는다: 「대기」를 골라도 서버가 보낸 줄(대기 아닌 줄 포함)이 그대로 그려진다', async () => {
    const { server } = setup();
    await loaded();
    choose(t.status.name, t.status.options.queued);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    await waitFor(() => expect(rowIds()).toEqual([5, 4, 3, 2, 1]));
    expect(count()).toBe('5건');
    choose(t.module.name, '그린워싱');
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(3));
    await waitFor(() => expect(rowIds()).toEqual([5, 4, 3, 2, 1]));
  });

  it('「검토: 검토 중」 → review=in_review·offset 0, 지표는 다시 안 부름. 받은 줄은 다시 거르지 않는다', async () => {
    const { server } = setup();
    await loaded();
    choose(t.review.name, t.review.options.in_review);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(server.listQueries()[1]).toEqual({
      ...MONTH,
      review: 'in_review',
      limit: '50',
      offset: '0',
    });
    expect(
      screen.getByRole('button', { name: t.review.name }).textContent,
    ).toBe('검토: 검토 중');
    await waitFor(() => expect(rowIds()).toEqual([5, 4, 3, 2, 1]));
    expect(server.count('GET /run-logs/metrics')).toBe(1);
    expect(await optionsOf(t.review.name)).toEqual([
      '전체',
      '미검토',
      '검토 중',
      '확정',
    ]);
  });

  it('선택지: 모듈 = 「전체」 + 고정 여섯(셸 차례) + 줄에서 본 id(끝에 id 그대로), 상태 = 전체·대기·처리 중·완료·실패, 기간 = 이번 달·지난달·전체', async () => {
    setup();
    await loaded();
    expect(await optionsOf(t.module.name)).toEqual([
      '전체',
      '온실가스 Scope 3',
      '그린워싱',
      '중대성평가 IRO',
      '데이터 검증',
      '영문번역',
      '보고서 작성',
      'inventory.scope12',
    ]);
    expect(await optionsOf(t.status.name)).toEqual([
      '전체',
      '대기',
      '처리 중',
      '완료',
      '실패',
    ]);
    expect(await optionsOf(t.period.name)).toEqual([
      '이번 달',
      '지난달',
      '전체',
    ]);
  });

  it('모듈 선택지: 줄이 없어도 고정 여섯, 한 번 본 id 는 다음 답에 없어도 남는다', async () => {
    const { server } = setup([fakeRunRow(9, { module: 'x.y' })]);
    await loaded();
    expect((await optionsOf(t.module.name)).slice(1)).toEqual([
      '온실가스 Scope 3',
      '그린워싱',
      '중대성평가 IRO',
      '데이터 검증',
      '영문번역',
      '보고서 작성',
      'x.y',
    ]);
    server.override['GET /run-logs'] = () =>
      json(200, { count: 1, isNext: false, results: [fakeRunRow(8)] });
    choose(t.status.name, t.status.options.done);
    await waitFor(() => expect(rowIds()).toEqual([8]));
    expect((await optionsOf(t.module.name)).at(-1)).toBe('x.y');
  });

  it('늦은 답은 버린다: 첫 거르기의 답을 붙잡고 다시 바꾸면, 둘째 답 뒤에 첫 답이 와도 화면은 둘째 값', async () => {
    const { server } = setup();
    await loaded();
    const releaseFirst = hold(server, 'GET /run-logs');
    choose(t.status.name, t.status.options.done);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    server.override['GET /run-logs'] = () =>
      json(200, { count: 1, isNext: false, results: [ROWS[1]] });
    choose(t.status.name, t.status.options.processing);
    await waitFor(() => expect(rowIds()).toEqual([4]));
    releaseFirst(
      json(200, { count: 2, isNext: false, results: [ROWS[0], ROWS[4]] }),
    );
    await new Promise((done) => setTimeout(done, 50));
    expect(rowIds()).toEqual([4]);
    expect(count()).toBe('1건');
  });
});

describe('AD-04 ④ 0건 꼴(디자인 답 5)', () => {
  const empty = () => screen.queryByTestId('empty');
  const clearButton = () =>
    screen.queryByRole('button', { name: t.clearFilter });

  it('기간만(이번 달): 「이번 달 실행이 없어요」·「기간을 넓혀 보세요.」, [거르기 풀기]·「조건에 맞는…」 없음', async () => {
    setup([]);
    await waitFor(() => expect(empty()).not.toBeNull());
    expect(count()).toBe('0건');
    expect(
      [...empty()!.querySelectorAll('p')].map((line) => line.textContent),
    ).toEqual(['이번 달 실행이 없어요', '기간을 넓혀 보세요.']);
    expect(clearButton()).toBeNull();
    expect(screen.queryByText(t.noMatch)).toBeNull();
  });

  it('기간 「전체」: 「아직 실행이 없어요」 한 줄', async () => {
    const { server } = setup([]);
    await waitFor(() => expect(empty()).not.toBeNull());
    choose(t.period.name, t.period.options.all);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    await waitFor(() =>
      expect(empty()!.textContent).toBe('아직 실행이 없어요'),
    );
    expect(empty()!.querySelectorAll('p')).toHaveLength(1);
    expect(clearButton()).toBeNull();
  });

  it('모듈을 고른 뒤: 「조건에 맞는 실행이 없어요」·[거르기 풀기] → 검색·모듈·상태를 비우고 기간 전체로', async () => {
    const { server } = setup([]);
    await waitFor(() => expect(empty()).not.toBeNull());
    choose(t.module.name, '영문번역');
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(server.listQueries()[1]!.module).toBe('translation');
    await waitFor(() =>
      expect(screen.getByText('조건에 맞는 실행이 없어요')).toBeTruthy(),
    );
    expect(empty()).toBeNull();
    fireEvent.click(clearButton()!);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(3));
    expect(server.listQueries()[2]).toEqual({ limit: '50', offset: '0' });
    await waitFor(() => expect(empty()?.textContent).toBe(t.emptyAll));
  });
});

describe('AD-04 ④-2 검토만 건 0건', () => {
  it('검토만 걸고 0건: 「조건에 맞는 실행이 없어요」 + [거르기 풀기] → review 풀림', async () => {
    const { server } = setup([]);
    await waitFor(() => expect(screen.queryByTestId('empty')).not.toBeNull());
    choose(t.review.name, t.review.options.confirmed);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(server.listQueries()[1]!.review).toBe('confirmed');
    await waitFor(() => expect(screen.getByText(t.noMatch)).toBeTruthy());
    expect(screen.queryByTestId('empty')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: t.clearFilter }));
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(3));
    expect(server.listQueries()[2]).toEqual({ limit: '50', offset: '0' });
    expect(
      screen.getByRole('button', { name: t.review.name }).textContent,
    ).toBe('검토: 전체');
  });
});

describe('AD-04 ⑤ 더 보기', () => {
  const many = Array.from({ length: 53 }, (_, i) => fakeRunRow(53 - i));

  it('「53건 중 50건」 → [더 보기] → offset 50, 줄이 이어 붙고, 다 받으면 단추 없이 「53건」', async () => {
    const { server } = setup(many);
    await loaded();
    expect(rowIds()).toHaveLength(50);
    expect(count()).toBe('53건 중 50건');
    fireEvent.click(screen.getByRole('button', { name: t.more }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    expect(server.listQueries()[1]).toEqual({
      ...MONTH,
      limit: '50',
      offset: '50',
    });
    expect(rowIds().slice(48)).toEqual([5, 4, 3, 2, 1]);
    expect(count()).toBe('53건');
    expect(screen.queryByRole('button', { name: t.more })).toBeNull();
    expect(server.count('GET /run-logs/metrics')).toBe(1);
  });

  it('더 보기 실패: 줄은 그대로, 「기록을 더 불러오지 못했어요」 + [다시 시도] → 이어 붙음', async () => {
    const { server } = setup(many);
    await loaded();
    server.override['GET /run-logs'] = [() => refusal(500, 'INTERNAL')];
    fireEvent.click(screen.getByRole('button', { name: t.more }));
    const more = await screen.findByTestId('more');
    await waitFor(() =>
      expect(within(more).getByText(t.moreFailed)).toBeTruthy(),
    );
    expect(rowIds()).toHaveLength(50);
    expect(screen.queryByTestId('load-failure')).toBeNull();
    fireEvent.click(within(more).getByRole('button', { name: t.retry }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    expect(server.listQueries().map((query) => query.offset)).toEqual([
      '0',
      '50',
      '50',
    ]);
  });

  it('더 보기 뒤 거르기를 바꾸면 offset 0 부터 다시', async () => {
    const { server } = setup(many);
    await loaded();
    fireEvent.click(screen.getByRole('button', { name: t.more }));
    await waitFor(() => expect(rowIds()).toHaveLength(53));
    choose(t.status.name, t.status.options.done);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(3));
    expect(server.listQueries()[2]!.offset).toBe('0');
    await waitFor(() => expect(rowIds()).toHaveLength(50));
  });
});

describe('AD-04 ⑥ 불러오기·실패', () => {
  it('300ms 안에는 아무것도, 뒤에는 aria-busy 스켈레톤, 지표는 받은 뒤에', async () => {
    vi.useFakeTimers();
    try {
      let release!: (response: Response) => void;
      setup(ROWS, METRICS, {
        prepare: (server) => {
          release = hold(server, 'GET /run-logs');
        },
      });
      const table = screen.getByRole('table', { name: t.tableLabel });
      expect(table.getAttribute('aria-busy')).toBeNull();
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(table.getAttribute('aria-busy')).toBe('true');
      expect(screen.getByRole('status').textContent).toBe(t.loading);
      expect(screen.queryByTestId('metrics')).toBeNull();
      await act(async () => {
        release(json(200, { count: 5, isNext: false, results: ROWS }));
        await vi.advanceTimersByTimeAsync(10);
      });
      expect(table.getAttribute('aria-busy')).toBeNull();
      expect(rowIds()).toHaveLength(5);
      expect(screen.getByTestId('metrics')).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it('줄 실패 → 「실행 기록을 불러오지 못했어요」 + [다시 시도] → 줄·지표 둘 다 다시. 실패 동안 건수·지표 없음', async () => {
    const { server } = setup(ROWS, METRICS, {
      prepare: (fake) => {
        fake.override['GET /run-logs'] = [
          () => refusal(422, 'VALIDATION_ERROR'),
        ];
      },
    });
    const failure = await screen.findByTestId('load-failure');
    expect(within(failure).getByText(t.failed)).toBeTruthy();
    expect(screen.queryByTestId('count')).toBeNull();
    expect(screen.queryByTestId('metrics')).toBeNull();
    fireEvent.click(within(failure).getByRole('button', { name: t.retry }));
    await loaded();
    expect(server.count('GET /run-logs')).toBe(2);
    expect(server.count('GET /run-logs/metrics')).toBe(2);
  });

  it('지표만 실패해도 실패 상자 하나(「둘로만」)', async () => {
    setup(ROWS, METRICS, {
      prepare: (server) => {
        server.override['GET /run-logs/metrics'] = [
          () => refusal(403, 'FORBIDDEN'),
        ];
      },
    });
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
    expect(rowIds()).toEqual([]);
    expect(screen.queryByTestId('metrics')).toBeNull();
  });

  it('연결 끊김(던짐)도 실패 상자', async () => {
    setup(ROWS, METRICS, {
      prepare: (server) => {
        server.override['GET /run-logs'] = () => {
          throw new TypeError('끊김');
        };
      },
    });
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
  });

  it('불러오기·실패·빈 줄은 초점을 받지 않는다(줄 tabIndex 없음·줄 이름 없음 — 밴드 TB1)', async () => {
    const table = () => screen.getByRole('table', { name: t.tableLabel });
    const focusableRows = () =>
      [...table().querySelectorAll('tbody tr')].filter(
        (row) => row.hasAttribute('tabindex') || row.hasAttribute('aria-label'),
      );
    vi.useFakeTimers();
    try {
      let release!: (response: Response) => void;
      setup(ROWS, METRICS, {
        prepare: (server) => {
          release = hold(server, 'GET /run-logs');
        },
      });
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(table().getAttribute('aria-busy')).toBe('true');
      expect(table().querySelectorAll('tbody tr').length).toBeGreaterThan(0);
      expect(focusableRows()).toEqual([]);
      await act(async () => {
        release(refusal(500, 'SERVER_ERROR'));
        await vi.advanceTimersByTimeAsync(10);
      });
    } finally {
      vi.useRealTimers();
    }
    expect(await screen.findByTestId('load-failure')).toBeTruthy();
    expect(focusableRows()).toEqual([]);
    cleanup();

    setup([]);
    await waitFor(() => expect(screen.queryByTestId('empty')).not.toBeNull());
    expect(focusableRows()).toEqual([]);
  });
});

describe('AD-04 ⑦ 표 줄 꼴(밴드 DT1 C15)', () => {
  it('표 칸은 줄 56(h-14)·좌우 16(px-4), 머리 칸도 좌우 16 — 48·12 아님', async () => {
    setup();
    await loaded();
    const row = document.querySelector('tr[data-run-id]')!;
    const cells = [...row.querySelectorAll('td')];
    expect(cells.length).toBeGreaterThan(0);
    for (const cell of cells) {
      expect(cell.className).toContain('h-14');
      expect(cell.className).toContain('px-4');
      expect(cell.className).not.toMatch(/\bh-12\b|\bpx-3\b/);
    }
    const heads = [...document.querySelectorAll('thead th')];
    expect(heads.length).toBeGreaterThan(0);
    for (const head of heads) {
      expect(head.className).toContain('px-4');
      expect(head.className).not.toMatch(/\bpx-3\b/);
    }
  });

  it('누를 수 있는 줄은 공용 hover·초점 꼴(ROW_HOVER·ROW_FOCUS) — 키보드 초점이 브라우저 기본 고리가 아니다(밴드 WM1, sid:MARC-ISSUE-606)', async () => {
    setup();
    await loaded();
    const classes = document
      .querySelector('tr[data-run-id]')!
      .className.split(/\s+/);
    for (const name of [
      'cursor-pointer',
      ...ROW_HOVER.split(' '),
      ...ROW_FOCUS.split(' '),
    ])
      expect(classes).toContain(name);
  });
});

describe('AD-04 ⑧ [엑셀 내보내기](밴드 AD4X ②)', () => {
  /** save 를 가짜로 넣어 그린다(setup 꼴 — 진짜 어댑터에 가짜 서버). */
  function renderExport(
    rows = ROWS,
    { prepare = () => {} }: { prepare?: (server: FakeServer) => void } = {},
  ) {
    const server = fakeRunLogServer(rows, METRICS, { baseUrl: BASE });
    prepare(server);
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    const save = vi.fn<(blob: Blob, fileName: string) => void>();
    render(<RunsScreen port={port} now={() => NOW} save={save} />);
    return { server, save };
  }
  const button = () => screen.getByTestId('export');
  const alertText = () => screen.getByTestId('export-error').textContent;
  const bytes = async (blob: Blob) =>
    new TextDecoder().decode(await blob.arrayBuffer());

  it('거르기 넷(모듈·상태·검토·기간) 뒤 누름 → export 하나, 질의 = 마지막 목록 질의 − 쪽, save(흉내 몸 Blob, 해독한 이름)', async () => {
    const { server, save } = renderExport();
    await loaded();
    choose(t.module.name, '그린워싱');
    choose(t.status.name, t.status.options.done);
    choose(t.review.name, t.review.options.confirmed);
    choose(t.period.name, t.period.options.lastMonth);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(5));
    await loaded();
    fireEvent.click(button());
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(server.count('GET /run-logs/export')).toBe(1);
    const { limit, offset, ...lastList } = server.listQueries().at(-1)!;
    expect([limit, offset]).toEqual(['50', '0']);
    expect(server.exportQueries()).toEqual([lastList]);
    expect(lastList).toEqual({
      dateFrom: '2026-09-01',
      dateTo: '2026-09-30',
      module: 'greenwash',
      status: 'done',
      review: 'confirmed',
    });
    const [blob, fileName] = save.mock.calls[0]!;
    expect(fileName).toBe(FAKE_EXPORT_NAME);
    expect(await bytes(blob)).toBe(FAKE_EXPORT_TEXT);
    expect(button().getAttribute('aria-disabled')).toBeNull();
  });

  it('검색 칸에 친 글이 300ms 안이면 export 질의에 q 가 없다(보낸 검색 기준), 보낸 뒤에는 실린다', async () => {
    const { server } = renderExport();
    await loaded();
    vi.useFakeTimers();
    try {
      type('평가');
      await act(async () => {
        fireEvent.click(button());
        await vi.advanceTimersByTimeAsync(10);
      });
      expect(server.exportQueries()).toEqual([MONTH]);
      await act(() => vi.advanceTimersByTimeAsync(300));
    } finally {
      vi.useRealTimers();
    }
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    await loaded();
    fireEvent.click(button());
    await waitFor(() => expect(server.count('GET /run-logs/export')).toBe(2));
    expect(server.exportQueries()[1]).toEqual({ ...MONTH, q: '평가' });
  });

  it('빠른 두 번(같은 그리기 안) → 요청 하나. 만드는 중엔 「엑셀 만드는 중…」·aria-busy·끔, 누름 → 0', async () => {
    let release!: (response: Response) => void;
    const { server, save } = renderExport(ROWS, {
      prepare: (fake) => {
        release = hold(fake, 'GET /run-logs/export');
      },
    });
    await loaded();
    act(() => {
      button().click();
      button().click();
    });
    await waitFor(() => expect(server.count('GET /run-logs/export')).toBe(1));
    expect(button().textContent).toBe(t.exporting);
    expect(button().getAttribute('aria-busy')).toBe('true');
    expect(button().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(button());
    await new Promise((done) => setTimeout(done, 30));
    expect(server.count('GET /run-logs/export')).toBe(1);
    await act(async () => {
      release(
        new Response(new TextEncoder().encode(FAKE_EXPORT_TEXT), {
          status: 200,
        }),
      );
    });
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(button().textContent).toBe(t.export);
    expect(button().getAttribute('aria-busy')).toBeNull();
  });

  it('0건: 끔(aria-disabled·Tab 에 남음) + 숨은 설명 「내보낼 기록이 없어요」(aria-describedby), 누름 → 요청 0, 옆 글 없음', async () => {
    const { server, save } = renderExport([]);
    await waitFor(() => expect(screen.queryByTestId('empty')).not.toBeNull());
    expect(button().getAttribute('aria-disabled')).toBe('true');
    expect(button().tabIndex).toBe(0);
    const hint = document.getElementById(
      button().getAttribute('aria-describedby')!,
    )!;
    expect(hint.textContent).toBe(t.exportEmpty);
    expect(hint.getAttribute('role')).toBeNull();
    expect(screen.queryByTestId('export-count')).toBeNull();
    fireEvent.click(button());
    await new Promise((done) => setTimeout(done, 30));
    expect(server.count('GET /run-logs/export')).toBe(0);
    expect(save).not.toHaveBeenCalled();
    // 숨은 글은 role 이 없어 화면의 status 는 하나뿐이다.
    expect(screen.getAllByRole('status')).toHaveLength(1);
  });

  it('불러오는 중: 끔, 누름 → 요청 0', async () => {
    let release!: (response: Response) => void;
    const { server } = renderExport(ROWS, {
      prepare: (fake) => {
        release = hold(fake, 'GET /run-logs');
      },
    });
    expect(button().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(button());
    await new Promise((done) => setTimeout(done, 30));
    expect(server.count('GET /run-logs/export')).toBe(0);
    release(json(200, { count: 5, isNext: false, results: ROWS }));
    await loaded();
    expect(button().getAttribute('aria-disabled')).toBeNull();
  });

  it('409 상한 넘음 → 그 글(alert)·다시 켬, 다시 누름 → 글 지우고 다시 요청, 500 → 판 글', async () => {
    const { server, save } = renderExport(ROWS, {
      prepare: (fake) => {
        fake.override['GET /run-logs/export'] = [
          () => refusal(409, 'RUN_LOG_EXPORT_TOO_LARGE'),
          () => refusal(500, 'INTERNAL'),
        ];
      },
    });
    await loaded();
    fireEvent.click(button());
    await waitFor(() => expect(alertText()).toBe(t.exportTooLarge));
    expect(button().getAttribute('aria-disabled')).toBeNull();
    let release!: (response: Response) => void;
    const answers = server.override['GET /run-logs/export'] as (() =>
      Response | Promise<Response>)[];
    const next = answers.shift()!;
    const held = new Promise<Response>((done) => (release = done));
    answers.unshift(() => held);
    fireEvent.click(button());
    await waitFor(() => expect(server.count('GET /run-logs/export')).toBe(2));
    expect(alertText()).toBe('');
    release(await next());
    await waitFor(() => expect(alertText()).toBe(t.exportFailed));
    expect(save).not.toHaveBeenCalled();
  });

  it('실패 글은 거르기를 바꾸면 지운다', async () => {
    const { server } = renderExport(ROWS, {
      prepare: (fake) => {
        fake.override['GET /run-logs/export'] = () => refusal(500, 'INTERNAL');
      },
    });
    await loaded();
    fireEvent.click(button());
    await waitFor(() => expect(alertText()).toBe(t.exportFailed));
    choose(t.status.name, t.status.options.done);
    await waitFor(() => expect(server.count('GET /run-logs')).toBe(2));
    expect(alertText()).toBe('');
  });

  it('옆 글: 「거른 결과 1,234건을 엑셀로 받아요」(서버 count, 쉼표)', async () => {
    renderExport(ROWS, {
      prepare: (fake) => {
        fake.override['GET /run-logs'] = () =>
          json(200, { count: 1234, isNext: true, results: ROWS });
      },
    });
    await loaded();
    expect(screen.getByTestId('export-count').textContent).toBe(
      '거른 결과 1,234건을 엑셀로 받아요',
    );
  });
});

// ⑨ AD-04a 실행 상세 모달(밴드 AD4W): 줄·문서 단추 → GET /run-logs/{id} 한 번 → 칸·단계·실패 줄·파일, 404·실패·늦은 답, 닫으면 초점 되돌림.
describe('AD-04 ⑨ AD-04a 실행 상세 모달(밴드 AD4W)', () => {
  const d = t.detail;
  const DETAIL_ROWS = [
    fakeRunRow(32, { documentName: '지어낸 첫 문서.pdf' }),
    fakeRunRow(31, {
      documentName: '지어낸 둘째 문서.pdf',
      aiSetting: { id: 3, name: 'v3' },
    }),
  ];
  const DETAILS: Record<number, RunLogDetail> = {
    32: fakeRunDetail(32, { documentName: '지어낸 첫 문서.pdf' }),
    31: fakeRunDetail(31, {
      documentName: '지어낸 둘째 문서.pdf',
      aiSetting: { id: 3, name: 'v3' },
    }),
  };

  function setupDetail(
    details: Record<number, RunLogDetail> = DETAILS,
    {
      rows = DETAIL_ROWS,
      prepare = () => {},
    }: { rows?: RunLogRow[]; prepare?: (server: FakeServer) => void } = {},
  ) {
    const server = fakeRunLogServer(rows, METRICS, { baseUrl: BASE, details });
    prepare(server);
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    render(<RunsScreen port={port} now={() => NOW} />);
    return { server };
  }
  const dialog = () => screen.queryByTestId('run-detail');
  const opener = (id: number) =>
    document.querySelector<HTMLElement>(
      `tr[data-run-id="${id}"] [data-run-open]`,
    )!;
  const clickAt = (id: number) => fireEvent.click(cellsOf(id)[0]!);
  const ready = () =>
    waitFor(() => expect(screen.getByTestId('run-fields')).toBeTruthy());
  const detailPaths = (server: FakeServer) =>
    server.detailCalls().map((call) => call.path);
  const stepRow = (name: string) =>
    [...document.querySelectorAll(`[data-step="${name}"] td`)].map(
      (cell) => cell.textContent,
    );

  it('1 둘째 줄 시각 칸 누름 → GET /run-logs/31 하나·질의 0 → 제목·배지·칸 글', async () => {
    const { server } = setupDetail();
    await loaded();
    clickAt(31);
    await ready();
    expect(server.detailCalls()).toEqual([{ path: '/run-logs/31', query: {} }]);
    const box = within(dialog()!);
    expect(box.getByRole('heading', { name: d.title })).toBeTruthy();
    const status = dialog()!.querySelector('[data-status]')!;
    expect(status.getAttribute('data-status')).toBe('done');
    expect(status.textContent).toBe('완료');
    expect(box.getByText('지어낸 둘째 문서.pdf')).toBeTruthy();
    expect(screen.getByTestId('module-flow').textContent).toBe('그린워싱 · E0');
    expect(screen.getByTestId('ai-setting').textContent).toBe(
      'AI 설정 그린워싱 v3',
    );
    expect(screen.getByTestId('times').textContent).toBe(
      '2026-10-15 14:20 시작 · 14:28 끝',
    );
    expect(screen.getByTestId('total').textContent).toBe(
      '8분 05초 · 토큰 108,100 · 비용(추정) $0.58',
    );
    expect(box.getByText('담당자 가')).toBeTruthy();
  });

  it('2 문서 단추(이름 「{문서} 결과 보기」, title 없음)에 초점 + 누름(Enter 의 click) → 요청 하나', async () => {
    const { server } = setupDetail();
    await loaded();
    const button = screen.getByRole('button', {
      name: d.openLabel('지어낸 첫 문서.pdf'),
    });
    expect(button).toBe(opener(32));
    expect(button.hasAttribute('title')).toBe(false);
    button.focus();
    fireEvent.click(button);
    await ready();
    expect(detailPaths(server)).toEqual(['/run-logs/32']);
  });

  it('3 단계 기록 있음: 단계 차례·판 이름·배지·「42초」·쉼표·0 토큰 「–」·표 아래 글·파일 이름(링크·단추 0)', async () => {
    setupDetail();
    await loaded();
    clickAt(31);
    await ready();
    const names = [...document.querySelectorAll('[data-step]')].map(
      (row) => row.querySelector('td')!.textContent,
    );
    expect(names).toEqual([
      '글 뽑기',
      '색인',
      '판정',
      '낱말 세기',
      '위치 찾기',
      '결과 만들기',
    ]);
    expect(stepRow('extract')).toEqual(['글 뽑기', '완료', '42초', '–', '–']);
    expect(stepRow('index')).toEqual([
      '색인',
      '완료',
      '58초',
      '21,300',
      '$0.01',
    ]);
    expect(stepRow('judge')).toEqual([
      '판정',
      '완료',
      '5분 31초',
      '86,800',
      '$0.57',
    ]);
    const badge = document.querySelector(
      '[data-step="judge"] [data-step-status]',
    )!;
    expect(badge.getAttribute('data-step-status')).toBe('done');
    expect(badge.className).toContain('support-success');
    expect(screen.queryByTestId('no-step-usage')).toBeNull();
    expect(screen.getByTestId('step-usage-note').textContent).toBe(
      d.stepUsageNote,
    );
    const files = screen.getByTestId('run-files');
    expect(
      [...files.querySelectorAll('li')].map((li) => li.textContent),
    ).toEqual(['지어낸 결과 31.xlsx', '지어낸 표시 31.pdf']);
    expect(files.querySelector('a, button, [href]')).toBeNull();
    expect(dialog()!.querySelector('a[href]')).toBeNull();
    expect(screen.queryByTestId('run-failure')).toBeNull();
  });

  it('3-2 처리 중 실행: 단계 배지 처리 중 orange · 대기 grey, 끝 시각 없음 → 「… 시작」만', async () => {
    const steps = fakeRunDetail(31).steps.map((step, index) =>
      index < 2 ? step
      : index === 2 ?
        {
          ...step,
          status: 'running' as const,
          finishedAt: null,
          durationSec: null,
          tokens: 14_800,
          costUsd: 0.09,
        }
      : {
          ...step,
          status: 'pending' as const,
          startedAt: null,
          finishedAt: null,
          durationSec: null,
          tokens: null,
          costUsd: null,
        },
    );
    setupDetail({
      31: fakeRunDetail(31, {
        status: 'processing',
        finishedAt: null,
        durationSec: null,
        steps,
      }),
    });
    await loaded();
    clickAt(31);
    await ready();
    const badgeOf = (name: string) =>
      document.querySelector(`[data-step="${name}"] [data-step-status]`)!;
    expect(badgeOf('judge').getAttribute('data-step-status')).toBe('running');
    expect(badgeOf('judge').textContent).toBe('처리 중');
    expect(badgeOf('judge').className).toContain('support-orange');
    expect(badgeOf('locate').getAttribute('data-step-status')).toBe('pending');
    expect(badgeOf('locate').textContent).toBe('대기');
    expect(badgeOf('locate').className).toContain('bg-background-tertiary');
    expect(stepRow('judge')).toEqual([
      '판정',
      '처리 중',
      '–',
      '14,800',
      '$0.09',
    ]);
    expect(stepRow('locate')).toEqual(['위치 찾기', '대기', '–', '–', '–']);
    expect(screen.getByTestId('times').textContent).toBe(
      '2026-10-15 14:20 시작',
    );
    expect(
      dialog()!.querySelector('[data-status]')!.getAttribute('data-status'),
    ).toBe('processing');
  });

  it('3-3 단계 0개 → 단계 표 한 줄 「–」, 결과 파일 0개 → 「–」(목록 없음)', async () => {
    setupDetail({ 31: fakeRunDetail(31, { steps: [], files: [] }) });
    await loaded();
    clickAt(31);
    await ready();
    expect(document.querySelectorAll('[data-step]')).toHaveLength(0);
    const body = screen.getByTestId('run-steps').querySelectorAll('tbody tr');
    expect(body).toHaveLength(1);
    expect(body[0]!.textContent).toBe('–');
    const files = screen.getByTestId('run-files');
    expect(files.querySelector('ul')).toBeNull();
    expect(files.querySelector('p')!.textContent).toBe('–');
  });

  it('4 stepUsageRecorded 거짓: 안내 줄·토큰·비용 칸 모두 「–」·시간은 값·합계 값·표 아래 글 없음', async () => {
    setupDetail({ 31: fakeRunDetail(31, { stepUsageRecorded: false }) });
    await loaded();
    clickAt(31);
    await ready();
    expect(screen.getByTestId('no-step-usage').textContent).toBe(d.noStepUsage);
    expect(stepRow('index')).toEqual(['색인', '완료', '58초', '–', '–']);
    expect(stepRow('judge')).toEqual(['판정', '완료', '5분 31초', '–', '–']);
    expect(screen.getByTestId('total').textContent).toBe(
      '8분 05초 · 토큰 108,100 · 비용(추정) $0.58',
    );
    expect(screen.queryByTestId('step-usage-note')).toBeNull();
  });

  it('5 실패 줄: 「판정 단계에서 멈췄어요 · 오류 코드 step_error」·단계 null·코드 null·모르는 단계 이름', async () => {
    const failed = (overrides: Partial<RunLogDetail>) =>
      fakeRunDetail(31, { status: 'failed', ...overrides });
    const cases: [Partial<RunLogDetail>, string][] = [
      [
        { failedStep: 'judge', errorCode: 'step_error' },
        '판정 단계에서 멈췄어요 · 오류 코드 step_error',
      ],
      [
        { failedStep: null, errorCode: 'worker_lost' },
        '단계 밖에서 멈췄어요 · 오류 코드 worker_lost',
      ],
      [{ failedStep: 'judge', errorCode: null }, '판정 단계에서 멈췄어요'],
      [
        { failedStep: 'calculate', errorCode: 'step_error' },
        'calculate 단계에서 멈췄어요 · 오류 코드 step_error',
      ],
    ];
    for (const [overrides, text] of cases) {
      setupDetail({ 31: failed(overrides) });
      await loaded();
      clickAt(31);
      await ready();
      expect(screen.getByTestId('run-failure').textContent).toBe(text);
      expect(
        dialog()!.querySelector('[data-status]')!.getAttribute('data-status'),
      ).toBe('failed');
      cleanup();
    }
  });

  it('6 문서 두 칸 null → 회색 「–」(실패 상자 아님)', async () => {
    setupDetail({
      31: fakeRunDetail(31, { documentId: null, documentName: null }),
    });
    await loaded();
    clickAt(31);
    await ready();
    const missing = dialog()!.querySelector('[data-document-missing]')!;
    expect(missing.textContent).toBe('–');
    expect(missing.className).toContain('text-text-tertiary');
    expect(screen.queryByTestId('run-detail-failure')).toBeNull();
  });

  it('7 404 → 「이 실행을 찾을 수 없어요」·[다시 시도] 없음 · 500 → [다시 시도] → 같은 id 요청 하나 더 → 값', async () => {
    setupDetail({});
    await loaded();
    clickAt(31);
    await waitFor(() =>
      expect(screen.getByTestId('run-not-found').textContent).toBe(d.notFound),
    );
    expect(
      within(dialog()!).queryByRole('button', { name: t.retry }),
    ).toBeNull();
    expect(
      within(dialog()!).getByRole('button', { name: d.close }),
    ).toBeTruthy();
    cleanup();

    const { server } = setupDetail(DETAILS, {
      prepare: (fake) => {
        fake.override['GET /run-logs/31'] = [() => json(500, undefined)];
      },
    });
    await loaded();
    clickAt(31);
    await waitFor(() =>
      expect(screen.getByTestId('run-detail-failure')).toBeTruthy(),
    );
    expect(screen.getByTestId('run-detail-failure').textContent).toContain(
      d.failed,
    );
    fireEvent.click(within(dialog()!).getByRole('button', { name: t.retry }));
    await ready();
    expect(detailPaths(server)).toEqual(['/run-logs/31', '/run-logs/31']);
  });

  it('8 불러오는 동안 300ms 안에는 스켈레톤 없음, 뒤에는 있음(제목·[닫기] 는 늘)', async () => {
    let release!: (response: Response) => void;
    setupDetail(DETAILS, {
      prepare: (server) => {
        release = hold(server, 'GET /run-logs/31');
      },
    });
    await loaded();
    vi.useFakeTimers();
    try {
      clickAt(31);
      await act(() => vi.advanceTimersByTimeAsync(10));
      expect(dialog()).not.toBeNull();
      expect(within(dialog()!).queryByTestId('load-skeleton')).toBeNull();
      expect(
        within(dialog()!).getByRole('button', { name: d.close }),
      ).toBeTruthy();
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(within(dialog()!).getByTestId('load-skeleton').textContent).toBe(
        d.loading,
      );
      await act(async () => {
        release(json(200, DETAILS[31]));
        await vi.advanceTimersByTimeAsync(10);
      });
      expect(within(dialog()!).queryByTestId('load-skeleton')).toBeNull();
      expect(screen.getByTestId('run-fields')).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });

  it('9 [닫기]·Escape → 모달 없음·초점 = 그 줄의 문서 단추(마우스로 줄을 연 때도)', async () => {
    setupDetail();
    await loaded();
    clickAt(31);
    await ready();
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener(31)));

    clickAt(32);
    await ready();
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
    await waitFor(() => expect(dialog()).toBeNull());
    await waitFor(() => expect(document.activeElement).toBe(opener(32)));
  });

  it('10 닫고 같은 줄을 다시 열면 요청 둘째(캐시 없음)', async () => {
    const { server } = setupDetail();
    await loaded();
    clickAt(31);
    await ready();
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    clickAt(31);
    await ready();
    expect(detailPaths(server)).toEqual(['/run-logs/31', '/run-logs/31']);
  });

  it('11 늦은 답은 버린다: A 열기(보류) → 닫기 → B 열기 → A 답 → 글은 B', async () => {
    let release!: (response: Response) => void;
    setupDetail(DETAILS, {
      prepare: (server) => {
        release = hold(server, 'GET /run-logs/32');
      },
    });
    await loaded();
    clickAt(32);
    await waitFor(() => expect(dialog()).not.toBeNull());
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    clickAt(31);
    await ready();
    expect(within(dialog()!).getByText('지어낸 둘째 문서.pdf')).toBeTruthy();
    await act(async () => {
      release(json(200, DETAILS[32]));
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(screen.getByTestId('run-fields')).toBeTruthy();
    expect(within(dialog()!).getByText('지어낸 둘째 문서.pdf')).toBeTruthy();
    expect(within(dialog()!).queryByText('지어낸 첫 문서.pdf')).toBeNull();
  });

  it('12 열고 닫아도 목록·지표 요청 수는 그대로', async () => {
    const { server } = setupDetail();
    await loaded();
    const before = [
      server.count('GET /run-logs'),
      server.count('GET /run-logs/metrics'),
    ];
    clickAt(31);
    await ready();
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    expect([
      server.count('GET /run-logs'),
      server.count('GET /run-logs/metrics'),
    ]).toEqual(before);
    expect(before).toEqual([1, 1]);
  });

  // 키보드 줄 열기(밴드 TB1 — sid:MARC-ENT-599 규칙 3·4, sid:MARC-ISSUE-605 ①).
  describe('13 줄 키보드 열기(밴드 TB1)', () => {
    const rowOf = (id: number) =>
      document.querySelector<HTMLElement>(`tr[data-run-id="${id}"]`)!;
    const closeDialog = async () => {
      fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
      await waitFor(() => expect(dialog()).toBeNull());
    };

    it('a 줄은 Tab 자리(tabIndex 0)·이름 = 문서 단추 이름(새 문구 0)', async () => {
      setupDetail(DETAILS, {
        rows: [
          ...DETAIL_ROWS,
          fakeRunRow(30, { documentId: null, documentName: null }),
        ],
      });
      await loaded();
      for (const id of [32, 31, 30]) {
        expect(rowOf(id).tabIndex).toBe(0);
        expect(rowOf(id).getAttribute('aria-label')).toBe(
          opener(id).getAttribute('aria-label'),
        );
      }
      expect(rowOf(31).getAttribute('aria-label')).toBe(
        d.openLabel('지어낸 둘째 문서.pdf'),
      );
    });

    it('b 줄에 초점 + Enter → 요청 하나 → 닫으면 초점이 그 줄로', async () => {
      const { server } = setupDetail();
      await loaded();
      rowOf(31).focus();
      fireEvent.keyDown(rowOf(31), { key: 'Enter' });
      await ready();
      expect(detailPaths(server)).toEqual(['/run-logs/31']);
      await closeDialog();
      await waitFor(() => expect(document.activeElement).toBe(rowOf(31)));
    });

    it('c 줄에 초점 + Space → 요청 하나(쪽 내림 막음) → Escape 로 닫으면 초점이 그 줄로', async () => {
      const { server } = setupDetail();
      await loaded();
      rowOf(32).focus();
      const notPrevented = fireEvent.keyDown(rowOf(32), { key: ' ' });
      expect(notPrevented).toBe(false);
      await ready();
      expect(detailPaths(server)).toEqual(['/run-logs/32']);
      fireEvent.keyDown(document.activeElement!, { key: 'Escape' });
      await waitFor(() => expect(dialog()).toBeNull());
      await waitFor(() => expect(document.activeElement).toBe(rowOf(32)));
    });

    it('d 문서 단추 클릭(줄로 번짐) → 요청 하나·창 하나 → 닫으면 초점이 단추로', async () => {
      const { server } = setupDetail();
      await loaded();
      fireEvent.click(opener(31));
      await ready();
      expect(detailPaths(server)).toEqual(['/run-logs/31']);
      expect(screen.getAllByTestId('run-detail')).toHaveLength(1);
      await closeDialog();
      await waitFor(() => expect(document.activeElement).toBe(opener(31)));
    });

    it('e 문서 단추 위 Enter·Space 는 단추 몫: 줄 onKeyDown 은 열지 않는다', async () => {
      const { server } = setupDetail();
      await loaded();
      opener(31).focus();
      fireEvent.keyDown(opener(31), { key: 'Enter' });
      fireEvent.keyDown(opener(31), { key: ' ' });
      await new Promise((done) => setTimeout(done, 50));
      expect(dialog()).toBeNull();
      expect(detailPaths(server)).toEqual([]);
    });

    it('f 줄의 다른 키(Tab·a)는 열지 않는다', async () => {
      const { server } = setupDetail();
      await loaded();
      rowOf(31).focus();
      fireEvent.keyDown(rowOf(31), { key: 'Tab' });
      fireEvent.keyDown(rowOf(31), { key: 'a' });
      await new Promise((done) => setTimeout(done, 50));
      expect(dialog()).toBeNull();
      expect(detailPaths(server)).toEqual([]);
    });
  });

  // 문서 없는 줄(밴드 ND1W — sid:MARC-ISSUE-292): 목록 가드가 null 두 칸을 받고, 문서 칸은 회색 「–」·단추 이름은 시각.
  const NO_DOCUMENT_ROWS = [
    fakeRunRow(32, { documentName: '지어낸 첫 문서.pdf' }),
    fakeRunRow(31, { documentId: null, documentName: null }),
  ];
  const NO_DOCUMENT_DETAILS: Record<number, RunLogDetail> = {
    ...DETAILS,
    31: fakeRunDetail(31, { documentId: null, documentName: null }),
  };

  it('8 문서 없는 줄 → 문서 칸 회색 「–」·title 없음·단추 이름 「<시각> 실행 결과 보기」, 다른 줄은 그대로', async () => {
    setupDetail(NO_DOCUMENT_DETAILS, { rows: NO_DOCUMENT_ROWS });
    await loaded();
    expect(rowIds()).toEqual([32, 31]);
    expect(screen.queryByText(t.failed)).toBeNull();
    const at = cellsOf(31)[0]!.textContent!;
    expect(at).toBe('2026-10-15 14:20');
    const button = screen.getByRole('button', {
      name: d.openLabelNoDocument(at),
    });
    expect(button).toBe(opener(31));
    expect(button.textContent).toBe('–');
    const missing = button.querySelector('[data-document-missing]')!;
    expect(missing.className).toContain('text-text-tertiary');
    expect(button.querySelector('[title]')).toBeNull();
    expect(button.hasAttribute('title')).toBe(false);
    const other = screen.getByRole('button', {
      name: d.openLabel('지어낸 첫 문서.pdf'),
    });
    expect(other).toBe(opener(32));
    expect(other.querySelector('[data-document-missing]')).toBeNull();
    expect(other.querySelector('[title]')!.getAttribute('title')).toBe(
      '지어낸 첫 문서.pdf',
    );
  });

  it('9 문서 없는 줄 누름 → 상세 요청 하나·모달 문서 칸 「–」 · 단추 초점 + 누름(Enter 의 click) → 요청 하나', async () => {
    const { server } = setupDetail(NO_DOCUMENT_DETAILS, {
      rows: NO_DOCUMENT_ROWS,
    });
    await loaded();
    clickAt(31);
    await ready();
    expect(server.detailCalls()).toEqual([{ path: '/run-logs/31', query: {} }]);
    expect(
      dialog()!.querySelector('[data-document-missing]')!.textContent,
    ).toBe('–');
    cleanup();

    const again = setupDetail(NO_DOCUMENT_DETAILS, { rows: NO_DOCUMENT_ROWS });
    await loaded();
    const button = opener(31);
    button.focus();
    fireEvent.click(button);
    await ready();
    expect(detailPaths(again.server)).toEqual(['/run-logs/31']);
    expect(
      dialog()!.querySelector('[data-document-missing]')!.textContent,
    ).toBe('–');
  });
});

// AD-04a 결과 파일 [내려받기](밴드 RF1W, 결정 MARC-ENT-395): step null 줄만 단추, 한 번에 하나(처리기가 막음), 실패 글 하나, 늦은 답은 버림.
describe('AD-04 ⑩ AD-04a 결과 파일 [내려받기](밴드 RF1W)', () => {
  const d = t.detail;
  const OUT_A = '지어낸 결과 41.xlsx';
  const OUT_B = '지어낸 표시 41.pdf';
  const MID = '지어낸 중간 41.json';
  const ROWS_41 = [
    fakeRunRow(42, { documentName: '지어낸 넷째 문서.pdf' }),
    fakeRunRow(41, { documentName: '지어낸 셋째 문서.pdf' }),
  ];
  const DETAILS_41: Record<number, RunLogDetail> = {
    41: fakeRunDetail(41, {
      documentName: '지어낸 셋째 문서.pdf',
      files: [
        { name: OUT_A, step: null, mediaType: 'application/pdf', sizeBytes: 1 },
        {
          name: MID,
          step: 'judge',
          mediaType: 'application/json',
          sizeBytes: 1,
        },
        { name: OUT_B, step: null, mediaType: 'application/pdf', sizeBytes: 1 },
      ],
    }),
    42: fakeRunDetail(42, {
      documentName: '지어낸 넷째 문서.pdf',
      files: [
        {
          name: '지어낸 결과 42.xlsx',
          step: null,
          mediaType: 'application/pdf',
          sizeBytes: 1,
        },
      ],
    }),
  };

  function setupFiles(prepare: (server: FakeServer) => void = () => {}) {
    const server = fakeRunLogServer(ROWS_41, METRICS, {
      baseUrl: BASE,
      details: DETAILS_41,
    });
    prepare(server);
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    const save = vi.fn<(blob: Blob, fileName: string) => void>();
    render(<RunsScreen port={port} now={() => NOW} save={save} />);
    return { server, save };
  }
  const dialog = () => screen.queryByTestId('run-detail');
  const openRun = async (id: number) => {
    fireEvent.click(cellsOf(id)[0]!);
    await waitFor(() => expect(screen.getByTestId('run-fields')).toBeTruthy());
  };
  const downloads = () => [
    ...document.querySelectorAll<HTMLElement>('[data-file-download]'),
  ];
  const downloadOf = (name: string) =>
    within(dialog()!).getByRole('button', { name: d.downloadLabel(name) });
  const fileError = () => screen.getByTestId('file-error').textContent;
  const settle = () =>
    act(async () => {
      await new Promise((done) => setTimeout(done, 20));
    });

  it('① step null 줄만 [내려받기](단계 중간 파일 줄은 이름만), 이름 「{파일} 내려받기」, 처음엔 켬·실패 글 없음', async () => {
    setupFiles();
    await loaded();
    await openRun(41);
    const items = [...screen.getByTestId('run-files').querySelectorAll('li')];
    expect(items.map((li) => li.querySelector('span')!.textContent)).toEqual([
      OUT_A,
      MID,
      OUT_B,
    ]);
    expect(items.map((li) => li.querySelectorAll('button').length)).toEqual([
      1, 0, 1,
    ]);
    expect(downloads()).toEqual([downloadOf(OUT_A), downloadOf(OUT_B)]);
    expect(downloadOf(OUT_A).textContent).toBe(d.download);
    for (const button of downloads())
      expect(button.hasAttribute('aria-disabled')).toBe(false);
    expect(fileError()).toBe('');
  });

  it('② 누르면 요청 하나(경로 = 그 실행·그 이름, 질의 0)·save 가 서버 이름(Content-Disposition)과 받은 바이트로 한 번', async () => {
    const { server, save } = setupFiles();
    await loaded();
    await openRun(41);
    fireEvent.click(downloadOf(OUT_B));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(server.fileCalls()).toEqual([
      { path: runFilePath(41, OUT_B), query: {} },
    ]);
    const [blob, fileName] = save.mock.calls[0]!;
    expect(fileName).toBe(fakeServedName(OUT_B));
    expect(new TextDecoder().decode(await blob.arrayBuffer())).toBe(
      FAKE_FILE_TEXT,
    );
    expect(fileError()).toBe('');
    expect(downloadOf(OUT_B).hasAttribute('aria-disabled')).toBe(false);
  });

  it('③ 받는 중: 모든 [내려받기] 끔(aria-disabled·opacity)·누른 줄 aria-busy, 다른 줄·같은 줄을 눌러도 요청 0 → 답 뒤 다시 켬', async () => {
    let release!: (response: Response) => void;
    const { server, save } = setupFiles((fake) => {
      release = hold(fake, `GET ${runFilePath(41, OUT_A)}`);
    });
    await loaded();
    await openRun(41);
    fireEvent.click(downloadOf(OUT_A));
    fireEvent.click(downloadOf(OUT_A));
    await waitFor(() =>
      expect(downloadOf(OUT_A).getAttribute('aria-busy')).toBe('true'),
    );
    for (const button of downloads()) {
      expect(button.getAttribute('aria-disabled')).toBe('true');
      expect(button.className).toContain('opacity-40');
    }
    expect(downloadOf(OUT_B).hasAttribute('aria-busy')).toBe(false);
    fireEvent.click(downloadOf(OUT_B));
    fireEvent.click(downloadOf(OUT_A));
    await settle();
    expect(server.fileCalls()).toHaveLength(1);
    await act(async () => {
      release(
        new Response(new TextEncoder().encode(FAKE_FILE_TEXT), {
          status: 200,
          headers: { 'Content-Type': 'application/octet-stream' },
        }),
      );
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0]![1]).toBe(OUT_A);
    for (const button of downloads())
      expect(button.hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(downloadOf(OUT_B));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    expect(server.fileCalls().map((call) => call.path)).toEqual([
      runFilePath(41, OUT_A),
      runFilePath(41, OUT_B),
    ]);
  });

  it('④ 실패(503) → 「파일을 받지 못했어요. 다시 시도해 주세요.」(alert)·다시 켬 → 다시 누름 → 요청 하나·성공하면 글 사라짐', async () => {
    const { server, save } = setupFiles((fake) => {
      fake.override[`GET ${runFilePath(41, OUT_A)}`] = [
        () => refusal(503, 'storage_unavailable'),
      ];
    });
    await loaded();
    await openRun(41);
    fireEvent.click(downloadOf(OUT_A));
    await waitFor(() => expect(fileError()).toBe(d.downloadFailed));
    expect(screen.getByTestId('file-error').getAttribute('role')).toBe('alert');
    expect(save).not.toHaveBeenCalled();
    expect(downloadOf(OUT_A).hasAttribute('aria-disabled')).toBe(false);
    fireEvent.click(downloadOf(OUT_A));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(server.fileCalls()).toHaveLength(2);
    expect(fileError()).toBe('');
  });

  it('④-2 단계 중간 파일 이름이 와도(서버 404 RUN_FILE_NOT_FOUND) 404 글 「파일을 찾을 수 없어요」(AD4P)', async () => {
    setupFiles((fake) => {
      fake.override[`GET ${runFilePath(41, OUT_A)}`] = () =>
        refusal(404, 'RUN_FILE_NOT_FOUND');
    });
    await loaded();
    await openRun(41);
    fireEvent.click(downloadOf(OUT_A));
    await waitFor(() => expect(fileError()).toBe(d.fileNotFound));
  });

  it('⑤ 받는 중 모달 닫음 → 다른 실행 엶 → 늦은 답(성공·실패)에 save 0·실패 글 0, 새 모달 단추는 켬', async () => {
    let releaseOk!: (response: Response) => void;
    let releaseFail!: (response: Response) => void;
    const { server, save } = setupFiles((fake) => {
      releaseOk = hold(fake, `GET ${runFilePath(41, OUT_A)}`);
      releaseFail = hold(fake, `GET ${runFilePath(41, OUT_B)}`);
    });
    await loaded();
    await openRun(41);
    fireEvent.click(downloadOf(OUT_A));
    await waitFor(() =>
      expect(downloadOf(OUT_A).getAttribute('aria-busy')).toBe('true'),
    );
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    await openRun(42);
    await act(async () => {
      releaseOk(
        new Response(new TextEncoder().encode(FAKE_FILE_TEXT), { status: 200 }),
      );
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(save).not.toHaveBeenCalled();
    expect(fileError()).toBe('');
    expect(
      downloadOf('지어낸 결과 42.xlsx').hasAttribute('aria-disabled'),
    ).toBe(false);

    // 같은 실행을 다시 연 뒤 앞 차례의 실패 답 — 글 0.
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    await openRun(41);
    fireEvent.click(downloadOf(OUT_B));
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());
    await openRun(41);
    await act(async () => {
      releaseFail(refusal(503, 'storage_unavailable'));
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(fileError()).toBe('');
    expect(save).not.toHaveBeenCalled();
    expect(server.fileCalls()).toHaveLength(2);
  });
});

describe('AD-04 ⑪ 같이 시작·이어서·결과 파일 다듬기(밴드 AD4P — 캔버스 v138, 디자인 6c 답 10-25)', () => {
  const d = t.detail;
  const LAUNCH = {
    launchKey: '지어낸-묶음-열쇠',
    launchFirstRunId: 101,
    launchSize: 3,
  };
  const OUT = '지어낸 결과 51.xlsx';
  const MID = '지어낸 판정 51.jsonl';
  const LAUNCH_ROWS = [
    fakeRunRow(103, {
      ...LAUNCH,
      launchIndex: 3,
      documentName: '지어낸 셋.pdf',
    }),
    fakeRunRow(102, {
      ...LAUNCH,
      launchIndex: 2,
      documentName: '지어낸 둘.pdf',
    }),
    fakeRunRow(101, {
      ...LAUNCH,
      launchIndex: 1,
      documentName: '지어낸 하나.pdf',
    }),
    fakeRunRow(52, {
      launchKey: '지어낸-혼자-열쇠',
      launchFirstRunId: 52,
      launchIndex: 1,
      launchSize: 1,
      resumedFromRunId: 88,
      documentName: '지어낸 이어서.pdf',
    }),
    fakeRunRow(51, { documentName: '지어낸 보통.pdf' }),
  ];
  const fileList = (failed = false) =>
    fakeRunDetail(51, {
      documentName: '지어낸 보통.pdf',
      ...(failed ? { status: 'failed' as const, failedStep: 'judge' } : {}),
      files: [
        {
          name: OUT,
          step: 'report',
          mediaType: 'application/pdf',
          sizeBytes: 1,
        },
        {
          name: MID,
          step: 'judge',
          mediaType: 'application/json',
          sizeBytes: 1,
        },
        { name: OUT, step: null, mediaType: 'application/pdf', sizeBytes: 1 },
      ],
    });
  const DETAILS: Record<number, RunLogDetail> = {
    102: fakeRunDetail(102, {
      ...LAUNCH,
      launchIndex: 2,
      documentName: '지어낸 둘.pdf',
    }),
    52: fakeRunDetail(52, {
      launchKey: '지어낸-혼자-열쇠',
      launchFirstRunId: 52,
      launchIndex: 1,
      launchSize: 1,
      resumedFromRunId: 88,
      documentName: '지어낸 이어서.pdf',
    }),
    51: fileList(),
  };

  function setupLaunch(
    details: Record<number, RunLogDetail> = DETAILS,
    prepare: (server: FakeServer) => void = () => {},
  ) {
    const server = fakeRunLogServer(LAUNCH_ROWS, METRICS, {
      baseUrl: BASE,
      details,
    });
    prepare(server);
    const port = createRunLogServerPort({
      api: createApi({ baseUrl: BASE, fetch: server.send }),
    });
    const save = vi.fn<(blob: Blob, fileName: string) => void>();
    render(<RunsScreen port={port} now={() => NOW} save={save} />);
    return { server, save };
  }
  const dialog = () => screen.queryByTestId('run-detail');
  const openRun = async (id: number) => {
    fireEvent.click(cellsOf(id)[0]!);
    await waitFor(() => expect(screen.getByTestId('run-fields')).toBeTruthy());
  };
  const markOf = (id: number, attr: string) =>
    document.querySelector(`tr[data-run-id="${id}"] [${attr}]`)?.textContent ??
    null;
  const fileError = () => screen.getByTestId('file-error').textContent;

  it('① 표: launchSize 3 줄에 「같이 시작 #101 · k/3」 회색 배지, size 1·null 줄엔 0 · resumedFromRunId 88 줄에 「이어서 #88」, null 줄엔 0 · 문서 단추 이름 그대로', async () => {
    setupLaunch();
    await loaded();
    expect(markOf(103, 'data-launch')).toBe('같이 시작 #101 · 3/3');
    expect(markOf(102, 'data-launch')).toBe('같이 시작 #101 · 2/3');
    expect(markOf(101, 'data-launch')).toBe('같이 시작 #101 · 1/3');
    expect(markOf(52, 'data-launch')).toBeNull();
    expect(markOf(51, 'data-launch')).toBeNull();
    expect(markOf(52, 'data-resumed')).toBe('이어서 #88');
    expect(markOf(102, 'data-resumed')).toBeNull();
    expect(markOf(51, 'data-resumed')).toBeNull();
    expect(
      document.querySelector('tr[data-run-id="102"] [data-launch]')!.className,
    ).toContain('bg-background-tertiary');
    expect(
      document
        .querySelector('tr[data-run-id="102"] [data-run-open]')!
        .getAttribute('aria-label'),
    ).toBe(d.openLabel('지어낸 둘.pdf'));
    expect(
      document
        .querySelector('tr[data-run-id="52"] [data-run-open]')!
        .getAttribute('aria-label'),
    ).toBe(d.openLabel('지어낸 이어서.pdf'));
  });

  it('② 상세: 같은 이름 둘(중간 + 흐름 출력) → li 하나·[내려받기] 하나 · 이름 다른 중간 파일은 단추 없는 줄로 남음', async () => {
    setupLaunch();
    await loaded();
    await openRun(51);
    const items = [...screen.getByTestId('run-files').querySelectorAll('li')];
    expect(items.map((li) => li.querySelector('span')!.textContent)).toEqual([
      MID,
      OUT,
    ]);
    expect(items.map((li) => li.querySelectorAll('button').length)).toEqual([
      0, 1,
    ]);
    expect(
      within(dialog()!).getByRole('button', { name: d.downloadLabel(OUT) }),
    ).toBeTruthy();
  });

  it('③ 상세: 실패 실행 → [내려받기] 0, 이름 줄은 보임', async () => {
    setupLaunch({ ...DETAILS, 51: fileList(true) });
    await loaded();
    await openRun(51);
    const items = [...screen.getByTestId('run-files').querySelectorAll('li')];
    expect(items.map((li) => li.textContent)).toEqual([MID, OUT]);
    expect(document.querySelectorAll('[data-file-download]')).toHaveLength(0);
    expect(screen.getByTestId('run-failure')).toBeTruthy();
  });

  it.each([['RUN_NOT_FOUND'], ['RUN_FILE_NOT_FOUND']])(
    '④ 받기 404 %s → 「파일을 찾을 수 없어요」(alert)·단추 켬 → 다시 누름 → 요청 하나 더·성공하면 글 사라짐',
    async (code) => {
      const { server, save } = setupLaunch(DETAILS, (fake) => {
        fake.override[`GET ${runFilePath(51, OUT)}`] = [
          () => refusal(404, code),
        ];
      });
      await loaded();
      await openRun(51);
      const button = () =>
        within(dialog()!).getByRole('button', { name: d.downloadLabel(OUT) });
      fireEvent.click(button());
      await waitFor(() => expect(fileError()).toBe(d.fileNotFound));
      expect(screen.getByTestId('file-error').getAttribute('role')).toBe(
        'alert',
      );
      expect(save).not.toHaveBeenCalled();
      expect(button().hasAttribute('aria-disabled')).toBe(false);
      fireEvent.click(button());
      await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
      expect(server.fileCalls()).toHaveLength(2);
      expect(fileError()).toBe('');
    },
  );

  it('④-2 받기 503 → 「파일을 받지 못했어요. 다시 시도해 주세요.」(404 글 아님)', async () => {
    setupLaunch(DETAILS, (fake) => {
      fake.override[`GET ${runFilePath(51, OUT)}`] = () =>
        refusal(503, 'STORAGE_UNAVAILABLE');
    });
    await loaded();
    await openRun(51);
    fireEvent.click(
      within(dialog()!).getByRole('button', { name: d.downloadLabel(OUT) }),
    );
    await waitFor(() => expect(fileError()).toBe(d.downloadFailed));
  });

  it('⑤ 상세: launchSize 3 → 칸 목록 맨 위 「같이 시작」 칸 「#101 · 2/3」 + 「같이 시작한 실행 2개」(누름 동작 0) · size 1 → 같이 시작 칸 0', async () => {
    setupLaunch();
    await loaded();
    await openRun(102);
    const fields = screen.getByTestId('run-fields');
    expect(fields.querySelector('dt')!.textContent).toBe(d.fields.launch);
    expect(screen.getByTestId('run-launch').textContent).toBe('#101 · 2/3');
    expect(screen.getByTestId('run-launch-siblings').textContent).toBe(
      '같이 시작한 실행 2개',
    );
    const launchRow = screen.getByTestId('run-launch').closest('div')!;
    expect(launchRow.querySelector('a, button, [href], [role]')).toBeNull();
    expect(screen.queryByTestId('run-resumed')).toBeNull();
    fireEvent.click(within(dialog()!).getByRole('button', { name: d.close }));
    await waitFor(() => expect(dialog()).toBeNull());

    await openRun(52);
    expect(screen.queryByTestId('run-launch')).toBeNull();
    expect(screen.queryByTestId('run-launch-siblings')).toBeNull();
    expect(
      screen.getByTestId('run-fields').querySelector('dt')!.textContent,
    ).toBe(d.fields.resumed);
    expect(screen.getByTestId('run-resumed').textContent).toBe('#88');
  });

  it('⑤-2 묶음·이어서 없는 실행 → 첫 칸은 「문서」 그대로', async () => {
    setupLaunch();
    await loaded();
    await openRun(51);
    expect(
      screen.getByTestId('run-fields').querySelector('dt')!.textContent,
    ).toBe(d.fields.document);
    expect(screen.queryByTestId('run-launch')).toBeNull();
    expect(screen.queryByTestId('run-resumed')).toBeNull();
  });

  describe('AF1 꼴(디자인 6c R4·R5·R12~R15 — 시안 .e-formrows · 결과 파일)', () => {
    it('칸 목록: 머리 500 14 tertiary · 옅은 회색 바탕 · 폭 160 · 좌우 24 · 줄 64 · 위아래 선 / 값 400 14 secondary', async () => {
      setupLaunch();
      await loaded();
      await openRun(102);
      const fields = screen.getByTestId('run-fields');
      expect(fields.className).toContain('border-t');
      const head = fields.querySelector('dt')!;
      for (const look of [
        'text-style-pre-body-05',
        'text-text-tertiary',
        'bg-support-grey-subtle',
        'w-40',
        'px-6',
      ])
        expect(head.className, look).toContain(look);
      const row = head.parentElement!;
      expect(row.className).toContain('min-h-16');
      expect(row.className).toContain('border-b');
      const value = fields.querySelector('dd')!;
      expect(value.className).toContain('text-style-pre-body-06');
      expect(value.className).toContain('text-text-secondary');
      expect(value.className).not.toContain('text-text-primary');
    });

    it('[내려받기]: sm(h-7) outline-black · 좌우 10 · 아이콘–글 2(gap 덮어쓰기 0)', async () => {
      setupLaunch();
      await loaded();
      await openRun(51);
      const button = document.querySelector<HTMLElement>(
        '[data-file-download]',
      )!;
      for (const look of [
        'h-7',
        'border-button-black',
        'bg-button-white',
        'px-2.5',
        'gap-0.5',
      ])
        expect(button.className, look).toContain(look);
      expect(button.className).not.toContain('h-[22px]');
      expect(button.className).not.toContain('bg-button-grey');
      expect(button.className).not.toContain('gap-1');
    });

    it('결과 파일: 줄 사이 gap-2 · 파일 이름 400 12 tertiary · 머리 h3 글 꼴 700 12 tertiary', async () => {
      setupLaunch();
      await loaded();
      await openRun(51);
      const files = screen.getByTestId('run-files');
      const list = files.querySelector('ul')!;
      expect(list.className).toContain('gap-2');
      expect(list.className).not.toContain('gap-1');
      expect(list.className).toContain('text-style-pre-caption-03');
      expect(list.className).toContain('text-text-tertiary');
      const head = files.querySelector('h3')!;
      expect(head.className).toContain('text-style-pre-caption-01');
      expect(head.className).toContain('text-text-tertiary');
    });
  });
});

describe('AD-04 ④ 첫 불러오기 자리(밴드 LD1, sid:MARC-ENT-443)', () => {
  it('받기 전: 첫 그림부터 몸 줄 5·지표 자리(이름 그대로), 빈 상태 0 — 받으면 빈 상태와 지표', async () => {
    let release!: (response: Response) => void;
    setup([], METRICS, {
      prepare: (server) => {
        release = hold(server, 'GET /run-logs');
      },
    });
    const skeletonRows = () =>
      document.querySelectorAll('tbody tr[data-skeleton-row]');
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('empty')).toBeNull();
    const pending = screen.getByTestId('metrics-pending');
    expect(pending.textContent).toContain(t.metrics.runsThisMonth);
    expect(pending.querySelectorAll('[data-skeleton-bar]')).toHaveLength(5);
    expect(screen.queryByTestId('metrics')).toBeNull();
    await new Promise((done) => setTimeout(done, 400));
    expect(skeletonRows()).toHaveLength(5);
    expect(screen.queryByTestId('empty')).toBeNull();
    await act(async () => {
      release(json(200, { count: 0, isNext: false, results: [] }));
    });
    expect(await screen.findByTestId('empty')).toBeTruthy();
    expect(skeletonRows()).toHaveLength(0);
    expect(screen.queryByTestId('metrics-pending')).toBeNull();
    expect(screen.getByTestId('metrics')).toBeTruthy();
  });

  // 밴드 DT1 ②(J3, sid:MARC-ISSUE-374): table-fixed + colgroup — 로딩·받은 뒤 같은 col 폭(잰 값, 6c 10-27 답 (가) — 문서만 폭 없음).
  it('열 폭: table-fixed · col 수 = 머리 칸 수 · 로딩과 받은 뒤 같은 col 폭', async () => {
    let release!: (response: Response) => void;
    setup([], METRICS, {
      prepare: (server) => {
        release = hold(server, 'GET /run-logs');
      },
    });
    const cols = () =>
      [...document.querySelectorAll('table colgroup > col')].map(
        (col) => (col as HTMLElement).style.width,
      );
    const table = screen.getByRole('table');
    expect(table.className.split(/\s+/)).toContain('table-fixed');
    expect(cols()).toHaveLength(table.querySelectorAll('thead th').length);
    const loading = cols();
    expect(loading).toEqual([
      '153px',
      '96px',
      '',
      '56px',
      '84px',
      '96px',
      '85px',
      '87px',
      '90px',
      '74px',
      '74px',
    ]);
    await act(async () => {
      release(json(200, { count: 0, isNext: false, results: [] }));
    });
    expect(await screen.findByTestId('empty')).toBeTruthy();
    expect(cols()).toEqual(loading);
  });
});
