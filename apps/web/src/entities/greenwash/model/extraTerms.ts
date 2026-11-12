// 단어 키(밴드 FW1b ②·FW2 ⓪). 서버 term_key(apps/api-py/esgapi/greenwash/engines/e0/gw1.py)와 같은 꼴로 낱말을 견준다:
//   소문자 → 앞뒤 공백 지움 → 「- _ / · • ∙」 여섯을 공백으로 → 이어진 공백을 하나로 → 앞뒤 공백 지움 → 공백을 모두 지움.
//   그래서 「탄소 중립」「탄소-중립」「탄소중립」「Tanso Jungrip」은 각각 같은 꼴끼리 같다(「eco」 와 「eco프리」 는 다르다).
// 쓰는 곳: GW-04 단어 빈도의 「추가」 가름(옛 실행의 extraTerms), 목 결과 짓기.
// 추가 단어 판정(checkExtraTerm·30자·30개·괄호 오류)은 밴드 GW2R ② 에서 걷었다 — 대상 단어가 읽기 전용이 되어(v115 GW-02_r2,
//   sid:MARC-ENT-360 3 안2) 화면이 추가 단어를 받지 않는다(검증 권고 R2).

/** 낱말 정규화에서 공백으로 바꾸는 글자 여섯. */
const TERM_SEPARATORS = /[-_/·•∙]/g;

/** 겹침 판정 키: 소문자 → 앞뒤 공백 → 구분 글자를 공백으로 → 공백 접기 → 앞뒤 공백 → 공백 모두 지움. */
export function termKey(raw: string): string {
  return raw
    .toLowerCase()
    .trim()
    .replace(TERM_SEPARATORS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/ /g, '');
}
