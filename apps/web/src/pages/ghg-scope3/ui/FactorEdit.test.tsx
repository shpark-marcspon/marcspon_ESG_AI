// @vitest-environment jsdom
// 그룹별 배출계수 창의 계수 수정(밴드 S3W3c2 ① — 발주서 §3 화면 ①~㉓). ResultView 를 바로 그린다(reread 가 진짜 길로 돈다). 값은 지어낸 것.
//   쓰기 답 표 열 칸(두 창·한 줄·reread 수) · failed 두 갈래 · 얼린 seen · 사진 · current.runId · 답 전 내려감 · 막힘 차례 · 권한 · 라디오 처음 고름 ·
//   필수 글 · 배열 자리 순위 · C5 · 초점 · 사유 간직 · columns · 같은 고름 · 제외 줄 · 지수 꼴 · 출처만 바꿈 · 히스토리 바뀐 값.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it } from 'vitest';

import {
  FAKE_EDITED_CO2E,
  activityRow,
  energyRow,
  fakeDoneResult,
  fakeRowFactor,
  fakeScope3Server,
  portOf,
  processedSheet,
  purchaseRow,
  refusal,
  unreachable,
} from '../../../entities/ghg-scope3/api/testing.ts';
import type { FakeRowEdit } from '../../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { ResultView } from './ResultView.tsx';

// 키트 radio-group(Radix)은 단추 크기를 ResizeObserver 로 잰다. jsdom 에는 없어서 아무것도 하지 않는 것을 둔다(review.test.tsx 꼴).
beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    Object.defineProperty(globalThis, 'ResizeObserver', {
      configurable: true,
      value: class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    });
});
afterEach(cleanup);

const fe = S3_TEXT.detail.factorEdit;
const w = S3_TEXT.rowEdit;
const YEAR = 'GET /inventory/scope3/years/2025';
const SHEET = 'c1_지어낸';
const id = (n: number) => `${SHEET}!${n + 2}`;
const factorPath = (run: number, c = 'C1') =>
  `/inventory/scope3/runs/${run}/categories/${c}/factors`;
const POST9 = `POST ${factorPath(9)}`;
type J = Record<string, unknown>;
const c1Body = (rows: J[] = [0, 1, 2].map((n) => purchaseRow('1', id(n)))) =>
  fakeDoneResult({ sheets: [processedSheet(SHEET, 'Category1', rows)] });
const done = (run: number, result: unknown, edits?: FakeRowEdit[]) => ({
  id: run,
  status: 'done' as const,
  reportYear: 2025,
  result: result as Record<string, unknown>,
  ...(edits ? { edits } : {}),
});
type Server = ReturnType<typeof fakeScope3Server>;
const draw = (server: Server, { runId = '9', operator = false } = {}) =>
  render(
    <ResultView
      port={portOf(server)}
      runId={runId}
      year={2025}
      operator={operator}
      onUpload={() => {}}
    />,
  );
const cardOf = (category: string) =>
  screen
    .getAllByTestId('s3-result-card')
    .find((card) => card.getAttribute('data-category') === category)!;
const openDetail = async (category = 'C1') => {
  await screen.findByTestId('s3-result');
  fireEvent.click(within(cardOf(category)).getByRole('button'));
  return screen.findByTestId('s3-detail');
};
const start = async (
  options: Parameters<typeof fakeScope3Server>[0] = {
    runs: [done(9, c1Body())],
  },
  drawn: Parameters<typeof draw>[1] = {},
  category = 'C1',
) => {
  const server = fakeScope3Server(options);
  draw(server, drawn);
  await openDetail(category);
  return server;
};
const openers = () => screen.getAllByTestId('s3-window-open');
const windowBox = () => screen.queryByTestId('s3-factor-window');
const openWindow = async (n = 0) => {
  fireEvent.click(openers()[n]!);
  return screen.findByTestId('s3-factor-window');
};
const editButton = () =>
  screen.getByTestId('s3-factor-edit') as HTMLButtonElement;
const startEdit = async (n = 0) => {
  await openWindow(n);
  fireEvent.click(editButton());
  await waitFor(() =>
    expect(windowBox()!.getAttribute('data-mode')).toBe('edit'),
  );
};
const radio = (testId: string, n = 0) =>
  screen.getAllByTestId(testId)[n] as HTMLButtonElement;
const checked = (one: HTMLElement) => one.getAttribute('data-state');
const pickRank = (n: number) =>
  fireEvent.click(radio('s3-factor-pick-rank', n));
const pickCustom = () => fireEvent.click(radio('s3-factor-pick-custom'));
const pickApplied = () => fireEvent.click(radio('s3-factor-pick-applied'));
const field = (name: 'title' | 'value' | 'source') =>
  screen.getByTestId(`s3-factor-${name}`) as HTMLInputElement;
const type = (name: 'title' | 'value' | 'source', value: string) =>
  fireEvent.change(field(name), { target: { value } });
const fillCustom = (
  title = '지어낸 제목',
  value = '0.5',
  source = '지어낸 출처',
) => {
  pickCustom();
  type('title', title);
  type('value', value);
  type('source', source);
};
const pressSave = () => fireEvent.click(screen.getByTestId('s3-factor-save'));
const reasonBox = () => screen.queryByTestId('s3-reason');
const reasonInput = () =>
  screen.getByTestId('s3-reason-input') as HTMLInputElement;
