// 결과·검토 계약 거울의 공개 표면(밴드 FW2 ①). api 칸 안에서 zod 를 가져오는 자리는 이 폴더뿐이다(app/guards/layers.test.ts).
// 저장소(GreenwashStore)는 결과·검토를 JSON 그대로(unknown) 주고, 훅이 이 거울로 꼴을 지킨다. 꼴이 어긋나면 「꼴 오류」 상태다.
import type { z } from 'zod';

import type {
  GreenwashResult,
  GreenwashReview,
  ReviewUpdate,
} from '../../model/index.ts';
import { resultBranchOf, resultSchema } from './result.ts';
import { reviewSchema, reviewUpdateSchema } from './review.ts';

export { resultItemSchema, resultSchema } from './result.ts';
export { reviewSchema, reviewUpdateSchema } from './review.ts';

export type Parsed<T> = { ok: true; value: T } | { ok: false; issues: string };

function parseWith<T>(schema: z.ZodType<T>, value: unknown): Parsed<T> {
  const parsed = schema.safeParse(value);
  return parsed.success ?
      { ok: true, value: parsed.data }
    : { ok: false, issues: describeIssues(parsed.error.issues) };
}

/** 꼴 오류 글(개발자용, 화면에 그대로 보이지 않는다): 「경로: 까닭」을 「; 」로 잇는다. */
function describeIssues(issues: readonly z.core.$ZodIssue[]): string {
  return issues
    .map(
      (issue) =>
        `${issue.path.map(String).join('.') || '(맨 위)'}: ${issue.message}`,
    )
    .join('; ');
}

/** 거절이면 dryRun 으로 고른 가지의 글을 단다(union 은 「(맨 위): Invalid input」 하나로 접는다. sid:MARC-ISSUE-133). */
export function parseResult(value: unknown): Parsed<GreenwashResult> {
  const parsed = parseWith(resultSchema, value);
  if (parsed.ok) return parsed;
  const branch = resultBranchOf(value)?.safeParse(value);
  return branch && !branch.success ?
      { ok: false, issues: describeIssues(branch.error.issues) }
    : parsed;
}
export const parseReview = (value: unknown): Parsed<GreenwashReview> =>
  parseWith(reviewSchema, value);
export const parseReviewUpdate = (value: unknown): Parsed<ReviewUpdate> =>
  parseWith(reviewUpdateSchema, value);
