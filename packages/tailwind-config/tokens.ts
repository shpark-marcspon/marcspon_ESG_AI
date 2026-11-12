/** Tailwind 전용 스냅샷 토큰 → Tailwind theme/shadcn 매핑. */
import {
  colorSchema,
  semanticColors,
  tailwindBreakpoints,
  tailwindContainerSizes,
  tailwindFontFamilies,
  tailwindFontWeights,
  tailwindRadii,
  tailwindZIndices,
  textStyles,
} from "./theme-tokens";

type NestedColors = { [key: string]: string | NestedColors };

/**
 * "grey.500" / "text.secondary.inverse" 형태의 플랫 키를 Tailwind 중첩
 * 구조로 변환. 같은 경로에 값과 하위 키가 공존하면(DEFAULT) 처리한다.
 * → 클래스: bg-grey-500, text-text-secondary, border-border-primary 등
 */
const setNested = (target: NestedColors, path: string[], value: string) => {
  const [head, ...rest] = path;
  if (head === undefined) return;

  if (rest.length === 0) {
    const existing = target[head];
    if (existing && typeof existing === "object") {
      existing.DEFAULT = value;
    } else {
      target[head] = value;
    }
    return;
  }

  const existing = target[head];
  if (typeof existing === "string") {
    target[head] = { DEFAULT: existing };
  } else if (!existing) {
    target[head] = {};
  }
  setNested(target[head] as NestedColors, rest, value);
};

const buildColors = (): NestedColors => {
  const result: NestedColors = {};

  for (const [key, value] of Object.entries(colorSchema)) {
    setNested(result, key.split("."), value);
  }

  // semantic token 값 형태: { default: string } (라이트 모드 전용)
  for (const [key, value] of Object.entries(semanticColors)) {
    const resolved =
      typeof value === "string"
        ? value
        : (value as { default: string }).default;
    if (typeof resolved === "string") {
      setNested(result, key.split("."), resolved);
    }
  }

  return result;
};

export const tokenColors = buildColors();

const toTokenVariableName = (key: string) =>
  `--marcspon-token-${key.replace(/\./g, "-")}`;

type SemanticColorKey = keyof typeof semanticColors;

const resolveSemanticColor = (key: SemanticColorKey): string => {
  const token = semanticColors[key];
  const resolved =
    typeof token === "string" ? token : (token as { default: string }).default;

  return resolved;
};

/**
 * 점진 마이그레이션 중 inline style이 필요한 호환 컴포넌트에서도 Chakra와
 * 동일한 원본 스냅샷 값을 사용하도록 foundation/semantic 토큰을 CSS 변수로
 * 노출한다. 값은 새로 추정하지 않고 theme-tokens.ts의 복사본만 사용한다.
 *
 * 예: `text.primary` → `var(--marcspon-token-text-primary)`
 *     `grey.300`    → `var(--marcspon-token-grey-300)`
 */
export const tokenCssVariables: Record<string, string> = {
  ...Object.fromEntries(
    Object.entries(colorSchema).map(([key, value]) => [
      toTokenVariableName(key),
      value,
    ]),
  ),
  ...Object.fromEntries(
    Object.entries(semanticColors).map(([key, value]) => [
      toTokenVariableName(key),
      typeof value === "string"
        ? value
        : (value as { default: string }).default,
    ]),
  ),
};

/**
 * shadcn의 역할 기반 변수 → Tailwind 전용 semantic token 스냅샷 매핑.
 *
 * 앱 CSS에 색상 값을 중복 선언하지 않는다. Chakra 원본 변경을 Tailwind에도
 * 반영할 때는 theme-tokens.ts의 복사본을 명시적으로 동기화한다.
 */
const shadcnSemanticTokenMap = {
  "--background": "background.primary",
  "--foreground": "text.primary",
  "--card": "background.primary",
  "--card-foreground": "text.primary",
  "--popover": "background.primary",
  "--popover-foreground": "text.primary",
  "--primary": "button.black",
  "--primary-foreground": "text.primary.inverse",
  "--secondary": "background.secondary",
  "--secondary-foreground": "text.primary",
  "--muted": "background.secondary",
  "--muted-foreground": "text.tertiary",
  "--accent": "background.secondary",
  "--accent-foreground": "text.primary",
  "--destructive": "support.error",
  "--destructive-foreground": "text.primary.inverse",
  "--border": "border.tertiary",
  "--input": "border.tertiary",
  "--ring": "border.primary",
  "--skeleton-start": "background.secondary",
  "--skeleton-end": "background.tertiary",
} as const satisfies Record<string, SemanticColorKey>;

