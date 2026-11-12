// e2e 의 영문번역 PDF 흉내 서버(밴드 TRW6 ② — e2e/translation-server.ts 꼴을 옮겨 적음, 그 파일은 0줄). 답의 값은 전부 지어낸 것이다.
// 꼴의 정본은 band-handoffs/TRS3-order.md §1(바꾸지 않는다). 포트는 쥐지 않는다 — playwright.config.ts 의 미리보기 서버에 붙는 page.route 뿐이다.
//   - 경로(②): POST /api/documents · 서명 올리기 /fake-upload/<id> · POST /api/documents/{id}/confirm(document.pageCount·hasText — core pdf probe 흉내:
//     올린 바이트의 `/Type /Page` 수, hasText 는 늘 true) · POST /api/runs(본문 그대로 적음) · GET /api/translation/batches(빈 목록) ·
//     POST /api/translation/glossary/read. GET /translation/documents/{id}/pages 는 부르면 안 된다(W4 — 부르면 calls 에 남아 시험이 0 을 단언).
//   - PDF 보기(③): 끝난 PDF 실행 하나(`done` 옵션 — 실행 30 · 문서 12)를 미리 둔다: GET /runs/{id}(flowId pdf · resultShapes 에 layout@1 · steps) ·
//     GET /translation/runs/{id}/layout(TRS3 §1-2 예 꼴 — 지어낸 글) · GET /documents/{id}(document + jobs) · GET /documents/{id}/file(PDF 바이트).
//     결과(result@1)는 답하지 않는다(404 — 붙이기는 vitest 가 본다). confirm 의 hasText 는 옵션(검증 권고 R6 — 기본 true).
//   - 묶음 길(④ S4b — TRS3 병합 뒤): POST /runs 로 만든 실행을 들고(본문 flowId 그대로, 없으면 colab), 묶음 읽기
//     GET /translation/documents/{d}/batches/{k}(TRS3 칸 inputKind·latest.flowId 포함) · 목록 GET /translation/batches(만든 묶음 전부) ·
//     GET /runs/{id} · GET /translation/runs/{id}/result(result@1) · …/layout(PDF 흐름이 끝났을 때 — layoutOf, 2쪽) · 올린 문서 GET /documents/{id}(/file).
//     새 실행은 준비 진행 중(prepare running)으로 서고, 시험이 setRun(id, 'done' | {failed: errorCode}) 으로 옮긴다(저절로 걷지 않음).
//     A·B 견주기 옵션이면 요약·결과·layout 의 문체가 A·B 둘. 검수 이슈 originalSpan 「Made-up Co.」 는 1·2쪽 BLOCK 1 둘째 번역에 붙는다(3쪽은 layout 밖 — 페이지만).
// 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다(route 는 나중 것이 이긴다).
import type { Page, Route } from '@playwright/test';

export interface TranslationPdfCall {
  method: string;
  path: string;
  body: unknown;
  idempotencyKey: string | null;
}

const NOW = '2026-10-29T10:12:00+09:00';
const PAIRS = [
  { ko: '지어낸용어', en: 'Made-up Term' },
  { ko: '가상지표', en: 'Virtual Metric' },
];

const answer = (route: Route, status: number, body?: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: body === undefined ? '' : JSON.stringify(body),
  });
const refusal = (route: Route, status: number, code: string) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields: null,
      legacyCode: code.toLowerCase(),
    },
  });

interface Doc {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  pageCount: number | null;
  /** 올린 바이트(④ — GET /documents/{id}/file). */
  bytes?: Buffer;
}
type Json = Record<string, unknown>;
/** POST /runs 로 만든 실행(④). */
interface Run {
  id: number;
  documentId: number;
  flowId: string;
  options: Json;
  launchKey: string | null;
  status: 'processing' | 'done' | 'failed';
  errorCode: string | null;
}
/** 시험이 실행을 옮기는 값: 끝남 · 실패(errorCode — no_text_layer 는 준비 단계에서). */
export type RunMove = 'done' | { failed: string };

