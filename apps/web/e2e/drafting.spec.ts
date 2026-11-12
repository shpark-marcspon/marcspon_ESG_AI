// 원고작성 화면을 빌드 결과에서(밴드 RPW1 ② S7a · ③ S7b — 발주서 §2-2·§2-3). 서버는 e2e/drafting-server.ts 의 흉내(import 만), 합성 PDF 3쪽은 메모리에서 짓는다.
//   RP-01 빈 → [새 프로젝트] → PDF 올림 셋(POST /documents → 서명 PUT(Authorization 0) → confirm) · PUT …/document 본문 → RP-03 목차 넷 + 요구 →
//   [초안 만들기] = PUT …/outline 본문 → POST /runs 본문·Idempotency-Key → RP-04 진행 줄 → 다 만듦.
// 흉내 밖 /api/ 요청은 덫(503)으로 적고 끝에 0 인지 본다(ghg-server.spec.ts 꼴).
import { expect, test } from '@playwright/test';
import type { Locator, Page, Route } from '@playwright/test';

import { readFileSync } from 'node:fs';

import { DR_TEXT } from '../src/entities/drafting/config/text.ts';
import { IR_TEXT } from '../src/entities/materiality/config/text.ts';
import { writePdf } from '../tools/pdf-writer.ts';
import { SEED_MARKS, fakeDraftingApi } from './drafting-server.ts';
import { fakeMaterialityApi } from './materiality-server.ts';
import { signIn } from './session.ts';

const PDF = Buffer.from(
  writePdf(
    Array.from({ length: 3 }, (_, n) => ({
      width: 595,
      height: 842,
      rotate: 0 as const,
      marks: [],
      texts: [{ x: 72, top: 72, size: 18, str: `Made-up page ${n + 1}` }],
      tables: [],
    })),
  ),
);

/** 흉내 밖 /api/ 요청을 적고 503 으로 끊는다(흉내보다 먼저 건다). */
async function trapUnrouted(page: Page) {
  const unrouted: string[] = [];
  await page.route(/\/api\//, (route) => {
    const url = new URL(route.request().url());
    unrouted.push(`${route.request().method()} ${url.pathname}`);
    return route.fulfill({ status: 503, body: '' });
  });
  return unrouted;
}

async function open(page: Page) {
  const unrouted = await trapUnrouted(page);
  const api = await fakeDraftingApi(page);
  await signIn(page);
  return { unrouted, api };
}

const outline = DR_TEXT.outline;

/** 고른 줄의 이름(과 요구)을 적는다. */
async function name(page: Page, title: string, requirement?: string) {
  await page.getByLabel(outline.nameLabel).fill(title);
  if (requirement !== undefined)
    await page.getByLabel(outline.requirementLabel).fill(requirement);
}

