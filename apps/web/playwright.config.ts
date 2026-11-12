import { defineConfig } from '@playwright/test';

import { baselineDir, guardBaselineUpdate } from './e2e/visual-baseline.ts';

// 실제 브라우저(머리 없는 Chromium)로 빌드 결과를 연다. 빌드는 여기서 한다(아래 webServer.command): 미리보기 서버를 띄우기 전에 늘 지금 코드를 빌드한다.
// 그래서 `pnpm test:browser` 만 돌려도, `pnpm exec playwright test e2e/<파일>` 로 하나만 돌려도 낡은 dist 를 시험하지 않는다.
// 값: 실행마다 빌드 한 번(이 기계에서 1초 안쪽). verify.sh 는 빌드 단계가 따로 있어 두 번 빌드한다.
// 포트가 겹치면 WEB_TEST_PORT 로 바꾼다.
const port = Number(process.env.WEB_TEST_PORT ?? 15174);

// 이번 실행이 시작된 때. e2e/fresh-build.spec.ts 가 「띄운 빌드가 이번 실행에서 만들어졌는가」를 볼 때 쓴다.
// 이 파일은 테스트를 돌리는 일꾼 프로세스에서도 다시 읽힌다. 그때는 물려받은 값을 그대로 둔다(??=).
process.env.WEB_TEST_STARTED ??= String(Date.now());

// 시각 비교(밴드 VS1 — 결정 sid:MARC-ENT-326): 기준 그림은 git 밖 한 자리(e2e/visual-baseline.ts). 기준 갱신은 main 에서 apps/web/scripts/visual-update.sh 로만 —
// 밴드 워크트리에서 -u 로 돌리면 여기서 멈춘다.
guardBaselineUpdate();

export default defineConfig({
  testDir: 'e2e',
  // 없는 기준을 쓰지 않는다(기본 'missing' 은 밴드 워크트리가 공용 폴더에 기준을 만들어 버린다). 갱신은 visual-update.sh 의 --update-snapshots.
  updateSnapshots: 'none',
  // toHaveScreenshot 만의 틀(다른 스펙의 toMatchSnapshot 에 번지지 않는다). 이름은 시각 스펙이 「<화면>-<상태>-<폭>.png」로 준다.
  // maxDiffPixels: 같은 맥·고정 Chromium 에서 잰 잡음 0(밴드 VS1 보고) — 화살표 2px 밀림도 잡는다. 비율(maxDiffPixelRatio)은 화면 크기에 비례해 놓친다.
  expect: {
    toHaveScreenshot: {
      pathTemplate: `${baselineDir()}/{testFileName}/{arg}{ext}`,
      maxDiffPixels: 0,
      threshold: 0.2,
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    },
  },
  // 캔버스의 픽셀을 읽는 테스트라 화면 조건을 못박는다.
  use: {
    baseURL: `http://127.0.0.1:${port}/`,
    viewport: { width: 1400, height: 900 },
    deviceScaleFactor: 1,
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  webServer: {
    // 빌드가 실패하면 서버가 뜨지 않고 테스트 실행이 멈춘다(낡은 dist 로 넘어가지 않는다).
    command: `pnpm build && pnpm exec vite preview --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}/`,
    reuseExistingServer: false,
    // 실제 자료 폴더가 있어도 테스트는 예시 자료만 본다.
    // VITE_DEMOS=1: 데모 넷(/dev/viewer·table·api·parts)을 여는 빌드다. 프로덕션 빌드에는 데모가 없다(src/app/router.tsx, 밴드 WC1 ②·RT1).
    env: { VIEWER_DATA_DIR: 'e2e/.no-local-data', VITE_DEMOS: '1' },
  },
});
