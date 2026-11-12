// 결과 글 칸 고치기의 순수 규칙(밴드 IRW11, 결정 sid:MARC-ENT-561). React·DOM·통신을 모른다.
// 서버 규칙(apps/api-py/esgapi/materiality/outputs/edits.py·contracts/edit_shapes.py)을 옮겨 적었다(가져오지 않는다):
//   - 칸 주소(JSON Pointer)는 POINTER_PATTERN 셋뿐: T/(impact|pathway)/rows/{r}/impactDefinition · T/pathway/rows/{r}/(impactDriver|
//     businessImpact|financialImpact) · T/(impact|financial|pathway)/rows/{r}/context/(regulations|controversies)/{k}/(title|summary|url),
//     T = /part2/topics/{t}/subtopics/{s}.
//   - 바른 주소(_canonical·groups): 맥락 항목은 그 토픽·쪽에서 url(strip — 빈 글·null 은 안 묶음)이 같은 impact·financial 항목 중 첫 자리
//     (모든 서브토픽 impact 다 → 모든 서브토픽 financial — 화면 mergedItems 와 같은 차례). url 이 비면 자기. pathway 항목은 fin(i-1)의
//     재무 항목(같은 k)으로 옮긴 뒤 같은 규칙. fin null·k 범위 밖이면 고칠 수 없음.
//     ★ 웹은 지금 결과(고친 판)로 묶는다 — 서버가 url 겹침·여럿 묶음 url 비우기를 막으니 고친 판의 묶음 = 원본 묶음(발주서 Q1 까닭).
//   - 값(_value): 빈 글·공백만 → null. 길이는 코드포인트 — 정의·①②③·summary 4,000 · title 1,000 · url 2,048. url 은 trim 이
//     ^https?:// . 같은 토픽·쪽의 다른 묶음 url(strip)과 같아지면 거절 · 묶음의 impact+financial 항목이 둘 이상인데 url 을 비우면 거절.
//     제어 문자·짝 없는 서로게이트는 서버만 거절한다(화면은 「저장하지 못했어요」 — 발주서 §5 ⑦).
// Directive: 바른 주소 차례·묶음 규칙은 서버 outputs/edits.py 와 같이 바꿀 것.
import { SIDES, finOf, rowsOf } from './result.ts';
import type {
  ContextItem,
  ImpactLine,
  MaterialityResult,
  MergedItem,
  PathwayLine,
  Side,
} from './result.ts';

export type RowField =
  'impactDefinition' | 'impactDriver' | 'businessImpact' | 'financialImpact';
export type ItemField = 'title' | 'summary' | 'url';
export type FieldKind = RowField | ItemField;

/** 맥락 항목 하나의 자리(결과 본문 안 — 0부터). */
export interface ItemRef {
  topic: number;
  subtopic: number;
  phase: 'impact' | 'financial' | 'pathway';
  row: number;
  side: Side;
  k: number;
}

/** 서버 POINTER_PATTERN(contracts/edit_shapes.py) 그대로. */
const N = '(0|[1-9][0-9]{0,5})';
export const POINTER_PATTERN = new RegExp(
  `^/part2/topics/${N}/subtopics/${N}/(` +
    `(impact|pathway)/rows/${N}/impactDefinition` +
    `|pathway/rows/${N}/(impactDriver|businessImpact|financialImpact)` +
    `|(impact|financial|pathway)/rows/${N}/context/(regulations|controversies)/${N}/(title|summary|url)` +
    ')$',
);

/** 칸 주소: 줄 칸(영향 정의·①②③). */
export const rowPointer = (
  at: { topic: number; subtopic: number; row: number },
  phase: 'impact' | 'pathway',
  field: RowField,
) =>
  `/part2/topics/${at.topic}/subtopics/${at.subtopic}/${phase}/rows/${at.row}/${field}`;

/** 칸 주소: 맥락 항목 칸(title·summary·url). */
export const itemPointer = (ref: ItemRef, field: ItemField) =>
  `/part2/topics/${ref.topic}/subtopics/${ref.subtopic}/${ref.phase}/rows/${ref.row}/context/${ref.side}/${ref.k}/${field}`;

const strip = (url: string | null): string | null =>
  url !== null && url.trim() !== '' ? url.trim() : null;

function contextItem(
  result: MaterialityResult,
  ref: ItemRef,
): ContextItem | null {
  if (result.part2.status !== 'done') return null;
  const sub = result.part2.topics[ref.topic]?.subtopics[ref.subtopic];
  if (sub === undefined) return null;
  const row = rowsOf<{ context: Record<Side, ContextItem[]> }>(sub[ref.phase])[
    ref.row
  ];
  return row?.context[ref.side][ref.k] ?? null;
}

