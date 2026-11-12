// @vitest-environment jsdom
// S3-08 ResultView 의 늦은 답(밴드 S3W2a ②): 같은 자리에서 runId 가 바뀌면 앞 실행의 늦은 결과는 버린다(asked 꼴).
// 화면(Scope3Screen)은 해를 바꾸면 이 부품을 내렸다 다시 올리므로, 여기서는 부품을 바로 그려 runId 만 바꾼다.
// 밴드 S3W2c ②: 카드 글꼴·간격(e6 대조 1–5 — 클래스 이름 그대로 단언, 토큰 정의에 없는 글꼴 0).
// 밴드 DB5: 카드 합·생물기원 숫자 굴림(맨 끝 describe — matchMedia·rAF 흉내는 그 안에서만).
import { act } from 'react';

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
  FAKE_EDITED_CO2E,
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
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { ResultView } from './ResultView.tsx';

afterEach(cleanup);
// 자물쇠에 초점이 오면 툴팁이 뜬다(jsdom 에 없다).
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

const one = (co2e: string) =>
  fakeDoneResult({
    sheets: [processedSheet('s', 'Category1', [purchaseRow(co2e)])],
  });
const total = () =>
  screen
    .getAllByTestId('s3-result-card')[0]!
    .querySelector('[data-testid="s3-card-total"]')!.textContent;

describe('ResultView — 늦은 답', () => {
  it('runId 5 를 기다리는 동안 4 로 바뀌면 5 의 늦은 답은 버린다', async () => {
    const server = fakeScope3Server({
      runs: [
        { id: 5, status: 'done', reportYear: 2025, result: one('25') },
        { id: 4, status: 'done', reportYear: 2024, result: one('24') },
      ],
    });
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override['GET /inventory/scope3/runs/5/result'] = [
      () => gate.then(() => json(200, one('25'))),
    ];
    const port = portOf(server);
    const { rerender } = render(
      <ResultView port={port} runId="5" year={2025} onUpload={() => {}} />,
    );
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/5/result')).toBe(1),
    );
    rerender(
      <ResultView port={port} runId="4" year={2024} onUpload={() => {}} />,
    );
    await screen.findByTestId('s3-result');
    expect(total()).toBe('24tCO2eq');
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(total()).toBe('24tCO2eq');
  });
});

describe('ResultView — 카드 글꼴·간격(S3W2c ② e6 대조 1–5)', () => {
  const cardOf = (id: string) =>
    screen
      .getAllByTestId('s3-result-card')
      .find((card) => card.getAttribute('data-category') === id)!;
  const classOf = (node: Element | null | undefined) =>
    node?.getAttribute('class') ?? null;

  it('값 카드: 합 display-04 brand · 단위 body-05 tertiary · 이름 body-05 tertiary · 「총 배출량」 caption-02 quaternary · 묶음 간격', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 5,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('s', 'Category1', [purchaseRow('12')]),
              failedSheet('f', 'Category2'),
            ],
          }),
        },
      ],
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="5"
        year={2025}
        onUpload={() => {}}
      />,
    );
    await screen.findByTestId('s3-result');
    const card = cardOf('C1');
    const box = card.querySelector('button')!;
    expect(classOf(box)).toContain('gap-3.5');
    expect(classOf(box)).not.toMatch(/(^| )gap-2( |$)/);
    const totalLine = card.querySelector('[data-testid="s3-card-total"]')!;
    expect(classOf(totalLine)).toBe('flex items-baseline justify-center gap-1');
    const [value, unit] = Array.from(totalLine.children);
    // 밴드 DB5(디자인 e6 (나)): 값 칸에 tabular-nums 를 더함.
    expect(classOf(value)).toBe(
      'text-style-pre-display-04 text-text-brand tabular-nums',
    );
    expect(value!.textContent).toBe('12');
    expect(classOf(unit)).toBe('text-style-pre-body-05 text-text-tertiary');
    expect(unit!.textContent).toBe('tCO2eq');
    // 숫자 줄 묶음: 숫자 줄 · 「총 배출량」(가운데, gap 2).
    const lower = totalLine.parentElement!;
    expect(classOf(lower)).toBe('flex flex-col items-center gap-0.5');
    expect(classOf(lower.children[1])).toBe(
      'block text-center text-style-pre-caption-02 text-text-quaternary',
    );
    // 제목·이름 묶음(gap 6).
    const upper = lower.previousElementSibling!;
    expect(classOf(upper)).toBe('flex flex-col gap-1.5');
    expect(classOf(upper.children[1])).toBe(
      'block text-style-pre-body-05 text-text-tertiary',
    );
    // 빈 카드 「-」 는 display-04 quaternary · 실패 카드는 body-04 오류색 그대로.
    const empty = cardOf('C3').querySelector('[data-testid="s3-card-total"]')!;
    expect(classOf(empty.firstElementChild)).toBe(
      'text-style-pre-display-04 text-text-quaternary',
    );
    const failed = cardOf('C2').querySelector('[data-testid="s3-card-total"]')!;
    expect(classOf(failed.firstElementChild)).toBe(
      'text-style-pre-body-04 text-support-error-accent',
    );
    // 토큰 정의에 없는 글꼴(heading 셋째 칸)이 카드에 남지 않는다 — 제목의 heading-02 만.
    expect(document.body.innerHTML).not.toMatch(/pre-heading-0[^2]/);
  });
});

