// @vitest-environment jsdom
// IR-02 새 평가 화면 시험(밴드 IRW2 ② — 발주서 §3 시험 5, 부록 A2·A4·A5·A6). 저장소는 가짜 중대성평가 서버를 앞에 둔 실어댑터(목 0).
//   탭 셋(IRW3 직접 입력) · 올리기 갈래(ok·bad_header·not_xlsx·too_long·끊김) + 판정 size·type·count(요청 0) · 붙여 넣기 · 표 편집 · [모두 지우기] ·
//   밸류체인 빈 칸 · [평가 시작] 검사(첫 오류 칸 초점·값 그대로·접힌 카드 펼침) · 누르는 동안 끔 · 거절 글(서버 message 0) · onStarted 한 번 ·
//   실패 뒤 다시 누름 = 같은 열쇠. 키트 Tabs(radix)는 mouseDown 으로 누른다. 값은 전부 지어낸 것이다.
//   IRW15(결정 MARC-ENT-668): [양식 받기](엑셀 탭만·파일 창 0) · 밸류체인 표기 더 받기 · 「최신 이슈 반영」 토글 0(요청 false) · 떠나기 경고(onDirtyChange·나가기 창).
//   IRW17: 「주 검색 언어」+ 한국어 정리 안내 · 업종 구분은 1. 카드 산업 분류 아래 · 떠나기 경고 빈틈(붙여 넣기 글·실패 파일 줄).
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  fakeMaterialityServer,
  refusal,
  serverStoreOf,
  unreachable,
  valueChainRejected,
} from '../../../entities/materiality/api/testing.ts';
import { IR_TEXT } from '../../../entities/materiality/config/text.ts';
import { NewScreen } from './NewScreen.tsx';
import type { NewScreenProps } from './NewScreen.tsx';

afterEach(cleanup);

const words = IR_TEXT.newRun;
const vc = words.valueChain;
/** 서울 2026-10-28. */
const NOW = () => new Date('2026-10-28T03:00:00Z');
const READ = 'POST /materiality/value-chain/read';

function keys(prefix: string) {
  let n = 0;
  return () =>
    `${prefix}000000-0000-4000-8000-${String(++n).padStart(12, '0')}`;
}

function setup(
  valueChain?: unknown,
  extra: Partial<Pick<NewScreenProps, 'onDirtyChange' | 'leave'>> = {},
) {
  const server = fakeMaterialityServer({ nextRunId: 55, valueChain });
  const store = serverStoreOf(server, {
    newKey: keys('aa'),
    newLaunchKey: keys('bb'),
  });
  const onStarted = vi.fn();
  const onCancel = vi.fn();
  const view = render(
    <NewScreen
      store={store}
      now={NOW}
      onStarted={onStarted}
      onCancel={onCancel}
      {...extra}
    />,
  );
  return { server, onStarted, onCancel, view, store };
}

const box = (name: string) => screen.getByRole('textbox', { name });
const type = (name: string, value: string) =>
  fireEvent.change(box(name), { target: { value } });

/** 꼭 칸 넷(기업명·SASB 이름·토픽 이름·서브토픽 이름). */
function fillRequired() {
  type('기업명', '가상물산');
  type('SASB 산업명', '가상 산업');
  type('1번째 토픽 이름', '가상토픽 A');
  type('가상토픽 A 서브토픽 이름', '가상 서브');
}

const xlsx = (name = '가치사슬.xlsx', bytes = 10) =>
  new File([new Uint8Array(bytes).fill(80)], name);

async function upload(...files: File[]) {
  const input = document.querySelector<HTMLInputElement>(
    '[data-testid="value-chain"] input[type="file"]',
  )!;
  await act(async () => {
    fireEvent.change(input, { target: { files } });
  });
  await act(async () => {});
}

async function start() {
  await act(async () => {
    fireEvent.click(screen.getByTestId('start'));
  });
  await act(async () => {});
}

const paste = (text: string) => {
  fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabPaste }));
  fireEvent.change(box(vc.pasteLabel), { target: { value: text } });
};

const TSV = [
  vc.columns.join('\t'),
  '가상 부문\t가상 시공\t자체운영\t근로자\t안전 관리',
  '\t\t중류\t협력회사\t구매',
].join('\n');

describe('IR-02 처음 꼴(A6-⑪)', () => {
  it('머리·STEP 1·카드 셋·처음 값 · 판 예시 값 0', () => {
    setup();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      '새 평가',
    );
    expect(
      screen
        .getByRole('list', { name: '평가 단계' })
        .querySelector('[aria-current="step"]')!.textContent,
    ).toContain('기본 정보 입력');
    for (const title of [
      '1. 기업과 산업',
      '2. 중대 토픽 (Short-list)',
      '3. 리서치 조건',
    ])
      expect(screen.getByRole('heading', { name: title })).toBeTruthy();
    expect((box('기업명') as HTMLInputElement).value).toBe('');
    expect((box('검색 지역') as HTMLInputElement).value).toBe(
      '글로벌(대한민국 · 북미 · EU 우선)',
    );
    expect((box('시작일') as HTMLInputElement).value).toBe('2024-01-01');
    expect(
      (screen.getByRole('combobox', { name: '기준 국가' }) as HTMLSelectElement)
        .value,
    ).toBe('KR');
    expect(
      screen.getByRole('combobox', { name: '주 검색 언어' }).textContent,
    ).toBe('한국어');
    expect(
      screen
        .getByRole('radio', { name: '비금융' })
        .getAttribute('aria-checked'),
    ).toBe('true');
    // IRW15 ③: 「최신 이슈 반영」 토글과 설명 줄 0
    expect(screen.queryByRole('switch')).toBeNull();
    expect(document.body.textContent).not.toContain('최신 이슈');
    expect(screen.getAllByTestId('topic-card')).toHaveLength(1);
    expect(
      screen
        .getByRole('tab', { name: vc.tabFile })
        .getAttribute('aria-selected'),
    ).toBe('true');
    expect(document.body.textContent).toContain(vc.empty);
    expect(document.body.textContent).not.toContain('가상건설');
    expect(screen.getByText('토픽 1개 · 서브토픽 0개')).toBeTruthy();
  });
});

