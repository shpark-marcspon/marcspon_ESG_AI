// @vitest-environment jsdom
// DV-04·04a 결과 화면 시험(밴드 DV2a ③ — 발주서 §3-3 11). 저장소는 가짜 데이터 검증 서버를 앞에 둔 실어댑터(목 0).
//   예시 → 칸 넷(검사 5 · 어긋남 1 · 계산 못 함 4 · 리스크 2) · 줄 5 · 「어긋남·계산 못 함만」 · 펼침 = 한국어 계산 식 ·
//   검토 실패 → 04a 띠·실패 전 줄 · Plan 읽지 못함 → 띠·검토 돌리지 않음 · unparsed 원문 · 출처 0 · 파일 없음 → 단추 0 ·
//   받기 실패 글 · 404 · 409 → onNotDone · 「1회차」 0 · [다시 실행]. 서버 message 는 화면에 0.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  fakeDataverifyServer,
  fakeRun,
  fakeSteps,
  refusal,
  serverStoreOf,
} from '../../../entities/dataverify/api/testing.ts';
import type {
  FakeDataverifyServer,
  FakeRun,
} from '../../../entities/dataverify/api/testing.ts';
import { DV_TEXT } from '../../../entities/dataverify/config/text.ts';
import {
  NOT_RUN_REVIEW,
  fakeChecks,
  fakeInput,
  fakeResult,
  insightDone,
  insightFailed,
  noTargetResult,
  planFailed,
  reviewDone,
  reviewFailed,
} from '../../../entities/dataverify/model/testing.ts';
import { PageInfoIcon } from '../../../shared/ui/page-info/index.ts';
import { ResultScreen } from './ResultScreen.tsx';

const words = DV_TEXT.result;
const common = DV_TEXT.common;
const WAIT = { timeout: 3_000 };

// jsdom 의 URL 에는 createObjectURL·revokeObjectURL 이 없다 — 시험 동안만 가짜(shared DownloadButton 시험 꼴).
const original = {
  create: URL.createObjectURL,
  revoke: URL.revokeObjectURL,
};
let saved: string[] = [];
beforeEach(() => {
  saved = [];
  URL.createObjectURL = vi.fn(() => 'blob:fake-1');
  URL.revokeObjectURL = vi.fn();
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    saved.push(this.download);
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  URL.createObjectURL = original.create;
  URL.revokeObjectURL = original.revoke;
});

const DONE: Partial<FakeRun> = {
  status: 'done',
  steps: fakeSteps(5),
  finishedAt: '2026-10-19T10:58:00+09:00',
  files: ['dataverify-report.xlsx'],
};

function setup(result: Record<string, unknown> = fakeResult(), run = DONE) {
  const server = fakeDataverifyServer({
    runs: [fakeRun(7, { ...run, result })],
  });
  const store = serverStoreOf(server, { pollMs: 5 });
  const props = { onBack: vi.fn(), onRerun: vi.fn(), onNotDone: vi.fn() };
  render(<ResultScreen store={store} runId="7" {...props} />);
  return { server, ...props };
}

/** 응답을 붙잡아 두는 서버(첫 불러오기 시험 — 밴드 DV2e). release() 뒤에야 답한다. */
function held(server: FakeDataverifyServer) {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  return {
    server: {
      ...server,
      send: async (request: Request) => {
        await gate;
        return server.send(request);
      },
    },
    release: () => act(async () => release()),
  };
}

const ready = () =>
  screen.findByTestId('cards', undefined, WAIT).then(() => undefined);
const stat = (id: string) => screen.getByTestId(`stat-${id}`).textContent;
const lineNos = () => [
  ...new Set(
    [...document.querySelectorAll('[data-card="checks"] tr[data-line]')].map(
      (row) => row.getAttribute('data-line'),
    ),
  ),
];
const bands = () =>
  screen.queryAllByTestId('band').map((el) => el.getAttribute('data-notice'));
const body = () => document.body.textContent ?? '';

