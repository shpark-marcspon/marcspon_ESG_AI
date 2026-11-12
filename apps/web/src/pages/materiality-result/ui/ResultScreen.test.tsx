// @vitest-environment jsdom
// IR-04·04a 결과 화면 시험(밴드 IRW1 ② — 발주서 §3-2 9). 저장소는 가짜 중대성평가 서버를 앞에 둔 실어댑터(목 0).
//   머리(기업명·완료·메타 — 「1회차」 0) · 카드 다섯 · 기본 탭 2-1 · 토픽 고르기·유형 탭·거른 빔·[거르기 풀기] · 정하지 못함 줄은 「전체」 끝에만 ·
//   2-2 줄 누르면 펼침 · 1-1 합침·리서치 못 함·javascript: 링크 0·빈 컨트로버시 안내 · 경고 줄 · 엑셀 단추 둘(sid:MARC-ENT-449 — 최종·리서치, 파일이 있을 때만)·받기 실패 ·
//   part2 not_run · 409 → onNotDone · 404 · [다시 실행]. 서버 message 는 화면에 0. 키트 Tabs(radix)는 mouseDown 으로 누른다.
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  REPORT,
  WEBSEARCH,
  doneRun,
  fakeMaterialityServer,
  fakeRun,
  refusal,
  serverStoreOf,
} from '../../../entities/materiality/api/testing.ts';
import type { FakeRun } from '../../../entities/materiality/api/testing.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import {
  FAKE_COMPANY,
  ctx,
  done,
  failed,
  fakeResult,
  financialRow,
  impactRow,
  item,
  notRun,
  part1Topic,
  pathwayRow,
  subtopic,
  warning,
} from '../../../entities/materiality/model/testing.ts';
import { ResultScreen } from './ResultScreen.tsx';

const words = IR_TEXT.result;
const common = IR_TEXT.common;
const dl = IR_TEXT.result.downloads;
const dash = IR_TEXT.dash;
/** 공통 링크 칩 aria-label 의 끝말(shared/ui 글 — 화면 시험은 글자로 본다). */
const NEW_TAB = '새 탭에서 열려요';
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

type Json = Record<string, unknown>;
const topic = (name: string, subtopics: Json[]) => ({
  topic: name,
  description: `${name} 설명`,
  subtopics,
});

/** 화면 시험의 결과: 토픽 둘(A — 가·나·라, 정하지 못함 나(2-1)·라(2-2) · B — 다, 리서치 못 함), 2-1 긍정 1·부정 3, 2-2 리스크 3·기회 1. */
function richResult(extra: Json = {}): Json {
  const raw = fakeResult(extra, [
    topic('가상토픽 A', [
      subtopic('서브 가', {
        impact: done([
          impactRow(
            '가 영향 긍정',
            '긍정',
            ctx(
              [item('규 하나', 'https://e.test/r1')],
              [item('컨 하나', 'javascript:alert(1)')],
            ),
          ),
          impactRow('가 영향 부정', '부정'),
        ]),
        financial: done([
          financialRow(
            '가 재무',
            '리스크',
            '리스크-평판',
            ctx([item('규 하나 재', ' https://e.test/r1 ')], []),
          ),
        ]),
        pathway: done([
          pathwayRow(
            '가 경로 리스크',
            '리스크',
            '리스크-평판',
            ctx([item('규 요약')], []),
          ),
          pathwayRow('가 경로 기회', '기회', null),
        ]),
      }),
      subtopic('서브 나', { impact: failed() }),
      subtopic('서브 라', { financial: failed(), pathway: notRun() }),
    ]),
    topic('가상토픽 B', [subtopic('서브 다')]),
  ]);
  (raw.part1 as { topics: Json[] }).topics = [
    part1Topic('가상토픽 A'),
    part1Topic('가상토픽 B', 'failed', 'not_run'),
  ];
  return raw;
}

function setup(result: Json = richResult(), run: Partial<FakeRun> = {}) {
  const server = fakeMaterialityServer({
    runs: [doneRun(7, { result, ...run })],
  });
  const store = serverStoreOf(server, { pollMs: 5 });
  const props = { onBack: vi.fn(), onRerun: vi.fn(), onNotDone: vi.fn() };
  render(<ResultScreen store={store} runId="7" {...props} />);
  return { server, ...props };
}
const ready = () =>
  screen.findByText(IR_TEXT.titleOf(FAKE_COMPANY), undefined, WAIT);
const body = () => document.body.textContent ?? '';
const rows = (kind: string) =>
  [...document.querySelectorAll(`tr[data-row="${kind}"]`)] as HTMLElement[];
const tab = (name: string) =>
  fireEvent.mouseDown(screen.getByRole('tab', { name }));
/** 고르기 칸(키트 dropdown-menu)을 열고 값 하나를 고른다. */
function choose(name: string, option: string) {
  fireEvent.keyDown(screen.getByRole('button', { name }), { key: 'Enter' });
  fireEvent.click(screen.getByRole('menuitemradio', { name: option }));
}

