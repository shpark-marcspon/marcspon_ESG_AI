// 강조의 좁은 상자가 「화면에 그려진 글자」 위에 놓였는지를 캔버스의 픽셀로 잰다. 눈으로 보기 전에 전부를 수치로 훑는 데 쓴다.
//   사용(서버가 떠 있어야 한다. tools/browser.ts): node tools/measure-ink.ts --data local/reconcile.json --scale 1 [--out <결과 JSON>]
//
// 글자 자리의 좌표는 문서를 분해한 쪽(PyMuPDF)이 낸 것이고, 화면의 글자는 pdf.js 가 그린 것이다. 둘이 글자 단위에서 맞는지는 그려 봐야 안다.
// 항목을 하나씩 골라, 골라진 강조의 조각마다 상자 안의 잉크(어두운 픽셀)가 차지한 범위를 찾고 상자의 네 변과의 틈을 낸다(포인트로 바꿔서).
//   잉크 없음      상자가 빈 곳에 놓였다(틀린 자리)
//   왼쪽·오른쪽 틈  글자 옆 여백만큼이면(1pt 안팎) 상자가 글자를 딱 덮은 것이다. 크면 상자가 글자보다 넓거나 옆으로 밀렸다
//   위·아래 틈      글자 자리의 세로는 글꼴의 줄 높이라 잉크보다 넉넉하다. 그 넉넉함이 얼마인지가 여기서 나온다
// 알 수 없는 것: 상자 안의 잉크가 「그 글자」인지(옆 글자를 덮고 있어도 잉크는 있다). 그것은 PDF 의 글자를 따로 읽어 견주거나 눈으로 본다.
// 잉크는 「상자 안에서 가장 흔한 색(바탕)과 뚜렷이 다른 픽셀」로 센다. 재는 격자가 화면 1픽셀이라 배율이 낮을수록 값이 거칠다(배율 1 이면 1pt).
import { writeFileSync } from 'node:fs';

import { arg, baseUrl, withBrowser } from './browser.ts';

const data = arg('data', 'sample/sentences.json');
const scale = Number(arg('scale', '1'));
const out = arg('out', '');

interface Row {
  item: string;
  highlight: string;
  document: string;
  page: number;
  piece: number;
  pieces: number;
  text?: string;
  ink: boolean;
  left?: number;
  right?: number;
  top?: number;
  bottom?: number;
  width: number;
  height: number;
}

