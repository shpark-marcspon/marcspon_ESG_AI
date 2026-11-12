// 결과 요약의 셈(밴드 FW2 ①, 시안 GW-04_r1·메모 gw-c-04a~c). 순수 함수만.
//   - 등급별 수: items 로 세고, 결과의 counts 와 맞는지도 낸다(서버 counts 는 items 를 다시 센 것 — 어긋나면 화면은 items 를 믿는다).
//   - 파트별 등급 수: 한 쪽이 두 파트에 들면 그 문장은 두 파트에 다 센다(서버 byPart 와 같은 셈). 그래서 합이 전체보다 클 수 있다.
//   - 단어 빈도: 문서 전체 = wordCounts.total, 파트별 = wordCounts.pages 를 그 파트의 쪽으로 묶어 더한 것(gw-c-04c).
//   - 「추가」 표시 [R1]: 추가 단어이고 기본 목록 단어가 아닐 때만(서버 frequency_extras 는 기본 목록과 겹친 추가 단어를 빈도에
//     더하지 않는다 — 그 줄은 기본 단어의 줄이다). 견주는 키는 termKey(서버 term_key 와 같다).
//   - 효력 등급(밴드 G1b-3 ③ — 디자인 80 회신 Q8): 등급 합·파트 × 등급은 고친 등급 ?? AI 등급으로 센다. 검토의 edits 를 받아
//     items 의 사본에 고친 등급을 얹어 센다(결과는 그대로). 세는 대상(items 전부)은 그대로. edits 를 안 주면(검토를 아직 못 읽음) AI 셈.
//     countsAgree 는 서버 counts(AI 셈)와 견주므로 늘 AI 셈이다.
//   - 기준 판단(밴드 GRJ1 ③ — 검증 3 B1): 효력 등급 = 고친 등급 ?? 기준 판단(가장 늦은 done 재판단) ?? 첫 판단. 고르기는 entities/greenwash/model
//     joinReview 의 shownLevel 한 곳(서버 checks levelCounts·확정 엑셀과 같은 뜻). 리스크 아님(null)은 세 등급 밖.
import {
  joinReview,
  termKey,
} from '../../../entities/greenwash/model/index.ts';
import { LEVELS } from '../../../entities/greenwash/model/index.ts';
import type {
  GreenwashResult,
  Level,
  LevelCounts,
  ResultItem,
  ReviewEdit,
  ReviewRejudge,
  TermCount,
} from '../../../entities/greenwash/model/index.ts';

const zero = (): LevelCounts => ({ High: 0, Mid: 0, Low: 0 });

/** 문장마다 효력 등급(joinReview 의 shownLevel — 고친 등급 ?? 기준 판단 ?? 첫 판단, 리스크 아님은 null)과 그 item. */
function effectiveLevels(
  items: readonly ResultItem[],
  edits: readonly ReviewEdit[],
  rejudges: readonly ReviewRejudge[],
): { item: ResultItem; level: Level | null }[] {
  return joinReview(items, [], edits, [], rejudges).map((row) => ({
    item: row.item,
    level: row.shownLevel,
  }));
}

function countLevels(levels: readonly (Level | null)[]): LevelCounts {
  const counts = zero();
  for (const level of levels) if (level !== null) counts[level] += 1;
  return counts;
}

/** items 를 등급별로 센다. edits·rejudges 를 주면 효력 등급(고친 등급 ?? 기준 판단 ?? AI)으로, 리스크 아님은 세지 않는다. */
export function levelCountsOf(
  items: readonly ResultItem[],
  edits: readonly ReviewEdit[] = [],
  rejudges: readonly ReviewRejudge[] = [],
): LevelCounts {
  return countLevels(
    effectiveLevels(items, edits, rejudges).map((row) => row.level),
  );
}

/** 결과의 counts(서버 셈)가 items 를 다시 센 것과 맞는가. dry-run(counts 없음)이면 true. */
export function countsAgree(result: GreenwashResult): boolean {
  if (result.counts === null) return true;
  const mine = levelCountsOf(result.items);
  return (
    result.counts.total === result.items.length &&
    LEVELS.every((level) => result.counts!.byLevel[level] === mine[level])
  );
}

export interface PartSummary {
  /** 결과의 parts[].name 그대로. */
  name: string;
  pages: readonly number[];
  counts: LevelCounts;
  /** 이 파트의 문장 수(등급 합). */
  total: number;
}

/**
 * 파트별 등급 수(결과의 parts 차례). 문장의 parts 에 이름이 들면 센다 — 두 파트에 든 문장은 두 번 센다.
 * edits 를 주면 효력 등급으로(levelCountsOf 와 같다).
 */
export function partSummaries(
  result: GreenwashResult,
  edits: readonly ReviewEdit[] = [],
  rejudges: readonly ReviewRejudge[] = [],
): PartSummary[] {
  const rows = effectiveLevels(result.items, edits, rejudges);
  return result.parts.map((part) => {
    const counts = countLevels(
      rows
        .filter((row) => row.item.parts.includes(part.name))
        .map((row) => row.level),
    );
    return {
      name: part.name,
      pages: part.pages,
      counts,
      total: counts.High + counts.Mid + counts.Low,
    };
  });
}

/** 단어 빈도의 범위: 문서 전체이거나 파트 하나(이름). */
export type TermScope = { kind: 'total' } | { kind: 'part'; name: string };

/**
 * 단어 빈도. 문서 전체는 wordCounts.total 그대로. 파트는 그 파트의 쪽에 든 wordCounts.pages 를 낱말마다 더한다
 * (많은 차례, 같으면 처음 나온 차례 — 쪽 차례, 쪽 안에서는 서버 차례). 없는 파트 이름이면 빈 목록.
 */
export function termFrequency(
  result: GreenwashResult,
  scope: TermScope,
): TermCount[] {
  if (scope.kind === 'total') return result.wordCounts.total.map(copy);
  const part = result.parts.find((p) => p.name === scope.name);
  if (!part) return [];
  const inPart = new Set(part.pages);
  const summed = new Map<string, number>();
  for (const page of result.wordCounts.pages) {
    if (!inPart.has(page.page)) continue;
    for (const { term, count } of page.counts)
      summed.set(term, (summed.get(term) ?? 0) + count);
  }
  return [...summed]
    .map(([term, count]) => ({ term, count }))
    .sort((a, b) => b.count - a.count);
}
const copy = (row: TermCount): TermCount => ({ ...row });

/** 빈도 줄에 「추가」를 붙이는가 [R1]: 키가 추가 단어에 있고 기본 목록에는 없을 때만. */
export function isExtraTermRow(
  term: string,
  extraTerms: readonly string[],
  defaultTerms: readonly string[],
): boolean {
  const key = termKey(term);
  return (
    extraTerms.some((extra) => termKey(extra) === key) &&
    !defaultTerms.some((base) => termKey(base) === key)
  );
}

/** 인식 실패 페이지 — entities 의 같은 함수(GW-03 끝남도 쓴다, 밴드 GW2R ②). 이 표면의 이름은 그대로 둔다. */
export { failedPagesOf } from '../../../entities/greenwash/model/index.ts';