test('S7a: RP-01 빈 → 새 프로젝트·PDF 올림 → 목차 넷 → 초안 만들기 → 진행 → 다 만듦', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/drafting');
  await expect(page.getByText(DR_TEXT.list.empty)).toBeVisible();
  await page.getByRole('button', { name: DR_TEXT.list.newProject }).click();
  await expect(page).toHaveURL(/\/drafting\/new$/);

  await page
    .locator('[data-card="document"] input[type="file"]')
    .setInputFiles({
      name: 'made_up_report.pdf',
      mimeType: 'application/pdf',
      buffer: PDF,
    });
  await page.getByRole('button', { name: DR_TEXT.create.next }).click();
  await expect(page).toHaveURL(/\/drafting\/projects\/1\/outline$/);
  expect(api.of('POST /drafting/projects')).toHaveLength(1);
  expect(api.of('POST /documents')).toHaveLength(1);
  const put = api.calls.filter((call) => call.path === '/fake-upload/101');
  expect(put.map((call) => [call.method, call.authorization])).toEqual([
    ['PUT', null],
  ]);
  expect(api.of('POST /documents/101/confirm')).toHaveLength(1);
  expect(
    api.of('PUT /drafting/projects/1/document').map((call) => call.body),
  ).toEqual([{ documentId: 101 }]);

  // RP-03 — 빈 목차, [초안 만들기] 꺼짐.
  await expect(page.getByTestId('outline-empty')).toBeVisible();
  const start = page.getByRole('button', { name: outline.start });
  await expect(start).toBeDisabled();
  await page.getByRole('button', { name: outline.addTop }).click();
  await name(page, '가상 환경');
  await page.getByRole('button', { name: outline.addChild }).click();
  await name(page, '가상 기후 대응', '가상 요구 — 배출 관리 개조식');
  await page.locator('[data-testid="outline-tree"] [data-key]').first().click();
  await page.getByRole('button', { name: outline.addChild }).click();
  await name(page, '가상 자원');
  await page.getByRole('button', { name: outline.addTop }).click();
  await name(page, '가상 사회');
  await expect(page.getByTestId('outline-counts')).toHaveText(
    outline.counts([2, 2, 0, 0], 3),
  );
  await expect(page.getByTestId('outline-dirty')).toBeVisible();
  // 새 마디 key 는 브라우저가 무작위로 짓는다(지운 key 를 다시 쓰지 않게 — 검증 R4) — 화면에서 읽어 본문과 견준다.
  const keys = await page
    .locator('[data-testid="outline-tree"] [data-key]')
    .evaluateAll((rows) => rows.map((row) => row.getAttribute('data-key')!));
  expect(keys).toHaveLength(4);
  expect(new Set(keys).size).toBe(4);
  for (const key of keys) expect(key).toMatch(/^n[0-9a-f]{8}$/);
  const [k1, k2, k3, k4] = keys as [string, string, string, string];

  await start.click();
  await expect(page).toHaveURL(/\/drafting\/projects\/1\/runs\/301$/);
  expect(
    api.of('PUT /drafting/projects/1/outline').map((call) => call.body),
  ).toEqual([
    {
      nodes: [
        {
          key: k1,
          parentKey: null,
          depth: 1,
          title: '가상 환경',
          requirement: '',
        },
        {
          key: k2,
          parentKey: k1,
          depth: 2,
          title: '가상 기후 대응',
          requirement: '가상 요구 — 배출 관리 개조식',
        },
        {
          key: k3,
          parentKey: k1,
          depth: 2,
          title: '가상 자원',
          requirement: '',
        },
        {
          key: k4,
          parentKey: null,
          depth: 1,
          title: '가상 사회',
          requirement: '',
        },
      ],
    },
  ]);
  const posts = api.of('POST /runs');
  expect(posts).toHaveLength(1);
  expect(posts[0]!.body).toMatchObject({
    module: 'drafting',
    options: { projectId: 1 },
  });
  expect(Object.keys(posts[0]!.body as object).sort()).toEqual([
    'launchKey',
    'module',
    'options',
  ]);
  expect(posts[0]!.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/);

  // RP-04 진행 — 줄 셋, 끝나면 다 만듦(폴링 멈춤).
  await expect(page.getByTestId('run-heading')).toHaveText(DR_TEXT.run.making);
  await expect(page.locator('[data-step]')).toHaveCount(3);
  await expect(page.locator('[data-step="draft"]')).toContainText(
    DR_TEXT.run.stepCount(1, 3),
    { timeout: 15_000 },
  );
  // 다 만듦 → 결과 세 칸(경계 ③).
  await expect(page.getByTestId('run-result')).toBeVisible({
    timeout: 20_000,
  });
  const reads = api.of('GET /runs/301').length;
  await page.waitForTimeout(2_500);
  expect(api.of('GET /runs/301')).toHaveLength(reads);
  expect(unrouted).toEqual([]);
});

const result = DR_TEXT.result;
const OUT = process.env.RPW1_SHOTS;