await withBrowser(async (browser) => {
  const page = await browser.newPage({
    viewport: { width: 1900, height: 1000 },
    deviceScaleFactor: 1,
  });
  await page.goto(`${baseUrl}?data=${encodeURIComponent(data)}`);
  await page.locator('.dv-item').first().waitFor();
  const input = (await (
    await page.request.get(`${baseUrl}${data}`)
  ).json()) as {
    items: { id: string; highlightIds: string[] }[];
    highlights: {
      id: string;
      documentId: string;
      page: number;
      text?: string;
    }[];
  };
  for (const pane of await page.locator('.dv-pane').all()) {
    for (let guard = 0; guard < 10; guard++) {
      const current = Number(await pane.getAttribute('data-scale'));
      if (current === scale) break;
      await pane
        .getByRole('button', { name: current < scale ? '확대' : '축소' })
        .click();
    }
  }

  const rows: Row[] = [];
  for (const item of input.items) {
    await page
      .locator(`.dv-item[data-item-id="${item.id}"] .dv-item-head`)
      .click();
    for (const highlightId of item.highlightIds) {
      const highlight = input.highlights.find((h) => h.id === highlightId)!;
      const pageElement = page.locator(
        `.dv-pane[data-document-id="${highlight.documentId}"] .dv-page[data-page="${highlight.page}"]`,
      );
      // 시간을 재지 않고 상태를 묻는다: 그 쪽이 다 그려졌는가.
      await pageElement.locator('canvas[data-render-state="done"]').waitFor();
      const measured = await pageElement.evaluate((element, id) => {
        const canvas = element.querySelector('canvas')!;
        const canvasRect = canvas.getBoundingClientRect();
        const density = canvas.width / canvasRect.width;
        const image = canvas
          .getContext('2d')!
          .getImageData(0, 0, canvas.width, canvas.height);
        const colorAt = (x: number, y: number) => {
          const at = (y * image.width + x) * 4;
          return [
            image.data[at]!,
            image.data[at + 1]!,
            image.data[at + 2]!,
          ] as const;
        };
        const pieces = [
          ...element.querySelectorAll<HTMLElement>(
            ".dv-highlight[data-narrowed='true']",
          ),
        ].filter((piece) =>
          piece.dataset.highlightIds!.split(' ').includes(id),
        );
        return pieces.map((piece) => {
          const box = piece.getBoundingClientRect();
          const left = box.left - canvasRect.left;
          const top = box.top - canvasRect.top;
          const x0 = Math.max(0, Math.round(left * density));
          const x1 = Math.min(
            image.width,
            Math.round((left + box.width) * density),
          );
          const y0 = Math.max(0, Math.round(top * density));
          const y1 = Math.min(
            image.height,
            Math.round((top + box.height) * density),
          );
          // 바탕색 = 상자 안에서 가장 흔한 색(16단계로 뭉쳐 센다). 잉크 = 바탕색과 뚜렷이 다른 픽셀. 흰 바탕의 회색 글자도, 색 바탕의 흰 글자도 잡는다.
          const tally = new Map<number, number>();
          for (let y = y0; y < y1; y++)
            for (let x = x0; x < x1; x++) {
              const [r, g, b] = colorAt(x, y);
              const key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4);
              tally.set(key, (tally.get(key) ?? 0) + 1);
            }
          const common =
            [...tally].sort((a, b) => b[1] - a[1])[0]?.[0] ?? 0xfff;
          const base = [
            ((common >> 8) & 15) * 16 + 8,
            ((common >> 4) & 15) * 16 + 8,
            (common & 15) * 16 + 8,
          ];
          const isInk = (x: number, y: number) => {
            const color = colorAt(x, y);
            return (
              Math.abs(color[0] - base[0]!) +
                Math.abs(color[1] - base[1]!) +
                Math.abs(color[2] - base[2]!) >
              150
            );
          };
          let minX = Infinity,
            maxX = -Infinity,
            minY = Infinity,
            maxY = -Infinity;
          for (let y = y0; y < y1; y++) {
            for (let x = x0; x < x1; x++) {
              if (!isInk(x, y)) continue;
              minX = Math.min(minX, x);
              maxX = Math.max(maxX, x);
              minY = Math.min(minY, y);
              maxY = Math.max(maxY, y);
            }
          }
          const size = { width: box.width, height: box.height };
          if (!Number.isFinite(minX))
            return {
              ink: false,
              left: undefined,
              right: undefined,
              top: undefined,
              bottom: undefined,
              ...size,
            };
          return {
            ink: true,
            left: minX / density - left,
            right: left + box.width - (maxX + 1) / density,
            top: minY / density - top,
            bottom: top + box.height - (maxY + 1) / density,
            ...size,
          };
        });
      }, highlightId);
      measured.forEach((m, piece) => {
        const pt = (value: number | undefined) =>
          value === undefined ? undefined : (
            Math.round((value / scale) * 100) / 100
          );
        rows.push({
          item: item.id,
          highlight: highlightId,
          document: highlight.documentId,
          page: highlight.page,
          piece,
          pieces: measured.length,
          text: highlight.text?.slice(0, 40),
          ink: m.ink,
          left: pt(m.left),
          right: pt(m.right),
          top: pt(m.top),
          bottom: pt(m.bottom),
          width: pt(m.width)!,
          height: pt(m.height)!,
        });
      });
    }
  }

  const inked = rows.filter((row) => row.ink);
  const stat = (key: 'left' | 'right' | 'top' | 'bottom') => {
    const values = inked.map((row) => row[key]!).sort((a, b) => a - b);
    const at = (q: number) =>
      values[Math.min(values.length - 1, Math.floor(values.length * q))];
    return `중앙값 ${at(0.5)} · 90% ${at(0.9)} · 최대 ${values.at(-1)} · 최소 ${values[0]}`;
  };
  console.log(
    `measure-ink: ${data}, 배율 ${scale}. 항목 ${input.items.length}, 좁은 상자로 그려진 조각 ${rows.length} (단위 pt, 재는 격자는 화면 1픽셀 = ${Math.round(100 / scale) / 100}pt)`,
  );
  console.log(
    `  잉크가 있는 조각 ${inked.length}, 없는 조각 ${rows.length - inked.length}`,
  );
  if (inked.length > 0)
    for (const key of ['left', 'right', 'top', 'bottom'] as const)
      console.log(
        `  상자의 ${{ left: '왼쪽', right: '오른쪽', top: '위', bottom: '아래' }[key]} 변에서 잉크까지: ${stat(key)}`,
      );
  const wide = inked.filter((row) => row.left! > 3 || row.right! > 3);
  console.log(`  왼쪽이나 오른쪽 틈이 3pt 를 넘는 조각 ${wide.length}`);
  for (const row of [...rows.filter((r) => !r.ink), ...wide].slice(0, 8))
    console.log(`    ${JSON.stringify(row)}`);
  if (out) writeFileSync(out, JSON.stringify(rows));
});