describe('IR-04 결과', () => {
  it('머리: 기업명·완료·메타(끝·토픽·서브토픽·기간 「오늘까지」→ 시작한 날·비금융 — 「1회차」 0) · 카드 다섯', async () => {
    setup();
    await ready();
    expect(screen.getByTestId('meta').textContent).toBe(
      words.meta(
        '2026-10-19 14:39',
        '2',
        '4',
        words.period('2025-01-01', '2026-10-19'),
        IR_TEXT.sector.non_financial,
      ),
    );
    expect(body()).not.toContain('1회차');
    expect(screen.getByTestId('stat-topics').textContent).toBe('2개');
    expect(screen.getByTestId('stat-regulation').textContent).toBe('1건');
    expect(screen.getByTestId('stat-controversy').textContent).toBe('1건');
    expect(screen.getByTestId('stat-impact').textContent).toBe('4개');
    expect(screen.getByTestId('stat-pathway').textContent).toBe('4개');
    expect(body()).toContain(words.cards.subtopics(4));
    expect(body()).toContain(words.cards.impactSub(1, 3));
    expect(body()).toContain(words.cards.pathwaySub(3, 1));
    expect(body()).not.toContain('지어낸');
  });

  it('정하지 못함 안내(important — 토픽 › 서브토픽 목록) · 경고 줄(서버 message 0)', async () => {
    setup(
      richResult({
        warnings: [
          warning('subtopic_autofilled', '가상토픽 A'),
          warning('subtopic_autofilled', '가상토픽 B'),
          warning('rows_dropped', '가상토픽 A'),
        ],
      }),
    );
    await ready();
    const info = screen.getByTestId('undecided');
    expect(info.textContent).toBe(
      words.undecided(
        4,
        2,
        [
          words.subtopicRef('가상토픽 A', '서브 나'),
          words.subtopicRef('가상토픽 A', '서브 라'),
        ].join(words.refJoiner),
      ),
    );
    expect(info.getAttribute('data-tone')).toBe('important');
    expect(
      screen.getAllByTestId('warning').map((node) => node.textContent),
    ).toEqual([
      IR_TEXT.warnings.subtopic_autofilled(2),
      IR_TEXT.warnings.other(1),
    ]);
    expect(body()).not.toContain('지어낸 서버 글');
  });

  it('기본 탭 2-1 · 줄 차례·배지 · 컨텍스트 요약 「1) 」 · 찾은 글 없이 정함 · 정하지 못함 줄은 「전체」 끝에만', async () => {
    setup();
    await ready();
    expect(
      screen
        .getByRole('tab', { name: words.tabs.impact })
        .getAttribute('aria-selected'),
    ).toBe('true');
    expect(rows('impact').map((row) => row.dataset.no)).toEqual([
      '1',
      '2',
      '3',
      '4',
    ]);
    const first = rows('impact')[0]!;
    expect(within(first).getByText('긍정')).toBeTruthy();
    expect(first.textContent).toContain('1) 규 하나 요약');
    expect(first.textContent).toContain('2) 컨 하나 요약');
    expect(rows('impact')[2]!.textContent).not.toContain(words.researchMissing);
    expect(rows('impact')[3]!.textContent).toContain(words.researchMissing);
    expect(rows('undecided').map((row) => row.textContent)).toEqual([
      `5가상토픽 A서브 나${dash}${words.undecidedCell}––`,
    ]);
    tab(words.impact.positive(1));
    expect(rows('impact')).toHaveLength(1);
    expect(rows('undecided')).toHaveLength(0);
  });

  it('토픽 고르기 · 거른 빔 → [거르기 풀기]', async () => {
    setup();
    await ready();
    choose(words.topicLabel, '가상토픽 B');
    expect(rows('impact').map((row) => row.dataset.no)).toEqual(['4']);
    tab(words.impact.positive(0));
    expect(rows('impact')).toHaveLength(0);
    expect(screen.getByTestId('filtered-empty').textContent).toContain(
      words.filteredEmpty,
    );
    fireEvent.click(screen.getByRole('button', { name: words.clearFilter }));
    expect(rows('impact')).toHaveLength(4);
    expect(rows('undecided')).toHaveLength(1);
  });

  it('2-2: pathway 줄 · 리스크 종류(접두 뗌·기회 「–」) · 줄 누르면 컨텍스트 요약 펼침 · 정하지 못함(재무 실패) 「전체」 끝', async () => {
    setup();
    await ready();
    tab(words.tabs.pathway);
    const lines = rows('pathway');
    expect(lines.map((row) => row.dataset.no)).toEqual(['1', '2', '3', '4']);
    expect(lines[0]!.textContent).toContain('평판');
    expect(lines[0]!.textContent).not.toContain('리스크-평판');
    expect(within(lines[1]!).getByText('기회')).toBeTruthy();
    expect(rows('pathway-summary')).toHaveLength(0);
    fireEvent.click(lines[0]!);
    expect(lines[0]!.getAttribute('aria-expanded')).toBe('true');
    expect(rows('pathway-summary')[0]!.textContent).toContain(
      '1) 규 요약 요약',
    );
    fireEvent.keyDown(lines[0]!, { key: 'Enter' });
    expect(rows('pathway-summary')).toHaveLength(0);
    expect(rows('undecided').map((row) => row.dataset.no)).toEqual(['5']);
    expect(rows('undecided')[0]!.textContent).toContain('서브 라');
    tab(words.pathway.risk(3));
    expect(rows('pathway')).toHaveLength(3);
    expect(rows('undecided')).toHaveLength(0);
  });

  it('1-1: [라벨] 칩(제목 = 칩 label — http 만 새 창 링크, javascript: 링크 0) · 합침 · 리서치 못 함 · 날짜·심각도 0', async () => {
    setup();
    await ready();
    tab(words.tabs.shortlist);
    const [a, b] = rows('shortlist');
    expect(a!.textContent).toContain(`1) ${words.shortlist.label.both} `);
    const links = [...document.querySelectorAll('a')];
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      'https://e.test/r1',
    ]);
    expect(links[0]!.getAttribute('target')).toBe('_blank');
    expect(links[0]!.getAttribute('rel')).toBe('noopener noreferrer');
    expect(links[0]!.getAttribute('aria-label')).toBe(
      `규 하나 · e.test · ${NEW_TAB}`,
    );
    // 머리는 칩 밖(칩 앞) — 칩 안 글은 도메인·제목·↗ 뿐
    expect(links[0]!.textContent).toBe('e.test규 하나↗');
    expect(links[0]!.parentElement!.textContent).toMatch(
      new RegExp(`^1\\) \\${words.shortlist.label.both}`),
    );
    expect(a!.textContent).toContain('컨 하나 · javascript:alert(1)');
    expect(document.querySelector('a[href^="javascript"]')).toBeNull();
    expect(b!.textContent).toContain(words.shortlist.notResearched);
    expect(body()).not.toContain('중간');
  });

  it('1-1: 컨트로버시 done·항목 0 → 그 토픽 안내', async () => {
    setup(fakeResult({}, [topic('가상토픽 A', [subtopic('서브 가')])]));
    await ready();
    tab(words.tabs.shortlist);
    expect(screen.getByTestId('no-controversy').textContent).toBe(
      words.shortlist.noControversy(['가상토픽 A']),
    );
    expect(screen.getByTestId('no-regulation').textContent).toBe(
      words.shortlist.noRegulation(['가상토픽 A']),
    );
  });

  it('part2 not_run: 카드는 토픽 수만 · 세 탭 몸 「영향 정의까지 가지 못했어요」', async () => {
    setup(fakeResult({ part2: notRun() }));
    await ready();
    expect(screen.getByTestId('stat-impact').textContent).toBe('–');
    expect(screen.getByTestId('stat-topics').textContent).toBe('2개');
    expect(screen.getByTestId('not-run').textContent).toBe(words.notRun);
  });

  it('받기(밴드 IRW16): 머리 [내려받기] 하나 → 공용 모달 줄 둘(결과 엑셀 · 리서치 엑셀, 이름·설명) · 화면 안 결과 엑셀 카드·1-1 리서치 단추 0', async () => {
    setup();
    await ready();
    const head = screen.getByTestId('downloads');
    expect(head.textContent).toBe(dl.title);
    expect(head.getAttribute('aria-haspopup')).toBe('dialog');
    expect(screen.getAllByRole('button', { name: dl.title })).toHaveLength(1);
    expect(document.querySelector('[data-card="report"]')).toBeNull();
    expect(body()).not.toContain('엑셀 내려받기');
    tab(words.tabs.shortlist);
    expect(
      within(
        document.querySelector('[data-card="shortlist"]') as HTMLElement,
      ).queryAllByRole('button', { name: /엑셀/ }),
    ).toEqual([]);
    expect(screen.queryByTestId('download-dialog')).toBeNull();
    fireEvent.click(head);
    const dialog = screen.getByTestId('download-dialog');
    expect(within(dialog).getByRole('heading').textContent).toBe(dl.title);
    const lines = [...dialog.querySelectorAll('li[data-file]')].map((li) => [
      li.getAttribute('data-file'),
      li.querySelectorAll('p')[0]!.textContent,
      li.querySelectorAll('p')[1]!.textContent,
    ]);
    expect(lines).toEqual([
      [
        'report',
        '결과 엑셀',
        '고친 값이 나가요 · 시트 4개(1-1 · 2-1 · 2-2 · RAW_JSON)',
      ],
      ['research', '리서치 엑셀', 'AI 가 찾은 원본 그대로예요 · 시트 2개'],
    ]);
    expect(dialog.querySelector('[aria-disabled]')).toBeNull();
    fireEvent.click(within(dialog).getByRole('button', { name: dl.close }));
    expect(screen.queryByTestId('download-dialog')).toBeNull();
  });

  it('받기: 결과 엑셀 줄 → GET /materiality/runs/{id}/report · 리서치 줄 → websearch 파일 · 실패면 그 줄 아래 공용 실패 글', async () => {
    const { server } = setup();
    await ready();
    fireEvent.click(screen.getByTestId('downloads'));
    await act(async () => {
      fireEvent.click(screen.getByTestId('download-dialog-file-report'));
    });
    await vi.waitFor(() => expect(saved).toEqual([REPORT]), WAIT);
    expect(server.count('GET /materiality/runs/7/report')).toBe(1);
    expect(server.count(`GET /runs/7/files/${REPORT}`)).toBe(0);
    await act(async () => {
      fireEvent.click(screen.getByTestId('download-dialog-file-research'));
    });
    await vi.waitFor(() => expect(saved).toEqual([REPORT, WEBSEARCH]), WAIT);
    expect(server.count(`GET /runs/7/files/${WEBSEARCH}`)).toBe(1);
    expect(server.count('GET /materiality/runs/7/report')).toBe(1);
    server.override['GET /materiality/runs/7/report'] = () =>
      refusal(500, 'INTERNAL');
    await act(async () => {
      fireEvent.click(screen.getByTestId('download-dialog-file-report'));
    });
    await vi.waitFor(
      () =>
        expect(
          screen.getByTestId('download-dialog-problem-report').textContent,
        ).toBe(common.downloadFailed),
      WAIT,
    );
    server.override[`GET /runs/7/files/${WEBSEARCH}`] = () =>
      refusal(500, 'INTERNAL');
    await act(async () => {
      fireEvent.click(screen.getByTestId('download-dialog-file-research'));
    });
    await vi.waitFor(
      () =>
        expect(
          screen.getByTestId('download-dialog-problem-research').textContent,
        ).toBe(common.downloadFailed),
      WAIT,
    );
  });

  it('받기: 파일이 없으면 줄을 숨기지 않고 꺼진 줄 + (?) 까닭(리서치 없음 · 결과 없음 · 둘 다 없어도 단추·모달) · 누름은 받지 않음', async () => {
    const offOf = () =>
      [
        ...screen
          .getByTestId('download-dialog')
          .querySelectorAll('li[data-file]'),
      ].map((li) => [
        li.getAttribute('data-file'),
        li.querySelector('[aria-disabled="true"]') !== null,
        li
          .querySelector<HTMLElement>('[data-testid^="download-dialog-help-"]')
          ?.getAttribute('aria-label') ?? null,
      ]);
    const { server } = setup(richResult(), { files: [REPORT] });
    await ready();
    fireEvent.click(screen.getByTestId('downloads'));
    expect(offOf()).toEqual([
      ['report', false, null],
      [
        'research',
        true,
        `${dl.fileMissingLabel}: 이 실행에는 리서치 엑셀이 없어요`,
      ],
    ]);
    await act(async () => {
      fireEvent.click(screen.getByTestId('download-dialog-file-research'));
    });
    expect(saved).toEqual([]);
    expect(server.count(`GET /runs/7/files/${WEBSEARCH}`)).toBe(0);
    cleanup();
    setup(richResult(), { files: [WEBSEARCH] });
    await ready();
    fireEvent.click(screen.getByTestId('downloads'));
    expect(offOf()).toEqual([
      [
        'report',
        true,
        `${dl.fileMissingLabel}: 이 실행에는 결과 엑셀이 없어요`,
      ],
      ['research', false, null],
    ]);
    cleanup();
    setup(richResult(), { files: [] });
    await ready();
    fireEvent.click(screen.getByTestId('downloads'));
    expect(offOf().map(([key, off]) => [key, off])).toEqual([
      ['report', true],
      ['research', true],
    ]);
  });

  it('거르기 없이 빈 2-1·2-2 → 「찾은 영향이 없어요」(단추 0 — 6c 덧붙임 B3) · 거르면 「조건에 맞는 영향이 없어요」', async () => {
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가', { impact: done([]), pathway: done([]) }),
        ]),
      ]),
    );
    await ready();
    const empty = screen.getByTestId('filtered-empty');
    expect(empty.textContent).toBe(words.noImpacts);
    expect(within(empty).queryAllByRole('button')).toEqual([]);
    tab(words.impact.positive(0));
    expect(screen.getByTestId('filtered-empty').textContent).toContain(
      words.filteredEmpty,
    );
    expect(
      screen.getByRole('button', { name: words.clearFilter }),
    ).toBeTruthy();
  });

  it('정하지 못함 줄의 No 는 토픽으로 걸러도 거르기 전 번호', async () => {
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가'),
          subtopic('서브 나', { impact: failed() }),
        ]),
        topic('가상토픽 B', [subtopic('서브 다', { impact: failed() })]),
      ]),
    );
    await ready();
    expect(rows('undecided').map((row) => row.dataset.no)).toEqual(['2', '3']);
    choose(words.topicLabel, '가상토픽 B');
    expect(rows('undecided').map((row) => row.dataset.no)).toEqual(['3']);
  });

  it('2-2 도 정하지 못함 줄의 No 는 토픽으로 걸러도 거르기 전 번호(검증 N9)', async () => {
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가'),
          subtopic('서브 나', { financial: failed(), pathway: notRun() }),
        ]),
        topic('가상토픽 B', [subtopic('서브 다', { pathway: failed() })]),
      ]),
    );
    await ready();
    tab(words.tabs.pathway);
    expect(rows('undecided').map((row) => row.dataset.no)).toEqual(['2', '3']);
    choose(words.topicLabel, '가상토픽 B');
    expect(rows('undecided').map((row) => row.dataset.no)).toEqual(['3']);
  });

  it('[다시 실행]: 받은 options 그대로 새 POST → onRerun · 거절이면 다시 실행 실패 글', async () => {
    const { server, onRerun } = setup();
    await ready();
    fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    await vi.waitFor(() => expect(onRerun).toHaveBeenCalledWith('30'), WAIT);
    expect(server.runs.get(30)!.options).toEqual(server.runs.get(7)!.options);
    server.override['POST /runs'] = () => refusal(500, 'INTERNAL');
    fireEvent.click(screen.getByRole('button', { name: common.rerun }));
    expect(
      (await screen.findByTestId('rerun-error', undefined, WAIT)).textContent,
    ).toBe(common.rerunFailed);
  });

  it('아직 끝나지 않음(409) → onNotDone · 없음(404) → 찾을 수 없음 · 그 밖 → 불러오지 못함', async () => {
    const server = fakeMaterialityServer({
      runs: [fakeRun(7, { status: 'processing' })],
    });
    const props = { onBack: vi.fn(), onRerun: vi.fn(), onNotDone: vi.fn() };
    render(
      <ResultScreen
        store={serverStoreOf(server, { pollMs: 5 })}
        runId="7"
        {...props}
      />,
    );
    await vi.waitFor(
      () => expect(props.onNotDone).toHaveBeenCalledTimes(1),
      WAIT,
    );
    cleanup();
    render(
      <ResultScreen
        store={serverStoreOf(fakeMaterialityServer())}
        runId="9"
        onBack={vi.fn()}
        onRerun={vi.fn()}
        onNotDone={vi.fn()}
      />,
    );
    await screen.findByText(common.notFound, undefined, WAIT);
    cleanup();
    const broken = fakeMaterialityServer({ runs: [doneRun(7)] });
    broken.override['GET /materiality/runs/7/result'] = () =>
      refusal(500, 'INTERNAL');
    render(
      <ResultScreen
        store={serverStoreOf(broken)}
        runId="7"
        onBack={vi.fn()}
        onRerun={vi.fn()}
        onNotDone={vi.fn()}
      />,
    );
    await screen.findByText(words.loadFailed, undefined, WAIT);
  });
});