const typeReason = (text: string) =>
  fireEvent.change(reasonInput(), { target: { value: text } });
const pressConfirm = () =>
  fireEvent.click(
    within(screen.getByTestId('s3-reason')).getByRole('button', {
      name: w.reason.confirm,
    }),
  );
/** [수정] → 고름 → [저장] → 사유 → [확인]. */
const write = async (choose: () => void, reason = '지어낸 사유', n = 0) => {
  await startEdit(n);
  choose();
  pressSave();
  await screen.findByTestId('s3-reason');
  typeReason(reason);
  pressConfirm();
};
const noticeText = () => screen.queryByTestId('s3-factor-notice')?.textContent;
const settled = () => new Promise((resolve) => setTimeout(resolve, 20));
const totalText = () => screen.getByTestId('s3-detail-total').textContent;
const rowCo2e = (n: number) =>
  within(screen.getAllByTestId('s3-row')[n]!)
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
    .join('|');

describe('보기 꼴 · 수정 꼴', () => {
  it('제목 줄 오른쪽 [수정] · 누르면 [취소][저장] · 적용·추천·직접입력 섹션 · 라디오 처음은 적용(⑪)', async () => {
    await start();
    await openWindow();
    expect(editButton().textContent).toBe(fe.edit);
    expect(editButton().disabled).toBe(false);
    fireEvent.click(editButton());
    const box = windowBox()!;
    expect(within(box).getByTestId('s3-factor-cancel').textContent).toBe(
      fe.cancel,
    );
    expect(within(box).getByTestId('s3-factor-save').textContent).toBe(fe.save);
    expect(within(box).queryByTestId('s3-factor-edit')).toBeNull();
    expect(within(box).getByTestId('s3-factor-applied')).toBeTruthy();
    expect(within(box).getAllByTestId('s3-factor-recommendation')).toHaveLength(
      2,
    );
    expect(within(box).getByTestId('s3-factor-custom')).toBeTruthy();
    expect(within(box).queryByTestId('s3-window-factor')).toBeNull();
    expect(checked(radio('s3-factor-pick-applied'))).toBe('checked');
    expect(within(box).getAllByRole('radio')).toHaveLength(4);
    // 단위 입력 칸 0 — 칸 셋.
    expect(within(box).getAllByRole('textbox')).toHaveLength(3);
    expect(field('title').placeholder).toBe(fe.placeholders.title);
  });

  it('[취소] — 쓴 것 버리고 보기 꼴 · 요청 0 · 다시 [수정]은 처음 고름', async () => {
    const server = await start();
    await startEdit();
    fillCustom();
    fireEvent.click(screen.getByTestId('s3-factor-cancel'));
    expect(windowBox()!.getAttribute('data-mode')).toBe('view');
    fireEvent.click(editButton());
    expect(checked(radio('s3-factor-pick-applied'))).toBe('checked');
    expect(field('title').value).toBe('');
    expect(server.count(POST9)).toBe(0);
  });

  it('적용 칸은 AI 원안 — 고친 줄도 본문 계수(C1) · 라디오는 지금 고름(직접입력에 값 채움)', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          {
            rowId: id(0),
            category: 'C1',
            factor: fakeRowFactor({ value: '0.75', title: '지어낸 고친 계수' }),
          },
        ]),
      ],
    });
    await startEdit();
    const applied = screen.getByTestId('s3-factor-applied');
    expect(applied.textContent).toContain('지어낸 항목');
    expect(applied.textContent).toContain('0.1');
    expect(applied.textContent).not.toContain('0.75');
    expect(checked(radio('s3-factor-pick-custom'))).toBe('checked');
    expect(field('title').value).toBe('지어낸 고친 계수');
    expect(field('value').value).toBe('0.75');
  });

  it('추천 고른 줄은 그 순위가 처음 고름', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          {
            rowId: id(0),
            category: 'C1',
            factor: fakeRowFactor({ choice: 'recommended', rank: 2 }),
          },
        ]),
      ],
    });
    await startEdit();
    expect(checked(radio('s3-factor-pick-rank', 1))).toBe('checked');
    expect(checked(radio('s3-factor-pick-applied'))).toBe('unchecked');
  });
});

