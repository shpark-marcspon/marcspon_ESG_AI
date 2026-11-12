// e2e 의 온실가스 Scope 3 흉내 서버(밴드 S3W1 ③ — e2e/translation-server.ts 꼴, 테스트 6d 알림 H3). 빌드한 웹의 실어댑터가 부르는 경로를
// page.route 로 채운다. 답의 값은 전부 지어낸 것이다(실재 기업명 0 · 받은 템플릿 0 — 양식 바이트는 「PK」 머리만). 포트는 쥐지 않는다.
// 꼴은 entities/ghg-scope3/api/testing.ts 의 가짜와 같은 규칙이다(e2e 는 웹 코드에서 문구 표만 들인다 — app/guards/layers.test.ts):
//   - 경로: POST /api/documents · POST /api/documents/{id}/confirm · POST /api/runs · GET /api/runs?module= · GET /api/runs/{id} ·
//     GET /api/inventory/scope3/template · GET /api/inventory/scope3/runs/{id}/result(S3W2a — done 이 아니면 409 run_not_done, 결과 null 이면
//     404 not_found, 그 밖 200 결과 본문 — 실행마다 runResults, 기본 e2eDoneResult()). 서명 올리기는 같은 출처 /fake-upload-s3/<문서 id>.
//     GET /api/inventory/scope3/runs/{id}/original(S3Q1 — 그 실행 문서에 PUT 한 바이트 그대로 · 실행 상태 안 봄 · 없음·안 올라옴 404 ·
//     Content-Type 은 올린 이름 끝(.xlsx·.xls·그 밖 octet-stream — openapi content 셋) · Content-Disposition 은 서버 content_disposition_header 꼴).
//   - RunOut 은 openapi 열여섯 칸 그대로(S3W2a). 실패 errorCode 는 실행마다 runErrors(기본 internal) — 단계 code 면 failedStep c1.
//     결과 본문·RunOut 의 칸은 spec 의 「흉내 ↔ openapi」 시험이 generated/openapi.json 과 걸어 내려가며 견준다.
//   - server 's3k1'(기본): options.reportYear 가 정수·1990~올해가 아니면 400 INVALID_OPTIONS · 운영 관리자 실행 열림 · 양식 200 xlsx 바이트.
//     server 'base': POST /runs 운영 관리자 403 FORBIDDEN(먼저) · 그 밖 422 FLOW_NOT_RUNNABLE · 양식 404.
//   - 문서 sizeBytes 가 20MB 를 넘으면 413 upload_too_large · 올리지 않은 문서 확인 409 · module·flowId 가 아니면 422 UNKNOWN_FLOW ·
//     resumeFromRunId 를 실으면 422 VALIDATION_ERROR(화면은 이어 돌기를 쓰지 않는다).
//   - 실행은 대본(runScripts — 만든 차례마다 하나, 기본 processing → done)을 GET /runs/{id} 한 번마다 한 칸씩 걷는다(끝 칸에 머문다).
//     목록은 새 것 먼저, 요약에 연도·options 칸은 없다(서버 그대로).
//   - 지금 결과(S3W3a ①): GET …/years/{y} · …/runs/{id}/edits·history · POST·DELETE …/lock · POST …/exclusions·restorations·factors 는 createScope3Ledger 가 답한다.
//     서버 규칙 그대로(기준 실행 = 새 것부터 첫 「done + 결과 done」, 잠기면 핀, 판정 차례, 합은 Decimal 정확합 글자). 연도 답은 판·실행 유무와 상관없다.
//     runEdits(만든 차례마다 사건)로 고친 줄을 둔다. 답의 칸은 spec 의 「흉내 ↔ openapi」 가 걷는다.
// 이 흉내는 위 경로만 받는다 — 그 밖 /api/ 는 다음 route(spec 의 덫 503)로 넘긴다. 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다.
import type { Page, Route } from '@playwright/test';

export interface Scope3Call {
  method: string;
  path: string;
  search: string;
  body: unknown;
  authorization: string | null;
  size: number;
}

type Json = Record<string, unknown>;
type Status = 'queued' | 'processing' | 'done' | 'failed';

export interface Scope3ApiOptions {
  server?: 's3k1' | 'base';
  operator?: boolean;
  runScripts?: Status[][];
  /** 만든 차례마다 실패 errorCode(기본 internal). */
  runErrors?: string[];
  /** 만든 차례마다 결과 본문(null 이면 404, 기본 e2eDoneResult()). */
  runResults?: unknown[];
  /** 만든 차례마다 미리 둔 사건(S3W3a). */
  runEdits?: E2eRowEdit[][];
}

/** 미리 둔 줄 사건 하나. excluded 면 제외 사건, factor 면 계수 사건. */
export interface E2eRowEdit {
  rowId: string;
  category: string;
  excluded?: boolean;
  factor?: Json;
  by?: Json | null;
}

interface Doc {
  id: number;
  fileName: string;
  sizeBytes: number;
  uploaded: boolean;
  /** PUT 한 바이트(S3Q1 원본 경로가 그대로 낸다). */
  bytes?: Buffer;
}
interface Run {
  id: number;
  documentId: number;
  flowId: string;
  options: Json;
  script: Status[];
  at: number;
  errorCode: string;
  result: unknown;
}

const NOW = '2026-10-30T09:00:00+09:00';
const LIMIT = 20 * 1024 * 1024;
/** 지어낸 양식 바이트(「PK」 머리만 — 실제 엑셀이 아니다). */
export const TEMPLATE_BYTES = Buffer.from([80, 75, 3, 4, 7, 7]);
export const TEMPLATE_NAME = 'scope3-template-sample.xlsx';

/** 원본 경로의 꼴(S3Q1 — 서버 ORIGINAL_MEDIA_TYPES 거울). */
export const originalMediaType = (fileName: string) => {
  const dot = fileName.lastIndexOf('.');
  const tail = dot < 0 ? '' : fileName.slice(dot).toLowerCase();
  return (
    tail === '.xlsx' ?
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    : tail === '.xls' ? 'application/vnd.ms-excel'
    : 'application/octet-stream'
  );
};
/** 서버 content_disposition_header 거울(RFC 6266): ASCII 이름은 filename="…", 아니면 filename*=utf-8''<퍼센트>. */
export const attachmentOf = (fileName: string) =>
  /^[\x20-\x7e]*$/.test(fileName) ?
    `attachment; filename="${fileName.replace(/[\\"]/g, '\\$&')}"`
  : `attachment; filename*=utf-8''${encodeURIComponent(fileName)}`;

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
const refusal = (route: Route, status: number, code: string) =>
  answer(route, status, {
    error: { code, message: `지어낸-${code}`, fields: null },
  });
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);
/** 서울 올해. */
const seoulYear = () =>
  new Date(Date.now() + 9 * 60 * 60 * 1000).getUTCFullYear();
const OWNED = /^\/(documents|runs|inventory\/scope3)(\/|$)/;
/** 단계가 실패한 errorCode(failedStep 이 그 단계 — 흉내는 c1). 그 밖은 실행기 code(failedStep null). */
const STEP_CODES = [
  'options_rejected',
  'flow_input_invalid',
  'step_output_invalid',
  'embedding_failed',
  'no_text_layer',
  'setup_error',
  'step_error',
];
/** 흉내 실패 글(화면에 나오면 안 된다). */
export const E2E_ERROR_MESSAGE = '흉내-서버-실패-글';
export const E2E_SHEET_ERROR = 'ValueError: 흉내-시트-오류-글';
export const E2E_REJECT_DETAIL = 'reader 흉내-거절-까닭-글';