describe('IR-04 시안 대조 손질(밴드 IRW1b)', () => {
  it('J2 빈 토픽 안내는 묶어 하나 — 빈 토픽 0·1·여럿 → 상자 0·1·1', async () => {
    // 0: richResult 의 A 는 두 쪽 다 글이 있고 B 는 리서치 못 함 → 안내 0 (1 은 위 「컨트로버시 done·항목 0」 시험)
    setup();
    await ready();
    tab(words.tabs.shortlist);
    expect(screen.queryAllByTestId('no-controversy')).toHaveLength(0);
    expect(screen.queryAllByTestId('no-regulation')).toHaveLength(0);
    cleanup();
    // 여럿: 토픽 셋이 다 비면 상자 하나에 이름 셋
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [subtopic('서브 가')]),
        topic('가상토픽 B', [subtopic('서브 나')]),
        topic('가상토픽 C', [subtopic('서브 다')]),
      ]),
    );
    await ready();
    tab(words.tabs.shortlist);
    const names = ['가상토픽 A', '가상토픽 B', '가상토픽 C'];
    expect(
      screen.getAllByTestId('no-controversy').map((node) => node.textContent),
    ).toEqual([words.shortlist.noControversy(names)]);
    expect(
      screen.getAllByTestId('no-regulation').map((node) => node.textContent),
    ).toEqual([words.shortlist.noRegulation(names)]);
    expect(screen.getByTestId('no-controversy').textContent).toContain(
      '「가상토픽 A」·「가상토픽 B」·「가상토픽 C」 토픽은',
    );
  });

  it('J1 주소: 보이는 글은 퍼센트 인코딩을 풀고 href 는 원래 값 · 잘못된 % 는 원문', async () => {
    const encoded = `https://e.test/${encodeURIComponent('가상 규제')}?q=${encodeURIComponent('탄소')}`;
    const broken = 'https://e.test/%E0%A4%A';
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가', {
            impact: done([
              impactRow(
                '가 영향',
                '부정',
                ctx([item('규 풀림', encoded)], [item('컨 깨짐', broken)]),
              ),
            ]),
          }),
        ]),
      ]),
    );
    await ready();
    tab(words.tabs.shortlist);
    const links = [...document.querySelectorAll('a')];
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      encoded,
      broken,
    ]);
    // 주소는 툴팁에만(칩이 풀어 보인다) — 보이는 글에는 주소 0
    expect(links.map((link) => link.getAttribute('title'))).toEqual([
      'https://e.test/가상 규제?q=탄소',
      broken,
    ]);
    expect(rows('shortlist')[0]!.textContent).not.toContain('https://');
  });

  it('W1 표 꼴(공용 DataTable — 머리 500 14 바탕 · 몸 400 14 · 칸 16) · W3 1-1 규제·컨트로버시 반반 · W4 완료 배지 sm', async () => {
    setup();
    await ready();
    const th = document.querySelector('[data-card="impact"] thead th')!;
    expect(th.className).toContain('text-style-pre-body-05');
    expect(th.className).toContain('bg-support-grey-subtle');
    expect(th.className).toContain('px-4');
    expect(th.closest('table')!.parentElement!.className).toContain(
      '[&_th]:whitespace-nowrap',
    );
    const td = rows('impact')[0]!.querySelector('td')!;
    expect(td.className).toContain('text-style-pre-body-06');
    expect(td.className).toContain('px-4');
    expect(td.className).not.toContain('text-style-pre-body-04');
    tab(words.tabs.shortlist);
    expect(
      document.querySelector('[data-card="shortlist"] table')!.className,
    ).toContain('table-fixed');
    expect(
      [
        ...document.querySelectorAll<HTMLElement>(
          '[data-card="shortlist"] col',
        ),
      ].map((col) => col.style.width),
    ).toEqual(['50px', '108px', '', '', '112px']);
    const badge = screen.getByText(IR_TEXT.badge.done);
    expect(badge.className).toContain('h-5');
  });

  it('IRW4 N1 2-1·1-1 공용 DataTable: table-fixed · col 폭(짧은 칸 meta.width, 긴 칸 남은 폭) · 정렬 0 · 표 이름 = 카드 제목', async () => {
    setup();
    await ready();
    const check = (card: string, widths: string[], title: string) => {
      const table = document.querySelector<HTMLTableElement>(
        `[data-card="${card}"] table`,
      )!;
      expect(table.className).toContain('table-fixed');
      expect(
        [...table.querySelectorAll<HTMLElement>('colgroup > col')].map(
          (col) => col.style.width,
        ),
      ).toEqual(widths);
      expect(table.querySelectorAll('thead th button')).toHaveLength(0);
      expect(table.getAttribute('aria-label')).toBe(title);
    };
    check(
      'impact',
      ['56px', '120px', '176px', '240px', '', '72px', '', '112px'],
      words.impact.title,
    );
    tab(words.tabs.shortlist);
    check(
      'shortlist',
      ['50px', '108px', '', '', '112px'],
      words.shortlist.title,
    );
  });

  it('IRW4 N2 2-1 정하지 못함 줄: 칸마다 흐린 span(공용 td 는 글 색을 직접 가져 tr 색이 안 내려옴) · 영향 줄 칸에는 0', async () => {
    setup();
    await ready();
    const [undecided] = rows('undecided');
    const tds = [...undecided!.querySelectorAll('td')];
    expect(tds).toHaveLength(8);
    for (const td of tds.slice(0, 7)) {
      expect(td.firstElementChild?.tagName).toBe('SPAN');
      expect(td.firstElementChild!.classList).toContain('text-text-quaternary');
    }
    for (const td of rows('impact')[0]!.querySelectorAll('td'))
      expect(
        td.firstElementChild?.classList.contains('text-text-quaternary') ??
          false,
      ).toBe(false);
  });

  it('IRW4 N3 2-1 감싸개: 데이터 줄 칸만 위아래 12·위 붙임 · 빈 몸은 div[data-testid=filtered-empty](tr[data-row] 밖)', async () => {
    setup();
    await ready();
    const wrap = document.querySelector(
      '[data-card="impact"] table',
    )!.parentElement!;
    expect(wrap.className).toContain('[&_tr[data-row]>td]:py-3');
    expect(wrap.className).toContain('[&_tr[data-row]>td]:align-top');
    choose(words.topicLabel, '가상토픽 B');
    tab(words.impact.positive(0));
    const empty = screen.getByTestId('filtered-empty');
    expect(empty.tagName).toBe('DIV');
    expect(empty.closest('tr[data-row]')).toBeNull();
    expect(empty.closest('[data-card="impact"] tbody')).not.toBeNull();
  });

  it('W5 숫자 카드 라벨 500 14 · 수 700 32 · 단위 500 14 · J3 떠오름 시차·CountUp(jsdom 은 끝 값) · W6 작은 글 400 12', async () => {
    setup();
    await ready();
    const cards = [
      ...document.querySelectorAll('[data-stat]'),
    ] as HTMLElement[];
    expect(
      cards.map((card) => card.style.getPropertyValue('--gw-m-delay')),
    ).toEqual(['0ms', '70ms', '140ms', '210ms', '280ms']);
    expect(cards.every((card) => card.className.includes('gw-m-rise'))).toBe(
      true,
    );
    const value = screen.getByTestId('stat-impact');
    expect(value.className).toContain('text-style-pre-display-03');
    expect(value.querySelector('small')!.className).toContain(
      'text-style-pre-body-05',
    );
    expect(cards[0]!.firstElementChild!.className).toContain(
      'text-style-pre-body-05',
    );
    expect(value.textContent).toBe('4개');
    expect(screen.getByText(words.impact.sub).className).toContain(
      'text-style-pre-caption-03',
    );
    expect(screen.getByText(words.impact.foot).className).toContain(
      'text-style-pre-caption-03',
    );
  });

  it('J3 탭 몸은 바꿀 때마다 비친다(gw-m-fade)', async () => {
    setup();
    await ready();
    expect(
      document.querySelector('[data-card="impact"]')!.parentElement!.className,
    ).toContain('gw-m-fade');
    tab(words.tabs.pathway);
    expect(
      document.querySelector('[data-card="pathway"]')!.parentElement!.className,
    ).toContain('gw-m-fade');
  });
});

