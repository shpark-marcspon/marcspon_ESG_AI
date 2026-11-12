// PDF 보기의 순수 셈(밴드 TRW6 ③, 6c v174 TR-P05·P05a). layout@1 + 고른 문체 → 쪽 목록 줄 · 쪽 하나의 상자 · 짝 · 경고. DOM 0, 글 0(열쇠와 수만).
// 짝 = variants[v].units[i] ↔ layout.units[i](TRS3 §1-2). 상자는 고른 문체의 level 로 짓는다(A·B level 이 다를 수 있음 — 발주서 W10).
//   level   상자                                         짝
//   block   단위의 member 마다 하나                       member j ↔ translations[j]
//   group   member 를 감싼 하나(점선)                     원문 member 전부 ↔ translations 전부
//   table   표 전체 하나(칸을 못 맞춤)                    표 원문 ↔ translations 전부
//   cell    표 테두리 하나 + bbox 있는 칸마다 하나        표 짝 하나(밴드 TRW7 ③b-2, sid:MARC-ENT-488): 원문·번역 같은 행·열 격자(grid).
//                                                         칸 상자도 그 표 짝을 가리키고(pair), 어느 칸인지는 상자의 cell — 짝 칸이 두 격자의 같은 칸을 강조.
//                                                         번역 칸이 없거나 빈 글이면(숫자 등 옮길 국문 없음) 원문 값, 원문이 빈 칸은 둘 다 비움.
//   source_only  member 마다 하나(흐림 — 머리글·꼬리말)   원문만
//   missing      member 마다 하나(빨간 점선)               원문 ↔ 번역 없음
// 단위 kind visual 은 「그림 안 글」 표지(visual 참). 글자 없는 쪽(skipped.imageOnlyPages · textLayer none)은 상자 0.
// 경고: variant 가 null 이거나 고른 문체와 같은 것만 이 문체의 것. tag 가 그 쪽 단위의 tag 와 같으면 그 단위 상자에 ⚠, 아니면 쪽 경고(짝 칸 위 한 줄).
import type {
  LayoutBox,
  LayoutUnit,
  LayoutVariantLabel,
  LayoutWarning,
  LayoutWarningCode,
  PlacedLevel,
  PlacedUnit,
  TranslationLayout,
} from '../../../entities/translation/model/index.ts';

export type BoxLook =
  | 'block'
  | 'group'
  | 'table'
  | 'table_border'
  | 'cell'
  | 'source_only'
  | 'missing';

/** 쪽 위 상자 하나. id 는 쪽 안에서 하나(data-box). pair 는 그 상자를 눌렀을 때의 짝 차례(pairs 의 자리). */
export interface PdfBox {
  id: string;
  unit: number;
  look: BoxLook;
  bbox: LayoutBox;
  pair: number;
  visual: boolean;
  /** 이 상자에 걸린 경고(귀퉁이 ⚠). */
  warned: boolean;
  /** 표 칸 상자면 그 칸(0 부터) — 누르면 표 짝을 고르고 이 칸을 강조. */
  cell?: PdfCellAt;
}

export interface PdfCellAt {
  row: number;
  col: number;
}

/** 표 짝의 격자 한 칸(원문·번역 같은 자리). */
export interface PdfGridCell extends PdfCellAt {
  source: string;
  translation: string;
}

/** 표 짝의 격자(level cell). 칸이 없는 자리는 cells 에 없다(빈 칸). */
export interface PdfGrid {
  rows: number;
  cols: number;
  cells: readonly PdfGridCell[];
}

/** cell 은 밴드 TRW7 ③b-2 부터 짓지 않는다(표는 짝 하나 — sid:MARC-ENT-488). 붙이기 규칙(pdfAttach searchOrder)을 0줄로 두려고 이름만 남김. */
export type PairKind =
  'block' | 'group' | 'table' | 'cell' | 'source_only' | 'missing';

/** 짝 하나(짝 칸의 한 줄). translation 이 null 이면 번역 없음(source_only·missing). */
export interface PdfPair {
  unit: number;
  kind: PairKind;
  /** 상자 kind(머리글·꼬리말 가름 등). */
  unitKind: LayoutUnit['kind'];
  visual: boolean;
  /** 원문(묶음이면 member 마다 하나). */
  source: readonly string[];
  /** 번역(묶음·표면 여럿). null = 번역 없음. */
  translation: readonly string[] | null;
  /** 칸을 맞춘 표(level cell)의 격자. 칸을 못 맞춘 표(level table)는 없음. */
  grid?: PdfGrid;
  /** block 의 몇째 member(0 부터). */
  member?: number;
}

