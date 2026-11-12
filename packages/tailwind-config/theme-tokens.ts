/**
 * Tailwind/shadcn 전용 테마 토큰 스냅샷.
 *
 * 2026-08-04 기준 Chakra theme 값을 복사한 파일이다.
 * 기존 Chakra theme과 ChakraProvider는 삭제하거나 이 파일을 참조하지 않는다.
 * 순차 마이그레이션 중 두 시스템은 독립적으로 공존하며, Chakra 토큰 변경 시
 * 필요한 값만 이 파일에 명시적으로 동기화한다.
 *
 * 원본 참고:
 * - packages/common/public/token.json
 * - packages/common/src/generated/tokens/{colors,text-styles}.ts
 * - packages/common/src/configs/theme/foundations/*
 */

export const colorSchema = {
  "common-white": "#ffffff",
  "grey.50": "#fafbfb",
  "grey.100": "#f3f4f5",
  "grey.200": "#e7e9ec",
  "grey.300": "#d1d5d9",
  "grey.400": "#b0b7bf",
  "grey.500": "#8b95a1",
  "grey.600": "#6f7781",
  "grey.700": "#545a61",
  "grey.800": "#383c40",
  "grey.900": "#1c1e21",
  "green.50": "#f4fcf9",
  "green.100": "#e2f8f0",
  "green.200": "#c4f1e2",
  "green.300": "#8ce3c5",
  "green.400": "#45cf9d",
  "green.500": "#1eb96e",
  "green.600": "#187f49",
  "green.700": "#124a37",
  "green.800": "#0c3124",
  "green.900": "#061912",
  "yellow.50": "#fffbf4",
  "yellow.100": "#fff5e3",
  "yellow.200": "#ffeac7",
  "yellow.300": "#ffd690",
  "yellow.400": "#ffba48",
  "yellow.500": "#ff9a23",
  "yellow.600": "#b7661b",
  "yellow.700": "#714215",
  "yellow.800": "#3d2c0e",
  "yellow.900": "#1f1607",
  "blue.50": "#f2f8ff",
  "blue.100": "#e0eeff",
  "blue.200": "#c1dfff",
  "blue.300": "#85beff",
  "blue.400": "#4091ff",
  "blue.500": "#175eff",
  "blue.600": "#1243b7",
  "blue.700": "#0e3371",
  "blue.800": "#09213d",
  "blue.900": "#05111f",
  "red.50": "#fef5f5",
  "red.100": "#fce4e6",
  "red.200": "#fbc8ce",
  "red.300": "#f7949d",
  "red.400": "#f14b58",
  "red.500": "#ea2831",
  "red.600": "#a72027",
  "red.700": "#65181d",
  "red.800": "#390f13",
  "red.900": "#1d080a",
  "pink.50": "#fff5f8",
  "pink.100": "#fee4eb",
  "pink.200": "#fccad9",
  "pink.300": "#f996b3",
  "pink.400": "#f74c7f",
  "pink.500": "#f22949",
  "pink.600": "#ae203a",
  "pink.700": "#6a182c",
  "pink.800": "#3a101d",
  "pink.900": "#1e080f",
  "teal.50": "#f2fbfc",
  "teal.100": "#ddf5f7",
  "teal.200": "#bcebee",
  "teal.300": "#7cd9dd",
  "teal.400": "#39bec7",
  "teal.500": "#0ea0ac",
  "teal.600": "#0b6c75",
  "teal.700": "#084346",
  "teal.800": "#052d2e",
  "teal.900": "#021718",
  "orange.50": "#fef9f7",
  "orange.100": "#feeee9",
  "orange.200": "#fcded4",
  "orange.300": "#fabdaa",
  "orange.400": "#f68f6e",
  "orange.500": "#f25c2c",
  "orange.600": "#c24922",
  "orange.700": "#92371a",
  "orange.800": "#612411",
  "orange.900": "#311309",
  "white-transparent.50": "#ffffff0D",
  "white-transparent.100": "#ffffff1A",
  "white-transparent.200": "#ffffff33",
  "white-transparent.300": "#ffffff4D",
  "white-transparent.400": "#ffffff66",
  "white-transparent.500": "#ffffff80",
  "white-transparent.600": "#ffffff99",
  "white-transparent.700": "#ffffffB2",
  "white-transparent.800": "#ffffffCC",
  "white-transparent.900": "#ffffffE5",
  "black-transparent.50": "#383c4005",
  "black-transparent.100": "#1c1e210D",
  "black-transparent.200": "#1c1e211A",
  "black-transparent.300": "#1c1e2133",
  "black-transparent.400": "#1c1e2157",
  "black-transparent.500": "#1c1e2180",
  "black-transparent.600": "#1c1e2199",
  "black-transparent.700": "#1c1e21B2",
  "black-transparent.800": "#1c1e21CC",
  "black-transparent.900": "#1c1e21E5",
  "grey-transparent.50": "#8b95a105",
  "grey-transparent.100": "#8b95a10D",
  "grey-transparent.200": "#8b95a11A",
  "grey-transparent.300": "#8b95a133",
  "grey-transparent.400": "#8b95a157",
  "grey-transparent.500": "#8b95a180",
  "grey-transparent.600": "#8b95a199",
  "grey-transparent.700": "#8b95a1B2",
  "grey-transparent.800": "#8b95a1CC",
  "grey-transparent.900": "#8b95a1E5",
};