// ── 결과 본문(scope3.colab.result@1) — 값은 지어낸 것. 칸은 generated/openapi.json 과 같다(spec 의 대조 시험). ──
const step = (name: string, origin = 'ai'): Json => ({
  origin,
  step: name,
  via: '흉내',
});
/** 그룹 단계 갈래(밴드 S3W4 ① — 상세 C1 첫 줄 ai · 둘째 줄 rule(계수 단계는 ai) · 셋째 줄 estimate). */
const GROUP_STEPS: readonly Json[][] = [
  [step('group')],
  [step('group', 'rule'), step('factor')],
  [step('group', 'estimate'), step('factor', 'rule')],
];
const AMOUNT: Json = {
  value: '1',
  unit: 'kg',
  baseValue: '1',
  baseUnit: 'kg',
  note: null,
};
const FACTOR: Json = {
  title: '흉내 계수',
  value: '0.5',
  unit: 'kgCO2e/kg',
  column: '흉내 열',
  sheet: '흉내 시트',
  code: 'Y1',
};
/** 줄의 입력 칸(S3R2 — openapi ColabRowInputJson 의 키 열여섯(S3R3 useMonths), 값은 글이거나 null). */
const INPUT: Json = {
  country: '흉내 나라',
  site: '흉내 사업장',
  name: '흉내 품목',
  vehicle: null,
  energy: '흉내 에너지',
  people: null,
  buildingArea: null,
  usedArea: null,
  buildingPeople: '40.0',
  ownPeople: '4.0',
  productCount: null,
  sales: '12.0',
  weight: null,
  weightUnit: null,
  stores: '2.0',
  useMonths: '60.0',
};
const bio = (biogenic: string | null): Json => ({
  fossilCo2e: '1',
  biogenicCo2e: biogenic,
  fcf: '0.2',
  note: '흉내',
});
const purchase = (co2e: string | null): Json => ({
  rowId: 'p',
  kind: 'purchase',
  month: 1,
  amount: '10',
  spendKrw: '10',
  spendNote: '흉내',
  co2e,
  unit: 'tCO2eq',
  formula: '흉내 식',
  factor: {
    title: '흉내 항목',
    value: '0.1',
    unit: 'kgCO2e/KRW',
    column: '2024',
    source: 'db_keyword',
  },
  group: {
    key: 'g',
    category: '흉내',
    family: '흉내',
    name: '흉내 묶음',
    reason: '흉내',
    llm: { answer: '흉내', outcome: 'success', reason: null },
  },
  recommendations: [{ title: '흉내 추천', value: '0.2', expectedCo2e: '0.3' }],
  origin: 'ai',
  originSteps: [step('group')],
  missing: [],
  input: INPUT,
});
const activity = (
  kind: string,
  co2e: string | null,
  biogenic?: string | null,
): Json => ({
  rowId: 'a',
  kind,
  month: null,
  activity: AMOUNT,
  factor: FACTOR,
  co2e,
  unit: 'tCO2eq',
  formula: '흉내 식',
  treatment: null,
  biogenic: biogenic === undefined ? null : bio(biogenic),
  distance: {
    departure: '흉내 출발',
    arrival: '흉내 도착',
    km: '3',
    roundTrip: '1',
    trips: '1',
    people: '1',
    workdays: '10',
    geoMode: 'ai',
    via: '흉내',
  },
  mode: { value: 'subway', origin: 'rule' },
  origin: 'rule',
  originSteps: [step('mapping')],
  missing: [],
  input: INPUT,
});
const energy = (
  kind: string,
  co2e: string | null,
  biogenic?: string | null,
): Json => ({
  rowId: 'e',
  kind,
  month: null,
  activity: AMOUNT,
  factor: FACTOR,
  co2e,
  unit: 'tCO2eq',
  formula: '흉내 식',
  match: { type: '흉내', score: '0.8' },
  allocation: {
    method: '흉내',
    areaRatio: null,
    personRatio: '0.5',
    buildingTotal: '5',
  },
  product: { totalUsage: '5', years: '2' },
  investment: { share: '0.2', scope1: '1', scope2: '1' },
  biogenic: biogenic === undefined ? null : bio(biogenic),
  origin: 'estimate',
  originSteps: [step('unit')],
  missing: [],
  input: INPUT,
});
const processed = (sheet: string, n: number, rows: Json[]): Json => ({
  status: 'processed',
  sheet,
  category: `Category${n}`,
  rows,
});

/**
 * done 결과 본문(줄 kind 열넷·시트 다섯 갈래). 카드 값: C1 <0.001(지수) · C3 0.3(긴 꼬리) · C4 1,234.75(시트 둘) · C5 생물기원 0.5 ·
 * C12 생물기원 <0.001 · C10·C14 「-」. problems 면 실패 시트 하나(C15)·AI 호출 실패 둘.
 */
export function e2eDoneResult({ problems = false } = {}): Json {
  return {
    status: 'done',
    schemaVersion: 'scope3.colab.result@1',
    reportYear: 2025,
    factorBook: {
      sheet: '흉내 계수표',
      column: '2024',
      year: 2024,
      reload: 'kept_initial',
      reloadProblem: null,
    },
    factorSheets: [
      { sheet: '흉내 계수표', header: null, rows: 2, read: 'initial' },
    ],
    llmCalls:
      problems ?
        {
          classify: { success: 5, 'failed:refusal': 1 },
          factor: { 'failed:timeout': 1 },
        }
      : { classify: { success: 5 } },
    sheets: [
      processed('s1', 1, [purchase('1e-05')]),
      processed('s2', 2, [purchase('2')]),
      processed('s3', 3, [energy('fuel_energy', '0.30000000000000004')]),
      processed('s4a', 4, [activity('transport_distance', '1234.5')]),
      processed('s4b', 4, [activity('transport_spend', '0.25')]),
      processed('s5', 5, [activity('waste', '2', '0.5')]),
      processed('s6', 6, [
        activity('travel_distance', '1'),
        activity('travel_spend', '1'),
      ]),
      processed('s7', 7, [activity('commute', '7')]),
      processed('s8', 8, [energy('leased_asset', '8')]),
      processed('s9', 9, [activity('transport_spend', '9')]),
      processed('s11', 11, [energy('product_use', '11')]),
      processed('s12', 12, [energy('product_eol', '12', '1e-04')]),
      processed('s13', 13, [energy('leased_out_asset', '13')]),
      { status: 'empty', sheet: 's14', category: 'Category14' },
      problems ?
        {
          status: 'failed',
          sheet: 's15',
          category: 'Category15',
          error: E2E_SHEET_ERROR,
        }
      : processed('s15', 15, [
          energy('investment', '15'),
          energy('franchise', null),
        ]),
      { status: 'not_target', sheet: 's-guide' },
      {
        status: 'not_yet_supported',
        sheet: 's-later',
        category: 'Category11',
        band: 'S3C-b',
      },
    ],
  };
}

/** 상세 e2e 의 지어낸 글자(화면에서 찾는다). */
export const E2E_GROUP_A = '흉내 묶음 가';
export const E2E_GROUP_B = '흉내 묶음 나';
export const E2E_TREATMENT = '흉내 처리';
/** 상세 e2e 의 C1 줄 수 — 쪽 나눔(50)을 넘는다. */
export const E2E_C1_ROWS = 53;
/** 시트 이름 — 앞머리는 엔진 양식의 앞머리(대문자 C — 실데이터 꼴), 뒤는 지어낸 글자. */
export const e2eSheet = (head: string) => `${head}_흉내`;

