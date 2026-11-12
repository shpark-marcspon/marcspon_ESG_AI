// 큰 문서를 열 때의 첫 그리기 시간과 메모리를 잰다.
//
// 사용(개발 서버나 `pnpm preview` 가 떠 있어야 한다):
//   node tools/measure-open.ts --data local/reconcile.json --runs 5
// 재는 것(실행마다 새 브라우저 창, 화면 1900×1000, 픽셀 밀도 1):
//   첫 쪽         주소를 연 때부터 첫 문서 칸의 1쪽 캔버스가 다 그려질 때까지(ms)
//   힙(처음)      그 직후의 JS 힙(MB). 캔버스의 픽셀 메모리는 여기 들지 않는다
//   힙(끝까지)    첫 문서 칸을 끝 쪽까지 열 번에 나눠 스크롤한 뒤의 JS 힙(MB)
//   캔버스        그때 화면에 만들어져 있는 캔버스 수(문서 칸 전부 합쳐서)
import { arg, baseUrl, withBrowser } from './browser.ts';

const data = arg('data', 'sample/compare.json');
const runs = Number(arg('runs', '5'));

const results: {
  first: number;
  heapStart: number;
  heapEnd: number;
  canvases: number;
  pages: number;
}[] = [];
await withBrowser(async (browser) => {
  for (let run = 0; run < runs; run++) {
    const context = await browser.newContext({
      viewport: { width: 1900, height: 1000 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send('Performance.enable');
    const heap = async () => {
      const { metrics } = await cdp.send('Performance.getMetrics');
      return (
        (metrics.find((metric) => metric.name === 'JSHeapUsedSize')?.value ??
          0) /
        1024 /
        1024
      );
    };

    await page.goto(`${baseUrl}?data=${encodeURIComponent(data)}`);
    const pane = page.locator('.dv-pane').first();
    await pane
      .locator('.dv-page[data-page="1"] canvas[data-render-state="done"]')
      .waitFor();
    const first = await page.evaluate(() => performance.now());
    const heapStart = await heap();

    const pages = Number(
      await pane.locator('.dv-page-input').getAttribute('max'),
    );
    for (let step = 1; step <= 10; step++) {
      const target = Math.max(1, Math.round((pages * step) / 10));
      await pane.locator('.dv-page-input').fill(String(target));
      await pane
        .locator(
          `.dv-page[data-page="${target}"] canvas[data-render-state="done"]`,
        )
        .waitFor();
    }
    results.push({
      first,
      heapStart,
      heapEnd: await heap(),
      canvases: await page.locator('canvas').count(),
      pages,
    });
    await context.close();
  }
});

const median = (values: number[]) =>
  [...values].sort((x, y) => x - y)[Math.floor(values.length / 2)]!;
const line = (label: string, values: number[], digits: number) =>
  `${label}: 중앙값 ${median(values).toFixed(digits)} (최소 ${Math.min(...values).toFixed(digits)} ~ 최대 ${Math.max(...values).toFixed(digits)})`;
console.log(`자료 ${data}, 첫 문서 ${results[0]?.pages}쪽, ${runs}회`);
console.log(
  line(
    '첫 쪽(ms)',
    results.map((r) => r.first),
    0,
  ),
);
console.log(
  line(
    '힙(처음, MB)',
    results.map((r) => r.heapStart),
    1,
  ),
);
console.log(
  line(
    '힙(끝까지, MB)',
    results.map((r) => r.heapEnd),
    1,
  ),
);
console.log(
  line(
    '캔버스(개)',
    results.map((r) => r.canvases),
    0,
  ),
);