describe('쓰기 답 표 열 칸', () => {
  it('ok: 두 창 닫힘 · 표 위 status · 다시 읽어 표·카드 합이 서버 값 · 초점 [목록](칸이 다시 달림)', async () => {
    const server = await start();
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    await waitFor(() => expect(windowBox()).toBeNull());
    expect(reasonBox()).toBeNull();
    expect(server.bodies(POST9)).toEqual([
      {
        rowId: id(0),
        choice: 'recommended',
        rank: 1,
        custom: null,
        reason: '지어낸 사유',
      },
    ]);
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    expect(screen.getByTestId('s3-factor-notice').getAttribute('role')).toBe(
      'status',
    );
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    await waitFor(() => expect(totalText()).toContain('9.25'));
    expect(rowCo2e(0)).toContain(FAKE_EDITED_CO2E);
    await settled();
    expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back'));
  });

  it('ok 뒤 합이 그대로면 칸 단추가 살아 있어 초점은 그 단추(C4)', async () => {
    const server = await start({
      runs: [
        done(
          9,
          c1Body([
            purchaseRow(FAKE_EDITED_CO2E, id(0)),
            purchaseRow('1', id(1)),
          ]),
        ),
      ],
    });
    const button = openers()[0]!;
    await write(() => pickRank(0));
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    await settled();
    await settled();
    expect(button.isConnected).toBe(true);
    expect(document.activeElement).toBe(button);
  });

  const closing = [
    ['LOCKED', () => refusal(409, 'LOCKED'), w.locked],
    ['STALE_RUN', () => refusal(409, 'STALE_RUN'), w.stale],
    [
      'VALIDATION_ERROR rowId(단수)',
      () => refusal(422, 'VALIDATION_ERROR', { rowId: ['지어낸'] }),
      w.stale,
    ],
    [
      'VALIDATION_ERROR rank',
      () => refusal(422, 'VALIDATION_ERROR', { rank: ['지어낸'] }),
      w.stale,
    ],
  ] as const;
  it.each(closing)(
    '%s: 두 창 닫힘 · 표 위 alert · 다시 읽음 · 초점은 누른 칸',
    async (_, answer, text) => {
      const server = await start();
      server.override[POST9] = [answer];
      const reads = server.count(YEAR);
      await write(() => pickRank(0));
      await waitFor(() => expect(windowBox()).toBeNull());
      expect(reasonBox()).toBeNull();
      await waitFor(() => expect(noticeText()).toBe(text));
      expect(screen.getByTestId('s3-factor-notice').getAttribute('role')).toBe(
        'alert',
      );
      await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
      await settled();
      // 합이 그대로라 칸이 다시 달리지 않는다 — 누른 칸 단추가 살아 있다(R4: 하나로 좁힘).
      expect(document.activeElement).toBe(openers()[0]);
    },
  );

  it('VALIDATION_ERROR reason: 두 창 둠 · 칸 아래 글 · 다시 읽기 0', async () => {
    const server = await start();
    server.override[POST9] = [
      () => refusal(422, 'VALIDATION_ERROR', { reason: ['지어낸'] }),
    ];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    expect(
      (await screen.findByTestId('s3-reason-input-error')).textContent,
    ).toBe(w.reason.rejected);
    await settled();
    expect(reasonBox()).not.toBeNull();
    expect(windowBox()!.getAttribute('data-mode')).toBe('edit');
    expect(server.count(YEAR)).toBe(reads);
  });

  it.each([
    ['custom.value', 'value', fe.notPositive],
    ['custom.title', 'title', fe.tooLong],
    ['custom.source', 'source', fe.tooLong],
  ] as const)(
    '%s: 사유 창 닫음 · 쓴 사유 간직(⑯) · 수정 꼴 둠 · 그 칸 아래 글 · 다시 읽기 0',
    async (key, name, text) => {
      const server = await start();
      server.override[POST9] = [
        () => refusal(422, 'VALIDATION_ERROR', { [key]: ['지어낸'] }),
      ];
      const reads = server.count(YEAR);
      await write(() => fillCustom(), '지어낸 긴 사유');
      await waitFor(() => expect(reasonBox()).toBeNull());
      expect(windowBox()!.getAttribute('data-mode')).toBe('edit');
      expect(screen.getByTestId(`s3-factor-${name}-error`).textContent).toBe(
        text,
      );
      expect(server.count(YEAR)).toBe(reads);
      await settled();
      expect(document.activeElement).toBe(field(name));
      pressSave();
      await screen.findByTestId('s3-reason');
      expect(reasonInput().value).toBe('지어낸 긴 사유');
    },
  );

  it('FACTOR_NOT_EDITABLE: 사유 창 닫고 사유 버림 · 보기 꼴 · 창 머리 아래 alert · 그 창이 열린 동안 [수정] 막음(C9) · 다시 읽기 0', async () => {
    const server = await start();
    server.override[POST9] = [() => refusal(409, 'FACTOR_NOT_EDITABLE')];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    await waitFor(() => expect(reasonBox()).toBeNull());
    const box = windowBox()!;
    expect(box.getAttribute('data-mode')).toBe('view');
    const alert = within(box).getByTestId('s3-factor-not-editable');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toBe(fe.rowNotEditable);
    expect(editButton().disabled).toBe(true);
    expect(server.count(YEAR)).toBe(reads);
    expect(noticeText()).toBeUndefined();
    // 창을 다시 열면 풀린다(서버가 또 409 를 낼 일이지만 웹은 미리 모른다 — 값 파일 ③).
    fireEvent.keyDown(box, { key: 'Escape' });
    await waitFor(() => expect(windowBox()).toBeNull());
    await openWindow();
    expect(editButton().disabled).toBe(false);
  });

  it('그 밖 거절(404): 두 창 둠 · 쓴 사유 유지 · 창 안 글 · 다시 읽기 0', async () => {
    const server = await start();
    server.override[POST9] = [() => refusal(404, 'NOT_FOUND')];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    expect((await screen.findByTestId('s3-reason-failed')).textContent).toBe(
      w.failed,
    );
    await settled();
    expect(reasonInput().value).toBe('지어낸 사유');
    expect(windowBox()).not.toBeNull();
    expect(server.count(YEAR)).toBe(reads);
  });

  it('refused: 두 창 닫힘 · 회사 글 · 다시 읽기 0', async () => {
    const server = await start();
    server.override[POST9] = [() => refusal(400, 'COMPANY_AMBIGUOUS')];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    await waitFor(() => expect(windowBox()).toBeNull());
    expect(reasonBox()).toBeNull();
    expect(noticeText()).toBe(S3_TEXT.company.ambiguous);
    await settled();
    expect(server.count(YEAR)).toBe(reads);
  });

  it('failed — 안 들어감: 두 창 둠 · 쓴 사유 유지 · 창 안 글 · 다시 읽음 · [확인]이 같은 몸(③)', async () => {
    const server = await start();
    server.override[POST9] = [unreachable];
    const reads = server.count(YEAR);
    await write(() => pickRank(1));
    expect((await screen.findByTestId('s3-reason-failed')).textContent).toBe(
      w.failed,
    );
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    expect(reasonInput().value).toBe('지어낸 사유');
    expect(windowBox()!.getAttribute('data-mode')).toBe('edit');
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    const [first, second] = server.bodies(POST9);
    expect(second).toEqual(first);
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
  });

  it('failed — 들어간 뒤 끊김: 표는 서버 값 · 창은 사진 그대로 · 다시 [확인]은 사건 0 으로 ok', async () => {
    const server = await start();
    const body = {
      rowId: id(0),
      choice: 'recommended',
      rank: 1,
      custom: null,
      reason: '지어낸 사유',
    };
    server.override[POST9] = [
      async () => {
        await server.send(
          new Request(`http://test.local/api${factorPath(9)}`, {
            method: 'POST',
            body: JSON.stringify(body),
          }),
        );
        return unreachable();
      },
    ];
    await write(() => pickRank(0));
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() => expect(totalText()).toContain('9.25'));
    // 창은 연 때 사진 — 적용 칸·고름이 그대로다.
    expect(checked(radio('s3-factor-pick-rank', 0))).toBe('checked');
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    const history = await server.send(
      new Request(
        `http://test.local/api/inventory/scope3/runs/9/history?rowId=${encodeURIComponent(id(0))}`,
      ),
    );
    expect(((await history.json()) as { count: number }).count).toBe(1);
  });
});

