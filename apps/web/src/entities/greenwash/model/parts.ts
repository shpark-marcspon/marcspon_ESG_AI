// 파트 셋과 파트별 쪽 집합(밴드 FW1b ①, 시안 GW-02_r1 카드 2).
// 파트: CEO 메시지 · 회사소개 · 기후·환경. 키 이름은 화면 안의 이름이다(계약 값이 정해지면 바꾼다. 무효 조건: GC1·실행 입력 꼴).
// 한 쪽이 두 파트에 들 수 있다(겹친 쪽). 점검할 쪽 합계는 합집합의 수다(시안: 4~5 + 5~14 + 25~37·55~74 → 44쪽).
import { sortPages } from './pageRange.ts';

export const PART_KEYS = ['ceo', 'company', 'climate'] as const;
export type PartKey = (typeof PART_KEYS)[number];

export type PartPages = Readonly<Record<PartKey, readonly number[]>>;

/**
 * 서버가 결과·엑셀에 쓰는 파트 이름(greenwash.result@1 parts[].name — 서버 차례). 화면 이름은 문구 표 newCheck.parts.names 다
 * (기후·환경 — 디자인 결정 (나), sid:MARC-ISSUE-314: 화면만 바꾸고 서버 계약·엑셀 글자는 그대로). 짝은 이 둘뿐이다.
 */
export const SERVER_PART_NAMES: Readonly<Record<PartKey, string>> = {
  ceo: 'CEO 메시지',
  company: '회사소개',
  climate: '기후/환경 토픽',
};

/** 서버 파트 이름 → 파트 키. 모르는 이름이면 null(화면은 서버 글자 그대로). */
export function partKeyOf(serverName: string): PartKey | null {
  return PART_KEYS.find((key) => SERVER_PART_NAMES[key] === serverName) ?? null;
}

export const EMPTY_PARTS: PartPages = { ceo: [], company: [], climate: [] };

/** 세 파트의 합집합(오름차순). */
export function unionPages(parts: PartPages): number[] {
  return sortPages(PART_KEYS.flatMap((key) => parts[key]));
}

/** 점검할 쪽 합계(합집합의 수). */
export function totalPages(parts: PartPages): number {
  return unionPages(parts).length;
}

/** 두 파트 이상에 든 쪽(오름차순). */
export function overlapPages(parts: PartPages): number[] {
  const seen = new Map<number, number>();
  for (const key of PART_KEYS)
    for (const page of new Set(parts[key]))
      seen.set(page, (seen.get(page) ?? 0) + 1);
  return sortPages([...seen].filter(([, n]) => n > 1).map(([page]) => page));
}

/** 한 쪽이 든 파트들(PART_KEYS 차례). */
export function partsOfPage(parts: PartPages, page: number): PartKey[] {
  return PART_KEYS.filter((key) => parts[key].includes(page));
}

/** 이 파트의 쪽 가운데 다른 파트와 겹친 쪽. */
export function overlapOf(parts: PartPages, part: PartKey): number[] {
  const others = new Set(
    PART_KEYS.filter((key) => key !== part).flatMap((key) => parts[key]),
  );
  return sortPages(parts[part].filter((page) => others.has(page)));
}

/** 세 파트가 모두 비었는가. */
export function allPartsEmpty(parts: PartPages): boolean {
  return PART_KEYS.every((key) => parts[key].length === 0);
}
