// 글자 자리(char-places.json)를 읽어 「그릇의 글에서 몇 번째 글자부터 몇 번째 글자까지」를 상자로 바꾼다.
//
// 글자 자리는 문서를 분해하는 쪽이 document.json 곁에 내는 파일이다(분해를 `parse --places` 로 돌렸을 때).
// 그릇 = 글 블록 하나(id `p3-b2`) 또는 표의 칸 하나(id `p3-t1:r2c4`). 그릇마다 글자별 가로 범위와 줄 토막별 세로 범위가 있다.
// 좌표는 뷰어의 입력 계약과 같다(포인트, 쪽의 왼쪽 위 원점). 그래서 여기서 얻은 상자를 그대로 innerBoxes 에 넣는다.
// 자리의 단위는 UTF-16 자리, 곧 JavaScript 문자열의 자리 그대로다("abc".slice(1, 2) 의 1 과 2).
//
// ★ 옮겨 적은 사본이다. 원본은 다른 저장소에 있어 import 할 수 없다.
//   원본: esg-lab 의 ts/reconcile/src/domain/places.ts (커밋 1c6c194) 의 sameLine, spanBoxes, sameSource
//         파일의 꼴은 같은 저장소의 schemas/char-places.schema.json (schema_version 0.1)
//   그쪽이 바뀌면 여기도 바꿔야 한다. 어긋났는지는 `pnpm --filter @esg/web measure:places` 에 그쪽이 낸
//   fact-places.json 을 주어 확인한다(값 후보 전부의 범위와 상자를 견준다. apps/web/docs/doc-viewer.md 의 「글자 자리」).
//   왜 옮겨 적었나: 변환 때 그쪽 스크립트를 불러 숫자의 상자만 받아 올 수도 있지만, 문장 강조처럼 「값 후보가 아닌
//   아무 글자 범위」의 상자도 필요해서 이 셈은 어차피 여기 있어야 한다.
import { z } from 'zod';

import type { Box } from '../../src/widgets/doc-viewer/model/index.ts';

const runSchema = z.object({
  /** 이 토막의 첫 글자가 그릇의 글에서 몇 번째 자리인가. */
  start: z.number().int().min(0),
  y0: z.number(),
  y1: z.number(),
  /** 글자마다 왼쪽 끝. k 번째 값은 글의 start + k 자리의 것. */
  x0: z.array(z.number()).min(1),
  x1: z.array(z.number()).min(1),
});

export const charPlacesSchema = z.object({
  schema_version: z.literal('0.1'),
  source: z.object({ sha256: z.string() }),
  unit: z.literal('utf16'),
  containers: z.array(
    z.object({
      id: z.string(),
      kind: z.enum(['block', 'cell']),
      page: z.number().int(),
      bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
      runs: z.array(runSchema).min(1),
    }),
  ),
  /** 글은 있는데 분해가 글자 자리를 잇지 못한 그릇. */
  unlinked: z.array(z.object({ id: z.string() })),
});
export type CharPlaces = z.infer<typeof charPlacesSchema>;
export type PlaceContainer = CharPlaces['containers'][number];

/** 문서 모델과 글자 자리가 같은 PDF 의 것인가. 다르면 상자가 엉뚱한 곳을 가리킨다. */
export function sameSource(
  document: { source: { sha256: string } },
  places: CharPlaces,
): boolean {
  return document.source.sha256 === places.source.sha256;
}

/** 그릇 id → 그릇. */
export function indexPlaces(
  places: CharPlaces,
): ReadonlyMap<string, PlaceContainer> {
  return new Map(
    places.containers.map((container) => [container.id, container]),
  );
}

/** 두 세로 범위가 한 줄인가: 겹친 높이가 낮은 쪽 높이의 절반을 넘는다. (한 줄 안에서 글자 크기가 다른 토막은 y 가 조금 다르다) */
function sameLine(a: Box, b: Box): boolean {
  const overlap = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
  return overlap > 0.5 * Math.min(a[3] - a[1], b[3] - b[1]);
}

export interface SpanBoxes {
  /** 줄마다 하나. 범위가 두 줄에 걸치면 둘이다. */
  boxes: Box[];
  /** 범위의 글자 가운데 좌표가 있던 글자의 수. 분해가 줄을 이으며 끼운 빈칸에는 좌표가 없다. */
  covered: number;
}

/** 그릇의 글자 범위 [start, end) 의 상자. 범위를 안 주면 그릇의 글 전체. */
export function spanBoxes(
  container: PlaceContainer,
  start?: number,
  end?: number,
): SpanBoxes {
  const boxes: Box[] = [];
  let covered = 0;
  for (const run of container.runs) {
    const runEnd = run.start + run.x0.length;
    const lo = Math.max(start ?? run.start, run.start);
    const hi = Math.min(end ?? runEnd, runEnd);
    if (lo >= hi) continue;
    covered += hi - lo;
    let x0 = Infinity;
    let x1 = -Infinity;
    for (let k = lo - run.start; k < hi - run.start; k++) {
      x0 = Math.min(x0, run.x0[k]!);
      x1 = Math.max(x1, run.x1[k]!);
    }
    const box: Box = [x0, run.y0, x1, run.y1];
    const last = boxes.at(-1);
    // 같은 줄의 토막은 한 상자로 묶는다. 줄이 바뀌면 상자가 따로다.
    if (last && sameLine(last, box))
      boxes[boxes.length - 1] = [
        Math.min(last[0], box[0]),
        Math.min(last[1], box[1]),
        Math.max(last[2], box[2]),
        Math.max(last[3], box[3]),
      ];
    else boxes.push(box);
  }
  return { boxes, covered };
}