/** 한 토픽·한 쪽의 impact·financial 항목(묶음 차례 — 모든 서브토픽 impact 다음 모든 서브토픽 financial). */
function sideItems(
  result: MaterialityResult,
  topic: number,
  side: Side,
): { ref: ItemRef; item: ContextItem }[] {
  if (result.part2.status !== 'done') return [];
  const subs = result.part2.topics[topic]?.subtopics ?? [];
  const out: { ref: ItemRef; item: ContextItem }[] = [];
  for (const phase of ['impact', 'financial'] as const)
    subs.forEach((sub, subtopic) =>
      rowsOf<{ context: Record<Side, ContextItem[]> }>(sub[phase]).forEach(
        (row, r) =>
          row.context[side].forEach((item, k) =>
            out.push({
              ref: { topic, subtopic, phase, row: r, side, k },
              item,
            }),
          ),
      ),
    );
  return out;
}

const sameRef = (a: ItemRef, b: ItemRef) =>
  a.topic === b.topic &&
  a.subtopic === b.subtopic &&
  a.phase === b.phase &&
  a.row === b.row &&
  a.side === b.side &&
  a.k === b.k;

/** 묶음 하나: 첫 자리(바른 주소 자리)와 impact·financial 항목 수·지금 url(strip). */
export interface ItemGroup {
  first: ItemRef;
  members: number;
  url: string | null;
}

/** 한 토픽·한 쪽의 묶음들(서버 groups 의 impact·financial 몫). */
export function groupsOf(
  result: MaterialityResult,
  topic: number,
  side: Side,
): ItemGroup[] {
  const groups: ItemGroup[] = [];
  const byUrl = new Map<string, ItemGroup>();
  for (const { ref, item } of sideItems(result, topic, side)) {
    const url = strip(item.url);
    const seen = url === null ? undefined : byUrl.get(url);
    if (seen !== undefined) {
      seen.members += 1;
      continue;
    }
    const group: ItemGroup = { first: ref, members: 1, url };
    groups.push(group);
    if (url !== null) byUrl.set(url, group);
  }
  return groups;
}

/** 그 항목이 든 묶음(pathway 는 재무 항목으로 옮긴 뒤). 고칠 수 없으면 null(fin null·k 범위 밖·자리 없음). */
export function groupOf(
  result: MaterialityResult,
  ref: ItemRef,
): ItemGroup | null {
  let target = ref;
  if (ref.phase === 'pathway') {
    if (result.part2.status !== 'done') return null;
    const sub = result.part2.topics[ref.topic]?.subtopics[ref.subtopic];
    if (sub === undefined) return null;
    const row = rowsOf(sub.pathway)[ref.row];
    if (row === undefined) return null;
    const fin = finOf(sub, row.i);
    if (fin === null) return null;
    target = { ...ref, phase: 'financial', row: fin };
  }
  const item = contextItem(result, target);
  if (item === null) return null;
  const url = strip(item.url);
  for (const group of groupsOf(result, target.topic, target.side)) {
    if (url === null ? sameRef(group.first, target) : group.url === url)
      return group;
  }
  return null;
}

/** 바른 자리(서버 _canonical 의 맥락 항목 갈래). 고칠 수 없으면 null(발주서 Q4). */
export const canonicalItem = (
  result: MaterialityResult,
  ref: ItemRef,
): ItemRef | null => groupOf(result, ref)?.first ?? null;

/** 상한(코드포인트, 서버 edit_shapes.py 어림 값). */
export const EDIT_LIMITS: Readonly<Record<FieldKind, number>> = {
  impactDefinition: 4000,
  impactDriver: 4000,
  businessImpact: 4000,
  financialImpact: 4000,
  summary: 4000,
  title: 1000,
  url: 2048,
};

/** 글자 수(코드포인트 — 서버 len(str) 과 같다). */
export const codepoints = (text: string) => Array.from(text).length;

const SAFE_URL = /^https?:\/\//;

/** 화면 칸 하나의 고칠 자리(편집 줄의 글 상자 하나). pointer 는 바른 주소. */
export interface EditField {
  pointer: string;
  kind: FieldKind;
  /** 지금 값(결과 그대로). */
  value: string | null;
  /** url 칸만: 그 묶음(같은 출처·비울 수 없음 검사). */
  group?: ItemGroup;
  /** url 칸만: 그 토픽 차례(같은 출처 검사). */
  topic?: number;
}

export type EditError =
  | 'tooLong'
  | 'titleTooLong'
  | 'urlTooLong'
  | 'urlScheme'
  | 'urlLocked'
  | 'urlDuplicate';

/** 보낼 값: 공백만이면 null, 아니면 쓴 글 그대로(앞뒤 공백 포함 — 서버가 정함). */
export const outgoing = (draft: string): string | null =>
  draft.trim() === '' ? null : draft;

