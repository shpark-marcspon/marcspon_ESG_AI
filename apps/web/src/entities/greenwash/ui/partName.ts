// 서버 파트 이름 → 화면 이름(디자인 결정 (나), sid:MARC-ISSUE-314). 짝은 model SERVER_PART_NAMES 와 문구 표 newCheck.parts.names 둘.
// 화면에 서버의 파트 이름이 나가는 자리(GW-04 파트 표·단어 탭 · GW-05 파트 탭·줄 meta·상세 배지·05a 인용 meta)는 이것을 거친다.
// 고르기·거르기 값은 서버 이름 그대로 둔다(보이는 글만 바꾼다).
import { GW_TEXT } from '../config/text.ts';
import { partKeyOf } from '../model/index.ts';

/** 서버 파트 이름의 화면 이름. 모르는 이름은 그대로. */
export function partName(serverName: string): string {
  const key = partKeyOf(serverName);
  return key === null ? serverName : GW_TEXT.newCheck.parts.names[key];
}