describe('DV-04 결과', () => {
  it('예시: 머리(기업명·완료·메타 — 「1회차」 0) · 단계 줄 · 칸 다섯(검산 6곳 ┃ 리스크) · Plan 2 · 줄 5 · 리스크 2 · 출처 · 검토 글', async () => {
    setup();
    await ready();
    expect(screen.getByTestId('meta').textContent).toBe(
      words.meta('2026-10-19 10:58', '가상건설', '2025', 12, 4, '2022~2024년'),
    );
    expect(body()).not.toContain('1회차');
    expect(screen.queryByTestId('some-failed')).toBeNull();
    const review = document.querySelector('[data-stage="review"]')!;
    expect(review.getAttribute('data-state')).toBe('partial');
    expect(review.textContent).toContain(words.partialTag);
    expect(stat('checks')).toBe(words.cards.checksValue(6));
    expect(stat('ok')).toBe(words.cards.okValue(1));
    expect(stat('mismatches')).toBe(words.cards.mismatchesValue(1));
    expect(stat('uncomputable')).toBe(words.cards.uncomputableValue(4));
    expect(stat('risks')).toBe(words.cards.risksValue(2));
    expect(body()).toContain(words.cards.checksSub);
    expect(body()).not.toContain('연도별로 맞음');
    // 칸 다섯 차례 · 넷째와 다섯째 사이 세로선(시안 v212 DV-04 r2, 밴드 DV7)
    const cards = [...screen.getByTestId('cards').children];
    expect(
      cards.map(
        (el) => el.getAttribute('data-stat') ?? el.getAttribute('data-testid'),
      ),
    ).toEqual([
      'checks',
      'ok',
      'mismatches',
      'uncomputable',
      'cards-sep',
      'risks',
    ]);
    expect(cards[4]!.getAttribute('aria-hidden')).toBe('true');
    expect(cards[4]!.className).toContain('bg-border-tertiary');
    expect(cards[1]!.textContent).toBe(
      words.cards.ok + words.cards.okValue(1) + '차이 0',
    );
    expect(screen.getByTestId('cards').className).toContain(
      'lg:grid-cols-[repeat(4,minmax(0,1fr))_auto_minmax(0,1fr)]',
    );
    expect(body()).toContain(words.cards.uncomputableSub(1, 1, 2));
    expect(body()).toContain(words.planLead(2));
    // 판정 허용 오차 0 인 새 실행(settings.tolerance "0.0" — 밴드 DV16, sid:MARC-ENT-685): 머리·카드에 「허용 오차」 없음
    expect(body()).toContain(
      '차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p',
    );
    expect(body()).toContain('차이가 있는 연도');
    expect(body()).not.toContain('허용 오차');
    expect(lineNos()).toEqual(['1', '2', '3', '4', '5']);
    expect(screen.getAllByTestId('risk-row')).toHaveLength(2);
    // 출처: 공통 링크 칩(이름 = 제목 — 밴드 DV10)
    expect(
      within(screen.getByTestId('sources'))
        .getByRole('link', { name: /^가상 기준서 · example\.org · / })
        .getAttribute('href'),
    ).toBe('https://example.org/standard');
    // 검토 글은 md 서식(밴드 DV10) — 「## 」 는 제목 요소가 되고 글자로 남지 않는다
    expect(
      within(screen.getByTestId('review-text')).getByRole('heading', {
        name: '1. 총 배출량 합계 검증',
      }),
    ).toBeTruthy();
    expect(screen.getByTestId('review-text').textContent).not.toContain('##');
    // 계산 검토 partial 띠(산식 2개)
    expect(bands()).toEqual(['review_partial']);
    expect(screen.getByTestId('band').textContent).toBe(
      DV_TEXT.notices.review_partial.band(2),
    );
    expect(body()).not.toContain('지어낸 도구 오류');
    expect(body()).not.toContain('지어낸-');
  });

  it('줄: 항목 칸(이름형 합계 · 단건 부분합 「값 없음」) · 도구 오류 줄(규칙 대응·모르면 –) · 줄 id(data-line) 1..n · 순번 열 없음(밴드 DV17)', async () => {
    setup();
    await ready();
    const row = (no: string) =>
      [
        ...document.querySelectorAll(
          `[data-card="checks"] tr[data-line="${no}"]`,
        ),
      ].map((r) => r.textContent ?? '');
    expect(row('1')[0]).toContain(
      '합계 온실가스 배출량 | 총 배출량 | Scope 1+2 | tCO2eq',
    );
    expect(row('1')).toHaveLength(2);
    expect(row('2')[0]).toContain('더한 값 1200.5 + 값 없음 ≈ 대상 1500');
    expect(row('2')[0]).toContain(words.notes['non-numeric']);
    expect(row('3')[0]).toContain(words.notes['division by zero']);
    expect(row('4')[0]).toContain(words.rules.sum);
    expect(row('4')[0]).toContain(words.notes.tool);
    // 모르는 도구(value_of)의 규칙은 「–」
    const unknown = document.querySelector('tr[data-line="5"]')!;
    expect(unknown.querySelectorAll('td')[0]!.textContent).toBe(DV_TEXT.dash);
  });

  it('펼침: [보기] → 이름 단 줄 다섯(계산식·입력값·실제값·판정·차이 — 밴드 DV6 ①) · [접기]', async () => {
    setup();
    await ready();
    const mismatch = document.querySelector(
      'tr[data-line="1"][data-verdict="mismatch"]',
    )!;
    fireEvent.click(within(mismatch as HTMLElement).getByRole('button'));
    const rows = words.explainRows;
    const detail = (key: string) =>
      screen.getByTestId('formula').querySelector(`[data-detail="${key}"]`)!
        .textContent;
    expect(
      [...screen.getByTestId('formula').querySelectorAll('[data-detail]')].map(
        (el) => el.getAttribute('data-detail'),
      ),
    ).toEqual(['formula', 'input', 'actual', 'verdict', 'diff']);
    expect(detail('formula')).toContain(rows.formula);
    expect(detail('formula')).toContain('합계 ');
    expect(detail('formula')).toContain(' = ');
    expect(detail('input')).toBe(`${rows.input}(${rows.inputHint})1605.0`);
    // 실제값 뒤 괄호 = 더한 값(밴드 DV17)
    expect(detail('actual')).toBe(
      `${rows.actual}(${rows.actualHint})1610.0 (1300.0 + 310.0)`,
    );
    expect(detail('verdict')).toBe(`${rows.verdict}${words.verdicts.mismatch}`);
    // 차이 뒤 = 대상 항목의 단위(이름형 대상의 넷째 칸 — 밴드 DV10) · 허용 오차 0 인 검산은 차이만(밴드 DV16)
    expect(detail('diff')).toBe(`${rows.diff}5.0 tCO2eq`);
    fireEvent.click(screen.getByRole('button', { name: words.hide }));
    expect(screen.queryByTestId('formula')).toBeNull();
    const zero = document.querySelector('tr[data-line="3"]')!;
    fireEvent.click(within(zero as HTMLElement).getByRole('button'));
    expect(detail('actual')).toBe(
      `${rows.actual}(${rows.actualHint})${DV_TEXT.dash} · ${words.explain.divisionByZero}`,
    );
    expect(detail('verdict')).toBe(
      `${rows.verdict}${words.verdicts.uncomputable}`,
    );
    expect(detail('diff')).toBe(`${rows.diff}${DV_TEXT.dash}`);
  });

  it('펼침(비율): 입력값 = 적힌 % · 실제값 = 계산한 % · 차이 %p(밴드 DV6 ① — 검증 B1)', async () => {
    const checks = fakeChecks();
    const ratio = checks.find((check) => check.seq === 6)! as {
      years: unknown[];
    };
    ratio.years = [
      {
        year: '2024',
        ok: true,
        status: 'OK',
        diff: '1.0',
        note: null,
        explanation:
          'Ratio = 30.0/120.0 × 100 = 25.0000%, Expected ≈ 24.0000%, Diff = 1.0000 → within tolerance (1.1 p.p.).',
      },
    ];
    setup(fakeResult({ review: reviewDone(false, checks) }));
    await ready();
    const line = document.querySelector('tr[data-line="3"]')!;
    fireEvent.click(within(line as HTMLElement).getByRole('button'));
    const rows = words.explainRows;
    const detail = (key: string) =>
      screen.getByTestId('formula').querySelector(`[data-detail="${key}"]`)!
        .textContent;
    expect(detail('input')).toBe(`${rows.input}(${rows.inputHint})24.0000%`);
    // 실제값 뒤 괄호 = 분자 ÷ 분모 × 100(밴드 DV17)
    expect(detail('actual')).toBe(
      `${rows.actual}(${rows.actualHint})25.0000% (30.0 ÷ 120.0 × 100)`,
    );
    expect(detail('verdict')).toBe(`${rows.verdict}${words.verdicts.ok}`);
    // 비율은 %p 그대로 — 단위 칸(%)을 붙이지 않는다(밴드 DV10). 이 줄은 옛 실행 꼴(허용 오차 1.1)이라 옛 글
    expect(detail('diff')).toBe(`${rows.diff}1.0%p · 허용 오차 1.1%p 안`);
    expect(detail('formula')).toContain('÷');
  });

  it('펼침 차이 단위: 대상 단위 칸이 비면 수만 · 단건(raw)도 수만(밴드 DV10)', async () => {
    const checks = fakeChecks();
    const sum = checks.find((check) => check.seq === 3)! as {
      items: { byName: { total: unknown[] } };
    };
    sum.items.byName.total = ['온실가스 배출량', '총 배출량', 'Scope 1+2', ' '];
    const raw = {
      seq: 99,
      tool: 'sum_check',
      kind: 'check',
      rule: 'sum',
      items: { byName: null, raw: { a: 1, b: 2, c: 4 } },
      tolerance: '0.01',
      years: [
        {
          year: null,
          ok: false,
          status: 'FAIL',
          diff: '1.0',
          note: null,
          explanation:
            'Sum(1.0 + 2.0) - Target(4.0) = -1.000000 → exceeds tolerance (0.01).',
        },
      ],
    } as (typeof checks)[number];
    setup(fakeResult({ review: reviewDone(false, [...checks, raw]) }));
    await ready();
    const rows = words.explainRows;
    const diffOf = (no: string) => {
      const line = document.querySelector(
        `tr[data-line="${no}"][data-verdict="mismatch"]`,
      )!;
      fireEvent.click(within(line as HTMLElement).getByRole('button'));
      const text = screen
        .getByTestId('formula')
        .querySelector('[data-detail="diff"]')!.textContent;
      fireEvent.click(screen.getByRole('button', { name: words.hide }));
      return text;
    };
    expect(diffOf('1')).toBe(`${rows.diff}5.0`);
    const last = String(lineNos().length);
    expect(diffOf(last)).toBe(`${rows.diff}1.0 · 허용 오차 0.01 넘음`);
  });

  it('옛 실행(판정 허용 오차 1.1 — 밴드 DV16 앞): 머리·카드·차이 칸·빈 글은 그때 규칙 글 그대로', async () => {
    const old = (value: unknown) =>
      JSON.parse(
        JSON.stringify(value)
          .replaceAll('"tolerance":"0.0"', '"tolerance":"1.1"')
          .replaceAll('tolerance (0.0)', 'tolerance (1.1)'),
      ) as ReturnType<typeof fakeChecks>;
    setup(
      fakeResult({
        settings: old(fakeResult().settings),
        review: reviewDone(false, old(fakeChecks())),
      }),
    );
    await ready();
    expect(body()).toContain(
      '허용 오차는 AI 가 검산마다 정하고, 정하지 않은 검산은 기본값(1.1)을 써요 · 항목 단위, 비율은 %p',
    );
    expect(body()).toContain('허용 오차 안');
    expect(body()).toContain('허용 오차를 넘은 연도');
    expect(body()).not.toContain('차이 0');
    const mismatch = document.querySelector(
      'tr[data-line="1"][data-verdict="mismatch"]',
    )!;
    fireEvent.click(within(mismatch as HTMLElement).getByRole('button'));
    expect(
      screen.getByTestId('formula').querySelector('[data-detail="diff"]')!
        .textContent,
    ).toBe(`${words.explainRows.diff}5.0 tCO2eq · 허용 오차 1.1 넘음`);
    cleanup();
    const okOnly = old(fakeChecks().filter((c) => c.seq === 3));
    (okOnly[0]!.years as unknown[]).splice(1, 1);
    setup(
      fakeResult({
        settings: old(fakeResult().settings),
        review: reviewDone(false, okOnly),
      }),
    );
    await ready();
    fireEvent.click(screen.getByTestId('only-problems'));
    expect(screen.getByTestId('no-problems').textContent).toBe(
      '어긋남과 계산 못 함이 없어요. 모든 검사가 허용 오차 안에서 맞았어요',
    );
  });

  it('「최대 횟수」「정해진 횟수」 0 — 펼침·띠·단계 줄 모두(밴드 DV6 ③)', async () => {
    setup();
    await ready();
    for (const button of within(
      document.querySelector('[data-card="checks"]') as HTMLElement,
    ).getAllByRole('button', { name: words.show }))
      fireEvent.click(button);
    expect(body()).toContain(words.partialTag);
    expect(body()).not.toContain('최대 횟수');
    expect(body()).not.toContain('정해진 횟수');
  });

  it('「어긋남·계산 못 함만」: 맞음 해를 빼고 순번 다시 · 다 맞으면 빈 글', async () => {
    setup();
    await ready();
    fireEvent.click(screen.getByTestId('only-problems'));
    expect(
      document.querySelectorAll('[data-card="checks"] tr[data-verdict="ok"]'),
    ).toHaveLength(0);
    expect(lineNos()).toEqual(['1', '2', '3', '4', '5']);
    cleanup();
    const okOnly = fakeChecks().filter((c) => c.seq === 3);
    (okOnly[0]!.years as unknown[]).splice(1, 1);
    setup(fakeResult({ review: reviewDone(false, okOnly) }));
    await ready();
    fireEvent.click(screen.getByTestId('only-problems'));
    expect(screen.getByTestId('no-problems').textContent).toBe(
      '어긋남과 계산 못 함이 없어요. 모든 검사의 차이가 0 이에요',
    );
  });

  it('검토 실패(04a): 「일부 단계 못 함」 · 띠(실패 전 검산한 n곳) · 실패 전 줄 · 표 머리 실패 꼴', async () => {
    setup(fakeResult({ review: reviewFailed() }));
    await ready();
    expect(screen.getByTestId('some-failed').textContent).toBe(
      words.someFailed,
    );
    expect(bands()).toEqual(['review_failed']);
    // 실패 전 기록 셋(search·value·합계) → 표 줄 하나, 연도 둘 = 검산 2곳
    expect(screen.getByTestId('band').textContent).toBe(
      DV_TEXT.notices.review_failed.band(2),
    );
    expect(body()).toContain(
      '실패 전까지 검산 2곳 · 차이가 0 이 아니면 어긋남이에요 · 항목 단위, 비율은 %p',
    );
    expect(body()).toContain('실패 전까지 검산한 2곳은');
    expect(body()).toContain('실패 전까지 검산 2곳 · ');
    expect(lineNos()).toEqual(['1']);
    expect(document.querySelector('[data-card="review"]')).toBeNull();
  });

  it('Plan 읽지 못함: 띠 하나 · Plan 표 없음 · 검토 「돌리지 않음」·「한 검사가 없어요」', async () => {
    setup(
      fakeResult({ plan: planFailed('unparsable'), review: NOT_RUN_REVIEW }),
    );
    await ready();
    expect(bands()).toEqual(['plan_unreadable']);
    expect(document.querySelector('[data-card="plan"]')).toBeNull();
    expect(
      document
        .querySelector('[data-stage="review"]')!
        .getAttribute('data-state'),
    ).toBe('not_run');
    expect(screen.getByTestId('no-checks').textContent).toBe(words.noChecks);
  });

  it('리스크: unparsed 원문 · 빈 표 · 실패 · 실패 + 일부 원문 · 출처 0 이면 칸 숨김', async () => {
    setup(fakeResult({ insight: insightDone({ rowsParsed: 'unparsed' }) }));
    await ready();
    expect(screen.getByTestId('risks-unparsed').textContent).toBe(
      words.risksUnparsed,
    );
    // 표로 못 읽은 원문도 md 서식 — 머리줄 있는 GFM 표는 표 요소(밴드 DV10)
    expect(
      within(screen.getByTestId('raw')).getByRole('table').textContent,
    ).toContain('지어낸 관찰');
    expect(screen.getByTestId('raw').textContent).not.toContain('|---|');
    expect(screen.queryAllByTestId('risk-row')).toHaveLength(0);
    expect(stat('risks')).toBe(DV_TEXT.dash);
    expect(body()).toContain(words.cards.risksUnparsed);
    cleanup();

    setup(fakeResult({ insight: insightDone({ rows: [], sources: [] }) }));
    await ready();
    expect(screen.getByTestId('risks-empty').textContent).toBe(
      words.risksEmpty,
    );
    expect(screen.queryByTestId('sources')).toBeNull();
    expect(stat('risks')).toBe(words.cards.risksValue(0));
    cleanup();

    setup(fakeResult({ insight: insightFailed() }));
    await ready();
    expect(screen.getByTestId('risks-failed').textContent).toBe(
      words.risksFailed,
    );
    expect(bands()).toEqual(['review_partial', 'insight_failed']);
    expect(body()).toContain(words.cards.risksNone);
    cleanup();

    setup(fakeResult({ insight: insightFailed('timeout', '지어낸 일부 글') }));
    await ready();
    expect(screen.getByTestId('risks-partial').textContent).toBe(
      words.risksPartialText,
    );
    expect(screen.getByTestId('raw').textContent).toBe('지어낸 일부 글');
  });

  it('테마 없음: 경고 띠 · 리스크 카드 없음', async () => {
    setup(noTargetResult());
    await ready();
    expect(bands()).toEqual(['no_target']);
    expect(document.querySelector('[data-card="risks"]')).toBeNull();
    expect(document.querySelector('[data-card="plan"]')).toBeNull();
  });

  it('[내려받기](DV-04b r1, 밴드 DV15): 머리 단추 → 공용 받기 모달 한 줄 → 받음 · 실패면 그 줄 아래 alert · 카드 0 · 파일 없으면 단추 0', async () => {
    const { server } = setup();
    await ready();
    const text = words.downloads;
    const head = screen.getByTestId('download-head');
    expect(head.textContent).toBe(common.download);
    expect(common.download).toBe('내려받기');
    expect(head.querySelector('svg')).not.toBeNull();
    expect(screen.queryByTestId('download-card')).toBeNull();
    expect(document.querySelector('[data-card="file"]')).toBeNull();
    // 단추는 받지 않는다 — 모달만 연다.
    fireEvent.click(head);
    expect(server.count('GET /runs/7/files/dataverify-report.xlsx')).toBe(0);
    const dialog = await screen.findByTestId('download-dialog');
    expect(screen.getByRole('dialog', { name: common.download })).toBe(dialog);
    const rows = dialog.querySelectorAll('li[data-file]');
    expect([...rows].map((row) => row.getAttribute('data-file'))).toEqual([
      'report',
    ]);
    expect(rows[0]!.textContent).toContain(text.reportName);
    expect(rows[0]!.textContent).toContain(text.reportNote);
    expect(text.reportNote).toBe(
      'AI 데이터 검증 결과물 — 검증 결과와 리스크 표를 담은 엑셀이에요',
    );
    const file = screen.getByTestId('download-dialog-file-report');
    expect(file.textContent).toContain('dataverify-report.xlsx');
    expect(file.getAttribute('aria-disabled')).toBeNull();
    expect(dialog.textContent).toContain(text.close);
    await act(async () => {
      fireEvent.click(file);
    });
    await vi.waitFor(
      () => expect(saved).toEqual(['dataverify-report.xlsx']),
      WAIT,
    );
    expect(server.count('GET /runs/7/files/dataverify-report.xlsx')).toBe(1);
    server.override['GET /runs/7/files/dataverify-report.xlsx'] = () =>
      refusal(500, 'INTERNAL');
    await act(async () => {
      fireEvent.click(file);
    });
    await vi.waitFor(
      () =>
        expect(
          dialog.querySelector('li[data-file="report"] [role="alert"]')
            ?.textContent,
        ).toBe(common.downloadFailed),
      WAIT,
    );
    fireEvent.click(screen.getByRole('button', { name: text.close }));
    await vi.waitFor(
      () => expect(screen.queryByTestId('download-dialog')).toBeNull(),
      WAIT,
    );
    await vi.waitFor(
      () =>
        expect(document.activeElement).toBe(
          screen.getByTestId('download-head'),
        ),
      WAIT,
    );
    cleanup();
    setup(fakeResult(), { ...DONE, files: [] });
    await ready();
    expect(screen.queryByTestId('download-head')).toBeNull();
    expect(screen.queryByRole('button', { name: common.download })).toBeNull();
    expect(document.querySelector('[data-card="file"]')).toBeNull();
  });

  it('[다시 실행]: 받은 options 그대로 새 POST → onRerun · 거절이면 시작 실패 글', async () => {
    const { server, onRerun } = setup();
    await ready();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    });
    await vi.waitFor(() => expect(onRerun).toHaveBeenCalledWith('30'), WAIT);
    expect(server.posts()[0]!.body).toEqual({
      module: 'dataverify',
      launchKey: expect.stringMatching(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
      ),
      options: server.runs.get(7)!.options,
    });
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    });
    expect(
      (await screen.findByTestId('rerun-error', undefined, WAIT)).textContent,
    ).toBe(DV_TEXT.newCheck.errors.startFailed);
    expect(onRerun).toHaveBeenCalledTimes(1);
  });

  it('아직 끝나지 않음(409) → onNotDone · 없음(404) → 찾을 수 없음 · 그 밖 → 불러오지 못함', async () => {
    const first = setup(fakeResult(), { status: 'processing' });
    await vi.waitFor(
      () => expect(first.onNotDone).toHaveBeenCalledTimes(1),
      WAIT,
    );
    cleanup();

    const server = fakeDataverifyServer();
    const onBack = vi.fn();
    render(
      <ResultScreen
        store={serverStoreOf(server)}
        runId="99"
        onBack={onBack}
        onRerun={vi.fn()}
        onNotDone={vi.fn()}
      />,
    );
    await screen.findByText(common.notFound, undefined, WAIT);
    cleanup();

    const again = fakeDataverifyServer({
      runs: [fakeRun(7, { ...DONE, result: fakeResult() })],
    });
    again.override['GET /dataverify/runs/7/result'] = [
      () => refusal(500, 'INTERNAL'),
    ];
    render(
      <ResultScreen
        store={serverStoreOf(again)}
        runId="7"
        onBack={vi.fn()}
        onRerun={vi.fn()}
        onNotDone={vi.fn()}
      />,
    );
    await screen.findByText(words.loadFailed, undefined, WAIT);
    fireEvent.click(screen.getByRole('button', { name: common.retry }));
    await ready();
  });
});