describe('IR-02 설명 예시(IRW14 — 결정 MARC-ENT-656)', () => {
  it('산업 예시는 늘 보이는 줄 하나 · SASB 설명 입력칸 바로 아래 같은 값 칸 안(IRW14b) · GICS·KSIC 0 · placeholder 에는 예시 0', () => {
    setup();
    const example =
      '산업 설명 예) 자동차 부품 제조 — 협력사 공급망, 작업장 안전, 제품 품질';
    expect(words.company.industryExample).toBe(example);
    expect(example.startsWith('산업 설명 예)')).toBe(true);
    const rows = screen.getAllByTestId('industry-example');
    expect(rows).toHaveLength(1);
    expect(rows[0]!.textContent).toBe(example);
    expect(document.body.textContent!.split(example)).toHaveLength(2);
    const sasb = box('SASB 산업 설명');
    expect(rows[0]!.previousElementSibling).toBe(sasb);
    expect(rows[0]!.parentElement).toBe(sasb.parentElement);
    for (const standard of ['GICS', 'KSIC'])
      expect(
        within(box(`${standard} 산업 설명`).parentElement!).queryAllByTestId(
          'industry-example',
        ),
      ).toHaveLength(0);
    for (const standard of ['SASB', 'GICS', 'KSIC'])
      expect(box(`${standard} 산업 설명`).getAttribute('placeholder')).toBe(
        '이 산업의 주요 사업과 관리 포인트를 한두 문장으로 적어요',
      );
  });

  it('토픽 카드마다 예시가 든 안내 줄 · 토픽 설명 placeholder 에는 예시 0', () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: words.topics.add }));
    const hint =
      '설명을 기준으로 규제·컨트로버시를 찾아요 · 예) 사업장·공급망의 온실가스 배출과 감축';
    expect(words.topics.descriptionHint).toBe(hint);
    expect(screen.getAllByTestId('topic-card')).toHaveLength(2);
    // 펼친 카드는 하나뿐이라 카드마다 펼쳐 본다(토픽 이름이 비어 「토픽 설명」).
    for (const index of [0, 1]) {
      const card = screen.getAllByTestId('topic-card')[index]!;
      if (card.getAttribute('data-open') === 'false')
        fireEvent.click(within(card).getByRole('button'));
      const open = screen.getAllByTestId('topic-card')[index]!;
      expect(open.getAttribute('data-open')).toBe('true');
      expect(within(open).getByText(hint)).toBeTruthy();
      expect(
        within(open)
          .getByRole('textbox', { name: '토픽 설명' })
          .getAttribute('placeholder'),
      ).toBe('이 토픽에서 무엇을 조사할지 한두 문장으로 적어요');
    }
  });
});

