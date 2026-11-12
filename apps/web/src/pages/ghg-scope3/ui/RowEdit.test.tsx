// @vitest-environment jsdom
// 상세 표 제외·복구·히스토리(밴드 S3W3b — 발주서 §3). ResultView 를 바로 그린다(reread 가 진짜 길로 돈다). 값은 지어낸 것.
//   쓰기 답 표 여덟 칸 · failed 두 갈래 · 얼린 seen · 고름이 풀리는 자리 · Space 뒤 초점 · 머리 체크·쪽·검색 · 시트 둘 · 앞 글 · 히스토리.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';

import { afterEach, describe, expect, it } from 'vitest';

import {
  FAKE_EDITOR,
  activityRow,
  fakeDetailResult,
  fakeDoneResult,
  fakeInput,
  fakeRowFactor,
  fakeScope3Server,
  portOf,
  processedSheet,
  purchaseRow,
  refusal,
  unreachable,
  withoutInput,
} from '../../../entities/ghg-scope3/api/testing.ts';
import type { FakeRowEdit } from '../../../entities/ghg-scope3/api/testing.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { ResultView } from './ResultView.tsx';
import { historyAtText } from './lockAt.ts';

afterEach(cleanup);

const w = S3_TEXT.rowEdit;
const YEAR = 'GET /inventory/scope3/years/2025';
const SHEET = 'c1_지어낸';
const ids = (count: number) =>
  Array.from({ length: count }, (_, i) => `${SHEET}!${i + 2}`);
const path = (run: number, what: 'exclusions' | 'restorations', c = 'C1') =>
  `/inventory/scope3/runs/${run}/categories/${c}/${what}`;
const POST9 = `POST ${path(9, 'exclusions')}`;
const c1Body = (count = 3, co2e = '1') =>
  fakeDoneResult({
    sheets: [
      processedSheet(
        SHEET,
        'Category1',
        ids(count).map((id) => purchaseRow(co2e, id)),
      ),
    ],
  });
