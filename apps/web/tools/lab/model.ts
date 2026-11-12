// 실측 산출물의 꼴 가운데 변환이 읽는 부분만. 검증은 zod 로 한다(파일이 기대와 다르면 바로 멈추게).
import { z } from 'zod';

const bbox = z.tuple([z.number(), z.number(), z.number(), z.number()]);

/** 문서를 분해한 결과(document.json). bbox 는 포인트, 왼쪽 위 원점. 뷰어의 좌표와 같다. */
export const labDocumentSchema = z.object({
  /** 원본 PDF 의 해시. 글자 자리(char-places.json)가 같은 PDF 의 것인지 견주는 데 쓴다. */
  source: z.object({ sha256: z.string() }),
  pages: z.array(
    z.object({ page: z.number(), width: z.number(), height: z.number() }),
  ),
  blocks: z.array(
    z.object({
      id: z.string(),
      page: z.number(),
      kind: z.string(),
      bbox,
      text: z.string().optional(),
    }),
  ),
  tables: z.array(
    z.object({
      id: z.string(),
      page: z.number(),
      bbox,
      cells: z.array(z.array(z.string())),
    }),
  ),
});
export type LabDocument = z.infer<typeof labDocumentSchema>;

/** 오류를 심은 시험지. 좌표가 없고 글과 칸의 값만 쓴다. */
export const labExamSchema = z.object({
  blocks: z.array(z.object({ id: z.string(), text: z.string().optional() })),
  tables: z.array(
    z.object({ id: z.string(), cells: z.array(z.array(z.string())) }),
  ),
});
export type LabExam = z.infer<typeof labExamSchema>;

/** 두 문서 대조의 결과(outcome.json). after.verdicts 가 최종 판정, states 가 자리별 상태다. */
export const labOutcomeSchema = z.object({
  after: z.object({
    verdicts: z.array(
      z.object({
        a: z.string(),
        b: z.string(),
        outcome: z.string(),
        reason: z.string(),
      }),
    ),
  }),
  states: z.object({
    a: z.record(z.string(), z.string()),
    b: z.record(z.string(), z.string()),
  }),
});
export type LabOutcome = z.infer<typeof labOutcomeSchema>;
