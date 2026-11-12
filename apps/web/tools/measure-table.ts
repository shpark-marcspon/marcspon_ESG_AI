// 검토 표가 많은 행에서 얼마나 걸리는지 잰다.
//
// 사용(빌드한 것을 `pnpm preview` 로 띄워 둔 뒤. 개발 서버로 재면 React 의 개발용 검사가 섞여 느리게 나온다):
//   node tools/measure-table.ts --rows 5000 --runs 5 [--screen cards]
// 재는 법: 페이지 안에서 동작을 일으킨 때부터 그다음 화면 그리기가 끝난 직후(requestAnimationFrame → setTimeout 0)까지.
//   그래서 값마다 한 프레임(약 17ms)까지의 기다림이 섞여 있다. 「다시 그린 행」은 ?probe=1 이 세는 행 부품의 그리기 횟수다.
// 실행마다 새 브라우저 창, 화면 1400×900, 픽셀 밀도 1.
import { arg, baseUrl, withBrowser } from './browser.ts';

const rows = Number(arg('rows', '5000'));
const runs = Number(arg('runs', '5'));
const screen = arg('screen', 'table');

interface Sample {
  /** 그리기가 끝날 때까지. */
  ms: number;
  /** 동작을 일으키고 마이크로태스크가 빌 때까지(React 의 다시 그리기 계산까지. 브라우저의 배치·칠하기와 프레임 기다림은 빠진다). 스크롤에는 뜻이 없다. */
  sync: number;
  renders: number;
}
const results: Record<string, Sample[]> = {};
const facts: Record<string, number[]> = {};
const note = (name: string, sample: Sample) =>
  (results[name] ??= []).push(sample);
const fact = (name: string, value: number) => (facts[name] ??= []).push(value);