export const tokenRadii = tailwindRadii;

export const shadcnCssVariables: Record<string, string> = {
  ...Object.fromEntries(
    Object.entries(shadcnSemanticTokenMap).map(([variable, token]) => [
      variable,
      resolveSemanticColor(token),
    ]),
  ),
  // Input/Button의 Chakra 기본 radius(8px)를 shadcn 기준 radius로 사용한다.
  "--radius": tokenRadii.component,
};

/** 복사한 breakpoints → Tailwind screens (`base`는 media query가 아니므로 제외). */
export const tokenScreens = Object.fromEntries(
  Object.entries(tailwindBreakpoints).filter(([key]) => key !== "base"),
) as Record<string, string>;

/** 복사한 container sizes → `max-w-container-{size}`. */
export const tokenContainerMaxWidths = Object.fromEntries(
  Object.entries(tailwindContainerSizes).map(([key, value]) => [
    `container-${key}`,
    value,
  ]),
) as Record<string, string>;

/** 복사한 fontWeights → Tailwind `font-{name}`. */
export const tokenFontWeights = Object.fromEntries(
  Object.entries(tailwindFontWeights).map(([key, value]) => [
    key,
    String(value),
  ]),
) as Record<string, string>;

/** 복사한 next/font 변수 → Tailwind font family 별칭. */
export const tokenFontFamilies = {
  body: [tailwindFontFamilies.body, "sans-serif"],
  heading: [tailwindFontFamilies.heading, "sans-serif"],
  pretendard: [tailwindFontFamilies.pretendard, "sans-serif"],
  nanum: [tailwindFontFamilies.nanum, "sans-serif"],
} as Record<string, string[]>;

/**
 * 복사한 zIndices → Tailwind zIndex. 중첩 그룹(layout.*)은 하이픈으로 평탄화.
 * → 클래스: z-modal, z-layout-leftMenu 등
 */
const buildZIndex = (): Record<string, string> => {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(tailwindZIndices)) {
    if (typeof value === "object") {
      for (const [subKey, subValue] of Object.entries(value)) {
        result[`${key}-${subKey}`] = String(subValue);
      }
    } else {
      result[key] = String(value);
    }
  }
  return result;
};

export const tokenZIndex = buildZIndex();

const textStyleFontFamilies: Record<string, string> = {
  "Pretendard JP Variable": tailwindFontFamilies.pretendard,
  "NanumSquare Neo variable": tailwindFontFamilies.nanum,
};

interface TailwindTextStyle {
  fontFamily?: string;
  fontWeight?: number | string;
  fontSize?: string | { base?: string; sm?: string; md?: string };
  lineHeight?: number | string;
  letterSpacing?: string;
  textDecoration?: string;
}

/**
 * 복사한 textStyles → `.text-style-{name}` 컴포넌트 클래스.
 *
 * 반응형 fontSize는 프로젝트 브레이크포인트(base=0, sm=1025px)만 반영한다.
 * 토큰의 `md` 값은 Chakra 쪽에서도 커스텀 breakpoints(base/sm만 정의)에
 * 의해 사용되지 않으므로 의도적으로 무시한다.
 */
type CSSRuleObject = {
  [key: string]: string | CSSRuleObject;
};

export const buildTextStyleComponents = (): CSSRuleObject => {
  const components: CSSRuleObject = {};

  for (const [name, style] of Object.entries(
    textStyles as Record<string, TailwindTextStyle>,
  )) {
    const base: CSSRuleObject = {};

    // 복사된 theme font 이름 → next/font 변수 해석
    // (예: "Pretendard JP Variable" → var(--font-pretendard))
    if (style.fontFamily) {
      base.fontFamily =
        textStyleFontFamilies[style.fontFamily] ?? style.fontFamily;
    }
    if (style.fontWeight) base.fontWeight = String(style.fontWeight);
    if (style.lineHeight) base.lineHeight = String(style.lineHeight);
    if (style.letterSpacing) base.letterSpacing = style.letterSpacing;
    if (style.textDecoration) base.textDecoration = style.textDecoration;

    if (typeof style.fontSize === "string") {
      base.fontSize = style.fontSize;
    } else if (style.fontSize) {
      if (style.fontSize.base) base.fontSize = style.fontSize.base;
      if (style.fontSize.sm && style.fontSize.sm !== style.fontSize.base) {
        base["@media (min-width: 1025px)"] = { fontSize: style.fontSize.sm };
      }
    }

    components[`.text-style-${name}`] = base;
  }

  return components;
};