test('S7b: RP-04 결과 → bullet → 실제 pdf.js 쪽 그림 + 근거 두 층 수 == 손셈 → 목차 고침 → 띠 → 다시 만들기 둘 → 내려받기', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { unrouted, api } = await open(page);
  const [projectId, runId] = api.seed(PDF);
  const runUrl = `/drafting/projects/${projectId}/runs/${runId}`;
  await page.goto(runUrl);
  await expect(page.getByTestId('result-counts')).toHaveText(
    result.counts(2, 2, 0, 0, 0),
  );

  // bullet → 1쪽: 실제 pdf.js 가 캔버스를 그리고, 옅은·진한 층 수가 흉내의 손셈과 같다.
  await page.getByText('가상 근거 bullet 하나').click();
  const sheet = page.getByTestId('source-sheet');
  await expect(sheet).toHaveAttribute('data-page', '1');
  await expect(sheet.locator('canvas[data-render-state="done"]')).toHaveCount(
    1,
    { timeout: 15_000 },
  );
  await expect(page.locator('[data-layer="block"]')).toHaveCount(
    SEED_MARKS[1]![0],
  );
  await expect(page.locator('[data-layer="sentence"]')).toHaveCount(
    SEED_MARKS[1]![1],
  );
  await expect(page.getByTestId('paragraph-only')).toHaveCount(0);
  // 고른 칩·쪽 칩이 실제로 칠해진다(없는 토큰이면 className 시험은 지나도 바탕이 비친다 — RPW2 ② 사진에서 잡음).
  const fill = (selector: string) =>
    page
      .locator(selector)
      .first()
      .evaluate((node) => getComputedStyle(node).backgroundColor);
  expect(
    await fill('[data-testid="source-chip"][aria-pressed="true"]'),
  ).not.toBe('rgba(0, 0, 0, 0)');
  // 쪽 칩은 button 기본 바탕이 있어 「비치지 않음」으로 못 가른다 — 고른 출처 칩과 같은 색인지 본다.
  expect(
    await fill('[data-testid="source-pane"] button[aria-pressed="true"]'),
  ).toBe(await fill('[data-testid="source-chip"][aria-pressed="true"]'));
  if (OUT) await page.screenshot({ path: `${OUT}/s7b-1-evidence.png` });

  // 칩 2쪽 → sentence null: 옅은 것만 + 「문단까지만 찾았어요」.
  await page.getByRole('button', { name: result.chip(2) }).click();
  await expect(sheet).toHaveAttribute('data-page', '2');
  await expect(sheet.locator('canvas[data-render-state="done"]')).toHaveCount(
    1,
    { timeout: 15_000 },
  );
  await expect(page.locator('[data-layer="block"]')).toHaveCount(
    SEED_MARKS[2]![0],
  );
  await expect(page.locator('[data-layer="sentence"]')).toHaveCount(
    SEED_MARKS[2]![1],
  );
  await expect(page.getByTestId('paragraph-only')).toBeVisible();
  if (OUT) await page.screenshot({ path: `${OUT}/s7b-2-paragraph.png` });
  expect(api.of('GET /documents/101/file')).toHaveLength(1);

  // 내려받기 — 머리 단추는 받기 모달만 열고(RPW13), 「개조식 초안」 줄 [Word] 가 받는다 · Content-Disposition 이름.
  await page.getByTestId('result-download').click();
  await expect(page.getByTestId('result-download-dialog')).toBeVisible();
  const download = page.waitForEvent('download');
  await page.getByTestId('result-download-dialog-file-docx').click();
  expect((await download).suggestedFilename()).toBe('가상 초안.docx');

  // 목차 고침(a1 이름 · 대제목 아래 새 잎) → 저장 → RP-04 띠 「바뀐 목차 2개」.
  await page.goto(`/drafting/projects/${projectId}/outline`);
  await page.locator('[data-key="a1"]').click();
  await name(page, '가상 기후 고침');
  await page.locator('[data-key="a"]').click();
  await page.getByRole('button', { name: outline.addChild }).click();
  await name(page, '가상 공급망');
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  await page.goto(runUrl);
  await expect(page.getByTestId('band-count')).toHaveText(
    `${result.changed} · ${result.changedCount(2)}`,
  );
  await expect(page.getByTestId('changed-mark')).toHaveCount(2);
  if (OUT) await page.screenshot({ path: `${OUT}/s7b-3-band.png` });

  // 다시 만들기 둘 — 바뀐 목차(rebuild []) · 이 목차(rebuild [a1]).
  await page.getByRole('button', { name: result.rebuildChanged }).click();
  await expect(page).toHaveURL(
    new RegExp(`/drafting/projects/${projectId}/runs/(?!${runId}$)\\d+$`),
  );
  await page.goto(runUrl);
  await page.getByRole('button', { name: result.rebuildOne }).click();
  await expect(page).toHaveURL(
    new RegExp(`/drafting/projects/${projectId}/runs/(?!${runId}$)\\d+$`),
  );
  expect(
    api
      .of('POST /runs')
      .map((call) => (call.body as { options: unknown }).options),
  ).toEqual([
    { projectId, base: { runId, rebuild: [] } },
    { projectId, base: { runId, rebuild: ['a1'] } },
  ]);
  expect(unrouted).toEqual([]);
});

