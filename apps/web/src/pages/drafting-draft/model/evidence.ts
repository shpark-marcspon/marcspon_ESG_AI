// RP-04 개조식 초안 결과 셈(밴드 RPW1 ③ — 발주서 §2-3). 순수 함수 — React·화면·통신을 모른다.
// - 트리 = 지금 목차(getProject().outline)에 결과 잎을 key 로 붙인 것. 점 다섯: done · done ∧ unsupported 있음 · no_material · failed · not_run(결과에 없는 잎 포함).
// - bullet 갈래(S/engines/v2/checks.py:57-79): unsupported ∧ sources=[] → 근거 없음 · unsupported ∧ sources≠[] → 원문에 없는 숫자 · 아니면 칩.
// - 근거 두 층(sid:MARC-ENT-514): 옅은 = 고른 bullet 출처 중 그 쪽의 blockBox(블록 id 로 겹침 하나) · 진한 = sentence.boxes 전부 ·
//   그 쪽 출처가 모두 sentence null 이면 옅은 것만 + 「문단까지만 찾았어요」.
// - 좌표는 PDF pt · CropBox 왼쪽 위 원점(pdf.js page.view 와 같음) — 화면 자리 = 좌표 × 배율. /Rotate≠0 쪽은 맞추지 않는다(sid:MARC-ISSUE-493).
//   셈은 공용 뷰어 boxToScreenRect(회전 0)·영문번역 pages/translation-run/ui/pdf/boxRect.ts 를 옮겨 적음(이 칸은 위젯을 가져오지 않는다).
// - 띠: 결과의 목차 판·문서가 지금과 다를 때만 차이를 읽는다. 다시 만들기 옵션 셋(전체는 base 0).
import { minuteOf } from '../../../entities/drafting/model/index.ts';
import type {
  Box,
  Bullet,
  DraftingResult,
  Leaf,
  OutlineChanges,
  OutlineNode,
  Project,
  RunOptions,
  RunPage,
} from '../../../entities/drafting/model/index.ts';

/** 트리 점(시안 범례 다섯). */
export type Dot = 'done' | 'unsupported' | 'no_material' | 'failed' | 'not_run';

/** 잎 하나 → 점(결과에 없으면 not_run). */
export function dotOf(leaf: Leaf | undefined): Dot {
  if (!leaf) return 'not_run';
  const { outcome } = leaf;
  if (outcome.status === 'done')
    return outcome.bullets.some((bullet) => bullet.unsupported) ?
        'unsupported'
      : 'done';
  return outcome.status;
}

/** 트리 한 줄. */
export interface TreeRow {
  key: string;
  depth: number;
  /** 「1.1.2」. */
  number: string;
  title: string;
  /** 지금 목차의 제목 경로(자기까지) — 결과에 없는 잎도 경로 줄을 짓는다(RPW3 06b). */
  titlePath: string[];
  requirement: string;
  /** 초안을 지을 목차(하위 없음)인가. */
  isLeaf: boolean;
  /** 결과의 잎(없으면 null — 아직 만들지 않음). */
  leaf: Leaf | null;
  /** 잎만 — 부모 줄은 null. */
  dot: Dot | null;
}

/** 지금 목차 + 결과 → 트리 줄(rejected 면 잎 전부 not_run — 결과 잎은 붙이지 않는다). */
export function treeOf(
  nodes: readonly OutlineNode[],
  result: DraftingResult,
): TreeRow[] {
  const leaves =
    result.status.status === 'done' ?
      new Map(result.leaves.map((leaf) => [leaf.key, leaf]))
    : new Map<string, Leaf>();
  const parents = new Set(nodes.map((node) => node.parentKey));
  const counts: number[] = [];
  const paths = new Map<string, string[]>();
  return nodes.map((node) => {
    counts.length = node.depth;
    counts[node.depth - 1] = (counts[node.depth - 1] ?? 0) + 1;
    const isLeaf = !parents.has(node.key);
    const leaf = isLeaf ? (leaves.get(node.key) ?? null) : null;
    const titlePath = [...(paths.get(node.parentKey ?? '') ?? []), node.title];
    paths.set(node.key, titlePath);
    return {
      key: node.key,
      depth: node.depth,
      number: counts.slice(0, node.depth).join('.'),
      title: node.title,
      titlePath,
      requirement: node.requirement,
      isLeaf,
      leaf,
      dot: isLeaf ? dotOf(leaf ?? undefined) : null,
    };
  });
}