describe('ResultView — 그 해의 지금 결과(S3W3a ②)', () => {
  const cardOf = (id: string) =>
    screen
      .getAllByTestId('s3-result-card')
      .find((card) => card.getAttribute('data-category') === id)!;
  const totalOf = (id: string) =>
    within(cardOf(id)).getByTestId('s3-card-total').textContent;
  const c1 = (...rows: [string, string][]) =>
    processedSheet(
      'c1_지어낸',
      'Category1',
      rows.map(([co2e, rowId]) => purchaseRow(co2e, rowId)),
    );
  const c2 = (co2e: string) =>
    processedSheet('c2_지어낸', 'Category2', [purchaseRow(co2e, 'B!2')]);
  const year = (...sheets: Record<string, unknown>[]) =>
    fakeDoneResult({ sheets });
  const draw = (server: ReturnType<typeof fakeScope3Server>, runId: string) =>
    render(
      <ResultView
        port={portOf(server)}
        runId={runId}
        year={2025}
        onUpload={() => {}}
      />,
    );

  it('카드 합 = 서버 지금 합(제외 빠짐·고친 값 듦) — 본문 합이 아니다', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['1', 'A!2'], ['2', 'A!3'], ['4', 'A!4'])),
          edits: [
            { rowId: 'A!2', category: 'C1', excluded: true },
            { rowId: 'A!3', category: 'C1', factor: fakeRowFactor() },
          ],
        },
      ],
    });
    draw(server, '9');
    await screen.findByTestId('s3-result');
    expect(totalOf('C1')).toBe('11.25tCO2eq');
    expect(FAKE_EDITED_CO2E).toBe('7.25');
  });

  it('잠근 카테고리는 새 실행 뒤에도 핀 값 · 다른 카드는 새 값 · 상세는 핀 줄', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['3', 'A!2']), c2('5')),
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['30', 'A!2'], ['31', 'A!3']), c2('50')),
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, '9');
    await screen.findByTestId('s3-result');
    expect(totalOf('C1')).toBe('3tCO2eq');
    expect(totalOf('C2')).toBe('50tCO2eq');
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    const detail = await screen.findByTestId('s3-detail');
    expect(within(detail).getAllByTestId('s3-row')).toHaveLength(1);
  });

  it('같은 실행은 result·edits 한 번씩 · 다른 실행은 그 실행 것을 하나씩', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['3', 'A!2'])),
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['4', 'A!2'])),
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, '9');
    await screen.findByTestId('s3-result');
    expect(server.count('GET /inventory/scope3/runs/9/result')).toBe(1);
    expect(server.count('GET /inventory/scope3/runs/7/result')).toBe(1);
    expect(server.count('GET /inventory/scope3/runs/9/edits')).toBe(1);
    expect(server.count('GET /inventory/scope3/runs/7/edits')).toBe(1);
    expect(server.count('GET /inventory/scope3/years/2025')).toBe(1);
  });

  it('rejected · 그 해 지금 결과 없음 → 까닭 글(앞 갈래 그대로, H-3)', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeRejectedResult(),
        },
      ],
    });
    draw(server, '9');
    await screen.findByTestId('s3-rejected');
    expect(screen.queryByTestId('s3-result')).toBeNull();
  });

  it('rejected · 연도 읽기 실패 → 읽기 실패가 아니라 까닭 글로 물러선다(H-3 · GX3 검증 권고 2)', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeRejectedResult('legacy_template'),
        },
      ],
    });
    server.override['GET /inventory/scope3/years/2025'] = [
      () => refusal(500, 'INTERNAL'),
    ];
    draw(server, '9');
    const box = await screen.findByTestId('s3-rejected');
    expect(box.textContent).toContain(S3_TEXT.result.rejected.legacy_template);
    expect(screen.queryByTestId('s3-result-failed')).toBeNull();
  });

  it.each([
    ['연도', 'GET /inventory/scope3/years/2025'],
    ['덧판', 'GET /inventory/scope3/runs/9/edits'],
    ['핀 결과', 'GET /inventory/scope3/runs/7/result'],
    ['핀 덧판', 'GET /inventory/scope3/runs/7/edits'],
  ])(
    'Q5 %s 읽기 실패 → 결과 읽기 실패와 같은 꼴(본문 합으로 물러서지 않음) · [다시 시도]',
    async (_, key) => {
      const server = fakeScope3Server({
        runs: [
          {
            id: 7,
            status: 'done',
            reportYear: 2025,
            result: year(c1(['3', 'A!2'])),
          },
          {
            id: 9,
            status: 'done',
            reportYear: 2025,
            result: year(c1(['4', 'A!2'])),
          },
        ],
        locks: [{ year: 2025, category: 'C1', runId: 7 }],
      });
      server.override[key] = [() => refusal(500, 'INTERNAL')];
      draw(server, '9');
      const failed = await screen.findByTestId('s3-result-failed');
      expect(screen.queryByTestId('s3-result')).toBeNull();
      fireEvent.click(
        within(failed).getByRole('button', { name: S3_TEXT.result.retryLoad }),
      );
      await screen.findByTestId('s3-result');
      expect(totalOf('C1')).toBe('3tCO2eq');
    },
  );

  it('연도 답 회사 거절 → 그 글', async () => {
    const server = fakeScope3Server({
      runs: [{ id: 9, status: 'done', reportYear: 2025 }],
    });
    server.override['GET /inventory/scope3/years/2025'] = () =>
      refusal(400, 'COMPANY_INACTIVE');
    draw(server, '9');
    const failed = await screen.findByTestId('s3-result-failed');
    expect(failed.textContent).toContain(S3_TEXT.company.inactive);
  });

  it('늦은 답: 연도·덧판을 기다리는 사이 runId 가 바뀌면 앞 답은 버린다', async () => {
    const server = fakeScope3Server({
      runs: [
        { id: 5, status: 'done', reportYear: 2025, result: one('25') },
        { id: 4, status: 'done', reportYear: 2024, result: one('24') },
      ],
    });
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const body = (await real.json()) as unknown;
    server.override['GET /inventory/scope3/years/2025'] = [
      () => gate.then(() => json(200, body)),
    ];
    const port = portOf(server);
    const { rerender } = render(
      <ResultView port={port} runId="5" year={2025} onUpload={() => {}} />,
    );
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/years/2025')).toBe(2),
    );
    rerender(
      <ResultView port={port} runId="4" year={2024} onUpload={() => {}} />,
    );
    await screen.findByTestId('s3-result');
    expect(total()).toBe('24tCO2eq');
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(total()).toBe('24tCO2eq');
    expect(server.count('GET /inventory/scope3/runs/5/edits')).toBe(0);
  });

  it('늦은 답: 덧판을 기다리는 사이 runId 가 바뀌면 앞 답은 안 그린다', async () => {
    const server = fakeScope3Server({
      runs: [
        { id: 5, status: 'done', reportYear: 2025, result: one('25') },
        { id: 4, status: 'done', reportYear: 2024, result: one('24') },
      ],
    });
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override['GET /inventory/scope3/runs/5/edits'] = [
      () => gate.then(() => json(200, { runId: '5', rows: [] })),
    ];
    const port = portOf(server);
    const { rerender } = render(
      <ResultView port={port} runId="5" year={2025} onUpload={() => {}} />,
    );
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/5/edits')).toBe(1),
    );
    rerender(
      <ResultView port={port} runId="4" year={2024} onUpload={() => {}} />,
    );
    await screen.findByTestId('s3-result');
    expect(total()).toBe('24tCO2eq');
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(total()).toBe('24tCO2eq');
  });

  it('덧판 회사 거절 → 그 글(읽기 실패로 뭉개지 않음)', async () => {
    const server = fakeScope3Server({
      runs: [{ id: 9, status: 'done', reportYear: 2025 }],
    });
    server.override['GET /inventory/scope3/runs/9/edits'] = () =>
      refusal(400, 'COMPANY_INACTIVE');
    draw(server, '9');
    const failed = await screen.findByTestId('s3-result-failed');
    expect(failed.textContent).toContain(S3_TEXT.company.inactive);
  });

  it.each([
    ['기준 9 에만 사건', 9, 'C2', 'C1'],
    ['핀 7 에만 사건', 7, 'C1', 'C2'],
  ] as const)(
    '570 %s: 같은 rowId 라도 사건은 그 실행 상세에만 붙는다',
    async (_, owner, marked, clean) => {
      const same = (category: 'C1' | 'C2') => ({
        rowId: 'A!2',
        category,
        excluded: true,
      });
      const both = () =>
        year(
          processedSheet('c1_지어낸', 'Category1', [purchaseRow('1', 'A!2')]),
          processedSheet('c2_지어낸', 'Category2', [purchaseRow('2', 'A!2')]),
        );
      const server = fakeScope3Server({
        runs: [
          {
            id: 7,
            status: 'done',
            reportYear: 2025,
            result: both(),
            edits: owner === 7 ? [same('C1')] : [],
          },
          {
            id: 9,
            status: 'done',
            reportYear: 2025,
            result: both(),
            edits: owner === 9 ? [same('C2')] : [],
          },
        ],
        locks: [{ year: 2025, category: 'C1', runId: 7 }],
      });
      draw(server, '9');
      const rowIn = async (id: string) => {
        await screen.findByTestId('s3-result');
        fireEvent.click(within(cardOf(id)).getByRole('button'));
        const detail = await screen.findByTestId('s3-detail');
        const row = within(detail).getByTestId('s3-row');
        const excluded = row.getAttribute('data-excluded');
        fireEvent.click(within(detail).getByTestId('s3-detail-back'));
        return excluded;
      };
      expect(await rowIn(marked)).toBe('true');
      expect(await rowIn(clean)).toBeNull();
    },
  );

  it('s3-problems: 시트 수는 지금 결과(핀의 실패 시트 포함), AI 수는 마지막 실행', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['3', 'A!2']), failedSheet('c1_나', 'Category1')),
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [c1(['4', 'A!2'])],
            llmCalls: { classify: { 'failed:timeout': 1 } },
          }),
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, '9');
    expect((await screen.findByTestId('s3-problems')).textContent).toBe(
      S3_TEXT.result.problems(1, 1),
    );
  });

  it('마지막 실행에 실패 시트가 있어도 핀이 덮은 카테고리면 시트 수에 안 든다', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 7,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['3', 'A!2'])),
        },
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: year(failedSheet('c1_나', 'Category1')),
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, '9');
    await screen.findByTestId('s3-result');
    expect(screen.queryByTestId('s3-problems')).toBeNull();
  });

  it('지금 결과가 없는 카테고리(current null): 카드 「-」 · 상세는 시트 없음', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: year(c1(['3', 'A!2'])),
        },
      ],
    });
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const body = (await real.json()) as {
      categories: { current: unknown }[];
    };
    body.categories[0]!.current = null;
    server.override['GET /inventory/scope3/years/2025'] = () => json(200, body);
    draw(server, '9');
    await screen.findByTestId('s3-result');
    expect(totalOf('C1')).toBe('-');
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    await screen.findByTestId('s3-detail-none');
  });
});