describe('가치사슬 — 엑셀 올리기', () => {
  it('ok → 표(밸류체인 서버 값·못 맞춘 칸 빔 + 표 위 글) · 파일 칩 「활동 n개 · 사업 부문 m개」 · 맨 바이트 한 번', async () => {
    const { server } = setup();
    await upload(xlsx());
    expect(server.count(READ)).toBe(1);
    const chip = screen.getByTestId('file-line');
    expect(chip.textContent).toContain('가치사슬.xlsx');
    expect(chip.textContent).toContain('활동 3개 · 사업 부문 2개');
    const stage = (n: number) =>
      screen.getByRole('combobox', {
        name: `${n}행 밸류체인`,
      }) as HTMLSelectElement;
    expect([stage(1).value, stage(2).value, stage(3).value]).toEqual([
      'own operations',
      'upstream',
      '',
    ]);
    expect(stage(3).getAttribute('aria-invalid')).toBe('true');
    expect(stage(1).getAttribute('aria-invalid')).toBeNull();
    expect(screen.getByTestId('stage-error').textContent).toBe(
      '밸류체인은 업스트림 · 자체운영 · 다운스트림 중에서 골라 주세요 (3행)',
    );
    // 고르면 사라진다
    fireEvent.change(stage(3), { target: { value: 'downstream' } });
    expect(screen.queryByTestId('stage-error')).toBeNull();
    // 표가 있으면 넣기 자리는 숨는다
    expect(
      document.querySelector('[data-testid="value-chain"] input[type="file"]'),
    ).toBeNull();
  });

  it('서버 거절 kind → 부록 A5 글 · 파일 이름 흐리게 「넣지 못함」 · 올리기 자리 남음', async () => {
    const cases: [unknown, string][] = [
      [valueChainRejected('bad_header'), vc.errors.badHeader],
      [valueChainRejected('not_xlsx'), vc.errors.notTable],
      [valueChainRejected('unsafe_xlsx'), vc.errors.notTable],
      [valueChainRejected('no_rows'), vc.errors.notTable],
      [
        valueChainRejected('too_large'),
        '파일이 너무 커요. 1MB 이하로 올려 주세요',
      ],
      [
        valueChainRejected('too_many_rows', 101),
        '활동이 너무 많아요. 100행까지 넣을 수 있어요',
      ],
      [
        valueChainRejected('too_many_scanned_rows'),
        '빈 줄이 너무 많아요 · 표만 남기고 다시 올려 주세요',
      ],
      [
        valueChainRejected('too_long', 4, 1),
        '4행의 사업 내용 칸이 너무 길어요. 200자까지예요',
      ],
      [
        valueChainRejected('not_text', 2, 3),
        '2행의 이해관계자 칸이 글자가 아니에요. 셀 서식을 텍스트로 바꿔 주세요',
      ],
    ];
    for (const [answer, text] of cases) {
      setup(answer);
      await upload(xlsx('표.xlsx'));
      expect(screen.getByTestId('value-chain-error').textContent).toBe(text);
      const failed = screen.getByTestId('file-line-failed');
      expect(failed.textContent).toContain('표.xlsx');
      expect(failed.textContent).toContain(vc.failed);
      expect(document.body.textContent).not.toContain('지어낸-');
      expect(
        document.querySelector(
          '[data-testid="value-chain"] input[type="file"]',
        ),
      ).not.toBeNull();
      cleanup();
    }
  });

  it('IRW6 파일 줄 = 공용 목록: 읽힘 → li 하나 · 이름 · meta · 날짜 · [×] 하나(IRW7) · 칩 0 · 실패 → 「넣지 못함」 빨강', async () => {
    setup();
    await upload(xlsx());
    const line = screen.getByTestId('file-line');
    const items = line.querySelectorAll('li');
    expect(items).toHaveLength(1);
    expect(items[0]!.textContent).toContain('가치사슬.xlsx');
    expect(line.querySelector('[data-testid="file-meta"]')?.textContent).toBe(
      '활동 3개 · 사업 부문 2개',
    );
    expect(items[0]!.textContent).toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(line.querySelectorAll('button')).toHaveLength(1);
    expect(document.querySelector('[data-testid*="chip"]')).toBeNull(); // 옛 칩 0
    cleanup();

    setup(valueChainRejected('bad_header'));
    await upload(xlsx('표.xlsx'));
    const failed = screen.getByTestId('file-line-failed');
    expect(failed.querySelectorAll('li')).toHaveLength(1);
    const mark = [...failed.querySelectorAll('li span')].find(
      (span) => span.textContent === vc.failed,
    );
    expect(mark?.className).toContain('text-support-error');
    expect(failed.querySelectorAll('button')).toHaveLength(0);
  });

  it('IRW6 D1: 가치사슬 표 머리 th 전부 공용 결과 표 머리 바탕·위아래 선', async () => {
    setup();
    await upload(xlsx());
    const heads = [
      ...screen.getByTestId('value-chain-table').querySelectorAll('thead th'),
    ];
    expect(heads.length).toBeGreaterThan(0);
    for (const th of heads) {
      expect(th.className).toContain('bg-support-grey-subtle');
      expect(th.className).toContain('border-y');
    }
  });

  it('끊김·5xx → A6-⑥', async () => {
    for (const answer of [
      unreachable,
      () => refusal(503, 'SERVICE_UNAVAILABLE'),
    ]) {
      const { server } = setup();
      server.override[READ] = answer;
      await upload(xlsx());
      expect(screen.getByTestId('value-chain-error').textContent).toBe(
        '파일을 읽지 못했어요. 잠시 뒤 다시 올려 주세요',
      );
      cleanup();
    }
  });

  it('판정 밖: 1MB 넘음 → A6-① · .xlsx 아님·두 개 → 「표가 비어…」 — 요청 0', async () => {
    const cases: [File[], string][] = [
      [[xlsx('큰.xlsx', 1024 * 1024 + 1)], vc.errors.tooLarge],
      [[new File(['a,b'], '가치사슬.csv')], vc.errors.notTable],
      [[xlsx('하나.xlsx'), xlsx('둘.xlsx')], vc.errors.notTable],
    ];
    for (const [files, text] of cases) {
      const { server } = setup();
      await upload(...files);
      expect(server.count(READ)).toBe(0);
      expect(screen.getByTestId('value-chain-error').textContent).toBe(text);
      expect(screen.getByTestId('file-line-failed').textContent).toContain(
        files[0]!.name,
      );
      cleanup();
    }
    // 꼭 1MB 는 보낸다
    const { server } = setup();
    await upload(xlsx('꼭.xlsx', 1024 * 1024));
    expect(server.count(READ)).toBe(1);
  });

  it('[모두 지우기] → 넣기 자리로 · 표 편집 · [행 추가] · 행 지우기', async () => {
    setup();
    await upload(xlsx());
    fireEvent.change(box('1행 사업 부문'), { target: { value: '고친 부문' } });
    expect((box('1행 사업 부문') as HTMLInputElement).value).toBe('고친 부문');
    fireEvent.click(screen.getByRole('button', { name: vc.addRow }));
    expect(box('4행 이해관계자')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: '4행 지우기' }));
    expect(
      screen.queryByRole('textbox', { name: '4행 이해관계자' }),
    ).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: vc.clear }));
    expect(screen.queryByTestId('value-chain-table')).toBeNull();
    expect(
      document.querySelector('[data-testid="value-chain"] input[type="file"]'),
    ).not.toBeNull();
    await upload(xlsx());
    fireEvent.click(screen.getByRole('button', { name: vc.clear }));
    expect(screen.queryByTestId('value-chain-table')).toBeNull();
  });
});