const done = (id: number, result: unknown, edits?: FakeRowEdit[]) => ({
  id,
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
const cardOf = (id: string) =>
  screen
    .getAllByTestId('s3-result-card')
    .find((card) => card.getAttribute('data-category') === id)!;
const open = async (id = 'C1') => {
  await screen.findByTestId('s3-result');
  fireEvent.click(within(cardOf(id)).getByRole('button'));
  return screen.findByTestId('s3-detail');
};
const start = async (
  options: Parameters<typeof fakeScope3Server>[0] = {
    runs: [done(9, c1Body())],
  },
  drawn: Parameters<typeof draw>[1] = {},
) => {
  const server = fakeScope3Server(options);
  draw(server, drawn);
  await open();
  return server;
};
const checks = () => screen.getAllByTestId('s3-pick-row');
const checkAt = (n: number) => checks()[n]!;
const chosenCount = () =>
  checks().filter((one) => one.getAttribute('data-state') === 'checked').length;
const excludeButton = () =>
  screen.getByTestId('s3-exclude') as HTMLButtonElement;
const restoreButton = () =>
  screen.getByTestId('s3-restore') as HTMLButtonElement;
const reasonBox = () => screen.queryByTestId('s3-reason');
const askExclude = async (rows: number[] = [0]) => {
  for (const n of rows) fireEvent.click(checkAt(n));
  fireEvent.click(excludeButton());
  return screen.findByTestId('s3-reason');
};
const typeReason = (text: string) =>
  fireEvent.change(screen.getByTestId('s3-reason-input'), {
    target: { value: text },
  });
const pressConfirm = () =>
  fireEvent.click(
    within(screen.getByTestId('s3-reason')).getByRole('button', {
      name: w.reason.confirm,
    }),
  );
const pressCancel = () =>
  fireEvent.click(
    within(screen.getByTestId('s3-reason')).getByRole('button', {
      name: w.reason.cancel,
    }),
  );
const noticeText = () => screen.queryByTestId('s3-edit-notice')?.textContent;
/** 창이 닫히고 초점이 돌아올 차례(Radix 가 다음 틱에 옮긴다). */
const settled = () => new Promise((resolve) => setTimeout(resolve, 20));

describe('표 열 · 표 위 줄', () => {
  it('앞 체크·뒤 히스토리 두 열 · 표 위 줄에 검색과 단추 셋([원본 다운로드] 맨 앞 — S3Q1) · 거름 0', async () => {
    await start();
    const table = screen.getByRole('table');
    const heads = within(table).getAllByRole('columnheader');
    expect(within(heads[0]!).getByRole('checkbox')).toBeTruthy();
    expect(heads[0]!.getAttribute('style') ?? '').toContain('52');
    expect(heads.at(-1)!.textContent).toBe(w.history.column);
    expect(heads.at(-1)!.getAttribute('style') ?? '').toContain('140');
    const tools = screen.getByTestId('s3-detail-tools');
    expect(within(tools).getByTestId('s3-detail-search')).toBeTruthy();
    expect(
      within(tools)
        .getAllByRole('button')
        .map((one) => one.textContent),
    ).toEqual([S3_TEXT.original.button, w.exclude, w.restore]);
    expect(within(tools).queryByRole('combobox')).toBeNull();
    expect(excludeButton().disabled).toBe(true);
    expect(restoreButton().disabled).toBe(true);
  });

  it('글 열 없는 표(generic)에도 단추 셋은 있고 검색은 없다', async () => {
    const sheet = '지어낸 표';
    await start({
      runs: [
        done(
          9,
          fakeDoneResult({
            sheets: [
              processedSheet(sheet, 'Category1', [
                {
                  ...activityRow('waste', '1', null, `${sheet}!2`),
                  kind: 'brand_new',
                },
              ]),
            ],
          }),
        ),
      ],
    });
    expect(screen.queryByTestId('s3-detail-search')).toBeNull();
    expect(
      within(screen.getByTestId('s3-detail-tools'))
        .getAllByRole('button')
        .map((one) => one.textContent),
    ).toEqual([S3_TEXT.original.button, w.exclude, w.restore]);
    fireEvent.click(checkAt(0));
    expect(excludeButton().disabled).toBe(false);
  });

  it('계산된 시트가 없어도 표 위 줄은 있고 [원본 다운로드] 하나뿐(S3Q1 — 검색·제외·복구 0)', async () => {
    await start({
      runs: [
        done(
          9,
          fakeDoneResult({
            sheets: [
              {
                status: 'failed',
                sheet: SHEET,
                category: 'Category1',
                error: 'x',
              },
              processedSheet('c2_지어낸', 'Category2', [
                purchaseRow('1', 'c2_지어낸!2'),
              ]),
            ],
          }),
        ),
      ],
    });
    const tools = screen.getByTestId('s3-detail-tools');
    expect(
      within(tools)
        .getAllByRole('button')
        .map((one) => one.textContent),
    ).toEqual([S3_TEXT.original.button]);
    expect(screen.queryByTestId('s3-detail-search')).toBeNull();
  });

  it('섞어 고르면 단추 둘 다 켜지고 단추마다 해당 줄만 보낸다', async () => {
    const server = await start({
      runs: [
        done(9, c1Body(), [
          { rowId: ids(3)[1]!, category: 'C1', excluded: true },
        ]),
      ],
    });
    fireEvent.click(checkAt(0));
    expect(excludeButton().disabled).toBe(false);
    expect(restoreButton().disabled).toBe(true);
    fireEvent.click(checkAt(1));
    expect(restoreButton().disabled).toBe(false);
    fireEvent.click(restoreButton());
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(server.bodies(`POST ${path(9, 'restorations')}`)).toEqual([
      { rowIds: [ids(3)[1]], reason: '지어낸 사유' },
    ]);
  });

  it('막힘 꼴(S3Q2 · c3 11-11): 고른 줄 없이 두 단추 막힘 클래스 같음 · 복구가 켜지면 검정', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          { rowId: ids(3)[1]!, category: 'C1', excluded: true },
        ]),
      ],
    });
    expect(excludeButton().disabled).toBe(true);
    expect(restoreButton().disabled).toBe(true);
    expect(restoreButton().className).toBe(excludeButton().className);
    expect(restoreButton().className.split(/\s+/)).not.toContain(
      'bg-button-black',
    );
    fireEvent.click(checkAt(1));
    expect(restoreButton().disabled).toBe(false);
    expect(restoreButton().className.split(/\s+/)).toContain('bg-button-black');
  });
});