test('S7d: RP-04 세 칸 — 1440 폭 차례·띠 단추 오른쪽 끝 · 1280 처음부터 접힘·겹침 0', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { api } = await open(page);
  const [projectId, runId] = api.seed(PDF);
  await page.goto(`/drafting/projects/${projectId}/outline`);
  await page.locator('[data-key="a1"]').click();
  await name(page, '가상 기후 고침');
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const runUrl = `/drafting/projects/${projectId}/runs/${runId}`;
  const box = async (testId: string) =>
    (await page.getByTestId(testId).boundingBox())!;

  await page.goto(runUrl);
  await expect(page.getByTestId('band-count')).toBeVisible();
  const tree = page.getByTestId('result-tree');
  await expect(tree).toHaveAttribute('data-folded', 'false');
  const wide = {
    tree: await box('result-tree'),
    leaf: await box('leaf-pane'),
    source: await box('source-pane'),
    band: await box('result-band'),
  };
  expect(wide.leaf.width).toBeGreaterThan(wide.source.width);
  expect(wide.source.width).toBeGreaterThan(wide.tree.width);
  const button = (await page
    .getByRole('button', { name: result.rebuildChanged })
    .boundingBox())!;
  expect(
    wide.band.x + wide.band.width - (button.x + button.width),
  ).toBeLessThanOrEqual(24);

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(runUrl);
  await expect(tree).toHaveAttribute('data-folded', 'true');
  const folded = await box('result-tree');
  const leaf = await box('leaf-pane');
  expect(folded.x + folded.width).toBeLessThanOrEqual(leaf.x);
});

test('S7f: 텍스트 없는 PDF → 다른 PDF → 시작 연결 끊김 → 앱 안에서 다시 들어와 누름 = 같은 키 · 실행 하나', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/drafting/new');
  const next = page.getByRole('button', { name: DR_TEXT.create.next });
  api.noTextNext();
  await page
    .locator('[data-card="document"] input[type="file"]')
    .setInputFiles({
      name: 'made_up_scan.pdf',
      mimeType: 'application/pdf',
      buffer: PDF,
    });
  await next.click();
  await expect(page.getByTestId('create-problem')).toHaveAttribute(
    'data-problem',
    'noText',
  );
  await expect(next).toBeDisabled();
  expect(api.of('PUT /drafting/projects/1/document')).toHaveLength(0);
  const chooser = page.waitForEvent('filechooser');
  await page.getByRole('button', { name: DR_TEXT.create.otherPdf }).click();
  await (
    await chooser
  ).setFiles({
    name: 'made_up_report.pdf',
    mimeType: 'application/pdf',
    buffer: PDF,
  });
  await expect(next).toBeEnabled();
  await next.click();
  await expect(page).toHaveURL(/\/drafting\/projects\/1\/outline$/);
  expect(api.of('POST /drafting/projects')).toHaveLength(1);
  expect(
    api.of('PUT /drafting/projects/1/document').map((call) => call.body),
  ).toEqual([{ documentId: 102 }]);

  await page.getByRole('button', { name: outline.addTop }).click();
  await name(page, '가상 환경');
  api.dropRunOnce();
  await page.getByRole('button', { name: outline.start }).click();
  await expect(page.getByTestId('outline-notice')).toHaveText(
    DR_TEXT.startFailed,
  );
  await expect(page).toHaveURL(/\/outline$/);

  // 앱 안 이동으로 떠났다 돌아온다(goto 는 페이지째 새로 짓는다 — 모듈 표는 페이지 수명만).
  await page.getByRole('button', { name: outline.toList }).click();
  await expect(page).toHaveURL(/\/drafting$/);
  await page.locator('[data-next="outline"]').click();
  await expect(page).toHaveURL(/\/outline$/);
  await page.getByRole('button', { name: outline.start }).click();
  await expect(page).toHaveURL(/\/drafting\/projects\/1\/runs\/301$/);

  const posts = api.of('POST /runs');
  expect(posts).toHaveLength(2);
  expect(posts[1]!.idempotencyKey).toBe(posts[0]!.idempotencyKey);
  expect((posts[1]!.body as { launchKey: string }).launchKey).toBe(
    (posts[0]!.body as { launchKey: string }).launchKey,
  );
  expect(api.runs.size).toBe(1);
  expect(unrouted).toEqual([]);
});

type Schema = {
  $ref?: string;
  anyOf?: Schema[];
  type?: string;
  required?: string[];
  properties?: Record<string, Schema>;
  items?: Schema;
};
type OpenApi = {
  paths: Record<
    string,
    Record<
      string,
      {
        responses: Record<
          string,
          { content?: Record<string, { schema: Schema }> }
        >;
      }
    >
  >;
  components: { schemas: Record<string, Schema> };
};