export const semanticColors = {
  "button.white.active": {
    default: colorSchema["grey.100"],
  },
  "button.grey.hover": {
    default: colorSchema["grey-transparent.300"],
  },
  "support.warning.subtle": {
    default: colorSchema["yellow.200"],
  },
  "text.primary.inverse": {
    default: colorSchema["common-white"],
  },
  "text.secondary.inverse": {
    default: colorSchema["grey.400"],
  },
  "text.secondary": {
    default: colorSchema["grey.800"],
  },
  "support.success.accent": {
    default: colorSchema["green.600"],
  },
  "button.black.hover": {
    default: colorSchema["grey.900"],
  },
  "background.brand": {
    default: colorSchema["orange.100"],
  },
  "support.warning": {
    default: colorSchema["yellow.500"],
  },
  "background.overlay": {
    default: colorSchema["black-transparent.500"],
  },
  "text.tertiary.inverse": {
    default: colorSchema["grey.600"],
  },
  "background.primary.inverse": {
    default: colorSchema["grey.900"],
  },
  "support.success": {
    default: colorSchema["green.500"],
  },
  "button.disabled": {
    default: colorSchema["grey.300"],
  },
  "text.tertiary": {
    default: colorSchema["grey.600"],
  },
  "border.secondary": {
    default: colorSchema["grey.500"],
  },
  "text.disabled": {
    default: colorSchema["grey.400"],
  },
  "background.primary": {
    default: colorSchema["common-white"],
  },
  "button.grey": {
    default: colorSchema["grey-transparent.200"],
  },
  "background.brand.inverse": {
    default: colorSchema["orange.500"],
  },
  "button.black.active": {
    default: colorSchema["grey.900"],
  },
  "support.error": {
    default: colorSchema["red.500"],
  },
  "support.error.accent": {
    default: colorSchema["red.600"],
  },
  "border.primary": {
    default: colorSchema["grey.800"],
  },
  "button.white": {
    default: colorSchema["common-white"],
  },
  "button.white.hover": {
    default: colorSchema["grey.100"],
  },
  "text.primary": {
    default: colorSchema["grey.900"],
  },
  "support.success.subtle": {
    default: colorSchema["green.100"],
  },
  "button.black": {
    default: colorSchema["grey.800"],
  },
  "support.error.subtle": {
    default: colorSchema["red.100"],
  },
  "text.disabled.inverse": {
    default: colorSchema["grey.600"],
  },
  "button.grey.active": {
    default: colorSchema["grey-transparent.300"],
  },
  "support.warning.accent": {
    default: colorSchema["yellow.600"],
  },
  "text.brand": {
    default: colorSchema["orange.500"],
  },
  "background.secondary": {
    default: colorSchema["grey.100"],
  },
  "background.tertiary": {
    default: colorSchema["grey.200"],
  },
  "support.yellow": {
    default: colorSchema["yellow.500"],
  },
  "support.green": {
    default: colorSchema["green.500"],
  },
  "support.turquoise": {
    default: colorSchema["teal.500"],
  },
  "support.blue": {
    default: colorSchema["blue.500"],
  },
  "support.red": {
    default: colorSchema["red.500"],
  },
  "background.secondary.inverse": {
    default: colorSchema["grey.800"],
  },
  "border.tertiary": {
    default: colorSchema["grey.300"],
  },
  "background.quaternary": {
    default: colorSchema["grey.300"],
  },
  "support.yellow.subtle": {
    default: colorSchema["yellow.200"],
  },
  "support.green.subtle": {
    default: colorSchema["green.100"],
  },
  "support.turquoise.subtle": {
    default: colorSchema["teal.100"],
  },
  "support.blue.subtle": {
    default: colorSchema["blue.100"],
  },
  "support.red.subtle": {
    default: colorSchema["red.100"],
  },
  "background.overlay.subtle": {
    default: colorSchema["black-transparent.100"],
  },
  "border.quaternary": {
    default: colorSchema["grey.100"],
  },
  "background.overlay.inverse": {
    default: colorSchema["white-transparent.500"],
  },
  "border.brand": {
    default: colorSchema["orange.500"],
  },
  "support.pink": {
    default: colorSchema["pink.500"],
  },
  "support.pink.subtle": {
    default: colorSchema["pink.100"],
  },
  "text.quaternary": {
    default: colorSchema["grey.400"],
  },
  "support.grey.subtle": {
    default: colorSchema["grey.50"],
  },
  "support.grey": {
    default: colorSchema["grey.500"],
  },
  "support.orange": {
    default: colorSchema["orange.500"],
  },
  "support.orange.subtle": {
    default: colorSchema["orange.100"],
  },
  "button.orange": {
    default: colorSchema["orange.500"],
  },
  "button.orange.hover": {
    default: colorSchema["orange.600"],
  },
  "button.orange.active": {
    default: colorSchema["orange.600"],
  },
  "support.green.dark": {
    default: colorSchema["green.600"],
  },
  "support.turquoise.dark": {
    default: colorSchema["teal.600"],
  },
  "support.blue.dark": {
    default: colorSchema["blue.600"],
  },
  "support.red.dark": {
    default: colorSchema["red.600"],
  },
  "support.pink.dark": {
    default: colorSchema["pink.600"],
  },
  "support.grey.dark": {
    default: colorSchema["grey.600"],
  },
  "support.orange.dark": {
    default: colorSchema["orange.600"],
  },
  "support.yellow.dark": {
    default: colorSchema["yellow.600"],
  },
  "support.orange.subtle2": {
    default: colorSchema["orange.300"],
  },
  "support.grey.subtle2": {
    default: colorSchema["grey.400"],
  },
  // token.json에는 있으나 현재 gen:theme 산출물에서 누락된 항목을
  // Tailwind 복사본에서 정상화한다. Chakra generated 파일은 변경하지 않는다.
  "support.blue.subtle2": {
    default: colorSchema["blue.300"],
  },
  "support.turquoise.subtle2": {
    default: colorSchema["teal.300"],
  },
  "support.green.subtle2": {
    default: colorSchema["green.300"],
  },
  "support.purple": {
    default: "#7980ff",
  },
};