const FINISHED = '2026-10-29T10:30:00+09:00';
const PERSON = { userId: 1, name: '지어낸-user01' };
/** 문체 하나마다 BLOCK 1 둘째 번역(검수 이슈 「Made-up Co.」 가 붙는 자리). */
const SECOND: Record<string, string> = {
  single: 'By 2030, Made-up Co. cuts',
  A: 'By 2030, Made-up Co. cuts',
  B: 'Made-up Co. will cut by 2030',
};
const ISSUE_SPAN = 'Made-up Co.';

/** 끝난 PDF 실행 30 · 문서 12 의 layout@1(TRS3 §1-2 예 꼴, 쪽 하나 — 지어낸 글). 상자 = member 셋 + 표 테두리 하나 + bbox 있는 칸 하나. */
export const PDF_RUN_ID = 30;
export const PDF_DOC_ID = 12;
export const PDF_LAYOUT_PAGE = 1;
export function pdfLayout(page = PDF_LAYOUT_PAGE) {
  return {
    schemaVersion: 'translation.layout@1',
    status: 'done',
    sourceSha256: '9'.repeat(64),
    source: {
      pdfSha256: 'a'.repeat(64),
      pageCount: 1,
      parser: { name: 'docparse', version: '0.4.0', layout: 2 },
      adapter: 'pdf_tags@1',
    },
    pages: [{ page, width: 595, height: 842, textLayer: 'present' }],
    units: [
      {
        tag: 'BLOCK 1',
        page,
        kind: 'block',
        members: [
          {
            id: `p${page}-b1`,
            key: 'k-3f9a',
            kind: 'heading',
            bbox: [72, 60, 320, 84],
            source: '기후 대응 전략',
          },
          {
            id: `p${page}-b2`,
            key: 'k-77c1',
            kind: 'paragraph',
            bbox: [72, 100, 520, 160],
            source: '지어낸 회사는 2030년까지 배출을 줄인다',
          },
        ],
      },
      {
        tag: 'TABLE 1',
        page,
        kind: 'table',
        members: [
          {
            id: `p${page}-t1`,
            key: 'k-0b21',
            kind: 'table',
            bbox: [72, 200, 520, 320],
            source: '| 구분 | 2025 |\n| --- | --- |\n| 배출량 | 1,200 |',
          },
        ],
        cells: [
          {
            row: 0,
            col: 0,
            id: `p${page}-t1:r0c0`,
            bbox: [76, 204, 200, 230],
            source: '구분',
          },
          {
            row: 0,
            col: 1,
            id: `p${page}-t1:r0c1`,
            bbox: null,
            source: '2025',
          },
        ],
        rows: [0, 1],
      },
      {
        tag: null,
        page,
        kind: 'footer',
        members: [
          {
            id: `p${page}-b9`,
            key: 'k-9e00',
            kind: 'paragraph',
            bbox: [72, 800, 520, 812],
            source: '2026 지어낸 보고서 1',
          },
        ],
      },
    ],
    variants: [
      {
        label: 'single',
        stage: 'autofix',
        units: [
          {
            tag: 'BLOCK 1',
            page,
            level: 'block',
            translations: ['Climate Strategy', 'By 2030, Made-up Co. cuts'],
          },
          {
            tag: 'TABLE 1',
            page,
            level: 'cell',
            translations: null,
            cells: [
              { row: 0, col: 0, text: 'Category' },
              { row: 0, col: 1, text: '2025' },
            ],
          },
          { tag: null, page, level: 'source_only', translations: null },
        ],
        unplaced: [],
      },
    ],
    skipped: { emptyTables: [], imageOnlyPages: [] },
    warnings: [],
  };
}

/**
 * 넓은 표 layout@1(밴드 TRW8 ② — 지어낸 글): pdfLayout 그대로에 표 TABLE 1 만 2행 × cols열(칸 맞춘 표, level cell)로.
 * 짝 칸(380) 안에서 칸 최소 폭으로 가로로 밀려야 하는 표. 칸 상자는 첫 칸만(bbox) — 나머지는 bbox null.
 */
