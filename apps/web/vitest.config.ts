import { defineConfig } from "vitest/config";

export default defineConfig({
  // 키트 부품(packages/ui 의 .tsx)은 tsconfig 의 jsx: preserve 를 물려받아 JSX 가 변환되지 않은 채 들어온다.
  // 빌드는 vite.config.ts 의 react 플러그인이 변환하지만 단위 시험에는 그 플러그인이 없다. 여기서 JSX 를 automatic 으로 변환한다(밴드 FK2, 감독 판정).
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    // e2e/ 는 Playwright 가 돌린다(실제 브라우저). 여기서는 단위 테스트와 부품 테스트만.
    include: ["src/**/*.test.{ts,tsx}", "tools/**/*.test.ts"],
    // 기본은 node. 부품 테스트(.test.tsx)는 파일 머리의 `// @vitest-environment jsdom` 으로 jsdom 을 쓴다.
    environment: "node",
  },
});