describe('DV-04 첫 불러오기(DV2e)', () => {
  it('응답 전에는 셸 제목 「데이터 검증」이 제목 자리에 없음(제목·메타 막대) → 응답 뒤 출처 제목', async () => {
    const { server, release } = held(
      fakeDataverifyServer({
        runs: [
          fakeRun(7, {
            ...DONE,
            options: {
              input: fakeInput(),
              source: { kind: 'file', name: 'a.json' },
            },
            result: fakeResult(),
          }),
        ],
      }),
    );
    const store = serverStoreOf(server, { pollMs: 5 });
    render(
      <ResultScreen
        store={store}
        runId="7"
        onBack={vi.fn()}
        onRerun={vi.fn()}
        onNotDone={vi.fn()}
      />,
    );
    await act(async () => {});
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading.textContent).not.toContain(DV_TEXT.shell.title);
    expect(screen.getByTestId('title-pending')).toBeTruthy();
    expect(screen.getByTestId('description-pending')).toBeTruthy();
    await release();
    await ready();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toContain(
      'a.json',
    );
    expect(screen.queryByTestId('title-pending')).toBeNull();
  });
});

describe('DV-04 머리 제목 = 출처 글(DV2b)', () => {
  const heading = () =>
    document.querySelector('[data-screen="dataverify-result"] h2')?.textContent;
  it('파일 → 파일 이름 · 붙여 넣기 → 「붙여 넣은 데이터」 · 출처 없는 옛 실행 → 기업명(메타 줄은 기업명 그대로)', async () => {
    for (const [source, title] of [
      [{ kind: 'file', name: 'EDK_가상_2025.json' }, 'EDK_가상_2025.json'],
      [{ kind: 'paste' }, DV_TEXT.source.paste],
      [undefined, '가상건설'],
    ] as const) {
      setup(fakeResult(), {
        ...DONE,
        options:
          source === undefined ?
            { input: fakeInput() }
          : { input: fakeInput(), source },
      });
      await ready();
      await waitFor(() => expect(heading()).toContain(title), WAIT);
      expect(heading()).toContain(DV_TEXT.result.done);
      expect(screen.getByTestId('meta').textContent).toContain('가상건설');
      cleanup();
    }
  });
});