/** 시트 앞머리 → 그 처리기가 채우는 입력 키(엔진 serialize.py 원천 표 — S3R2 §C0 표, src 의 FAKE_INPUT_KEYS 와 같은 표를 옮겨 적음). */
const E2E_INPUT_KEYS: Record<string, readonly string[]> = {
  C1: ['country', 'site', 'name'],
  C2: ['country', 'site', 'name'],
  C3: ['country', 'site', 'energy'],
  'C4-1': ['country', 'site', 'name'],
  'C4-2': ['country', 'site', 'name', 'vehicle'],
  C5: ['country', 'site', 'name'],
  'C6-1': ['country', 'site', 'people'],
  'C6-2': ['country', 'site', 'vehicle', 'people'],
  C7: ['country', 'site', 'people'],
  'C8-1': ['country', 'name', 'energy'],
  'C8-2': ['country', 'name', 'energy', 'buildingArea', 'usedArea'],
  'C8-3': ['country', 'name', 'energy', 'buildingPeople', 'ownPeople'],
  'C9-1': ['country', 'site', 'name'],
  'C9-2': ['country', 'site', 'name', 'vehicle'],
  C11: ['country', 'name', 'energy', 'productCount', 'useMonths'],
  C12: ['country', 'name', 'sales', 'weight', 'weightUnit'],
  'C13-1': ['country', 'name', 'energy'],
  'C13-2': ['country', 'name', 'energy', 'buildingArea', 'usedArea'],
  'C13-3': ['country', 'name', 'energy', 'buildingPeople', 'ownPeople'],
  C14: ['country', 'name', 'energy', 'stores'],
  C15: ['name'],
};
const E2E_INPUT_WORDS: Json = {
  country: '나라',
  site: '사업장',
  name: '이름',
  vehicle: '수단',
  energy: '에너지',
};
const E2E_INPUT_NUMBERS: Json = {
  people: '6.0',
  buildingArea: '250.0',
  usedArea: '50.0',
  buildingPeople: '80.0',
  ownPeople: '8.0',
  productCount: '9.0',
  sales: '3400.0',
  weight: '1.5',
  weightUnit: 'g',
  stores: '15.0',
  useMonths: '30.5',
};
/** 그 시트의 입력 칸(키 열여섯 — 처리기에 없는 키 null). 글은 「흉내 나라 C1」 꼴. */
export function e2eInput(head: string, overrides: Json = {}): Json {
  const out: Json = Object.fromEntries(
    Object.keys(INPUT).map((key) => [key, null]),
  );
  for (const key of E2E_INPUT_KEYS[head] ?? [])
    out[key] =
      E2E_INPUT_NUMBERS[key] ?? `흉내 ${String(E2E_INPUT_WORDS[key])} ${head}`;
  return { ...out, ...overrides };
}
/** C1 둘째 줄(엑셀 6)만의 사업장 — 입력 글 검색 e2e. */
export const E2E_LONE_SITE = '흉내 외딴 사업장';

const at = (
  row: Json,
  sheet: string,
  line: string,
  extra: Json = {},
): Json => ({
  ...row,
  rowId: `${sheet}!${line}`,
  ...extra,
});

/**
 * 상세 표 e2e 의 done 본문(S3W2b ①): 시트 꼴 21 전부(이름 앞머리 C1…C15) · 줄 kind 열넷 · C1 53 줄(쪽 둘 · 그룹 둘 · 같은 엑셀 줄 #n ·
 * 지수 글자) · C4 일부 실패(둘째 C4-2 시트 failed) · C6 둘째 시트 empty · C5 생물기원·FCF·추정 줄. 값은 지어낸 것.
 */
export function e2eDetailResult(): Json {
  const body = e2eDetailBase();
  // 입력 칸(S3W2c ①): 줄마다 그 시트 처리기의 키에 시트마다 다른 흉내 값 · C1 엑셀 6 줄만 다른 사업장 · C1 마지막 줄(4#2)은
  //   옛 줄(input 칸 없음 — 입력 열 「-」) · C14 둘째 줄은 가맹점 수 2(정렬) · C11 첫 줄(!3)은 키 열다섯 옛 판(S3R3 앞 저장 —
  //   useMonths 없음 → 평균사용기간 「-」, 감독 처분 Q3), C11 둘째 줄(!4)은 useMonths 「30.5」(배출량 0 — 합계 그대로).
  for (const sheet of body.sheets as Json[]) {
    if (sheet.status !== 'processed') continue;
    const head = String(sheet.sheet).replace(/_흉내$/, '');
    sheet.rows = (sheet.rows as Json[]).map((row) => {
      const lone = head === 'C1' && String(row.rowId).endsWith('!6');
      return {
        ...row,
        input: e2eInput(head, lone ? { site: E2E_LONE_SITE } : {}),
      };
    });
  }
  const sheets = body.sheets as Json[];
  const c1 = sheets.find((one) => one.sheet === e2eSheet('C1'))!.rows as Json[];
  const { input: _input, ...old } = c1[c1.length - 1]!;
  void _input;
  c1[c1.length - 1] = old;
  const c14 = sheets.find((one) => one.sheet === e2eSheet('C14'))!
    .rows as Json[];
  c14.push({
    ...c14[0]!,
    rowId: `${e2eSheet('C14')}!4`,
    co2e: '0',
    input: e2eInput('C14', { stores: '2.0' }),
  });
  const c11 = sheets.find((one) => one.sheet === e2eSheet('C11'))!
    .rows as Json[];
  const { useMonths: _useMonths, ...fifteen } = c11[0]!.input as Json;
  void _useMonths;
  c11.push({ ...c11[0]!, rowId: `${e2eSheet('C11')}!4`, co2e: '0' });
  c11[0] = { ...c11[0]!, input: fifteen };
  return body;
}