describe('얼린 seen · 사진 · 쓰는 실행', () => {
  const later = (title = '지어낸 새 항목') => ({
    ...done(
      11,
      c1Body(
        [0, 1, 2].map((n) =>
          purchaseRow('10', id(n), {
            factor: {
              title,
              value: '0.1',
              unit: 'kgCO2e/KRW',
              column: '2024',
              source: 'db_keyword',
            },
          }),
        ),
      ),
    ),
    status: 'processing' as const,
    script: ['processing', 'done'] as ('processing' | 'done')[],
  });

  it('창이 열린 사이 새 실행이 지금 결과가 되어도 본 실행으로 보내 stale_run 이 일한다 · 창은 사진 그대로(④⑤)', async () => {
    const server = await start({ runs: [done(9, c1Body()), later()] });
    server.override[POST9] = [unreachable];
    await write(() => pickRank(0));
    await server.send(new Request('http://test.local/api/runs/11'));
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() => expect(totalText()).toContain('30'));
    // 사진은 rowId 로 갈아 끼우지 않는다 — 같은 rowId 의 새 줄 제목이 창에 없다.
    expect(windowBox()!.textContent).toContain('지어낸 항목');
    expect(windowBox()!.textContent).not.toContain('지어낸 새 항목');
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(server.count(POST9)).toBe(2);
    expect(server.count(`POST ${factorPath(11)}`)).toBe(0);
    await waitFor(() => expect(noticeText()).toBe(w.stale));
  });

  it('실행이 바뀐 뒤 [저장]을 다시 눌러도 연 때 seen 으로 보낸다(누른 때 읽지 않음)', async () => {
    const server = await start({ runs: [done(9, c1Body()), later()] });
    server.override[POST9] = [unreachable];
    await write(() => pickRank(0));
    await server.send(new Request('http://test.local/api/runs/11'));
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() => expect(totalText()).toContain('30'));
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    fireEvent.keyDown(reasonInput(), { key: 'Escape' });
    await waitFor(() => expect(reasonBox()).toBeNull());
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(2));
    expect(server.count(`POST ${factorPath(11)}`)).toBe(0);
    await waitFor(() => expect(noticeText()).toBe(w.stale));
  });

  it('화면 prop 의 실행이 아니라 그 카테고리 지금 결과 실행으로 보낸다(⑥)', async () => {
    const server = await start(
      { runs: [done(7, c1Body()), done(9, c1Body())] },
      { runId: '7' },
    );
    await write(() => pickRank(0));
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect(server.count(`POST ${factorPath(7)}`)).toBe(0);
  });

  it('답 전에 [목록]으로 나가도 다시 읽는다(⑦)', async () => {
    const server = await start();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[POST9] = [
      async () => {
        await gate;
        return refusal(409, 'STALE_RUN');
      },
    ];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    // 창 둘이 떠 있어 [목록]은 화면 밖 — 상세가 내려가는 길(카드 바뀜)을 흉내 내려 cleanup 대신 다시 그리지 않고 직접 누른다.
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    release();
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
  });
});