test('S7e: 흉내의 JSON 응답마다 openapi 성공 꼴의 required 를 다 싣는다(손 목록 0, 브라우저 0)', async () => {
  const O = JSON.parse(
    readFileSync(
      new URL('../../api-py/generated/openapi.json', import.meta.url),
      'utf8',
    ),
  ) as OpenApi;
  const named = (schema: Schema) =>
    schema.$ref ? O.components.schemas[schema.$ref.split('/').pop()!]! : schema;
  /** $ref 를 풀고 「꼴 하나 | null」 을 꼴로 — 여러 꼴의 합은 null(가르지 않는다). */
  const shapeOf = (schema: Schema): Schema | null => {
    if (!schema.anyOf) return named(schema);
    const rest = schema.anyOf.filter((one) => one.type !== 'null');
    return rest.length === 1 ? named(rest[0]!) : null;
  };
  const missing = (value: unknown, schema: Schema, at: string): string[] => {
    const shape = shapeOf(schema);
    if (!shape || value === null || typeof value !== 'object') return [];
    if (Array.isArray(value))
      return shape.items ?
          value.flatMap((one, n) => missing(one, shape.items!, `${at}[${n}]`))
        : [];
    const held = value as Record<string, unknown>;
    return [
      ...(shape.required ?? [])
        .filter((key) => !(key in held))
        .map((key) => `${at}.${key}`),
      ...Object.entries(shape.properties ?? {}).flatMap(([key, sub]) =>
        key in held ? missing(held[key], sub, `${at}.${key}`) : [],
      ),
    ];
  };
  const templateOf = (path: string) =>
    Object.keys(O.paths).find((one) =>
      new RegExp(`^${one.replace(/\{[^}]+\}/g, '[^/]+')}$`).test(path),
    );

  const handlers = new Map<string, (route: Route) => Promise<unknown>>();
  const fakePage = {
    route: async (
      pattern: string,
      handler: (route: Route) => Promise<unknown>,
    ) => {
      handlers.set(pattern, handler);
    },
  } as unknown as Page;
  const api = await fakeDraftingApi(fakePage);
  const gaps: string[] = [];
  const checked = new Set<string>();
  const call = async (
    method: string,
    path: string,
    body?: unknown,
    headers: Record<string, string> = {},
  ) => {
    let sent: { status?: number; body?: string | Buffer } = {};
    const url = `http://fake.test/api${path}`;
    const route = {
      request: () => ({
        url: () => url,
        method: () => method,
        postData: () => (body === undefined ? null : JSON.stringify(body)),
        postDataJSON: () => body,
        headers: () => headers,
      }),
      fulfill: async (out: typeof sent) => {
        sent = out;
      },
      fallback: async () => {
        throw new Error(`흉내 밖: ${method} ${path}`);
      },
    } as unknown as Route;
    await handlers.get('**/api/**')!(route);
    const bare = path.split('?')[0]!;
    const template = templateOf(bare);
    expect(template, `${method} ${bare} 가 openapi 에 없다`).toBeDefined();
    expect(sent.status, `${method} ${bare}`).toBeLessThan(300);
    const answer =
      O.paths[template!]![method.toLowerCase()]!.responses[
        String(sent.status)
      ]!;
    const schema = answer.content?.['application/json']?.schema;
    expect(schema, `${method} ${template} 성공 꼴`).toBeDefined();
    const value = JSON.parse(String(sent.body)) as unknown;
    gaps.push(...missing(value, schema!, `${method} ${template}`));
    checked.add(`${method} ${template}`);
    return value as Record<string, never>;
  };

  await call('GET', '/drafting/projects');
  await call('POST', '/drafting/projects', { year: 2026, name: '가상' });
  await call('POST', '/documents', { fileName: '가상.pdf', sizeBytes: 4 });
  await handlers.get('**/fake-upload/*')!({
    request: () => ({
      url: () => 'http://fake.test/fake-upload/101',
      method: () => 'PUT',
      postDataBuffer: () => PDF,
      headers: () => ({}),
    }),
    fulfill: async () => {},
  } as unknown as Route);
  await call('POST', '/documents/101/confirm');
  await call('GET', '/documents/101');
  await call('PUT', '/drafting/projects/1/document', { documentId: 101 });
  await call('PUT', '/drafting/projects/1/outline', {
    nodes: [
      { key: 'a', parentKey: null, depth: 1, title: '가상', requirement: '' },
    ],
  });
  await call(
    'POST',
    '/runs',
    { module: 'drafting', launchKey: 'made-up', options: { projectId: 1 } },
    { 'idempotency-key': 'made-up-key' },
  );
  // 끝날 때까지 읽되, 걸음마다 목록·실행 목록의 latestRun·progress 꼴도 본다.
  let run = await call('GET', '/runs/301');
  for (let left = 12; left > 0 && String(run.status) !== 'done'; left -= 1) {
    await call('GET', '/drafting/projects');
    await call('GET', '/drafting/projects/1/runs');
    run = await call('GET', '/runs/301');
  }
  expect(String(run.status)).toBe('done');
  await call('GET', '/drafting/projects/1');
  await call('GET', '/drafting/projects/1/runs');
  await call('GET', '/drafting/runs/301/result');
  await call('GET', '/drafting/projects/1/outline/changes?baseRunId=301');

  expect(gaps).toEqual([]);
  expect(api.of('GET /runs/301').length).toBeGreaterThan(1);
  expect(checked.size).toBe(13);
});