function e2eDetailBase(): Json {
  const c1 = e2eSheet('C1');
  const c1Rows: Json[] = [];
  for (let i = 0; i < E2E_C1_ROWS; i += 1)
    c1Rows.push(
      at(purchase(i === 0 ? '1e-05' : String(i)), c1, String(5 + i), {
        group: {
          ...(purchase(null).group as Json),
          name: i % 2 === 0 ? E2E_GROUP_A : E2E_GROUP_B,
        },
        originSteps: GROUP_STEPS[i] ?? [step('group')],
      }),
    );
  // 같은 엑셀 줄이 두 줄로 나온 것(#1·#2).
  c1Rows.push(at(purchase('0.5'), c1, '4#1'), at(purchase('0.25'), c1, '4#2'));
  const s = e2eSheet;
  const one = (head: string, n: number, row: Json, extra: Json = {}) =>
    processed(s(head), n, [at(row, s(head), '3', extra)]);
  return {
    status: 'done',
    schemaVersion: 'scope3.colab.result@1',
    reportYear: 2025,
    factorBook: {
      sheet: '흉내 계수표',
      column: '2024',
      year: 2024,
      reload: 'kept_initial',
      reloadProblem: null,
    },
    factorSheets: [
      { sheet: '흉내 계수표', header: null, rows: 2, read: 'initial' },
    ],
    llmCalls: { classify: { success: 5 } },
    sheets: [
      processed(c1, 1, c1Rows),
      one('C2', 2, purchase('2')),
      one('C3', 3, energy('fuel_energy', '3')),
      one('C4-1', 4, activity('transport_distance', '4')),
      one('C4-2', 4, activity('transport_spend', '1'), {
        distance: null,
        mode: null,
      }),
      {
        status: 'failed',
        sheet: `${s('C4-2')} 둘`,
        category: 'Category4',
        error: E2E_SHEET_ERROR,
      },
      processed(s('C5'), 5, [
        at(activity('waste', '3', '1.5'), s('C5'), '3', {
          treatment: E2E_TREATMENT,
          distance: null,
          mode: null,
          origin: 'estimate',
        }),
        at(activity('waste', '1', '0.5'), s('C5'), '4', {
          treatment: '흉내 다른 처리',
          distance: null,
          mode: null,
        }),
      ]),
      one('C6-1', 6, activity('travel_distance', '6')),
      one('C6-2', 6, activity('travel_spend', '1'), { distance: null }),
      { status: 'empty', sheet: `${s('C6-2')} 둘`, category: 'Category6' },
      one('C7', 7, activity('commute', '7')),
      one('C8-1', 8, energy('leased_asset', '8')),
      one('C8-2', 8, energy('leased_asset', '1')),
      one('C8-3', 8, energy('leased_asset', '1')),
      one('C9-1', 9, activity('transport_distance', '9')),
      one('C9-2', 9, activity('transport_spend', '1'), {
        distance: null,
        mode: null,
      }),
      one('C11', 11, energy('product_use', '11')),
      one('C12', 12, energy('product_eol', '12', '0.75'), {
        biogenic: {
          fossilCo2e: '11.25',
          biogenicCo2e: '0.75',
          fcf: null,
          note: '해당없음',
        },
        formula: '',
      }),
      one('C13-1', 13, energy('leased_out_asset', '13')),
      one('C13-2', 13, energy('leased_out_asset', '1')),
      one('C13-3', 13, energy('leased_out_asset', '1')),
      one('C14', 14, energy('franchise', '14')),
      one('C15', 15, energy('investment', '15'), { factor: null }),
      { status: 'not_target', sheet: 's-guide' },
    ],
  };
}

/** S3Q1 흉내 출처 글·C12 칸(지어낸 값 — 실제 책 글 0). */
export const E2E_SOURCE_TEXT = '흉내 기관 계수 고시 2099';
export const E2E_C3_NOTE = '흉내 지침 을(업스트림)';
export const E2E_C12_CODE = '92-02-02';
export const E2E_C12_NAME = '흉내 폐포장재';
/** C12 처리방법별 값(openapi ColabC12TreatmentsJson 꼴). nan 은 MARC-ISSUE-390 꼴(빈 비중 칸 — share null 인데 used). */
export function e2eTreatments(branch: 'code' | 'average' | 'nan'): Json {
  if (branch === 'average')
    return {
      branch: 'average',
      shareTotal: null,
      parts: ['매립', '소각', '재활용'].map((treatment, i) => ({
        treatment,
        share: null,
        factor: ['0.17', '1.17', '0.02'][i],
        used: false,
      })),
    };
  return {
    branch: 'code',
    shareTotal: branch === 'nan' ? null : '1.0',
    parts: [
      {
        treatment: '매립',
        share: branch === 'nan' ? null : '0.2',
        factor: '0.013',
        used: true,
      },
      { treatment: '소각', share: '0.3', factor: '3.4', used: true },
      { treatment: '재활용', share: '0.5', factor: '0.0186', used: true },
    ],
  };
}
/**
 * S3Q1 새 칸 결과(줄 kind 열넷 기본 본문의 C12·C3·C5 시트를 갈음): C12 줄 넷(code·average·nan·옛 줄 칸 없음) · C3 줄 둘(sourceText 있음·없음) ·
 * C5 줄(sourceText 있음).
 */
export function e2eS3Q1Result(): Json {
  const body = e2eDoneResult();
  const c12 = (
    rowId: string,
    treatments: Json | undefined,
    value: string | null = '0.5',
  ): Json => ({
    ...energy('product_eol', '0.25', '0.05'),
    rowId,
    factor: {
      ...FACTOR,
      sheet: '폐기물_C12',
      title: null,
      value,
      unit: 'kgCO2eq/kg',
      column: null,
      code: E2E_C12_CODE,
    },
    input: { ...INPUT, name: E2E_C12_NAME },
    ...(treatments === undefined ? {} : { treatments }),
  });
  const c3 = (rowId: string, sourceText?: string): Json => ({
    ...energy('fuel_energy', '0.3'),
    rowId,
    factor: {
      ...FACTOR,
      sheet: '에너지_C3',
      ...(sourceText === undefined ? {} : { sourceText }),
    },
  });
  const sheets = (body.sheets as Json[]).filter(
    (sheet) =>
      !['Category12', 'Category3', 'Category5'].includes(
        String(sheet.category),
      ),
  );
  return {
    ...body,
    sheets: [
      ...sheets,
      processed('c12_흉내', 12, [
        c12('c12_흉내!3', e2eTreatments('code')),
        c12('c12_흉내!4', e2eTreatments('average')),
        c12('c12_흉내!5', e2eTreatments('nan'), null),
        c12('c12_흉내!6', undefined),
      ]),
      processed('c3_흉내', 3, [c3('c3_흉내!3', E2E_C3_NOTE), c3('c3_흉내!4')]),
      processed('c5_흉내', 5, [
        {
          ...activity('waste', '0.5', '0.1'),
          rowId: 'c5_흉내!3',
          factor: { ...FACTOR, sourceText: E2E_SOURCE_TEXT },
        },
      ]),
    ],
  };
}

export const e2eRejectedResult = (reason = 'legacy_template'): Json => ({
  status: 'rejected',
  schemaVersion: 'scope3.colab.result@1',
  rejected: { reason, detail: E2E_REJECT_DETAIL },
});

// ── 지금 결과(S3W3a ①) — 서버 actions/scope3_state.py·scope3_edits.py 의 거울. 페이지 없이 부를 수 있다(spec 의 openapi 걸음). ──

/** 서버 CATEGORIES(C1~C15, C10 뺌). */
const CATEGORY_NAMES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15].map(
  (n) => `C${n}`,
);
/** 식이 있는 줄 kind(서버 _FORMULAS + waste). product_eol·investment 는 식이 없어 409 다(sid:MARC-ENT-579). */
const FORMULA_KINDS = [
  'purchase',
  'transport_spend',
  'travel_spend',
  'transport_distance',
  'travel_distance',
  'commute',
  'fuel_energy',
  'leased_asset',
  'leased_out_asset',
  'product_use',
  'franchise',
  'waste',
];
const FACTOR_KEYS = ['rowId', 'choice', 'rank', 'custom', 'reason'];
const CUSTOM_KEYS = ['title', 'value', 'source'];
const FACTOR_CHOICES = ['applied', 'recommended', 'custom'];
const FACTOR_VALUE = /^[0-9]+(?:\.([0-9]+))?$/;
export const E2E_EDITOR = { id: '7', name: '흉내 담당자' };
/** 추천·직접 입력으로 고른 줄의 값(식은 흉내 내지 않는다 — 칸이 모자란 줄·본문과 글자가 다른 줄·schemaVersion·flow 어긋남의 409 도 그래서 없다). */
export const E2E_EDITED_CO2E = '7.25';
export const E2E_EDITED_BIOGENIC = '0.75';