describe('막힘 차례(⑧)', () => {
  it('보기 꼴로 열린 사이 잠기면 [수정]이 꺼진다 — 잠김은 연 때 얼리지 않고 지금 값(검증 X3)', async () => {
    await start({ runs: [done(9, c1Body())] }, { operator: true });
    await openWindow();
    expect(editButton().disabled).toBe(false);
    fireEvent.click(screen.getByTestId('s3-lock'));
    await waitFor(() =>
      expect(screen.getByTestId('s3-lock').getAttribute('data-locked')).toBe(
        'true',
      ),
    );
    await waitFor(() => expect(editButton().disabled).toBe(true));
    expect(screen.getByTestId('s3-factor-locked')).toBeTruthy();
  });

  it('잠김: [수정] 막힘 · 툴팁 자리 span 이 초점을 받는다 · 수정 꼴에 들어간 뒤 잠기면 [저장]은 둔다', async () => {
    await start({
      runs: [done(9, c1Body())],
      locks: [{ year: 2025, category: 'C1', runId: 9 }],
    });
    await openWindow();
    expect(editButton().disabled).toBe(true);
    const tip = screen.getByTestId('s3-factor-locked');
    expect(tip.getAttribute('tabindex')).toBe('0');
    expect(screen.queryByTestId('s3-factor-blocked')).toBeNull();
  });

  it('수정 꼴에 들어간 뒤 잠기면 [저장]은 켜져 있고 서버 locked 가 일한다', async () => {
    const server = await start(
      { runs: [done(9, c1Body())] },
      { operator: true },
    );
    await startEdit();
    // 다른 길로 잠근다(서버 직접).
    await server.send(
      new Request(
        'http://test.local/api/inventory/scope3/years/2025/categories/C1/lock?runId=9',
        { method: 'POST' },
      ),
    );
    pickRank(0);
    expect(
      (screen.getByTestId('s3-factor-save') as HTMLButtonElement).disabled,
    ).toBe(false);
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(noticeText()).toBe(w.locked));
  });

  const c12Body = (rows: J[]) =>
    fakeDoneResult({
      sheets: [processedSheet('c12_지어낸', 'Category12', rows)],
    });

  it('C12: 창 열림 · [수정] 막힘 · 왼쪽 글 · 잠기면 툴팁만(하나만)', async () => {
    await start(
      {
        runs: [
          done(
            9,
            c12Body([energyRow('product_eol', '1', '0.5', 'c12_지어낸!2')]),
          ),
        ],
      },
      {},
      'C12',
    );
    await openWindow();
    expect(editButton().disabled).toBe(true);
    expect(screen.getByTestId('s3-factor-blocked').textContent).toBe(fe.c12);
    cleanup();
    await start(
      {
        runs: [
          done(
            9,
            c12Body([energyRow('product_eol', '1', '0.5', 'c12_지어낸!2')]),
          ),
        ],
        locks: [{ year: 2025, category: 'C12', runId: 9 }],
      },
      {},
      'C12',
    );
    await openWindow();
    expect(screen.getByTestId('s3-factor-locked')).toBeTruthy();
    expect(screen.queryByTestId('s3-factor-blocked')).toBeNull();
  });

  it('C12 줄도 제외·복구는 그대로(⑩)', async () => {
    await start(
      {
        runs: [
          done(
            9,
            c12Body([energyRow('product_eol', '1', '0.5', 'c12_지어낸!2')]),
          ),
        ],
      },
      {},
      'C12',
    );
    fireEvent.click(screen.getAllByTestId('s3-pick-row')[0]!);
    expect(
      (screen.getByTestId('s3-exclude') as HTMLButtonElement).disabled,
    ).toBe(false);
  });

  it('계수 없는 줄(C8): [수정] 막힘 · 왼쪽 「이 줄은…」', async () => {
    const sheet = 'c8-1_지어낸';
    await start(
      {
        runs: [
          done(
            9,
            fakeDoneResult({
              sheets: [
                processedSheet(sheet, 'Category8', [
                  energyRow('leased_asset', '1', undefined, `${sheet}!2`, {
                    factor: null,
                  }),
                ]),
              ],
            }),
          ),
        ],
      },
      {},
      'C8',
    );
    await openWindow();
    expect(editButton().disabled).toBe(true);
    expect(screen.getByTestId('s3-factor-blocked').textContent).toBe(
      fe.rowNotEditable,
    );
  });

  it('rowId 없는 줄: [수정] 막힘(글 없음)', async () => {
    await start({
      runs: [
        done(
          9,
          c1Body([
            purchaseRow('1', id(0), { rowId: null }),
            purchaseRow('1', id(1)),
          ]),
        ),
      ],
    });
    // rowId 없는 줄은 행 차례 맨 뒤(sortRows).
    await openWindow(1);
    expect(editButton().disabled).toBe(true);
    expect(screen.queryByTestId('s3-factor-blocked')).toBeNull();
  });
});