describe('IR-04 손질(밴드 IRW2 ③ — 381 m3·J1 · N1)', () => {
  it.each([
    ['불러오지 못함(500)', () => refusal(500, 'INTERNAL')],
    ['없음(404)', () => refusal(404, 'NOT_FOUND')],
  ])(
    'm3 실행이 %s → 머리 [내려받기] 자리에 회색 한 줄(A6-⑫ — 밴드 IRW16) · 단추·모달 0 · 「오늘까지」 원문',
    async (_, answer) => {
      const server = fakeMaterialityServer({ runs: [doneRun(7)] });
      server.override['GET /runs/7'] = answer;
      render(
        <ResultScreen
          store={serverStoreOf(server, { pollMs: 5 })}
          runId="7"
          onBack={vi.fn()}
          onRerun={vi.fn()}
          onNotDone={vi.fn()}
        />,
      );
      await ready();
      const line = screen.getByTestId('downloads-run-failed');
      expect(line.textContent).toBe(
        '실행 정보를 불러오지 못해 내려받기를 열 수 없어요. 새로 고침해 주세요.',
      );
      expect(line.textContent).toBe(dl.runFailed);
      expect(line.className).toContain('text-text-tertiary');
      // 머리 actions 자리([다시 실행] 바로 뒤)
      expect(line.previousElementSibling!.textContent).toBe(common.rerun);
      expect(document.querySelector('[data-card="report"]')).toBeNull();
      expect(screen.queryByTestId('downloads')).toBeNull();
      expect(screen.queryAllByRole('button', { name: dl.title })).toEqual([]);
      expect(screen.queryByTestId('download-dialog')).toBeNull();
      expect(screen.getByTestId('meta').textContent).toContain('오늘까지');
    },
  );

  it('m3 실행을 읽으면 회색 줄 0', async () => {
    setup();
    await ready();
    expect(screen.getByTestId('downloads')).not.toBeNull();
    expect(screen.queryByTestId('downloads-run-failed')).toBeNull();
  });

  it('J1 보이는 주소에서 방향 제어 문자를 걷는다(풀린 것·원래 든 것) · href 는 그대로', async () => {
    const encoded = 'https://e.test/a%E2%80%AEb%E2%81%A6c%E2%80%8Fd%D8%9Ce';
    const literal = 'https://e.test/x\u202Ay\u2069z\u200E';
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가', {
            impact: done([
              impactRow(
                '가 영향',
                '부정',
                ctx([item('규 제어', encoded)], [item('컨 제어', literal)]),
              ),
            ]),
          }),
        ]),
      ]),
    );
    await ready();
    tab(words.tabs.shortlist);
    const links = [...document.querySelectorAll('a')];
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      encoded,
      literal,
    ]);
    expect(links.map((link) => link.getAttribute('title'))).toEqual([
      'https://e.test/abcde',
      'https://e.test/xyz',
    ]);
  });

  it('IRW12 1-1 칩 경계: 대문자 스킴은 링크 · 제목 빈 줄은 경로 · http(s) 아님은 제목 글 + 주소 회색 · 스킴만 주소는 제목만(제목 빈 줄은 회색 주소 — 개정 2) · 제목 없는 비링크는 회색 값만(IRW12b m2) · 주소 없음은 제목만 · 줄 사이 6(m1)', async () => {
    const raw = (title: string | null, url: string | null) => ({
      title,
      summary: '요약',
      url,
    });
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가', {
            impact: done([
              impactRow(
                '가 영향',
                '부정',
                ctx(
                  [
                    item('규 대문자', 'HTTPS://E.test/up'),
                    raw(null, 'https://e.test/reports/2024-a'),
                    raw('   ', 'https://e.test/blank'),
                    item('규 빈호스트', 'https://'),
                    item('규 대문자 스킴만', ' HTTP:// '),
                    raw(null, 'Http://'),
                    raw('  ', 'HTTPS://'),
                  ],
                  [
                    item('컨 메일', 'mailto:a@e.test'),
                    item('컨 주소없음', null),
                    item('컨 주소공백', '  '),
                    raw(null, 'mailto:b@e.test'),
                    raw(null, null),
                  ],
                ),
              ),
            ]),
          }),
        ]),
      ]),
    );
    await ready();
    tab(words.tabs.shortlist);
    const lines = [
      ...rows('shortlist')[0]!.querySelectorAll<HTMLElement>(
        '[data-item-label]',
      ),
    ];
    const link = (line: HTMLElement) => line.querySelector('a');
    const grey = (line: HTMLElement) =>
      line.querySelector<HTMLElement>('span.text-text-tertiary');
    expect(lines).toHaveLength(12);
    const [
      upper,
      untitled,
      blank,
      noHost,
      upperSchemeOnly,
      untitledScheme,
      blankScheme,
      mail,
      none,
      spaces,
      untitledMail,
      bare,
    ] = lines;
    // m1(IRW12b): 읽기 칸의 줄들은 세로 flex·사이 6(gap-1.5) — 고침 표시 없는 칸
    for (const line of lines)
      expect(line.parentElement!.className.split(' ')).toEqual(
        expect.arrayContaining(['flex', 'flex-col', 'gap-1.5']),
      );
    expect(link(upper!)!.getAttribute('href')).toBe('HTTPS://E.test/up');
    expect(link(upper!)!.getAttribute('aria-label')).toBe(
      `규 대문자 · e.test · ${NEW_TAB}`,
    );
    expect(link(untitled!)!.getAttribute('aria-label')).toBe(
      `reports/2024-a · e.test · ${NEW_TAB}`,
    );
    expect(link(blank!)!.getAttribute('aria-label')).toBe(
      `blank · e.test · ${NEW_TAB}`,
    );
    {
      const [line, title, url] = [mail!, '컨 메일', 'mailto:a@e.test'];
      expect(link(line)).toBeNull();
      expect(line.textContent).toContain(`${title} · ${url}`);
      expect(grey(line)!.textContent).toBe(url);
      expect(grey(line)!.textContent).not.toContain(title);
    }
    // 제목 없는 비링크 줄(스킴만·mailto): 머리 뒤 회색 값만 — 「–」·「 · 」 0(빈 줄 방지는 그대로 — 개정 2 · IRW12b m2)
    for (const [line, url] of [
      [untitledScheme!, 'Http://'],
      [blankScheme!, 'HTTPS://'],
      [untitledMail!, 'mailto:b@e.test'],
    ] as const) {
      expect(link(line)).toBeNull();
      expect(grey(line)!.textContent).toBe(url);
      expect(line.textContent).toMatch(
        new RegExp(`^\\d+\\) \\[[^\\]]+\\] ${url.replace(/[.]/g, '\\.')}$`),
      );
      expect(line.textContent).not.toContain(' · ');
      expect(line.textContent).not.toContain(dash);
    }
    // 제목도 주소도 없는 줄은 「–」 그대로
    expect(link(bare!)).toBeNull();
    expect(grey(bare!)).toBeNull();
    expect(bare!.textContent).toMatch(new RegExp(`\\] ${dash}$`));
    // 스킴만 주소 + 제목: 「· 주소」 없이 제목만(주소 없음 줄과 같은 꼴 — 개정 2)
    for (const [line, title] of [
      [noHost!, '규 빈호스트'],
      [upperSchemeOnly!, '규 대문자 스킴만'],
      [none!, '컨 주소없음'],
      [spaces!, '컨 주소공백'],
    ] as const) {
      expect(link(line)).toBeNull();
      expect(grey(line)).toBeNull();
      expect(line.textContent).toMatch(new RegExp(`${title}$`));
      expect(line.textContent).not.toContain(' · ');
    }
  });

  it('N1 숫자 카드 sub 는 400 12(pre-caption-03) · 표 머리 정의 덧말은 없다(판 r3 — 밴드 IRW11 B1)', async () => {
    setup();
    await ready();
    const sub =
      screen.getByTestId('stat-topics').parentElement!.lastElementChild!;
    expect(sub.className).toContain('text-style-pre-caption-03');
    expect(sub.className).not.toContain('text-style-pre-caption-02');
    expect(
      screen.queryByText('AI 가 쓴 글 그대로', { exact: false }),
    ).toBeNull();
    tab(words.tabs.pathway);
    expect(
      screen.queryByText('AI 가 쓴 글 그대로', { exact: false }),
    ).toBeNull();
  });
});