/** 계수 사건의 값(Scope3RowEditFactorOut 칸 그대로). 값은 지어낸 것이다. */
export const e2eRowFactor = (overrides: Json = {}): Json => ({
  choice: 'custom',
  rank: null,
  title: '흉내 고친 계수',
  value: '0.5',
  source: '흉내 출처',
  unit: 'kgCO2e/KRW',
  co2e: E2E_EDITED_CO2E,
  biogenicCo2e: null,
  ai: {
    title: '흉내 원안 계수',
    value: '0.25',
    source: '흉내 시트',
    co2e: '1.25',
  },
  ...overrides,
});

/** 서버 repr(float(글자)) 꼴(저장 꼴 — 「0.50」 은 「0.5」, 「2」 는 「2.0」, 작은 값은 「1e-05」). */
function storedValue(text: string): string {
  const value = Number(text);
  const [mantissa, power] = value.toExponential().split('e') as [
    string,
    string,
  ];
  const exponent = Number(power);
  if (exponent < -4 || exponent >= 16)
    return `${mantissa}e${exponent < 0 ? '-' : '+'}${String(Math.abs(exponent)).padStart(2, '0')}`;
  const plain = String(value);
  return plain.includes('.') ? plain : `${plain}.0`;
}

/** 서버 _check_value: 십진 글자 · 소수 10자리 안 · 유한 · 0 초과. */
function goodValue(text: unknown): text is string {
  const found = typeof text === 'string' ? FACTOR_VALUE.exec(text) : null;
  if (found === null || (found[1] ?? '').length > 10) return false;
  const value = Number(text);
  return Number.isFinite(value) && value > 0;
}

const trimmed = (value: unknown) =>
  typeof value === 'string' ? value.trim() : '';
/** 서버 _custom_problems 의 글 칸: 걷고 1~200자(코드 포인트). */
const badText = (value: unknown) => {
  const size = [...trimmed(value)].length;
  return size < 1 || size > 200;
};

/** 서버 _source: 계수의 시트 이름. 구매 줄은 sheet 칸이 없어 factorBook.sheet + factor.column. */
function factorSource(factor: Json, book: unknown): string | null {
  if (typeof factor.sheet === 'string') return factor.sheet;
  const name =
    isRecord(book) && typeof book.sheet === 'string' ? book.sheet : null;
  if (name === null || typeof factor.column !== 'string') return name;
  return `${name} ${factor.column.replaceAll('\n', ' ')}`;
}

/** 서버 chosen: 고름 → 사건 값. 그 줄에 없는 추천 순위면 null. */
function chosenFactor(b: Json, row: Json, book: unknown): Json | null {
  const factor = row.factor as Json;
  const ai = {
    title: factor.title,
    value: factor.value,
    source: factorSource(factor, book),
    co2e: row.co2e,
  };
  const biogenic = isRecord(row.biogenic) ? row.biogenic : null;
  const shared = { choice: b.choice, rank: b.rank, unit: factor.unit, ai };
  if (b.choice === 'applied')
    return {
      ...shared,
      title: ai.title,
      value: ai.value,
      source: ai.source,
      co2e: ai.co2e,
      biogenicCo2e: biogenic?.biogenicCo2e ?? null,
    };
  // 생물기원은 폐기물 줄만 새로 온다(서버 _waste — FCF 가 없으면 「0.0」).
  const edited = {
    co2e: E2E_EDITED_CO2E,
    biogenicCo2e:
      row.kind !== 'waste' ? null
      : biogenic?.fcf === null || biogenic?.fcf === undefined ? '0.0'
      : E2E_EDITED_BIOGENIC,
  };
  if (isRecord(b.custom))
    return {
      ...shared,
      ...edited,
      title: trimmed(b.custom.title),
      value: storedValue(b.custom.value as string),
      source: trimmed(b.custom.source),
    };
  const items = Array.isArray(row.recommendations) ? row.recommendations : [];
  const item: unknown = items[(b.rank as number) - 1];
  if (!isRecord(item) || !Number.isFinite(Number(item.value ?? NaN)))
    return null;
  return {
    ...shared,
    ...edited,
    title: item.title,
    value: item.value,
    source: ai.source,
  };
}

/** 판정 ①(서버 StrictIn + check_factor_body). 칸 이름 → 글. */
function factorBodyFields(b: Json): Record<string, string[]> {
  const fields: Record<string, string[]> = {};
  for (const key of FACTOR_KEYS)
    if (!(key in b)) fields[key] = ['지어낸-칸 없음'];
  for (const key of Object.keys(b))
    if (!FACTOR_KEYS.includes(key)) fields[key] = ['지어낸-더한 칸'];
  if (typeof b.rowId !== 'string') fields.rowId = ['지어낸-줄'];
  if (!FACTOR_CHOICES.includes(b.choice as string))
    fields.choice = ['지어낸-고름'];
  const rank = b.rank ?? null;
  if (
    (b.choice === 'recommended') !== (rank !== null) ||
    (rank !== null && !(isInt(rank) && rank >= 1 && rank <= 4))
  )
    fields.rank = ['지어낸-순위'];
  const asked = b.custom ?? null;
  if (
    (b.choice === 'custom') !== (asked !== null) ||
    (asked !== null && !isRecord(asked))
  )
    fields.custom = ['지어낸-입력'];
  else if (isRecord(asked)) {
    for (const key of Object.keys(asked))
      if (!CUSTOM_KEYS.includes(key))
        fields[`custom.${key}`] = ['지어낸-더한 칸'];
    for (const cell of ['title', 'source'])
      if (badText(asked[cell])) fields[`custom.${cell}`] = ['지어낸-칸'];
    if (!goodValue(asked.value)) fields['custom.value'] = ['지어낸-값'];
  }
  const size = [...trimmed(b.reason)].length;
  if (size < 1 || size > 300) fields.reason = ['지어낸-사유'];
  return fields;
}

const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/;

function decimalOf(text: unknown): { digits: bigint; scale: number } | null {
  const found = typeof text === 'string' ? DECIMAL.exec(text) : null;
  if (!found) return null;
  const [, sign, whole, fraction = '', exponent = '0'] = found;
  const raw = BigInt(`${whole}${fraction}`);
  const scale = fraction.length - Number(exponent);
  const digits = sign === '-' ? -raw : raw;
  return scale >= 0 ?
      { digits, scale }
    : { digits: digits * 10n ** BigInt(-scale), scale: 0 };
}

/** 서버 sum_or_none + decimal_text 의 거울: 정확합을 지수 없는 글자로(끝 0 걷음). 수가 없으면 null. */
export function decimalSum(texts: readonly unknown[]): string | null {
  const found = texts.flatMap((text) => decimalOf(text) ?? []);
  if (found.length === 0) return null;
  const scale = Math.max(...found.map((one) => one.scale));
  const sum = found.reduce(
    (total, one) => total + one.digits * 10n ** BigInt(scale - one.scale),
    0n,
  );
  const negative = sum < 0n;
  const plain = (negative ? -sum : sum).toString().padStart(scale + 1, '0');
  const whole = plain.slice(0, plain.length - scale);
  const fraction = plain.slice(plain.length - scale).replace(/0+$/, '');
  return `${negative ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`;
}

export interface LedgerRun {
  id: number;
  flowId: string;
  options: Json;
  result: unknown;
}
interface LedgerEvent {
  id: number;
  runId: number;
  rowId: string;
  category: string;
  kind: 'exclude' | 'restore' | 'factor';
  reason: string;
  at: string;
  by: Json | null;
  batchId: string | null;
  factor: Json | null;
}
/** 답 하나(상태 번호와 본문). */
export interface LedgerAnswer {
  status: number;
  body: unknown;
}

const isRecord = (value: unknown): value is Json =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const denied = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
): LedgerAnswer => ({
  status,
  body: {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  },
});
const ok = (body: unknown): LedgerAnswer => ({ status: 200, body });

