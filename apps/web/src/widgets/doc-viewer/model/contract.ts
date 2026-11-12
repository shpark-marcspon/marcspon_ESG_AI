// 뷰어의 입력 계약: 타입과 런타임 검증.
//
// 뷰어는 이 꼴의 자료 하나만 받는다. 그 자료가 어디서 왔는지(어느 모듈의 결과인지)는 모른다.
// 좌표의 뜻은 geometry.ts 머리말에 있다.
//
// 검증을 두 단계로 나눈 까닭:
//   1) 꼴(zod): 필드가 있고 타입이 맞는가
//   2) 가리킴(checkReferences): 강조가 가리키는 문서·쪽, 항목이 가리키는 강조가 실제로 있는가
// 2)는 zod 의 superRefine 에 넣을 수도 있지만, 따로 두는 편이 읽기 쉽고 오류 문장을 고르기 쉽다.
import { z } from 'zod';

const pageSchema = z.object({
  width: z.number().positive(),
  height: z.number().positive(),
});

const documentSchema = z.object({
  id: z.string().min(1),
  /** 화면에 보일 이름. 없으면 id 를 쓴다. */
  title: z.string().optional(),
  /** PDF 주소. 뷰어는 이 주소를 그대로 연다. */
  url: z.string().min(1),
  /** 쪽별 크기(포인트). pages[0] 이 1쪽이다. PDF 를 열기 전에 자리를 잡는 데 쓴다. */
  pages: z.array(pageSchema).min(1),
});

const boxSchema = z.tuple([z.number(), z.number(), z.number(), z.number()]);

const highlightSchema = z.object({
  id: z.string().min(1),
  documentId: z.string().min(1),
  /** 1부터 센다. */
  page: z.number().int().min(1),
  /** [왼쪽, 위, 오른쪽, 아래] 포인트, 원점은 쪽의 왼쪽 위. 「여기까지는 확실하다」는 범위(표 전체, 문단 전체). */
  box: boxSchema,
  /**
   * box 안에서 더 좁힌 자리(표의 칸, 문단 속 숫자 하나, 문장 하나)의 상자들. 없을 수 있다.
   * 글자 범위가 여러 줄에 걸치면 줄마다 하나다. 전부 이 강조의 쪽(page) 위에 있다. 상자가 여럿이어도 강조는 하나다
   * (같이 골라지고 같이 가리켜진다). 뷰어는 이것을 그리고, 골라진 강조의 box 를 점선으로 같이 보여 준다(어느 표·문단인지).
   * 뷰어는 이 상자가 어디서 왔는지 모른다. 맞는 자리인지는 자료를 만드는 쪽의 책임이다.
   */
  innerBoxes: z.array(boxSchema).min(1).optional(),
  /** 예전 꼴: 좁힌 자리가 상자 하나. innerBoxes: [상자] 와 같은 뜻이다. innerBoxes 와 같이 주면 안 된다. 읽을 때는 innerBoxesOf 로 읽는다. */
  innerBox: boxSchema.optional(),
  /** 종류. 뷰어는 뜻을 모른다. 같은 종류끼리 같은 색을 쓸 뿐이다. */
  kind: z.string().min(1),
  /** 그 자리의 글자(칸의 값, 문장). 상자에 마우스를 올리면 보인다. */
  text: z.string().optional(),
});

const reviewSchema = z.discriminatedUnion('status', [
  z.object({ status: z.literal('pending') }),
  z.object({ status: z.literal('confirmed') }),
  z.object({ status: z.literal('rejected'), reason: z.string().min(1) }),
]);

const itemSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  /** 제목 아래 덧붙는 글. 줄바꿈(\n)은 그대로 보인다. */
  detail: z.string().optional(),
  /** 이 항목이 가리키는 강조들. 문서 하나 또는 둘에 걸친다. */
  highlightIds: z.array(z.string().min(1)).min(1),
  review: reviewSchema,
});

const kindSchema = z.object({
  kind: z.string().min(1),
  /** 범례에 보일 이름. */
  label: z.string().min(1),
  /** CSS 색. */
  color: z.string().min(1),
});

export const viewerInputSchema = z.object({
  version: z.literal(1),
  /** 화면 위에 띠로 보일 알림(예: 「이 강조는 검출을 흉내 낸 가짜 자료다」). */
  notice: z.string().optional(),
  /** 하나면 한 문서 배치, 둘이면 나란히 놓는 배치. */
  documents: z.array(documentSchema).min(1).max(2),
  highlights: z.array(highlightSchema),
  items: z.array(itemSchema),
  /** 종류별 이름과 색. 여기 없는 종류는 기본 색으로 그린다. */
  kinds: z.array(kindSchema).optional(),
});

