// 사업장(S15)의 꼴과 셈(밴드 W12-0a ①). React·DOM·통신을 모른다.
//   - 꼴: 서버 BranchOut·BranchDetailOut·BranchFacilityOut·BranchPageOut 그대로(응답 id 는 글자 — 거울은 api/contract).
//   - 고침 판(draft): 상세 화면이 들고 있는 것. 모달 저장은 판의 줄 목록에만 들고, 페이지 [저장]이 branchSaveBody 로 한 번에 보낸다.
//   - 본사 규칙(스펙 S15 [확인]·[우리 해석]): 본사는 고르지 못하고(체크박스 비활성) 끄지 못하고 지우지 못한다.
//     일괄 끄기는 본사를 뺀다 — 켜기는 섞여도 된다(K1b-1 ⑤ ②).
//   - 판 버전(밴드 K1b-3): 상세의 updatedAt 글자. 판(draft)에는 싣지 않고 화면이 따로 들며, PUT 본문에만 받은 글자 그대로 싣는다(branchPutBody).
import { toRequestId } from './ids.ts';

export interface Branch {
  id: string;
  name: string;
  isHeadquarters: boolean;
  inventoryEnabled: boolean;
  externalId: string | null;
  createdAt: string;
}

export interface BranchFacility {
  id: string;
  facilityCodeId: string;
  /** 코드 글자(F0001 꼴) — 화면에 보이지 않는다. 코드가 지워져도 그대로 온다. */
  facilityCode: string;
  facilityName: string;
  detailName: string;
}

export interface BranchDetail extends Branch {
  facilities: BranchFacility[];
  /** 이 판의 버전(서버 updatedAt — µs·+09:00 글자). 날짜로 바꾸지 않고 PUT 본문에 그대로 돌려준다. */
  updatedAt: string;
}

/** 쪽 번호 쪽(서버 PageNumberPage). */
export interface NumberedPage<T> {
  count: number;
  totalPages: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
  results: T[];
}

export type BranchPage = NumberedPage<Branch>;

/** 상세 화면 표의 줄 하나. id 는 서버에 있는 줄이면 그 id, 화면에서 더한 줄이면 null. key 는 화면 안 열쇠. */
export interface FacilityLine {
  key: string;
  id: string | null;
  facilityCodeId: string;
  facilityName: string;
  detailName: string;
}

export interface BranchDraft {
  name: string;
  inventoryEnabled: boolean;
  isHeadquarters: boolean;
  facilities: FacilityLine[];
}

/** 새 사업장의 빈 판(인벤토리 사용 켬 — 서버 기본값과 같다). */
export function emptyDraft(): BranchDraft {
  return {
    name: '',
    inventoryEnabled: true,
    isHeadquarters: false,
    facilities: [],
  };
}

/** 서버 상세를 판으로(줄 차례 그대로, 줄 열쇠는 서버 id). */
export function draftOf(detail: BranchDetail): BranchDraft {
  return {
    name: detail.name,
    inventoryEnabled: detail.inventoryEnabled,
    isHeadquarters: detail.isHeadquarters,
    facilities: detail.facilities.map((line) => ({
      key: `saved-${line.id}`,
      id: line.id,
      facilityCodeId: line.facilityCodeId,
      facilityName: line.facilityName,
      detailName: line.detailName,
    })),
  };
}

/** 두 판이 같은가(취소 확인 창을 띄울지). 줄은 차례까지 견준다. */
export function sameDraft(a: BranchDraft, b: BranchDraft): boolean {
  return (
    a.name === b.name &&
    a.inventoryEnabled === b.inventoryEnabled &&
    a.facilities.length === b.facilities.length &&
    a.facilities.every((line, i) => {
      const other = b.facilities[i]!;
      return (
        line.id === other.id &&
        line.facilityCodeId === other.facilityCodeId &&
        line.detailName === other.detailName
      );
    })
  );
}