describe('가치사슬 — 파일 줄 [×](IRW7, IRW6 전과 같음)', () => {
  const fileInputs = () =>
    document.querySelectorAll('[data-testid="value-chain"] input[type="file"]');
  const removeName = `가치사슬.xlsx ${vc.removeFile}`;

  it('N1 읽힘 줄 [×] → 표·파일 줄 0 · 넣기 자리 보임([모두 지우기]와 같은 끝)', async () => {
    setup();
    await upload(xlsx());
    fireEvent.click(screen.getByRole('button', { name: removeName }));
    expect(screen.queryByTestId('value-chain-table')).toBeNull();
    expect(screen.queryByTestId('file-line')).toBeNull();
    expect(screen.queryByTestId('file-line-failed')).toBeNull();
    expect(fileInputs()).toHaveLength(1);
    expect(screen.getByText(vc.dropTitle)).toBeTruthy();
    await upload(xlsx());
    expect(screen.getByTestId('value-chain-table')).toBeTruthy();
    // 지운 파일이 남지 않음: [×] 뒤 [직접 입력]으로 표가 다시 생겨도 파일 줄(li·이름) 0
    fireEvent.click(screen.getByRole('button', { name: removeName }));
    fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabManual }));
    type('1행 사업 부문', '가상 부문');
    expect(screen.getByTestId('value-chain-table')).toBeTruthy();
    expect(screen.queryByTestId('file-line')).toBeNull();
    expect(document.body.textContent).not.toContain('가치사슬.xlsx');
  });

  it('N2 실패 줄 → [×] 0 · 넣기 자리 그대로', async () => {
    setup(valueChainRejected('bad_header'));
    await upload(xlsx('표.xlsx'));
    const failed = screen.getByTestId('file-line-failed');
    expect(failed.querySelectorAll('button')).toHaveLength(0);
    expect(
      screen.queryByRole('button', { name: `표.xlsx ${vc.removeFile}` }),
    ).toBeNull();
    expect(fileInputs()).toHaveLength(1);
  });

  it('N3 누르는 동안(disabled) → [×] 0', async () => {
    const { server } = setup();
    fillRequired();
    await upload(xlsx());
    for (const row of [1, 2, 3]) {
      const stage = screen.getByRole('combobox', {
        name: `${row}행 밸류체인`,
      }) as HTMLSelectElement;
      if (stage.value === '')
        fireEvent.change(stage, { target: { value: 'upstream' } });
    }
    expect(screen.getByRole('button', { name: removeName })).toBeTruthy();
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['POST /runs'] = async () => {
      await gate;
      return new Response(JSON.stringify({ id: 55, status: 'queued' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    };
    await start();
    expect(server.posts()).toHaveLength(1);
    expect(
      screen.getByTestId('file-line').querySelectorAll('button'),
    ).toHaveLength(0);
    expect(screen.queryByRole('button', { name: removeName })).toBeNull();
    await act(async () => release());
    await act(async () => {});
  });

  it('N4 표가 있으면 드롭존 칸·input 0(hideDrop) · 파일 줄 안에도 0', async () => {
    setup();
    await upload(xlsx());
    const line = screen.getByTestId('file-line');
    expect(fileInputs()).toHaveLength(0);
    expect(line.querySelectorAll('input')).toHaveLength(0);
    expect(line.querySelectorAll('[role="button"]')).toHaveLength(0);
    expect(screen.queryByText(vc.dropTitle)).toBeNull();
  });
});

describe('가치사슬 — 붙여 넣기', () => {
  it('열 이름 줄 뗌 · 같은 표 · 물려받기 · 파일 칩 없음 · 서버 0', () => {
    const { server } = setup();
    paste(TSV);
    expect(server.count(READ)).toBe(0);
    expect(screen.queryByTestId('file-line')).toBeNull();
    expect((box('1행 사업 부문') as HTMLInputElement).value).toBe('가상 부문');
    expect((box('2행 사업 부문') as HTMLInputElement).value).toBe('가상 부문');
    expect((box('2행 사업 내용') as HTMLInputElement).value).toBe('가상 시공');
    expect(screen.queryByRole('textbox', { name: '3행 사업 부문' })).toBeNull();
    expect(screen.getByTestId('stage-error').textContent).toContain('(2행)');
  });

  it('5열 아님 → 「붙여 넣은 표가 n열이에요…」 · 글 칸 남음', () => {
    setup();
    paste('가\t나\t다\t라');
    expect(screen.getByTestId('value-chain-error').textContent).toBe(
      '붙여 넣은 표가 4열이에요. 사업 부문부터 관련 비즈니스 활동까지 5열을 복사해 주세요',
    );
    expect((box(vc.pasteLabel) as HTMLTextAreaElement).value).toBe(
      '가\t나\t다\t라',
    );
  });

  it('긴 칸 → A6-③ · 101 행 → A6-②', () => {
    setup();
    paste(`가\t나\t업스트림\t${'x'.repeat(51)}\t마`);
    expect(screen.getByTestId('value-chain-error').textContent).toBe(
      '1행의 이해관계자 칸이 너무 길어요. 50자까지예요',
    );
    paste(Array.from({ length: 101 }, () => '가\t\t업스트림\t\t').join('\n'));
    expect(screen.getByTestId('value-chain-error').textContent).toBe(
      vc.errors.tooManyRows,
    );
  });

  it('밸류체인 빈 행 여럿 「(a·b·c행 외 k행)」', () => {
    setup();
    paste(Array.from({ length: 5 }, () => '가\t\t중류\t라\t').join('\n'));
    expect(screen.getByTestId('stage-error').textContent).toBe(
      '밸류체인은 업스트림 · 자체운영 · 다운스트림 중에서 골라 주세요 (1·2·3행 외 2행)',
    );
  });
});

describe('가치사슬 — 직접 입력 · 판 v170 값(IRW3)', () => {
  const manual = () =>
    fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabManual }));
  const tab = (name: string) =>
    fireEvent.mouseDown(screen.getByRole('tab', { name }));
  const cell = (name: string) => box(name) as HTMLInputElement;

  it('탭 셋(엑셀 올리기 · 붙여 넣기 · 직접 입력) · 밑줄 탭(N1)', () => {
    setup();
    const tabs = screen.getAllByRole('tab');
    expect(tabs.map((each) => each.textContent)).toEqual([
      vc.tabFile,
      vc.tabPaste,
      vc.tabManual,
    ]);
    for (const each of tabs) expect(each.className).toContain('min-w-24');
  });

  it('처음 꼴 = 빈 행 하나의 표 + [＋ 행 추가]만 + 「비워 두면…」 · 파일 칩 0', () => {
    setup();
    manual();
    expect(screen.getByTestId('value-chain-table')).toBeTruthy();
    for (const column of vc.columns.filter((_, at) => at !== 2))
      expect(cell(`1행 ${column}`).value).toBe('');
    expect(
      (
        screen.getByRole('combobox', {
          name: '1행 밸류체인',
        }) as HTMLSelectElement
      ).value,
    ).toBe('');
    expect(screen.queryByRole('textbox', { name: '2행 사업 부문' })).toBeNull();
    const add = screen.getByRole('button', { name: vc.addRow });
    expect(add.querySelector('svg[aria-hidden]')).not.toBeNull();
    expect(screen.queryByRole('button', { name: vc.clear })).toBeNull();
    expect(screen.getByText(vc.empty)).toBeTruthy();
    expect(screen.queryByTestId('file-line')).toBeNull();
    expect(screen.queryByTestId('stage-error')).toBeNull();
  });

  it('적으면 행 · [행 추가] · 행 지우기·[모두 지우기]로 0 이면 다시 빈 행 하나(①) · 파일 칩 0(④)', () => {
    setup();
    manual();
    fireEvent.change(cell('1행 사업 부문'), { target: { value: '가상 부문' } });
    expect(cell('1행 사업 부문').value).toBe('가상 부문');
    expect(screen.queryByTestId('file-line')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: vc.addRow }));
    expect(cell('2행 사업 부문').value).toBe('');
    fireEvent.click(screen.getByRole('button', { name: '2행 지우기' }));
    fireEvent.click(screen.getByRole('button', { name: '1행 지우기' }));
    expect(cell('1행 사업 부문').value).toBe('');
    expect(screen.queryByRole('textbox', { name: '2행 사업 부문' })).toBeNull();
    fireEvent.change(cell('1행 이해관계자'), { target: { value: '가상' } });
    fireEvent.click(screen.getByRole('button', { name: vc.clear }));
    expect(cell('1행 이해관계자').value).toBe('');
    expect(screen.queryByRole('button', { name: vc.clear })).toBeNull();
  });

  it('다 빈 행뿐이면 탭을 바꿀 때 그 탭의 넣기 자리(②) · 채운 행이 있으면 표 그대로(③)', () => {
    setup();
    manual();
    fireEvent.click(screen.getByRole('button', { name: vc.addRow }));
    fireEvent.change(cell('2행 사업 부문'), { target: { value: '  ' } });
    tab(vc.tabPaste);
    expect(screen.queryByTestId('value-chain-table')).toBeNull();
    expect(box(vc.pasteLabel)).toBeTruthy();
    tab(vc.tabFile);
    expect(
      document.querySelector('[data-testid="value-chain"] input[type="file"]'),
    ).not.toBeNull();
    manual();
    expect(screen.queryByRole('textbox', { name: '2행 사업 부문' })).toBeNull();
    fireEvent.change(cell('1행 관련 비즈니스 활동'), {
      target: { value: '가상 활동' },
    });
    tab(vc.tabPaste);
    expect(cell('1행 관련 비즈니스 활동').value).toBe('가상 활동');
    expect(screen.queryByRole('textbox', { name: vc.pasteLabel })).toBeNull();
  });

  it('직접 적은 값 → [평가 시작] 본문 valueChain(다 빈 행은 빠짐 · 밸류체인 글 0)', async () => {
    const { server } = setup();
    fillRequired();
    manual();
    type('1행 사업 부문', '가상 부문');
    type('1행 사업 내용', '가상 내용');
    fireEvent.change(screen.getByRole('combobox', { name: '1행 밸류체인' }), {
      target: { value: 'upstream' },
    });
    type('1행 이해관계자', '가상 협력사');
    type('1행 관련 비즈니스 활동', '가상 구매');
    fireEvent.click(screen.getByRole('button', { name: vc.addRow }));
    await start();
    expect(screen.queryByTestId('stage-error')).toBeNull();
    expect(server.posts()).toHaveLength(1);
    const { options } = server.posts()[0]!.body as {
      options: { input: { valueChain: unknown } };
    };
    expect(options.input.valueChain).toEqual([
      {
        business_unit: '가상 부문',
        business_unit_description: '가상 내용',
        value_chain_stage: 'upstream',
        stakeholder: '가상 협력사',
        business_activity: '가상 구매',
      },
    ]);
  });

  it('다 빈 행은 빨강·aria-invalid 0 — 밸류체인 빈 찬 행만(IRW3 검증 1 B2)', async () => {
    const { server } = setup();
    fillRequired();
    manual();
    fireEvent.click(screen.getByRole('button', { name: vc.addRow }));
    type('2행 사업 부문', '가상 부문');
    await start();
    expect(server.posts()).toHaveLength(0);
    expect(screen.getByTestId('stage-error').textContent).toContain('(2행)');
    expect(
      screen
        .getByRole('combobox', { name: '1행 밸류체인' })
        .hasAttribute('aria-invalid'),
    ).toBe(false);
    expect(
      screen
        .getByRole('combobox', { name: '2행 밸류체인' })
        .getAttribute('aria-invalid'),
    ).toBe('true');
  });

  it('빈 행 하나뿐인 직접 입력 → [평가 시작] valueChain null', async () => {
    const { server } = setup();
    fillRequired();
    manual();
    await start();
    const { options } = server.posts()[0]!.body as {
      options: { input: { valueChain: unknown } };
    };
    expect(options.input.valueChain).toBeNull();
  });

  it('오류 줄 = 400 12 + ⓘ 아이콘 aria-hidden(N3) · 글 칸 점선(N5, 오류 때도 점선 — Q5)', async () => {
    setup();
    paste('가\t나\t다\t라');
    const error = screen.getByTestId('value-chain-error');
    expect(error.className).toContain('text-style-pre-caption-03');
    expect(error.className).not.toContain('text-style-pre-caption-02');
    expect(error.getAttribute('role')).toBe('alert');
    expect(error.querySelector('svg[aria-hidden]')).not.toBeNull();
    const area = box(vc.pasteLabel);
    expect(area.getAttribute('aria-invalid')).toBe('true');
    for (const name of ['border-dashed', 'border-text-quaternary', 'min-h-24'])
      expect(area.className).toContain(name);
    await start();
    const company = screen.getByText(words.required.company);
    expect(company.className).toContain('text-style-pre-caption-03');
    expect(company.querySelector('svg[aria-hidden]')).not.toBeNull();
  });

  it('표 머리 왼쪽 맞춤·좌우 8 · 칸 8(N2) · [토픽 더하기]·[서브토픽 더하기] ＋ 아이콘(N4)', () => {
    setup();
    manual();
    const table = screen.getByTestId('value-chain-table');
    for (const th of table.querySelectorAll('th')) {
      expect(th.className).toContain('h-10');
      expect(th.className).toContain('px-2');
    }
    expect(table.querySelector('th')!.className).toContain('text-left');
    expect(table.querySelector('td')!.className).toContain('p-2');
    for (const name of [words.topics.add, words.topics.addSub])
      expect(
        screen.getByRole('button', { name }).querySelector('svg[aria-hidden]'),
      ).not.toBeNull();
  });

  it('토픽 이름이 비면 서브토픽 aria 앞 빈칸 0', () => {
    setup();
    const labels = [
      ...document.querySelectorAll('[aria-label*="서브토픽"]'),
    ].map((each) => each.getAttribute('aria-label'));
    expect(labels).toContain('서브토픽 이름');
    expect(labels).toContain('서브토픽 설명');
    for (const label of labels) expect(label!.startsWith(' ')).toBe(false);
  });
});

