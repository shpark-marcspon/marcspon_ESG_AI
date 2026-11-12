// 그림 없이 재는 자리 단언(밴드 VS1 — sid:MARC-ISSUE-198·202). 시각 스펙(visual.spec.ts)이 장마다 부른다. 기준 그림이 없어도 늘 돈다.
//   - 가로 스크롤 0: document 의 scrollWidth ≤ 창 폭.
//   - 셀렉터 ▾(202 2·3번, 한 꼴 sid:MARC-ENT-430): 거르기 칸 FilterSelect = button[data-filter-value] 와 그 안 svg, 기본 select NativeSelect =
//     select + svg(감싼 span 이 상자). ▾ 상자가 단추 상자 안 · 오른쪽 여백(단추 오른쪽 − ▾ 오른쪽) 16±2 · 세로 가운데 차이 ≤ 1.
//   - GW-05 칩(202 1번): [data-testid="chips"] > * 가 [data-testid="review-detail-card"] 안(±0.5).
//   - 낱말 안 꺾임·한 줄 말줄임(밴드 KA1): 앱 바탕 keep-all 로 낱말이 한 줄에 남는지 · AD-04 올린 사람이 한 줄 말줄임 + title 인지.
// 실패 글에 화면·폭·상자 좌표를 싣는다(빨강의 1차 판단이 그림 없이 되게).
import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';

/** 셀렉터 ▾ 오른쪽 여백(px-4·right-4 — selectLook.ts·NativeSelect.tsx)과 허용 폭. */
const CHEVRON_GAP = 16;
const CHEVRON_SLACK = 2;

type Box = { left: number; right: number; top: number; bottom: number };

export async function assertNoHorizontalScroll(page: Page, where: string) {
  const { scroll, inner } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    inner: window.innerWidth,
  }));
  expect(
    scroll,
    `${where}: 가로 스크롤 — scrollWidth ${scroll} > 창 ${inner}`,
  ).toBeLessThanOrEqual(inner);
}

/** 화면에 보이는 셀렉터 전부의 ▾ 자리를 잰다. 잰 개수를 돌려준다. */
export async function assertSelectChevrons(page: Page, where: string) {
  const measured = await page.evaluate(() => {
    const box = (el: Element) => {
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    const visible = (el: Element) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    };
    const out: {
      kind: 'filter' | 'native';
      name: string;
      trigger: Box;
      chevron: Box | null;
    }[] = [];
    for (const button of document.querySelectorAll(
      'button[data-filter-value]',
    )) {
      if (!visible(button)) continue;
      const svg = button.querySelector('svg');
      out.push({
        kind: 'filter',
        name: button.getAttribute('aria-label') ?? button.textContent ?? '',
        trigger: box(button),
        chevron: svg ? box(svg) : null,
      });
    }
    for (const select of document.querySelectorAll('select')) {
      const wrap = select.parentElement;
      if (!wrap || !visible(select)) continue;
      // NativeSelect 꼴: 감싼 span 안의 select 다음 형제가 ▾
      const svg = select.nextElementSibling;
      out.push({
        kind: 'native',
        name: select.getAttribute('aria-label') ?? select.name ?? select.id,
        trigger: box(wrap),
        chevron: svg instanceof SVGElement ? box(svg) : null,
      });
    }
    return out;
  });
  for (const [index, m] of measured.entries()) {
    const label = `${where}: ${m.kind} 셀렉터 #${index}「${m.name.trim()}」 단추 ${fmt(m.trigger)} ▾ ${m.chevron ? fmt(m.chevron) : '없음'}`;
    expect(m.chevron, `${label} — ▾ 없음`).not.toBeNull();
    const c = m.chevron!;
    const t = m.trigger;
    expect(
      c.left >= t.left - 0.5 &&
        c.right <= t.right + 0.5 &&
        c.top >= t.top - 0.5 &&
        c.bottom <= t.bottom + 0.5,
      `${label} — ▾ 가 단추 밖`,
    ).toBe(true);
    const gap = t.right - c.right;
    expect(
      Math.abs(gap - CHEVRON_GAP),
      `${label} — 오른쪽 여백 ${gap.toFixed(1)}(기대 ${CHEVRON_GAP}±${CHEVRON_SLACK})`,
    ).toBeLessThanOrEqual(CHEVRON_SLACK);
    const middle = (t.top + t.bottom) / 2 - (c.top + c.bottom) / 2;
    expect(
      Math.abs(middle),
      `${label} — 세로 가운데 차이 ${middle.toFixed(1)}`,
    ).toBeLessThanOrEqual(1);
  }
  return measured.length;
}

