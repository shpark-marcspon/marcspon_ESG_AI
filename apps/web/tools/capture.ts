// 항목을 하나씩 골라, 골라진 강조 상자 둘레를 그림으로 남긴다. 「상자가 글자 위에 놓였는가」를 눈으로 보는 데 쓴다.
//
// 사용(개발 서버가 떠 있어야 한다):
//   node tools/capture.ts --data local/reconcile.json --items v1,v2,u-a1 --scale 1.5 --out <그림을 쓸 폴더>
//   --items 를 안 주면 --every N (기본 12) 번째 항목마다 하나씩 고른다. --mode outline|selected|fill 로 강조의 보기 방식을 정한다.
// 그림과 함께 index.json 을 쓴다: 그림마다 어느 항목의 어느 문서인지, 상자가 가리켜야 하는 글자가 무엇인지.
// ★ 실제 자료의 그림이 나오므로 --out 은 저장소 밖이거나 .gitignore 된 폴더(.local-data/)여야 한다.
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { arg, baseUrl, withBrowser } from './browser.ts';

const data = arg('data', 'sample/compare.json');
const scale = Number(arg('scale', '1'));
const every = Number(arg('every', '12'));
const outDir = resolve(arg('out', '.local-data/shots'));
const wanted = arg('items', '');
// 강조의 보기 방식(outline | selected | fill). 안 주면 뷰어의 기본값.
const mode = arg('mode', '');
mkdirSync(outDir, { recursive: true });

await withBrowser(async (browser) => {
  const page = await browser.newPage({
    viewport: { width: 1900, height: 1000 },
    deviceScaleFactor: 1,
  });
  await page.goto(
    `${baseUrl}?data=${encodeURIComponent(data)}${mode ? `&mode=${mode}` : ''}`,
  );
  await page.locator('.dv-item').first().waitFor();

  const input = (await (
    await page.request.get(`${baseUrl}${data}`)
  ).json()) as {
    items: {
      id: string;
      title: string;
      detail?: string;
      highlightIds: string[];
    }[];
    highlights: {
      id: string;
      documentId: string;
      page: number;
      text?: string;
      innerBox?: number[];
      innerBoxes?: number[][];
    }[];
  };
  const ids =
    wanted ?
      wanted.split(',')
    : input.items
        .filter((_, index) => index % every === 0)
        .map((item) => item.id);

  // 배율을 맞춘다(문서 칸마다).
  for (const pane of await page.locator('.dv-pane').all()) {
    for (let guard = 0; guard < 10; guard++) {
      const current = Number(await pane.getAttribute('data-scale'));
      if (current === scale) break;
      await pane
        .getByRole('button', { name: current < scale ? '확대' : '축소' })
        .click();
    }
  }

  const index: unknown[] = [];
  for (const id of ids) {
    const item = input.items.find((candidate) => candidate.id === id);
    if (!item) throw new Error(`항목 ${id} 가 없다`);
    await page.locator(`.dv-item[data-item-id="${id}"] .dv-item-head`).click();

    for (const highlightId of item.highlightIds) {
      const highlight = input.highlights.find((h) => h.id === highlightId)!;
      const pane = page.locator(
        `.dv-pane[data-document-id="${highlight.documentId}"]`,
      );
      const pageElement = pane.locator(
        `.dv-page[data-page="${highlight.page}"]`,
      );
      // 시간을 재지 않고 상태를 묻는다: 그 쪽이 다 그려졌는가.
      await pageElement.locator('canvas[data-render-state="done"]').waitFor();
      // 골라진 강조의 조각 전부(여러 줄이면 여럿)를 감싼 자리.
      const rects = await pane
        .locator('.dv-highlight[data-selected="true"]')
        .evaluateAll((elements) =>
          elements
            .map((element) => element.getBoundingClientRect())
            .map((r) => ({ x: r.x, y: r.y, right: r.right, bottom: r.bottom })),
        );
      if (rects.length === 0)
        throw new Error(`${highlightId}: 골라진 상자가 화면에 없다`);
      const left = Math.min(...rects.map((r) => r.x));
      const top = Math.min(...rects.map((r) => r.y));
      const box = {
        x: left,
        y: top,
        width: Math.max(...rects.map((r) => r.right)) - left,
        height: Math.max(...rects.map((r) => r.bottom)) - top,
      };

      const paneBox = (await pane.locator('.dv-scroller').boundingBox())!;
      const pad = { x: 170, y: 70 };
      const x = Math.max(paneBox.x, box.x - pad.x);
      const y = Math.max(paneBox.y, box.y - pad.y);
      const clip = {
        x,
        y,
        width:
          Math.min(paneBox.x + paneBox.width, box.x + box.width + pad.x) - x,
        height:
          Math.min(paneBox.y + paneBox.height, box.y + box.height + pad.y) - y,
      };
      const file = `${id}_${highlight.documentId}_x${scale}.png`;
      await page.screenshot({ path: join(outDir, file), clip });
      index.push({
        file,
        item: id,
        title: item.title,
        document: highlight.documentId,
        page: highlight.page,
        shouldCover: highlight.text,
        narrowed: Boolean(highlight.innerBoxes ?? highlight.innerBox),
        pieces: rects.length,
        scale,
      });
    }
  }
  writeFileSync(
    join(outDir, `index_x${scale}.json`),
    JSON.stringify(index, null, 2),
  );
  console.log(`capture: 그림 ${index.length}장을 ${outDir} 에 썼다`);
});
