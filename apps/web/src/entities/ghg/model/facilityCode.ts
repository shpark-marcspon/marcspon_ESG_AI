// 자산/시설명 및 코드(S18 — 모든 고객사 공통 목록, 편집은 운영 관리자만)의 꼴과 셈(밴드 W12-0a ①).
// 화면은 이름만 보인다 — code(F0001 꼴)는 서버가 붙이는 안정 키이고 수정해도 그대로다.
import type { NumberedPage } from './branch.ts';

export interface FacilityCode {
  id: string;
  code: string;
  name: string;
}

export interface AdminFacilityCode extends FacilityCode {
  /** 1차는 늘 false(서버가 자리만 둠). */
  inUse: boolean;
}

export type AdminFacilityCodePage = NumberedPage<AdminFacilityCode>;

/** 가나다(ko 정렬 — 한글 먼저) → 같으면 id. */
const KO = new Intl.Collator('ko');

/**
 * 고르는 칸의 차례(GX2 L-8): 이름 가나다 → id. 서버 GET /facility-codes 는 order_by("name", "id") 이지만 DB 정렬 규칙(collation)이
 * 가나다가 아니라(GX1 실측 「경유·등유·용제·나프타·…·구매 전력·B-A유」) 웹이 다시 줄 세운다. 서버는 고치지 않는다.
 */
export function codesInKoreanOrder(
  codes: readonly FacilityCode[],
): FacilityCode[] {
  return [...codes].sort(
    (a, b) => KO.compare(a.name, b.name) || Number(a.id) - Number(b.id),
  );
}

export type CodeNameProblem = 'required' | 'duplicate';

/**
 * 모달 [저장]의 검사: 빈 이름 → required, 다른 항목과 같은 이름(앞뒤 공백을 걷고) → duplicate. 없으면 null.
 * 수정이면 selfId 의 항목은 견주지 않는다(같은 이름 그대로 저장은 겹침이 아니다).
 */
export function validateCodeName(
  name: string,
  existing: readonly FacilityCode[],
  selfId: string | null = null,
): CodeNameProblem | null {
  const trimmed = name.trim();
  if (trimmed === '') return 'required';
  return (
      existing.some(
        (code) => code.id !== selfId && code.name.trim() === trimmed,
      )
    ) ?
      'duplicate'
    : null;
}