describe('IR-04 2-2 공용 DataTable · 한국어 칸 keep-all · 경고 줄 묶음(밴드 IRW5 — sid:MARC-ISSUE-402·433)', () => {
  const pathwayTable = () =>
    document.querySelector<HTMLTableElement>('[data-card="pathway"] table')!;

  it('N1 2-2 공용 표: 이름·정렬 0·colgroup 0(auto) · 누름 줄 tabindex·aria-expanded·hover 바탕(IRW13 규칙 2) · 정하지 못함 줄은 누름 0·흐린 span · 펼침 줄 data-expanded-row·colSpan 12(IRW10 가치사슬 활동 열 +1 · IRW13 꺾쇠 열 +1) · 감싸개', async () => {
    setup();
    await ready();
    tab(words.tabs.pathway);
    const table = pathwayTable();
    expect(table.getAttribute('aria-label')).toBe(words.pathway.title);
    expect(table.querySelectorAll('thead th')).toHaveLength(12);
    expect(table.querySelectorAll('thead th button')).toHaveLength(0);
    expect(table.querySelectorAll('colgroup')).toHaveLength(0);
    for (const line of rows('pathway')) {
      expect(line.getAttribute('tabindex')).toBe('0');
      expect(line.getAttribute('aria-expanded')).toBe('false');
      expect(line.className).toContain('cursor-pointer');
      expect(line.className).toContain('hover:bg-background-secondary');
    }
    const [undecided] = rows('undecided');
    expect(undecided!.hasAttribute('tabindex')).toBe(false);
    expect(undecided!.hasAttribute('aria-expanded')).toBe(false);
    expect(undecided!.className).not.toContain('cursor-pointer');
    expect(undecided!.className).not.toContain('hover:bg-background-secondary');
    const tds = [...undecided!.querySelectorAll('td')];
    expect(tds).toHaveLength(12);
    // 첫 칸은 꺾쇠 열(IRW13 개정 2 — 정하지 못함 줄은 빈 칸), 데이터 칸 10 은 그 뒤
    expect(tds[0]!.textContent).toBe('');
    for (const td of tds.slice(1, 11)) {
      expect(td.firstElementChild?.tagName).toBe('SPAN');
      expect(td.firstElementChild!.classList).toContain('text-text-quaternary');
    }
    fireEvent.click(undecided!);
    expect(rows('pathway-summary')).toHaveLength(0);
    fireEvent.click(rows('pathway')[1]!);
    const [summary] = rows('pathway-summary');
    expect(summary!.dataset.no).toBe('2');
    expect(summary!.hasAttribute('data-expanded-row')).toBe(true);
    expect(summary!.querySelector('td')!.colSpan).toBe(12);
    expect(rows('pathway')[1]!.getAttribute('aria-expanded')).toBe('true');
    const wrap = table.parentElement!.className;
    expect(wrap).toContain('[&_tr[aria-expanded=true]>td]:border-b-0');
    expect(wrap).toContain('[&_tr[data-expanded-row][data-row]>td]:pt-0');
    expect(wrap).toContain('[&_tr[data-row]>td]:py-3');
    expect(wrap).toContain('[&_tr[data-row]>td]:align-top');
  });

  it('IRW13 2-2 줄 누름 규칙(sid:MARC-ENT-599 규칙 4·5, 개정 2): 누름 줄 이름 「n번 서브토픽 컨텍스트 요약」(펼치기·접기 0 — 상태는 aria-expanded) · 꺾쇠 첫 열(No 앞)·aria-hidden·tertiary 16·열림 180° · 정하지 못함 줄 이름·꺾쇠 0 · Enter 로 열고 닫음', async () => {
    // 이름 두 꼴(서브토픽이 비면 번호만 — null·공백)
    expect(words.pathway.rowLabel(3, '가상 서브 가')).toBe(
      '3번 가상 서브 가 컨텍스트 요약',
    );
    expect(words.pathway.rowLabel(4, '  ')).toBe('4번 컨텍스트 요약');
    expect(words.pathway.rowLabel(5, null)).toBe('5번 컨텍스트 요약');
    setup();
    await ready();
    tab(words.tabs.pathway);
    const lines = rows('pathway');
    expect(lines.length).toBeGreaterThan(1);
    const first = lines[0]!;
    const cellsOf = (tr: HTMLElement) => [...tr.querySelectorAll('td')];
    // 꺾쇠: 첫 칸 · No 는 둘째 · 끝 칸은 고치기(열 차례)
    const tds = cellsOf(first);
    expect(tds).toHaveLength(12);
    const mark = tds[0]!.querySelector<HTMLElement>('[data-expand-mark]')!;
    expect(mark).not.toBeNull();
    expect(tds[1]!.textContent).toBe('1');
    expect(tds[11]!.querySelector('[data-edit-button]')).not.toBeNull();
    expect(
      tds.slice(1).some((td) => td.querySelector('[data-expand-mark]')),
    ).toBe(false);
    const ths = [
      ...document.querySelectorAll('[data-card="pathway"] thead th'),
    ];
    expect(ths[0]!.querySelector('[data-col=expand]')).not.toBeNull();
    expect(ths[0]!.textContent).toBe('');
    expect(ths[1]!.textContent).toBe(words.pathway.head.no);
    const subtopic = tds[3]!.textContent!;
    const name = `1번 ${subtopic} 컨텍스트 요약`;
    expect(first.getAttribute('aria-label')).toBe(name);
    expect(first.getAttribute('aria-label')).not.toMatch(/펼치기|접기/);
    const icon = mark.querySelector('svg')!;
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(icon.getAttribute('class')).toContain('size-4');
    expect(icon.getAttribute('class')).toContain('text-text-tertiary');
    expect(icon.getAttribute('class')).not.toContain('rotate-180');
    expect(mark.dataset.expandMark).toBe('closed');
    expect(mark.hasAttribute('data-dim')).toBe(false);
    // 정하지 못함 줄: 이름 0 · 꺾쇠 0(첫 칸 비움)
    const [undecided] = rows('undecided');
    expect(undecided!.hasAttribute('aria-label')).toBe(false);
    expect(undecided!.querySelector('[data-expand-mark]')).toBeNull();
    expect(cellsOf(undecided!)[0]!.textContent).toBe('');
    // Enter 로 열림 → 이름 그대로 · 꺾쇠 180° · 다른 줄은 그대로
    fireEvent.keyDown(first, { key: 'Enter' });
    expect(first.getAttribute('aria-expanded')).toBe('true');
    expect(first.getAttribute('aria-label')).toBe(name);
    const opened = first.querySelector<HTMLElement>('[data-expand-mark]')!;
    expect(opened.dataset.expandMark).toBe('open');
    expect(opened.querySelector('svg')!.getAttribute('class')).toContain(
      'rotate-180',
    );
    expect(
      rows('pathway')[1]!.querySelector<HTMLElement>('[data-expand-mark]')!
        .dataset.expandMark,
    ).toBe('closed');
    fireEvent.keyDown(first, { key: 'Enter' });
    expect(first.getAttribute('aria-expanded')).toBe('false');
    expect(first.getAttribute('aria-label')).toBe(name);
    // 꺾쇠 누름 = 줄 누름 한 번(장식 — 두 번 토글 0)
    fireEvent.click(first.querySelector('[data-expand-mark] svg')!);
    expect(first.getAttribute('aria-expanded')).toBe('true');
    expect(rows('pathway-summary')).toHaveLength(1);
  });

  it('N1 2-2 Space 로도 열고 닫음 · 빈 몸은 div[data-testid=filtered-empty](tr[data-row] 밖)', async () => {
    setup();
    await ready();
    tab(words.tabs.pathway);
    fireEvent.keyDown(rows('pathway')[2]!, { key: ' ' });
    expect(rows('pathway-summary').map((row) => row.dataset.no)).toEqual(['3']);
    fireEvent.keyDown(rows('pathway')[2]!, { key: ' ' });
    expect(rows('pathway-summary')).toHaveLength(0);
    cleanup();
    setup(
      fakeResult({}, [
        topic('가상토픽 A', [
          subtopic('서브 가', { impact: done([]), pathway: done([]) }),
        ]),
      ]),
    );
    await ready();
    tab(words.tabs.pathway);
    const empty = screen.getByTestId('filtered-empty');
    expect(empty.tagName).toBe('DIV');
    expect(empty.textContent).toBe(words.noImpacts);
    expect(empty.closest('tr[data-row]')).toBeNull();
    expect(empty.closest('[data-card="pathway"] tbody')).not.toBeNull();
  });

  it('N2 결과 표 셋의 감싸개 ⊃ [&_td]:break-keep(한국어 칸은 낱말 사이에서만 꺾임 — 433 ①)', async () => {
    setup();
    await ready();
    const wrapOf = (card: string) =>
      document.querySelector(`[data-card="${card}"] table`)!.parentElement!
        .className;
    expect(wrapOf('impact')).toContain('[&_td]:break-keep');
    tab(words.tabs.pathway);
    expect(wrapOf('pathway')).toContain('[&_td]:break-keep');
    tab(words.tabs.shortlist);
    expect(wrapOf('shortlist')).toContain('[&_td]:break-keep');
  });

  it('N3 경고 줄은 한 묶음(gap-2 — 433 ③) · 정하지 못함 안내는 묶음 밖 · 경고 0 이면 묶음 0', async () => {
    setup(
      richResult({
        warnings: [
          warning('subtopic_autofilled', '가상토픽 A'),
          warning('rows_dropped', '가상토픽 A'),
        ],
      }),
    );
    await ready();
    const group = screen.getByTestId('warnings');
    expect(group.className).toContain('gap-2');
    expect(group.className).toContain('flex-col');
    const lines = screen.getAllByTestId('warning');
    expect(lines).toHaveLength(2);
    for (const line of lines) expect(line.parentElement).toBe(group);
    expect(group.contains(screen.getByTestId('undecided'))).toBe(false);
    cleanup();
    setup();
    await ready();
    expect(screen.queryByTestId('warnings')).toBeNull();
    expect(screen.queryAllByTestId('warning')).toEqual([]);
  });

  it('N4 사본 0: 2-2 머리 칸 꼴 = 2-1 머리 칸 꼴(공용 머리 한 꼴)', async () => {
    setup();
    await ready();
    const impactTh = document.querySelector('[data-card="impact"] thead th')!;
    const impactClass = impactTh.className;
    tab(words.tabs.pathway);
    const ths = [
      ...document.querySelectorAll('[data-card="pathway"] thead th'),
    ];
    expect(ths.length).toBe(12);
    for (const th of ths) expect(th.className).toBe(impactClass);
  });
});