export interface PdfWarning {
  code: LayoutWarningCode;
  page: number | null;
  tag: string | null;
  /** 견주기에서 한 문체에만 걸린 경고면 그 문체(두 문체 다·한 문체 실행이면 null — 「스타일 B 에서만」). */
  only: 'A' | 'B' | null;
  /** 붙은 단위(tag 가 그 쪽 단위와 맞을 때). */
  unit: number | null;
}

export interface PdfPageView {
  page: number;
  width: number;
  height: number;
  /** 글자 없는 쪽(그림뿐) — 상자 0. */
  imageOnly: boolean;
  boxes: readonly PdfBox[];
  pairs: readonly PdfPair[];
  /** 「번역 N곳」 — 번역이 붙은 단위 수(source_only·missing 빼고). */
  places: number;
  warnings: readonly PdfWarning[];
  /** 자리를 찾지 못한 번역. */
  unplaced: readonly string[];
}

/** 쪽 목록 한 줄. */
export interface PdfPageLine {
  page: number;
  imageOnly: boolean;
  places: number;
  /** 「확인할 곳 N」(이 문체의 경고 수). */
  checks: number;
  /** 「스타일 B 에서만」 — 이 쪽 경고가 모두 한 문체에만 있을 때. */
  only: 'A' | 'B' | null;
}

const LOOK_OF: Readonly<Record<PlacedLevel, BoxLook>> = {
  block: 'block',
  group: 'group',
  table: 'table',
  cell: 'table_border',
  source_only: 'source_only',
  missing: 'missing',
};

/** 고를 수 있는 문체(한 문체 실행이면 single 하나). */
export const variantLabelsOf = (
  layout: TranslationLayout,
): LayoutVariantLabel[] => layout.variants.map((variant) => variant.label);

const isCompare = (layout: TranslationLayout) =>
  layout.variants.some((variant) => variant.label !== 'single');

/** member 상자들을 감싼 하나. */
function unionOf(boxes: readonly LayoutBox[]): LayoutBox {
  return [
    Math.min(...boxes.map((box) => box[0])),
    Math.min(...boxes.map((box) => box[1])),
    Math.max(...boxes.map((box) => box[2])),
    Math.max(...boxes.map((box) => box[3])),
  ];
}

/** 이 문체에 걸린 경고(그림뿐 경고는 문체와 상관없이 — 판 P05a). */
function warningsFor(
  layout: TranslationLayout,
  label: LayoutVariantLabel,
): PdfWarning[] {
  const compare = isCompare(layout);
  const mine = layout.warnings.filter(
    (warning) =>
      warning.variant === null ||
      warning.variant === label ||
      warning.code === 'image_only_page',
  );
  // 같은 경고(code·page·tag)가 두 문체 다에 있으면 「…에서만」을 붙이지 않는다.
  const both = (warning: LayoutWarning) =>
    layout.warnings.some(
      (other) =>
        other !== warning &&
        other.code === warning.code &&
        other.page === warning.page &&
        other.tag === warning.tag &&
        other.variant !== warning.variant,
    );
  return mine.map((warning) => ({
    code: warning.code,
    page: warning.page,
    tag: warning.tag,
    only:
      (
        compare &&
        (warning.variant === 'A' || warning.variant === 'B') &&
        !both(warning)
      ) ?
        warning.variant
      : null,
    unit:
      warning.page === null || warning.tag === null ?
        null
      : (() => {
          const at = layout.units.findIndex(
            (unit) => unit.page === warning.page && unit.tag === warning.tag,
          );
          return at < 0 ? null : at;
        })(),
  }));
}

const imageOnlyOf = (layout: TranslationLayout, page: number) =>
  layout.skipped.imageOnlyPages.includes(page) ||
  layout.pages.some((each) => each.page === page && each.textLayer === 'none');

/** 표 짝 격자: 원문 칸(unit.cells — bbox 없는 칸도) 자리에 번역 칸(같은 row·col). 번역이 없거나 빈 글이면 원문 값. */
function gridOf(unit: LayoutUnit, placed: PlacedUnit): PdfGrid {
  const sources = unit.cells ?? [];
  const cells = sources.map((cell) => {
    const text = placed.cells?.find(
      (each) => each.row === cell.row && each.col === cell.col,
    )?.text;
    return {
      row: cell.row,
      col: cell.col,
      source: cell.source,
      translation:
        cell.source.trim() === '' ? ''
        : text === undefined || text.trim() === '' ? cell.source
        : text,
    };
  });
  return {
    rows: Math.max(0, ...cells.map((cell) => cell.row + 1)),
    cols: Math.max(0, ...cells.map((cell) => cell.col + 1)),
    cells,
  };
}

