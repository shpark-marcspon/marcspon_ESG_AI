// 목록의 항목에 마우스를 올리고 뗄 때의 비용을 잰다(올리면 그 항목의 상자가 진해진다).
//
// 사용(`pnpm preview` 로 빌드한 것을 띄워 두고):
//   node tools/measure-hover.ts --data local/reconcile.json --moves 200 --runs 5
// 하는 일: 상자가 가장 많이 그려진 쪽으로 두 문서 칸을 옮긴 뒤, 화면에 보이는 항목들 위로 마우스를 차례로 옮긴다
//   (한 번 옮길 때마다 앞 항목에서 떼고 다음 항목에 올린다 = 화면 갱신 한 번). 옮길 때마다 다음 프레임까지 기다린다.
// 재는 것(화면 1900×1000, 픽셀 밀도 1):
//   옮기기 한 번의 일     브라우저가 그 한 번에 쓴 시간(ms) = 스크립트 + 스타일 + 배치. CDP 의 Performance.getMetrics 를 앞뒤로 읽어 뺀 것
//   그중 스크립트         그 가운데 JS(React 의 계산 포함)
//   다음 프레임까지       올린 때부터 다음 화면 그리기 직후까지(ms). 한 프레임(약 17ms)까지의 기다림이 섞여 있다
//   그려진 상자           그때 DOM 에 있는 상자 수(React 가 다시 계산하는 대상)
//   바뀐 상자             옮기기 한 번에 속성이 바뀌거나 새로 생기거나 없어진 상자 수(DOM 이 실제로 바뀐 것)
import { arg, baseUrl, withBrowser } from './browser.ts';

const data = arg('data', 'sample/compare.json');
const mode = arg('mode', '');
const moves = Number(arg('moves', '200'));
const runs = Number(arg('runs', '5'));

interface Result {
  work: number;
  script: number;
  frame: number;
  boxes: number;
  changed: number;
  items: number;
}
const results: Result[] = [];

await withBrowser(async (browser) => {
  for (let run = 0; run < runs; run++) {
    const context = await browser.newContext({
      viewport: { width: 1900, height: 1000 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    const cdp = await context.newCDPSession(page);
    await cdp.send('Performance.enable');
    const metrics = async () => {
      const { metrics: list } = await cdp.send('Performance.getMetrics');
      const of = (name: string) =>
        list.find((metric) => metric.name === name)?.value ?? 0;
      return {
        script: of('ScriptDuration') * 1000,
        work:
          (of('ScriptDuration') +
            of('RecalcStyleDuration') +
            of('LayoutDuration')) *
          1000,
      };
    };

    await page.goto(
      `${baseUrl}?data=${encodeURIComponent(data)}${mode ? `&mode=${mode}` : ''}`,
    );
    await page.locator('.dv-item').first().waitFor();
    const input = (await (
      await page.request.get(`${baseUrl}${data}`)
    ).json()) as { highlights: { documentId: string; page: number }[] };

    // 문서 칸마다 상자가 가장 많은 쪽으로 간다.
    for (const pane of await page.locator('.dv-pane').all()) {
      const documentId = await pane.getAttribute('data-document-id');
      const perPage = new Map<number, number>();
      for (const h of input.highlights)
        if (h.documentId === documentId)
          perPage.set(h.page, (perPage.get(h.page) ?? 0) + 1);
      const busiest = [...perPage].sort((x, y) => y[1] - x[1])[0]?.[0] ?? 1;
      await pane.locator('.dv-page-input').fill(String(busiest));
      await pane
        .locator(
          `.dv-page[data-page="${busiest}"] canvas[data-render-state="done"]`,
        )
        .waitFor();
    }

    // 화면에 보이는 항목들의 한가운데.
    const points = await page.locator('.dv-item-head').evaluateAll((heads) => {
      const list = document.querySelector('.dv-items')!.getBoundingClientRect();
      return heads
        .map((head) => head.getBoundingClientRect())
        .filter((rect) => rect.top >= list.top && rect.bottom <= list.bottom)
        .map((rect) => ({
          x: rect.left + rect.width / 2,
          y: rect.top + Math.min(10, rect.height / 2),
        }));
    });
    if (points.length < 2) throw new Error('화면에 보이는 항목이 둘보다 적다');

    // 바뀐 상자를 센다.
    await page.evaluate(() => {
      const state = { changed: new Set<Node>(), total: 0 };
      (window as unknown as { __hover: typeof state }).__hover = state;
      new MutationObserver((records) => {
        for (const record of records) {
          if (record.type === 'attributes') state.changed.add(record.target);
          for (const node of [...record.addedNodes, ...record.removedNodes])
            if ((node as Element).classList?.contains('dv-highlight'))
              state.changed.add(node);
        }
      }).observe(document.querySelector('.dv-panes')!, {
        subtree: true,
        attributes: true,
        childList: true,
        attributeFilter: ['data-pointed', 'data-selected'],
      });
    });
    const nextFrame = () =>
      page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => setTimeout(resolve, 0)),
          ),
      );

    await page.mouse.move(points[0]!.x, points[0]!.y);
    await nextFrame();
    await page.evaluate(() =>
      (
        window as unknown as { __hover: { changed: Set<Node> } }
      ).__hover.changed.clear(),
    );
    const before = await metrics();
    let frame = 0;
    let changed = 0;
    for (let move = 1; move <= moves; move++) {
      const point = points[move % points.length]!;
      const started = Date.now();
      await page.mouse.move(point.x, point.y);
      await nextFrame();
      frame += Date.now() - started;
      changed += await page.evaluate(() => {
        const state = (window as unknown as { __hover: { changed: Set<Node> } })
          .__hover;
        const count = state.changed.size;
        state.changed.clear();
        return count;
      });
    }
    const after = await metrics();
    results.push({
      work: (after.work - before.work) / moves,
      script: (after.script - before.script) / moves,
      frame: frame / moves,
      boxes: await page.locator('.dv-highlight').count(),
      changed: changed / moves,
      items: await page.locator('.dv-item').count(),
    });
    await context.close();
  }
});

const median = (values: number[]) =>
  [...values].sort((x, y) => x - y)[Math.floor(values.length / 2)]!;
const line = (label: string, values: number[], digits: number) =>
  `${label}: 중앙값 ${median(values).toFixed(digits)} (최소 ${Math.min(...values).toFixed(digits)} ~ 최대 ${Math.max(...values).toFixed(digits)})`;
console.log(
  `자료 ${data}, 보기 방식 ${mode || '기본값'}, 항목 ${results[0]?.items}개, 옮기기 ${moves}번 × ${runs}회`,
);
console.log(
  line(
    '옮기기 한 번의 일(ms)',
    results.map((r) => r.work),
    2,
  ),
);
console.log(
  line(
    '  그중 스크립트(ms)',
    results.map((r) => r.script),
    2,
  ),
);
console.log(
  line(
    '다음 프레임까지(ms. 재는 쪽의 왕복 포함)',
    results.map((r) => r.frame),
    1,
  ),
);
console.log(
  line(
    '그려진 상자(개)',
    results.map((r) => r.boxes),
    0,
  ),
);
console.log(
  line(
    '옮기기 한 번에 바뀐 상자(개)',
    results.map((r) => r.changed),
    1,
  ),
);
