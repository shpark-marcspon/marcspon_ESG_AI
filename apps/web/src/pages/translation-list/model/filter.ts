// 목록 화면 거르기(밴드 TRP2 TE2, 시안 TR-01 「파일명 검색」). 서버 목록 인자에 검색이 없어 받은 줄(첫 20줄) 안에서 거른다
// (데이터 검증 목록 pages/dataverify-list/model/filter.ts 꼴). 순수 함수.

/** 파일명에 검색어가 든 줄만(대소문자 무시, 앞뒤 빈칸 무시). 검색어가 비면 그대로. */
export function filterByFileName<T extends { fileName: string }>(
  rows: readonly T[],
  query: string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (needle === '') return [...rows];
  return rows.filter((row) => row.fileName.toLowerCase().includes(needle));
}