describe('쓰기 답 표 여덟 칸', () => {
  const cases = [
    ['LOCKED', () => refusal(409, 'LOCKED'), w.locked, true],
    ['STALE_RUN', () => refusal(409, 'STALE_RUN'), w.stale, true],
    [
      'rowIds 만',
      () => refusal(422, 'VALIDATION_ERROR', { rowIds: ['지어낸'] }),
      w.stale,
      true,
    ],
  ] as const;

  it('ok: 창 닫힘 · 보낸 수 한 줄 · 다시 읽어 표가 서버 값 · 고름 풂 · 초점 [목록]', async () => {
    const server = await start();
    const reads = server.count(YEAR);
    await askExclude([0, 1]);
    typeReason('  지어낸 사유  ');
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(server.bodies(POST9)).toEqual([
      { rowIds: ids(3).slice(0, 2), reason: '지어낸 사유' },
    ]);
    await waitFor(() => expect(noticeText()).toBe(w.excluded(2)));
    expect(screen.getByTestId('s3-edit-notice').getAttribute('role')).toBe(
      'status',
    );
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    await waitFor(() =>
      expect(
        screen
          .getAllByTestId('s3-row')
          .filter((row) => row.getAttribute('data-excluded') === 'true'),
      ).toHaveLength(2),
    );
    expect(chosenCount()).toBe(0);
    await settled();
    expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back'));
    // 다음 고름에 알림을 지운다.
    fireEvent.click(checkAt(2));
    expect(noticeText()).toBeUndefined();
  });

  it('복구 ok: 「되돌렸어요」 글', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          { rowId: ids(3)[0]!, category: 'C1', excluded: true },
        ]),
      ],
    });
    fireEvent.click(checkAt(0));
    fireEvent.click(restoreButton());
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(noticeText()).toBe(w.restored(1)));
    // 다시 읽기가 덧씌우기 전 본문을 쓰지 않으면 옛 제외가 남는다.
    await waitFor(() =>
      expect(
        screen.getAllByTestId('s3-row')[0]!.getAttribute('data-excluded'),
      ).toBeNull(),
    );
  });

  it.each(cases)(
    '%s: 창 닫힘 · 한 줄 · 다시 읽음 · 고름 풂 · 초점 [목록](B4)',
    async (_, answer, text) => {
      const server = await start();
      server.override[POST9] = [answer];
      const reads = server.count(YEAR);
      await askExclude();
      typeReason('지어낸 사유');
      pressConfirm();
      await waitFor(() => expect(reasonBox()).toBeNull());
      await waitFor(() => expect(noticeText()).toBe(text));
      expect(screen.getByTestId('s3-edit-notice').getAttribute('role')).toBe(
        'alert',
      );
      await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
      expect(chosenCount()).toBe(0);
      await settled();
      expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back'));
    },
  );

  it('VALIDATION_ERROR reason: 창 둠 · 칸 아래 글 · 다시 읽기 0 · 고름 둠', async () => {
    const server = await start();
    server.override[POST9] = [
      () => refusal(422, 'VALIDATION_ERROR', { reason: ['지어낸'] }),
    ];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    expect(
      (await screen.findByTestId('s3-reason-input-error')).textContent,
    ).toBe(w.reason.rejected);
    await settled();
    expect(reasonBox()).not.toBeNull();
    expect(server.count(YEAR)).toBe(reads);
    expect(chosenCount()).toBe(1);
  });

  it('그 밖 거절(404): 창 둠 · 쓴 사유 유지 · 창 안 글 · 다시 읽기 0 · 고름 둠', async () => {
    const server = await start();
    server.override[POST9] = [() => refusal(404, 'NOT_FOUND')];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    expect((await screen.findByTestId('s3-reason-failed')).textContent).toBe(
      w.failed,
    );
    await settled();
    expect(
      (screen.getByTestId('s3-reason-input') as HTMLInputElement).value,
    ).toBe('지어낸 사유');
    expect(server.count(YEAR)).toBe(reads);
    expect(chosenCount()).toBe(1);
  });

  it('refused: 창 닫힘 · 회사 글 · 다시 읽기 0 · 고름 둠 · 초점은 누른 단추', async () => {
    const server = await start();
    server.override[POST9] = [() => refusal(400, 'COMPANY_AMBIGUOUS')];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(noticeText()).toBe(S3_TEXT.company.ambiguous);
    await settled();
    expect(server.count(YEAR)).toBe(reads);
    expect(chosenCount()).toBe(1);
    expect(document.activeElement).toBe(excludeButton());
  });

  it('failed — 안 들어감: 창 둠 · 쓴 사유 유지 · 다시 읽음 · 고름 둠 · [확인]이 같은 몸', async () => {
    const server = await start();
    server.override[POST9] = [unreachable];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    expect((await screen.findByTestId('s3-reason-failed')).textContent).toBe(
      w.failed,
    );
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
    expect(
      (screen.getByTestId('s3-reason-input') as HTMLInputElement).value,
    ).toBe('지어낸 사유');
    expect(chosenCount()).toBe(1);
    await waitFor(() =>
      expect(
        (screen.getByTestId('s3-reason-input') as HTMLInputElement).disabled,
      ).toBe(false),
    );
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    const [first, second] = server.bodies(POST9);
    expect(second).toEqual(first);
  });

  it('failed — 서버에 들어간 뒤 끊김: 창 뒤 표가 서버 값 · 다시 [확인]은 ok', async () => {
    const server = await start();
    server.override[POST9] = [
      async () => {
        await server.send(
          new Request(`http://test.local/api${path(9, 'exclusions')}`, {
            method: 'POST',
            body: JSON.stringify({
              rowIds: [ids(3)[0]],
              reason: '지어낸 사유',
            }),
          }),
        );
        return unreachable();
      },
    ];
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() =>
      expect(
        screen.getAllByTestId('s3-row')[0]!.getAttribute('data-excluded'),
      ).toBe('true'),
    );
    await waitFor(() =>
      expect(
        (screen.getByTestId('s3-reason-input') as HTMLInputElement).disabled,
      ).toBe(false),
    );
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(noticeText()).toBe(w.excluded(1));
  });

  it('답 전에 [목록]으로 나가도 다시 읽어 카드 합이 서버 값', async () => {
    const server = await start();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[POST9] = [
      async () => {
        await gate;
        return server.send(
          new Request(`http://test.local/api${path(9, 'exclusions')}`, {
            method: 'POST',
            body: JSON.stringify({
              rowIds: [ids(3)[0]],
              reason: '지어낸 사유',
            }),
          }),
        );
      },
    ];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    release();
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
  });

  it('failed — 답 전에 [목록]으로 나가도 다시 읽는다(서버에 들어간 뒤 끊김)', async () => {
    const server = await start();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.override[POST9] = [
      async () => {
        await gate;
        await server.send(
          new Request(`http://test.local/api${path(9, 'exclusions')}`, {
            method: 'POST',
            body: JSON.stringify({
              rowIds: [ids(3)[0]],
              reason: '지어낸 사유',
            }),
          }),
        );
        return unreachable();
      },
    ];
    const reads = server.count(YEAR);
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    fireEvent.click(screen.getByTestId('s3-detail-back'));
    await screen.findByTestId('s3-result');
    release();
    await waitFor(() => expect(server.count(YEAR)).toBe(reads + 1));
  });
});

