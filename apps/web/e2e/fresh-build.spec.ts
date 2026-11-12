// 브라우저 테스트가 보는 것은 「지금 코드」의 빌드다.
// 전에는 `pnpm --filter @esg/web test:browser` 만 돌리면 앞서 만들어 둔 dist 를 그대로 띄웠다. 코드를 고치고 빌드를 잊으면
// 고치기 전의 화면을 시험하고 초록이 됐다. 지금은 Playwright 가 미리보기 서버를 띄우기 전에 빌드한다(playwright.config.ts).
// 여기서는 dist 가 이번 실행에서 만들어졌는지를 본다: 실행이 시작된 때(설정 파일이 적어 둔다)보다 뒤에 쓰였는가.
import { expect, test } from '@playwright/test';

import { readFileSync, statSync } from 'node:fs';

test('띄운 빌드(dist)는 이번 테스트 실행이 시작된 뒤에 만들어졌다', () => {
  const started = Number(process.env.WEB_TEST_STARTED);
  expect(started).toBeGreaterThan(0);
  const built = statSync(
    new URL('../dist/index.html', import.meta.url),
  ).mtimeMs;
  expect(
    built,
    'dist/index.html 이 이번 실행보다 먼저 만들어진 것이다(낡은 빌드를 시험하고 있다)',
  ).toBeGreaterThanOrEqual(started);
});

// 위의 것은 dist 가 새것인지만 본다. 서버가 그 dist 를 띄웠는지는 따로 본다: 빌드는 새로 했는데 미리보기 서버가 다른 폴더
// (앞서 만들어 둔 다른 빌드)를 내주면, 위는 초록인 채로 낡은 화면을 시험하게 된다.
test('미리보기 서버가 내주는 첫 화면은 그 빌드(dist/index.html) 그대로다', async ({
  request,
}) => {
  const served = await request.get('./');
  expect(served.ok()).toBe(true);
  // index.html 은 빌드마다 내용에서 뽑은 이름의 스크립트·CSS 를 가리킨다. 다른 빌드를 띄웠으면 여기서 갈린다.
  expect(await served.text()).toBe(
    readFileSync(new URL('../dist/index.html', import.meta.url), 'utf8'),
  );
});