for (const kind of ['service', 'admin'] as const) {
  test(`S7c: ${kind} — 다른 모듈 메뉴 「보고서 작성」 → RP-01 · current · 인사말`, async ({
    page,
  }) => {
    const unrouted = await trapUnrouted(page);
    // 나중에 건 route 가 먼저 받는다 — 원고작성 흉내가 제 경로만 받고 나머지는 중대성평가 흉내로 넘긴다.
    await fakeMaterialityApi(page);
    const api = await fakeDraftingApi(page);
    await signIn(
      page,
      kind === 'admin' ? { kind, username: 'ops.admin' } : { kind },
    );
    const [projectId] = api.seed(PDF);
    await page.goto('/materiality');
    const nav = page.getByRole('navigation', {
      name: IR_TEXT.shell.menuLabel,
    });
    await nav
      .getByRole('button', { name: IR_TEXT.shell.menu.drafting })
      .click();
    await expect(page).toHaveURL(/\/drafting$/);
    await expect(page.locator('[data-screen="drafting-list"]')).toBeAttached();
    await expect(page.getByText('가상 보고서')).toBeVisible();
    await expect(nav.locator('[aria-current="page"]')).toHaveText(
      DR_TEXT.shell.menu.drafting,
    );
    await expect(nav.locator('[aria-disabled="true"]')).toHaveCount(1);
    if (kind === 'admin') {
      await expect(page.getByText(DR_TEXT.shell.adminGreeting)).toBeVisible();
      await expect(
        page.getByRole('button', { name: DR_TEXT.shell.toAdmin }),
      ).toBeVisible();
    } else {
      await expect(page.getByText(DR_TEXT.shell.greeting)).toBeVisible();
      await expect(
        page.getByRole('button', { name: DR_TEXT.shell.toAdmin }),
      ).toHaveCount(0);
    }
    expect(api.of('GET /drafting/projects')).toHaveLength(1);
    expect(projectId).toBeGreaterThan(0);
    expect(unrouted).toEqual([]);
  });
}

test('S7g: 트리 잎 제목 두 줄까지 · 점은 첫 줄 높이 — 결과·목차 설정 둘 다(RPW3 D2)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { api } = await open(page);
  const [projectId, runId] = api.seed(PDF);
  const long = '가상 기후 변화 대응 전략과 감축 목표 이행 점검 '
    .repeat(4)
    .trim();
  await page.goto(`/drafting/projects/${projectId}/outline`);
  await page.locator('[data-key="a1"]').click();
  await name(page, long);
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  const measure = (row: Locator) =>
    row.getByTestId('tree-title').evaluate((title) => {
      const line = parseFloat(getComputedStyle(title).lineHeight);
      const mark = title
        .querySelector('[data-testid="tree-marks"]')!
        .getBoundingClientRect();
      const box = title.getBoundingClientRect();
      return {
        line,
        height: box.height,
        cut: title.scrollHeight > title.clientHeight,
        markFromTop: mark.top + mark.height / 2 - box.top,
      };
    });
  for (const row of [
    page.getByTestId('outline-tree').locator('[data-key="a1"]'),
    null,
  ]) {
    if (row === null)
      await page.goto(`/drafting/projects/${projectId}/runs/${runId}`);
    const at =
      row ?? page.getByTestId('result-tree').locator('[data-key="a1"]');
    await expect(at.getByTestId('tree-title')).toHaveAttribute('title', long);
    const got = await measure(at);
    expect(got.height).toBeGreaterThan(got.line * 1.5);
    expect(got.height).toBeLessThanOrEqual(got.line * 2 + 1);
    expect(got.cut).toBe(true);
    expect(got.markFromTop).toBeLessThan(got.line * 0.75);
  }
});