export const textStyles = {
  "nanum-display-01": {
    fontFamily: "NanumSquare Neo variable",
    textDecoration: "none",
    fontSize: {
      base: "20px",
      sm: "24px",
      md: "24px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.03em",
  },
  "pre-display-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 800,
    fontSize: {
      base: "48px",
      sm: "72px",
      md: "80px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-display-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "40px",
      sm: "56px",
      md: "64px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-display-03": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "24px",
      sm: "28px",
      md: "32px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-display-04": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "20px",
      sm: "24px",
      md: "24px",
    },
    lineHeight: 1.4,
    letterSpacing: "0em",
  },
  "pre-heading-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "18px",
      sm: "20px",
      md: "20px",
    },
    lineHeight: 1.4,
    letterSpacing: "0em",
  },
  "pre-heading-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "16px",
      sm: "18px",
      md: "18px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-body-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "16px",
      sm: "16px",
      md: "16px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-body-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "16px",
      sm: "16px",
      md: "16px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-body-03": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 400,
    fontSize: {
      base: "16px",
      sm: "16px",
      md: "16px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-body-04": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "14px",
      sm: "14px",
      md: "14px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-body-05": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "14px",
      sm: "14px",
      md: "14px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-body-06": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 400,
    fontSize: {
      base: "14px",
      sm: "14px",
      md: "14px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-caption-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: "12px",
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-caption-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "12px",
      sm: "12px",
      md: "12px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-caption-03": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 400,
    fontSize: {
      base: "12px",
      sm: "12px",
      md: "12px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-caption-04": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "10px",
      sm: "10px",
      md: "10px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-bold-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "56px",
      sm: "56px",
      md: "56px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-bold-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "50px",
      sm: "50px",
      md: "50px",
    },
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
  },
  "pre-bold-03": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "40px",
      sm: "40px",
      md: "40px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-bold-04": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "30px",
      sm: "30px",
      md: "30px",
    },
    lineHeight: 1.2,
    letterSpacing: "-0.01em",
  },
  "pre-bold-05": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "24px",
      sm: "24px",
      md: "24px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-bold-06": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "18px",
      sm: "18px",
      md: "18px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-bold-07": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 700,
    fontSize: {
      base: "14px",
      sm: "14px",
      md: "14px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-med-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "18px",
      sm: "18px",
      md: "18px",
    },
    lineHeight: 1.4,
    letterSpacing: "-0.01em",
  },
  "pre-med-02": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "16px",
      sm: "16px",
      md: "16px",
    },
    lineHeight: 1,
    letterSpacing: "-0.01em",
  },
  "pre-med-03": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "14px",
      sm: "14px",
      md: "14px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-med-04": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 500,
    fontSize: {
      base: "12px",
      sm: "12px",
      md: "12px",
    },
    lineHeight: 1.6,
    letterSpacing: "-0.01em",
  },
  "pre-light-01": {
    fontFamily: "Pretendard JP Variable",
    textDecoration: "none",
    fontWeight: 300,
    fontSize: {
      base: "20px",
      sm: "20px",
      md: "20px",
    },
    lineHeight: 1.4,
    letterSpacing: "0em",
  },
};

export const tailwindBreakpoints = {
  base: "0px",
  sm: "1025px",
} as const;

export const tailwindContainerSizes = {
  xs: "420px",
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
} as const;

export const tailwindFontFamilies = {
  body: "var(--font-pretendard)",
  heading: "var(--font-pretendard)",
  pretendard: "var(--font-pretendard)",
  nanum: "var(--font-nanum)",
} as const;

export const tailwindFontWeights = {
  thin: 100,
  extralight: 200,
  light: 300,
  regular: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  extrabold: 800,
  black: 900,
} as const;

export const tailwindZIndices = {
  hide: -1,
  auto: "auto",
  base: 0,
  docked: 10,
  dropdown: 1000,
  sticky: 1100,
  banner: 1200,
  overlay: 1300,
  modal: 1400,
  popover: 1500,
  skipLink: 1600,
  toast: 1700,
  tooltip: 1800,
  layout: {
    logo: 1500,
    leftMenu: 1000,
    topHeader: 1000,
    header: 1000,
  },
} as const;

/** Chakra 컴포넌트 테마에서 반복되는 radius를 복사한 Tailwind 별칭. */
export const tailwindRadii = {
  control: "4px",
  component: "8px",
  dialog: "16px",
  full: "9999px",
} as const;
