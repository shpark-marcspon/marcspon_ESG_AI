// 두 문서 대조의 결과를 뷰어의 입력으로 바꾼다. 파일도 PDF 도 읽지 않는 순수 함수다(읽는 일은 tools/convert.ts 가 한다).
//
//   판정 하나(a 자리, b 자리, 일치/불일치) → 항목 하나 + 강조 둘
//   짝을 못 찾은 자리 하나                 → 항목 하나 + 강조 하나(「확인 못 함」)
//
// 강조의 box 는 표 전체 또는 문단 전체다(document.json 이 아는 좌표가 거기까지다).
// 글자 자리(places)를 주면 그 안의 칸·숫자의 상자를 innerBoxes 로 넣는다. 안 주면 넣지 않는다(짐작하지 않는다).
import type {
  Highlight,
  Item,
  ViewerInput,
} from '../../src/widgets/doc-viewer/model/index.ts';
import type { Box } from '../../src/widgets/doc-viewer/model/index.ts';
import type { LabDocument, LabExam, LabOutcome } from './model.ts';
import { spanBoxes } from './places.ts';
import type { PlaceContainer } from './places.ts';
import { parseRef, scanNumbers } from './refs.ts';

export interface Side {
  /** 뷰어 입력의 문서 id. */
  id: 'a' | 'b';
  title: string;
  url: string;
  document: LabDocument;
  /** 판정이 실제로 본 값(오류를 심은 시험지). 없으면 document 의 값을 쓴다. */
  exam?: LabExam;
  /** 글자 자리(그릇 id → 그릇. tools/lab/places.ts 의 indexPlaces). 없으면 좁힌 상자를 넣지 않는다. */
  places?: ReadonlyMap<string, PlaceContainer>;
}

/** 자리 표기 하나를 풀어낸 것. */
export interface Target {
  page: number;
  /** 확실한 범위: 표 전체 또는 문단 전체. */
  box: Box;
  form: 'cell' | 'cell#n' | 'block#n';
  /** PDF 원문의 값(document.json). 숫자의 몸통만이다(뒤의 % 는 뺀다). */
  value: string;
  /** 판정이 본 값. 시험지가 값을 바꿨으면 value 와 다르다. */
  judgedValue: string;
  /** 사람이 읽을 위치 설명. */
  where: string;
  /** 글자 자리에서 찾을 그릇: 칸이면 `표ID:r행c열`, 문단이면 블록 ID. */
  containerId: string;
  /** 그릇의 글에서의 글자 범위 [start, end). 칸 전체면 null. 숫자 뒤의 % 까지 든다(대조 쪽 값 후보의 범위와 같게). */
  span: { start: number; end: number } | null;
}

export function resolveTarget(
  side: Side,
  refText: string,
): { ok: true; target: Target } | { ok: false; error: string } {
  const parsed = parseRef(refText);
  if (!parsed.ok) return parsed;
  const ref = parsed.ref;

  if (ref.kind === 'cell') {
    const table = side.document.tables.find((t) => t.id === ref.tableId);
    const cellText = table?.cells[ref.row]?.[ref.col];
    if (!table || cellText === undefined)
      return { ok: false, error: `"${refText}": 그런 표나 칸이 없다` };
    const examText =
      side.exam?.tables.find((t) => t.id === ref.tableId)?.cells[ref.row]?.[
        ref.col
      ] ?? cellText;

    const containerId = `${ref.tableId}:r${ref.row}c${ref.col}`;
    const rowHead =
      table.cells[ref.row]
        ?.slice(0, ref.col)
        .filter(Boolean)
        .slice(0, 2)
        .join(' / ') ?? '';
    const colHead = table.cells[0]?.[ref.col] ?? '';
    const where = `${ref.page}쪽 표 · ${[rowHead, colHead].filter(Boolean).join(' · ') || `r${ref.row}c${ref.col}`}`;

    if (ref.nth === null) {
      return {
        ok: true,
        target: {
          page: table.page,
          box: table.bbox,
          form: 'cell',
          value: cellText,
          judgedValue: examText,
          where,
          containerId,
          span: null,
        },
      };
    }
    const token = scanNumbers(cellText)[ref.nth - 1];
    if (!token)
      return {
        ok: false,
        error: `"${refText}": 그 칸에 ${ref.nth}번째 숫자가 없다`,
      };
    return {
      ok: true,
      target: {
        page: table.page,
        box: table.bbox,
        form: 'cell#n',
        value: token.body,
        judgedValue: scanNumbers(examText)[ref.nth - 1]?.body ?? token.body,
        where,
        containerId,
        span: { start: token.start, end: token.end },
      },
    };
  }

  const block = side.document.blocks.find((b) => b.id === ref.blockId);
  if (!block || block.text === undefined)
    return { ok: false, error: `"${refText}": 그런 문단이 없다` };
  const token = scanNumbers(block.text)[ref.nth - 1];
  if (!token)
    return {
      ok: false,
      error: `"${refText}": 그 문단에 ${ref.nth}번째 숫자가 없다`,
    };
  const examText =
    side.exam?.blocks.find((b) => b.id === ref.blockId)?.text ?? block.text;
  const snippet = block.text
    .slice(Math.max(0, token.start - 18), token.start + token.body.length + 12)
    .replace(/\s+/g, ' ');
  return {
    ok: true,
    target: {
      page: block.page,
      box: block.bbox,
      form: 'block#n',
      value: token.body,
      judgedValue: scanNumbers(examText)[ref.nth - 1]?.body ?? token.body,
      where: `${ref.page}쪽 문장 · …${snippet}…`,
      containerId: block.id,
      span: { start: token.start, end: token.end },
    },
  };
}

