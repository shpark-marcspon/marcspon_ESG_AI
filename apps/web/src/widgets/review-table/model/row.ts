// 검토 표의 한 행. React 도, TanStack 도, DOM 도 모르는 순수 TypeScript 다.
//
// 한 행에는 세 가지가 따로 들어 있다.
//   ai      AI 가 낸 원본값(카테고리, 후보들). 한 번 받으면 바뀌지 않는다
//   edit    사람이 고친 값. 고치지 않았으면 null. 원본값을 덮어쓰지 않고 옆에 둔다
//   status  검토 상태
// 화면이 보여 줄 「지금 값」은 아래 current* 함수로 읽는다(수정값이 있으면 수정값, 없으면 원본값).

export type ReviewStatus =
  | 'pending'
  | 'accepted'
  | 'declined'
  | 'edited'
  | 'rerequested'
  | 'rejected'
  | 'finalized';

export const STATUSES: readonly ReviewStatus[] = [
  'pending',
  'accepted',
  'declined',
  'edited',
  'rerequested',
  'rejected',
  'finalized',
];

export const STATUS_LABEL: Record<ReviewStatus, string> = {
  pending: '검토대기',
  accepted: '반영',
  declined: '미반영',
  edited: '수정',
  rerequested: '재추천요청',
  rejected: '반려',
  finalized: '최종확정',
};

export type Confidence = 'high' | 'medium' | 'low';

/** AI 가 제안한 배출계수 후보 하나. */
export interface Candidate {
  id: string;
  factorName: string;
  /** 계수 값. 값이 없는 계수도 있다. */
  factorValue: number | null;
  factorUnit: string;
  source?: string;
  /** 적용 기준(매핑 이유). 자료에 없으면 비어 있다. */
  reason?: string;
  /** 신뢰도. 자료에 없으면 비어 있다. */
  confidence?: Confidence;
  /** 이 후보로 계산한 배출량(tCO2eq). 계산은 서버의 일이고, 여기서는 받은 값이다(다시 환산하지 않는다). 값이 나오지 않았으면 null. */
  emission: number | null;
}

export type RawValue = string | number | null;

/** 사람이 고친 값. 고친 것만 들어 있다. */
export interface RowEdit {
  category?: string;
  candidateId?: string;
  /** 고친 값으로 다시 계산한 배출량. 재계산을 기다리는 동안, 계산해도 값이 나오지 않았을 때, 계산이 실패했을 때는 null. */
  emission: number | null;
  /** 재계산을 기다리는 중인가. 이 동안에는 최종 확정이 안 된다. */
  recalcPending: boolean;
  /**
   * 재계산이 실패했다(계산 함수가 거부했거나 예외를 냈다). 이때 emission 은 null 이고 recalcPending 은 false 다.
   * 「계산해 보니 값이 없다」(emission 만 null)와 다르다. 실패는 다시 시도할 수 있고(retryRecalc), 그 전에는 최종 확정이 안 된다.
   * 실패하지 않았으면 이 필드가 아예 없다.
   */
  recalcFailed?: true;
}

export interface ReviewRow {
  id: string;
  /** 원본 데이터. 이 부품은 키의 뜻을 모른다. 무엇을 열로 보일지는 열 구성(입력)이 정한다. */
  raw: Readonly<Record<string, RawValue>>;
  /** 처리 상태(분석 중, 결과 생성 등). 서버가 준 값을 그대로 든다. */
  processing?: string;
  ai: {
    category: string | null;
    /** AI 가 그 카테고리로 분류한 까닭. */
    categoryNote?: string;
    /** 첫 번째가 대표 후보다. 0개일 수 있다. */
    candidates: readonly Candidate[];
  };
  edit: RowEdit | null;
  status: ReviewStatus;
  rejectReason?: string;
}

export function currentCategory(row: ReviewRow): string | null {
  return row.edit?.category ?? row.ai.category;
}

/** 지금 골라진 후보. 사람이 다른 후보를 골랐으면 그것, 아니면 대표 후보. 후보가 없으면 null. */
export function currentCandidate(row: ReviewRow): Candidate | null {
  const picked = row.edit?.candidateId;
  if (picked !== undefined)
    return (
      row.ai.candidates.find((candidate) => candidate.id === picked) ?? null
    );
  return row.ai.candidates[0] ?? null;
}

/** 지금 유효한 배출량. 수정했으면 재계산한 값, 아니면 대표 후보의 값. */
export function currentEmission(row: ReviewRow): number | null {
  if (row.edit) return row.edit.emission;
  return row.ai.candidates[0]?.emission ?? null;
}

export function isRecalcPending(row: ReviewRow): boolean {
  return row.edit?.recalcPending ?? false;
}

/** 재계산이 실패한 채로 있는가. 배출량이 없는 것(currentEmission 이 null)과 따로 묻는다. */
export function isRecalcFailed(row: ReviewRow): boolean {
  return row.edit?.recalcFailed === true;
}
