// 코드로 만든 가짜 행. 씨앗이 같으면 늘 같은 행이 나온다. 실제 자료가 아니다(품목·수량·계수 전부 지어낸 값).
// 상태와 후보 수가 섞이게 만든다: 후보 0~3개, 일곱 상태 전부, 배출량을 계산하지 못한 후보.
import type { TableInputJson } from '../../widgets/review-table/index.ts';

type RowJson = TableInputJson['rows'][number];
type CandidateJson = RowJson['ai']['candidates'][number];

export const FAKE_CATEGORIES = [
  '구매한 제품과 서비스',
  '자본재',
  '업스트림 운송',
  '출장',
  '통근',
  '다운스트림 운송',
];

const ITEMS = [
  '수지 원료',
  '강판',
  '포장 상자',
  '윤활유',
  '전선',
  '볼트',
  '도료',
  '유리판',
  '고무 패킹',
  '알루미늄 봉',
  '화물 운송',
  '출장 항공',
  '통근 버스',
  '사무 용지',
  '세척제',
  '모터',
];
const UNITS = ['kg', 't', '개', 'km', '건'];
const SOURCES = ['가짜 계수표 A', '가짜 계수표 B'];
const REASONS = [
  '품목 이름과 계수 이름이 같다',
  '재질이 같은 계수다',
  '상위 분류의 평균 계수다',
  '용도가 비슷한 계수다',
];
const CONFIDENCES = ['high', 'medium', 'low'] as const;

/** 작은 난수 발생기(mulberry32). 씨앗이 같으면 같은 수열. */
function random(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round1 = (value: number) => Math.round(value * 10) / 10;

export function makeFakeInput(count: number, seed = 20261005): TableInputJson {
  const next = random(seed);
  const pick = <T>(list: readonly T[]): T =>
    list[Math.floor(next() * list.length)]!;
  const rows: RowJson[] = [];

  for (let i = 0; i < count; i++) {
    const quantity = Math.floor(next() * 5000) + 1;
    const draw = next();
    const candidateCount =
      draw < 0.08 ? 0
      : draw < 0.58 ? 1
      : draw < 0.85 ? 2
      : 3;
    const itemName = `${pick(ITEMS)} ${String(i + 1).padStart(4, '0')}`;

    const candidates: CandidateJson[] = [];
    for (let c = 0; c < candidateCount; c++) {
      // 스무 개에 하나꼴로 값이 없는 계수: 그 후보는 배출량을 계산하지 못한다.
      const factorValue = next() < 0.05 ? null : round1(next() * 9 + 0.1);
      candidates.push({
        id: `f${i + 1}-${c + 1}`,
        factorName: `가짜 계수 ${Math.floor(next() * 900) + 100}`,
        factorValue,
        factorUnit: 'kgCO2e/단위',
        source: pick(SOURCES),
        // 셋에 하나는 이유·신뢰도가 없다(실제 자료에도 없는 행이 있다).
        ...(next() < 0.67 ?
          { reason: pick(REASONS), confidence: pick(CONFIDENCES) }
        : {}),
        // 수량 × 계수는 kgCO2e 다. 톤으로 한 번만 나눈다(kg 에서 0.1 로 자른 뒤 ÷1000 — 톤에서 다시 자르지 않는다).
        emission:
          factorValue === null ? null : round1(quantity * factorValue) / 1000,
      });
    }

    rows.push({
      id: `row-${String(i + 1).padStart(4, '0')}`,
      raw: { itemName, quantity, unit: pick(UNITS) },
      processing: candidateCount === 0 ? '후보 없음' : '결과 생성',
      ai: {
        category: next() < 0.03 ? null : pick(FAKE_CATEGORIES),
        candidates,
      },
      review: fakeReview(next(), candidates),
    });
  }

  return {
    version: 2,
    unit: 'tCO2eq',
    notice:
      '코드로 만든 가짜 행이다. 배출량(tCO2eq)은 수량 × 가짜 계수(kgCO2e/단위) ÷ 1000 이다.',
    categories: FAKE_CATEGORIES,
    rows,
  };
}

/** 열에 일곱은 검토대기, 나머지는 다른 상태들. 조건이 안 맞으면(후보가 없는데 반영 등) 검토대기로 둔다. */
function fakeReview(
  draw: number,
  candidates: readonly CandidateJson[],
): RowJson['review'] {
  const first = candidates[0];
  const second = candidates[1];
  if (draw < 0.7) return { status: 'pending' };
  if (draw < 0.8) return first ? { status: 'accepted' } : { status: 'pending' };
  if (draw < 0.84)
    return second ?
        {
          status: 'edited',
          edit: { candidateId: second.id, emission: second.emission },
        }
      : { status: 'pending' };
  if (draw < 0.88) return { status: 'declined' };
  if (draw < 0.91) return { status: 'rerequested' };
  if (draw < 0.95)
    return { status: 'rejected', rejectReason: '품목과 맞는 계수가 없다' };
  return first && first.emission !== null ?
      { status: 'finalized' }
    : { status: 'pending' };
}