export function wideTableLayout(cols = 14, page = PDF_LAYOUT_PAGE) {
  const base = pdfLayout(page);
  const at = base.units.findIndex((unit) => unit.tag === 'TABLE 1');
  const grid = [0, 1].flatMap((row) =>
    Array.from({ length: cols }, (_, col) => ({ row, col })),
  );
  const head = Array.from({ length: cols }, (_, col) => `지어낸 열 ${col + 1}`);
  const units = base.units.map((unit, n) =>
    n !== at ? unit : (
      {
        ...unit,
        members: [
          {
            ...unit.members[0]!,
            source: `| ${head.join(' | ')} |\n| ${head.map(() => '---').join(' | ')} |\n| ${head.map((_, col) => String(col * 100)).join(' | ')} |`,
          },
        ],
        cells: grid.map(({ row, col }) => ({
          row,
          col,
          id: `p${page}-t1:r${row}c${col}`,
          bbox: row === 0 && col === 0 ? [76, 204, 200, 230] : null,
          source: row === 0 ? head[col]! : String(col * 100),
        })),
      }
    ),
  );
  const variant = base.variants[0]!;
  return {
    ...base,
    units,
    variants: [
      {
        ...variant,
        units: variant.units.map((unit, n) =>
          n !== at ? unit : (
            {
              ...unit,
              cells: grid.map(({ row, col }) => ({
                row,
                col,
                text:
                  row === 0 ? `Made-up column ${col + 1}` : String(col * 100),
              })),
            }
          ),
        ),
      },
    ],
  };
}

/** 긴 layout 의 쪽 수(밴드 TRW7 ② — sticky·쪽 칸 스크롤·쪽 넘김을 재는 길이). */
export const LONG_PAGES = 12;

/**
 * 긴 layout@1(밴드 TRW7 ② S3 — 지어낸 글): 쪽 1~pageCount, 세로 595×842, 쪽마다 짝 열(BLOCK 1 member 넷 · pipe 표 하나 ·
 * BLOCK 2 member 셋 · 맨 아래 BLOCK 3 member 하나(검수 이슈 「Made-up Co.」 가 붙는 글 — 쪽 칸을 내려야 보이는 자리) · 꼬리말).
 * 상자 id 는 p<쪽>-b<n>(맨 아래 = b8) · 표 p<쪽>-t1.
 */
export function longLayout(pageCount = LONG_PAGES) {
  const pageNumbers = Array.from({ length: pageCount }, (_, n) => n + 1);
  const member = (page: number, n: number, top: number, source: string) => ({
    id: `p${page}-b${n}`,
    key: `k-${page}-${n}`,
    kind: n === 1 ? 'heading' : 'paragraph',
    bbox: [72, top, 520, top + 36],
    source,
  });
  const units = pageNumbers.flatMap((page) => [
    {
      tag: 'BLOCK 1',
      page,
      kind: 'block',
      members: [
        member(page, 1, 60, `지어낸 ${page}쪽 제목`),
        member(page, 2, 110, '지어낸 회사는 배출을 줄인다'),
        member(page, 3, 160, '지어낸 둘째 문단'),
        member(page, 4, 210, '지어낸 셋째 문단'),
      ],
    },
    {
      tag: 'TABLE 1',
      page,
      kind: 'table',
      members: [
        {
          id: `p${page}-t1`,
          key: `k-${page}-t1`,
          kind: 'table',
          bbox: [72, 270, 520, 380],
          source: '| 구분 | 2025 |\n| --- | --- |\n| 배출량 | 1,200 |',
        },
      ],
    },
    {
      tag: 'BLOCK 2',
      page,
      kind: 'block',
      members: [
        member(page, 5, 420, '지어낸 넷째 문단'),
        member(page, 6, 520, '지어낸 다섯째 문단'),
        member(page, 7, 620, '지어낸 여섯째 문단'),
      ],
    },
    {
      tag: 'BLOCK 3',
      page,
      kind: 'block',
      members: [member(page, 8, 730, '지어낸 회사의 아래쪽 문단')],
    },
    {
      tag: null,
      page,
      kind: 'footer',
      members: [
        {
          id: `p${page}-b9`,
          key: `k-${page}-9`,
          kind: 'paragraph',
          bbox: [72, 800, 520, 812],
          source: `2026 지어낸 보고서 ${page}`,
        },
      ],
    },
  ]);
  const variantUnits = pageNumbers.flatMap((page) => [
    {
      tag: 'BLOCK 1',
      page,
      level: 'block',
      translations: [
        `Made-up page ${page}`,
        'The made-up firm cuts emissions',
        'Second made-up paragraph',
        'Third made-up paragraph',
      ],
    },
    {
      tag: 'TABLE 1',
      page,
      level: 'table',
      translations: ['| Item | 2025 |\n| --- | --- |\n| Emissions | 1,200 |'],
    },
    {
      tag: 'BLOCK 2',
      page,
      level: 'block',
      translations: [
        'Fourth made-up paragraph',
        'Fifth made-up paragraph',
        'Sixth made-up paragraph',
      ],
    },
    {
      tag: 'BLOCK 3',
      page,
      level: 'block',
      translations: ['By 2030, Made-up Co. cuts more'],
    },
    { tag: null, page, level: 'source_only', translations: null },
  ]);
  return {
    ...pdfLayout(1),
    source: { ...pdfLayout(1).source, pageCount },
    pages: pageNumbers.map((page) => ({
      page,
      width: 595,
      height: 842,
      textLayer: 'present',
    })),
    units,
    variants: [
      {
        label: 'single',
        stage: 'translated',
        units: variantUnits,
        unplaced: [],
      },
    ],
  };
}