describe('권한 · 제외 줄', () => {
  it.each([true, false])(
    '운영 관리자 %s 도 [수정] 켜짐 · 「관리자만」 글 0(⑨)',
    async (operator) => {
      await start({ runs: [done(9, c1Body())] }, { operator });
      await openWindow();
      expect(editButton().disabled).toBe(false);
      expect(screen.queryByText(/관리자만/)).toBeNull();
    },
  );

  it('제외 줄도 [수정] 켬(⑳ · C13)', async () => {
    await start({
      runs: [
        done(9, c1Body(), [{ rowId: id(0), category: 'C1', excluded: true }]),
      ],
    });
    await openWindow();
    expect(editButton().disabled).toBe(false);
  });
});

describe('직접입력 검사 · 순위 · C5', () => {
  it('칸에 쓴 뒤 다른 라디오를 누르면 그 고름 · 칸 검사 0 · 칸 값은 두되 몸에 0(⑫ — R3 갈음)', async () => {
    const server = await start();
    await startEdit();
    type('value', '지어낸 틀린 값');
    pickRank(0);
    expect(field('value').value).toBe('지어낸 틀린 값');
    pressSave();
    expect(await screen.findByTestId('s3-reason')).toBeTruthy();
    expect(screen.queryByTestId('s3-factor-value-error')).toBeNull();
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect(server.bodies(POST9)[0]).toMatchObject({
      choice: 'recommended',
      rank: 1,
      custom: null,
    });
  });

  it('직접입력 빈 칸 셋 — 필수 글 · 첫 칸에 초점 · 사유 창 0', async () => {
    const server = await start();
    await startEdit();
    pickCustom();
    pressSave();
    for (const name of ['title', 'value', 'source'] as const) {
      expect(screen.getByTestId(`s3-factor-${name}-error`).textContent).toBe(
        fe.required,
      );
      expect(field(name).getAttribute('aria-invalid')).toBe('true');
    }
    expect(document.activeElement).toBe(field('title'));
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
    // 고치면 그 칸 글만 걷힌다.
    type('title', '지어낸');
    expect(screen.queryByTestId('s3-factor-title-error')).toBeNull();
    expect(screen.getByTestId('s3-factor-value-error')).toBeTruthy();
  });

  it.each([
    ['0', fe.notPositive],
    ['1e3', fe.notPositive],
    ['1.00000000001', fe.decimals],
  ])('값 %s → 글 · 초점은 값 칸', async (value, text) => {
    await start();
    await startEdit();
    fillCustom('지어낸', value, '지어낸');
    pressSave();
    expect(screen.getByTestId('s3-factor-value-error').textContent).toBe(text);
    expect(document.activeElement).toBe(field('value'));
    expect(reasonBox()).toBeNull();
  });

  it('제목 201 코드 포인트 → 200자 글 · 200 은 받고 보낸 제목·출처는 걷는다', async () => {
    const server = await start();
    await startEdit();
    fillCustom('가'.repeat(201), '0.5', '지어낸');
    pressSave();
    expect(screen.getByTestId('s3-factor-title-error').textContent).toBe(
      fe.tooLong,
    );
    type('title', ` ${'가'.repeat(200)} `);
    type('source', '  지어낸 출처  ');
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect(server.bodies(POST9)[0]).toEqual({
      rowId: id(0),
      choice: 'custom',
      rank: null,
      custom: { title: '가'.repeat(200), value: '0.5', source: '지어낸 출처' },
      reason: '지어낸 사유',
    });
  });

  it('rank 는 배열 자리 — 앞 추천 값 null 이면 그 라디오만 막고 뒤는 2순위(⑬)', async () => {
    const server = await start({
      runs: [
        done(
          9,
          c1Body([
            purchaseRow('1', id(0), {
              recommendations: [
                { title: '지어낸 빈 추천', value: null, expectedCo2e: null },
                { title: '지어낸 둘째', value: '0.4', expectedCo2e: '0.6' },
              ],
            }),
          ]),
        ),
      ],
    });
    await startEdit();
    expect(radio('s3-factor-pick-rank', 0).disabled).toBe(true);
    expect(radio('s3-factor-pick-rank', 1).disabled).toBe(false);
    pickRank(1);
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect((server.bodies(POST9)[0] as J).rank).toBe(2);
  });

  it('C5: 추천 섹션 0 · FCF 입력 0 · 탄소기원 섹션은 읽기 글로 둠(⑭ · C2)', async () => {
    const sheet = 'c5_지어낸';
    await start(
      {
        runs: [
          done(
            9,
            fakeDoneResult({
              sheets: [
                processedSheet(sheet, 'Category5', [
                  activityRow('waste', '2', '0.5', `${sheet}!2`),
                ]),
              ],
            }),
          ),
        ],
      },
      {},
      'C5',
    );
    await startEdit();
    const box = windowBox()!;
    expect(within(box).queryByTestId('s3-factor-recommended')).toBeNull();
    const carbon = within(box).getByTestId('s3-window-carbon');
    expect(within(carbon).queryByRole('textbox')).toBeNull();
    expect(within(box).getAllByRole('textbox')).toHaveLength(3);
    expect(within(box).getAllByRole('radio')).toHaveLength(2);
  });
});