describe('[평가 시작]', () => {
  it('빈 폼 → 칸마다 글 · 첫 오류 칸(기업명) 초점 · 요청 0', async () => {
    const { server } = setup();
    await start();
    expect(server.posts()).toHaveLength(0);
    const body = document.body.textContent!;
    expect(body).toContain('기업명을 넣어 주세요');
    expect(body).toContain(
      'SASB 산업명을 넣어 주세요 · GICS · KSIC 만으로는 시작할 수 없어요',
    );
    expect(body).toContain('토픽 이름을 넣어 주세요');
    expect(body).toContain(
      '서브토픽을 하나 이상 넣어 주세요 · 영향은 서브토픽마다 정해요',
    );
    expect(document.activeElement).toBe(box('기업명'));
    expect(box('기업명').getAttribute('aria-invalid')).toBe('true');
    // 고치면 그 자리에서 사라진다
    type('기업명', '가상물산');
    expect(document.body.textContent).not.toContain('기업명을 넣어 주세요');
  });

  it('시작일: 오늘 → 「앞선 날」 · 달력 밖 → A6-⑨ · 넣은 값 그대로 · 초점', async () => {
    const { server } = setup();
    fillRequired();
    type('시작일', '2026-10-28');
    await start();
    expect(document.body.textContent).toContain(
      '시작일은 오늘보다 앞선 날이어야 해요',
    );
    expect((box('시작일') as HTMLInputElement).value).toBe('2026-10-28');
    expect(document.activeElement).toBe(box('시작일'));
    type('시작일', '2024-02-30');
    expect(document.body.textContent).toContain('시작일을 넣어 주세요');
    expect(server.posts()).toHaveLength(0);
  });

  it('검색 지역 빔 → A6-⑭ · GICS 설명만 → A6-⑩', async () => {
    setup();
    fillRequired();
    type('검색 지역', ' ');
    type('GICS 산업 설명', '설명만');
    await start();
    const body = document.body.textContent!;
    expect(body).toContain('검색 지역을 넣어 주세요');
    expect(body).toContain(
      'GICS 산업명을 넣어 주세요 · 설명만으로는 넣지 않아요',
    );
    expect(document.activeElement).toBe(box('GICS 산업명'));
  });

  it('토픽 더하기는 앞 카드를 접고 · 겹친 이름은 그 카드를 펼쳐 초점', async () => {
    setup();
    fillRequired();
    fireEvent.click(screen.getByRole('button', { name: words.topics.add }));
    const folded = screen.getByRole('button', { name: '가상토픽 A 펼치기' });
    expect(folded.textContent).toBe('서브토픽 1개 · 펼치기');
    type('2번째 토픽 이름', '가상토픽 A');
    type('가상토픽 A 서브토픽 이름', '서브');
    await start();
    expect(document.body.textContent).toContain(
      '같은 이름의 토픽이 있어요. 토픽 이름은 한 번씩만 넣어 주세요',
    );
    expect(document.activeElement).toBe(box('2번째 토픽 이름'));
  });

  it('서브토픽 설명만 → 「서브토픽 이름을 넣어 주세요」 · 지우기 단추 이름(A6-⑬)', async () => {
    setup();
    fillRequired();
    fireEvent.click(screen.getByRole('button', { name: words.topics.addSub }));
    const descriptions = screen.getAllByRole('textbox', {
      name: '가상토픽 A 서브토픽 설명',
    });
    fireEvent.change(descriptions[1]!, { target: { value: '설명만' } });
    expect(
      screen.getByRole('button', { name: '가상토픽 A 서브토픽 2 지우기' }),
    ).toBeTruthy();
    await start();
    expect(document.body.textContent).toContain('서브토픽 이름을 넣어 주세요');
    expect(document.activeElement).toBe(
      screen.getAllByRole('textbox', { name: '가상토픽 A 서브토픽 이름' })[1],
    );
  });

  it('밸류체인 빈 칸 → 그 고름 칸 초점 · 요청 0', async () => {
    const { server } = setup();
    fillRequired();
    paste('가\t\t업스트림\t\t\n나\t\t\t라\t');
    await start();
    expect(server.posts()).toHaveLength(0);
    expect(document.activeElement).toBe(
      screen.getByRole('combobox', { name: '2행 밸류체인' }),
    );
  });

  it('통과 → POST /runs 한 번(input@1 = 폼) · 누르는 동안 끔 · onStarted(runId) 한 번', async () => {
    const { server, onStarted } = setup();
    fillRequired();
    type('SASB 산업 설명', ' 가상 설명 ');
    paste('가\t나\t다운스트림\t라\t마');
    fireEvent.click(screen.getByRole('radio', { name: '금융' }));
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['POST /runs'] = async () => {
      await gate;
      return new Response(JSON.stringify({ id: 55, status: 'queued' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      });
    };
    await act(async () => {
      fireEvent.click(screen.getByTestId('start'));
      fireEvent.click(screen.getByTestId('start'));
    });
    expect(
      screen.getByTestId('start').hasAttribute('disabled') ||
        screen.getByTestId('start').getAttribute('aria-disabled') === 'true',
    ).toBe(true);
    expect(
      screen
        .getByRole('button', { name: words.cancel })
        .hasAttribute('disabled'),
    ).toBe(true);
    await act(async () => release());
    await act(async () => {});
    expect(server.posts()).toHaveLength(1);
    expect(onStarted).toHaveBeenCalledTimes(1);
    expect(onStarted).toHaveBeenCalledWith('55');
    const { options } = server.posts()[0]!.body as {
      options: { input: Record<string, unknown> };
    };
    expect(Object.keys(options)).toEqual(['input']);
    expect(options.input).toEqual({
      schemaVersion: 'materiality.input@1',
      company: { name: '가상물산' },
      industries: [
        {
          standard: 'SASB',
          industryName: '가상 산업',
          description: '가상 설명',
        },
      ],
      topics: [{ topic: '가상토픽 A', description: '' }],
      geoScope: '글로벌(대한민국 · 북미 · EU 우선)',
      userLocation: 'KR',
      mainLanguage: '한국어',
      dateRange: '2024-01-01~오늘까지',
      sector: 'financial',
      latestEventMode: false,
      subtopicsByTopic: {
        '가상토픽 A': [{ name: '가상 서브', description: '' }],
      },
      valueChain: [
        {
          business_unit: '가',
          business_unit_description: '나',
          value_chain_stage: 'downstream',
          stakeholder: '라',
          business_activity: '마',
        },
      ],
    });
  });

  it('거절(422)·끊김 → 판 글(서버 message 0) · 넣은 값 그대로 · 다시 누르면 같은 열쇠', async () => {
    const { server, onStarted } = setup();
    server.override['POST /runs'] = [
      () => refusal(422, 'VALIDATION_ERROR'),
      unreachable,
    ];
    fillRequired();
    await start();
    expect(screen.getByTestId('start-error').textContent).toBe(
      '평가를 시작하지 못했어요. 넣은 내용은 그대로 있으니 잠시 뒤 [평가 시작]을 다시 눌러 주세요.',
    );
    expect(document.body.textContent).not.toContain('지어낸-');
    expect((box('기업명') as HTMLInputElement).value).toBe('가상물산');
    await start();
    expect(screen.getByTestId('start-error')).toBeTruthy();
    await start();
    expect(onStarted).toHaveBeenCalledWith('55');
    const ik = server
      .posts()
      .map((post) => post.headers.get('Idempotency-Key'));
    expect(new Set(ik).size).toBe(1);
    expect(ik).toHaveLength(3);
  });

  it('[취소] → onCancel · 화면을 떠나면 열쇠를 버린다', () => {
    const { onCancel } = setup();
    fireEvent.click(screen.getByRole('button', { name: words.cancel }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(within(document.body).getByTestId('start')).toBeTruthy();
  });
});

describe('[양식 받기](IRW15 ①)', () => {
  const link = () => screen.getByTestId('value-chain-template');

  it('엑셀 올리기 탭 드롭 칸의 열 안내 줄 바로 아래 · 이름 「양식 받기」 · 정적 파일로 내려받음', () => {
    setup();
    const anchor = link() as HTMLAnchorElement;
    expect(anchor.tagName).toBe('A');
    expect(anchor.textContent).toBe(vc.template);
    expect(anchor.getAttribute('href')).toBe(
      `/templates/${encodeURIComponent(vc.templateFile)}`,
    );
    expect(anchor.getAttribute('download')).toBe('가치사슬_양식.xlsx');
    // 열 안내 줄과 같은 <p> 안, 안내 글 뒤
    const hint = anchor.closest('p')!;
    expect(hint.textContent!.startsWith(vc.dropHint)).toBe(true);
    expect(hint.closest('[role="button"]')).toBeTruthy();
  });

  it('누름·Enter·Space 가 드롭 칸의 파일 고르기를 열지 않는다(칸을 누르면 연다)', () => {
    setup();
    const picker = document.querySelector<HTMLInputElement>(
      '[data-testid="value-chain"] input[type="file"]',
    )!;
    const opened = vi.spyOn(picker, 'click');
    link().addEventListener('click', (event) => event.preventDefault());
    fireEvent.click(link());
    fireEvent.keyDown(link(), { key: 'Enter' });
    fireEvent.keyDown(link(), { key: ' ' });
    expect(opened).not.toHaveBeenCalled();
    fireEvent.click(link().closest('[role="button"]')!);
    expect(opened).toHaveBeenCalledTimes(1);
  });

  it('붙여 넣기·직접 입력 탭에는 0', () => {
    setup();
    fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabPaste }));
    expect(screen.queryByTestId('value-chain-template')).toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabManual }));
    expect(screen.queryByTestId('value-chain-template')).toBeNull();
    fireEvent.mouseDown(screen.getByRole('tab', { name: vc.tabFile }));
    expect(screen.getByTestId('value-chain-template')).toBeTruthy();
  });
});

