// 밴드 G1b-3 ③: 목 저장소가 검토 고침의 서버 규칙(apps/api-py/esgapi/greenwash/service/actions/review.py 머리말)을 흉내 내는가 —
// 정규화(strip·빈 항목 버림·AI 와 같은 값은 null)·칸마다 때·사람(값이 바뀐 칸만)·edits 생략은 그대로·[] 는 다 지움·pending → in_review·
// 400(rejected)·확정 뒤 잠김, 목록 levelCounts 는 효력 등급. 씨앗 run-102(검토 대기)를 쓴다. 값은 지어낸 것이다.
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  ReviewEdit,
  ReviewEditIn,
  ScanResult,
} from '../../model/index.ts';
import { StoreError } from '../store.ts';
import { listedGreenwashServer, serverStoreOf } from '../testing.ts';
import { createMockStore, nextEdits } from './mockStore.ts';

const RUN = 'run-102';

afterEach(() => {
  vi.useRealTimers();
});

/** 시계를 손으로 돌리는 목 저장소. */
function setup() {
  let at = new Date('2026-10-22T05:00:00Z'); // 14:00 +09:00
  const control = createMockStore({ now: () => at });
  return {
    store: control.store,
    tick: (minutes: number) => {
      at = new Date(at.getTime() + minutes * 60_000);
    },
  };
}

const flat = (
  over: Partial<ReviewEditIn> & { itemIndex: number },
): ReviewEditIn => ({
  level: null,
  reasonBullets: null,
  fixParagraph: null,
  ...over,
});

async function items(store: ReturnType<typeof setup>['store']) {
  return ((await store.getResult(RUN)) as ScanResult).items;
}

describe('목 저장소의 고침 규칙', () => {
  it('정규화: 앞뒤 공백·빈 항목을 지우고, AI 값과 같은 칸은 null, 셋 다 null 인 문장은 빠진다', async () => {
    const { store } = setup();
    const ai = await items(store);
    const saved = await store.putReview(RUN, {
      marks: [],
      edits: [
        flat({
          itemIndex: 0,
          level: ai[0]!.level, // AI 와 같음 → null
          reasonBullets: ['  고친 사유  ', '   ', ''],
          fixParagraph: `  ${ai[0]!.fixParagraph}  `, // strip 하면 AI 와 같음 → null
        }),
        flat({ itemIndex: 1, level: ai[1]!.level }), // 셋 다 null → 빠짐
      ],
    });
    expect(saved).toMatchObject({
      state: 'in_review',
      edits: [
        {
          itemIndex: 0,
          level: null,
          reasonBullets: {
            value: ['고친 사유'],
            editedAt: '2026-10-22T14:00:00+09:00',
            editedBy: { id: 1, name: '김하나' },
          },
          fixParagraph: null,
        },
      ],
    });
  });

  it('AI 와 같은 값만 보내면 고침 없음 — 상태 그대로(pending)', async () => {
    const { store } = setup();
    const ai = await items(store);
    const saved = (await store.putReview(RUN, {
      marks: [],
      edits: [flat({ itemIndex: 0, level: ai[0]!.level })],
    })) as { state: string; edits: unknown[] };
    expect(saved.state).toBe('pending');
    expect(saved.edits).toEqual([]);
  });

  it('칸마다 때·사람: 값이 바뀐 칸만 새로, edits 생략(채택)은 고침 그대로, [] 는 다 지움', async () => {
    const ai0 = (await items(setup().store))[0]!.level;
    const { store, tick } = setup();
    // AI 등급이 아닌 둘
    const [one, two] = (['High', 'Mid', 'Low'] as const).filter(
      (level) => level !== ai0,
    ) as ['High' | 'Mid' | 'Low', 'High' | 'Mid' | 'Low'];
    const first = (await store.putReview(RUN, {
      marks: [],
      edits: [flat({ itemIndex: 0, level: one, fixParagraph: '고친 방향' })],
    })) as {
      edits: {
        level: { editedAt: string };
        fixParagraph: { editedAt: string };
      }[];
    };
    expect(first.edits[0]!.level.editedAt).toBe('2026-10-22T14:00:00+09:00');
    tick(30);
    const second = (await store.putReview(RUN, {
      marks: [],
      edits: [flat({ itemIndex: 0, level: two, fixParagraph: '고친 방향' })],
    })) as typeof first;
    expect(second.edits[0]!.level.editedAt).toBe('2026-10-22T14:30:00+09:00');
    expect(second.edits[0]!.fixParagraph.editedAt).toBe(
      '2026-10-22T14:00:00+09:00',
    );
    const adopted = (await store.putReview(RUN, {
      marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
    })) as typeof first;
    expect(adopted.edits).toEqual(second.edits);
    const cleared = (await store.putReview(RUN, {
      marks: [{ itemIndex: 0, decision: 'adopted', excludeReason: null }],
      edits: [],
    })) as { edits: unknown[]; marks: unknown[] };
    expect(cleared.edits).toEqual([]);
    expect(cleared.marks).toHaveLength(1);
  });

  it('잘못이면 rejected(서버 400): 빈 사유·빈 수정 방향·범위 밖·겹친 번호·상한 넘음. 검토는 그대로', async () => {
    const { store } = setup();
    const bad: ReviewEditIn[][] = [
      [flat({ itemIndex: 0, reasonBullets: [' ', ''] })],
      [flat({ itemIndex: 0, fixParagraph: '   ' })],
      [flat({ itemIndex: 99, level: 'Low' })],
      [
        flat({ itemIndex: 0, level: 'Low' }),
        flat({ itemIndex: 0, level: 'Mid' }),
      ],
      [
        flat({
          itemIndex: 0,
          reasonBullets: Array.from({ length: 11 }, (_, i) => `${i}`),
        }),
      ],
      [flat({ itemIndex: 0, reasonBullets: ['가'.repeat(501)] })],
      [flat({ itemIndex: 0, fixParagraph: '가'.repeat(2001) })],
    ];
    for (const edits of bad) {
      const error = await store.putReview(RUN, { marks: [], edits }).then(
        () => null,
        (e: unknown) => e,
      );
      expect(error).toBeInstanceOf(StoreError);
      expect((error as StoreError).kind).toBe('rejected');
    }
    expect(await store.getReview(RUN)).toMatchObject({
      state: 'pending',
      edits: [],
    });
  });

  it('확정 PUT 의 edits 는 저장된 뒤 잠기고, 확정 뒤 edits 는 review_locked', async () => {
    const { store } = setup();
    const confirmed = (await store.putReview(RUN, {
      state: 'confirmed',
      marks: [],
      edits: [flat({ itemIndex: 0, fixParagraph: '고친 방향' })],
    })) as { state: string; edits: unknown[] };
    expect(confirmed.state).toBe('confirmed');
    expect(confirmed.edits).toHaveLength(1);
    const error = await store.putReview(RUN, { marks: [], edits: [] }).then(
      () => null,
      (e: unknown) => e,
    );
    expect((error as StoreError).kind).toBe('review_locked');
    expect(
      ((await store.getReview(RUN)) as { edits: unknown[] }).edits,
    ).toHaveLength(1);
  });

  it('목록 levelCounts 는 효력 등급 — 등급을 고치면 AI 등급 −1·고친 등급 +1', async () => {
    const { store } = setup();
    const ai = await items(store);
    const before = (await store.listCheckRows()).runs.find(
      (run) => run.runId === RUN,
    )!.levelCounts!;
    const from = ai[0]!.level;
    const to = from === 'Low' ? 'High' : 'Low';
    await store.putReview(RUN, {
      marks: [],
      edits: [flat({ itemIndex: 0, level: to })],
    });
    const after = (await store.listCheckRows()).runs.find(
      (run) => run.runId === RUN,
    )!.levelCounts!;
    expect(after).toEqual({
      ...before,
      [from]: before[from] - 1,
      [to]: before[to] + 1,
    });
    // 결과(AI 원본)는 그대로
    expect((await items(store))[0]!.level).toBe(from);
  });
});

