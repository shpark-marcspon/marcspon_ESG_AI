// 밴드 GRJ1 ③: 근거 고침·재판단의 흉내 규칙(rejudgeRules.ts 한 벌)을 목 저장소와 시험용 가짜 서버(진짜 실어댑터 + 가짜 fetch)가
// 똑같이 쓰는가 — 같은 대본을 둘에 돌려 갈래(거절 code·줄 상태·셈·지운 칩)가 같은지 본다(GMK1 교훈). 서버 정본 차례는
// apps/api-py/esgapi/greenwash/service/actions/rejudge.py 머리말. 값은 지어낸 것이다.
import { describe, expect, it } from 'vitest';

import type { GreenwashReview, ScanResult } from '../../model/index.ts';
import { storeErrorKind } from '../store.ts';
import type { GreenwashStore } from '../store.ts';
import { listedGreenwashServer, serverStoreOf } from '../testing.ts';
import { createMockStore } from './mockStore.ts';
import {
  MOCK_FAIL_MARK,
  MOCK_NONRISK_MARK,
  REJUDGE_SETTLE_READS,
} from './rejudgeRules.ts';

const MOCK_RUN = 'run-106'; // 칩 있는 문장이 있는 씨앗(실호출 씨앗 — 값은 지어낸 판)

const outcome = async (call: () => Promise<unknown>) => {
  try {
    await call();
    return 'ok';
  } catch (error) {
    return storeErrorKind(error);
  }
};

/** 같은 대본: 칩 있는 문장 하나를 지우고 재판단 → 도는 중 → 끝남 → 같은 근거 → 실패 → 리스크 아님 → 확정 뒤 잠김. */
async function script(store: GreenwashStore, runId: string) {
  const result = (await store.getResult(runId)) as ScanResult;
  const index = result.items.findIndex(
    (item) => item.confirmedInEvidence.length > 0,
  );
  expect(index).toBeGreaterThanOrEqual(0);
  const read = async () => (await store.getReview(runId)) as GreenwashReview;
  const line = (review: GreenwashReview) =>
    review.rejudges.find((l) => l.itemIndex === index) ?? null;
  const proof = (review: GreenwashReview) =>
    review.evidence.find((e) => e.itemIndex === index) ?? null;
  const put = (
    removed: number[],
    added: { text: string; page: number | null }[],
  ) =>
    store.putReview(runId, {
      marks: [],
      evidence: [{ itemIndex: index, removed, added }],
    });
  const trace: unknown[] = [];
  const note = (...values: unknown[]) => trace.push(values);

  note('같은 근거', await outcome(() => store.rejudge(runId, index)));
  note('칩 밖', await outcome(() => put([99], [])));
  note('빈 조각', await outcome(() => put([], [{ text: '   ', page: null }])));
  // ④ M1: NUL 은 서버 has_bad_chars 로 400(짝 없는 서로게이트는 서버가 JSON 풀기에서 422 — 둘 다 rejected)
  note(
    '쓸 수 없는 글자',
    await outcome(() => put([], [{ text: '지어낸\u0000조각', page: null }])),
  );
  note(
    '페이지 밖',
    await outcome(() =>
      put([], [{ text: '지어낸 조각', page: result.source.pageCount + 1 }]),
    ),
  );
  note('문장 밖', await outcome(() => store.rejudge(runId, 999)));
  note('지움 저장', await outcome(() => put([0, 0], [])));
  note('정규화', proof(await read())?.removed);
  note('만듦', await outcome(() => store.rejudge(runId, index)));
  note('또 누름', await outcome(() => store.rejudge(runId, index)));
  // ④ B1: 도는 재판단이 있으면 확정을 받지 않는다(서버 규칙 8 — 확정 뒤에 기준 판단이 바뀌지 않게). 검토 GET 은 끝남 차례를
  // 세므로 여기서 읽지 않는다 — 잠기지 않은 것은 아래 「끝남」 뒤 재판단·맨 끝 확정이 잰다
  note(
    '도는 중 확정',
    await outcome(() =>
      store.putReview(runId, { state: 'confirmed', marks: [] }),
    ),
  );
  // GRJ3(서버 규칙 8 넓힘): 도는 문장의 근거를 지금 값과 다르게 바꾸는 PUT 은 409, 같은 값을 다시 실음·근거 생략은 받는다
  note('도는 중 근거 바꿈', await outcome(() => put([], [])));
  note('도는 중 같은 근거', await outcome(() => put([0], [])));
  note(
    '도는 중 근거 생략',
    await outcome(() => store.putReview(runId, { marks: [] })),
  );
  // 만든 뒤 위에서 한 번 읽었다 — 끝나는 읽기까지
  const reads: unknown[] = [];
  for (let n = 1; n < REJUDGE_SETTLE_READS; n++) {
    const review = await read();
    reads.push([line(review)?.status, line(review)?.count]);
  }
  note('도는 중', reads);
  const done = await read();
  note(
    '끝남',
    line(done)?.status,
    line(done)?.count,
    line(done)?.current?.level,
  );
  note('지운 칩 비움', proof(done));
  note('끝난 뒤 같은 근거', await outcome(() => store.rejudge(runId, index)));
  // 실패: 기준 판단은 앞 그대로
  const before = line(done)?.current?.runId;
  await put([], [{ text: `${MOCK_FAIL_MARK} 지어낸 조각`, page: 1 }]);
  note('실패 만듦', await outcome(() => store.rejudge(runId, index)));
  for (let n = 0; n <= REJUDGE_SETTLE_READS; n++) await read();
  const failed = line(await read());
  note(
    '실패',
    failed?.status,
    failed?.count,
    failed?.current?.runId === before,
  );
  // 리스크 아님
  await put([], [{ text: `${MOCK_NONRISK_MARK} 지어낸 조각`, page: null }]);
  note('리스크 아님 만듦', await outcome(() => store.rejudge(runId, index)));
  for (let n = 0; n <= REJUDGE_SETTLE_READS; n++) await read();
  const nonrisk = line(await read())?.current;
  note('리스크 아님', nonrisk?.outcome, nonrisk?.level);
  // 목록의 등급 수: 리스크 아님은 세 칸 밖
  const rows = await store.listCheckRows();
  const counts = rows.runs.find((r) => r.runId === runId)?.levelCounts;
  note(
    '셈',
    counts === null || counts === undefined ?
      null
    : counts.High + counts.Mid + counts.Low,
    result.items.length,
  );
  // 확정 뒤 잠김
  await store.putReview(runId, { state: 'confirmed', marks: [] });
  note('확정 뒤', await outcome(() => store.rejudge(runId, index)));
  return trace;
}