/** 바뀐 칸만(지금 값 null 은 '' 로 견줌). 같은 바른 주소는 하나로(서버 「앞 고침과 같은 칸」 400 — critic 덧). */
export function changesOf(
  fields: readonly EditField[],
  drafts: Readonly<Record<string, string>>,
): { pointer: string; value: string | null }[] {
  const seen = new Set<string>();
  const out: { pointer: string; value: string | null }[] = [];
  for (const field of fields) {
    if (seen.has(field.pointer)) continue;
    seen.add(field.pointer);
    const draft = drafts[field.pointer];
    if (draft === undefined || draft === (field.value ?? '')) continue;
    out.push({ pointer: field.pointer, value: outgoing(draft) });
  }
  return out;
}

/** 판 오류 여섯을 [저장] 때 미리 거른다(발주서 Q8). 바뀐 칸만 본다. 돌려주는 것은 바른 주소 → 오류. */
export function checkDrafts(
  result: MaterialityResult,
  fields: readonly EditField[],
  drafts: Readonly<Record<string, string>>,
): Record<string, EditError> {
  const errors: Record<string, EditError> = {};
  const changes = changesOf(fields, drafts);
  const changed = new Map(changes.map((c) => [c.pointer, c.value]));
  /** url 칸의 지금 값(이 저장 반영) — 바른 주소 → url(strip). */
  const urlNow = (pointer: string, fallback: string | null) =>
    changed.has(pointer) ? strip(changed.get(pointer)!) : strip(fallback);
  for (const field of fields) {
    if (!changed.has(field.pointer) || errors[field.pointer]) continue;
    const value = changed.get(field.pointer)!;
    if (value === null) {
      if (field.kind === 'url' && field.group && field.group.members >= 2)
        errors[field.pointer] = 'urlLocked';
      continue;
    }
    if (codepoints(value) > EDIT_LIMITS[field.kind]) {
      errors[field.pointer] =
        field.kind === 'title' ? 'titleTooLong'
        : field.kind === 'url' ? 'urlTooLong'
        : 'tooLong';
      continue;
    }
    if (field.kind !== 'url') continue;
    if (!SAFE_URL.test(value.trim())) {
      errors[field.pointer] = 'urlScheme';
      continue;
    }
    if (field.group === undefined || field.topic === undefined) continue;
    const mine = value.trim();
    const side = field.group.first.side;
    const clash = groupsOf(result, field.topic, side).some((group) => {
      const pointer = itemPointer(group.first, 'url');
      return pointer !== field.pointer && urlNow(pointer, group.url) === mine;
    });
    if (clash) errors[field.pointer] = 'urlDuplicate';
  }
  return errors;
}

/** GET …/result/edits 의 고침 하나(거울이 지난 꼴). */
export interface ResultEdit {
  pointer: string;
  value: string | null;
  original: string | null;
  editedAt: string;
  editedBy: { name: string };
}

/** 화면 칸 하나 ↔ 고침: 주소 목록과 겹친 고침 중 editedAt 가 가장 늦은 것. 없으면 null. */
export function editOfCell(
  pointers: readonly string[],
  edits: readonly ResultEdit[],
): ResultEdit | null {
  let latest: ResultEdit | null = null;
  const wanted = new Set(pointers);
  for (const edit of edits)
    if (
      wanted.has(edit.pointer) &&
      (latest === null || edit.editedAt > latest.editedAt)
    )
      latest = edit;
  return latest;
}

const STAMP = /^\d{4}-(\d{2})-(\d{2})T(\d{2}):(\d{2})/;
/** +09:00 ISO 글에서 「MM-DD HH:mm」 을 글자로 뗀다(Date 셈 0). 못 떼면 「–」. */
export function editedStamp(editedAt: string): string {
  const m = STAMP.exec(editedAt);
  return m === null ? '–' : `${m[1]}-${m[2]} ${m[3]}:${m[4]}`;
}
/** 「HH:mm」(배지). 못 떼면 「–」. */
export function editedClock(editedAt: string): string {
  const m = STAMP.exec(editedAt);
  return m === null ? '–' : `${m[3]}:${m[4]}`;
}

/** 칸 묶음의 고친 칸 수와 가장 늦은 고침(배지 — 발주서 Q10). */
export function editSummary(
  cells: readonly (readonly string[])[],
  edits: readonly ResultEdit[],
): { count: number; latest: ResultEdit | null } {
  let count = 0;
  let latest: ResultEdit | null = null;
  for (const cell of cells) {
    const edit = editOfCell(cell, edits);
    if (edit === null) continue;
    count += 1;
    if (latest === null || edit.editedAt > latest.editedAt) latest = edit;
  }
  return { count, latest };
}