export type PlaceMissing =
  | 'no_places' // 글자 자리를 주지 않았다(분해를 --places 없이 돌렸다)
  | 'container_missing' // 글자 자리에 그 칸·문단이 없다(분해가 글자를 잇지 못했거나, 글이 빈 칸이다)
  | 'page_differs' // 글자 자리의 그릇이 다른 쪽에 있다(자료가 서로 어긋났다)
  | 'no_glyphs_in_span'; // 그 글자 범위에 좌표 있는 글자가 없다

export type PlaceResult =
  | {
      found: true;
      boxes: Box[];
      /** 범위의 글자 가운데 좌표가 있던 글자의 수 / 범위의 글자 수(칸 전체면 null) */ covered: number;
      length: number | null;
    }
  | { found: false; reason: PlaceMissing };

/** 자리 하나의 좁힌 상자들을 글자 자리에서 얻는다. */
export function placeOf(
  target: Target,
  places: ReadonlyMap<string, PlaceContainer> | undefined,
): PlaceResult {
  if (!places) return { found: false, reason: 'no_places' };
  const container = places.get(target.containerId);
  if (!container) return { found: false, reason: 'container_missing' };
  if (container.page !== target.page)
    return { found: false, reason: 'page_differs' };
  const { boxes, covered } = spanBoxes(
    container,
    target.span?.start,
    target.span?.end,
  );
  if (boxes.length === 0) return { found: false, reason: 'no_glyphs_in_span' };
  return {
    found: true,
    boxes,
    covered,
    length: target.span ? target.span.end - target.span.start : null,
  };
}

/** 강조 하나의 상자를 얻은 기록. 측정(tools/measure-places.ts)이 이것을 센다. */
export interface PlaceRecord {
  highlightId: string;
  side: 'a' | 'b';
  ref: string;
  form: Target['form'];
  result: PlaceResult;
}

export interface ReconcileResult {
  input: ViewerInput;
  records: PlaceRecord[];
  /** 풀지 못한 자리 표기. 있으면 자료와 변환이 어긋난 것이다. */
  problems: string[];
}

const REASON_LABEL: Record<string, string> = {
  exact: '값이 같다',
  rounded_half_up: '반올림하면 같다',
  values_differ: '값이 다르다',
};

/** 「확인 못 함」으로 보여 줄 상태. 짝지은 표 안에서 짝을 못 찾은 것들이다. 나머지(표 자체가 짝이 없는 것 등)는 개수만 알린다. */
const isShownUnverified = (state: string) =>
  state.startsWith('asked:no_counterpart') || state === 'left:in_paired_table';
const isCompared = (state: string) => state.startsWith('compared:');