describe('밸류체인 표기 더 받기(IRW15 ②)', () => {
  it('붙여 넣은 own_operations·Own Operation·UPSTREAM → 요청에는 정규 값', async () => {
    const { server } = setup();
    fillRequired();
    paste(
      [
        '가\t나\town_operations\t라\t마',
        '가\t나\tOwn Operation\t라\t바',
        '가\t나\tUPSTREAM\t라\t사',
        '가\t나\tdown-stream\t라\t아',
      ].join('\n'),
    );
    await start();
    const { options } = server.posts()[0]!.body as {
      options: { input: { valueChain: { value_chain_stage: string }[] } };
    };
    expect(
      options.input.valueChain.map((row) => row.value_chain_stage),
    ).toEqual(['own operations', 'own operations', 'upstream', 'downstream']);
  });

  it('올린 파일의 own-operations 도 같은 함수(서버 글 그대로 → 정규 값)', async () => {
    const { server } = setup({
      ok: true,
      rows: [
        {
          business_unit: '가',
          business_unit_description: '나',
          value_chain_stage: 'own-operations',
          stakeholder: '다',
          business_activity: '라',
        },
      ],
      rowCount: 1,
    });
    fillRequired();
    await upload(xlsx());
    expect(
      (
        screen.getByRole('combobox', {
          name: '1행 밸류체인',
        }) as HTMLSelectElement
      ).value,
    ).toBe('own operations');
    await start();
    const { options } = server.posts()[0]!.body as {
      options: { input: { valueChain: { value_chain_stage: string }[] } };
    };
    expect(options.input.valueChain[0]!.value_chain_stage).toBe(
      'own operations',
    );
  });
});