describe('근거 고침·재판단 흉내 규칙 한 벌(목 저장소 = 가짜 서버)', () => {
  it('같은 대본이 같은 갈래를 낸다', async () => {
    const mock = createMockStore();
    const fromMock = await script(mock.store, MOCK_RUN);

    const server = listedGreenwashServer();
    const run = server.runs.get(5)!;
    run.result = (await createMockStore().store.getResult(
      MOCK_RUN,
    )) as ScanResult;
    run.review = { ...run.review!, state: 'pending', marks: [], edits: [] };
    const fromServer = await script(serverStoreOf(server).store, '5');

    expect(fromServer).toEqual(fromMock);
    // 대본이 실제로 갈래를 지나갔는지(둘 다 같은 틀린 값이어도 초록이 되지 않게)
    expect(fromMock).toEqual([
      ['같은 근거', 'nothing_to_rejudge'],
      ['칩 밖', 'rejected'],
      ['빈 조각', 'rejected'],
      ['쓸 수 없는 글자', 'rejected'],
      ['페이지 밖', 'rejected'],
      ['문장 밖', 'not_found'],
      ['지움 저장', 'ok'],
      ['정규화', [0]],
      ['만듦', 'ok'],
      ['또 누름', 'rejudge_running'],
      ['도는 중 확정', 'rejudge_running'],
      ['도는 중 근거 바꿈', 'rejudge_running'],
      ['도는 중 같은 근거', 'ok'],
      ['도는 중 근거 생략', 'ok'],
      ['도는 중', [['running', 0]]],
      ['끝남', 'done', 1, 'High'],
      ['지운 칩 비움', null],
      ['끝난 뒤 같은 근거', 'nothing_to_rejudge'],
      ['실패 만듦', 'ok'],
      ['실패', 'failed', 1, true],
      ['리스크 아님 만듦', 'ok'],
      ['리스크 아님', 'nonrisk', null],
      ['셈', expect.any(Number), expect.any(Number)],
      ['확정 뒤', 'review_locked'],
    ]);
    const [, sum, total] = fromMock.find(
      (row) => (row as unknown[])[0] === '셈',
    ) as [string, number, number];
    expect(sum).toBe(total - 1);
  });

  it('가짜 서버 POST 의 꼴: 202 {rejudgeRunId}, 거절은 대문자 code', async () => {
    const server = listedGreenwashServer();
    const run = server.runs.get(5)!;
    run.result = (await createMockStore().store.getResult(
      MOCK_RUN,
    )) as ScanResult;
    run.review = { ...run.review!, state: 'pending', marks: [], edits: [] };
    const index = run.result.items.findIndex(
      (item) => item.confirmedInEvidence.length > 0,
    );
    const { store } = serverStoreOf(server);
    await store.putReview('5', {
      marks: [],
      evidence: [{ itemIndex: index, removed: [0], added: [] }],
    });
    expect(await store.rejudge('5', index)).toEqual({ rejudgeRunId: '9001' });
    const posts = server.calls.filter((c) => c.method === 'POST');
    expect(posts.at(-1)?.path).toBe(`/greenwash/runs/5/items/${index}/rejudge`);
  });
});