test('S7h: 「바뀜」 잎 둘째 줄은 알약 아래로 흐른다 — 1440·1280(RPW4 E1)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { api } = await open(page);
  const [projectId, runId] = api.seed(PDF);
  await page.goto(`/drafting/projects/${projectId}/outline`);
  await page.locator('[data-key="a1"]').click();
  for (const title of ['가상 셋째', '감축 목표와 이행']) {
    await page.getByRole('button', { name: outline.addChild }).click();
    await name(page, title);
  }
  await page.getByRole('button', { name: outline.save }).click();
  await expect(page.getByTestId('outline-dirty')).toHaveCount(0);
  await page.goto(`/drafting/projects/${projectId}/runs/${runId}`);
  const tree = page.getByTestId('result-tree');
  const row = tree.locator('[data-mark]', { hasText: '감축 목표와 이행' });
  await expect(row.getByTestId('changed-mark')).toBeVisible();
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 1000 });
    if (width === 1280) {
      const open = page.getByRole('button', { name: result.treeOpen });
      if (await open.count()) await open.click();
    }
    await expect(row.getByTestId('tree-title-text')).toBeVisible();
    const got = await row.getByTestId('tree-title').evaluate((title) => {
      const text = title.querySelector('[data-testid="tree-title-text"]')!;
      const range = document.createRange();
      range.selectNodeContents(text);
      const lines = [...range.getClientRects()];
      const marks = title
        .querySelector('[data-testid="tree-marks"]')!
        .getBoundingClientRect();
      const beside = lines.filter((one) => one.top < marks.bottom - 1);
      return {
        cut: title.scrollHeight > title.clientHeight,
        height: title.getBoundingClientRect().height,
        line: parseFloat(getComputedStyle(title).lineHeight),
        besideRight: Math.max(0, ...beside.map((one) => one.right)),
        marksLeft: marks.left,
        marksHeight: marks.height,
      };
    });
    expect(got.cut, `${width} 잘림`).toBe(false);
    expect(got.height).toBeLessThanOrEqual(got.line * 2 + 1);
    // 알약은 첫 줄 높이만 먹는다 — 그 옆 글은 알약 왼쪽에서 끝나고, 아래 줄은 칸 폭을 다 쓴다.
    expect(got.besideRight).toBeLessThanOrEqual(got.marksLeft);
    expect(got.marksHeight).toBeLessThanOrEqual(got.line + 1);
  }
});

test('S7i: 실행 중 머리 = 결과 머리 — 실행 고르기 y 같음(RPW4 E2)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { api } = await open(page);
  const [projectId, runId] = api.seed(PDF);
  const picker = page.getByRole('button', { name: DR_TEXT.run.picker });
  await page.goto(`/drafting/projects/${projectId}/runs/${runId}`);
  await expect(page.getByTestId('run-result')).toBeVisible();
  await expect(picker).toBeVisible();
  const done = (await picker.boundingBox())!.y;
  const stuck = 900;
  api.runs.set(stuck, {
    ...structuredClone(api.runs.get(runId)!),
    id: stuck,
    tick: 0,
    status: 'processing',
  });
  await page.goto(`/drafting/projects/${projectId}/runs/${stuck}`);
  await expect(page.getByTestId('run-progress')).toBeVisible();
  await expect(page.getByTestId('run-subtitle')).toContainText(
    'made_up_report.pdf',
  );
  await expect(picker).toBeVisible();
  expect((await picker.boundingBox())!.y).toBe(done);
});