/** GW-05: 근거 칩이 상세 카드 안. 잰 칩 개수를 돌려준다. */
export async function assertChipsInsideCard(page: Page, where: string) {
  const { card, chips } = await page.evaluate(() => {
    const box = (el: Element) => {
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    const host = document.querySelector('[data-testid="review-detail-card"]');
    return {
      card: host ? box(host) : null,
      chips: [...document.querySelectorAll('[data-testid="chips"] > *')].map(
        box,
      ),
    };
  });
  expect(card, `${where}: review-detail-card 없음`).not.toBeNull();
  for (const [index, chip] of chips.entries())
    expect(
      chip.left >= card!.left - 0.5 && chip.right <= card!.right + 0.5,
      `${where}: 칩 #${index} ${fmt(chip)} 가 카드 ${fmt(card!)} 밖`,
    ).toBe(true);
  return chips.length;
}

const fmt = (b: Box) =>
  `[${b.left.toFixed(1)},${b.top.toFixed(1)}–${b.right.toFixed(1)},${b.bottom.toFixed(1)}]`;

/**
 * 한국어 낱말이 줄 가운데서 꺾이지 않았는가(밴드 KA1 — 앱 바탕 keep-all, VS1 6c). root 안 글 마디에서 낱말마다 그 글자 Range 의
 * 줄(getClientRects 의 폭>0 상자 top)이 하나인지 잰다. 낱말은 보이는 자리에서 한 번 이상 찾아야 한다(못 찾으면 빈 검사 — 빨강).
 * root 의 계산된 word-break 가 keep-all 인지도(앱 바탕 상속).
 */
export async function assertWordsUnbroken(
  page: Page,
  where: string,
  root: string,
  words: readonly string[],
) {
  const measured = await page.evaluate(
    ({ root, words }) => {
      const host = document.querySelector(root);
      if (!host) return null;
      const found: Record<string, number> = {};
      const broken: { word: string; tops: number[]; text: string }[] = [];
      for (const word of words) found[word] = 0;
      const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
      for (let text = walker.nextNode(); text; text = walker.nextNode()) {
        const value = text.textContent ?? '';
        for (const word of words) {
          for (
            let at = value.indexOf(word);
            at !== -1;
            at = value.indexOf(word, at + word.length)
          ) {
            const range = document.createRange();
            range.setStart(text, at);
            range.setEnd(text, at + word.length);
            const tops = [
              ...new Set(
                [...range.getClientRects()]
                  .filter((rect) => rect.width > 0)
                  .map((rect) => Math.round(rect.top)),
              ),
            ];
            if (tops.length === 0) continue;
            found[word]!++;
            if (tops.length > 1) broken.push({ word, tops, text: value });
          }
        }
      }
      return { wordBreak: getComputedStyle(host).wordBreak, found, broken };
    },
    { root, words },
  );
  expect(measured, `${where}: ${root} 없음`).not.toBeNull();
  const { wordBreak, found, broken } = measured!;
  expect(wordBreak, `${where}: ${root} 의 word-break`).toBe('keep-all');
  for (const word of words)
    expect(
      found[word],
      `${where}: 낱말 없음「${word}」(${root})`,
    ).toBeGreaterThan(0);
  expect(
    broken.map((b) => `「${b.word}」 줄 ${b.tops.join('/')} — ${b.text}`),
    `${where}: 낱말 가운데서 꺾임`,
  ).toEqual([]);
  return words.map((word) => found[word]!).reduce((a, b) => a + b, 0);
}

/**
 * 한 줄 말줄임 칸(밴드 KA1 — AD-04 올린 사람): root 안에서 글이 text 인 맨 끝 요소마다 한 줄(Range 줄 top 하나) ·
 * 정말 말줄임(scrollWidth > clientWidth) · title = 전체 글. 잰 개수를 돌려준다(0 이면 빈 검사 — 빨강).
 */
export async function assertTruncatedOneLine(
  page: Page,
  where: string,
  root: string,
  text: string,
) {
  const cells = await page.evaluate(
    ({ root, text }) =>
      [...document.querySelectorAll(root)].flatMap((host) =>
        [host, ...host.querySelectorAll('*')]
          .filter(
            (el) =>
              el.childElementCount === 0 && el.textContent?.trim() === text,
          )
          .map((el) => {
            const range = document.createRange();
            range.selectNodeContents(el);
            const lines = new Set(
              [...range.getClientRects()]
                .filter((rect) => rect.width > 0)
                .map((rect) => Math.round(rect.top)),
            ).size;
            return {
              lines,
              scroll: el.scrollWidth,
              client: el.clientWidth,
              title: el.getAttribute('title'),
            };
          }),
      ),
    { root, text },
  );
  expect(
    cells.length,
    `${where}: 「${text}」 칸 없음(${root})`,
  ).toBeGreaterThan(0);
  for (const [index, cell] of cells.entries()) {
    const label = `${where}: 「${text}」 #${index}`;
    expect(cell.lines, `${label} — 줄 수`).toBe(1);
    expect(
      cell.scroll,
      `${label} — 말줄임 아님(scrollWidth ${cell.scroll} ≤ clientWidth ${cell.client})`,
    ).toBeGreaterThan(cell.client);
    expect(cell.title, `${label} — title`).toBe(text);
  }
  return cells.length;
}