describe('IR-04 r2 가치사슬 활동 열(밴드 IRW10 — sid:MARC-ENT-558·sid:MARC-ISSUE-529)', () => {
  const LONG =
    '지어낸 긴 활동 · 여러 공정이 겹치는 자리의 관리와 절차 운영을 한 줄로 길게 적은 글';
  /** 토픽 하나: 서브 가(2-1 활동 둘·하나 빈 목록 · 재무 둘 · 경로 i 1·2·null·9) · 서브 나(2-1·재무 실패 → 정하지 못함). */
  function activityResult(): Json {
    const raw = fakeResult({}, [
      topic('가상토픽 A', [
        subtopic('서브 가', {
          impact: done([
            {
              ...impactRow('가 영향 하나'),
              valueChainActivities: ['활동 갑', LONG],
            },
            impactRow('가 영향 둘'),
          ]),
          financial: done([
            {
              ...financialRow('가 재무 하나'),
              valueChainActivities: ['재무 활동 을'],
            },
            {
              ...financialRow('가 재무 둘'),
              valueChainActivities: ['재무 활동 병', '재무 활동 정'],
            },
          ]),
          pathway: done([
            { ...pathwayRow('가 경로 i1'), i: 1 },
            { ...pathwayRow('가 경로 i2'), i: 2 },
            { ...pathwayRow('가 경로 null'), i: null },
            { ...pathwayRow('가 경로 범위 밖'), i: 9 },
          ]),
        }),
        subtopic('서브 나', {
          impact: failed(),
          financial: failed(),
          pathway: notRun(),
        }),
      ]),
    ]);
    (raw.part1 as { topics: Json[] }).topics = [part1Topic('가상토픽 A')];
    return raw;
  }
  const heads = (card: string) =>
    [
      ...document.querySelectorAll<HTMLElement>(
        `[data-card="${card}"] thead th`,
      ),
    ].map((th) => th.textContent);
  /** 줄의 가치사슬 활동 칸(머리 「서브토픽」 바로 뒤 = 넷째 칸, 2-2 는 첫 꺾쇠 열 뒤라 다섯째 — IRW13 개정 2). */
  const cell = (row: HTMLElement) =>
    row.querySelectorAll('td')[row.closest('[data-card="pathway"]') ? 4 : 3]!;
  const acts = (row: HTMLElement) =>
    [...cell(row).querySelectorAll('[data-activity]')].map(
      (el) => el.textContent,
    );
  const isMutedDash = (row: HTMLElement) => {
    const muted = cell(row).querySelector('.text-text-quaternary');
    return (
      cell(row).querySelectorAll('[data-activity]').length === 0 &&
      muted?.textContent === dash &&
      cell(row).textContent === dash
    );
  };

  it('2-1: 머리 「가치사슬 활동」은 서브토픽 뒤·영향 정의 앞 · 활동 둘은 덩이 둘(2줄 말줄임) · 빈 목록·정하지 못함 줄은 회색 「–」', async () => {
    setup(activityResult());
    await ready();
    const impactHeads = heads('impact');
    expect(impactHeads[2]).toBe(words.impact.head.subtopic);
    expect(impactHeads[3]).toBe('가치사슬 활동');
    expect(impactHeads[4]).toContain(words.impact.head.definition);
    const [first, second] = rows('impact');
    expect(acts(first!)).toEqual(['활동 갑', LONG]);
    for (const el of cell(first!).querySelectorAll('[data-activity]'))
      expect(el.className).toContain('line-clamp-2');
    const box = cell(first!).querySelector<HTMLElement>('[data-activities]')!;
    for (const name of [
      'min-w-[180px]',
      'max-w-[240px]',
      'gap-1',
      'whitespace-normal',
    ])
      expect(box.className).toContain(name);
    expect(isMutedDash(second!)).toBe(true);
    const [undecided] = rows('undecided');
    expect(undecided!.textContent).toContain('서브 나');
    expect(isMutedDash(undecided!)).toBe(true);
  });

  it('2-2: 머리 자리 같음 · pathway i 로 같은 서브토픽 재무 rows[i-1] 활동 · i null·범위 밖 → 회색 「–」 · 정하지 못함 줄 「–」', async () => {
    setup(activityResult());
    await ready();
    tab(words.tabs.pathway);
    const pathwayHeads = heads('pathway');
    // 첫 머리는 꺾쇠 열(글 없음 — IRW13 개정 2), 데이터 머리는 그 뒤로 한 칸씩
    expect(pathwayHeads[0]).toBe('');
    expect(pathwayHeads[3]).toBe(words.pathway.head.subtopic);
    expect(pathwayHeads[4]).toBe('가치사슬 활동');
    expect(pathwayHeads[5]).toContain(words.pathway.head.definition);
    // 토픽·서브토픽 머리 덩이 최소 68(+ 칸 16·16 = 100) — 활동 열로 넘쳐도 100 아래로 줄지 않게(감독 판단 IRW10 B).
    for (const th of [
      ...document.querySelectorAll('[data-card="pathway"] thead th'),
    ].slice(2, 4))
      expect(th.firstElementChild!.className).toContain('min-w-[68px]');
    const lines = rows('pathway');
    expect(lines).toHaveLength(4);
    expect(acts(lines[0]!)).toEqual(['재무 활동 을']);
    expect(acts(lines[1]!)).toEqual(['재무 활동 병', '재무 활동 정']);
    expect(isMutedDash(lines[2]!)).toBe(true);
    expect(isMutedDash(lines[3]!)).toBe(true);
    const [undecided] = rows('undecided');
    expect(undecided!.textContent).toContain('서브 나');
    expect(isMutedDash(undecided!)).toBe(true);
  });

  it('툴팁: 잘린 덩이(scrollHeight > clientHeight)만 전체 글 · 안 잘린 덩이는 툴팁 0', async () => {
    // 공용 툴팁(radix popper)이 재는 ResizeObserver — jsdom 에 없어 이 시험 동안만(drafting OutlineTree 시험 꼴).
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    setup(activityResult());
    await ready();
    const [short, long] = [
      ...cell(rows('impact')[0]!).querySelectorAll<HTMLElement>(
        '[data-activity]',
      ),
    ];
    const size = (el: HTMLElement, scroll: number, client: number) => {
      Object.defineProperty(el, 'scrollHeight', {
        value: scroll,
        configurable: true,
      });
      Object.defineProperty(el, 'clientHeight', {
        value: client,
        configurable: true,
      });
    };
    size(short!, 20, 20);
    size(long!, 60, 40);
    fireEvent.focus(short!);
    expect(screen.queryByRole('tooltip')).toBeNull();
    fireEvent.blur(short!);
    fireEvent.focus(long!);
    expect(
      (await screen.findByRole('tooltip', undefined, WAIT)).textContent,
    ).toBe(LONG);
    vi.unstubAllGlobals();
  });
});

