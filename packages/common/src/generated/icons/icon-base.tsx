import { colorSchema, colors } from "../tokens/colors";
import type {
  CSSProperties,
  MouseEventHandler,
  ReactNode,
  SVGProps,
} from "react";

type SizeValue = unknown;

/**
 * 생성 아이콘이 Chakra 런타임 없이도 기존 호출부의 크기·간격 props를
 * 받아들일 수 있게 하는 얇은 SVG 호환 타입이다.
 */
interface IconRuntimeProps extends Omit<
  SVGProps<SVGSVGElement>,
  "color" | "height" | "width"
> {
  [key: string]: unknown;
  boxSize?: SizeValue;
  color?: unknown;
  h?: SizeValue;
  height?: SizeValue;
  sx?: unknown;
  w?: SizeValue;
  width?: SizeValue;
}

/**
 * 생성 아이콘의 공개 props는 프레임워크 중립적인 object로 둔다.
 * 기존 Chakra 화면의 ResponsiveValue props와 Tailwind 화면의 SVG props를
 * 마이그레이션 기간 동안 모두 받을 수 있게 하기 위한 호환 경계다.
 */
export interface IconProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- Chakra와 SVG 양쪽 호출부를 잇는 임시 마이그레이션 경계
  [key: string]: any;
  children?: ReactNode;
  onClick?: MouseEventHandler<SVGSVGElement>;
}

const getBaseValue = (value: SizeValue) => {
  if (Array.isArray(value)) {
    return value.find((item) => item !== null && item !== undefined);
  }
  if (value && typeof value === "object") {
    const responsiveValue = value as Partial<
      Record<"base" | "sm" | "md" | "lg" | "xl" | "2xl", unknown>
    >;
    return (
      responsiveValue.base ??
      responsiveValue.sm ??
      responsiveValue.md ??
      responsiveValue.lg ??
      responsiveValue.xl ??
      responsiveValue["2xl"]
    );
  }
  return value;
};

const toCssSize = (value: SizeValue, spacing = false) => {
  const resolved = getBaseValue(value);
  if (typeof resolved === "number") {
    return spacing ? `${resolved * 4}px` : `${resolved}px`;
  }
  return typeof resolved === "string" ? resolved : undefined;
};

const resolveColor = (value: unknown) => {
  const resolvedValue = getBaseValue(value);
  if (typeof resolvedValue !== "string") return undefined;
  const semantic = (colors as Record<string, string | { default: string }>)[
    resolvedValue
  ];
  if (typeof semantic === "string") return semantic;
  if (semantic?.default) return semantic.default;
  return (
    (colorSchema as Record<string, string>)[resolvedValue] ?? resolvedValue
  );
};

const sanitizeStyle = (style: unknown) => {
  if (!style || typeof style !== "object") return undefined;
  return Object.fromEntries(
    Object.entries(style)
      .filter(([, value]) => ["string", "number"].includes(typeof value))
      .map(([key, value]) => [
        key,
        typeof value === "string"
          ? value.replace(/\s*!important\s*$/, "")
          : value,
      ]),
  ) as CSSProperties;
};

const hasUtility = (
  className: string | undefined,
  matcher: (utility: string) => boolean,
) =>
  className
    ?.split(/\s+/)
    .map((token) => token.split(":").at(-1)?.replace(/^!/, "") ?? "")
    .some(matcher) ?? false;