describe('쓰는 실행 · 고름이 풀리는 자리', () => {
  const later = () => ({
    ...done(11, c1Body(3, '10')),
    status: 'processing' as const,
    script: ['processing', 'done'] as ('processing' | 'done')[],
  });

  it('화면 prop 의 실행이 아니라 그 카테고리 지금 결과 실행으로 보낸다', async () => {
    const server = await start(
      { runs: [done(7, c1Body()), done(9, c1Body())] },
      { runId: '7' },
    );
    await askExclude();
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    expect(server.count(`POST ${path(7, 'exclusions')}`)).toBe(0);
  });

  it('창이 열린 사이 지금 결과가 바뀌어도 본 실행을 보내 stale_run 이 일한다 · 그때 고름은 풀리고 같은 rowId 는 고른 꼴이 아니다', async () => {
    const server = await start({ runs: [done(9, c1Body()), later()] });
    server.override[POST9] = [unreachable];
    await askExclude();
    typeReason('지어낸 사유');
    await server.send(new Request('http://test.local/api/runs/11'));
    pressConfirm();
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() =>
      expect(
        (screen.getByTestId('s3-reason-input') as HTMLInputElement).disabled,
      ).toBe(false),
    );
    await waitFor(() =>
      expect(screen.getByTestId('s3-detail-total').textContent).toContain('30'),
    );
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(server.count(POST9)).toBe(2);
    expect(server.count(`POST ${path(11, 'exclusions')}`)).toBe(0);
    await waitFor(() => expect(noticeText()).toBe(w.stale));
    expect(chosenCount()).toBe(0);
  });

  it('실행이 바뀌면 같은 rowId 의 고름이 풀린다(창을 취소해도)', async () => {
    const server = await start({ runs: [done(9, c1Body()), later()] });
    server.override[POST9] = [unreachable];
    await askExclude();
    typeReason('지어낸 사유');
    await server.send(new Request('http://test.local/api/runs/11'));
    pressConfirm();
    await screen.findByTestId('s3-reason-failed');
    await waitFor(() =>
      expect(
        (screen.getByTestId('s3-reason-input') as HTMLInputElement).disabled,
      ).toBe(false),
    );
    pressCancel();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(chosenCount()).toBe(0);
    expect(excludeButton().disabled).toBe(true);
    await settled();
    expect(document.activeElement).toBe(screen.getByTestId('s3-detail-back'));
  });

  it('잠기면 고름이 풀리고 체크·단추가 막히고 툴팁 자리가 초점을 받는다 · 히스토리는 열린다', async () => {
    await start({ runs: [done(9, c1Body())] }, { operator: true });
    fireEvent.click(checkAt(0));
    fireEvent.click(screen.getByTestId('s3-lock'));
    await waitFor(() =>
      expect(screen.getByTestId('s3-lock').getAttribute('data-locked')).toBe(
        'true',
      ),
    );
    await waitFor(() => expect(chosenCount()).toBe(0));
    expect((checkAt(0) as HTMLButtonElement).disabled).toBe(true);
    expect(excludeButton().disabled).toBe(true);
    expect(restoreButton().disabled).toBe(true);
    const tips = screen.getAllByTestId('s3-edit-locked');
    expect(tips).toHaveLength(2);
    expect(tips[0]!.getAttribute('tabindex')).toBe('0');
    const history = screen.getAllByTestId(
      's3-history-open',
    )[0] as HTMLButtonElement;
    expect(history.disabled).toBe(false);
    fireEvent.click(history);
    await screen.findByTestId('s3-history');
  });

  it('운영 관리자도 단추 둘이 있고 켜진다', async () => {
    await start({ runs: [done(9, c1Body())] }, { operator: true });
    fireEvent.click(checkAt(0));
    expect(excludeButton().disabled).toBe(false);
  });

  it.each(['C12', 'C15'])('%s 도 제외·히스토리를 막지 않는다', async (id) => {
    const server = fakeScope3Server({ runs: [done(9, fakeDetailResult())] });
    draw(server);
    await open(id);
    fireEvent.click(checkAt(0));
    expect(excludeButton().disabled).toBe(false);
    expect(
      (screen.getAllByTestId('s3-history-open')[0] as HTMLButtonElement)
        .disabled,
    ).toBe(false);
  });

  it('취소: 요청 0 · 초점은 누른 단추 · 고름 둠', async () => {
    const server = await start();
    await askExclude();
    pressCancel();
    await waitFor(() => expect(reasonBox()).toBeNull());
    await settled();
    expect(server.count(POST9)).toBe(0);
    expect(chosenCount()).toBe(1);
    expect(document.activeElement).toBe(excludeButton());
  });
});

