// 측정·캡처 스크립트가 같이 쓰는 것: 머리 없는 Chromium 을 띄우고, 떠 있는 개발 서버의 주소를 정한다.
// 서버는 따로 띄워 둔다(pnpm --filter @esg/web dev). 이 스크립트들은 서버를 띄우거나 내리지 않는다.
import { chromium } from '@playwright/test';
import type { Browser } from '@playwright/test';

export const baseUrl =
  process.env.WEB_URL ?? `http://localhost:${process.env.WEB_PORT ?? 15173}/`;

export async function withBrowser<T>(
  run: (browser: Browser) => Promise<T>,
): Promise<T> {
  const browser = await chromium.launch();
  try {
    return await run(browser);
  } finally {
    await browser.close();
  }
}

/** `--name 값` 꼴의 인자를 읽는다. */
export function arg(name: string, fallback: string): string {
  const at = process.argv.indexOf(`--${name}`);
  return at === -1 ? fallback : (process.argv[at + 1] ?? fallback);
}
