import { defineConfig } from '@playwright/test';

import { fileURLToPath } from 'node:url';

// 떠 있는 api-py 에 실제로 닿는 확인. 평소의 `pnpm test:browser` 는 이 폴더를 줍지 않는다(파일 이름이 .spec.ts 가 아니다).
// 돌리는 법: api-py 를 띄우고 테넌트와 토큰을 준비한 뒤(apps/web/scripts/section4-F9.sh --containers 가 한다)
//   F9_TOKEN=… F9_TENANT=… API_PY_ORIGIN=… WEB_TEST_PORT=… pnpm exec playwright test -c e2e/live/playwright.config.ts
// 진짜 Vite 프록시(vite preview)를 거친다. 빌드는 여기서 한다.
const port = Number(process.env.WEB_TEST_PORT ?? 15174);
const webRoot = fileURLToPath(new URL('../..', import.meta.url));

export default defineConfig({
  testDir: '.',
  testMatch: '*.pw.ts',
  // 산출물은 .gitignore 가 가리는 자리에만 둔다. 실패 때의 자취·영상·화면 갈무리는 남기지 않는다(입력칸의 값이 들 수 있다).
  outputDir: '../../test-results/live',
  use: {
    baseURL: `http://127.0.0.1:${port}/`,
    viewport: { width: 1400, height: 900 },
    trace: 'off',
    video: 'off',
    screenshot: 'off',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  webServer: {
    command: `pnpm build && pnpm exec vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    cwd: webRoot,
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: false,
    env: {
      VIEWER_DATA_DIR: 'e2e/.no-local-data',
      API_PY_ORIGIN: process.env.API_PY_ORIGIN ?? 'http://127.0.0.1:18081',
    },
  },
});