await withBrowser(async (browser) => {
  for (let run = 0; run < runs; run++) {
    const context = await browser.newContext({
      viewport: { width: 1400, height: 900 },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await page.goto(
      `${baseUrl}?view=table&data=fake&rows=${rows}&probe=1${screen === 'cards' ? '&screen=cards' : ''}`,
    );
    await page
      .locator('[data-testid="rt-scroll"] [data-row-id]')
      .first()
      .waitFor();
    // 주소를 연 때부터(가짜 행 만들기와 입력 검증까지 든다).
    note('첫 그리기', {
      ms: await page.evaluate(() => performance.now()),
      sync: 0,
      renders: await page.evaluate(() => window.__rowRenders ?? 0),
    });
    fact('DOM 의 행 수(처음)', await page.locator('[data-row-id]').count());

    /** 페이지 안에서 동작 하나를 일으키고, 그리기가 끝날 때까지의 시간과 다시 그린 행 수를 돌려준다. */
    const timed = (name: string, action: string) =>
      page
        .evaluate(async (source) => {
          const before = window.__rowRenders ?? 0;
          const start = performance.now();
          new Function(source)();
          // React 는 다시 그리기를 마이크로태스크로 미룰 수 있다. 그것까지 돌게 두 번 양보한 뒤에 잰다.
          await Promise.resolve();
          await Promise.resolve();
          const sync = performance.now() - start;
          await new Promise((done) =>
            requestAnimationFrame(() => setTimeout(done, 0)),
          );
          return {
            ms: performance.now() - start,
            sync,
            renders: (window.__rowRenders ?? 0) - before,
          };
        }, action)
        .then((sample) => note(name, sample));

    const click = (selector: string) =>
      `document.querySelector(${JSON.stringify(selector)}).click()`;
    const byText = (text: string) =>
      `[...document.querySelectorAll("button")].find((b) => b.textContent.trim().startsWith(${JSON.stringify(text)})).click()`;
    const setValue = (label: string, value: string, proto: string) =>
      `const el = document.querySelector('[aria-label="${label}"]');
       Object.getOwnPropertyDescriptor(${proto}.prototype, "value").set.call(el, ${JSON.stringify(value)});
       el.dispatchEvent(new Event(${proto === 'HTMLSelectElement' ? '"change"' : '"input"'}, { bubbles: true }));`;

    // 스크롤: 끝까지 스무 번에 나눠 간다.
    for (let step = 1; step <= 20; step++) {
      await timed(
        '스크롤 한 번(전체의 1/20)',
        `const s = document.querySelector('[data-testid="rt-scroll"]'); s.scrollTop = (s.scrollHeight - s.clientHeight) * ${step} / 20;`,
      );
    }
    await page.locator(`[data-index="${rows - 1}"]`).waitFor();
    fact('DOM 의 행 수(끝)', await page.locator('[data-row-id]').count());
    await timed(
      '맨 위로',
      `document.querySelector('[data-testid="rt-scroll"]').scrollTop = 0`,
    );

    if (screen === 'table') {
      await timed('정렬(배출량 오름)', byText('배출량'));
      await timed('정렬(배출량 내림)', byText('배출량'));
      await timed('정렬 풀기', byText('배출량'));
    }
    await timed(
      '걸러 보기(글자 「강판」)',
      setValue('글자로 걸러 보기', '강판', 'HTMLInputElement'),
    );
    fact(
      '걸러 본 행 수(강판)',
      Number(
        await page
          .locator('[data-testid="rt-shown"]')
          .getAttribute('data-shown'),
      ),
    );
    await timed(
      '걸러 보기 풀기',
      setValue('글자로 걸러 보기', '', 'HTMLInputElement'),
    );
    await timed(
      '걸러 보기(상태 검토대기)',
      setValue('상태로 걸러 보기', 'pending', 'HTMLSelectElement'),
    );
    await timed(
      '걸러 보기 풀기(상태)',
      setValue('상태로 걸러 보기', '', 'HTMLSelectElement'),
    );

    // 한 행: 후보가 있는 검토대기 행을 펼쳐 반영한다.
    const target = `[data-row-id][data-status="pending"]`;
    await timed('한 행 펼치기', click(`${target} [aria-label="펼치기"]`));
    await page.locator(`${target} [aria-label="접기"]`).first().waitFor();
    const accept = `[...document.querySelectorAll('[data-row-id] button')].find((b) => b.textContent.trim() === "반영" && !b.disabled).click()`;
    await timed('한 행 반영', accept);

    await timed('일괄 반영(전체)', byText('일괄 반영'));
    fact(
      '일괄 반영: 적용',
      Number(
        await page
          .locator('[data-testid="rt-bulk-result"]')
          .getAttribute('data-applied'),
      ),
    );
    await timed('일괄 최종 확정(전체)', byText('일괄 최종 확정'));
    fact(
      '일괄 최종 확정: 적용',
      Number(
        await page
          .locator('[data-testid="rt-bulk-result"]')
          .getAttribute('data-applied'),
      ),
    );
    fact(
      '일괄 최종 확정: 건너뜀',
      Number(
        await page
          .locator('[data-testid="rt-bulk-result"]')
          .getAttribute('data-skipped'),
      ),
    );
    await context.close();
  }
});

const median = (values: number[]) =>
  [...values].sort((x, y) => x - y)[Math.floor(values.length / 2)]!;
console.log(`가짜 ${rows}행, 화면 ${screen}, ${runs}회, ${baseUrl}`);
console.log(
  '동작 | 그리기까지 중앙값(ms) | 최소 ~ 최대(ms) | React 계산까지 중앙값(ms) | 다시 그린 행(중앙값) | 표본',
);
for (const [name, samples] of Object.entries(results)) {
  const ms = samples.map((sample) => sample.ms);
  console.log(
    `${name} | ${median(ms).toFixed(0)} | ${Math.min(...ms).toFixed(0)} ~ ${Math.max(...ms).toFixed(0)} | ${median(samples.map((sample) => sample.sync)).toFixed(1)} | ${median(samples.map((sample) => sample.renders))} | ${samples.length}`,
  );
}
for (const [name, values] of Object.entries(facts))
  console.log(`${name}: ${[...new Set(values)].join(', ')}`);