describe('DV-04 띠 아이콘 · 「계산 계획」(DV2c)', () => {
  it('단계 띠·테마 없음 띠의 아이콘 = 공용 PageInfoIcon · 계산 계획 표 제목·단계 이름은 「계산 계획」', async () => {
    const icon = render(<PageInfoIcon />, {
      container: document.createElement('div'),
    }).container.innerHTML;
    const bandIcon = () =>
      screen.getByTestId('band').querySelector('svg')?.outerHTML;
    setup();
    await ready();
    expect(bandIcon()).toBe(icon);
    expect(document.querySelector('[data-card="plan"]')!.textContent).toContain(
      '계산 계획',
    );
    expect(
      document.querySelector('[data-stage="plan"]')!.textContent,
    ).toContain('계산 계획');
    expect(body()).not.toContain('계산 Plan');
    cleanup();
    setup(noTargetResult());
    await ready();
    expect(bandIcon()).toBe(icon);
  });
});

describe('DV-04 시안 대조 손질(밴드 DV3 ①)', () => {
  const tableOf = (card: string) =>
    document.querySelector(`[data-card="${card}"] table`)!;

  it('W1 표 셋: 머리 회색 바탕·500 14 · 몸 400 14 · 700 0 · 차이·계산 식 칸 오른쪽(순번 열 없음 — 밴드 DV17) · 「–」 칸 tertiary', async () => {
    setup();
    await ready();
    for (const card of ['plan', 'checks', 'risks']) {
      const table = tableOf(card);
      const ths = [...table.querySelectorAll('th')];
      // 계획 표는 산식 한 열(밴드 DV17)
      expect(ths.length).toBeGreaterThan(card === 'plan' ? 0 : 1);
      for (const th of ths) {
        expect(th.className).toContain('bg-support-grey-subtle');
        expect(th.className).toContain('text-style-pre-body-05');
      }
      const tds = [...table.querySelectorAll('td')];
      expect(tds.length).toBeGreaterThan(1);
      for (const td of tds)
        expect(td.className).toContain('text-style-pre-body-06');
      expect(
        [...table.querySelectorAll('th, td')].some((cell) =>
          cell.className.includes('text-style-pre-body-04'),
        ),
      ).toBe(false);
    }
    const heads = [...tableOf('checks').querySelectorAll('th')];
    expect(
      heads
        .filter((th) => th.className.includes('text-right'))
        .map((th) => th.textContent),
    ).toEqual([words.checksHead[4], words.checksHead[6]]);
    expect(words.checksHead).not.toContain('순번');
    // 줄 1 의 첫 연도 줄(규칙·항목 rowSpan 칸이 있는 줄)
    const first = document.querySelector('tr[data-line="1"]')!;
    const cells = [...first.querySelectorAll('td')];
    expect(cells).toHaveLength(words.checksHead.length);
    expect(cells[0]!.className).not.toContain('text-right');
    expect(cells[cells.length - 1]!.className).toContain('text-right');
    expect(cells[cells.length - 3]!.className).toContain('text-right');
    const dashes = [...tableOf('checks').querySelectorAll('td')].filter(
      (td) => td.textContent === DV_TEXT.dash,
    );
    expect(dashes.length).toBeGreaterThan(0);
    for (const td of dashes)
      expect(td.querySelector('span')!.className).toContain(
        'text-text-tertiary',
      );
    // 계획 표 = 산식 한 열(번호 열 없음 — 밴드 DV17)
    expect(
      [...tableOf('plan').querySelectorAll('th')].map((th) => th.textContent),
    ).toEqual(['산식']);
    expect(tableOf('plan').querySelector('td')!.className).not.toContain(
      'text-right',
    );
  });

  it('W1 긴 칸(메모·계산 식 줄·리스크 글) 위아래 12 · 항목(묶음 칸) 아래 12', async () => {
    setup();
    await ready();
    expect(screen.getAllByTestId('items')[0]!.className).toContain('pb-3');
    const mismatch = document.querySelector(
      'tr[data-line="1"][data-verdict="mismatch"]',
    )!;
    fireEvent.click(within(mismatch as HTMLElement).getByRole('button'));
    expect(screen.getByTestId('formula').closest('td')!.className).toContain(
      'py-3',
    );
    const risk = screen.getAllByTestId('risk-row')[0]!;
    expect(risk.querySelectorAll('td')).toHaveLength(5);
    expect(risk.querySelectorAll('td > div.py-3')).toHaveLength(3);
  });

  it('W8 수 칸: 글 「n회」 그대로 · 안에 small 단위 · 수 display-03 · 이름 500 14 · 꼬리 400 12 · 리스크 null 은 「–」 하나', async () => {
    setup();
    await ready();
    expect(stat('checks')).toBe(words.cards.checksValue(6));
    const value = screen.getByTestId('stat-checks');
    expect(value.className).toContain('text-style-pre-display-03');
    const small = value.querySelector('small')!;
    expect(small.textContent).toBe(words.cards.units.checks);
    expect(small.className).toContain('text-style-pre-body-05');
    const card = document.querySelector('[data-stat="checks"]')!;
    expect(card.className).toContain('p-6');
    expect(card.firstElementChild!.className).toContain(
      'text-style-pre-body-05',
    );
    expect(card.lastElementChild!.className).toContain(
      'text-style-pre-caption-03',
    );
    cleanup();
    setup(fakeResult({ insight: insightDone({ rowsParsed: 'unparsed' }) }));
    await ready();
    expect(stat('risks')).toBe(DV_TEXT.dash);
    expect(
      screen.getByTestId('stat-risks').querySelectorAll('small').length,
    ).toBe(0);
  });

  it('W9 머리 [내려받기]·[다시 실행] 둘 다 outlineGrey(디자인 c3 11-11 — 다섯 모듈 같은 꼴) · 차례 [다시 실행] → [내려받기]', async () => {
    setup();
    await ready();
    const head = screen.getByTestId('download-head');
    expect(head.className).toContain('bg-button-white');
    expect(head.className).not.toContain('bg-button-black');
    const rerun = screen.getByRole('button', { name: common.rerun });
    expect(head.parentElement!.lastElementChild).toBe(head);
    expect(
      rerun.compareDocumentPosition(head) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: common.rerun }).className,
    ).not.toContain('bg-button-black');
  });

  it('원문 자리(검토 글·raw) = 공통 md 부품 — 점선 상자·pre-wrap 0(시안 DV-04 r3, 밴드 DV10)', async () => {
    setup();
    await ready();
    const review = screen.getByTestId('review-text');
    expect(review.hasAttribute('data-markdown')).toBe(true);
    expect(review.className).not.toContain('border-dashed');
    expect(review.className).not.toContain('whitespace-pre-wrap');
    cleanup();
    setup(fakeResult({ insight: insightDone({ rowsParsed: 'unparsed' }) }));
    await ready();
    const raw = screen.getByTestId('raw');
    expect(raw.hasAttribute('data-markdown')).toBe(true);
    expect(raw.className).not.toContain('border-dashed');
  });

  it('W11 단계 줄: 「·」 = 단계 수 − 1 · 이름 400 16 · 「단계」 400 12', async () => {
    setup();
    await ready();
    const stages = screen.getByTestId('stages');
    const dots = [...stages.querySelectorAll('[aria-hidden]')].filter(
      (el) => el.textContent === '·',
    );
    const count = stages.querySelectorAll('[data-stage]').length;
    expect(count).toBeGreaterThan(1);
    expect(dots).toHaveLength(count - 1);
    expect(stages.className).toContain('text-style-pre-body-03');
    expect(stages.firstElementChild!.className).toContain(
      'text-style-pre-caption-03',
    );
  });

  it('J1 계획·리스크·검토 카드 머리는 한 줄(justify-between) · 검증 결과는 쌓인 꼴 · 꼬리 글 400 12', async () => {
    setup();
    await ready();
    const headOf = (card: string) =>
      document.querySelector(`[data-card="${card}"] h3`)!.parentElement!;
    for (const card of ['plan', 'risks', 'review']) {
      const head = headOf(card);
      expect(head.className).toContain('justify-between');
      expect(head.lastElementChild!.className).toContain(
        'text-style-pre-caption-03',
      );
    }
    const checks = headOf('checks');
    expect(checks.className).toContain('flex-col');
    expect(checks.lastElementChild!.className).toContain(
      'text-style-pre-caption-03',
    );
  });

  it('머리 「완료」 배지는 키트 sm(500 12/20) — md 꼴 0(감독 처분 1)', async () => {
    setup();
    await ready();
    const badge = [
      ...document.querySelectorAll('[data-screen="dataverify-result"] h2 *'),
    ].find((el) => el.textContent === words.done)!;
    expect(badge.className).toContain('h-5');
    expect(badge.className).toContain('text-style-pre-caption-02');
    expect(badge.className).not.toContain('h-6');
  });
});