describe('잠금(S3W3a ③ · 값 파일 E1 · 처분 Q7·Q9)', () => {
  const lockWords = S3_TEXT.lock;
  const YEAR = 'GET /inventory/scope3/years/2025';
  const LOCK = '/inventory/scope3/years/2025/categories/C1/lock';
  const body = (co2e: string, extra: Record<string, unknown>[] = []) =>
    fakeDoneResult({
      sheets: [
        processedSheet('c1_지어낸', 'Category1', [purchaseRow(co2e, 'A!2')]),
        ...extra,
      ],
    });
  const run = (id: number, co2e: string) => ({
    id,
    status: 'done' as const,
    reportYear: 2025,
    result: body(co2e),
  });
  const draw = (
    server: ReturnType<typeof fakeScope3Server>,
    { runId = '9', operator = false } = {},
  ) =>
    render(
      <ResultView
        port={portOf(server)}
        runId={runId}
        year={2025}
        operator={operator}
        onUpload={() => {}}
      />,
    );
  const cardOf = (id: string) =>
    screen
      .getAllByTestId('s3-result-card')
      .find((card) => card.getAttribute('data-category') === id)!;
  const open = async (id = 'C1') => {
    await screen.findByTestId('s3-result');
    fireEvent.click(within(cardOf(id)).getByRole('button'));
    return screen.findByTestId('s3-detail');
  };
  const posts = (server: ReturnType<typeof fakeScope3Server>) =>
    server.calls.filter((c) => c.method === 'POST' && c.path === LOCK);
  const deletes = (server: ReturnType<typeof fakeScope3Server>) =>
    server.calls.filter((c) => c.method === 'DELETE' && c.path === LOCK);
  const lockButton = () => screen.getByTestId('s3-lock');
  /** 다시 읽기 뒤의 그리기까지 기다린다. */
  const settle = () => new Promise((resolve) => setTimeout(resolve, 20));
  const confirm = async (testId: string, name: string) =>
    fireEvent.click(
      within(await screen.findByTestId(testId)).getByRole('button', { name }),
    );
  const totalIn = () => screen.getByTestId('s3-detail-total').textContent;

  it('카드: 열다섯 모두 자물쇠 표시(누를 자리 없음) · 잠긴 카드만 잠김 · 카드 안 단추는 하나', async () => {
    const server = fakeScope3Server({
      runs: [run(9, '1')],
      locks: [{ year: 2025, category: 'C1', runId: 9 }],
    });
    draw(server);
    await screen.findByTestId('s3-result');
    const marks = screen.getAllByTestId('s3-card-lock');
    expect(marks).toHaveLength(15);
    expect(marks[0]!.getAttribute('aria-label')).toBe(lockWords.lockedLabel);
    expect(marks[1]!.getAttribute('aria-label')).toBe(lockWords.unlockedLabel);
    expect(within(cardOf('C1')).getAllByRole('button')).toHaveLength(1);
  });

  it('고객사 잠그기: 확인 창 → 본 runId → 상세가 남고 그림으로 바뀌고 초점은 [목록] · 잠근 사람·때', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    fireEvent.click(lockButton());
    const window = await screen.findByTestId('s3-lock-confirm');
    expect(window.textContent).toContain(lockWords.lockConfirmPlain);
    expect(posts(server)).toHaveLength(0);
    await confirm('s3-lock-confirm', lockWords.lockOk);
    await screen.findByTestId('s3-locked-mark');
    expect(posts(server)[0]!.query.get('runId')).toBe('9');
    expect(screen.queryByTestId('s3-lock')).toBeNull();
    expect(screen.getByTestId('s3-detail')).toBeTruthy();
    expect(screen.getByTestId('s3-locked-info').textContent).toBe(
      lockWords.lockedInfo('지어낸 담당자', '2026-03-02 10:02'),
    );
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back')),
    );
  });

  it('고객사 잠그기 창: 첫 초점은 취소 · 취소를 누르면 POST 0', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    fireEvent.click(lockButton());
    const window = await screen.findByTestId('s3-lock-confirm');
    const cancel = within(window).getByRole('button', {
      name: lockWords.cancel,
    });
    await waitFor(() => expect(document.activeElement).toBe(cancel));
    // 취소 단추는 type button 이라 Enter 가 폼을 보내지 않고 눌림이 된다(ConfirmModal 머리).
    expect(cancel.getAttribute('type')).toBe('button');
    fireEvent.click(cancel);
    await waitFor(() =>
      expect(screen.queryByTestId('s3-lock-confirm')).toBeNull(),
    );
    expect(posts(server)).toHaveLength(0);
  });

  it('고객사 취소: POST 0 · 초점은 자물쇠', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    fireEvent.click(lockButton());
    await confirm('s3-lock-confirm', lockWords.cancel);
    await waitFor(() =>
      expect(screen.queryByTestId('s3-lock-confirm')).toBeNull(),
    );
    expect(posts(server)).toHaveLength(0);
    await waitFor(() => expect(document.activeElement).toBe(lockButton()));
  });

  it('고객사 + 잠김: 풀기 단추 0 · 잠긴 이름이 빈 글자면 「-」', async () => {
    const server = fakeScope3Server({
      runs: [run(9, '1')],
      locks: [
        { year: 2025, category: 'C1', runId: 9, by: { id: '3', name: '' } },
      ],
    });
    draw(server);
    await open();
    expect(screen.queryByTestId('s3-lock')).toBeNull();
    expect(screen.getByTestId('s3-locked-mark')).toBeTruthy();
    expect(screen.getByTestId('s3-locked-info').textContent).toContain('- · ');
  });

  it('운영 관리자: 확인 없이 잠그고, 핀 = 기준이면 확인 없이 푼다', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    expect(screen.queryByTestId('s3-lock-confirm')).toBeNull();
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('false'),
    );
    expect(screen.queryByTestId('s3-unlock-confirm')).toBeNull();
    expect(deletes(server)).toHaveLength(1);
  });

  it('핀 ≠ 기준 풀기: 확인 창(n · 초점 취소) → 풀면 기준 값 · 취소면 DELETE 0', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        {
          ...run(7, '3'),
          edits: [{ rowId: 'A!2', category: 'C1', excluded: true }],
        },
        run(9, '30'),
      ],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, { operator: true });
    await open();
    fireEvent.click(lockButton());
    const window = await screen.findByTestId('s3-unlock-confirm');
    expect(window.textContent).toContain(lockWords.unlockTitle);
    expect(window.textContent).toContain(lockWords.unlockBody(1));
    await waitFor(() =>
      expect(document.activeElement?.textContent).toBe(lockWords.cancel),
    );
    await confirm('s3-unlock-confirm', lockWords.cancel);
    await waitFor(() =>
      expect(screen.queryByTestId('s3-unlock-confirm')).toBeNull(),
    );
    expect(deletes(server)).toHaveLength(0);
    fireEvent.click(lockButton());
    await confirm('s3-unlock-confirm', lockWords.unlockOk);
    await waitFor(() => expect(totalIn()).toBe('30tCO2eq'));
    expect(deletes(server)).toHaveLength(1);
  });

  it('핀 ≠ 기준 · 고친 행 0: 「없으면」 본문', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [run(7, '3'), run(9, '30')],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, { operator: true });
    await open();
    fireEvent.click(lockButton());
    expect(
      (await screen.findByTestId('s3-unlock-confirm')).textContent,
    ).toContain(lockWords.unlockBody(0));
    expect(lockWords.unlockBody(0)).not.toContain('고친 행');
  });

  it('쥔 값은 핀 = 기준이어도 누른 때 새로 읽은 값이 다르면 확인 창', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        run(9, '3'),
        {
          ...run(11, '30'),
          status: 'processing',
          script: ['processing', 'done'],
        },
      ],
      locks: [{ year: 2025, category: 'C1', runId: 9 }],
    });
    draw(server, { operator: true });
    await open();
    // 다른 세션의 실행이 끝나 기준이 11 로 넘어간다 — 화면은 모른다.
    await server.send(new Request('http://test.local/api/runs/11'));
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-unlock-confirm');
    expect(deletes(server)).toHaveLength(0);
  });

  it('풀기 앞 연도 읽기 실패: 넘어가지 않고 실패 줄 · DELETE 0', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [run(7, '3'), run(9, '30')],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, { operator: true });
    await open();
    server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
    fireEvent.click(lockButton());
    expect((await screen.findByTestId('s3-lock-problem')).textContent).toBe(
      lockWords.lockFailed,
    );
    expect(deletes(server)).toHaveLength(0);
    expect(screen.queryByTestId('s3-unlock-confirm')).toBeNull();
  });

  it('창 안에서 풀기 실패: 창을 닫고 실패 줄', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [run(7, '3'), run(9, '30')],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, { operator: true });
    await open();
    server.override[`DELETE ${LOCK}`] = () => refusal(500, 'INTERNAL');
    fireEvent.click(lockButton());
    await confirm('s3-unlock-confirm', lockWords.unlockOk);
    await screen.findByTestId('s3-lock-problem');
    expect(screen.queryByTestId('s3-unlock-confirm')).toBeNull();
  });

  it('stale_run: 그 글 + 다시 읽기 · not_computed: 그 글(다시 읽기 0) · 그 밖 실패: E1 글(다시 읽기 0)', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override[`POST ${LOCK}`] = [
      () => refusal(409, 'STALE_RUN'),
      () => refusal(409, 'NOT_COMPUTED'),
      () => refusal(500, 'INTERNAL'),
    ];
    const problem = () => screen.getByTestId('s3-lock-problem').textContent;
    const before = server.count(YEAR);
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-lock-problem');
    expect(problem()).toBe(lockWords.lockStale);
    await waitFor(() => expect(server.count(YEAR)).toBe(before + 1));
    await waitFor(() =>
      expect((lockButton() as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(lockButton());
    await waitFor(() => expect(problem()).toBe(lockWords.lockNotComputed));
    await waitFor(() =>
      expect((lockButton() as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(lockButton());
    await waitFor(() => expect(problem()).toBe(lockWords.lockFailed));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(server.count(YEAR)).toBe(before + 1);
  });

  it('잠글 때는 사용자가 본 실행을 보낸다 — 그사이 기준이 넘어갔으면 stale_run 한 줄 + 새 값(핀 0)', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        run(9, '1'),
        {
          ...run(11, '10'),
          status: 'processing',
          script: ['processing', 'done'],
        },
      ],
    });
    draw(server, { operator: true });
    await open();
    await server.send(new Request('http://test.local/api/runs/11'));
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-lock-problem');
    expect(posts(server)[0]!.query.get('runId')).toBe('9');
    await waitFor(() => expect(totalIn()).toBe('10tCO2eq'));
    expect(lockButton().getAttribute('data-locked')).toBe('false');
  });

  it.each([
    ['잠그기', 'POST', false, 'true'],
    ['풀기', 'DELETE', true, 'false'],
  ] as const)(
    '%s 답 전에 [목록]으로 나가도 다시 읽어 카드 자물쇠가 서버 값',
    async (_, method, seeded, want) => {
      const server = fakeScope3Server({
        operator: true,
        runs: [run(9, '1')],
        ...(seeded ?
          { locks: [{ year: 2025, category: 'C1', runId: 9 }] }
        : {}),
      });
      draw(server, { operator: true });
      await open();
      let release = () => {};
      const gate = new Promise<void>((resolve) => {
        release = resolve;
      });
      const url = `http://test.local/api${LOCK}${method === 'POST' ? '?runId=9' : ''}`;
      server.override[`${method} ${LOCK}`] = [
        async () => {
          await gate;
          return server.send(new Request(url, { method }));
        },
      ];
      const reads = server.count(YEAR);
      fireEvent.click(lockButton());
      if (seeded)
        await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
      await waitFor(() =>
        expect(
          server.calls.some(
            (one) => one.method === method && one.path === LOCK,
          ),
        ).toBe(true),
      );
      fireEvent.click(screen.getByTestId('s3-detail-back'));
      await screen.findByTestId('s3-result');
      release();
      await waitFor(() =>
        expect(
          within(cardOf('C1'))
            .getByTestId('s3-card-lock')
            .getAttribute('data-locked'),
        ).toBe(want),
      );
    },
  );

  it.each([
    ['잠그기', 'POST', false, 'true'],
    ['풀기', 'DELETE', true, 'false'],
  ] as const)(
    '%s 가 서버에 든 뒤 답이 끊기면 줄 없음 + 다시 읽어 자물쇠가 서버 값',
    async (_, method, seeded, want) => {
      const server = fakeScope3Server({
        operator: true,
        runs: [run(9, '1')],
        ...(seeded ?
          { locks: [{ year: 2025, category: 'C1', runId: 9 }] }
        : {}),
      });
      draw(server, { operator: true });
      await open();
      const url = `http://test.local/api${LOCK}${method === 'POST' ? '?runId=9' : ''}`;
      server.override[`${method} ${LOCK}`] = [
        async () => {
          await server.send(new Request(url, { method }));
          return unreachable();
        },
      ];
      lockButton().focus();
      fireEvent.click(lockButton());
      await waitFor(() =>
        expect(lockButton().getAttribute('data-locked')).toBe(want),
      );
      await settle();
      expect(screen.queryByTestId('s3-lock-problem')).toBeNull();
      // 운영 관리자는 초점을 옮기지 않는다.
      expect(document.activeElement).toBe(lockButton());
      fireEvent.click(screen.getByTestId('s3-detail-back'));
      await screen.findByTestId('s3-result');
      expect(
        within(cardOf('C1'))
          .getByTestId('s3-card-lock')
          .getAttribute('data-locked'),
      ).toBe(want);
    },
  );

  /** 쓰기 답을 끊는다. reach 면 서버에 든 뒤에. */
  const cutAnswer = (
    server: ReturnType<typeof fakeScope3Server>,
    method: 'POST' | 'DELETE',
    reach: boolean,
  ) => {
    const url = `http://test.local/api${LOCK}${method === 'POST' ? '?runId=9' : ''}`;
    server.override[`${method} ${LOCK}`] = [
      async () => {
        if (reach) await server.send(new Request(url, { method }));
        return unreachable();
      },
    ];
  };
  const lockAsCompany = async () => {
    fireEvent.click(lockButton());
    await confirm('s3-lock-confirm', lockWords.lockOk);
  };

  it('고객사 잠금이 서버에 든 뒤 답이 끊기면 줄 없음 · 그림으로 바뀌고 초점은 [목록]', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    cutAnswer(server, 'POST', true);
    await lockAsCompany();
    await screen.findByTestId('s3-locked-mark');
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back')),
    );
    expect(screen.queryByTestId('s3-lock-problem')).toBeNull();
  });

  it('끊긴 잠금의 다시 읽기 사이에 행 고침 다시 읽기가 시작돼도 서버에 들었으면 실패 줄 0 · 초점 [목록](sid:MARC-ISSUE-587 R1)', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    cutAnswer(server, 'POST', true);
    // 다시 읽기 둘(잠금 A · 행 고침 B)의 연도 읽기를 따로 잡는다. 둘 다 불린 뒤에 풀어 기본 답으로 보낸다.
    const yearUrl = 'http://test.local/api/inventory/scope3/years/2025';
    const gates: (() => void)[] = [];
    const held = () =>
      new Promise<void>((resolve) => {
        gates.push(resolve);
      }).then(() => server.send(new Request(yearUrl)));
    server.override[YEAR] = [held, held];
    const years = () => server.count(YEAR);
    const before = years();
    await lockAsCompany();
    await waitFor(() => expect(years()).toBe(before + 1));
    // 잠금 A 가 연도를 기다리는 사이 행 제외 — 답 뒤 B 가 다시 읽는다.
    fireEvent.click(screen.getAllByTestId('s3-pick-row')[0]!);
    fireEvent.click(screen.getByTestId('s3-exclude'));
    fireEvent.change(await screen.findByTestId('s3-reason-input'), {
      target: { value: '지어낸 까닭' },
    });
    fireEvent.click(
      within(screen.getByTestId('s3-reason')).getByRole('button', {
        name: S3_TEXT.rowEdit.reason.confirm,
      }),
    );
    await waitFor(() => expect(years()).toBe(before + 2));
    gates[0]!();
    await settle();
    gates[1]!();
    await screen.findByTestId('s3-locked-mark');
    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back')),
    );
    await settle();
    expect(screen.queryByTestId('s3-lock-problem')).toBeNull();
  });

  it.each([
    ['잠그기', 'POST', false, 'false'],
    ['풀기', 'DELETE', true, 'true'],
  ] as const)(
    '%s 가 서버에 안 들고 답이 끊기면 실패 줄 · 자물쇠 그대로',
    async (_, method, seeded, want) => {
      const server = fakeScope3Server({
        operator: true,
        runs: [run(9, '1')],
        ...(seeded ?
          { locks: [{ year: 2025, category: 'C1', runId: 9 }] }
        : {}),
      });
      draw(server, { operator: true });
      await open();
      cutAnswer(server, method, false);
      fireEvent.click(lockButton());
      expect((await screen.findByTestId('s3-lock-problem')).textContent).toBe(
        lockWords.lockFailed,
      );
      expect(lockButton().getAttribute('data-locked')).toBe(want);
    },
  );

  it('답이 끊기고 다시 읽기도 실패면 서버에 들었어도 실패 줄 · 초점 안 옮김', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    cutAnswer(server, 'POST', true);
    server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
    await lockAsCompany();
    expect((await screen.findByTestId('s3-lock-problem')).textContent).toBe(
      lockWords.lockFailed,
    );
    await screen.findByTestId('s3-reread-failed');
    expect(document.activeElement).not.toBe(
      screen.getByTestId('s3-detail-back'),
    );
  });

  it('답을 기다리는 사이 [목록]으로 나가면 초점을 옮기지 않고 카드는 서버 값', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[`POST ${LOCK}`] = [
      async () => {
        await held;
        await server.send(
          new Request(`http://test.local/api${LOCK}?runId=9`, {
            method: 'POST',
          }),
        );
        return unreachable();
      },
    ];
    await lockAsCompany();
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    const card = within(cardOf('C1')).getByRole('button');
    card.focus();
    release();
    await waitFor(() =>
      expect(
        within(cardOf('C1'))
          .getByTestId('s3-card-lock')
          .getAttribute('data-locked'),
      ).toBe('true'),
    );
    await settle();
    expect(document.activeElement).toBe(card);
    expect(screen.queryByTestId('s3-lock-problem')).toBeNull();
  });

  it('낡은 바람이 남지 않는다: 안 든 끊긴 답 뒤 남이 잠가 stale 로 다시 읽어도 초점 안 옮김 · 줄은 stale 글', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open();
    cutAnswer(server, 'POST', false);
    await lockAsCompany();
    await screen.findByTestId('s3-lock-problem');
    await server.send(
      new Request(`http://test.local/api${LOCK}?runId=9`, { method: 'POST' }),
    );
    server.override[`POST ${LOCK}`] = [() => refusal(409, 'STALE_RUN')];
    const back = screen.getByTestId('s3-detail-back');
    lockButton().focus();
    await lockAsCompany();
    await screen.findByTestId('s3-locked-mark');
    await settle();
    expect(screen.getByTestId('s3-lock-problem').textContent).toBe(
      lockWords.lockStale,
    );
    expect(document.activeElement).not.toBe(back);
  });

  it('잠그기 창이 열린 사이 지금 결과가 바뀌어도 연 때 본 실행을 보낸다', async () => {
    const two = (one: string, other: string) =>
      fakeDoneResult({
        sheets: [
          processedSheet('c1_지어낸', 'Category1', [purchaseRow(one, 'A!2')]),
          processedSheet('c2_지어낸', 'Category2', [purchaseRow(other, 'B!2')]),
        ],
      });
    const server = fakeScope3Server({
      runs: [
        { id: 9, status: 'done', reportYear: 2025, result: two('1', '2') },
        {
          id: 11,
          status: 'processing',
          reportYear: 2025,
          script: ['processing', 'done'],
          result: two('10', '20'),
        },
      ],
    });
    draw(server);
    await open();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    // C1 잠금 답을 잡아 둔다 — 그사이 C2 를 열어 창을 띄우고, 답이 오면 다시 읽기가 새 기준을 가져온다.
    server.override[`POST ${LOCK}`] = [
      async () => {
        await gate;
        const real = await server.send(
          new Request(`http://test.local/api${LOCK}?runId=9`, {
            method: 'POST',
          }),
        );
        await server.send(new Request('http://test.local/api/runs/11'));
        return real;
      },
    ];
    fireEvent.click(lockButton());
    await confirm('s3-lock-confirm', lockWords.lockOk);
    await waitFor(() => expect(posts(server)).toHaveLength(1));
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C2');
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-lock-confirm');
    release();
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/11/result')).toBe(1),
    );
    await waitFor(() => expect(totalIn()).toBe('20tCO2eq'));
    await confirm('s3-lock-confirm', lockWords.lockOk);
    const c2 = '/inventory/scope3/years/2025/categories/C2/lock';
    await waitFor(() =>
      expect(
        server.calls.filter((c) => c.method === 'POST' && c.path === c2),
      ).toHaveLength(1),
    );
    expect(
      server.calls
        .find((c) => c.method === 'POST' && c.path === c2)!
        .query.get('runId'),
    ).toBe('9');
  });

  it('다시 읽기 실패 뒤 다음 다시 읽기가 되면 실패 줄이 사라진다', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-reread-failed');
    await waitFor(() =>
      expect((lockButton() as HTMLButtonElement).disabled).toBe(false),
    );
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(screen.queryByTestId('s3-reread-failed')).toBeNull(),
    );
  });

  it('풀기 창의 n 은 누른 때 새로 읽은 값', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [run(7, '3'), run(9, '30')],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    draw(server, { operator: true });
    await open();
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const fresh = (await real.json()) as {
      categories: { editedRows: number }[];
    };
    fresh.categories[0]!.editedRows = 5;
    server.override[YEAR] = [() => json(200, fresh)];
    fireEvent.click(lockButton());
    expect(
      (await screen.findByTestId('s3-unlock-confirm')).textContent,
    ).toContain(lockWords.unlockBody(5));
  });

  it('운영 관리자가 잠근 뒤 초점은 자물쇠에 남는다([목록]으로 안 튄다)', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    lockButton().focus();
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(document.activeElement).toBe(lockButton());
  });

  it('다시 읽기 둘이 겹치면 앞 답이 뒤 답을 덮지 않는다', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        {
          ...run(9, '1'),
          result: fakeDoneResult({
            sheets: [
              processedSheet('c1_지어낸', 'Category1', [
                purchaseRow('1', 'A!2'),
              ]),
              processedSheet('c2_지어낸', 'Category2', [
                purchaseRow('2', 'B!2'),
              ]),
            ],
          }),
        },
      ],
    });
    draw(server, { operator: true });
    await open();
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const old = (await real.json()) as unknown;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[YEAR] = [() => gate.then(() => json(200, old))];
    const reads = server.count(YEAR);
    fireEvent.click(lockButton());
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await open('C2');
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(lockButton().getAttribute('data-locked')).toBe('true');
  });

  it('다시 읽기를 기다리는 사이 runId 가 바뀌면 앞 답은 버린다', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        { id: 9, status: 'done', reportYear: 2025, result: one('25') },
        { id: 4, status: 'done', reportYear: 2024, result: one('24') },
      ],
    });
    const port = portOf(server);
    const { rerender } = render(
      <ResultView
        port={port}
        runId="9"
        year={2025}
        operator
        onUpload={() => {}}
      />,
    );
    await open();
    const real = await server.send(
      new Request('http://test.local/api/inventory/scope3/years/2025'),
    );
    const old = (await real.json()) as unknown;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[YEAR] = [() => gate.then(() => json(200, old))];
    const reads = server.count(YEAR);
    fireEvent.click(lockButton());
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    rerender(
      <ResultView
        port={port}
        runId="4"
        year={2024}
        operator
        onUpload={() => {}}
      />,
    );
    await screen.findByTestId('s3-result');
    expect(total()).toBe('24tCO2eq');
    release();
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(total()).toBe('24tCO2eq');
  });

  it('다시 읽기의 덧판 실패도 한 줄 · 지금 값 유지', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override['GET /inventory/scope3/runs/9/edits'] = [
      () => refusal(500, 'INTERNAL'),
    ];
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-reread-failed');
    expect(totalIn()).toBe('1tCO2eq');
  });

  it('회사 거절 → 그 글', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override[`POST ${LOCK}`] = () => refusal(400, 'COMPANY_INACTIVE');
    fireEvent.click(lockButton());
    expect((await screen.findByTestId('s3-lock-problem')).textContent).toBe(
      S3_TEXT.company.inactive,
    );
  });

  it('셈한 시트 없는 카드는 단추 막음', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    draw(server);
    await open('C3');
    expect((lockButton() as HTMLButtonElement).disabled).toBe(true);
  });

  it('두 번 눌러도 POST 하나', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    fireEvent.click(lockButton());
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    expect(posts(server)).toHaveLength(1);
  });

  it('L3: 쓰기 답의 category 로 덮지 않는다 — 화면은 다시 읽은 연도를 따른다', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override[`POST ${LOCK}`] = () =>
      json(200, {
        category: 'C1',
        current: { runId: '9', total: '999', sheets: 1, failedSheets: 0 },
        locked: true,
        lockedAt: '2026-03-02T01:02:03Z',
        lockedBy: { id: '7', name: '지어낸' },
        editedRows: 0,
      });
    const before = server.count(YEAR);
    fireEvent.click(lockButton());
    await waitFor(() => expect(server.count(YEAR)).toBe(before + 1));
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(totalIn()).toBe('1tCO2eq');
    expect(lockButton().getAttribute('data-locked')).toBe('false');
  });

  it('다시 읽기: 뼈대·목록으로 안 튄다 · 검색어가 남는다', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    fireEvent.change(screen.getByTestId('s3-detail-search'), {
      target: { value: '지어낸 말' },
    });
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    expect(screen.queryByTestId('s3-result')).toBeNull();
    expect(
      (screen.getByTestId('s3-detail-search') as HTMLInputElement).value,
    ).toBe('지어낸 말');
    expect(server.count('GET /inventory/scope3/runs/9/result')).toBe(1);
    expect(server.count('GET /inventory/scope3/runs/9/edits')).toBe(2);
  });

  it('새 실행이 기준이 되면 그 실행 result 도 읽고 다른 카드는 새 값 · 잠근 카드는 핀', async () => {
    const two = (one: string, other: string) =>
      fakeDoneResult({
        sheets: [
          processedSheet('c1_지어낸', 'Category1', [purchaseRow(one, 'A!2')]),
          processedSheet('c2_지어낸', 'Category2', [purchaseRow(other, 'B!2')]),
        ],
      });
    const server = fakeScope3Server({
      operator: true,
      runs: [
        { id: 9, status: 'done', reportYear: 2025, result: two('1', '2') },
        {
          id: 11,
          status: 'processing',
          reportYear: 2025,
          script: ['processing', 'done'],
          result: two('10', '20'),
        },
      ],
    });
    draw(server, { operator: true });
    await open();
    // 잠금이 받아진 바로 뒤 새 실행이 기준이 된다(S3K2b-1 리뷰 L3 의 장면).
    server.override[`POST ${LOCK}`] = [
      async () => {
        const real = await server.send(
          new Request(`http://test.local/api${LOCK}?runId=9`, {
            method: 'POST',
          }),
        );
        await server.send(new Request('http://test.local/api/runs/11'));
        return real;
      },
    ];
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(server.count('GET /inventory/scope3/runs/11/result')).toBe(1),
    );
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    expect(totalIn()).toBe('1tCO2eq');
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    expect(within(cardOf('C2')).getByTestId('s3-card-total').textContent).toBe(
      '20tCO2eq',
    );
  });

  it('다시 읽기는 덧씌우기 전 결과에 새 덧판을 얹는다 — 복구한 줄이 제외로 남지 않는다', async () => {
    const server = fakeScope3Server({
      operator: true,
      runs: [
        {
          ...run(9, '1'),
          edits: [{ rowId: 'A!2', category: 'C1', excluded: true }],
        },
      ],
    });
    draw(server, { operator: true });
    const detail = await open();
    expect(
      within(detail).getByTestId('s3-row').getAttribute('data-excluded'),
    ).toBe('true');
    await server.send(
      new Request(
        'http://test.local/api/inventory/scope3/runs/9/categories/C1/restorations',
        {
          method: 'POST',
          body: JSON.stringify({ rowIds: ['A!2'], reason: '지어낸' }),
        },
      ),
    );
    fireEvent.click(lockButton());
    await waitFor(() =>
      expect(lockButton().getAttribute('data-locked')).toBe('true'),
    );
    expect(
      within(detail).getByTestId('s3-row').getAttribute('data-excluded'),
    ).toBeNull();
  });

  it('다시 읽기 실패: 한 줄 · 지금 값 유지 · 상세 남음', async () => {
    const server = fakeScope3Server({ operator: true, runs: [run(9, '1')] });
    draw(server, { operator: true });
    await open();
    server.override[YEAR] = [() => refusal(500, 'INTERNAL')];
    fireEvent.click(lockButton());
    await screen.findByTestId('s3-reread-failed');
    expect(screen.getByTestId('s3-detail')).toBeTruthy();
    expect(totalIn()).toBe('1tCO2eq');
  });
});