describe('초점 · columns', () => {
  it('[취소] 뒤 Esc 로 닫으면 초점은 누른 칸 단추(⑮)', async () => {
    await start();
    const button = openers()[0]!;
    await startEdit();
    fireEvent.click(screen.getByTestId('s3-factor-cancel'));
    fireEvent.keyDown(windowBox()!, { key: 'Escape' });
    await waitFor(() => expect(windowBox()).toBeNull());
    await settled();
    expect(document.activeElement).toBe(button);
  });

  it('사유 창 Esc 는 사유 창만 닫는다 · 초점은 [저장]', async () => {
    await start();
    await startEdit();
    pickRank(0);
    pressSave();
    await screen.findByTestId('s3-reason');
    await settled();
    fireEvent.keyDown(reasonInput(), { key: 'Escape' });
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(windowBox()).not.toBeNull();
    await settled();
    expect(document.activeElement).toBe(screen.getByTestId('s3-factor-save'));
  });

  it('고름·창 상태가 표 칸을 다시 달지 않는다(⑰)', async () => {
    await start();
    const button = openers()[0]!;
    await startEdit();
    pickRank(1);
    fillCustom();
    pickApplied();
    expect(button.isConnected).toBe(true);
    expect(openers()[0]).toBe(button);
  });
});

describe('같은 고름 · 지수 꼴 · 출처만', () => {
  it('바꾸지 않고 [저장] — 요청 0 · 사유 창 없이 보기 꼴(⑲ · C10)', async () => {
    const server = await start();
    await startEdit();
    pressSave();
    expect(reasonBox()).toBeNull();
    expect(windowBox()!.getAttribute('data-mode')).toBe('view');
    expect(server.count(POST9)).toBe(0);
  });

  it('추천 고른 줄에 같은 순위로 [저장] — 요청 0', async () => {
    const server = await start({
      runs: [
        done(9, c1Body(), [
          {
            rowId: id(0),
            category: 'C1',
            factor: fakeRowFactor({ choice: 'recommended', rank: 1 }),
          },
        ]),
      ],
    });
    await startEdit();
    pressSave();
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
  });

  const tiny = () =>
    done(9, c1Body(), [
      {
        rowId: id(0),
        category: 'C1',
        factor: fakeRowFactor({
          value: '1e-05',
          title: '지어낸 작은 계수',
          source: '지어낸 출처',
        }),
      },
    ]);

  it('「1e-05」 줄 — 십진 글자로 채움 · 그대로 [저장]은 요청 0 · 제목만 바꾸면 POST 1 · 값은 십진 글자(㉑)', async () => {
    const server = await start({ runs: [tiny()] });
    await startEdit();
    expect(field('value').value).toBe('0.00001');
    pressSave();
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
    fireEvent.click(editButton());
    type('title', '지어낸 딴 제목');
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect((server.bodies(POST9)[0] as J).custom).toEqual({
      title: '지어낸 딴 제목',
      value: '0.00001',
      source: '지어낸 출처',
    });
  });

  it('출처만 바꿈 — POST 1 · 히스토리 둘(㉒ · V4)', async () => {
    const server = await start({ runs: [tiny()] });
    await startEdit();
    type('source', '지어낸 딴 출처');
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    expect(server.count(POST9)).toBe(1);
    const history = await server.send(
      new Request(
        `http://test.local/api/inventory/scope3/runs/9/history?rowId=${encodeURIComponent(id(0))}`,
      ),
    );
    expect(((await history.json()) as { count: number }).count).toBe(2);
  });

  it('히스토리 계수 줄 — 종류 글 뒤 「{AI 값} → {고른 값}」(㉓ · C6)', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          {
            rowId: id(0),
            category: 'C1',
            factor: fakeRowFactor({
              value: '0.5',
              ai: {
                title: '지어낸',
                value: '0.25',
                source: '지어낸',
                co2e: '1',
              },
            }),
          },
        ]),
      ],
    });
    fireEvent.click(screen.getAllByTestId('s3-history-open')[0]!);
    const change = await screen.findByTestId('s3-history-change');
    expect(change.textContent).toBe(`0.25${w.history.arrow}0.5`);
  });
});

