import type { Config } from "tailwindcss";

import plugin from "tailwindcss/plugin";
import animatePlugin from "tailwindcss-animate";

import {
  buildTextStyleComponents,
  shadcnCssVariables,
  tokenCssVariables,
  tokenColors,
  tokenContainerMaxWidths,
  tokenFontFamilies,
  tokenFontWeights,
  tokenRadii,
  tokenScreens,
  tokenZIndex,
} from "./tokens";

/**
 * Chakra 공존을 위한 공유 Tailwind preset.
 *
 * - preflight OFF: Tailwind 전역 리셋이 기존 Chakra 화면(resetCSS)에 영향을
 *   주지 않도록 비활성화. 전환된 페이지는 `.twp` 래퍼로 스코프된 리셋을
 *   옵트인한다 (packages/tailwind-config/preflight-scoped.css).
 * - screens: Chakra 커스텀 브레이크포인트(sm=1025px)와 동일하게 맞춤.
 *   Tailwind 기본값(sm=640px)을 쓰면 기존 화면과 반응형이 어긋난다.
 * - 색상/텍스트 토큰은 Chakra theme에서 복사한 독립 스냅샷을 사용한다.
 *   기존 Chakra theme은 이 preset을 참조하지 않으며 그대로 유지된다.
 */
const config: Omit<Config, "content"> = {
  corePlugins: {
    preflight: false,
  },
  theme: {
    // Chakra에서 복사한 Tailwind 전용 foundation 값.
    // 기존 공용 Editor CSS가 사용하던 Tailwind `lg:`도 점진 공존 기간에는
    // 제거할 수 없으므로 Chakra의 desktop(sm=1025px)과 같은 값으로 유지한다.
    screens: {
      ...tokenScreens,
      lg: "1025px",
    },
    extend: {
      // Tailwind 전용 토큰 스냅샷에서 매핑 — theme-tokens.ts 참조
      colors: {
        ...tokenColors,
        // shadcn/ui 시맨틱 색 — 아래 plugin이 Chakra 토큰 값으로 :root에 주입
        // background/border는 프로젝트 토큰 그룹(background.*, border.*)을
        // 유지한 채 DEFAULT만 추가 → bg-background, border-border 사용 가능
        background: {
          ...(tokenColors.background as Record<string, unknown>),
          DEFAULT: "var(--background)",
        },
        border: {
          ...(tokenColors.border as Record<string, unknown>),
          DEFAULT: "var(--border)",
        },
        foreground: "var(--foreground)",
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        input: "var(--input)",
        ring: "var(--ring)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        control: tokenRadii.control,
        component: tokenRadii.component,
        dialog: tokenRadii.dialog,
        full: tokenRadii.full,
      },
      zIndex: tokenZIndex,
      maxWidth: tokenContainerMaxWidths,
      fontFamily: tokenFontFamilies,
      fontWeight: tokenFontWeights,
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        // 체크박스 체크 표시가 선 시작점부터 그려지는 애니메이션
        // (dashoffset은 사용하는 path 길이 이상의 값과 맞출 것)
        "check-draw": {
          from: { "stroke-dashoffset": "24" },
          to: { "stroke-dashoffset": "0" },
        },
        "skeleton-bg-fade": {
          from: {
            backgroundColor: "var(--skeleton-start)",
            borderColor: "var(--skeleton-start)",
          },
          to: {
            backgroundColor: "var(--skeleton-end)",
            borderColor: "var(--skeleton-end)",
          },
        },
        "loading-dots": {
          "0%": { content: '"."' },
          "33%": { content: '".."' },
          "66%, 100%": { content: '"..."' },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "check-draw": "check-draw 0.2s ease-out forwards",
        "skeleton-bg-fade": "skeleton-bg-fade 0.8s linear infinite alternate",
        "loading-dots": "loading-dots 1.5s steps(3, end) infinite",
      },
    },
  },
  plugins: [
    animatePlugin,
    plugin(({ addBase, addComponents }) => {
      // 복사한 semantic token → shadcn 역할 기반 CSS 변수.
      addBase({
        ":root": {
          ...tokenCssVariables,
          ...shadcnCssVariables,
        },
      });

      // 복사한 textStyles → .text-style-{name} 컴포넌트 클래스
      addComponents(buildTextStyleComponents());
    }),
  ],
};

export default config;
