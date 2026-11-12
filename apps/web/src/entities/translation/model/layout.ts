// translation.layout@1 의 화면 꼴(밴드 TRW6 ①, 정본: apps/api-py/esgapi/translation/tests/data/flow-shapes/translation.layout@1.schema.json —
// TRS3 §1-2). 좌표는 pt, 왼쪽 위 원점(쪽 width·height 로 나눈다). variants[].units[i] ↔ units[i]. 거절이면 variants 가 빈 목록.
// PDF 흐름 판별: 실행 flowId 가 PDF_FLOW_PREFIX 로 시작 · 결과에 layout 이 있음 = GET /runs/{id} 의 resultShapes 에 LAYOUT_SHAPE.

/** PDF 흐름 id(POST /runs 본문 flowId — TRS3 §1-1). */
export const PDF_FLOW_ID = 'translation.pdf@158';
/** PDF 흐름 id 의 앞(판이 바뀌어도 PDF 흐름). */
export const PDF_FLOW_PREFIX = 'translation.pdf@';
/** layout 결과의 schemaVersion(resultShapes 에 실린다). */
export const LAYOUT_SHAPE = 'translation.layout@1';

export const isPdfFlow = (flowId: string): boolean =>
  flowId.startsWith(PDF_FLOW_PREFIX);

export type LayoutBox = readonly [
  x0: number,
  y0: number,
  x1: number,
  y1: number,
];
export type LayoutVariantLabel = 'single' | 'A' | 'B';

export interface LayoutPage {
  page: number;
  width: number;
  height: number;
  textLayer: 'present' | 'none';
}

export interface LayoutMember {
  id: string;
  key: string | null;
  kind: 'heading' | 'paragraph' | 'table';
  bbox: LayoutBox;
  source: string;
}

export interface LayoutCell {
  row: number;
  col: number;
  id: string;
  bbox: LayoutBox | null;
  source: string;
}

export type LayoutUnitKind = 'block' | 'visual' | 'table' | 'header' | 'footer';

export interface LayoutUnit {
  tag: string | null;
  page: number;
  kind: LayoutUnitKind;
  members: readonly LayoutMember[];
  cells?: readonly LayoutCell[];
  rows?: readonly number[];
}

export type PlacedLevel =
  'block' | 'group' | 'cell' | 'table' | 'source_only' | 'missing';

export interface PlacedUnit {
  tag: string | null;
  page: number;
  level: PlacedLevel;
  translations: readonly string[] | null;
  cells?: readonly { row: number; col: number; text: string }[];
}

export interface LayoutVariant {
  label: LayoutVariantLabel;
  stage: 'autofix' | 'translated';
  units: readonly PlacedUnit[];
  unplaced: readonly { page: number; text: string }[];
}

export type LayoutWarningCode =
  | 'image_only_page'
  | 'tag_missing'
  | 'tag_extra'
  | 'tag_shift'
  | 'page_missing'
  | 'length_ratio';

export interface LayoutWarning {
  code: LayoutWarningCode;
  page: number | null;
  tag: string | null;
  variant: LayoutVariantLabel | null;
}

export interface TranslationLayout {
  status: 'done' | 'rejected';
  pages: readonly LayoutPage[];
  units: readonly LayoutUnit[];
  variants: readonly LayoutVariant[];
  skipped: {
    emptyTables: readonly string[];
    imageOnlyPages: readonly number[];
  };
  warnings: readonly LayoutWarning[];
}