describe('실패 시트 수 · Scope 3 총합(S3W3a ③ · 값 파일 E3·E4)', () => {
  const words = S3_TEXT.result;
  const draw = (sheets: Record<string, unknown>[]) => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 9,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({ sheets }),
        },
      ],
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="9"
        year={2025}
        onUpload={() => {}}
      />,
    );
    return screen.findByTestId('s3-result');
  };
  const c1 = (co2e: string | null) =>
    processedSheet('c1_지어낸', 'Category1', [purchaseRow(co2e, 'A!2')]);

  it('총합 = 카테고리 서버 합의 합 · 단위 · 빠진 시트 n', async () => {
    await draw([
      c1('1.5'),
      processedSheet('c2_지어낸', 'Category2', [purchaseRow('2.5', 'B!2')]),
      failedSheet('c2_나', 'Category2'),
      failedSheet('c3_나', 'Category3'),
    ]);
    const line = screen.getByTestId('s3-scope-total');
    expect(line.textContent).toContain(words.scopeTotalLabel);
    expect(line.textContent).toContain('4tCO2eq');
    expect(screen.getByTestId('s3-scope-missing').textContent).toBe(
      words.scopeTotalMissing(2),
    );
    expect(screen.getByTestId('s3-card-partial').textContent).toBe(
      words.cardPartial(1),
    );
  });

  it('총합은 C1 부터 C15 까지 든다', async () => {
    await draw([
      c1('1'),
      processedSheet('c15_지어낸', 'Category15', [purchaseRow('2', 'C!2')]),
    ]);
    expect(screen.getByTestId('s3-scope-total').textContent).toContain(
      '3tCO2eq',
    );
  });

  it('합이 없으면 「-」만(단위·빠짐 글 0) — 다 실패여도', async () => {
    await draw([failedSheet('c3_나', 'Category3')]);
    const line = screen.getByTestId('s3-scope-total');
    expect(line.textContent).toBe(`${words.scopeTotalLabel}${words.empty}`);
    expect(screen.queryByTestId('s3-scope-missing')).toBeNull();
  });

  it('일부 실패 카드 n · 다 실패 카드는 수 없이 「계산 실패」', async () => {
    await draw([
      c1('1'),
      failedSheet('c1_나', 'Category1'),
      failedSheet('c1_다', 'Category1'),
      failedSheet('c3_나', 'Category3'),
    ]);
    expect(screen.getByTestId('s3-card-partial').textContent).toBe(
      words.cardPartial(2),
    );
    expect(document.body.textContent).toContain(words.cardFailed);
  });
});

