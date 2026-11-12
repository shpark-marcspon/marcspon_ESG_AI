// 새 번역 양식의 셈(밴드 TRW1a ②, 시안 TR-02·02a). 순수 함수 — 화면 상태(글자 칸·용어집·회사 칸)에서 쪽 범위와 틀린 칸을 센다.
// 쪽 수를 모르면(pageCount null — docx·txt, 감독 판단 1) 마지막 쪽 검사(over_last)를 하지 않는다: 범위 밖 쪽은 서버가 결과 no_pages 로 거절한다.
import {
  PART_KEYS,
  ceoError,
  parseRange,
} from '../../../entities/translation/model/index.ts';
import type {
  PartKey,
  Range,
  RangeError,
} from '../../../entities/translation/model/index.ts';

/** 글자 칸 셋 → 구간·오류. lastPage 는 쪽 수(모르면 null — 끝 검사 없음). */
export function readRanges(
  texts: Readonly<Record<PartKey, string>>,
  pageCount: number | null,
): {
  ranges: Record<PartKey, Range | null>;
  errors: Partial<Record<PartKey, RangeError>>;
} {
  const lastPage = pageCount ?? Number.POSITIVE_INFINITY;
  const ranges: Record<PartKey, Range | null> = {
    ceo: null,
    story: null,
    general: null,
  };
  const errors: Partial<Record<PartKey, RangeError>> = {};
  for (const part of PART_KEYS) {
    const read = parseRange(texts[part], lastPage);
    if (read.ok) ranges[part] = read.range;
    else errors[part] = read.error;
  }
  return { ranges, errors };
}

/** 틀린 칸 하나(「틀린 칸 n곳」의 셈 단위). */
export type FormProblem =
  | { code: 'no_file' }
  | { code: 'range'; part: PartKey }
  | { code: 'no_parts' }
  | { code: 'client_glossary' }
  | { code: 'company_name' }
  | { code: 'company_subject' }
  | { code: 'company_standards' };

export interface FormState {
  /** 올림을 마친 문서가 있는가. */
  uploaded: boolean;
  ranges: Readonly<Record<PartKey, Range | null>>;
  errors: Readonly<Partial<Record<PartKey, RangeError>>>;
  /** 고객사 용어집을 읽었는가. */
  clientGlossary: boolean;
  company: {
    name: string;
    preferredSubject: string;
    industryStandards: string;
  };
}

/** 틀린 칸들(화면 차례). CEO 한도 넘음은 그 파트의 범위 오류로 센다. */
export function formProblems(state: FormState): FormProblem[] {
  const problems: FormProblem[] = [];
  if (!state.uploaded) problems.push({ code: 'no_file' });
  for (const part of PART_KEYS)
    if (
      state.errors[part] !== undefined ||
      (part === 'ceo' && ceoError(state.ranges.ceo) !== null)
    )
      problems.push({ code: 'range', part });
  if (
    PART_KEYS.every(
      (part) => state.ranges[part] === null && state.errors[part] === undefined,
    )
  )
    problems.push({ code: 'no_parts' });
  if (!state.clientGlossary) problems.push({ code: 'client_glossary' });
  if (state.company.name.trim() === '') problems.push({ code: 'company_name' });
  if (state.company.preferredSubject.trim() === '')
    problems.push({ code: 'company_subject' });
  if (state.company.industryStandards.trim() === '')
    problems.push({ code: 'company_standards' });
  return problems;
}

/** 파일 크기 글자(「1.2MB」·「12KB」 — 그린워싱 파일 줄 꼴). */
export function sizeText(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  if (mb >= 0.1) return `${mb.toFixed(1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}