/** 실행 옵션의 문체 → 결과 문체 이름(견주기면 A·B, 아니면 single). */
const labelsOf = (options: Json) =>
  (options.style as { compareAb?: boolean } | undefined)?.compareAb ?
    ['A', 'B']
  : ['single'];
function pagesOf(options: Json): number[] {
  const pages = options.pages as { start: number; end: number };
  const out: number[] = [];
  for (let n = pages.start; n <= pages.end; n++) out.push(n);
  return out;
}

/** 만든 PDF 실행의 layout@1 — 쪽 1·2(pdfLayout 두 벌을 잇고 문체마다 둘째 번역만 바꿈). 원본 쪽 수는 올린 PDF 의 것. */
export function layoutOf(labels: readonly string[], pageCount: number) {
  const pages = [1, 2].map((n) => pdfLayout(n));
  const first = pages[0]!;
  return {
    ...first,
    source: { ...first.source, pageCount },
    pages: pages.flatMap((each) => each.pages),
    units: pages.flatMap((each) => each.units),
    variants: labels.map((label) => ({
      ...first.variants[0]!,
      label,
      units: pages.flatMap((each) =>
        each.variants[0]!.units.map((unit) =>
          unit.level === 'block' ?
            {
              ...unit,
              translations: ['Climate Strategy', SECOND[label]!],
            }
          : unit,
        ),
      ),
    })),
  };
}

const fileName = (kind: string, label: string) =>
  `translation-${kind}-${label}.docx`;

function digestOf(run: Run): Json {
  const pages = pagesOf(run.options);
  return {
    schemaVersion: 'translation.digest@1',
    status: 'done',
    rejectionKind: null,
    outcome: 'done',
    pageCount: pages.length,
    failedPages: [],
    variants: labelsOf(run.options).map((label) => ({
      label,
      reviewStatus: 'reviewed',
      reviewStoppedAt: null,
      parseFailedPages: 0,
      issueCount: pages.length,
      issueCounts: { high: 0, medium: 0, low: pages.length },
      glossaryMisses: 0,
      autofixStatus: 'done',
      autofixChangedPages: 1,
      files: {
        bilingual: fileName('bilingual', label),
        qa: fileName('qa', label),
        autofix: fileName('autofix', label),
      },
    })),
    warningCount: 0,
  };
}