const E2E_STEP_NAMES = [
  ...[1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15].map((n) => `c${n}`),
  'assemble',
];

/** RunOut.steps 꼴(서버: 실행을 만들 때부터 전부 선언 차례로). 처리 중이면 읽을 때마다 한 단계씩. */
function e2eSteps(status: string, at: number, stepFailed: boolean): Json[] {
  return E2E_STEP_NAMES.map((step, index) => {
    const state =
      status === 'done' ? 'done'
      : status === 'failed' ?
        stepFailed && index === 0 ?
          'failed'
        : 'pending'
      : status === 'queued' ? 'pending'
      : index < at ? 'done'
      : index === at ? 'running'
      : 'pending';
    const calls = state === 'pending' ? null : index;
    return { step, status: state, done: calls, total: calls };
  });
}

/** 흉내의 지금 결과 장부. runs·statusOf 는 흉내 쪽 것을 받는다(같은 실행을 본다). operator 가 아니면 풀기 403. */
export function createScope3Ledger<R extends LedgerRun>(
  runs: readonly R[],
  statusOf: (run: R) => Status,
  operator: boolean,
) {
  const events: LedgerEvent[] = [];
  const locks = new Map<string, { runId: number; at: string; by: Json }>();
  let eventSeq = 1;
  let batchSeq = 1;
  const addEvent = (
    event: Omit<LedgerEvent, 'id' | 'at' | 'by'> & { by?: Json | null },
  ) => {
    const id = eventSeq++;
    events.push({
      by: E2E_EDITOR,
      ...event,
      id,
      at: `2026-03-01T00:00:${String(id % 60).padStart(2, '0')}Z`,
    });
  };
  const folded = (runId: number) => {
    const found = new Map<string, LedgerEvent>();
    for (const event of events) {
      if (event.runId !== runId) continue;
      const key = `${event.rowId} ${event.kind === 'factor' ? 'factor' : 'row'}`;
      const last = found.get(key);
      if (!last || event.id > last.id) found.set(key, event);
    }
    return [...found.values()];
  };
  const excludedOf = (runId: number, category: string) =>
    new Set(
      folded(runId)
        .filter((one) => one.category === category && one.kind === 'exclude')
        .map((one) => one.rowId),
    );
  const fixedOf = (runId: number, category: string) =>
    new Map(
      folded(runId)
        .filter(
          (one) =>
            one.category === category &&
            one.factor !== null &&
            one.factor.choice !== 'applied',
        )
        .map((one) => [one.rowId, one.factor!.co2e]),
    );
  const isDone = (body: unknown): body is Json & { sheets: unknown[] } =>
    isRecord(body) && body.status === 'done' && Array.isArray(body.sheets);
  const baseOf = (year: number) => {
    const candidates = runs
      .filter(
        (run) =>
          run.flowId === 'scope3.colab@157' && run.options.reportYear === year,
      )
      .sort((a, b) => b.id - a.id);
    return {
      latest: candidates[0] ?? null,
      base:
        candidates.find(
          (run) => statusOf(run) === 'done' && isDone(run.result),
        ) ?? null,
    };
  };
  const sheetsOf = (run: R, category: string) =>
    (isDone(run.result) ? run.result.sheets : []).filter(
      (sheet): sheet is Json =>
        isRecord(sheet) && sheet.category === `Category${category.slice(1)}`,
    );
  const rowsIn = (run: R, category: string) =>
    sheetsOf(run, category)
      .filter((sheet) => sheet.status === 'processed')
      .flatMap((sheet) => sheet.rows as Json[]);
  const currentOf = (year: number, category: string) => {
    const lock = locks.get(`${year} ${category}`);
    const runId = lock ? lock.runId : baseOf(year).base?.id;
    if (runId === undefined) return null;
    const run = runs.find((one) => one.id === runId)!;
    const excluded = excludedOf(runId, category);
    const fixed = fixedOf(runId, category);
    const sheets = sheetsOf(run, category);
    return {
      runId: String(runId),
      total: decimalSum(
        rowsIn(run, category).flatMap((row) => {
          const id = row.rowId;
          if (typeof id !== 'string') return [row.co2e];
          if (excluded.has(id)) return [];
          return [fixed.has(id) ? fixed.get(id) : row.co2e];
        }),
      ),
      sheets: sheets.filter((sheet) => sheet.status === 'processed').length,
      failedSheets: sheets.filter((sheet) => sheet.status === 'failed').length,
    };
  };
  const categoryOut = (year: number, category: string) => {
    const lock = locks.get(`${year} ${category}`);
    const current = currentOf(year, category);
    const runId = current === null ? null : Number(current.runId);
    return {
      category,
      current,
      locked: lock !== undefined,
      lockedAt: lock?.at ?? null,
      lockedBy: lock?.by ?? null,
      editedRows:
        runId === null ? 0 : (
          new Set([
            ...excludedOf(runId, category),
            ...fixedOf(runId, category).keys(),
          ]).size
        ),
    };
  };
  const yearOut = (year: number) => {
    const { latest, base } = baseOf(year);
    const categories = CATEGORY_NAMES.map((one) => categoryOut(year, one));
    return {
      year,
      baseRunId: base === null ? null : String(base.id),
      latest:
        latest === null ? null : (
          { runId: String(latest.id), status: statusOf(latest) }
        ),
      categories,
      editedRowsUnlocked: categories
        .filter((one) => !one.locked)
        .reduce((sum, one) => sum + one.editedRows, 0),
    };
  };
  const rowStates = (runId: number, only?: readonly string[]) => {
    const split = new Map<string, LedgerEvent[]>();
    for (const event of folded(runId))
      if (!only || only.includes(event.rowId))
        split.set(event.rowId, [...(split.get(event.rowId) ?? []), event]);
    return [...split.keys()].sort().map((rowId) => {
      const lines = split.get(rowId)!;
      const last = lines.reduce((a, b) => (b.id > a.id ? b : a));
      return {
        rowId,
        category: last.category,
        excluded: lines.some((one) => one.kind === 'exclude'),
        factor: lines.find((one) => one.factor !== null)?.factor ?? null,
        editedAt: last.at,
        editedBy: last.by,
      };
    });
  };
  const historyOut = (runId: number, query: URLSearchParams) => {
    const rowId = query.get('rowId');
    const page = Number(query.get('page') ?? '1');
    const pageSize = Number(query.get('pageSize') ?? '20');
    const lines = events
      .filter(
        (one) => one.runId === runId && (rowId === null || one.rowId === rowId),
      )
      .sort((a, b) => b.id - a.id);
    const totalPages = Math.ceil(lines.length / pageSize);
    return {
      count: lines.length,
      totalPages,
      page,
      pageSize,
      hasNext: page < totalPages,
      hasPrevious: page > 1,
      results: lines
        .slice((page - 1) * pageSize, page * pageSize)
        .map((one) => ({
          id: String(one.id),
          rowId: one.rowId,
          category: one.category,
          kind: one.kind,
          reason: one.reason,
          at: one.at,
          by: one.by,
          batchId: one.batchId,
          factor: one.factor,
        })),
    };
  };
  function lock(year: number, category: string, runId: number): LedgerAnswer {
    if (!CATEGORY_NAMES.includes(category)) return denied(404, 'NOT_FOUND');
    const current = currentOf(year, category);
    if (current === null || current.sheets === 0)
      return denied(409, 'NOT_COMPUTED');
    if (!runs.some((run) => run.id === runId)) return denied(404, 'NOT_FOUND');
    if (String(runId) !== current.runId) return denied(409, 'STALE_RUN');
    const key = `${year} ${category}`;
    if (!locks.has(key))
      locks.set(key, { runId, at: '2026-03-02T01:02:03Z', by: E2E_EDITOR });
    return ok(categoryOut(year, category));
  }
  function unlock(year: number, category: string): LedgerAnswer {
    if (!operator) return denied(403, 'FORBIDDEN');
    if (!CATEGORY_NAMES.includes(category)) return denied(404, 'NOT_FOUND');
    locks.delete(`${year} ${category}`);
    return ok(categoryOut(year, category));
  }
  /** 판정 ②~⑥(서버 _held). */
  function held(
    runId: number,
    category: string,
  ): { run: R; year: number } | LedgerAnswer {
    if (!CATEGORY_NAMES.includes(category)) return denied(404, 'NOT_FOUND');
    const run = runs.find((one) => one.id === runId);
    if (!run) return denied(404, 'NOT_FOUND');
    const year = run.options.reportYear;
    if (!isInt(year)) return denied(409, 'STALE_RUN');
    if (locks.has(`${year} ${category}`)) return denied(409, 'LOCKED');
    if (baseOf(year).base?.id !== runId) return denied(409, 'STALE_RUN');
    return { run, year };
  }
  const reasonOf = (value: unknown) =>
    typeof value === 'string' ? value.trim() : '';
  function editRows(
    runId: number,
    category: string,
    kind: 'exclude' | 'restore',
    body: unknown,
  ): LedgerAnswer {
    const b = isRecord(body) ? body : {};
    const reason = reasonOf(b.reason);
    const rowIds = b.rowIds;
    const fields: Record<string, string[]> = {};
    if (
      !Array.isArray(rowIds) ||
      rowIds.length === 0 ||
      new Set(rowIds).size !== rowIds.length
    )
      fields.rowIds = ['지어낸-줄'];
    if ([...reason].length < 1 || [...reason].length > 300)
      fields.reason = ['지어낸-사유'];
    if (Object.keys(fields).length > 0)
      return denied(422, 'VALIDATION_ERROR', fields);
    const found = held(runId, category);
    if ('status' in found) return found;
    const ids = rowIds as string[];
    const known = rowsIn(found.run, category).map((row) => row.rowId);
    if (!ids.every((id) => known.includes(id)))
      return denied(422, 'VALIDATION_ERROR', { rowIds: ['지어낸-줄'] });
    const excluded = excludedOf(runId, category);
    const batchId = `batch-${batchSeq++}`;
    for (const rowId of ids)
      if (excluded.has(rowId) !== (kind === 'exclude'))
        addEvent({
          runId,
          rowId,
          category,
          kind,
          reason,
          batchId,
          factor: null,
        });
    return ok({
      category: categoryOut(found.year, category),
      rows: rowStates(runId, ids),
    });
  }
  /** 계수 고르기(서버 factor). 판정 차례: 몸 422 → 404 → 잠김 → stale → 줄 없음 422 → 409 → 없는 순위 422 → 같은 고름이면 사건 0. */
  function editFactor(
    runId: number,
    category: string,
    body: unknown,
  ): LedgerAnswer {
    const b = isRecord(body) ? body : {};
    const fields = factorBodyFields(b);
    if (Object.keys(fields).length > 0)
      return denied(422, 'VALIDATION_ERROR', fields);
    const reason = reasonOf(b.reason);
    const found = held(runId, category);
    if ('status' in found) return found;
    const row = rowsIn(found.run, category).find(
      (one) => one.rowId === b.rowId,
    );
    if (!row) return denied(422, 'VALIDATION_ERROR', { rowId: ['지어낸-줄'] });
    if (
      !FORMULA_KINDS.includes(row.kind as string) ||
      !isRecord(row.factor) ||
      typeof row.factor.unit !== 'string'
    )
      return denied(409, 'FACTOR_NOT_EDITABLE');
    const rowId = b.rowId as string;
    const factor = chosenFactor(
      { ...b, rank: b.rank ?? null },
      row,
      isRecord(found.run.result) ? found.run.result.factorBook : null,
    );
    if (factor === null)
      return denied(422, 'VALIDATION_ERROR', { rank: ['지어낸-순위'] });
    const last = folded(runId).find(
      (one) => one.kind === 'factor' && one.rowId === rowId,
    )?.factor;
    // 서버 same_choice: 사건이 없으면 지금은 AI 원안(applied 는 사건 0), 있으면 갈래·순위·값·제목·출처가 같을 때 사건 0.
    const same =
      last ?
        ['choice', 'rank', 'value', 'title', 'source'].every(
          (cell) => last[cell] === factor[cell],
        )
      : b.choice === 'applied';
    if (!same)
      addEvent({
        runId,
        rowId,
        category,
        kind: 'factor',
        reason,
        batchId: `batch-${batchSeq++}`,
        factor,
      });
    return ok({
      category: categoryOut(found.year, category),
      rows: rowStates(runId, [rowId]),
    });
  }
  /** 사건을 미리 둔다(runEdits). */
  function seed(runId: number, edits: readonly E2eRowEdit[]) {
    for (const edit of edits) {
      const line = {
        runId,
        rowId: edit.rowId,
        category: edit.category,
        reason: '흉내 사유',
        batchId: `batch-${batchSeq++}`,
        ...(edit.by === undefined ? {} : { by: edit.by }),
      };
      if (edit.excluded) addEvent({ ...line, kind: 'exclude', factor: null });
      if (edit.factor)
        addEvent({ ...line, kind: 'factor', factor: edit.factor });
    }
  }
  /** 경로 하나에 답한다. 이 장부의 경로가 아니면 null. */
  function answerOf(
    method: string,
    path: string,
    query: URLSearchParams,
    body: unknown,
  ): LedgerAnswer | null {
    let match = /^\/inventory\/scope3\/years\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const year = Number(match[1]);
      return year < 1990 || year > 2100 ?
          denied(422, 'VALIDATION_ERROR', { year: ['지어낸-해'] })
        : ok(yearOut(year));
    }
    match =
      /^\/inventory\/scope3\/years\/(\d+)\/categories\/([^/]+)\/lock$/.exec(
        path,
      );
    if (match && method === 'POST')
      return lock(Number(match[1]), match[2]!, Number(query.get('runId')));
    if (match && method === 'DELETE')
      return unlock(Number(match[1]), match[2]!);
    match = /^\/inventory\/scope3\/runs\/(\d+)\/(edits|history)$/.exec(path);
    if (match && method === 'GET') {
      const runId = Number(match[1]);
      if (!runs.some((run) => run.id === runId))
        return denied(404, 'NOT_FOUND');
      return ok(
        match[2] === 'edits' ?
          { runId: String(runId), rows: rowStates(runId) }
        : historyOut(runId, query),
      );
    }
    match =
      /^\/inventory\/scope3\/runs\/(\d+)\/categories\/([^/]+)\/(exclusions|restorations|factors)$/.exec(
        path,
      );
    if (match && method === 'POST') {
      const runId = Number(match[1]);
      if (match[3] === 'factors') return editFactor(runId, match[2]!, body);
      return editRows(
        runId,
        match[2]!,
        match[3] === 'exclusions' ? 'exclude' : 'restore',
        body,
      );
    }
    return null;
  }
  return { answerOf, seed };
}

