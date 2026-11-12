// 손으로 쓴 결과·검토 꼴(result.ts)이 계약의 생성 타입(apps/api-py/generated/api.d.ts)과 양방향으로 같은가(밴드 WC1 ① 2).
// 재는 것은 tsc 다(typecheck 단계): 아래 Expect<Equal<…>> 가 하나라도 거짓이면 타입 오류다. vitest 는 빈 시험 하나만 돈다.
// 생성 타입은 src/api 의 공개 표면(api/index.ts 가 다시 내보내는 domain 의 Schemas)으로만 가져온다 — api.d.ts 를 직접 가져오지 않는다
// (app/guards/layers.test.ts). entities/greenwash/model 에서 바깥 파일을 가져오는 것은 이 시험 파일의 `import type` 하나뿐이다(같은 시험).
//
// 견주기 전에 두 쪽을 같은 꼴로 편다(Plain): 배열·튜플은 readonly 로, 객체 칸의 readonly 는 뗀다. 손으로 쓴 꼴은 배열을 readonly 로
// 두고 생성 타입은 그냥 배열이라, 그 차이만은 같다고 본다. 이름·nullable·optional·리터럴의 차이는 그대로 잡힌다.
// 생성 타입과 다른 칸(아래 KNOWN_DIFFERENCES — 이름·nullable 차이는 없고, 손으로 쓴 꼴이 더 좁은 곳 둘)은 고치지 않고 보고했다: 다른 칸을 뺀 나머지가 같은지, 다른 칸이 지금 그 꼴인지를 따로 단언한다
// — 둘 중 어느 쪽이 바뀌어도 tsc 가 빨갛다.
import { describe, expect, it } from 'vitest';

import type { Schemas } from '../../../shared/api/index.ts';
import type {
  DryRunResult,
  EvidenceAdded,
  GreenwashReview,
  Rejudged,
  ResultItem,
  ReviewEdit,
  ReviewEditIn,
  ReviewEditedFix,
  ReviewEditedLevel,
  ReviewEditedReasons,
  ReviewEvidence,
  ReviewEvidenceIn,
  ReviewMark,
  ReviewRejudge,
  ReviewReviewer,
  ReviewUpdate,
  ScanResult,
} from './result.ts';

type Equal<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true
  : false;
type Expect<T extends true> = T;

/** 배열·튜플은 readonly, 객체 칸은 readonly 를 뗀다(속까지). 함수는 없다. */
type Plain<T> =
  T extends readonly unknown[] ? { readonly [K in keyof T]: Plain<T[K]> }
  : T extends object ? { -readonly [K in keyof T]: Plain<T[K]> }
  : T;

type Same<A, B> = Equal<Plain<A>, Plain<B>>;

// ── 검토 greenwash.review@3 · PUT 본문 ──
export type ReviewChecks = [
  Expect<Same<GreenwashReview, Schemas['GreenwashReviewState']>>,
  Expect<Same<ReviewMark, Schemas['GreenwashReviewMark']>>,
  Expect<Same<ReviewReviewer, Schemas['GreenwashReviewer']>>,
  Expect<Same<ReviewUpdate, Schemas['GreenwashReviewUpdate']>>,
  // review@2 의 고침(G1b-3 ①)
  Expect<Same<ReviewEdit, Schemas['GreenwashReviewEdit']>>,
  // review@3 의 근거 고침·재판단(GRJ1)
  Expect<Same<ReviewEvidence, Schemas['GreenwashReviewEvidence']>>,
  Expect<Same<ReviewEvidenceIn, Schemas['GreenwashReviewEvidenceIn']>>,
  Expect<Same<EvidenceAdded, Schemas['GreenwashEvidenceAdded']>>,
  Expect<Same<ReviewRejudge, Schemas['GreenwashReviewRejudge']>>,
  Expect<Same<Rejudged, Schemas['GreenwashRejudged']>>,
  Expect<Same<ReviewEditedLevel, Schemas['GreenwashReviewEditedLevel']>>,
  Expect<Same<ReviewEditedReasons, Schemas['GreenwashReviewEditedReasons']>>,
  Expect<Same<ReviewEditedFix, Schemas['GreenwashReviewEditedFix']>>,
  Expect<Same<ReviewEditIn, Schemas['GreenwashReviewEditIn']>>,
];

// ── 결과 greenwash.result@1 ──
// KNOWN_DIFFERENCES(손으로 쓴 꼴이 더 좁다 — 거울도 그 꼴로 지킨다. 고치지 않고 보고, 밴드 WC1 ①):
//   1. position.boxes  손: readonly Box[](Box = 수 넷의 튜플)   생성: number[][](openapi-typescript 가 길이 넷을 싣지 않는다)
//   2. DryRunResult.items  손: readonly [](빈 튜플)   생성: Item[](스키마 설명에만 「빈 목록」)
//   3. ScanResult.items·DryRunResult.items 는 1 때문에 Item 이 달라 같이 다르다 — 칸을 뺀 나머지와 Item 의 나머지를 따로 본다.
type Position = NonNullable<ResultItem['position']>;
type GenPosition = Schemas['Position'];

export type ResultChecks = [
  // 다른 칸을 뺀 나머지는 같다
  Expect<Same<Omit<ResultItem, 'position'>, Omit<Schemas['Item'], 'position'>>>,
  Expect<Same<Omit<Position, 'boxes'>, Omit<GenPosition, 'boxes'>>>,
  Expect<Same<Omit<ScanResult, 'items'>, Omit<Schemas['ScanResult'], 'items'>>>,
  Expect<
    Same<Omit<DryRunResult, 'items'>, Omit<Schemas['DryRunResult'], 'items'>>
  >,
  // 다른 칸은 지금 이 꼴이다(어느 쪽이 바뀌어도 빨강)
  Expect<Equal<ResultItem['position'], Position | null>>,
  Expect<Equal<Schemas['Item']['position'], GenPosition | null>>,
  Expect<
    Equal<
      Plain<Position['boxes']>,
      readonly (readonly [number, number, number, number])[]
    >
  >,
  Expect<Equal<GenPosition['boxes'], number[][]>>,
  Expect<Equal<ScanResult['items'], readonly ResultItem[]>>,
  Expect<Equal<Schemas['ScanResult']['items'], Schemas['Item'][]>>,
  Expect<Equal<DryRunResult['items'], readonly []>>,
  Expect<Equal<Schemas['DryRunResult']['items'], Schemas['Item'][]>>,
  // 손으로 쓴 꼴은 생성 타입 안에 든다(더 좁을 뿐 어긋나지 않는다)
  Expect<
    Plain<Position['boxes']> extends Plain<GenPosition['boxes']> ? true : false
  >,
];

describe('결과·검토 꼴 = 생성 타입', () => {
  it('tsc 가 잰다(이 파일의 Expect<…>)', () => {
    expect(true).toBe(true);
  });
});