describe('DV-04 움직임(밴드 DV3 ②)', () => {
  afterEach(() => vi.unstubAllGlobals());
  const motionOn = () =>
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: !query.includes('reduce'),
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    );

  it('②-4 수 칸 다섯에 gw-m-rise · 시차 0·70·140·210·280ms(밴드 DV7 — 맞음 칸)', async () => {
    setup();
    await ready();
    const cards = [...document.querySelectorAll<HTMLElement>('[data-stat]')];
    expect(cards.map((card) => card.getAttribute('data-stat'))).toEqual([
      'checks',
      'ok',
      'mismatches',
      'uncomputable',
      'risks',
    ]);
    for (const card of cards)
      expect(card.classList.contains('gw-m-rise')).toBe(true);
    expect(
      cards.map((card) => card.style.getPropertyValue('--gw-m-delay')),
    ).toEqual(['0ms', '70ms', '140ms', '210ms', '280ms']);
  });

  it('②-4 움직임 켬: 수는 처음 「0회」에서 끝 값으로 · 리스크 null 은 처음부터 「–」', async () => {
    motionOn();
    const seen = new Map<string, string[]>();
    const observer = new MutationObserver(() => {
      for (const id of ['checks', 'risks']) {
        const el = document.querySelector(`[data-testid="stat-${id}"]`);
        if (!el) continue;
        const list = seen.get(id) ?? [];
        if (list[list.length - 1] !== el.textContent)
          list.push(el.textContent ?? '');
        seen.set(id, list);
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
    });
    try {
      setup();
      await ready();
      await vi.waitFor(
        () => expect(stat('checks')).toBe(words.cards.checksValue(6)),
        WAIT,
      );
      cleanup();
      setup(fakeResult({ insight: insightDone({ rowsParsed: 'unparsed' }) }));
      await ready();
      await act(async () => {});
    } finally {
      observer.disconnect();
    }
    const checks = seen.get('checks')!;
    expect(checks[0]).toBe(words.cards.checksValue(0));
    expect(checks).toContain(words.cards.checksValue(6));
    expect(seen.get('risks')!.slice(-1)).toEqual([DV_TEXT.dash]);
    expect(stat('risks')).toBe(DV_TEXT.dash);
  });

  it('②-5 띠에 gw-m-rise', async () => {
    setup();
    await ready();
    const list = screen.getAllByTestId('band');
    expect(list.length).toBeGreaterThan(0);
    for (const band of list)
      expect(band.classList.contains('gw-m-rise')).toBe(true);
  });

  it('②-6 「어긋남·계산 못 함만」을 누르면 표 감싸개가 새 노드(gw-m-fade) · 결과 부름 수 그대로', async () => {
    const { server } = setup();
    await ready();
    const wrap = () =>
      document.querySelector('[data-card="checks"] table')!.parentElement!
        .parentElement!;
    const before = wrap();
    expect(before.classList.contains('gw-m-fade')).toBe(true);
    const calls = server.count('GET /dataverify/runs/7/result');
    fireEvent.click(screen.getByTestId('only-problems'));
    const after = wrap();
    expect(after).not.toBe(before);
    expect(after.classList.contains('gw-m-fade')).toBe(true);
    expect(server.count('GET /dataverify/runs/7/result')).toBe(calls);
    // 체크 칸은 감싸개 밖
    expect(after.contains(screen.getByTestId('only-problems'))).toBe(false);
  });

  it('②-5 테마 없음 띠(no_target)에도 gw-m-rise', async () => {
    setup(noTargetResult());
    await ready();
    const list = screen.getAllByTestId('band');
    expect(list.map((band) => band.getAttribute('data-notice'))).toEqual([
      'no_target',
    ]);
    expect(list[0]!.classList.contains('gw-m-rise')).toBe(true);
  });
});