describe('IR-04 r3 글 칸 고치기(밴드 IRW11 — sid:MARC-ENT-561)', () => {
  const edit = IR_TEXT.result.edit;
  const T = '/part2/topics/0/subtopics/0';
  const DEF = `${T}/impact/rows/0/impactDefinition`;
  const SUM1 = `${T}/impact/rows/0/context/regulations/0/summary`;
  const SUM2 = `${T}/impact/rows/0/context/controversies/0/summary`;
  const R1 = 'https://example.test/r1';

  /** 토픽 A 서브 가: 2-1 한 줄(규 일·규 삼·컨 일) · 재무 한 줄(규 일 재 — r1 같은 출처) · 2-2 두 줄(i 1 · i null). 토픽 B 는 기본. */
  function editResult(): Json {
    const raw = fakeResult({}, [
      topic('가상토픽 A', [
        subtopic('서브 가', {
          impact: done([
            impactRow(
              '가상 정의 글 하나',
              '부정',
              ctx(
                [
                  item('규 일', R1, '규 일 요약'),
                  item('규 삼', 'https://example.test/r3', '규 삼 요약'),
                ],
                [item('컨 일', 'https://example.test/c1', '컨 일 요약')],
              ),
            ),
          ]),
          financial: done([
            financialRow(
              '가상 재무 글',
              '리스크',
              '리스크-평판',
              ctx([item('규 일 재', R1, '규 일 재 요약')], []),
            ),
          ]),
          pathway: done([
            pathwayRow(
              '가상 경로 글',
              '리스크',
              '리스크-평판',
              ctx([item('규 일 재', R1, '규 일 재 요약')], []),
            ),
            {
              ...pathwayRow(
                '가상 경로 둘',
                '기회',
                null,
                ctx([item('규 이', 'https://example.test/r2', '규 이 요약')]),
              ),
              i: null,
            },
          ]),
        }),
      ]),
      topic('가상토픽 B', [subtopic('서브 다')]),
    ]);
    return raw;
  }

  const button = (key: string) =>
    vi.waitFor(() => {
      const found = document.querySelector<HTMLElement>(
        `[data-edit-button="${key}"]`,
      );
      expect(found).not.toBeNull();
      return found!;
    }, WAIT);
  async function open(key: string) {
    fireEvent.click(await button(key));
  }
  const box = (name: string) =>
    screen.getByRole('textbox', { name }) as HTMLTextAreaElement;
  const type = (name: string, value: string) =>
    fireEvent.change(box(name), { target: { value } });
  const saveButton = () => screen.getByRole('button', { name: edit.save });
  const posts = (server: ReturnType<typeof setup>['server']) =>
    server.calls.filter(
      (call) =>
        call.method === 'POST' &&
        call.path === '/materiality/runs/7/result/edits',
    );
  const editButtons = () =>
    document.querySelectorAll('[data-edit-button]').length;

  it('[고치기] → 그 줄만 글 상자 · 고치기 열 숨음 · 줄 아래 안내·[취소][저장] · 안 바꾸면 [저장] 꺼짐 · [취소] 닫고 그 줄 단추로', async () => {
    setup(editResult());
    await ready();
    await open('impact-1');
    const impact = document.querySelector('[data-card="impact"]')!;
    expect(
      within(impact as HTMLElement)
        .getAllByRole('textbox')
        .map((el) => el.getAttribute('aria-label')),
    ).toEqual([
      edit.definition,
      edit.summary(1),
      edit.summary(2),
      edit.summary(3),
    ]);
    expect(document.activeElement).toBe(box(edit.definition));
    expect(editButtons()).toBe(0);
    expect(
      document.querySelectorAll('[data-card="impact"] thead th'),
    ).toHaveLength(7);
    // 0b70c4d7 — 고치기 줄 안내 새 글(IRW17)
    expect(screen.getByTestId('edit-note').textContent).toBe(
      '요약을 고치면 같은 글을 근거로 쓴 다른 줄의 요약도 함께 바뀌어요 · 요약을 비우고 저장하면 그 요약은 이 줄에서 빠져요(출처는 1-1 에 남아요) · 한 번에 한 줄씩 고칠 수 있어요',
    );
    expect(document.body.textContent).not.toContain('같은 출처의 요약');
    expect(rows('edit-actions')).toHaveLength(1);
    const editing = document.querySelector('tr[data-editing]')!;
    expect(editing.getAttribute('data-no')).toBe('1');
    expect(editing.querySelector('td')!.className).toContain(
      'bg-background-secondary',
    );
    expect((saveButton() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: edit.cancel }));
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
    await vi.waitFor(
      () =>
        expect(document.activeElement).toBe(
          document.querySelector('[data-edit-button="impact-1"]'),
        ),
      WAIT,
    );
  });

  it('[저장]: 바뀐 칸만·빈 글 null·baseRevision → 연필(누가·언제)·배지 「고친 칸 n · 저장 HH:MM」 · 둘째 저장 baseRevision 1', async () => {
    const { server } = setup(editResult());
    await ready();
    await open('impact-1');
    type(edit.definition, '가상 정의 글 고침');
    type(edit.summary(3), '   ');
    fireEvent.click(saveButton());
    await vi.waitFor(
      () => expect(screen.queryAllByRole('textbox')).toHaveLength(0),
      WAIT,
    );
    expect(posts(server).map((call) => call.body)).toEqual([
      {
        baseRevision: 0,
        changes: [
          { pointer: DEF, value: '가상 정의 글 고침' },
          { pointer: SUM2, value: null },
        ],
      },
    ]);
    const row = rows('impact')[0]!;
    expect(row.textContent).toContain('가상 정의 글 고침');
    expect(row.textContent).not.toContain('컨 일 요약');
    const marks = within(row).getAllByTestId('edited-mark');
    expect(marks.map((mark) => mark.getAttribute('aria-label'))).toEqual([
      edit.editedLabel('담당자 A', '11-03 14:28'),
      edit.editedLabel('담당자 A', '11-03 14:28'),
    ]);
    expect(marks[0]!.getAttribute('role')).toBe('img');
    expect(marks[0]!.getAttribute('tabindex')).toBe('0');
    expect(screen.getByTestId('edited-badge').textContent).toBe(
      edit.badge(2, '14:28'),
    );
    server.clock.editedAt = '2026-11-03T15:02:09+09:00';
    await open('impact-1');
    type(edit.definition, '가상 정의 글 두 번째');
    fireEvent.click(saveButton());
    await vi.waitFor(() => expect(posts(server)).toHaveLength(2), WAIT);
    expect((posts(server)[1]!.body as Json).baseRevision).toBe(1);
    await vi.waitFor(
      () =>
        expect(screen.getByTestId('edited-badge').textContent).toBe(
          edit.badge(2, '15:02'),
        ),
      WAIT,
    );
  });

  it('409 → 첫 고칠 칸 아래 글 + [새로 불러오기] → 글 상자 = 새 값 · 줄 열린 채', async () => {
    const { server } = setup(editResult());
    await ready();
    await open('impact-1');
    server.editElsewhere(7, DEF, '다른 사람 정의 글');
    type(edit.definition, '내 정의 글');
    fireEvent.click(saveButton());
    const error = await screen.findByText(edit.conflict, undefined, WAIT);
    expect(box(edit.definition).closest('div')!.contains(error)).toBe(true);
    fireEvent.click(screen.getByTestId('edit-reload'));
    await vi.waitFor(
      () => expect(box(edit.definition).value).toBe('다른 사람 정의 글'),
      WAIT,
    );
    expect(screen.queryByText(edit.conflict)).toBeNull();
    type(edit.definition, '내 정의 글 다시');
    fireEvent.click(saveButton());
    await vi.waitFor(() => expect(posts(server)).toHaveLength(2), WAIT);
    expect((posts(server)[1]!.body as Json).baseRevision).toBe(1);
  });

  it('그 밖 실패(500·400·끊김) → 줄 아래 「저장하지 못했어요」 · 쓴 글 그대로 · 서버 message 0', async () => {
    const { server } = setup(editResult());
    await ready();
    await open('impact-1');
    server.override['POST /materiality/runs/7/result/edits'] = [
      () => refusal(500, 'INTERNAL'),
      () => refusal(400, 'INVALID_EDIT'),
    ];
    type(edit.definition, '가상 정의 글 고침');
    for (let n = 0; n < 2; n += 1) {
      fireEvent.click(saveButton());
      await vi.waitFor(
        () => expect(screen.getByText(edit.saveFailed)).toBeTruthy(),
        WAIT,
      );
    }
    expect(box(edit.definition).value).toBe('가상 정의 글 고침');
    expect(body()).not.toContain('지어낸');
  });

  it('판 오류: 4,000자 · 제목 1,000자 · 주소 2,048자 · http(s) · 비울 수 없음 · 같은 출처 — 저장 0, 그 칸을 고치면 그 오류 지움', async () => {
    const { server } = setup(editResult());
    await ready();
    await open('impact-1');
    type(edit.definition, 'ㄱ'.repeat(4001));
    fireEvent.click(saveButton());
    expect(screen.getByText(edit.errors.tooLong)).toBeTruthy();
    expect(box(edit.definition).getAttribute('aria-invalid')).toBe('true');
    type(edit.definition, 'ㄱ'.repeat(4000));
    expect(screen.queryByText(edit.errors.tooLong)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: edit.cancel }));

    tab(words.tabs.shortlist);
    await open('shortlist-1');
    const titles = screen.getAllByRole('textbox', { name: edit.title });
    const urls = screen.getAllByRole('textbox', { name: edit.url });
    expect(titles.map((el) => (el as HTMLTextAreaElement).value)).toEqual([
      '규 일',
      '규 삼',
      '컨 일',
    ]);
    const set = (el: HTMLElement, value: string) =>
      fireEvent.change(el, { target: { value } });
    const tryError = (text: string) => {
      fireEvent.click(saveButton());
      expect(screen.getByText(text)).toBeTruthy();
    };
    set(titles[0]!, 'ㄱ'.repeat(1001));
    tryError(edit.errors.titleTooLong);
    set(titles[0]!, '규 일');
    set(urls[0]!, `https://${'a'.repeat(2041)}`);
    tryError(edit.errors.urlTooLong);
    set(urls[0]!, 'ftp://example.test/x');
    tryError(edit.errors.urlScheme);
    set(urls[0]!, ' ');
    tryError(edit.errors.urlLocked);
    set(urls[0]!, R1);
    set(urls[1]!, ` ${R1} `);
    tryError(edit.errors.urlDuplicate);
    expect(posts(server)).toHaveLength(0);
    // 하나뿐인 묶음은 비울 수 있다(규 삼 — impact 하나).
    set(urls[1]!, '');
    fireEvent.click(saveButton());
    await vi.waitFor(() => expect(posts(server)).toHaveLength(1), WAIT);
    expect((posts(server)[0]!.body as Json).changes).toEqual([
      { pointer: `${T}/impact/rows/0/context/regulations/1/url`, value: null },
    ]);
  });

  it('1-1: 항목마다 「n) 라벨」·제목·주소 · 줄 아래 「같은 항목이…」 · 제목 고침은 묶음 첫 자리로', async () => {
    const { server } = setup(editResult());
    await ready();
    tab(words.tabs.shortlist);
    await open('shortlist-1');
    expect(screen.getByTestId('edit-note').textContent).toBe(
      '1-1 을 고치면 2-1 · 2-2 의 같은 항목 요약도 함께 바뀌어요 · 한 번에 한 줄씩 고칠 수 있어요',
    );
    const heads = [...document.querySelectorAll('[data-edit-item]')].map(
      (el) => el.firstElementChild!.textContent,
    );
    expect(heads).toEqual([
      `1) ${words.shortlist.label.both}`,
      `2) ${words.shortlist.label.social}`,
      `1) ${words.shortlist.label.social}`,
    ]);
    expect(
      screen
        .getAllByRole('textbox', { name: edit.url })[0]!
        .getAttribute('placeholder'),
    ).toBe(edit.urlPlaceholder);
    fireEvent.change(screen.getAllByRole('textbox', { name: edit.title })[0]!, {
      target: { value: '규 일 고침' },
    });
    fireEvent.click(saveButton());
    await vi.waitFor(() => expect(posts(server)).toHaveLength(1), WAIT);
    expect((posts(server)[0]!.body as Json).changes).toEqual([
      {
        pointer: `${T}/impact/rows/0/context/regulations/0/title`,
        value: '규 일 고침',
      },
    ]);
    await vi.waitFor(
      () =>
        expect(screen.getByTestId('edited-badge').textContent).toBe(
          edit.badge(1, '14:28'),
        ),
      WAIT,
    );
    expect(
      within(rows('shortlist')[0]!).getAllByTestId('edited-mark'),
    ).toHaveLength(1);
    // m1(IRW12b): 고침 표시 있는 칸도 줄 사이 6 — 연필은 absolute 라 flex 사이에 끼지 않는다
    const edited = within(rows('shortlist')[0]!).getByTestId(
      'edited-mark',
    ).parentElement!;
    expect(edited.hasAttribute('data-edited')).toBe(true);
    expect(edited.className.split(' ')).toEqual(
      expect.arrayContaining(['relative', 'flex', 'flex-col', 'gap-1.5']),
    );
    expect(edited.querySelector('[data-item-label]')!.parentElement).toBe(
      edited,
    );
  });

  it('2-2: 펼침이 저절로 열림 · 넷 + 요약 상자 · 요약은 재무 항목의 바른 주소로 · 다른 줄 누름 0 · i null 줄 요약은 글만 · 저장 뒤 탭 그대로(loading 0)', async () => {
    const { server } = setup(editResult());
    await ready();
    tab(words.tabs.pathway);
    await open('pathway-1');
    expect(
      screen.getAllByRole('textbox').map((el) => el.getAttribute('aria-label')),
    ).toEqual([
      edit.definition,
      words.pathway.head.driver,
      words.pathway.head.business,
      words.pathway.head.financial,
      edit.summary(1),
    ]);
    expect(rows('pathway-edit')).toHaveLength(1);
    expect(rows('pathway')[0]!.getAttribute('aria-expanded')).toBe('true');
    expect(rows('pathway')[1]!.hasAttribute('tabindex')).toBe(false);
    // 편집 중 꺾쇠(IRW13 규칙 5): 줄마다 남되 흐림(quaternary) · 편집 줄은 열림 · 누름 줄 이름 0(줄 누름이 막힘)
    const marks = [
      ...document.querySelectorAll<HTMLElement>(
        '[data-card="pathway"] [data-expand-mark]',
      ),
    ];
    expect(marks.length).toBe(rows('pathway').length);
    for (const mark of marks) {
      expect(mark.hasAttribute('data-dim')).toBe(true);
      expect(mark.querySelector('svg')!.getAttribute('class')).toContain(
        'text-text-quaternary',
      );
    }
    expect(marks[0]!.dataset.expandMark).toBe('open');
    expect(marks[1]!.dataset.expandMark).toBe('closed');
    expect(rows('pathway')[1]!.hasAttribute('aria-label')).toBe(false);
    fireEvent.click(rows('pathway')[1]!);
    expect(rows('pathway-summary')).toHaveLength(0);
    type(edit.summary(1), '규 일 재 요약 고침');
    fireEvent.click(saveButton());
    await vi.waitFor(() => expect(posts(server)).toHaveLength(1), WAIT);
    expect((posts(server)[0]!.body as Json).changes).toEqual([
      { pointer: SUM1, value: '규 일 재 요약 고침' },
    ]);
    await vi.waitFor(
      () => expect(screen.queryAllByRole('textbox')).toHaveLength(0),
      WAIT,
    );
    // [고치기] 누름은 줄 누름을 일으키지 않았다(규칙 3 — 저장 뒤 요약 펼침 0 · 꺾쇠 다시 진하게)
    expect(rows('pathway-summary')).toHaveLength(0);
    expect(rows('pathway')[0]!.getAttribute('aria-expanded')).toBe('false');
    expect(
      document.querySelector('[data-card="pathway"] [data-dim]'),
    ).toBeNull();
    expect(
      screen
        .getByRole('tab', { name: words.tabs.pathway })
        .getAttribute('aria-selected'),
    ).toBe('true');
    expect(document.querySelector('[data-result-state="loading"]')).toBeNull();
    expect(server.count('GET /materiality/runs/7/result')).toBe(2);
    await open('pathway-2');
    expect(screen.queryByRole('textbox', { name: edit.summary(1) })).toBeNull();
    expect(rows('pathway-edit')[0]!.textContent).toContain('규 이 요약');
  });

  it('나가기: 바꾼 채 탭·유형 탭·토픽 → 창 · [계속 고치기] 머묾 · [나가기] 그 이동 · 안 바꾸면 창 0', async () => {
    setup(editResult());
    await ready();
    await open('impact-1');
    type(edit.definition, '가상 정의 글 고침');
    tab(words.tabs.shortlist);
    const dialog = await screen.findByTestId('leave-dialog');
    expect(within(dialog).getByText(edit.leaveBody)).toBeTruthy();
    fireEvent.click(
      within(dialog).getByRole('button', { name: edit.leaveStay }),
    );
    expect(screen.queryByTestId('leave-dialog')).toBeNull();
    expect(box(edit.definition).value).toBe('가상 정의 글 고침');
    fireEvent.mouseDown(
      screen.getByRole('tab', { name: words.impact.positive(0) }),
    );
    fireEvent.click(
      within(await screen.findByTestId('leave-dialog')).getByRole('button', {
        name: edit.leaveStay,
      }),
    );
    choose(words.topicLabel, '가상토픽 B');
    fireEvent.click(
      within(await screen.findByTestId('leave-dialog')).getByRole('button', {
        name: edit.leaveStay,
      }),
    );
    tab(words.tabs.shortlist);
    fireEvent.click(
      within(await screen.findByTestId('leave-dialog')).getByRole('button', {
        name: edit.leaveGo,
      }),
    );
    expect(
      screen
        .getByRole('tab', { name: words.tabs.shortlist })
        .getAttribute('aria-selected'),
    ).toBe('true');
    tab(words.tabs.impact);
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
    await open('impact-1');
    tab(words.tabs.pathway);
    expect(screen.queryByTestId('leave-dialog')).toBeNull();
    expect(
      screen
        .getByRole('tab', { name: words.tabs.pathway })
        .getAttribute('aria-selected'),
    ).toBe('true');
  });

  it('고침을 못 읽으면 읽기 전용(Q7): 고치기 열·연필·배지 0', async () => {
    const { server } = setup(editResult());
    server.override['GET /materiality/runs/7/result/edits'] = () =>
      refusal(500, 'INTERNAL');
    await ready();
    await vi.waitFor(
      () =>
        expect(server.count('GET /materiality/runs/7/result/edits')).toBe(1),
      WAIT,
    );
    expect(editButtons()).toBe(0);
    expect(
      document.querySelectorAll('[data-card="impact"] thead th'),
    ).toHaveLength(7);
    expect(screen.queryByTestId('edited-badge')).toBeNull();
    expect(screen.queryByTestId('edited-mark')).toBeNull();
  });

  it('글(판 r3): 2-1 발 글 · 「고친 값」 줄과 1-1 리서치 안내는 화면에서 걷고 모달 설명으로(밴드 IRW16)', async () => {
    setup(editResult());
    await ready();
    expect(body()).toContain(words.impact.foot);
    expect(words.impact.foot).toBe(
      '영향 정의는 AI 가 쓴 글이고, 컨텍스트 요약은 리서치에서 찾은 글의 요약이에요. 출처는 「1-1 토픽별 리서치」 탭에 있어요.',
    );
    expect(screen.queryByTestId('report-edited')).toBeNull();
    expect(body()).not.toContain('결과 엑셀에는 고친 값이 나가요');
    tab(words.tabs.shortlist);
    expect(screen.queryByTestId('research-note')).toBeNull();
    expect(body()).not.toContain('AI 가 찾은 원본 그대로예요');
  });

  it('1-1 근거 글(IRW14 — 결정 MARC-ENT-656): 리서치 엑셀 파일이 있으면 두 문장 · 없으면 첫 문장만 · foot 앞(밴드 IRW16 — 조건은 파일)', async () => {
    expect(words.shortlist.basis).toBe(
      '영향의 근거로 쓴 규제·정책·컨트로버시만 보여요.',
    );
    expect(words.shortlist.basisResearch).toBe('전체는 리서치 엑셀에 있어요.');
    setup(editResult());
    await ready();
    tab(words.tabs.shortlist);
    const both = screen.getByTestId('shortlist-basis');
    expect(both.textContent).toBe(
      '영향의 근거로 쓴 규제·정책·컨트로버시만 보여요. 전체는 리서치 엑셀에 있어요.',
    );
    expect(both.nextElementSibling!.textContent).toBe(words.shortlist.foot);
    cleanup();
    setup(editResult(), { files: [REPORT] });
    await ready();
    tab(words.tabs.shortlist);
    const one = screen.getByTestId('shortlist-basis');
    expect(one.textContent).toBe(words.shortlist.basis);
    expect(one.textContent).not.toContain('리서치 엑셀');
    expect(one.nextElementSibling!.textContent).toBe(words.shortlist.foot);
  });

  it('연필은 초점으로도 툴팁 「고친 사람 … · …」', async () => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    const { server } = setup(editResult());
    server.editElsewhere(7, DEF, '먼저 고친 정의 글');
    await ready();
    const mark = await screen.findByTestId('edited-mark', undefined, WAIT);
    fireEvent.focus(mark);
    expect(
      (await screen.findByRole('tooltip', undefined, WAIT)).textContent,
    ).toBe(edit.editedBy('담당자 A', '11-03 14:28'));
    vi.unstubAllGlobals();
  });

  it('536: 잘린 활동 덩이만 tabIndex 0 · 초점이면 툴팁 · 안 잘린 덩이는 tabIndex 없음', async () => {
    const LONG_ACT = '가상 활동 아주 긴 글 '.repeat(8);
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
    const proto = HTMLElement.prototype;
    const scroll = Object.getOwnPropertyDescriptor(proto, 'scrollHeight');
    const client = Object.getOwnPropertyDescriptor(proto, 'clientHeight');
    Object.defineProperty(proto, 'scrollHeight', {
      configurable: true,
      get(this: HTMLElement) {
        return this.textContent === LONG_ACT ? 60 : 20;
      },
    });
    Object.defineProperty(proto, 'clientHeight', {
      configurable: true,
      get() {
        return 20;
      },
    });
    try {
      const raw = editResult();
      const sub = (raw.part2 as { topics: { subtopics: Json[] }[] }).topics[0]!
        .subtopics[0]!;
      ((sub.impact as Json).rows as Json[])[0]!.valueChainActivities = [
        '가상 활동 짧음',
        LONG_ACT,
      ];
      setup(raw);
      await ready();
      const [short, long] = [
        ...rows('impact')[0]!.querySelectorAll<HTMLElement>('[data-activity]'),
      ];
      expect(short!.hasAttribute('tabindex')).toBe(false);
      expect(long!.getAttribute('tabindex')).toBe('0');
      fireEvent.focus(long!);
      expect(
        (await screen.findByRole('tooltip', undefined, WAIT)).textContent,
      ).toBe(LONG_ACT);
    } finally {
      if (scroll) Object.defineProperty(proto, 'scrollHeight', scroll);
      else delete (proto as unknown as Json).scrollHeight;
      if (client) Object.defineProperty(proto, 'clientHeight', client);
      else delete (proto as unknown as Json).clientHeight;
      vi.unstubAllGlobals();
    }
  });
});