describe('IR-02 1차 댓글 글·자리(IRW17)', () => {
  it('dc1240f4 「주 검색 언어」 · 칸 아래 회색 「결과는 늘 한국어로 정리돼요」 · 값 그대로', () => {
    setup();
    const research = document.querySelector('[data-card="research"]')!;
    const select = within(research as HTMLElement).getByRole('combobox', {
      name: '주 검색 언어',
    });
    expect(select.textContent).toBe('한국어');
    expect(research.textContent).toContain('주 검색 언어');
    const hint = screen.getByTestId('language-hint');
    expect(hint.textContent).toBe('결과는 늘 한국어로 정리돼요');
    expect(hint.className).toMatch(/text-text-tertiary/);
    expect(hint.parentElement!.contains(select)).toBe(true);
    // 칸 이름 「검색 언어」 단독 0(「주 검색 언어」만)
    expect(
      [...document.querySelectorAll('label')].filter(
        (label) => label.textContent === '검색 언어',
      ),
    ).toEqual([]);
  });

  it('eb6298ea 업종 구분 · 설명 줄은 1. 카드 산업 분류(KSIC) 바로 아래 · 3. 카드에 0 · 값 그대로', () => {
    const onDirtyChange = vi.fn();
    setup(undefined, { onDirtyChange });
    const company = document.querySelector<HTMLElement>(
      '[data-card="company"]',
    )!;
    const research = document.querySelector<HTMLElement>(
      '[data-card="research"]',
    )!;
    expect(company.textContent).toContain('업종 구분');
    expect(company.textContent).toContain(
      '규제·정책을 찾을 신뢰 출처 목록이 달라요',
    );
    expect(research.textContent).not.toContain('업종 구분');
    expect(research.textContent).not.toContain('신뢰 출처 목록');
    // 자리: KSIC 산업명 칸 뒤 · 가치사슬 칸 앞
    const radio = within(company).getByRole('radio', { name: '비금융' });
    const ksic = within(company).getByRole('textbox', { name: 'KSIC 산업명' });
    const vcField = screen.getByTestId('value-chain');
    expect(
      ksic.compareDocumentPosition(radio) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(
      radio.compareDocumentPosition(vcField) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(radio.getAttribute('aria-checked')).toBe('true');
    expect(onDirtyChange).not.toHaveBeenCalledWith(true);
    fireEvent.click(within(company).getByRole('radio', { name: '금융' }));
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });
});

describe('떠나기 경고(IRW15 ④)', () => {
  it('빈 폼은 dirty 0 · 무엇이든 넣으면 true · 처음 꼴로 되돌리면 false', () => {
    const onDirtyChange = vi.fn();
    setup(undefined, { onDirtyChange });
    expect(onDirtyChange).not.toHaveBeenCalledWith(true);
    type('기업명', '가');
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    type('기업명', '');
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    fireEvent.click(screen.getByRole('radio', { name: '금융' }));
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });

  it('토픽 카드를 더하고 처음 카드를 빼면(key 만 다름) 처음 꼴 · 붙여 넣은 표는 dirty', () => {
    const onDirtyChange = vi.fn();
    setup(undefined, { onDirtyChange });
    fireEvent.click(screen.getByRole('button', { name: words.topics.add }));
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    // 앞 카드는 접혀 [토픽 빼기]가 없다 — 펼친 뒤 처음 카드(첫 [토픽 빼기])를 뺀다. 남는 것은 새 카드(key 만 다른 빈 카드).
    fireEvent.click(
      screen.getByRole('button', { name: words.topics.expand('') }),
    );
    const removes = screen.getAllByRole('button', {
      name: words.topics.remove,
    });
    expect(removes).toHaveLength(2);
    fireEvent.click(removes[0]!);
    expect(screen.getAllByTestId('topic-card')).toHaveLength(1);
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    paste('가\t나\t업스트림\t라\t마');
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });

  it('시작 요청을 기다리는 동안 false(막지 않음) · 실패하면 다시 true', async () => {
    const onDirtyChange = vi.fn();
    const { server } = setup(undefined, { onDirtyChange });
    fillRequired();
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['POST /runs'] = async () => {
      await gate;
      return new Response('{}', { status: 503 });
    };
    await act(async () => {
      fireEvent.click(screen.getByTestId('start'));
    });
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    await act(async () => release());
    await act(async () => {});
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });

  it('IRW17 빈틈: 표로 안 읽히는 붙여 넣기 글만 → true · 글을 비우면 false', () => {
    const onDirtyChange = vi.fn();
    setup(undefined, { onDirtyChange });
    paste('가상 글 한 줄');
    // 표로 안 읽혀 행 0(draft 그대로) — 글 칸은 남는다
    expect((box(vc.pasteLabel) as HTMLTextAreaElement).value).toBe(
      '가상 글 한 줄',
    );
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    fireEvent.change(box(vc.pasteLabel), { target: { value: '' } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it('IRW17 빈틈: 실패 파일 줄만 → true', async () => {
    const onDirtyChange = vi.fn();
    setup(valueChainRejected('bad_header'), { onDirtyChange });
    expect(onDirtyChange).not.toHaveBeenCalledWith(true);
    await upload(xlsx('표.xlsx'));
    expect(screen.getByTestId('file-line-failed')).toBeTruthy();
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });

  it('IRW17 빈틈: 아무것도 없음 → false 만 · 시작 중이면 붙여 넣기 글이 있어도 false', async () => {
    const onDirtyChange = vi.fn();
    const { server } = setup(undefined, { onDirtyChange });
    expect(onDirtyChange).not.toHaveBeenCalledWith(true);
    fillRequired();
    paste('가상 글 한 줄');
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    let release!: () => void;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.override['POST /runs'] = async () => {
      await gate;
      return new Response('{}', { status: 503 });
    };
    await act(async () => {
      fireEvent.click(screen.getByTestId('start'));
    });
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
    await act(async () => release());
    await act(async () => {});
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });

  it('leave.pending → 나가기 창(글 넷) · [계속 입력] reset · [나가기] proceed', () => {
    const leave = { pending: true, proceed: vi.fn(), reset: vi.fn() };
    setup(undefined, { leave });
    const dialog = screen.getByTestId('leave-dialog');
    expect(within(dialog).getByText(words.leave.title)).toBeTruthy();
    expect(
      within(dialog).getByText('나가면 넣은 내용이 사라져요'),
    ).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: '계속 입력' }));
    expect(leave.reset).toHaveBeenCalledTimes(1);
    fireEvent.click(within(dialog).getByRole('button', { name: '나가기' }));
    expect(leave.proceed).toHaveBeenCalledTimes(1);
  });

  it('leave 가 없거나 pending false 면 창 0', () => {
    setup(undefined, {
      leave: { pending: false, proceed: vi.fn(), reset: vi.fn() },
    });
    expect(screen.queryByTestId('leave-dialog')).toBeNull();
  });
});