describe('감독 처분 ④ — R1·R2·R3', () => {
  it('칸에 쓰면 라디오가 직접입력으로 · 안 고른 채 [저장]은 직접입력 검사 → 채우면 POST(R3)', async () => {
    const server = await start();
    await startEdit();
    expect(checked(radio('s3-factor-pick-applied'))).toBe('checked');
    type('value', '0.5');
    expect(checked(radio('s3-factor-pick-custom'))).toBe('checked');
    pressSave();
    expect(screen.getByTestId('s3-factor-title-error').textContent).toBe(
      fe.required,
    );
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
    type('title', '지어낸 제목');
    type('source', '지어낸 출처');
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect(server.bodies(POST9)[0]).toMatchObject({
      choice: 'custom',
      rank: null,
      custom: { title: '지어낸 제목', value: '0.5', source: '지어낸 출처' },
    });
  });

  it('칸을 다 비워도 라디오는 직접입력 그대로 · 빈 칸은 필수 글(R3)', async () => {
    const server = await start();
    await startEdit();
    type('title', '지어낸');
    type('title', '');
    expect(checked(radio('s3-factor-pick-custom'))).toBe('checked');
    pressSave();
    expect(screen.getByTestId('s3-factor-title-error').textContent).toBe(
      fe.required,
    );
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
  });

  it('failed 를 받은 창은 처음 고름(적용)으로 돌아가도 사유 창 → POST(R2 — 같은 고름 판정 건너뜀)', async () => {
    const server = await start();
    server.override[POST9] = [unreachable];
    await write(() => pickRank(0));
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    fireEvent.keyDown(reasonInput(), { key: 'Escape' });
    await waitFor(() => expect(reasonBox()).toBeNull());
    pickApplied();
    pressSave();
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 되돌림');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(2));
    expect(server.bodies(POST9)[1]).toMatchObject({
      choice: 'applied',
      rank: null,
      custom: null,
    });
  });

  it('failed 뒤 창을 닫고 다시 연 창은 같은 고름 판정을 다시 한다 — 처음 고름이면 요청 0(R2 경계 · 검증 X6)', async () => {
    const server = await start();
    server.override[POST9] = [unreachable];
    await write(() => pickRank(0));
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() => expect(reasonInput().disabled).toBe(false));
    fireEvent.keyDown(reasonInput(), { key: 'Escape' });
    await waitFor(() => expect(reasonBox()).toBeNull());
    fireEvent.keyDown(windowBox()!, { key: 'Escape' });
    await waitFor(() => expect(windowBox()).toBeNull());
    await startEdit();
    expect(checked(radio('s3-factor-pick-applied'))).toBe('checked');
    pressSave();
    await waitFor(() =>
      expect(windowBox()!.getAttribute('data-mode')).toBe('view'),
    );
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(1);
  });

  it('같은 창이 failed 없이 처음 고름이면 여전히 요청 0(R2 — 좁힌 짝)', async () => {
    const server = await start();
    await startEdit();
    pickRank(0);
    pickApplied();
    pressSave();
    await waitFor(() =>
      expect(windowBox()!.getAttribute('data-mode')).toBe('view'),
    );
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
  });

  it('답 뒤 다시 읽는 중에는 칸을 눌러도 창이 안 열린다 · 다 읽은 뒤에는 열린다(R1)', async () => {
    const server = await start();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[YEAR] = [
      async () => {
        await gate;
        return server.send(
          new Request('http://test.local/api/inventory/scope3/years/2025'),
        );
      },
    ];
    const reads = server.count(YEAR);
    await write(() => pickRank(0));
    await waitFor(() => expect(windowBox()).toBeNull());
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    fireEvent.click(openers()[0]!);
    await settled();
    expect(windowBox()).toBeNull();
    release();
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    await settled();
    await openWindow();
    expect(windowBox()).not.toBeNull();
  });
});

describe('알림 줄은 마지막 하나(GX1 S3-09)', () => {
  it('계수를 고친 뒤 줄을 빼면 앞 「배출계수를 고쳤어요」는 지워지고 새 알림 하나만', async () => {
    await start();
    await write(() => pickRank(0));
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    fireEvent.click(screen.getAllByTestId('s3-pick-row')[1]!);
    fireEvent.click(screen.getByTestId('s3-exclude'));
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 뺀 사유');
    pressConfirm();
    await waitFor(() =>
      expect(screen.queryByTestId('s3-edit-notice')).not.toBeNull(),
    );
    expect(screen.queryByTestId('s3-factor-notice')).toBeNull();
    await write(() => pickRank(1), '지어낸 둘째 사유', 2);
    await waitFor(() => expect(noticeText()).toBe(fe.saved));
    expect(screen.queryByTestId('s3-edit-notice')).toBeNull();
  });
});

describe('창 머리 고정 · 산식 수식 글만 · 이름 칸 단추 색(GX3 ②)', () => {
  it('닫기·제목은 몸(민다) 밖 · 몸은 overflow-y-auto · 서버 산식의 숫자 자취는 뺀다', async () => {
    await start({
      runs: [
        done(
          9,
          c1Body([
            {
              ...purchaseRow('1', id(0)),
              formula:
                '배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000 = 9.1e+06 × 5.42043e-05 / 1000 = 0.493259',
            },
          ]),
        ),
      ],
    });
    expect(openers()[0]!.className).toContain('text-text-secondary');
    await openWindow();
    const box = windowBox()!;
    const body = within(box).getByTestId('s3-factor-window-body');
    expect(body.className).toContain('overflow-y-auto');
    expect(box.className).toContain('overflow-hidden');
    expect(body.contains(within(box).getByRole('heading', { level: 2 }))).toBe(
      false,
    );
    expect(body.contains(screen.getByTestId('s3-factor-edit'))).toBe(false);
    const basic = within(body).getByTestId('s3-window-basic');
    expect(
      within(basic).getByText(S3_TEXT.detail.factorWindow.emission).nextSibling
        ?.textContent,
    ).toBe('배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000');
  });
});