/** 2-1·2-2 줄의 요약마다 고칠 자리(summaries 와 같은 길이 — 고칠 수 없는 요약은 null, 발주서 Q4·critic 덧). */
export function summaryFields(
  result: MaterialityResult,
  line: ImpactLine | PathwayLine,
  phase: 'impact' | 'pathway',
): (EditField | null)[] {
  return line.summaryAt.map((at, n) => {
    const first = canonicalItem(result, {
      ...line.at,
      phase,
      side: at.side,
      k: at.k,
    });
    return first === null ? null : (
        {
          pointer: itemPointer(first, 'summary'),
          kind: 'summary',
          value: line.summaries[n] ?? null,
        }
      );
  });
}

/** 2-1 줄의 고칠 칸(영향 정의 + 요약들). */
export function impactFields(
  result: MaterialityResult,
  line: ImpactLine,
): { definition: EditField; summaries: (EditField | null)[] } {
  return {
    definition: {
      pointer: rowPointer(line.at, 'impact', 'impactDefinition'),
      kind: 'impactDefinition',
      value: line.definition,
    },
    summaries: summaryFields(result, line, 'impact'),
  };
}

const PATHWAY_ROW_FIELDS = [
  ['definition', 'impactDefinition'],
  ['driver', 'impactDriver'],
  ['business', 'businessImpact'],
  ['financial', 'financialImpact'],
] as const;
export type PathwayCell = (typeof PATHWAY_ROW_FIELDS)[number][0];

/** 2-2 줄의 고칠 칸(영향 정의·①②③ + 펼친 요약들). */
export function pathwayFields(
  result: MaterialityResult,
  line: PathwayLine,
): { rows: Record<PathwayCell, EditField>; summaries: (EditField | null)[] } {
  const rows = Object.fromEntries(
    PATHWAY_ROW_FIELDS.map(([cell, field]) => [
      cell,
      {
        pointer: rowPointer(line.at, 'pathway', field),
        kind: field,
        value: line[cell],
      },
    ]),
  ) as Record<PathwayCell, EditField>;
  return { rows, summaries: summaryFields(result, line, 'pathway') };
}

/** 1-1 칸 항목 하나의 고칠 칸(제목·출처 주소). 자리가 없으면 null. */
export function itemFields(
  result: MaterialityResult,
  topic: number,
  item: MergedItem,
): { title: EditField; url: EditField } | null {
  if (item.at === null) return null;
  const ref: ItemRef = { topic, ...item.at };
  const group = groupOf(result, ref) ?? undefined;
  const first = group?.first ?? ref;
  return {
    title: {
      pointer: itemPointer(first, 'title'),
      kind: 'title',
      value: item.title,
    },
    url: {
      pointer: itemPointer(first, 'url'),
      kind: 'url',
      value: item.url,
      group,
      topic,
    },
  };
}

/** 2-1·2-2 요약 칸의 주소 목록(연필): 보이는 요약 + 지금 summary 가 빈 항목(비운 요약도 연필이 붙게). */
export function summaryCellPointers(
  result: MaterialityResult,
  line: ImpactLine | PathwayLine,
  phase: 'impact' | 'pathway',
  context: Record<Side, readonly ContextItem[]> | null,
): string[] {
  const refs = line.summaryAt.map((at) => ({ side: at.side, k: at.k }));
  if (context !== null)
    for (const side of SIDES)
      context[side].forEach((item, k) => {
        if (item.summary === null) refs.push({ side, k });
      });
  const out: string[] = [];
  for (const { side, k } of refs) {
    const first = canonicalItem(result, { ...line.at, phase, side, k });
    if (first !== null) out.push(itemPointer(first, 'summary'));
  }
  return out;
}

/** 줄의 맥락(연필 — 비운 요약 찾기). 자리가 없으면 null. */
export function lineContext(
  result: MaterialityResult,
  line: ImpactLine | PathwayLine,
  phase: 'impact' | 'pathway',
): Record<Side, readonly ContextItem[]> | null {
  if (result.part2.status !== 'done') return null;
  const sub = result.part2.topics[line.at.topic]?.subtopics[line.at.subtopic];
  if (sub === undefined) return null;
  const row = rowsOf<{ context: Record<Side, ContextItem[]> }>(sub[phase])[
    line.at.row
  ];
  return row?.context ?? null;
}

/** 1-1 칸의 주소 목록(연필): 항목마다 제목·주소의 바른 주소. */
export function shortlistCellPointers(
  result: MaterialityResult,
  topic: number,
  items: readonly MergedItem[],
): string[] {
  return items.flatMap((item) => {
    const fields = itemFields(result, topic, item);
    return fields === null ? [] : [fields.title.pointer, fields.url.pointer];
  });
}