describe('DV-04 공용 DataTable(밴드 DVW1 ①)', () => {
  const checks = () =>
    document.querySelector<HTMLElement>('[data-card="checks"] table')!;
  const firstTd = (no: string) =>
    document
      .querySelector(`[data-card="checks"] tr[data-line="${no}"]`)!
      .querySelectorAll('td');

  it('구조: 검증 결과·리스크 표가 DataTable 꼴(바깥 overflow-x-auto · th scope=col · 정렬 단추 0)', async () => {
    setup();
    await ready();
    for (const card of ['checks', 'risks']) {
      const table = document.querySelector(`[data-card="${card}"] table`)!;
      expect(table.parentElement!.className).toContain('overflow-x-auto');
      const ths = [...table.querySelectorAll('thead th')];
      expect(ths.length).toBeGreaterThan(1);
      for (const th of ths) expect(th.getAttribute('scope')).toBe('col');
      expect(table.querySelectorAll('thead button')).toHaveLength(0);
    }
  });

  it('rowSpan: 줄 1 첫 해 줄 규칙·항목 rowSpan 2 · 둘째 해 줄 칸 = 열 − 2 · [보기] 뒤 3 · 펼침 칸 colSpan 5 · 펼침 줄에 data-line 없음', async () => {
    setup();
    await ready();
    const rows = [
      ...checks().querySelectorAll('tr[data-line="1"]'),
    ] as HTMLElement[];
    expect(rows).toHaveLength(2);
    const head = words.checksHead.length;
    const cells = [...rows[0]!.querySelectorAll('td')];
    for (const td of cells.slice(0, 2))
      expect(td.getAttribute('rowspan')).toBe('2');
    expect(cells[2]!.hasAttribute('rowspan')).toBe(false);
    expect(rows[1]!.querySelectorAll('td')).toHaveLength(head - 2);
    fireEvent.click(within(rows[1]!).getByRole('button'));
    expect(firstTd('1')[0]!.getAttribute('rowspan')).toBe('3');
    const formula = screen.getByTestId('formula').closest('td')!;
    expect(formula.getAttribute('colspan')).toBe('5');
    expect(formula.closest('tr')!.hasAttribute('data-line')).toBe(false);
    expect(lineNos()).toEqual(['1', '2', '3', '4', '5']);
  });

  it('해 하나 줄: [보기] 전 rowspan 없음·align-top · 뒤 규칙·항목 rowSpan 2 · 계산 식 줄 colSpan 5', async () => {
    setup();
    await ready();
    const row = checks().querySelector<HTMLElement>('tr[data-line="2"]')!;
    const before = [...row.querySelectorAll('td')].slice(0, 2);
    for (const td of before) {
      expect(td.hasAttribute('rowspan')).toBe(false);
      expect(td.className).toContain('align-top');
    }
    fireEvent.click(within(row).getByRole('button'));
    for (const td of [...firstTd('2')].slice(0, 2))
      expect(td.getAttribute('rowspan')).toBe('2');
    expect(
      screen.getByTestId('formula').closest('td')!.getAttribute('colspan'),
    ).toBe('5');
  });

  it('rowAttrs: 오류 줄 data-kind="error"(data-verdict 없음) · 해 줄에 data-kind 없음 · risk-row 2', async () => {
    setup();
    await ready();
    const error = checks().querySelector('tr[data-line="4"]')!;
    expect(error.getAttribute('data-kind')).toBe('error');
    expect(error.hasAttribute('data-verdict')).toBe(false);
    const years = [...checks().querySelectorAll('tr[data-verdict]')];
    expect(years.length).toBeGreaterThan(0);
    for (const tr of years) expect(tr.hasAttribute('data-kind')).toBe(false);
    expect(screen.getAllByTestId('risk-row')).toHaveLength(2);
  });

  it('펼침 리셋: [보기] → 「어긋남·계산 못 함만」 켬 → 계산 식 줄 0(거르기가 펼침을 지움) · 결과 부름 수 그대로', async () => {
    const { server } = setup();
    await ready();
    const calls = server.count('GET /dataverify/runs/7/result');
    const mismatch = checks().querySelector<HTMLElement>(
      'tr[data-line="1"][data-verdict="mismatch"]',
    )!;
    fireEvent.click(within(mismatch).getByRole('button'));
    expect(screen.getByTestId('formula')).toBeTruthy();
    fireEvent.click(screen.getByTestId('only-problems'));
    expect(
      checks().querySelector('tr[data-line="1"][data-verdict="mismatch"]'),
    ).not.toBeNull();
    expect(screen.queryByTestId('formula')).toBeNull();
    expect(server.count('GET /dataverify/runs/7/result')).toBe(calls);
  });

  it('같은 줄에 같은 해 글이 둘: [보기] 한 번에 계산 식 하나 · 다른 해 단추는 닫힌 채(검증 B1)', async () => {
    const twins = fakeChecks();
    const years = (twins[2] as { years: { year: string }[] }).years;
    years[1]!.year = '2023';
    setup(fakeResult({ review: reviewDone(false, twins) }));
    await ready();
    const rows = [
      ...checks().querySelectorAll('tr[data-line="1"]'),
    ] as HTMLElement[];
    expect(rows).toHaveLength(2);
    fireEvent.click(within(rows[1]!).getByRole('button'));
    expect(screen.getAllByTestId('formula')).toHaveLength(1);
    expect(
      within(rows[0]!).getByRole('button').getAttribute('aria-expanded'),
    ).toBe('false');
  });

  it('긴 칸: 메모·리스크는 칸 안 감싸개 py-3 · 항목은 pb-3(td 에는 py-3 0) · 「–」 칸 안 span tertiary', async () => {
    setup();
    await ready();
    const items = screen.getAllByTestId('items')[0]!;
    expect(items.className).toContain('pb-3');
    expect(items.closest('td')!.className).not.toContain('py-3');
    const note = checks()
      .querySelector('tr[data-line="4"]')!
      .querySelectorAll('td')[5]!;
    expect(note.querySelector('div')!.className).toContain('py-3');
    expect(note.className).not.toContain('py-3');
    const risk = screen.getAllByTestId('risk-row')[0]!;
    for (const td of risk.querySelectorAll('td'))
      expect(td.className).not.toContain('py-3');
    for (const wrap of risk.querySelectorAll('td > div'))
      expect(wrap.className).toContain('whitespace-pre-wrap');
    const dash = [...checks().querySelectorAll('td')].find(
      (td) => td.textContent === DV_TEXT.dash,
    )!;
    expect(dash.querySelector('span')!.className).toContain(
      'text-text-tertiary',
    );
  });
});