/** Chakra `Icon`을 대체하는 순수 SVG primitive. */
export const Icon = (props: IconProps) => {
  const {
    boxSize,
    w,
    h,
    width,
    height,
    minW,
    minH,
    maxW,
    maxH,
    color,
    fontSize,
    display,
    position,
    pos,
    top,
    right,
    bottom,
    left,
    transform,
    transition,
    rotate,
    cursor,
    p,
    padding,
    px,
    py,
    pt,
    pr,
    pb,
    pl,
    m,
    margin,
    mx,
    my,
    mt,
    mr,
    mb,
    ml,
    borderRadius,
    rounded,
    opacity,
    flex,
    flexShrink,
    flexGrow,
    verticalAlign,
    zIndex,
    pointerEvents,
    bg,
    bgColor,
    background,
    backgroundColor,
    border,
    borderColor,
    borderStyle,
    borderWidth,
    boxSizing,
    lineHeight,
    overflow,
    textAlign,
    as: _as,
    _hover,
    _active,
    _focus,
    _focusVisible,
    sx,
    style,
    className,
    children,
    ...svgProps
  } = props as IconRuntimeProps;
  void _as;
  void _hover;
  void _active;
  void _focus;
  void _focusVisible;
  const hasDisplayUtility = hasUtility(className, (utility) =>
    [
      "block",
      "contents",
      "flex",
      "flow-root",
      "grid",
      "hidden",
      "inline",
      "inline-block",
      "inline-flex",
      "inline-grid",
      "list-item",
      "table",
    ].includes(utility),
  );
  const hasShrinkUtility = hasUtility(className, (utility) =>
    utility.startsWith("shrink"),
  );
  const hasLeadingUtility = hasUtility(className, (utility) =>
    utility.startsWith("leading-"),
  );
  const hasAlignUtility = hasUtility(className, (utility) =>
    utility.startsWith("align-"),
  );
  // Chakra의 숫자형 size/position props는 spacing scale(1 = 4px)을 사용한다.
  // 명시적인 px/rem 문자열과 Tailwind className은 그대로 우선한다.
  const resolvedBoxSize = toCssSize(boxSize, true);
  const resolvedWidth =
    toCssSize(width, true) ?? toCssSize(w, true) ?? resolvedBoxSize ?? "1em";
  const resolvedHeight =
    toCssSize(height, true) ?? toCssSize(h, true) ?? resolvedBoxSize ?? "1em";
  const resolvedTransform =
    rotate && transform === "auto" ? `rotate(${String(rotate)})` : transform;

  const computedStyle: CSSProperties = {
    display:
      (display as CSSProperties["display"]) ??
      (hasDisplayUtility ? undefined : "inline-block"),
    minWidth: toCssSize(minW as SizeValue, true),
    minHeight: toCssSize(minH as SizeValue, true),
    maxWidth: toCssSize(maxW as SizeValue, true),
    maxHeight: toCssSize(maxH as SizeValue, true),
    color: resolveColor(color),
    fontSize: toCssSize(fontSize as SizeValue),
    position: (position ?? pos) as CSSProperties["position"],
    top: toCssSize(top as SizeValue, true),
    right: toCssSize(right as SizeValue, true),
    bottom: toCssSize(bottom as SizeValue, true),
    left: toCssSize(left as SizeValue, true),
    transform: resolvedTransform as CSSProperties["transform"],
    transition: transition as CSSProperties["transition"],
    cursor: cursor as CSSProperties["cursor"],
    padding: toCssSize((padding ?? p) as SizeValue, true),
    paddingInline: toCssSize(px as SizeValue, true),
    paddingBlock: toCssSize(py as SizeValue, true),
    paddingTop: toCssSize(pt as SizeValue, true),
    paddingRight: toCssSize(pr as SizeValue, true),
    paddingBottom: toCssSize(pb as SizeValue, true),
    paddingLeft: toCssSize(pl as SizeValue, true),
    margin: toCssSize((margin ?? m) as SizeValue, true),
    marginInline: toCssSize(mx as SizeValue, true),
    marginBlock: toCssSize(my as SizeValue, true),
    marginTop: toCssSize(mt as SizeValue, true),
    marginRight: toCssSize(mr as SizeValue, true),
    marginBottom: toCssSize(mb as SizeValue, true),
    marginLeft: toCssSize(ml as SizeValue, true),
    borderRadius: toCssSize((borderRadius ?? rounded) as SizeValue),
    opacity: opacity as CSSProperties["opacity"],
    flex: flex as CSSProperties["flex"],
    flexShrink:
      (flexShrink as CSSProperties["flexShrink"]) ??
      (hasShrinkUtility ? undefined : 0),
    flexGrow: flexGrow as CSSProperties["flexGrow"],
    verticalAlign:
      (verticalAlign as CSSProperties["verticalAlign"]) ??
      (hasAlignUtility ? undefined : "middle"),
    zIndex: zIndex as CSSProperties["zIndex"],
    pointerEvents: pointerEvents as CSSProperties["pointerEvents"],
    background: resolveColor(background ?? backgroundColor ?? bgColor ?? bg),
    border: border as CSSProperties["border"],
    borderColor: resolveColor(borderColor),
    borderStyle: borderStyle as CSSProperties["borderStyle"],
    borderWidth: toCssSize(borderWidth),
    boxSizing: boxSizing as CSSProperties["boxSizing"],
    lineHeight:
      (getBaseValue(lineHeight) as CSSProperties["lineHeight"]) ??
      (hasLeadingUtility ? undefined : "1em"),
    overflow: overflow as CSSProperties["overflow"],
    textAlign: textAlign as CSSProperties["textAlign"],
    ...sanitizeStyle(sx),
    ...style,
  };

  return (
    <svg
      className={className}
      display="inline-block"
      focusable="false"
      height={resolvedHeight}
      role={svgProps["aria-label"] ? "img" : "presentation"}
      style={computedStyle}
      width={resolvedWidth}
      {...(svgProps as SVGProps<SVGSVGElement>)}
    >
      {children}
    </svg>
  );
};
