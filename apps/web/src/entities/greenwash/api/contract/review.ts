// greenwash.review@3(@2 + evidence·rejudges, GRJ1) 와 PUT 본문(GreenwashReviewUpdate)의 zod 거울(밴드 FW2 ①). 정본(main ee18aaa, 읽기만):
//   apps/api-py/esgapi/greenwash/tests/data/flow-shapes/review/greenwash.review@3.schema.json (contracts/review_shapes.py)
//   apps/api-py/esgapi/greenwash/service/apis/greenwash.py GreenwashReviewUpdate(StrictIn: 모르는 칸 거절, state 는 'confirmed' 나 없음·null 만 —
//   pending → in_review 는 서버가 표시를 보고 스스로 옮긴다. 결함 D1)
// 맨 위 응답 객체(reviewSchema)는 모르는 키를 버리고 통과시키고(결함 D10, 밴드 WC1 ①), 안쪽 객체(mark·confirmedBy)와 PUT 본문은
// 모르는 키를 거절한다(result.ts 의 obj. PUT 본문은 화면이 짓는 것이고 서버 StrictIn 이 거절하므로 strict 그대로). 설명 글의 규칙(excludeReason 은 excluded 일 때만 글, confirmedAt 은 confirmed
// 일 때만 값, marks 는 오름차순·겹침 없음)은 스키마에 없어 검사하지 않는다 — 화면이 짓는 본문은 domain(markUpdate·confirmUpdate)이 지킨다.
import { z } from 'zod';

import { LEVELS, REVIEW_SHAPE, REVIEW_STATES } from '../../model/index.ts';
import type {
  EvidenceAdded,
  GreenwashReview,
  Rejudged,
  ReviewEdit,
  ReviewEditIn,
  ReviewEvidence,
  ReviewEvidenceIn,
  ReviewMark,
  ReviewRejudge,
  ReviewUpdate,
} from '../../model/index.ts';
import { obj } from './result.ts';

const mark: z.ZodType<ReviewMark> = obj({
  itemIndex: z.int().min(0),
  decision: z.enum(['adopted', 'excluded']),
  excludeReason: z.string().nullable(),
});

const reviewer = obj({ id: z.int(), name: z.string().min(1) });

/** 고침(G1b-3) — 칸마다 {value, editedAt, editedBy} 또는 null. */
const edit: z.ZodType<ReviewEdit> = obj({
  itemIndex: z.int().min(0),
  level: obj({
    value: z.enum(LEVELS),
    editedAt: z.string(),
    editedBy: reviewer,
  }).nullable(),
  reasonBullets: obj({
    value: z.array(z.string()),
    editedAt: z.string(),
    editedBy: reviewer,
  }).nullable(),
  fixParagraph: obj({
    value: z.string(),
    editedAt: z.string(),
    editedBy: reviewer,
  }).nullable(),
});

/** PUT 본문의 고침 — 평평한 값. */
const editIn: z.ZodType<ReviewEditIn> = obj({
  itemIndex: z.int().min(0),
  level: z.enum(LEVELS).nullable(),
  reasonBullets: z.array(z.string()).nullable(),
  fixParagraph: z.string().nullable(),
});

/** 더한 근거 조각(GRJ1) — 응답·본문 둘 다 닫힌 꼴. */
const added: z.ZodType<EvidenceAdded> = obj({
  text: z.string().min(1),
  page: z.int().min(1).nullable(),
});

const evidence: z.ZodType<ReviewEvidence> = obj({
  itemIndex: z.int().min(0),
  removed: z.array(z.int().min(0)),
  added: z.array(added),
  editedAt: z.string(),
  editedBy: reviewer,
});

const evidenceIn: z.ZodType<ReviewEvidenceIn> = obj({
  itemIndex: z.int().min(0),
  removed: z.array(z.int().min(0)),
  added: z.array(added),
});

const rejudged: z.ZodType<Rejudged> = obj({
  runId: z.int(),
  judgedAt: z.string(),
  judgedBy: reviewer,
  outcome: z.enum(['judged', 'nonrisk']),
  level: z.enum(LEVELS).nullable(),
  riskTags: z.array(z.string()),
  confirmedInEvidence: z.array(z.string()),
  missingFields: z.array(z.string()),
  reasonBullets: z.array(z.string()),
  fixParagraph: z.string(),
  evidencePages: z.array(z.int().min(1)),
  added: z.array(added),
});

const rejudge: z.ZodType<ReviewRejudge> = obj({
  itemIndex: z.int().min(0),
  status: z.enum(['running', 'failed', 'done']),
  count: z.int().min(0),
  current: rejudged.nullable(),
});

/** greenwash.review@3 거울. */
export const reviewSchema: z.ZodType<GreenwashReview> = z.object({
  schemaVersion: z.literal(REVIEW_SHAPE),
  runId: z.int(),
  state: z.enum(REVIEW_STATES),
  confirmedAt: z.string().nullable(),
  // 확정한 사람(GC2). 필수 칸이고 confirmed 가 아니면 null(밴드 WC1 ①).
  confirmedBy: reviewer.nullable(),
  marks: z.array(mark),
  edits: z.array(edit),
  evidence: z.array(evidence),
  rejudges: z.array(rejudge),
});

/** PUT /greenwash/runs/{run_id}/review 본문 거울. */
export const reviewUpdateSchema: z.ZodType<ReviewUpdate> = obj({
  state: z.literal('confirmed').nullable().optional(),
  marks: z.array(mark),
  edits: z.array(editIn).nullable().optional(),
  evidence: z.array(evidenceIn).nullable().optional(),
});