describe('DV-04 배지 · 계획 표 폭(밴드 DVW1 ②)', () => {
  it('②-1 「일부 단계 못 함」 배지는 「완료」와 같은 키트 sm(500 12/20) — md 꼴 0', async () => {
    setup(fakeResult({ review: reviewFailed() }));
    await ready();
    const badge = screen.getByTestId('some-failed');
    expect(badge.className).toContain('h-5');
    expect(badge.className).toContain('text-style-pre-caption-02');
    expect(badge.className).not.toContain('h-6');
  });

  it('②-2 계획 표: table-fixed · col 하나(산식 — 번호 열 없음, 밴드 DV17) · 산식 폭 없음', async () => {
    setup();
    await ready();
    const table = document.querySelector('[data-card="plan"] table')!;
    expect(table.className).toContain('table-fixed');
    const cols = [...table.querySelectorAll(':scope > colgroup > col')];
    expect(cols).toHaveLength(table.querySelectorAll('thead th').length);
    expect(cols.map((col) => (col as HTMLElement).style.width)).toEqual(['']);
  });
});

describe('DV-04 출처 칩(밴드 DV10 — 공통 LinkChip, sid:MARC-ISSUE-565)', () => {
  const sourcesOf = async (
    sources: { title: string | null; url: string }[],
  ) => {
    setup(fakeResult({ insight: insightDone({ sources }) }));
    await ready();
    return screen.getByTestId('sources');
  };
  const NEW_TAB = '새 탭에서 열려요';

  it('제목 있음 → 칩 이름 = 제목 · 도메인 뱃지 · 새 탭 · 주소 글자 0', async () => {
    const list = await sourcesOf([
      { title: '가상 기준서', url: 'https://example.com/std' },
    ]);
    const link = within(list).getByRole('link');
    expect(link.getAttribute('aria-label')).toBe(
      `가상 기준서 · example.com · ${NEW_TAB}`,
    );
    expect(link.getAttribute('href')).toBe('https://example.com/std');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(link.textContent).toBe('example.com가상 기준서↗');
    expect(list.textContent).not.toContain('https://');
  });

  it('제목 없음 → 칩이 주소에서 이름을 짓는다(경로 앞부분)', async () => {
    const list = await sourcesOf([
      { title: null, url: 'https://example.com/long/path' },
    ]);
    const link = within(list).getByRole('link');
    expect(link.getAttribute('href')).toBe('https://example.com/long/path');
    expect(link.getAttribute('aria-label')).toBe(
      `long/path · example.com · ${NEW_TAB}`,
    );
  });

  it('http(s) 밖(javascript:·data:·상대·ftp·빈 글자) → 링크 0 · 글자로(칩이 거름) · HTTPS 대문자는 칩', async () => {
    const list = await sourcesOf([
      { title: null, url: 'javascript:alert(1)' },
      { title: '데이터 글', url: 'data:text/html,x' },
      { title: null, url: '/relative' },
      { title: null, url: 'ftp://x' },
      { title: '빈 주소', url: '' },
      { title: null, url: 'HTTPS://Example.com/a' },
    ]);
    const links = within(list).getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0]!.getAttribute('href')).toBe('HTTPS://Example.com/a');
    const lines = [...list.querySelectorAll('li')].map((li) => li.textContent);
    expect(lines.slice(0, 5)).toEqual([
      'javascript:alert(1)',
      '데이터 글 · data:text/html,x',
      '/relative',
      'ftp://x',
      '빈 주소',
    ]);
    expect(list.innerHTML).not.toContain('href="javascript');
  });

  it('칩 칸(li)은 칩과 같은 상한 — 칩의 100% 는 칸을 줄이지 못한다(밴드 DV11) · 링크 아닌 칸은 줄 폭까지', async () => {
    const list = await sourcesOf([
      { title: '가상 기준서', url: 'https://example.com/std' },
      { title: '가상 기준서', url: 'ftp://example.org/a' },
    ]);
    const [chipCell, textCell] = list.querySelectorAll('li');
    const cap = 'max-w-[min(100%,calc(theme(spacing.16)*5))]';
    expect(chipCell!.classList.contains(cap)).toBe(true);
    expect(chipCell!.classList.contains('min-w-0')).toBe(true);
    expect(within(chipCell!).getByRole('link').className).toContain(cap);
    expect(textCell!.classList.contains('max-w-full')).toBe(true);
    expect(textCell!.classList.contains(cap)).toBe(false);
  });

  it('링크 아닌 출처: 제목 있음 → 「제목 · 값」 · 없음 → 값만 · 회색 · 칩과 같은 글 크기 · 줄 바꿈 그대로(밴드 DV11)', async () => {
    const list = await sourcesOf([
      { title: '가상 기준서', url: 'ftp://example.org/a' },
      { title: '가상 기준서', url: 'mailto:a@example.org' },
      { title: null, url: 'ftp://example.org/a' },
      { title: '  ', url: 'mailto:a@example.org' },
      { title: '가상 기준서', url: 'http:example.org' },
    ]);
    expect(within(list).queryByRole('link')).toBeNull();
    const cells = [...list.querySelectorAll('li')];
    expect(cells.map((li) => li.textContent)).toEqual([
      '가상 기준서 · ftp://example.org/a',
      '가상 기준서 · mailto:a@example.org',
      'ftp://example.org/a',
      'mailto:a@example.org',
      '가상 기준서 · http:example.org',
    ]);
    for (const cell of cells) {
      const text = cell.firstElementChild!;
      expect(text.tagName).toBe('SPAN');
      for (const name of [
        'text-style-pre-caption-02',
        'text-text-tertiary',
        'break-all',
      ])
        expect(text.classList.contains(name)).toBe(true);
    }
  });

  it('utm_source=openai 는 href·title 모두에서 뗌(칩이 뗀다) · 다른 쿼리는 href 에 그대로', async () => {
    const list = await sourcesOf([
      { title: null, url: 'https://example.com/a?b=1&utm_source=openai' },
      { title: '가상 글', url: '  https://example.com/?utm_source=openai' },
      { title: null, url: 'https://example.com/c?utm_source=news&q=1' },
    ]);
    const [first, second, third] = within(list).getAllByRole('link');
    expect(first!.getAttribute('href')).toBe('https://example.com/a?b=1');
    expect(first!.getAttribute('title')).toBe('https://example.com/a?b=1');
    expect(second!.getAttribute('href')).toBe('https://example.com/');
    expect(second!.getAttribute('title')).toBe('https://example.com/');
    expect(third!.getAttribute('href')).toBe(
      'https://example.com/c?utm_source=news&q=1',
    );
    expect(third!.getAttribute('title')).toBe('https://example.com/c?q=1');
    expect(list.innerHTML).not.toContain('openai');
  });

  it('받은 주소를 다시 짓지 않는다 — href 가 공통 칩만 쓴 꼴(IRO 1-1)과 같다(밴드 DV12, sid:MARC-ISSUE-570)', async () => {
    const cases = [
      [
        'https://example.org/p?q=a%20b&utm_source=openai',
        'https://example.org/p?q=a%20b',
      ],
      [
        'https://example.org/p?x=가&utm_source=openai',
        'https://example.org/p?x=가',
      ],
      [
        'https://example.org/p?x=(1)~!*&utm_source=openai',
        'https://example.org/p?x=(1)~!*',
      ],
      [
        'https://example.org/p?flag&utm_source=openai',
        'https://example.org/p?flag',
      ],
      ['https://Example.org/p?utm_source=openai', 'https://Example.org/p'],
      [
        'https://Example.org/p?q=a%20b&x=가',
        'https://Example.org/p?q=a%20b&x=가',
      ],
    ] as const;
    const list = await sourcesOf(cases.map(([url]) => ({ title: null, url })));
    const hrefs = within(list)
      .getAllByRole('link')
      .map((link) => link.getAttribute('href'));
    expect(hrefs).toEqual(cases.map(([, href]) => href));
  });
});