// 밴드 DB3(sid:MARC-TICK-538 — 움직임 e6 ②·③ · 감독 판단 7·15 B2·B3): 카드 15장만 gw-m-rise(카드마다 40, 상한 400) · 총합 머리·띠 0 ·
//   같은 해 다시 읽기는 같은 노드 · 상세 → [목록] 뒤 안 돎(7 (a)) · runId 바뀜 뒤 다시 떠오름(7 (b)) · 해 바뀜 새 노드 · 초점(e6 「추정」 3).
describe('ResultView — 카드 떠오름(밴드 DB3)', () => {
  const LOCK = '/inventory/scope3/years/2025/categories/C1/lock';
  const run = (id: number, co2e: string, reportYear = 2025) => ({
    id,
    status: 'done' as const,
    reportYear,
    result: fakeDoneResult({
      sheets: [
        processedSheet('c1_지어낸', 'Category1', [purchaseRow(co2e, 'A!2')]),
      ],
    }),
  });
  const cards = () => screen.getAllByTestId('s3-result-card');
  const cardOf = (id: string) =>
    cards().find((card) => card.getAttribute('data-category') === id)!;
  const delayOf = (node: HTMLElement) =>
    node.style.getPropertyValue('--gw-m-delay');
  const view = (
    port: ReturnType<typeof portOf>,
    runId: string,
    year = 2025,
  ) => <ResultView port={port} runId={runId} year={year} onUpload={() => {}} />;

  it('카드 15장 gw-m-rise · 지연 0·40·…·400(11번째부터 400 에서 멈춤) · 총합 머리·안내 띠·s3-problems 에 gw-m- 0', async () => {
    const server = fakeScope3Server({
      runs: [
        {
          ...run(9, '1'),
          result: fakeDoneResult({
            sheets: [
              processedSheet('c1_지어낸', 'Category1', [purchaseRow('1')]),
              failedSheet('c4_지어낸', 'Category4'),
            ],
          }),
        },
      ],
    });
    render(view(portOf(server), '9'));
    await screen.findByTestId('s3-result');
    expect(cards()).toHaveLength(15);
    expect(cards().every((card) => card.classList.contains('gw-m-rise'))).toBe(
      true,
    );
    expect(cards().map(delayOf)).toEqual([
      ...Array.from({ length: 11 }, (_, at) => `${at * 40}ms`),
      '400ms',
      '400ms',
      '400ms',
      '400ms',
    ]);
    for (const id of ['s3-scope-total', 's3-result-notice', 's3-problems'])
      expect(screen.getByTestId(id).outerHTML).not.toContain('gw-m-');
  });

  it('같은 해 다시 읽기(잠금 답을 붙잡고 [목록] → 답 풂): 카드 li 같은 노드 · 상세 → [목록] 뒤 떠오름 없음(감독 판단 7 (a)) · 초점은 연 카드', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1')] });
    render(view(portOf(server), '9'));
    await screen.findByTestId('s3-result');
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    await screen.findByTestId('s3-detail');
    let release = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[`POST ${LOCK}`] = [
      async () => {
        await held;
        await server.send(
          new Request(`http://test.local/api${LOCK}?runId=9`, {
            method: 'POST',
          }),
        );
        return unreachable();
      },
    ];
    fireEvent.click(screen.getByTestId('s3-lock'));
    fireEvent.click(
      within(await screen.findByTestId('s3-lock-confirm')).getByRole('button', {
        name: S3_TEXT.lock.lockOk,
      }),
    );
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    const card = cardOf('C1');
    expect(document.activeElement).toBe(within(card).getByRole('button'));
    expect(card.classList.contains('gw-m-rise')).toBe(false);
    expect(delayOf(card)).toBe('');
    release();
    await waitFor(() =>
      expect(
        within(cardOf('C1'))
          .getByTestId('s3-card-lock')
          .getAttribute('data-locked'),
      ).toBe('true'),
    );
    expect(cardOf('C1')).toBe(card);
    expect(card.classList.contains('gw-m-rise')).toBe(false);
  });

  it('새 실행이 끝나 runId 가 바뀌면 다시 떠오름(감독 판단 7 (b)) — 상세 → [목록] 뒤라도', async () => {
    const server = fakeScope3Server({ runs: [run(9, '1'), run(10, '2')] });
    const port = portOf(server);
    const { rerender } = render(view(port, '9'));
    await screen.findByTestId('s3-result');
    fireEvent.click(within(cardOf('C1')).getByRole('button'));
    fireEvent.click(await screen.findByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    expect(cardOf('C1').classList.contains('gw-m-rise')).toBe(false);
    rerender(view(port, '10'));
    await waitFor(() =>
      expect(cardOf('C1').classList.contains('gw-m-rise')).toBe(true),
    );
    expect(cards().map(delayOf).slice(0, 2)).toEqual(['0ms', '40ms']);
  });

  it('해를 바꾸면 카드 li 가 새 노드 + 다시 떠오름 · 초점은 바깥에 있던 그대로(e6 「추정」 3 — 연 카드로 끌어오지 않음)', async () => {
    const server = fakeScope3Server({
      runs: [run(9, '1'), run(8, '3', 2024)],
    });
    const port = portOf(server);
    const outside = document.createElement('button');
    document.body.append(outside);
    const { rerender } = render(view(port, '9'));
    await screen.findByTestId('s3-result');
    const before = cardOf('C1');
    outside.focus();
    rerender(view(port, '8', 2024));
    await waitFor(() => expect(cardOf('C1')).not.toBe(before));
    await screen.findByTestId('s3-result');
    expect(cardOf('C1').classList.contains('gw-m-rise')).toBe(true);
    expect(document.activeElement).toBe(outside);
    outside.remove();
  });
});