/** result@1(e2e/translation-server.ts resultOf 꼴을 옮겨 적음 — 쪽마다 검수 이슈 하나, originalSpan 「Made-up Co.」). */
function resultOf(run: Run): Json {
  const pages = pagesOf(run.options);
  const labels = labelsOf(run.options);
  return {
    schemaVersion: 'translation.result@1',
    status: 'done',
    rejection: null,
    settings: {
      part: run.options.part,
      variants: labels,
      routes: { translate: 'light-anthropic', review: 'light-anthropic' },
      promptIds: ['translation/section@2'],
      engine: 'colab_158',
      constants: {
        editorialQaMinScore: 96,
        tableBatchSize: 24,
        polishMinChars: 120,
        polishMaxChars: 6000,
        koreanRepairRounds: 2,
        autofixKoreanRepairRounds: 1,
      },
      retry: null,
    },
    document: {
      pageNumbers: pages,
      duplicatePages: {},
      sourceSha256: '0'.repeat(64),
    },
    variants: labels.map((label) => ({
      label,
      translatedText: `[PAGE 1]\n${SECOND[label]}`,
      bilingualText: `[PAGE 1]\n${SECOND[label]}`,
      fragments: pages.map((pageNum) => ({
        pageNum,
        status: 'translated',
        error: null,
        editorialQa: null,
        remainingKorean: [],
      })),
      pages: pages.map((pageNum) => ({
        pageNum,
        translated: `[PAGE ${pageNum}]\n${SECOND[label]}`,
        bilingual: `[PAGE ${pageNum}]\n${SECOND[label]}`,
        review: {
          status: 'reviewed',
          issues: [
            {
              issueType: 'UNNATURAL',
              severity: 'LOW',
              originalSpan: ISSUE_SPAN,
              suggestion: 'Invented text',
              reason: '지어낸 까닭',
              source: 'model',
            },
          ],
          counts: { high: 0, medium: 0, low: 1 },
          message: null,
        },
      })),
      glossaryCheck: [],
      autofix: {
        status: 'done',
        pages: [],
        translatedText: '[PAGE 1]\nFixed text',
        bilingualText: '[PAGE 1]\nFixed text',
        stop: null,
        notRunReason: null,
      },
    })),
    warnings: [],
  };
}

/** 실행 단계 셋(prepare·translate·report — TRS3 §1-1 선언 차례). */
function stepsOf(run: Run) {
  return ['prepare', 'translate', 'report'].map((step, index) => ({
    step,
    status:
      run.status === 'done' ? 'done'
      : run.status === 'failed' ?
        index === failedIndex(run) ? 'failed'
        : index < failedIndex(run) ? 'done'
        : 'pending'
      : index === 0 ? 'running'
      : 'pending',
    done: null,
    total: null,
  }));
}
/** no_text_layer 는 준비 단계에서, 그 밖 실패는 번역 단계에서. */
const failedIndex = (run: Run) => (run.errorCode === 'no_text_layer' ? 0 : 1);

export interface FakeTranslationPdfOptions {
  /** confirm 의 hasText(기본 true — 검증 권고 R6 의 false 꼴). */
  hasText?: boolean | null;
  /** 만든 PDF 실행 layout 의 warnings(밴드 TRW7 ③a — 「확인할 곳」 칸). 기본 없음(빈 목록 그대로). */
  warnings?: readonly unknown[];
  /** 만든 PDF 실행의 layout 답을 이 약속이 풀릴 때까지 붙잡는다(밴드 TRW8 ⑧ — 요약 「확인할 곳」 읽는 동안). 기본 바로 답함. */
  layoutHold?: Promise<unknown>;
  /** 끝난 PDF 실행 30(문서 12)을 미리 둔다 — 원본 PDF 바이트와 layout. */
  done?: {
    pdf: Uint8Array;
    layout?: unknown;
    /** 결과(result@1 — 쪽마다 검수 이슈 하나)도 준다(밴드 TRW7 ① — 짝 칸 밑줄). 없으면 결과 404 그대로. */
    result?: boolean;
    /** 실행의 쪽 수(옵션 pages 1~n — 결과의 쪽마다 이슈도). 기본 1(밴드 TRW7 ② 긴 layout 은 LONG_PAGES). */
    pages?: number;
  };
}

/** 끝난 PDF 실행 30 의 옵션(GET /runs/30 · 결과가 같은 것을 본다). */
const DONE_OPTIONS = {
  batchId: 'b-1',
  part: 'story',
  style: { compareAb: false, single: 'B' },
  pages: { start: 1, end: 1 },
};