export interface BranchFacilityBody {
  id?: number;
  facilityCodeId: number;
  detailName: string;
}

/** POST /branches·PUT /branches/{id} 본문. 새 줄은 id 없이, 있던 줄은 id 정수로(빠진 줄 = 삭제 표시). */
export interface BranchSaveBody {
  name: string;
  inventoryEnabled: boolean;
  facilities: BranchFacilityBody[];
}

export function branchSaveBody(draft: BranchDraft): BranchSaveBody {
  return {
    name: draft.name.trim(),
    // 본사는 늘 켬(서버도 끄면 409 HEADQUARTERS_LOCKED).
    inventoryEnabled: draft.isHeadquarters ? true : draft.inventoryEnabled,
    facilities: draft.facilities.map((line) => ({
      ...(line.id === null ? {} : { id: toRequestId(line.id) }),
      facilityCodeId: toRequestId(line.facilityCodeId),
      detailName: line.detailName.trim(),
    })),
  };
}

/** PUT /branches/{id} 본문: 공통 본문 + 그 판의 버전(다르면 서버가 409 STALE). POST 본문에는 싣지 않는다(서버 422). */
export interface BranchPutBody extends BranchSaveBody {
  updatedAt: string;
}

export function branchPutBody(
  draft: BranchDraft,
  version: string,
): BranchPutBody {
  return { ...branchSaveBody(draft), updatedAt: version };
}

/** (시설명 및 코드, 세부시설명) 겹침 열쇠 — 세부시설명은 앞뒤 공백을 걷고 견준다. */
const lineKey = (facilityCodeId: string, detailName: string) =>
  `${facilityCodeId}\u0000${detailName.trim()}`;

export type BranchProblem = 'nameRequired' | 'duplicateFacility';

/** 페이지 [저장]의 검사: 첫 문제 하나(이름 빔이 먼저). 없으면 null. */
export function validateBranch(draft: BranchDraft): BranchProblem | null {
  if (draft.name.trim() === '') return 'nameRequired';
  const seen = new Set<string>();
  for (const line of draft.facilities) {
    const key = lineKey(line.facilityCodeId, line.detailName);
    if (seen.has(key)) return 'duplicateFacility';
    seen.add(key);
  }
  return null;
}

export type FacilityLineProblem =
  'codeRequired' | 'detailRequired' | 'duplicateFacility';

/** 모달 [저장]의 검사: 시설명 및 코드 빔 → 세부시설명 빔 → 판에 이미 있는 줄과 겹침. 없으면 null. */
export function validateFacilityLine(
  lines: readonly FacilityLine[],
  facilityCodeId: string,
  detailName: string,
): FacilityLineProblem | null {
  if (facilityCodeId === '') return 'codeRequired';
  if (detailName.trim() === '') return 'detailRequired';
  const key = lineKey(facilityCodeId, detailName);
  return (
      lines.some(
        (line) => lineKey(line.facilityCodeId, line.detailName) === key,
      )
    ) ?
      'duplicateFacility'
    : null;
}

/** 목록에서 고를 수 있는 행인가(본사는 체크박스 비활성). */
export const isSelectable = (branch: Branch) => !branch.isHeadquarters;

/** 행 토글을 누를 수 있는가(본사는 켜진 채 비활성). */
export const canToggleInventory = (branch: Branch) => !branch.isHeadquarters;

/** 일괄 「인벤토리 사용」(enabled)·「사용취소」의 대상 id. 끄기에서는 본사를 뺀다. */
export function inventoryTargets(
  selected: readonly Branch[],
  enabled: boolean,
): string[] {
  return selected
    .filter((branch) => enabled || !branch.isHeadquarters)
    .map((branch) => branch.id);
}

/** 「사업장 삭제」의 대상 id(본사는 빠진다). */
export function deleteTargets(selected: readonly Branch[]): string[] {
  return selected
    .filter((branch) => !branch.isHeadquarters)
    .map((branch) => branch.id);
}