// 밴드 DB5(sid:MARC-TICK-544 — 발주서 §2-② · §3 ②③④ · 감독 판단 1): 카드 합·생물기원 값 칸 굴림.
//   시작 = 그 카드 떠오름 지연(40 계단·400 상한) · 길이 = min(700, 1000 − 지연) · 생물기원 = 합과 같은 지연·길이 · 때 = 떠오름(still)과 같음.
//   끝 글자 씨앗은 BASE 34681f54 에서 뜬 DB5.out/base-text.txt(같은 지어낸 시트). jsdom 에 matchMedia·rAF 시계가 없어 흉내 낸다.
describe('ResultView — 카드 숫자 굴림(밴드 DB5)', () => {
  const BASE5 = {
    C3: '12,345.679tCO2eq',
    C1: '<0.001tCO2eq',
    C5: '2tCO2eq',
    C5bio: `${S3_TEXT.result.biogenicLabel} 0.5 tCO2eq`,
    C7: '80tCO2eq',
    C12: '3,456.5tCO2eq',
    C12bio: `${S3_TEXT.result.biogenicLabel} 1.25 tCO2eq`,
    C13: '0tCO2eq',
    C14: S3_TEXT.result.empty,
    C15: S3_TEXT.result.cardFailed,
    // 밴드 S3N1: C3 이름 옆 고정 안내도 단추 글에 든다(아이콘은 aria-hidden).
    C3name: `Category 3연료 및 에너지 활동 ${S3_TEXT.result.adjustLater}12,345.679tCO2eq총 배출량`,
    C5name: `Category 5사업장 발생 폐기물2tCO2eq총 배출량${S3_TEXT.result.biogenicLabel} 0.5 tCO2eq`,
  };
  const result = (scale = '') =>
    fakeDoneResult({
      sheets: [
        processedSheet('s1', 'Category1', [purchaseRow('1e-05')]),
        processedSheet('s3', 'Category3', [
          energyRow('leased_asset', `12345.6789${scale}`),
        ]),
        processedSheet('s5', 'Category5', [activityRow('waste', '2', '0.5')]),
        processedSheet('s7', 'Category7', [activityRow('commute', '80')]),
        failedSheet('s7f', 'Category7'),
        processedSheet('s12', 'Category12', [
          energyRow('product_eol', '3456.5', '1.25'),
        ]),
        processedSheet('s13', 'Category13', [
          energyRow('leased_out_asset', '-0.0'),
        ]),
        { status: 'empty', sheet: 's14', category: 'Category14' },
        failedSheet('s15', 'Category15'),
      ],
    });
  const runs = [
    { id: 9, status: 'done' as const, reportYear: 2025, result: result() },
    { id: 10, status: 'done' as const, reportYear: 2025, result: result() },
  ];

  function motionStubs({ reduce = false }: { reduce?: boolean } = {}) {
    const queue = new Map<number, FrameRequestCallback>();
    let next = 1;
    let now = 1000;
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches:
        reduce ? query.includes(': reduce') : query.includes('no-preference'),
      media: query,
      onchange: null,
      addEventListener() {},
      removeEventListener() {},
      addListener() {},
      removeListener() {},
      dispatchEvent: () => false,
    }));
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      const id = next++;
      queue.set(id, callback);
      return id;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => queue.delete(id));
    const advance = (ms: number) =>
      act(() => {
        now += ms;
        const run = [...queue.values()];
        queue.clear();
        run.forEach((callback) => callback(now));
      });
    return {
      advance,
      pending: () => queue.size,
      finish: () => {
        for (let step = 0; step < 50; step += 1) advance(50);
      },
    };
  }
  afterEach(() => {
    vi.unstubAllGlobals();
    // 이 파일 머리의 ResizeObserver 흉내는 beforeAll 하나라 다시 단다.
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  const cards = () => screen.getAllByTestId('s3-result-card');
  const cardOf = (id: string) =>
    cards().find((card) => card.getAttribute('data-category') === id)!;
  const totalOf = (id: string) =>
    within(cardOf(id)).getByTestId('s3-card-total');
  const bioOf = (id: string) =>
    within(cardOf(id)).getByTestId('s3-card-biogenic');
  const rollingIn = (node: Element) => node.querySelector('[data-rolling]');
  const anyRolling = () =>
    screen.getByTestId('s3-result').querySelectorAll('[data-rolling]').length;
  /** 화면 읽기 글(aria-hidden 뺀 글자). */
  const spoken = (node: Element) => {
    const copy = node.cloneNode(true) as Element;
    copy
      .querySelectorAll('[aria-hidden="true"]')
      .forEach((one) => one.remove());
    return copy.textContent;
  };
  const view = (port: ReturnType<typeof portOf>, runId = '9') => (
    <ResultView port={port} runId={runId} year={2025} onUpload={() => {}} />
  );

  it('시험 ②: 값 카드 합·생물기원이 그 카드 떠오름 지연에서 시작해 min(700, 1000 − 지연) 뒤 끝 · 생물기원 = 합 · 지연+길이 ≤ 1,000 · 끝 글자 = BASE 바이트', async () => {
    const clock = motionStubs();
    render(view(portOf(fakeScope3Server({ runs: [runs[0]!] }))));
    await screen.findByTestId('s3-result');
    const order = (id: string) => cards().indexOf(cardOf(id));
    const rollingIds = ['C3', 'C5', 'C7', 'C12'];
    for (const id of rollingIds) expect(rollingIn(totalOf(id))).not.toBeNull();
    expect(rollingIn(bioOf('C5'))).not.toBeNull();
    expect(rollingIn(bioOf('C12'))).not.toBeNull();
    // 첫 프레임이 시작 시각 — 10ms 씩 걸으며 첫 움직임과 끝을 잰다.
    const zero = new Map<Element, string>();
    const watch = [
      ...rollingIds.map((id) => [id, totalOf(id)] as const),
      ['C5bio', bioOf('C5')] as const,
      ['C12bio', bioOf('C12')] as const,
    ];
    for (const [, node] of watch)
      zero.set(
        node,
        node.querySelector('[data-rolling] [aria-hidden]:not(.invisible)')!
          .textContent!,
      );
    const moved = new Map<string, number>();
    const ended = new Map<string, number>();
    clock.advance(0);
    for (let at = 10; at <= 1100; at += 10) {
      clock.advance(10);
      for (const [name, node] of watch) {
        const frame = node.querySelector(
          '[data-rolling] [aria-hidden]:not(.invisible)',
        )?.textContent;
        if (!moved.has(name) && frame !== undefined && frame !== zero.get(node))
          moved.set(name, at);
        if (!ended.has(name) && rollingIn(node) === null) ended.set(name, at);
      }
    }
    const delayOf = (id: string) => Math.min(order(id) * 40, 400);
    for (const id of rollingIds) {
      const delay = delayOf(id);
      const duration = Math.min(700, 1000 - delay);
      // 지연 전엔 첫 프레임 그대로(작은 수 「2」 는 이징 뒤에야 글자가 바뀐다 — 앞선 움직임 0 만 본다).
      expect(moved.get(id)!).toBeGreaterThan(delay);
      expect(ended.get(id)).toBe(delay + duration);
      expect(ended.get(id)!).toBeLessThanOrEqual(1000);
    }
    expect(moved.get('C5bio')!).toBeGreaterThan(delayOf('C5'));
    expect(moved.get('C12bio')!).toBeGreaterThan(delayOf('C12'));
    // 큰 수는 지연 바로 뒤 움직인다(시작 = 그 카드 떠오름 지연).
    for (const name of ['C3', 'C12', 'C12bio'])
      expect(moved.get(name)!).toBeLessThanOrEqual(
        delayOf(name.replace('bio', '')) + 10,
      );
    expect(order('C3')).toBe(2);
    expect(order('C12')).toBe(11);
    expect(ended.get('C12')).toBe(1000); // 400 + 600
    expect(ended.get('C5bio')).toBe(ended.get('C5'));
    expect(ended.get('C12bio')).toBe(ended.get('C12'));
    expect(clock.pending()).toBe(0);
    expect(anyRolling()).toBe(0);
    for (const id of [
      'C3',
      'C5',
      'C7',
      'C12',
      'C1',
      'C13',
      'C14',
      'C15',
    ] as const)
      expect(totalOf(id).textContent).toBe(BASE5[id]);
    expect(bioOf('C5').textContent).toBe(BASE5.C5bio);
    expect(bioOf('C12').textContent).toBe(BASE5.C12bio);
    expect(
      within(cardOf('C7')).getByTestId('s3-card-partial').textContent,
    ).toBe(S3_TEXT.result.cardPartial(1));
  });

  it('시험 ②: 실패·빈 칸·「-」·0·「<0.001」은 첫 그림부터 제자리(굴림 0) · 단위·「총 배출량」·빠짐 글·생물기원 앞 글은 굴림 칸 밖', async () => {
    motionStubs();
    render(view(portOf(fakeScope3Server({ runs: [runs[0]!] }))));
    await screen.findByTestId('s3-result');
    for (const id of ['C1', 'C2', 'C10', 'C13', 'C14', 'C15']) {
      expect(rollingIn(cardOf(id))).toBeNull();
      expect(totalOf(id).textContent).toBe(
        (BASE5 as Record<string, string>)[id] ?? S3_TEXT.result.empty,
      );
    }
    const [value, unit] = Array.from(totalOf('C3').children);
    expect(rollingIn(value!)).not.toBeNull();
    expect(unit!.textContent).toBe('tCO2eq');
    expect(rollingIn(unit!)).toBeNull();
    expect(
      rollingIn(within(cardOf('C7')).getByTestId('s3-card-partial')),
    ).toBeNull();
    expect(bioOf('C5').firstChild!.textContent).toBe(
      S3_TEXT.result.biogenicLabel,
    );
    // 디자인 e6 (나): 값 칸(합·생물기원 값)은 늘 tabular-nums · 생물기원 앞 글·단위는 밖 · 굴림 감싸개에는 따로 없음.
    expect(value!.className).toContain('tabular-nums');
    expect(rollingIn(value!)!.className).toBe('inline-grid');
    const bioValue = bioOf('C5').querySelector('.tabular-nums')!;
    expect(rollingIn(bioValue)).not.toBeNull();
    expect(bioValue.parentElement).toBe(bioOf('C5'));
    expect(bioOf('C5').className).not.toContain('tabular-nums');
  });

  it('시험 ②: 상세 → [목록] 엔 안 굴림(떠오름과 같은 판정) · 같은 실행 다시 그리기도 0 · runId 바뀜에는 다시 굴림', async () => {
    const clock = motionStubs();
    const port = portOf(fakeScope3Server({ runs }));
    const { rerender } = render(view(port, '9'));
    await screen.findByTestId('s3-result');
    expect(anyRolling()).toBeGreaterThan(0);
    clock.finish();
    fireEvent.click(within(cardOf('C3')).getByRole('button'));
    fireEvent.click(await screen.findByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    expect(cardOf('C3').classList.contains('gw-m-rise')).toBe(false);
    expect(anyRolling()).toBe(0);
    expect(totalOf('C3').textContent).toBe(BASE5.C3);
    rerender(view(port, '9'));
    expect(anyRolling()).toBe(0);
    rerender(view(port, '10'));
    await waitFor(() =>
      expect(cardOf('C3').classList.contains('gw-m-rise')).toBe(true),
    );
    expect(rollingIn(totalOf('C3'))).not.toBeNull();
    expect(rollingIn(bioOf('C5'))).not.toBeNull();
    clock.finish();
    expect(totalOf('C3').textContent).toBe(BASE5.C3);
  });

  it('시험 ③: 움직임 줄임이면 처음부터 끝 글자 · rAF 0', async () => {
    const clock = motionStubs({ reduce: true });
    render(view(portOf(fakeScope3Server({ runs: [runs[0]!] }))));
    await screen.findByTestId('s3-result');
    expect(anyRolling()).toBe(0);
    expect(clock.pending()).toBe(0);
    expect(totalOf('C3').textContent).toBe(BASE5.C3);
    expect(bioOf('C5').textContent).toBe(BASE5.C5bio);
    // 끝 그림(굴림 0)에도 값 칸 tabular-nums(디자인 e6 (나)).
    expect(totalOf('C3').firstElementChild!.className).toContain(
      'tabular-nums',
    );
    expect(bioOf('C5').querySelector('.tabular-nums')!.textContent).toBe('0.5');
  });

  it('시험 ④: 굴리는 동안 카드 단추의 화면 읽기 글 = BASE · 굴림 칸은 프레임·깔개 aria-hidden + sr-only 끝 글자 하나', async () => {
    const clock = motionStubs();
    render(view(portOf(fakeScope3Server({ runs: [runs[0]!] }))));
    await screen.findByTestId('s3-result');
    clock.advance(0);
    clock.advance(300);
    expect(rollingIn(totalOf('C3'))).not.toBeNull();
    expect(spoken(within(cardOf('C3')).getByRole('button'))).toBe(BASE5.C3name);
    expect(spoken(within(cardOf('C5')).getByRole('button'))).toBe(BASE5.C5name);
    for (const node of [totalOf('C3'), bioOf('C5')]) {
      const box = rollingIn(node)!;
      const heard = [...box.children].filter(
        (child) => child.getAttribute('aria-hidden') !== 'true',
      );
      expect(heard.map((one) => one.className)).toEqual(['sr-only']);
    }
    clock.finish();
  });
});

describe('ResultView — C3 「확인 필요 — 2차에서 보정」(밴드 S3N1)', () => {
  const cardOf = (id: string) =>
    screen
      .getAllByTestId('s3-result-card')
      .find((card) => card.getAttribute('data-category') === id)!;
  const draw = async () => {
    const server = fakeScope3Server({
      runs: [
        {
          id: 5,
          status: 'done',
          reportYear: 2025,
          result: fakeDoneResult({
            sheets: [
              processedSheet('s1', 'Category1', [purchaseRow('12')]),
              processedSheet('s3', 'Category3', [
                energyRow('leased_asset', '3.5'),
              ]),
            ],
          }),
        },
      ],
    });
    render(
      <ResultView
        port={portOf(server)}
        runId="5"
        year={2025}
        onUpload={() => {}}
      />,
    );
    await screen.findByTestId('s3-result');
  };

  it('C3 카드 이름 옆에 고정 안내 하나 — 글은 글 표 그대로, 주황 글 · 아이콘', async () => {
    await draw();
    const marks = within(cardOf('C3')).getAllByTestId('s3-adjust-later');
    expect(marks).toHaveLength(1);
    const mark = marks[0]!;
    expect(S3_TEXT.result.adjustLater).toBe('확인 필요 — 2차에서 보정');
    expect(mark.textContent).toBe(S3_TEXT.result.adjustLater);
    expect(mark.getAttribute('class')).toContain('text-support-orange-dark');
    expect(mark.querySelector('svg')).not.toBeNull();
    // 이름 칸 안(이름 옆).
    expect(mark.parentElement!.textContent).toBe(
      `${S3_TEXT.result.cards.C3} ${S3_TEXT.result.adjustLater}`,
    );
  });

  it('다른 카드(C1·C2·C4~C15, 꺼진 C10 포함)에는 없다 — 화면 전체에 하나', async () => {
    await draw();
    expect(screen.getAllByTestId('s3-adjust-later')).toHaveLength(1);
    for (const id of ['C1', 'C2', 'C4', 'C5', 'C10', 'C12', 'C15'])
      expect(within(cardOf(id)).queryByTestId('s3-adjust-later')).toBeNull();
  });

  it('툴팁 0 — title 속성 · tooltip 역할 · aria-describedby 없음', async () => {
    await draw();
    const mark = within(cardOf('C3')).getByTestId('s3-adjust-later');
    for (const node of [mark, ...Array.from(mark.querySelectorAll('*'))]) {
      expect(node.hasAttribute('title')).toBe(false);
      expect(node.hasAttribute('aria-describedby')).toBe(false);
    }
    expect(mark.closest('[title]')).toBeNull();
    expect(screen.queryByRole('tooltip')).toBeNull();
  });
});