/** 잎 수(실행 중 머리 셈 — 결과가 아직 없을 때). */
export function leafCountOf(nodes: readonly OutlineNode[]) {
  const parents = new Set(nodes.map((node) => node.parentKey));
  return nodes.filter((node) => !parents.has(node.key)).length;
}

/** 머리 셈 「목차 n개 · 초안 n · 맞는 자료 없음 n · 못 만듦 n · 아직 n」(잎만). */
export function headCountsOf(rows: readonly TreeRow[]) {
  const leaves = rows.filter((row) => row.isLeaf);
  const of = (...dots: Dot[]) =>
    leaves.filter((row) => dots.includes(row.dot!)).length;
  return {
    total: leaves.length,
    drafted: of('done', 'unsupported'),
    noMaterial: of('no_material'),
    failed: of('failed'),
    notRun: of('not_run'),
  };
}

/** bullet 갈래. */
export type BulletKind = 'chips' | 'no_source' | 'not_in_source';

export function bulletKindOf(bullet: Bullet): BulletKind {
  if (!bullet.unsupported) return 'chips';
  return bullet.sources.length === 0 ? 'no_source' : 'not_in_source';
}

/** 출처 칩 — 출처 쪽마다 하나(차례대로, 겹침 하나). */
export function chipPagesOf(bullet: Bullet): number[] {
  return [...new Set(bullet.sources.map((source) => source.page))].sort(
    (a, b) => a - b,
  );
}

/** 「찾은 페이지 a~b」 — 쪽이 없으면 null, 하나면 [a, a]. */
export function pageSpanOf(pages: readonly number[]): [number, number] | null {
  if (pages.length === 0) return null;
  return [Math.min(...pages), Math.max(...pages)];
}

/** 쪽 위 근거 상자 하나. */
export interface Mark {
  layer: 'block' | 'sentence';
  blockId: string;
  box: Box;
}

/** 고른 bullet 의 그 쪽 근거 두 층. paragraphOnly = 그 쪽 출처가 모두 sentence null(진한 층 0). */
export function marksOf(
  bullet: Bullet | null,
  page: number,
): { marks: Mark[]; paragraphOnly: boolean } {
  const here = bullet?.sources.filter((source) => source.page === page) ?? [];
  const marks: Mark[] = [];
  const seen = new Set<string>();
  for (const source of here) {
    if (seen.has(source.blockId)) continue;
    seen.add(source.blockId);
    marks.push({
      layer: 'block',
      blockId: source.blockId,
      box: source.blockBox,
    });
  }
  for (const source of here)
    for (const box of source.sentence?.boxes ?? [])
      marks.push({ layer: 'sentence', blockId: source.blockId, box });
  return {
    marks,
    paragraphOnly:
      here.length > 0 && here.every((source) => source.sentence === null),
  };
}

/** 화면 자리(CSS 픽셀). */
export interface ScreenRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** PDF pt 상자(왼쪽 위 원점) → 그려진 쪽 위 자리. 쪽 크기가 0 이면 null(그리지 않는다). */
export function screenRectOf(
  box: Box,
  page: { width: number; height: number },
  scale: number,
): ScreenRect | null {
  if (!(page.width > 0 && page.height > 0)) return null;
  const [x0, y0, x1, y1] = box;
  return {
    left: Math.min(x0, x1) * scale,
    top: Math.min(y0, y1) * scale,
    width: Math.abs(x1 - x0) * scale,
    height: Math.abs(y1 - y0) * scale,
  };
}