export type ViewerInput = z.infer<typeof viewerInputSchema>;
export type ViewerDocument = ViewerInput['documents'][number];
export type Highlight = ViewerInput['highlights'][number];
export type Item = ViewerInput['items'][number];
export type KindStyle = NonNullable<ViewerInput['kinds']>[number];

/** 강조의 좁힌 자리 상자들. 새 꼴(innerBoxes)과 예전 꼴(innerBox 하나)을 여기서 하나로 읽는다. 없으면 빈 목록. */
export function innerBoxesOf(
  highlight: Pick<Highlight, 'innerBox' | 'innerBoxes'>,
): readonly Highlight['box'][] {
  if (highlight.innerBoxes) return highlight.innerBoxes;
  return highlight.innerBox ? [highlight.innerBox] : [];
}

export type ParseResult =
  { ok: true; input: ViewerInput } | { ok: false; errors: string[] };

/** 모르는 값(JSON)을 받아 검증한다. 틀린 곳을 전부 모아 돌려준다. */
export function parseViewerInput(raw: unknown): ParseResult {
  const shape = viewerInputSchema.safeParse(raw);
  if (!shape.success) {
    return {
      ok: false,
      errors: shape.error.issues.map(
        (issue) => `${issue.path.join('.') || '(root)'}: ${issue.message}`,
      ),
    };
  }
  const errors = checkReferences(shape.data);
  if (errors.length > 0) return { ok: false, errors };
  return { ok: true, input: shape.data };
}

/** 상자가 쪽 밖으로 나가도 봐주는 여유(포인트). 좌표가 소수 한 자리로 반올림되어 온다. */
const BOX_TOLERANCE = 1;

/** 꼴은 맞는 자료에서, 서로 가리키는 것들이 실제로 있는지 본다. */
export function checkReferences(input: ViewerInput): string[] {
  const errors: string[] = [];

  const documents = new Map<string, ViewerDocument>();
  for (const doc of input.documents) {
    if (documents.has(doc.id))
      errors.push(`documents: id "${doc.id}" 가 둘 이상이다`);
    documents.set(doc.id, doc);
  }

  const highlights = new Map<string, Highlight>();
  for (const h of input.highlights) {
    if (highlights.has(h.id))
      errors.push(`highlights: id "${h.id}" 가 둘 이상이다`);
    highlights.set(h.id, h);

    const doc = documents.get(h.documentId);
    if (!doc) {
      errors.push(
        `highlights "${h.id}": 없는 문서 "${h.documentId}" 를 가리킨다`,
      );
      continue;
    }
    const page = doc.pages[h.page - 1];
    if (!page) {
      errors.push(
        `highlights "${h.id}": 없는 쪽 ${h.page} 를 가리킨다(문서 "${doc.id}" 는 ${doc.pages.length}쪽)`,
      );
      continue;
    }
    if (h.innerBox && h.innerBoxes)
      errors.push(
        `highlights "${h.id}": innerBox 와 innerBoxes 를 같이 줄 수 없다(예전 꼴과 새 꼴 가운데 하나만)`,
      );
    const named: [string, Highlight['box'] | undefined][] = [
      ['box', h.box],
      ['innerBox', h.innerBox],
      ...(h.innerBoxes ?? []).map((box, index): [string, Highlight['box']] => [
        `innerBoxes[${index}]`,
        box,
      ]),
    ];
    for (const [name, box] of named) {
      if (!box) continue;
      const [x0, y0, x1, y1] = box;
      if (!(x0 < x1 && y0 < y1)) {
        errors.push(
          `highlights "${h.id}": ${name} 의 왼쪽·위가 오른쪽·아래보다 작아야 한다`,
        );
      } else if (
        x0 < -BOX_TOLERANCE ||
        y0 < -BOX_TOLERANCE ||
        x1 > page.width + BOX_TOLERANCE ||
        y1 > page.height + BOX_TOLERANCE
      ) {
        errors.push(
          `highlights "${h.id}": ${name} 가 쪽(${page.width}×${page.height}) 밖으로 나간다`,
        );
      }
    }
  }

  const itemIds = new Set<string>();
  for (const item of input.items) {
    if (itemIds.has(item.id))
      errors.push(`items: id "${item.id}" 가 둘 이상이다`);
    itemIds.add(item.id);
    for (const id of item.highlightIds) {
      if (!highlights.has(id))
        errors.push(`items "${item.id}": 없는 강조 "${id}" 를 가리킨다`);
    }
  }

  const styled = new Set<string>();
  for (const style of input.kinds ?? []) {
    if (styled.has(style.kind))
      errors.push(`kinds: "${style.kind}" 가 둘 이상이다`);
    styled.add(style.kind);
  }

  return errors;
}