// 밴드 RPW6(sid:MARC-ENT-530): RP-01 머리 「작성 안내」 → RP-00 → [시작하기] → RP-02 새 프로젝트. 안내를 그리는 동안 원고작성 요청 0,
//   흉내 밖 /api/ 덫 0. RPW1_SHOTS 가 있으면 RP-00 을 1280·1440 으로 한 장씩(디자인 대조용).
test('S7j: RP-01 「작성 안내」 → RP-00 → 시작하기 → 새 프로젝트(RPW6)', async ({
  page,
}) => {
  const { unrouted, api } = await open(page);
  await page.goto('/drafting');
  await expect(page.getByText(DR_TEXT.list.empty)).toBeVisible();
  const before = api.calls.length;
  await page.getByRole('link', { name: DR_TEXT.list.introLink }).click();
  await expect(page).toHaveURL(/\/drafting\/intro$/);
  const intro = page.locator('[data-screen="drafting-intro"]');
  await expect(
    intro.getByRole('heading', { level: 3, name: DR_TEXT.intro.heading }),
  ).toBeVisible();
  await expect(
    intro.getByRole('list', { name: DR_TEXT.intro.flowTitle }).locator('li'),
  ).toHaveCount(3);
  await expect(page.locator('nav [aria-current="page"]')).toHaveText(
    DR_TEXT.shell.menu.drafting,
  );
  expect(api.calls.slice(before)).toEqual([]);
  if (OUT)
    for (const width of [1280, 1440]) {
      await page.setViewportSize({ width, height: 1560 });
      await page.screenshot({
        path: `${OUT}/RP-00-${width}.png`,
        fullPage: true,
      });
    }
  await page.getByRole('button', { name: DR_TEXT.intro.start }).click();
  await expect(page).toHaveURL(/\/drafting\/new$/);
  await expect(page.locator('[data-screen="drafting-new"]')).toBeVisible();
  expect(unrouted).toEqual([]);
});

test('S7k: RP-04 트리 점 눈꼴 셋 — 완성 채움 · 근거 빈 문장·자료 없음·실패·아직은 같은 빈 원 · 주황·빨강 점 0(RPW12)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { api, unrouted } = await open(page);
  const leaf = (key: string) => ({
    key,
    parentKey: 'a',
    depth: 2,
    title: `가상 잎 ${key}`,
    requirement: '',
  });
  const [projectId, runId] = api.seed(PDF, [
    { key: 'a', parentKey: null, depth: 1, title: '가상 대', requirement: '' },
    ...['a1', 'a2', 'a3', 'a4', 'a5'].map(leaf),
  ]);
  // 흉내 결과(a1 근거 · 나머지 unsupported)를 이 시험에서만 고친다: a3 자료 없음 · a4 실패 · a5 결과에 없음(아직).
  // 흉내 서버를 고치지 않으려고 원래 답은 표식 머리를 단 같은 요청으로 다시 받는다(표식이 있으면 흉내로 넘김).
  const PASS = 'x-rpw12-pass';
  await page.route(
    /\/api\/drafting\/runs\/\d+\/result$/,
    async (route: Route) => {
      if (route.request().headers()[PASS]) return route.fallback();
      const url = route.request().url();
      const body = await page.evaluate(
        async ([target, pass]) =>
          (await fetch(target!, { headers: { [pass!]: '1' } })).json(),
        [url, PASS],
      );
      body.leaves = body.leaves
        .filter((one: { key: string }) => one.key !== 'a5')
        .map((one: { key: string; outcome: unknown }) =>
          one.key === 'a3' ? { ...one, outcome: { status: 'no_material' } }
          : one.key === 'a4' ?
            {
              ...one,
              outcome: {
                status: 'failed',
                failure: { kind: 'made_up', message: '지어낸 실패' },
              },
            }
          : one,
        );
      return route.fulfill({ status: 200, json: body });
    },
  );
  await page.goto(`/drafting/projects/${projectId}/runs/${runId}`);
  const tree = page.getByTestId('result-tree');
  await expect(tree.locator('[data-key="a5"]')).toBeVisible();
  const look = async (key: string) => {
    const row = tree.locator(`[data-key="${key}"]`);
    return {
      dot: await row.getAttribute('data-dot'),
      ...(await row.getByTestId('tree-dot').evaluate((dot) => {
        const style = getComputedStyle(dot);
        return {
          bg: style.backgroundColor,
          border: style.borderTopWidth,
          className: dot.className,
        };
      })),
    };
  };
  const [done, ...rest] = await Promise.all(
    ['a1', 'a2', 'a3', 'a4', 'a5'].map((key) => look(key)),
  );
  expect([done!, ...rest].map((one) => one.dot)).toEqual([
    'done',
    'unsupported',
    'no_material',
    'failed',
    'not_run',
  ]);
  expect(new Set(rest.map((one) => `${one.bg}|${one.border}`))).toEqual(
    new Set(['rgba(0, 0, 0, 0)|1px']),
  );
  expect(done!.bg).not.toBe('rgba(0, 0, 0, 0)');
  for (const one of [done!, ...rest])
    expect(one.className).not.toMatch(/support-(orange|error)/);
  if (OUT) await tree.screenshot({ path: `${OUT}/rp04-tree-dots.png` });
  expect(unrouted).toEqual([]);
});