describe('DV-04 md 서식(밴드 DV10 — 공통 MarkdownText, sid:MARC-ENT-572)', () => {
  const MD = [
    '# 지어낸 검토 제목',
    '',
    '**굵은 말** 과 목록:',
    '',
    '- 하나',
    '- 둘',
    '',
    '| 연도 | 차이 |',
    '|---|---|',
    '| 2024 | 5.0 |',
    '',
    '<script>window.__dv10 = 1</script>',
    '',
    '<img src=x onerror="window.__dv10 = 2">',
    '',
    '[나쁜 링크](javascript:alert(1)) · [가상 문서](https://example.com/a?utm_source=openai)',
  ].join('\n');

  it('검토 글: heading·strong·list·table 요소 · <script>·<img onerror> 요소 0 · javascript: 링크 0 · http(s) 링크는 칩', async () => {
    setup(fakeResult({ review: { ...reviewDone(), report: MD } }));
    await ready();
    const box = screen.getByTestId('review-text');
    expect(
      within(box).getByRole('heading', { name: '지어낸 검토 제목' }),
    ).toBeTruthy();
    expect(box.querySelector('strong')!.textContent).toBe('굵은 말');
    expect(within(box).getAllByRole('listitem')).toHaveLength(2);
    expect(within(box).getByRole('table').textContent).toContain('2024');
    expect(box.querySelectorAll('script, img, iframe')).toHaveLength(0);
    // 원 HTML 은 요소가 아니라 글자(또는 사라짐) — onerror 를 단 요소 0
    expect(box.querySelectorAll('[onerror]')).toHaveLength(0);
    const links = within(box).getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0]!.getAttribute('aria-label')).toBe(
      '가상 문서 · example.com · 새 탭에서 열려요',
    );
    expect(links[0]!.getAttribute('title')).toBe('https://example.com/a');
    expect(box.innerHTML).not.toContain('href="javascript');
    expect((window as { __dv10?: number }).__dv10).toBeUndefined();
  });

  it('리스크 unparsed 원문·실패 일부 원문도 같은 부품(제목 요소)', async () => {
    setup(
      fakeResult({
        insight: insightDone({
          rowsParsed: 'unparsed',
          report: '## 지어낸 리스크 요약\n\n**환경** 하나',
        }),
      }),
    );
    await ready();
    const raw = screen.getByTestId('raw');
    expect(
      within(raw).getByRole('heading', { name: '지어낸 리스크 요약' }),
    ).toBeTruthy();
    expect(raw.querySelector('strong')!.textContent).toBe('환경');
    cleanup();
    setup(
      fakeResult({
        insight: insightFailed('timeout', '## 지어낸 멈춘 곳\n\n1. 하나'),
      }),
    );
    await ready();
    const partial = screen.getByTestId('raw');
    expect(
      within(partial).getByRole('heading', { name: '지어낸 멈춘 곳' }),
    ).toBeTruthy();
    expect(within(partial).getAllByRole('listitem')).toHaveLength(1);
  });
});

describe('DV-04 실제값 옆 넣은 값 · 절 접기(밴드 DV17)', () => {
  const sumN = (seq: number, list: string, total: string) =>
    ({
      seq,
      tool: 'sum_n_check',
      kind: 'check',
      rule: 'sum_n',
      items: { byName: null, raw: { addends: [], target: 0 } },
      tolerance: '0.0',
      years: [
        {
          year: null,
          ok: true,
          status: 'OK',
          diff: '0.0',
          note: null,
          explanation: `Sum([${list}]) - Target(${total}) = 0.000000 → within tolerance (0.0).`,
        },
      ],
    }) as ReturnType<typeof fakeChecks>[number];

  it('부분합: 더한 값 「 + 」 괄호 · 더한 값 0개면 괄호 없음', async () => {
    const checks = [
      ...fakeChecks(),
      sumN(97, '4.5, 7.25, 8.0', '19.75'),
      sumN(98, '', '0.0'),
    ];
    setup(fakeResult({ review: reviewDone(false, checks) }));
    await ready();
    const rows = words.explainRows;
    const actualOf = (no: string) => {
      const line = document.querySelector(`tr[data-line="${no}"]`)!;
      fireEvent.click(within(line as HTMLElement).getByRole('button'));
      const text = screen
        .getByTestId('formula')
        .querySelector('[data-detail="actual"]')!.textContent;
      fireEvent.click(screen.getByRole('button', { name: words.hide }));
      return text;
    };
    const count = lineNos().length;
    expect(actualOf(String(count - 1))).toBe(
      `${rows.actual}(${rows.actualHint})19.75 (4.5 + 7.25 + 8.0)`,
    );
    expect(actualOf(String(count))).toBe(`${rows.actual}(${rows.actualHint})0`);
    expect(rows.actualWith('3', { kind: 'sum', addends: [] })).toBe('3');
    expect(
      rows.actualWith('12.5%', {
        kind: 'ratio',
        numerator: '5',
        denominator: '40',
      }),
    ).toBe('12.5% (5 ÷ 40 × 100)');
  });

  it('카드 넷(계산 계획·검증 결과·리스크·검토 글): 기본 펼침 · 누르면 몸 0·머리 남음·「펼치기」 · 다시 누르면 돌아옴', async () => {
    setup(fakeResult({ review: reviewDone(false, fakeChecks()) }));
    await ready();
    const titles = {
      plan: words.planTitle,
      checks: words.checksTitle,
      risks: words.risksTitle,
      review: words.reviewTitle,
    } as const;
    for (const [card, title] of Object.entries(titles)) {
      const el = document.querySelector<HTMLElement>(`[data-card="${card}"]`)!;
      const fold = within(el).getByTestId('fold');
      expect(fold.getAttribute('aria-expanded')).toBe('true');
      expect(fold.getAttribute('aria-label')).toBe(words.fold(title));
      const bodyId = fold.getAttribute('aria-controls')!;
      expect(document.getElementById(bodyId)).not.toBeNull();
      expect(el.contains(document.getElementById(bodyId))).toBe(true);
      fireEvent.click(fold);
      expect(fold.getAttribute('aria-expanded')).toBe('false');
      expect(fold.getAttribute('aria-label')).toBe(words.unfold(title));
      expect(document.getElementById(bodyId)).toBeNull();
      expect(el.querySelector('table')).toBeNull();
      expect(el.querySelector('[data-testid="review-text"]')).toBeNull();
      expect(within(el).getByRole('heading', { name: title })).toBeTruthy();
      fireEvent.click(fold);
      expect(fold.getAttribute('aria-expanded')).toBe('true');
      expect(document.getElementById(bodyId)).not.toBeNull();
    }
    expect(screen.getAllByTestId('fold')).toHaveLength(4);
    expect(words.fold('검토 글')).toBe('검토 글 접기');
    expect(words.unfold('검토 글')).toBe('검토 글 펼치기');
  });

  it('검증 결과를 접으면 「어긋남·계산 못 함만」 상자·각주도 없음 · 거르기는 접었다 펴도 그대로', async () => {
    setup();
    await ready();
    const card = document.querySelector<HTMLElement>('[data-card="checks"]')!;
    fireEvent.click(screen.getByTestId('only-problems'));
    const fold = within(card).getByTestId('fold');
    fireEvent.click(fold);
    expect(screen.queryByTestId('only-problems')).toBeNull();
    expect(card.textContent).not.toContain(words.checksFootnote);
    expect(card.querySelector('tr[data-line]')).toBeNull();
    fireEvent.click(fold);
    expect(
      (screen.getByTestId('only-problems') as HTMLInputElement).checked,
    ).toBe(true);
    expect(card.querySelectorAll('tr[data-verdict="ok"]')).toHaveLength(0);
  });
});