/** 칸 폭에 맞춘 쪽 그림 배율(boxRect.ts fitScale 을 옮겨 적음 — 넓으면 base, 0.01 단위 내림). */
export function fitScale(
  available: number,
  pageWidth: number,
  base: number,
): number {
  if (!(available > 0 && pageWidth > 0)) return base;
  const fit = Math.floor((available / pageWidth) * 100) / 100;
  return Math.min(base, Math.max(fit, 0.01));
}

/** 띠를 위해 차이를 읽어야 하는가 — 결과의 목차 판이나 문서가 지금과 다를 때만. */
export function needsChanges(
  project: Project,
  result: DraftingResult,
): boolean {
  return (
    (project.outline !== null &&
      project.outline.outlineId !== result.outlineId) ||
    (project.pdf !== null && project.pdf.documentId !== result.pdf.documentId)
  );
}

/** 띠 셈 — 바뀐 목차 수(changed·added) · 줄 표지 · 문서를 다시 올렸는가. 바뀐 것이 없으면 null(띠 0). */
export function bandOf(changes: OutlineChanges) {
  const marks = new Map<string, 'changed' | 'added'>();
  for (const leaf of changes.leaves)
    if (leaf.change !== 'same') marks.set(leaf.key, leaf.change);
  const reuploaded = changes.pdf === 'changed';
  if (marks.size === 0 && !reuploaded) return null;
  return { count: marks.size, marks, reuploaded };
}

/** 다시 만들기 옵션 — 전체(base 0) · 바뀐 목차(rebuild []) · 이 목차(rebuild [key]). */
export function rebuildOptionsOf(
  how: { kind: 'all' } | { kind: 'changed' } | { kind: 'one'; key: string },
  projectId: number,
  runId: number,
): RunOptions {
  if (how.kind === 'all') return { projectId };
  return {
    projectId,
    base: { runId, rebuild: how.kind === 'one' ? [how.key] : [] },
  };
}

/** 앞 실행 위에서 다시 짓는 잎(S/flows/reuse.py s2_keys·reusable) — 문서가 바뀌었거나 앞 지도가 깨졌으면 잎 전부, 아니면 rebuild ∪ 바뀐·더한 잎 ∪ 앞 결과에서 done 아닌 잎. */
export function rebuildingKeysOf(
  rebuild: readonly string[],
  band: ReturnType<typeof bandOf>,
  rows: readonly TreeRow[],
  result: Pick<DraftingResult, 'mapping'>,
): Set<string> {
  const leaves = rows.filter((row) => row.isLeaf);
  if (band?.reuploaded || result.mapping.failedBatches.length > 0)
    return new Set(leaves.map((row) => row.key));
  return new Set([
    ...rebuild,
    ...(band?.marks.keys() ?? []),
    ...leaves
      .filter((row) => row.leaf?.outcome.status !== 'done')
      .map((row) => row.key),
  ]);
}

/** 다시 짓는 잎이 사용자가 고르거나 바꾼 잎(rebuild ∪ 띠 marks)보다 많은가 — 많으면 못 만듦·아직 잎도 함께 짓는다(RPW3 D4). */
export function rebuildsMoreThanAsked(
  rebuilding: ReadonlySet<string>,
  rebuild: readonly string[],
  band: ReturnType<typeof bandOf>,
): boolean {
  const asked = new Set([...rebuild, ...(band?.marks.keys() ?? [])]);
  return rebuilding.size > asked.size;
}

/** 실행 고르기 한 줄. */
export interface RunChoice {
  runId: number;
  /** 프로젝트의 몇 번째 실행인가(1 부터, 만든 차례). */
  n: number;
  at: string;
  /** 가장 새 실행인가(「지금」). */
  latest: boolean;
}

/** 실행 목록(새 것 먼저) → 고르기 줄. 지금 보는 실행이 이 쪽에 없으면 null(고르기를 숨긴다 — 고른 값을 보일 수 없다). */
export function runChoicesOf(page: RunPage, runId: number): RunChoice[] | null {
  if (!page.results.some((run) => run.id === runId)) return null;
  return page.results.map((run, index) => ({
    runId: run.id,
    n: page.count - index,
    at: minuteOf(run.createdAt),
    latest: index === 0,
  }));
}