export function buildReconcileInput(
  a: Side,
  b: Side,
  outcome: LabOutcome,
): ReconcileResult {
  const highlights: Highlight[] = [];
  const items: Item[] = [];
  const records: PlaceRecord[] = [];
  const problems: string[] = [];
  const sides = { a, b };

  function addHighlight(
    id: string,
    sideId: 'a' | 'b',
    refText: string,
    kind: string,
  ): Target | null {
    const side = sides[sideId];
    const resolved = resolveTarget(side, refText);
    if (!resolved.ok) {
      problems.push(resolved.error);
      return null;
    }
    const target = resolved.target;
    const result = placeOf(target, side.places);
    records.push({
      highlightId: id,
      side: sideId,
      ref: refText,
      form: target.form,
      result,
    });
    highlights.push({
      id,
      documentId: side.id,
      page: target.page,
      box: [...target.box],
      ...(result.found ?
        {
          innerBoxes: result.boxes.map(
            (box) => [...box] as [number, number, number, number],
          ),
        }
      : {}),
      kind,
      text: target.value,
    });
    return target;
  }

  const describe = (label: string, target: Target) =>
    `${label} ${target.where}` +
    (target.judgedValue !== target.value ?
      `\n  ※ 판정은 「${target.judgedValue}」로 봤다(시험지가 바꾼 값). PDF 원문은 「${target.value}」`
    : '');

  // ── 판정: 불일치를 먼저, 그다음 일치 ──
  const verdicts = outcome.after.verdicts.map((verdict, index) => ({
    verdict,
    id: `v${index + 1}`,
  }));
  const ordered = [
    ...verdicts.filter((v) => v.verdict.outcome !== 'match'),
    ...verdicts.filter((v) => v.verdict.outcome === 'match'),
  ];
  for (const { verdict, id } of ordered) {
    const ta = addHighlight(`${id}-a`, 'a', verdict.a, verdict.outcome);
    const tb = addHighlight(`${id}-b`, 'b', verdict.b, verdict.outcome);
    if (!ta || !tb) continue;
    items.push({
      id,
      title: `${ta.judgedValue} ${verdict.outcome === 'match' ? '=' : '≠'} ${tb.judgedValue}`,
      detail: [
        describe('A', ta),
        describe('B', tb),
        `판정: ${REASON_LABEL[verdict.reason] ?? verdict.reason}`,
      ].join('\n'),
      highlightIds: [`${id}-a`, `${id}-b`],
      review: { status: 'pending' },
    });
  }

  // ── 확인 못 함 ──
  const hidden: Record<string, number> = {};
  for (const sideId of ['a', 'b'] as const) {
    let n = 0;
    for (const [refText, state] of Object.entries(outcome.states[sideId])) {
      if (isCompared(state)) continue;
      if (!isShownUnverified(state)) {
        hidden[sideId] = (hidden[sideId] ?? 0) + 1;
        continue;
      }
      n += 1;
      const id = `u-${sideId}${n}`;
      const target = addHighlight(id, sideId, refText, 'unverified');
      if (!target) continue;
      items.push({
        id,
        title: `${target.judgedValue} · 짝 없음`,
        detail: `${describe(sideId.toUpperCase(), target)}\n상태: ${state}`,
        highlightIds: [id],
        review: { status: 'pending' },
      });
    }
  }

  const count = (kind: string) =>
    verdicts.filter((v) => v.verdict.outcome === kind).length;
  const narrowed = records.filter((record) => record.result.found).length;
  const withPlaces = a.places !== undefined || b.places !== undefined;
  const notice = [
    `두 문서 대조 결과를 옮긴 것이다. 판정 ${verdicts.length}건(일치 ${count('match')}, 불일치 ${count('mismatch')}), 짝을 못 찾은 자리 ${items.filter((item) => item.id.startsWith('u-')).length}건.`,
    `목록에 넣지 않은 「확인 못 함」: A ${hidden.a ?? 0}자리, B ${hidden.b ?? 0}자리(짝지어지지 않은 표, 표 밖의 숫자).`,
    a.exam || b.exam ?
      '판정은 오류를 심은 시험지에 대해 낸 것이다. 그래서 불일치 항목이 PDF 화면에서는 같은 값으로 보일 수 있다.'
    : '',
    withPlaces ?
      `칸과 숫자의 상자는 문서를 분해할 때 나온 글자 좌표다(강조 ${highlights.length}개 중 ${narrowed}개가 상자를 얻었다). 못 얻은 강조는 표·문단 전체 상자로 보인다. 글자 층이 없는 쪽과 그림으로 박힌 표의 숫자는 분해된 자료에 없어 강조도 없다.`
    : '글자 자리(char-places.json) 없이 변환했다. 그래서 상자가 표 전체·문단 전체다. 칸과 숫자의 상자를 보려면 분해를 --places 로 돌려 다시 변환한다.',
  ]
    .filter(Boolean)
    .join('\n');

  const input: ViewerInput = {
    version: 1,
    notice,
    documents: [a, b].map((side) => ({
      id: side.id,
      title: side.title,
      url: side.url,
      pages: side.document.pages.map((page) => ({
        width: page.width,
        height: page.height,
      })),
    })),
    kinds: [
      { kind: 'mismatch', label: '불일치', color: '#dc2626' },
      { kind: 'match', label: '일치', color: '#15803d' },
      { kind: 'unverified', label: '확인 못 함(짝 없음)', color: '#6b7280' },
    ],
    highlights,
    items,
  };
  return { input, records, problems };
}