export async function fakeScope3Api(
  page: Page,
  {
    server = 's3k1',
    operator = false,
    runScripts = [],
    runErrors = [],
    runResults = [],
    runEdits = [],
  }: Scope3ApiOptions = {},
) {
  const calls: Scope3Call[] = [];
  const docs = new Map<number, Doc>();
  const runs: Run[] = [];
  let docSeq = 31;
  let runSeq = 51;

  const statusOf = (run: Run) =>
    run.script[Math.min(run.at, run.script.length - 1)]!;
  const ledger = createScope3Ledger(runs, statusOf, operator);
  const runOut = (run: Run) => {
    const status = statusOf(run);
    const failed = status === 'failed';
    return {
      id: run.id,
      module: 'inventory.scope3',
      flowId: run.flowId,
      documentId: run.documentId,
      options: run.options,
      status,
      steps: e2eSteps(
        status,
        run.at,
        failed && STEP_CODES.includes(run.errorCode),
      ),
      resultShapes: [],
      files: [],
      createdAt: NOW,
      startedAt: status === 'queued' ? null : NOW,
      finishedAt: status === 'done' || failed ? NOW : null,
      failedStep: failed && STEP_CODES.includes(run.errorCode) ? 'c1' : null,
      errorCode: failed ? run.errorCode : null,
      errorMessage: failed ? E2E_ERROR_MESSAGE : null,
      resumedFromRunId: null,
    };
  };

  await page.route('**/fake-upload-s3/*', async (route) => {
    const request = route.request();
    const id = Number(new URL(request.url()).pathname.split('/').pop());
    const doc = docs.get(id);
    if (doc && request.method() === 'PUT') {
      doc.uploaded = true;
      doc.bytes = request.postDataBuffer() ?? Buffer.alloc(0);
    }
    calls.push({
      method: request.method(),
      path: new URL(request.url()).pathname,
      search: '',
      body: undefined,
      authorization: request.headers()['authorization'] ?? null,
      size: request.postDataBuffer()?.length ?? 0,
    });
    return route.fulfill({ status: doc ? 200 : 404, body: '' });
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
    if (!OWNED.test(path)) return route.fallback();
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
      search: url.search,
      body,
      authorization: request.headers()['authorization'] ?? null,
      size: request.postDataBuffer()?.length ?? 0,
    });
    const key = `${method} ${path}`;

    if (key === 'POST /documents') {
      const { fileName, sizeBytes } = body as Json;
      if (!isInt(sizeBytes) || typeof fileName !== 'string')
        return refusal(route, 422, 'VALIDATION_ERROR');
      if (sizeBytes > LIMIT) return refusal(route, 413, 'upload_too_large');
      const doc: Doc = {
        id: docSeq++,
        fileName,
        sizeBytes,
        uploaded: false,
      };
      docs.set(doc.id, doc);
      return answer(route, 201, {
        document: {
          id: doc.id,
          fileName,
          sizeBytes,
          status: 'awaiting_upload',
          pageCount: null,
          uploadedAt: null,
        },
        upload: {
          url: `${url.origin}/fake-upload-s3/${doc.id}`,
          method: 'PUT',
          expiresInSeconds: 900,
        },
      });
    }
    let match = /^\/documents\/(\d+)\/confirm$/.exec(path);
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
          pageCount: null,
          uploadedAt: NOW,
        },
      });
    }
    if (key === 'POST /runs') {
      const b = body as Json;
      if (b.resumeFromRunId !== undefined)
        return refusal(route, 422, 'VALIDATION_ERROR');
      if (b.module !== 'inventory.scope3' || b.flowId !== 'scope3.colab@157')
        return refusal(route, 422, 'UNKNOWN_FLOW');
      if (server === 'base' && operator)
        return refusal(route, 403, 'FORBIDDEN');
      if (server === 'base') return refusal(route, 422, 'FLOW_NOT_RUNNABLE');
      const doc = docs.get(b.documentId as number);
      if (!doc) return refusal(route, 422, 'DOCUMENT_REQUIRED');
      if (!doc.uploaded) return refusal(route, 409, 'DOCUMENT_NOT_UPLOADED');
      const options = (b.options ?? {}) as Json;
      const year = options.reportYear;
      if (!isInt(year) || year < 1990 || year > seoulYear())
        return refusal(route, 400, 'INVALID_OPTIONS');
      const run: Run = {
        id: runSeq++,
        documentId: doc.id,
        flowId: b.flowId as string,
        options: structuredClone(options),
        script: runScripts[runs.length] ?? ['processing', 'done'],
        at: 0,
        errorCode: runErrors[runs.length] ?? 'internal',
        result:
          runResults[runs.length] === undefined ?
            e2eDoneResult()
          : runResults[runs.length],
      };
      ledger.seed(run.id, runEdits[runs.length] ?? []);
      runs.push(run);
      return answer(route, 201, { id: run.id, status: 'queued' });
    }
    if (key === 'GET /runs') {
      if (url.searchParams.get('module') !== 'inventory.scope3')
        return answer(route, 200, { count: 0, isNext: false, results: [] });
      const results = [...runs]
        .sort((a, b) => b.id - a.id)
        .map((run) => {
          const out = runOut(run);
          return {
            id: out.id,
            module: out.module,
            flowId: out.flowId,
            status: out.status,
            createdAt: out.createdAt,
            finishedAt: out.finishedAt,
          };
        });
      return answer(route, 200, {
        count: results.length,
        isNext: false,
        results,
      });
    }
    match = /^\/runs\/(\d+)$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.find((one) => one.id === Number(match![1]));
      if (!run) return refusal(route, 404, 'NOT_FOUND');
      const out = runOut(run);
      run.at += 1;
      return answer(route, 200, out);
    }
    match = /^\/inventory\/scope3\/runs\/(\d+)\/original$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.find((one) => one.id === Number(match![1]));
      const doc = run ? docs.get(run.documentId) : undefined;
      if (!doc || !doc.uploaded) return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType: originalMediaType(doc.fileName),
        headers: {
          'Content-Disposition': attachmentOf(doc.fileName),
          'X-Content-Type-Options': 'nosniff',
        },
        body: doc.bytes ?? Buffer.alloc(0),
      });
    }
    match = /^\/inventory\/scope3\/runs\/(\d+)\/result$/.exec(path);
    if (match && method === 'GET') {
      const run = runs.find((one) => one.id === Number(match![1]));
      if (!run || run.result === null) return refusal(route, 404, 'not_found');
      if (statusOf(run) !== 'done') return refusal(route, 409, 'run_not_done');
      return answer(route, 200, run.result);
    }
    const reply = ledger.answerOf(method, path, url.searchParams, body);
    if (reply) return answer(route, reply.status, reply.body);
    if (key === 'GET /inventory/scope3/template') {
      if (server === 'base') return refusal(route, 404, 'NOT_FOUND');
      return route.fulfill({
        status: 200,
        contentType:
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers: {
          // 실서버 꼴: filename*=utf-8''<퍼센트> 하나(scope3_runs.py — Django content_disposition_header).
          'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(TEMPLATE_NAME)}`,
        },
        body: TEMPLATE_BYTES,
      });
    }
    return refusal(route, 404, 'NOT_FOUND');
  });

  const keys = () => calls.map((call) => `${call.method} ${call.path}`);
  const count = (key: string) => keys().filter((one) => one === key).length;
  const runBodies = () =>
    calls
      .filter((call) => call.method === 'POST' && call.path === '/runs')
      .map((call) => call.body as Json & { options: Json });
  return { calls, keys, count, runBodies, runs, runOut, ledger };
}