export async function fakeTranslationPdfApi(
  page: Page,
  {
    hasText = true,
    done,
    warnings,
    layoutHold,
  }: FakeTranslationPdfOptions = {},
) {
  // 쪽 수를 준 끝난 실행이면 옵션 pages 1~n(결과의 쪽마다 이슈) — 기본은 DONE_OPTIONS 그대로.
  const doneOptions =
    done?.pages === undefined ?
      DONE_OPTIONS
    : { ...DONE_OPTIONS, pages: { start: 1, end: done.pages } };
  const calls: TranslationPdfCall[] = [];
  const docs = new Map<number, Doc>();
  let docSeq = 12;
  let runSeq = 20;
  const runs = new Map<number, Run>();

  const keyOf = (run: Run) => String(run.options.batchId);
  const order = ['ceo_message', 'story', 'general'];
  const isPdf = (run: Run) => run.flowId.startsWith('translation.pdf@');
  const batchOf = (documentId: number, key: string) => {
    const list = [...runs.values()].filter(
      (run) => run.documentId === documentId && keyOf(run) === key,
    );
    const doc = docs.get(documentId);
    if (list.length === 0 || doc === undefined) return null;
    const newest = [...list].sort((a, b) => b.id - a.id);
    const parts = order.flatMap((part) => {
      const rounds = newest.filter((run) => run.options.part === part);
      if (rounds.length === 0) return [];
      const [run, ...earlier] = rounds as [Run, ...Run[]];
      const pages = run.options.pages as { start: number; end: number };
      const glossary = (run.options.glossary ?? {}) as {
        base?: unknown[];
        final?: unknown[];
      };
      const ended = run.status !== 'processing';
      return [
        {
          part,
          latest: {
            runId: run.id,
            flowId: run.flowId,
            status: run.status,
            pages: { start: pages.start, end: pages.end },
            style: run.options.style,
            glossaryCounts: {
              base: glossary.base?.length ?? 0,
              final: glossary.final?.length ?? 0,
            },
            createdAt: NOW,
            startedAt: NOW,
            finishedAt: ended ? FINISHED : null,
            failedStep:
              run.status === 'failed' ?
                ['prepare', 'translate', 'report'][failedIndex(run)]!
              : null,
            errorCode: run.status === 'failed' ? run.errorCode : null,
            steps: stepsOf(run),
            digest: run.status === 'done' ? digestOf(run) : null,
          },
          earlier: earlier.map((old) => ({
            runId: old.id,
            status: old.status,
            createdAt: NOW,
            finishedAt: FINISHED,
            outcome: old.status === 'done' ? 'done' : null,
          })),
          round: rounds.length,
        },
      ];
    });
    const latest = parts.map((p) => p.latest);
    return {
      batchKey: key,
      inputKind: isPdf(newest[0]!) ? 'pdf' : 'word',
      document: {
        id: doc.id,
        fileName: doc.fileName,
        uploadedAt: NOW,
        uploadedBy: PERSON,
      },
      createdBy: PERSON,
      parts,
      state:
        latest.some((run) => run.status === 'processing') ? 'active'
        : latest.some((run) => run.status === 'failed') ? 'failed'
        : 'done',
      doneParts: latest.filter((run) => run.status === 'done').length,
      partCount: latest.length,
    };
  };
  const batches = () => {
    const seen = new Map<
      string,
      { top: number; documentId: number; key: string }
    >();
    for (const run of runs.values()) {
      const id = `${run.documentId}/${keyOf(run)}`;
      const at = seen.get(id);
      if (at === undefined || run.id > at.top)
        seen.set(id, {
          top: run.id,
          documentId: run.documentId,
          key: keyOf(run),
        });
    }
    return [...seen.values()]
      .sort((a, b) => b.top - a.top)
      .map((each) => batchOf(each.documentId, each.key)!);
  };
  const runInfo = (run: Run) => ({
    id: run.id,
    module: 'translation',
    flowId: run.flowId,
    documentId: run.documentId,
    options: run.options,
    status: run.status,
    errorCode: run.status === 'failed' ? run.errorCode : null,
    errorMessage: run.status === 'failed' ? '지어낸 실패 글' : null,
    failedStep: null,
    files: [],
    steps: stepsOf(run),
    resultShapes:
      run.status !== 'done' ? []
      : isPdf(run) ?
        ['translation.result@1', 'translation.digest@1', 'translation.layout@1']
      : ['translation.result@1', 'translation.digest@1'],
    createdAt: NOW,
    startedAt: NOW,
    finishedAt: run.status === 'processing' ? null : FINISHED,
  });

  await page.route('**/fake-upload/*', async (route) => {
    const id = Number(new URL(route.request().url()).pathname.split('/').pop());
    const doc = docs.get(id);
    if (doc) {
      doc.uploaded = true;
      doc.bytes = route.request().postDataBuffer() ?? Buffer.alloc(0);
      const text = doc.bytes.toString('latin1');
      const pages = text.match(/\/Type \/Page(?!s)/g)?.length ?? 0;
      doc.pageCount = pages > 0 ? pages : null;
    }
    calls.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: undefined,
      idempotencyKey: null,
    });
    return route.fulfill({ status: 200, body: '' });
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
    const method = request.method();
    let body: unknown;
    try {
      body = request.postData() ? request.postDataJSON() : undefined;
    } catch {
      body = undefined;
    }
    calls.push({
      method,
      path,
      body,
      idempotencyKey: request.headers()['idempotency-key'] ?? null,
    });
    const key = `${method} ${path}`;
    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = body as {
        fileName: string;
        sizeBytes: number;
      };
      const doc: Doc = {
        id: docSeq++,
        fileName,
        sizeBytes,
        uploaded: false,
        pageCount: null,
      };
      docs.set(doc.id, doc);
      return answer(route, 201, {
        document: {
          id: doc.id,
          fileName,
          sizeBytes,
          status: 'awaiting_upload',
          pageCount: null,
          hasText: null,
          uploadedAt: null,
        },
        upload: {
          url: `${url.origin}/fake-upload/${doc.id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    const match = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (match && method === 'POST') {
      const doc = docs.get(Number(match[1]));
      if (!doc) return refusal(route, 404, 'NOT_FOUND');
      if (!doc.uploaded) return refusal(route, 409, 'NOT_UPLOADED');
      return answer(route, 200, {
        document: {
          id: doc.id,
          fileName: doc.fileName,
          sizeBytes: doc.sizeBytes,
          status: 'uploaded',
          pageCount: doc.pageCount,
          hasText,
          uploadedAt: NOW,
        },
      });
    }
    if (key === 'POST /runs') {
      const sent = body as {
        flowId?: string;
        documentId: number;
        launchKey?: string;
        options: Json;
      };
      const run: Run = {
        id: runSeq++,
        documentId: sent.documentId,
        flowId: sent.flowId ?? 'translation.colab@158',
        options: sent.options,
        launchKey: sent.launchKey ?? null,
        status: 'processing',
        errorCode: null,
      };
      runs.set(run.id, run);
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    if (method === 'GET') {
      const batch = /^\/translation\/documents\/(\d+)\/batches\/([^/]+)$/.exec(
        path,
      );
      if (batch) {
        const found = batchOf(Number(batch[1]), decodeURIComponent(batch[2]!));
        return found === null ?
            refusal(route, 404, 'NOT_FOUND')
          : answer(route, 200, { ...found, truncated: false });
      }
      const runPath =
        /^\/(?:translation\/)?runs\/(\d+)(?:\/(result|layout))?$/.exec(path);
      const run = runPath ? runs.get(Number(runPath[1])) : undefined;
      if (runPath && run !== undefined) {
        const tail = runPath[2];
        if (tail === undefined && !path.startsWith('/translation/'))
          return answer(route, 200, runInfo(run));
        if (run.status !== 'done') return refusal(route, 409, 'RUN_NOT_DONE');
        if (tail === 'result') return answer(route, 200, resultOf(run));
        if (tail === 'layout' && isPdf(run)) {
          if (layoutHold !== undefined) await layoutHold;
          return answer(route, 200, {
            ...layoutOf(
              labelsOf(run.options),
              docs.get(run.documentId)?.pageCount ?? 1,
            ),
            ...(warnings === undefined ? {} : { warnings }),
          });
        }
        return refusal(route, 404, 'NOT_FOUND');
      }
      const docPath = /^\/documents\/(\d+)(\/file)?$/.exec(path);
      const doc = docPath ? docs.get(Number(docPath[1])) : undefined;
      if (docPath && doc?.bytes !== undefined) {
        if (docPath[2] === '/file')
          return route.fulfill({
            status: 200,
            contentType: 'application/pdf',
            headers: {
              'Content-Disposition': `attachment; filename="${doc.fileName}"`,
            },
            body: doc.bytes,
          });
        return answer(route, 200, {
          document: {
            id: doc.id,
            fileName: doc.fileName,
            sizeBytes: doc.sizeBytes,
            status: 'uploaded',
            pageCount: doc.pageCount,
            hasText,
            uploadedAt: NOW,
          },
          jobs: [],
        });
      }
    }
    if (done !== undefined && method === 'GET') {
      if (path === `/runs/${PDF_RUN_ID}`)
        return answer(route, 200, {
          id: PDF_RUN_ID,
          module: 'translation',
          flowId: 'translation.pdf@158',
          documentId: PDF_DOC_ID,
          options: doneOptions,
          status: 'done',
          errorCode: null,
          errorMessage: null,
          failedStep: null,
          files: [],
          steps: ['prepare', 'translate', 'report'].map((step) => ({
            step,
            status: 'done',
            done: null,
            total: null,
          })),
          resultShapes: [
            'translation.result@1',
            'translation.digest@1',
            'translation.layout@1',
          ],
          createdAt: NOW,
          startedAt: NOW,
          finishedAt: NOW,
        });
      if (path === `/translation/runs/${PDF_RUN_ID}/layout`)
        return answer(route, 200, done.layout ?? pdfLayout());
      if (
        done.result === true &&
        path === `/translation/runs/${PDF_RUN_ID}/result`
      )
        return answer(
          route,
          200,
          resultOf({
            id: PDF_RUN_ID,
            documentId: PDF_DOC_ID,
            flowId: 'translation.pdf@158',
            options: doneOptions,
            launchKey: null,
            status: 'done',
            errorCode: null,
          }),
        );
      if (path === `/documents/${PDF_DOC_ID}`)
        return answer(route, 200, {
          document: {
            id: PDF_DOC_ID,
            fileName: 'made_up.pdf',
            sizeBytes: done.pdf.length,
            status: 'uploaded',
            pageCount: done.pages ?? 1,
            hasText: true,
            uploadedAt: NOW,
          },
          jobs: [],
        });
      if (path === `/documents/${PDF_DOC_ID}/file`)
        return route.fulfill({
          status: 200,
          contentType: 'application/pdf',
          headers: {
            'Content-Disposition': 'attachment; filename="made_up.pdf"',
          },
          body: Buffer.from(done.pdf),
        });
    }
    if (key === 'GET /translation/batches') {
      const results = batches();
      return answer(route, 200, {
        companyName: '지어낸 회사',
        count: results.length,
        isNext: false,
        truncated: false,
        results,
      });
    }
    if (key === 'POST /translation/glossary/read')
      return answer(route, 200, {
        ok: true,
        pairs: PAIRS,
        rowCount: PAIRS.length,
      });
    return refusal(route, 404, 'NOT_FOUND');
  });

  const keys = () => calls.map((call) => `${call.method} ${call.path}`);
  const runCalls = () =>
    calls.filter((call) => call.method === 'POST' && call.path === '/runs');
  /** 만든 실행을 옮긴다(④ — 다음 묶음 읽기부터 보임). */
  const setRun = (id: number, move: RunMove) => {
    const run = runs.get(id);
    if (run === undefined) throw new Error(`no run ${id}`);
    if (move === 'done') {
      run.status = 'done';
      run.errorCode = null;
    } else {
      run.status = 'failed';
      run.errorCode = move.failed;
    }
  };
  return { calls, keys, runCalls, runs, setRun };
}