describe('체크', () => {
  it('누른 뒤 초점이 그 상자에 남고 칸이 다시 달리지 않는다', async () => {
    await start();
    const box = checkAt(1);
    box.focus();
    fireEvent.click(box);
    expect(box.isConnected).toBe(true);
    expect(document.activeElement).toBe(box);
    expect(box.getAttribute('data-state')).toBe('checked');
  });

  it('머리 체크는 지금 쪽만 · 일부면 mixed · 쪽을 넘겨도 고름은 남는다', async () => {
    const server = await start({ runs: [done(9, c1Body(53))] });
    const head = screen.getByTestId('s3-pick-page');
    fireEvent.click(checkAt(0));
    expect(head.getAttribute('aria-checked')).toBe('mixed');
    fireEvent.click(head);
    expect(chosenCount()).toBe(50);
    expect(head.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(
      within(screen.getByTestId('s3-pager')).getByRole('button', {
        name: S3_TEXT.detail.nextPage,
      }),
    );
    await waitFor(() => expect(checks()).toHaveLength(3));
    expect(chosenCount()).toBe(0);
    expect(
      screen.getByTestId('s3-pick-page').getAttribute('aria-checked'),
    ).toBe('false');
    fireEvent.click(excludeButton());
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    const [body] = server.bodies(POST9) as { rowIds: string[] }[];
    expect(body!.rowIds).toHaveLength(50);
  });

  it('검색어가 바뀌면 고름을 푼다(B7)', async () => {
    await start();
    fireEvent.click(checkAt(0));
    fireEvent.change(screen.getByTestId('s3-detail-search'), {
      target: { value: '지' },
    });
    await waitFor(() => expect(excludeButton().disabled).toBe(true));
  });

  it('시트 둘에서 고르면 요청은 하나', async () => {
    const other = 'c1_둘째';
    const server = await start({
      runs: [
        done(
          9,
          fakeDoneResult({
            sheets: [
              processedSheet(SHEET, 'Category1', [
                purchaseRow('1', `${SHEET}!2`),
              ]),
              processedSheet(other, 'Category1', [
                purchaseRow('1', `${other}!2`),
              ]),
            ],
          }),
        ),
      ],
    });
    await askExclude([0, 1]);
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(reasonBox()).toBeNull());
    expect(server.bodies(POST9)).toEqual([
      { rowIds: [`${SHEET}!2`, `${other}!2`], reason: '지어낸 사유' },
    ]);
  });

  /** 모든 쪽을 고른다(쪽마다 머리 체크). */
  const pickAllPages = (pages: number) => {
    for (let at = 1; at < pages; at += 1) {
      fireEvent.click(screen.getByTestId('s3-pick-page'));
      fireEvent.click(
        within(screen.getByTestId('s3-pager')).getByRole('button', {
          name: S3_TEXT.detail.nextPage,
        }),
      );
    }
    fireEvent.click(screen.getByTestId('s3-pick-page'));
  };
  const oneOut = (rows: number) =>
    done(9, c1Body(rows), [
      { rowId: ids(rows)[0]!, category: 'C1', excluded: true },
    ]);

  it('보낼 줄이 2,001 이면 창을 열지 않고 한 줄 · 요청 0', async () => {
    const server = await start({ runs: [oneOut(2002)] });
    pickAllPages(41);
    fireEvent.click(excludeButton());
    expect(noticeText()).toBe(w.tooMany);
    expect(reasonBox()).toBeNull();
    expect(server.count(POST9)).toBe(0);
  }, 30000);

  it('고른 수가 2,001 이어도 보낼 줄이 2,000 이면 창이 열리고 해당 줄만 나간다(섞임)', async () => {
    const server = await start({ runs: [oneOut(2001)] });
    pickAllPages(41);
    fireEvent.click(excludeButton());
    await screen.findByTestId('s3-reason');
    typeReason('지어낸 사유');
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
    const [body] = server.bodies(POST9) as { rowIds: string[] }[];
    expect(body!.rowIds).toHaveLength(2000);
    expect(body!.rowIds).not.toContain(ids(2001)[0]);
  }, 30000);
});

