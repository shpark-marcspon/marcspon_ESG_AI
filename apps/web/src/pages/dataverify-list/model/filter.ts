// 검증 목록의 화면 거르기(밴드 DV2b — 순수 함수, DOM·글을 모른다). 파일명 검색·보고연도는 서버 인자가 없어 받은 쪽(새 것 20건) 안에서만
// 거른다(사용자 10-23 (다) — 그린워싱 filterCheckRows 꼴, 서버 검색은 2차 sid:MARC-ENT-432). 상태·「내가 올린 것만」은 서버 인자다.
import type { RunStatus } from '../../../entities/dataverify/model/index.ts';

/** 상태 탭(판 DV-01 — 「대기·처리 중」은 상태 둘을 한 요청으로, QB3 (가)). */
export const LIST_TABS = ['all', 'active', 'done', 'failed'] as const;
export type ListTab = (typeof LIST_TABS)[number];

/** 탭 → 서버 status 인자(전체는 없음). */
export function statusesOf(tab: ListTab): RunStatus[] | undefined {
  switch (tab) {
    case 'all':
      return undefined;
    case 'active':
      return ['queued', 'processing'];
    default:
      return [tab];
  }
}

export interface ScreenFilter {
  /** 파일명 검색 글(앞뒤 빈칸 빼고, 대소문자 가리지 않음). */
  query: string;
  /** 보고연도(글자 — 서버 reportingYear 그대로). null 이면 전체. */
  year: string | null;
}

export const NO_SCREEN_FILTER: ScreenFilter = { query: '', year: null };

/** 거를 줄의 꼴: 화면에 보이는 파일명 글(붙여 넣은 줄은 「붙여 넣은 데이터 · 시각」)과 보고연도. */
export interface Filterable {
  label: string;
  reportingYear: string | null;
}

export function filterRows<T extends Filterable>(
  rows: readonly T[],
  filter: ScreenFilter,
): T[] {
  const query = filter.query.trim().toLowerCase();
  return rows.filter(
    (row) =>
      (query === '' || row.label.toLowerCase().includes(query)) &&
      (filter.year === null || row.reportingYear === filter.year),
  );
}

/** 보고연도 고르기의 값들(받은 줄에 있는 것만, 새 해 먼저). */
export const yearsOf = (rows: readonly Filterable[]) =>
  [
    ...new Set(
      rows.flatMap((row) =>
        row.reportingYear === null ? [] : [row.reportingYear],
      ),
    ),
  ].sort((a, b) => b.localeCompare(a));