/** 쪽 하나의 상자·짝(placed 가 없으면 — 거절·문체 없음 — 상자 0). */
export function pdfPageOf(
  layout: TranslationLayout,
  label: LayoutVariantLabel,
  page: number,
): PdfPageView {
  const size = layout.pages.find((each) => each.page === page);
  const variant = layout.variants.find((each) => each.label === label);
  const warnings = warningsFor(layout, label).filter(
    (warning) => warning.page === page,
  );
  const warnedUnits = new Set(
    warnings.flatMap((warning) =>
      warning.unit === null ? [] : [warning.unit],
    ),
  );
  const imageOnly = imageOnlyOf(layout, page);
  const boxes: PdfBox[] = [];
  const pairs: PdfPair[] = [];
  let places = 0;
  if (!imageOnly && variant !== undefined)
    layout.units.forEach((unit, index) => {
      if (unit.page !== page) return;
      const placed: PlacedUnit | undefined = variant.units[index];
      if (placed === undefined) return;
      const visual = unit.kind === 'visual';
      const warned = warnedUnits.has(index);
      const base = {
        unit: index,
        unitKind: unit.kind,
        visual,
      };
      const look = LOOK_OF[placed.level];
      if (placed.level !== 'source_only' && placed.level !== 'missing')
        places += 1;
      if (
        placed.level === 'block' ||
        placed.level === 'source_only' ||
        placed.level === 'missing'
      ) {
        unit.members.forEach((member, j) => {
          boxes.push({
            id: member.id,
            unit: index,
            look,
            bbox: member.bbox,
            pair: pairs.length,
            visual,
            warned,
          });
          pairs.push({
            ...base,
            kind: placed.level as PairKind,
            source: [member.source],
            translation:
              placed.level === 'block' ?
                placed.translations?.[j] === undefined ?
                  null
                : [placed.translations[j]!]
              : null,
            member: j,
          });
        });
        return;
      }
      if (unit.members.length === 0) return;
      const whole = pairs.length;
      const grid = placed.level === 'cell' ? gridOf(unit, placed) : undefined;
      boxes.push({
        id: `${unit.members[0]!.id}#${placed.level}`,
        unit: index,
        look,
        bbox: unionOf(unit.members.map((member) => member.bbox)),
        pair: whole,
        visual,
        warned,
      });
      pairs.push({
        ...base,
        kind: placed.level === 'group' ? 'group' : 'table',
        source: unit.members.map((member) => member.source),
        translation:
          placed.level === 'cell' ?
            (placed.cells ?? []).map((cell) => cell.text)
          : (placed.translations ?? []),
        ...(grid === undefined ? {} : { grid }),
      });
      if (placed.level !== 'cell') return;
      for (const cell of unit.cells ?? []) {
        if (cell.bbox === null) continue;
        boxes.push({
          id: cell.id,
          unit: index,
          look: 'cell',
          bbox: cell.bbox,
          pair: whole,
          visual,
          warned,
          cell: { row: cell.row, col: cell.col },
        });
      }
    });
  return {
    page,
    width: size?.width ?? 0,
    height: size?.height ?? 0,
    imageOnly,
    boxes,
    pairs,
    places,
    warnings,
    unplaced: (variant?.unplaced ?? [])
      .filter((each) => each.page === page)
      .map((each) => each.text),
  };
}

/** 쪽 목록(layout 의 쪽 차례). */
export function pdfPageLinesOf(
  layout: TranslationLayout,
  label: LayoutVariantLabel,
): PdfPageLine[] {
  const warnings = warningsFor(layout, label);
  return layout.pages.map(({ page }) => {
    const here = warnings.filter((warning) => warning.page === page);
    const onlys = new Set(here.map((warning) => warning.only));
    return {
      page,
      imageOnly: imageOnlyOf(layout, page),
      places: pdfPageOf(layout, label, page).places,
      checks: here.length,
      only:
        here.length > 0 && onlys.size === 1 ? (here[0]!.only ?? null) : null,
    };
  });
}

/** 쪽에 매이지 않은 경고(page null — 짝 칸 위 한 줄만). */
export const looseWarningsOf = (
  layout: TranslationLayout,
  label: LayoutVariantLabel,
): PdfWarning[] =>
  warningsFor(layout, label).filter((warning) => warning.page === null);

/** 고른 문체의 단계(짝 칸 머리 한 줄 — autofix·translated). */
export const stageOf = (
  layout: TranslationLayout,
  label: LayoutVariantLabel,
): 'autofix' | 'translated' | null =>
  layout.variants.find((variant) => variant.label === label)?.stage ?? null;