describe('사유 창', () => {
  it('글·첫 초점 칸 · 빈칸만은 칸 글 요청 0', async () => {
    const server = await start();
    const box = await askExclude();
    expect(within(box).getByRole('heading').textContent).toBe(w.reason.title);
    expect(within(box).getByTestId('s3-reason-warning').textContent).toBe(
      w.reason.warning,
    );
    await settled();
    expect(document.activeElement).toBe(screen.getByTestId('s3-reason-input'));
    typeReason('    ');
    pressConfirm();
    expect(screen.getByTestId('s3-reason-input-error').textContent).toBe(
      w.reason.required,
    );
    expect(server.count(POST9)).toBe(0);
  });

  it('300자는 나가고 301자는 칸 글 요청 0(500 이 아니다)', async () => {
    const server = await start();
    await askExclude();
    typeReason('가'.repeat(301));
    pressConfirm();
    expect(screen.getByTestId('s3-reason-input-error').textContent).toBe(
      w.reason.tooLong(300),
    );
    expect(server.count(POST9)).toBe(0);
    typeReason('가'.repeat(300));
    pressConfirm();
    await waitFor(() => expect(server.count(POST9)).toBe(1));
  });
});

describe('제외 줄 꼴', () => {
  const seeded = (rowId: string) => [{ rowId, category: 'C1', excluded: true }];

  it('C1 앞 글은 그룹 칸 · 단추 밖 · 이름만 링크 · 비율 「-」 · 값은 그대로', async () => {
    await start({ runs: [done(9, c1Body(2), seeded(ids(2)[0]!))] });
    const [row] = screen.getAllByTestId('s3-row');
    const opener = within(row!).getByTestId('s3-window-open');
    expect(opener.textContent).not.toContain(w.excludedLead);
    expect(opener.parentElement!.textContent).toBe(
      `${w.excludedLead} - ${opener.textContent}`,
    );
    expect(row!.getAttribute('data-excluded')).toBe('true');
  });

  it('앞 글이 비면 「산정 제외」만(B3 — 「산정 제외 - -」 아님)', async () => {
    const sheet = 'c5_지어낸';
    const server = fakeScope3Server({
      runs: [
        done(
          9,
          fakeDoneResult({
            sheets: [
              processedSheet(sheet, 'Category5', [
                withoutInput(
                  activityRow('waste', '1', undefined, `${sheet}!3`),
                ),
                {
                  ...activityRow('waste', '1', undefined, `${sheet}!4`),
                  input: fakeInput('c5', { site: '' }),
                },
                {
                  ...activityRow('waste', '1', undefined, `${sheet}!5`),
                  input: fakeInput('c5', { site: '지어낸 곳' }),
                },
              ]),
            ],
          }),
          [3, 4, 5].map((n) => ({
            rowId: `${sheet}!${n}`,
            category: 'C5',
            excluded: true,
          })),
        ),
      ],
    });
    draw(server);
    await open('C5');
    const leads = screen
      .getAllByTestId('s3-row')
      .map((row) => row.querySelectorAll('td')[2]!.textContent);
    expect(leads).toEqual([
      w.excludedLead,
      w.excludedLead,
      `${w.excludedLead} - 지어낸 곳`,
    ]);
  });

  it('「산정 제외」로 검색해도 걸리지 않는다', async () => {
    await start({ runs: [done(9, c1Body(2), seeded(ids(2)[0]!))] });
    fireEvent.change(screen.getByTestId('s3-detail-search'), {
      target: { value: w.excludedLead },
    });
    await waitFor(() =>
      expect(screen.queryAllByTestId('s3-row')).toHaveLength(0),
    );
  });
});