// 밴드 GMK1(sid:MARC-ISSUE-477): 서버 GRV1(actions/review.py _checked_edits)과 같은 견줌·다듬기 전 그물·코드 포인트 셈.
describe('서버 GRV1 과 같은 고침 규칙', () => {
  const NOW = {
    at: '2026-10-22T14:00:00+09:00',
    by: { id: 1, name: '김하나' },
  };
  /** AI 값이 지저분한 결과(문장 하나). 값은 지어낸 것이다. */
  async function dirtyResult(): Promise<ScanResult> {
    const result = (await setup().store.getResult(RUN)) as ScanResult;
    return {
      ...result,
      items: [
        {
          ...result.items[0]!,
          reasonBullets: ['  지어낸 사유 하나  ', '   ', '지어낸 사유 둘\n'],
          fixParagraph: '\n  지어낸 수정 방향  ',
        },
      ],
    };
  }
  const put = async (over: Partial<ReviewEditIn>) =>
    nextEdits(await dirtyResult(), [], [flat({ itemIndex: 0, ...over })], NOW);
  // 코드 포인트 하나가 UTF-16 둘인 글자(CJK 확장 B)
  const wide = (n: number) => '\u{20000}'.repeat(n);

  it('지저분한 AI 값을 그대로 보내면 고침 0(화면이 AI 값을 그대로 보낸 PUT)', async () => {
    const result = await dirtyResult();
    const ai = result.items[0]!;
    expect(
      nextEdits(
        result,
        [],
        [
          {
            itemIndex: 0,
            level: ai.level,
            reasonBullets: [...ai.reasonBullets],
            fixParagraph: ai.fixParagraph,
          },
        ],
        NOW,
      ),
    ).toEqual([]);
  });

  it('진짜 고침은 남는다 — 한 칸만 고치면 그 칸만, 값은 다듬은 값', async () => {
    const result = await dirtyResult();
    const ai = result.items[0]!;
    expect(
      nextEdits(
        result,
        [],
        [
          {
            itemIndex: 0,
            level: ai.level,
            reasonBullets: [...ai.reasonBullets],
            fixParagraph: '  고친 수정 방향  ',
          },
        ],
        NOW,
      ),
    ).toEqual([
      {
        itemIndex: 0,
        level: null,
        reasonBullets: null,
        fixParagraph: {
          value: '고친 수정 방향',
          editedAt: NOW.at,
          editedBy: NOW.by,
        },
      },
    ]);
  });

  it('AI 값이 꼴이 다르면 날것끼리 견준다(값이 있으면 고침으로 남음)', async () => {
    const result = await dirtyResult();
    const broken = {
      ...result,
      items: [
        {
          ...result.items[0]!,
          reasonBullets: null,
          fixParagraph: null,
        },
      ],
    } as unknown as ScanResult;
    const out = nextEdits(
      broken,
      [],
      [flat({ itemIndex: 0, reasonBullets: ['가'], fixParagraph: '나' })],
      NOW,
    ) as ReviewEdit[];
    expect(out[0]!.reasonBullets?.value).toEqual(['가']);
    expect(out[0]!.fixParagraph?.value).toBe('나');
  });

  it.each([
    [
      '원래 51항목(공백뿐) → 빈 사유 문장이 아니라 10줄 문장',
      { reasonBullets: Array.from({ length: 51 }, () => ' ') },
      '판정 사유는 10줄까지 쓸 수 있어요',
    ],
    [
      '원래 한 줄 1001자(공백뿐) → 빈 사유 문장이 아니라 500자 문장',
      { reasonBullets: [' '.repeat(1001)] },
      '판정 사유는 한 줄에 500자까지 쓸 수 있어요',
    ],
    [
      '원래 수정 방향 4001자(공백뿐) → 빈 글 문장이 아니라 2000자 문장',
      { fixParagraph: ' '.repeat(4001) },
      '수정 방향은 2000자까지 쓸 수 있어요',
    ],
  ])('다듬기 전 그물: %s', async (_name, over, message) => {
    expect(await put(over)).toBe(message);
  });

  it('그물 경계값(원래 50항목·줄 1000자·수정 방향 4000자)은 지나 다듬기 뒤 값으로 저장', async () => {
    const out = (await put({
      reasonBullets: [
        ...Array.from({ length: 49 }, () => ' '),
        `${' '.repeat(998)}가`,
      ],
      fixParagraph: `${' '.repeat(3999)}나`,
    })) as ReviewEdit[];
    expect(out[0]!.reasonBullets?.value).toEqual(['가']);
    expect(out[0]!.fixParagraph?.value).toBe('나');
  });

  it('글자 수는 코드 포인트 — UTF-16 둘인 글자도 500자·2000자·그물까지 한 글자로 센다', async () => {
    const ok = (await put({
      reasonBullets: [wide(500)],
      fixParagraph: wide(2000),
    })) as ReviewEdit[];
    expect(ok[0]!.reasonBullets?.value).toEqual([wide(500)]);
    expect(ok[0]!.fixParagraph?.value).toBe(wide(2000));
    expect(await put({ reasonBullets: [wide(501)] })).toBe(
      '판정 사유는 한 줄에 500자까지 쓸 수 있어요',
    );
    expect(await put({ fixParagraph: wide(2001) })).toBe(
      '수정 방향은 2000자까지 쓸 수 있어요',
    );
    // 그물: 공백 999 + 넓은 글자 1 = 코드 포인트 1000(지남), UTF-16 1001
    const raw = (await put({
      reasonBullets: [`${' '.repeat(999)}${wide(1)}`],
    })) as ReviewEdit[];
    expect(raw[0]!.reasonBullets?.value).toEqual([wide(1)]);
  });

  it('시험용 가짜 서버도 같은 규칙: 지저분한 AI 값 그대로 → 고침 0, 그물 넘음 → 400 INVALID_REVIEW(rejected)', async () => {
    const server = listedGreenwashServer();
    const run = server.runs.get(5)!;
    run.result = await dirtyResult();
    run.review = { ...run.review!, state: 'pending', edits: [] };
    const { store } = serverStoreOf(server);
    const ai = run.result.items[0]!;
    const saved = (await store.putReview('5', {
      marks: [],
      edits: [
        {
          itemIndex: 0,
          level: ai.level,
          reasonBullets: [...ai.reasonBullets],
          fixParagraph: ai.fixParagraph,
        },
      ],
    })) as { edits: unknown[] };
    expect(saved.edits).toEqual([]);
    const error = await store
      .putReview('5', {
        marks: [],
        edits: [flat({ itemIndex: 0, fixParagraph: ' '.repeat(4001) })],
      })
      .then(
        () => null,
        (e: unknown) => e,
      );
    expect((error as StoreError).kind).toBe('rejected');
  });
});
