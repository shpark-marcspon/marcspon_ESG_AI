// 새 점검 폼 검사(밴드 FW1b ①). 「점검 시작」을 누를 때 검사한다. 사유 코드로만 낸다(문구는 ui).
// 글자 없는 PDF 는 시안 GW-02a 대로 시작 버튼을 끄는 것과 별도로 여기서도 사유로 낸다.
import { MAX_PAGE_COUNT } from '../../../entities/greenwash/model/index.ts';
import type { PageRangeError } from '../../../entities/greenwash/model/index.ts';
import { allPartsEmpty } from '../../../entities/greenwash/model/index.ts';
import type {
  PartKey,
  PartPages,
} from '../../../entities/greenwash/model/index.ts';

// 1차 입력 한도 MAX_PAGE_COUNT(300쪽)는 pageRange.ts 에 있다(쪽 범위의 위쪽 한도로도 쓴다). 크기 한도 MAX_UPLOAD_MB(50)는 드롭존의 maxMb 가 지키고, 서버 413 은 폼 훅의 uploadTooLarge 로 같은 안내.

export type FormProblem =
  | { code: 'no_file' }
  | { code: 'no_text' }
  | { code: 'too_many_pages'; pageCount: number; max: number }
  | { code: 'page_range'; part: PartKey; error: PageRangeError }
  | { code: 'no_parts' };

export interface FormInput {
  /** 올린 문서. 없거나 올리는 중이면 null. */
  uploaded: { pageCount: number; hasText: boolean } | null;
  parts: PartPages;
  /** 파트별 글자 칸의 지금 오류. */
  partErrors: Readonly<Partial<Record<PartKey, PageRangeError | null>>>;
}

/**
 * 검사 사유 목록. 비었으면 시작할 수 있다. 문서 문제가 있으면 쪽 검사는 하지 않는다(쪽 수를 믿을 수 없다).
 * 차례는 화면의 칸 차례다(파트 셋 → 파트 묶음): ui 가 첫 사유의 칸으로 초점을 옮긴다(밴드 FW2 ⓪).
 * 파트는 하나 이상이면 된다: 셋 다 비었을 때만 no_parts(2026-10-16 사용자 결정).
 */
export function validateNewCheck(input: FormInput): FormProblem[] {
  const { uploaded } = input;
  if (uploaded === null) return [{ code: 'no_file' }];
  if (!uploaded.hasText) return [{ code: 'no_text' }];
  if (uploaded.pageCount > MAX_PAGE_COUNT)
    return [
      {
        code: 'too_many_pages',
        pageCount: uploaded.pageCount,
        max: MAX_PAGE_COUNT,
      },
    ];
  const problems: FormProblem[] = [];
  for (const [part, error] of Object.entries(input.partErrors) as [
    PartKey,
    PageRangeError | null | undefined,
  ][])
    if (error) problems.push({ code: 'page_range', part, error });
  if (
    !problems.some((problem) => problem.code === 'page_range') &&
    allPartsEmpty(input.parts)
  )
    problems.push({ code: 'no_parts' });
  return problems;
}