describe('히스토리 창', () => {
  const HISTORY = '/inventory/scope3/runs/9/history';
  const asked = (server: Server) =>
    server.calls.filter((one) => one.path === HISTORY);
  const openHistory = async (n = 0) => {
    fireEvent.click(screen.getAllByTestId('s3-history-open')[n]!);
    return screen.findByTestId('s3-history');
  };

  it('rowId 를 실어 지금 결과 실행으로 읽는다 · 세 칸 · 종류 글 · [확인] 뒤 초점은 누른 단추', async () => {
    const server = await start({
      runs: [
        done(9, c1Body(), [
          {
            rowId: ids(3)[0]!,
            category: 'C1',
            excluded: true,
            factor: fakeRowFactor(),
          },
          { rowId: ids(3)[1]!, category: 'C1', excluded: true, by: null },
        ]),
      ],
    });
    const box = await openHistory(0);
    await within(box).findAllByTestId('s3-history-row');
    const [call] = asked(server);
    expect(call!.query.get('rowId')).toBe(ids(3)[0]);
    expect(call!.query.get('pageSize')).toBe('20');
    expect(call!.query.get('page')).toBe('1');
    const kinds = within(box)
      .getAllByTestId('s3-history-kind')
      .map((one) => one.textContent);
    expect([...kinds].sort()).toEqual(
      [w.history.kinds.exclude, w.history.kinds.factor].sort(),
    );
    expect(
      within(box)
        .getAllByRole('columnheader')
        .map((one) => one.textContent),
    ).toEqual([w.history.at, w.history.by, w.history.reason]);
    expect(
      within(box).getAllByTestId('s3-history-row')[0]!.textContent,
    ).toContain(FAKE_EDITOR.name);
    const opener = screen.getAllByTestId('s3-history-open')[0]!;
    fireEvent.click(screen.getByTestId('s3-history-close'));
    await waitFor(() => expect(screen.queryByTestId('s3-history')).toBeNull());
    await settled();
    expect(document.activeElement).toBe(opener);
  });

  it('by null 은 「-」 · 빈 이력 글', async () => {
    await start({
      runs: [
        done(9, c1Body(), [
          { rowId: ids(3)[1]!, category: 'C1', excluded: true, by: null },
        ]),
      ],
    });
    const box = await openHistory(1);
    const [line] = await within(box).findAllByTestId('s3-history-row');
    expect(line!.querySelectorAll('td')[1]!.textContent).toBe(
      S3_TEXT.result.empty,
    );
    fireEvent.click(screen.getByTestId('s3-history-close'));
    await waitFor(() => expect(screen.queryByTestId('s3-history')).toBeNull());
    const empty = await openHistory(0);
    expect(
      (await within(empty).findByTestId('s3-history-empty')).textContent,
    ).toBe(w.history.empty);
  });

  it('마지막 실행이 아니라 지금 결과 실행(잠근 핀)을 읽는다', async () => {
    const server = await start({
      runs: [done(7, c1Body()), done(9, c1Body())],
      locks: [{ year: 2025, category: 'C1', runId: 7 }],
    });
    await openHistory();
    const pinned = '/inventory/scope3/runs/7/history';
    await waitFor(() =>
      expect(server.calls.some((one) => one.path === pinned)).toBe(true),
    );
    expect(asked(server)).toHaveLength(0);
  });

  it('20개 넘으면 쪽 넘김 · 다음 쪽을 읽는다 · 넘기는 동안 단추가 남는다 · 늦은 앞 쪽 답은 버린다', async () => {
    const edits = Array.from({ length: 21 }, () => ({
      rowId: ids(3)[0]!,
      category: 'C1',
      excluded: true,
    }));
    const server = await start({ runs: [done(9, c1Body(), edits)] });
    const box = await openHistory();
    await within(box).findByTestId('s3-history-pager');
    expect(within(box).getAllByTestId('s3-history-row')).toHaveLength(20);
    const turn = (name: string) => within(box).getByRole('button', { name });
    const shownPage = () =>
      within(box).getByTestId('s3-history-page').textContent;
    const { nextPage, prevPage, pageStatus } = S3_TEXT.detail;
    const next = turn(nextPage);
    fireEvent.click(next);
    await waitFor(() => expect(shownPage()).toBe(pageStatus(2, 2)));
    expect(asked(server).at(-1)!.query.get('page')).toBe('2');
    expect(asked(server).at(-1)!.query.get('rowId')).toBe(ids(3)[0]);
    expect(within(box).getAllByTestId('s3-history-row')).toHaveLength(1);
    expect(next.isConnected).toBe(true);
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const url = `http://test.local/api${HISTORY}?rowId=${encodeURIComponent(ids(3)[0]!)}&page=1&pageSize=20`;
    server.override[`GET ${HISTORY}`] = [
      async () => {
        await gate;
        return server.send(new Request(url));
      },
    ];
    // 1 쪽 답을 붙잡아 두고 2 쪽 답이 먼저 온다 — 늦은 1 쪽 답이 덮으면 안 된다.
    fireEvent.click(turn(prevPage));
    await waitFor(() =>
      expect(asked(server).at(-1)!.query.get('page')).toBe('1'),
    );
    fireEvent.click(turn(nextPage));
    await waitFor(() =>
      expect(asked(server).at(-1)!.query.get('page')).toBe('2'),
    );
    await settled();
    release();
    await settled();
    expect(shownPage()).toBe(pageStatus(2, 2));
    expect(within(box).getAllByTestId('s3-history-row')).toHaveLength(1);
  });

  it('쪽을 넘기다 실패하면 앞 쪽 표를 걷고 실패 글 · [다시 시도]는 불러오는 중을 띄우고 그 쪽을 읽는다', async () => {
    const edits = Array.from({ length: 21 }, () => ({
      rowId: ids(3)[0]!,
      category: 'C1',
      excluded: true,
    }));
    const server = await start({ runs: [done(9, c1Body(), edits)] });
    const box = await openHistory();
    await within(box).findByTestId('s3-history-pager');
    const { nextPage, pageStatus } = S3_TEXT.detail;
    server.override[`GET ${HISTORY}`] = [unreachable];
    fireEvent.click(within(box).getByRole('button', { name: nextPage }));
    await within(box).findByTestId('s3-history-failed');
    expect(asked(server).at(-1)!.query.get('page')).toBe('2');
    // 앞 쪽을 두면 실패를 말없이 삼킨다.
    expect(within(box).queryAllByTestId('s3-history-row')).toHaveLength(0);
    expect(within(box).queryByTestId('s3-history-pager')).toBeNull();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const url = `http://test.local/api${HISTORY}?rowId=${encodeURIComponent(ids(3)[0]!)}&page=2&pageSize=20`;
    server.override[`GET ${HISTORY}`] = [
      async () => {
        await gate;
        return server.send(new Request(url));
      },
    ];
    const tries = asked(server).length;
    fireEvent.click(within(box).getByTestId('s3-history-retry'));
    await within(box).findByTestId('s3-history-loading');
    expect(within(box).queryByTestId('s3-history-failed')).toBeNull();
    // 붙잡은 답이 page=2 를 스스로 읽으므로 나간 쪽은 풀기 전에 본다.
    await waitFor(() => expect(asked(server)).toHaveLength(tries + 1));
    expect(asked(server).at(-1)!.query.get('page')).toBe('2');
    release();
    await waitFor(() =>
      expect(within(box).getByTestId('s3-history-page').textContent).toBe(
        pageStatus(2, 2),
      ),
    );
    expect(within(box).getAllByTestId('s3-history-row')).toHaveLength(1);
    expect(within(box).queryByTestId('s3-history-loading')).toBeNull();
  });

  it('답 전에 닫아도 늦은 답이 창을 되살리지 않는다', async () => {
    const server = await start();
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const url = `http://test.local/api${HISTORY}?rowId=${encodeURIComponent(ids(3)[0]!)}&page=1&pageSize=20`;
    server.override[`GET ${HISTORY}`] = [
      async () => {
        await gate;
        return server.send(new Request(url));
      },
    ];
    await openHistory();
    fireEvent.click(screen.getByTestId('s3-history-close'));
    await waitFor(() => expect(screen.queryByTestId('s3-history')).toBeNull());
    release();
    await settled();
    expect(screen.queryByTestId('s3-history')).toBeNull();
  });

  it('읽기 실패 글 · [다시 시도] · 회사 거절은 다시 시도 0', async () => {
    const server = await start();
    server.override[`GET ${HISTORY}`] = [unreachable];
    const box = await openHistory();
    await within(box).findByTestId('s3-history-failed');
    fireEvent.click(within(box).getByTestId('s3-history-retry'));
    await within(box).findByTestId('s3-history-empty');
    expect(asked(server)).toHaveLength(2);
    fireEvent.click(screen.getByTestId('s3-history-close'));
    await waitFor(() => expect(screen.queryByTestId('s3-history')).toBeNull());
    server.override[`GET ${HISTORY}`] = [
      () => refusal(400, 'COMPANY_INACTIVE'),
    ];
    const again = await openHistory();
    expect(
      (await within(again).findByTestId('s3-history-refused')).textContent,
    ).toBe(S3_TEXT.company.inactive);
    expect(within(again).queryByTestId('s3-history-retry')).toBeNull();
  });

  it('수정일시 꼴: 한국 시각 점 꼴 · 못 읽으면 받은 글자', () => {
    expect(historyAtText('2031-02-03T15:04:00Z')).toBe('2031.02.04 00:04');
    expect(historyAtText('지어낸 때')).toBe('지어낸 때');
  });
});
