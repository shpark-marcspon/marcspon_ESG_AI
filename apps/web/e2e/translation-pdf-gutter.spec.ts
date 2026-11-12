// 밴드 TRW13 A(컨설턴트 댓글 — TR-P04 확인할 곳을 누르면 PDF 가 흔들림, 가로 쪽 문서에서만): 공간을 차지하는 스크롤바 아래에서
// 스크롤바 생김 → 칸 폭 −15 → 배율 줄어 캔버스 새로 → 쪽(또는 문서)이 낮아져 스크롤바 사라짐 → 폭 +15 → … 의 순환.
// 두 갈래 — ① 쪽 칸(pdf-page-scroll) 자체 스크롤바 ② 창 스크롤바(문서 높이 ≈ 창 높이). ①은 쪽 칸 scrollbar-gutter: stable,
// ②는 useWidth 의 히스테리시스(줄어듦은 바로, 늘어남은 20px 넘을 때만 — PdfView.tsx settleWidth)로 끊는다.
// 맥의 겹침 스크롤바·머리 없는 Chromium 기본(--hide-scrollbars)·jsdom 에서는 안 나서, 이 파일만 그 인자를 빼고 15px 스크롤바를 그린다.
// 창 크기는 이 기계에서 잰 순환 자리(고치기 전 300ms 동안 캔버스 새로 18~19번) 둘레를 3px 씩 훑는다 — 레이아웃이 조금 바뀌어도 걸리게.
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { writePdf } from '../tools/pdf-writer.ts';
import { signIn } from './session.ts';
import {
  PDF_DOC_ID,
  PDF_RUN_ID,
  fakeTranslationPdfApi,
  pdfLayout,
} from './translation-pdf-server.ts';

test.use({ launchOptions: { ignoreDefaultArgs: ['--hide-scrollbars'] } });

const WIDE = { width: 1440, height: 810 };
const PDF = Buffer.from(
  writePdf([
    {
      ...WIDE,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: 'Made-up wide page' }],
      tables: [],
    },
  ]),
);

/** pdfLayout 그대로에 쪽 크기만 가로(1440×810). 상자 좌표는 그 쪽 안. */
function wideLayout() {
  const layout = pdfLayout();
  layout.pages = [{ page: 1, ...WIDE, textLayer: 'present' }];
  return layout;
}

async function openWide(page: Page) {
  await fakeTranslationPdfApi(page, {
    done: { pdf: PDF, layout: wideLayout(), result: true },
  });
  await signIn(page);
  await page.goto(
    `/translation/documents/${PDF_DOC_ID}/batches/b-1/pdf/${PDF_RUN_ID}`,
  );
  await page.addStyleTag({
    content:
      '::-webkit-scrollbar { width: 15px; height: 15px } ::-webkit-scrollbar-thumb { background: #888 }',
  });
  await expect(
    page.locator('[data-testid="pdf-page"] canvas[data-render-state="done"]'),
  ).toBeVisible();
  await page.locator('[data-box="p1-b2"]').click();
  // ① 의 방어(쪽 칸 스크롤바 자리를 늘 비움). 이 꼴에서는 ②의 히스테리시스만으로도 순환이 멈춰(심은 파손 표) 따로 본다.
  await expect(page.getByTestId('pdf-page-scroll')).toHaveCSS(
    'scrollbar-gutter',
    'stable',
  );
}

/** ms 동안 쪽 칸 안에 캔버스가 새로 붙은 횟수와 쪽 칸 clientWidth 의 서로 다른 값(프레임마다 읽음). */
function watch(page: Page, ms: number) {
  return page.evaluate(async (wait) => {
    const scroller = document.querySelector<HTMLElement>(
      '[data-testid="pdf-page-scroll"]',
    )!;
    let canvases = 0;
    const widths = new Set<number>();
    const mutation = new MutationObserver((records) => {
      for (const record of records)
        record.addedNodes.forEach((node) => {
          if (
            node instanceof HTMLElement &&
            (node.tagName === 'CANVAS' || node.querySelector('canvas') !== null)
          )
            canvases += 1;
        });
    });
    mutation.observe(scroller, { childList: true, subtree: true });
    const start = performance.now();
    while (performance.now() - start < wait) {
      widths.add(scroller.clientWidth);
      await new Promise((resolve) => requestAnimationFrame(resolve));
    }
    mutation.disconnect();
    return { canvases, widths: [...widths] };
  }, ms);
}

const canvasWidth = (page: Page) =>
  page
    .locator('[data-testid="pdf-page"] canvas')
    .evaluate((canvas) => canvas.getBoundingClientRect().width);

// 이 기계에서 잰 순환 자리: 1440×483~486(① 쪽 칸 562↔577) · 1440×669~672(② 창) · 1920×756~762(①) · 1920×942~948(②).
const AROUND: ReadonlyArray<readonly [number, number, number]> = [
  [1440, 474, 498],
  [1440, 660, 681],
  [1920, 750, 768],
  [1920, 936, 954],
];

for (const [width, from, to] of AROUND)
  test(`TRW13 A ${width}×${from}~${to}: 공간 차지 스크롤바 · 가로 쪽 상자 누름 → 창 높이마다 캔버스 새로 ≤ 1 · 칸 폭 한 값`, async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width, height: from });
    await openWide(page);
    const shaky: string[] = [];
    for (let height = from; height <= to; height += 3) {
      await page.setViewportSize({ width, height });
      // 창을 바꾼 직후 한 번 다시 그리는 것은 정상 — 가라앉은 뒤 1초를 본다(순환이면 계속 새로 그린다).
      await page.waitForTimeout(150);
      const seen = await watch(page, 1000);
      if (seen.canvases > 1 || seen.widths.length > 1)
        shaky.push(`${width}×${height} ${JSON.stringify(seen)}`);
    }
    expect(shaky).toEqual([]);
  });

// 감독 0f 11-10: 히스테리시스가 넓힘을 막지 않는가 — 창을 20px 넘게 넓히면 쪽 그림도 따라 커진다.
test('TRW13 A: 창을 크게 넓히면(칸 폭 +20px 넘음) 배율이 따라 커짐 · 좁히면 바로 줄어듦', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1400, height: 900 });
  await openWide(page);
  const before = await canvasWidth(page);
  await page.setViewportSize({ width: 1480, height: 900 });
  await expect.poll(() => canvasWidth(page)).toBeGreaterThan(before + 20);
  await page.setViewportSize({ width: 1300, height: 900 });
  await expect.poll(() => canvasWidth(page)).toBeLessThan(before);
});
