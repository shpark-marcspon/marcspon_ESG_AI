// 시험용 가짜 Scope 3 서버(밴드 S3W1 ①). 시험만 쓴다(공개 표면이 아니다). 값은 전부 지어낸 것이다(받은 템플릿·코랩 출력 0).
// 답의 꼴은 api-py 의 core 경로(/documents 셋·/runs 셋 — generated)와 짝 서버 밴드 S3K1 의 계약(발주서 S3K1 §1-4)을 따른다. 판 둘:
//   server 's3k1'(기본) — S3K1 병합 뒤: POST /runs 의 options.reportYear 검사(빠짐·정수 아님·1990 앞·올해 뒤 400 INVALID_OPTIONS) ·
//     운영 관리자 실행 열림 · GET /inventory/scope3/template 200 xlsx 바이트(Content-Disposition 첨부) ·
//     GET /inventory/scope3/runs/{id}/result(S3W2a): done 이 아니면 409 run_not_done · 없음·결과 null 이면 404 not_found · 그 밖 200 결과 본문
//     (실행마다 result, 기본 fakeDoneResult()). 실패 실행의 errorCode 는 실행마다(기본 internal), failedStep 은 단계 code 면 c1 · 실행기 code 면 null.
//   server 'base' — BASE 그대로: inventory 에 끼움이 없어 POST /runs 422 FLOW_NOT_RUNNABLE · 운영 관리자 403 FORBIDDEN(먼저) · 양식 404.
// 그 밖 규칙: POST /documents 는 sizeBytes 가 uploadLimit 를 넘으면 413 upload_too_large(소문자 — 서버 그대로) · 올리지 않은 문서로 실행 409
//   DOCUMENT_NOT_UPLOADED · module·flowId 가 아니면 422 UNKNOWN_FLOW · 같은 Idempotency-Key·같은 본문이면 앞 실행 201 ·
//   resumeFromRunId 를 실으면 422 VALIDATION_ERROR(화면은 이어 돌기를 쓰지 않는다 — 감독 86 10-30) ·
//   company 옵션이면 /documents·/runs 는 그 회사 거절(400·404). 실행은 대본(runScripts — 만든 차례마다 하나, 기본 queued → processing → done)을
//   GET /runs/{id} 한 번마다 한 칸씩 걷는다(끝 칸에 머문다). 목록(GET /runs)은 새 것(id 큰 것) 먼저, 요약에 연도·options 칸은 없다(서버 그대로).
// 지금 결과(S3W3a ①): GET …/years/{y}·…/runs/{id}/edits·history · POST·DELETE …/lock · POST …/exclusions·restorations·factors 는 서버 규칙을 그대로 거울한다
//   (actions/scope3_state.py·scope3_edits.py — 기준 실행 = 새 것부터 첫 「done + 결과 done」, 잠기면 핀, 판정 차례 ②~⑩, 합은 Decimal 정확합 글자).
//   GET 연도는 판(server)·실행 유무와 상관없이 답한다(첫 화면 [다음]도 570 문을 지난다). 계수 고침의 셈(식)은 흉내 내지 않는다 — 고른 값의 co2e 는 FAKE_EDITED_CO2E.
//   실행 시드 edits·옵션 locks 로 사건·잠금을 두고, 거절은 override 로 준다(refusal 의 셋째 칸이 422 fields).
// Bearer 는 보지 않는다. override 에 「메서드 경로」 → 답을 주면 그 경로는 그 답을 낸다(차례대로 쓰는 목록도 된다).
import { createApi } from '../../../shared/api/index.ts';
import {
  RUN_STEP_NAMES,
  SCOPE3_FLOW_ID,
  SCOPE3_MODULE,
} from '../model/index.ts';
import type { RunStatus } from '../model/index.ts';
import { createScope3Port } from './server.ts';
import type { Scope3Port } from './server.ts';

export interface FakeScope3Call {
  method: string;
  path: string;
  query: URL['searchParams'];
  headers: Headers;
  body: unknown;
}

type Answer = () => Response | Promise<Response>;

export const json = (status: number, body: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
export const refusal = (
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  json(status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });
export const unreachable = (): Response => {
  throw new TypeError('fetch failed');
};

/** 회사 거절 셋(서버 그대로의 상태·code). */
const COMPANY = {
  ambiguous: () => refusal(400, 'COMPANY_AMBIGUOUS'),
  inactive: () => refusal(400, 'COMPANY_INACTIVE'),
  not_found: () => refusal(404, 'COMPANY_NOT_FOUND'),
} as const;

/** 지어낸 양식 바이트(엑셀 꼴이 아니다 — 받은 템플릿을 싣지 않는다). */
export const FAKE_TEMPLATE_BYTES = new Uint8Array([
  0x50, 0x4b, 0x03, 0x04, 0x53, 0x33,
]);
/** 지어낸 양식 이름(Content-Disposition filename* 로 나간다). */
export const FAKE_TEMPLATE_NAME = '지어낸 Scope3 양식.xlsx';
export const XLSX_MEDIA_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
/** 원본 경로의 꼴(S3Q1 — 서버 actions/scope3_runs.py ORIGINAL_MEDIA_TYPES 거울: 올린 이름 끝, 그 밖 octet-stream). */
export const originalMediaType = (fileName: string) => {
  const dot = fileName.lastIndexOf('.');
  const tail = dot < 0 ? '' : fileName.slice(dot).toLowerCase();
  return (
    tail === '.xlsx' ? XLSX_MEDIA_TYPE
    : tail === '.xls' ? 'application/vnd.ms-excel'
    : 'application/octet-stream'
  );
};
/** 서버 content_disposition_header 거울(RFC 6266): ASCII 이름은 filename="…"(따옴표·역빗금 escape), 아니면 filename*=utf-8''<퍼센트>. */
export const attachmentOf = (fileName: string) =>
  /^[\x20-\x7e]*$/.test(fileName) ?
    `attachment; filename="${fileName.replace(/[\\"]/g, '\\$&')}"`
  : `attachment; filename*=utf-8''${encodeURIComponent(fileName)}`;
/** 올린 바이트가 없는 시드 문서의 원본(지어낸 바이트 — 엑셀로 열지 않는다). */
export const FAKE_ORIGINAL_BYTES = new Uint8Array([
  0x50, 0x4b, 0x03, 0x04, 0x4f, 0x52,
]);

/** 실행기가 정하는 errorCode(failedStep null — api-py runs/calc/errors.py). */
const RUNNER_ERROR_CODES = [
  'flow_not_runnable',
  'document_missing',
  'object_missing',
  'object_changed',
  'object_too_large',
  'storage_denied',
  'storage_unconfigured',
  'attempts_exhausted',
  'result_too_large',
  'versions_mismatch',
  'internal',
  'segments_mismatch',
] as const;
/** 단계가 실패한 errorCode(failedStep 은 그 단계 — 가짜는 c1). */
const STEP_ERROR_CODES: readonly string[] = [
  'options_rejected',
  'flow_input_invalid',
  'step_output_invalid',
  'embedding_failed',
  'no_text_layer',
  'setup_error',
  'step_error',
  'segments_failed',
  'segments_empty',
];
/** 가짜가 낼 수 있는 errorCode 전부(= 발주서 S3W2a §1-6 표 = errors.py RUN_ERROR_MESSAGES — 시험이 견준다). */
export const FAKE_ERROR_CODES: readonly string[] = [
  ...RUNNER_ERROR_CODES,
  ...STEP_ERROR_CODES,
];
export type FakeErrorCode = string;
/** 가짜 실패 글(화면에 나오면 안 된다 — 시험이 찾는다). */
export const FAKE_ERROR_MESSAGE = '지어낸-서버-실패-글';
/** 가짜 시트 오류·거절 까닭 글(화면 0). */
export const FAKE_SHEET_ERROR = 'ValueError: 지어낸-시트-오류-글';
export const FAKE_REJECT_DETAIL = 'reader 지어낸-거절-까닭-글';

// ── 결과 본문(scope3.colab.result@1) — 값은 전부 지어낸 것. 칸은 generated/openapi.json 과 같다(server.test.ts 가 걸어 내려가며 견준다). ──
type J = Record<string, unknown>;
const origin = (step: string, from = 'ai'): J => ({
  origin: from,
  step,
  via: '지어낸',
});
/** 그룹 단계가 규칙표(계수 단계는 ai — 별은 group 단계로만 가른다)·물러선 그룹인 구매 줄의 칸(밴드 S3W4 ①). */
export const ruleGroupSteps: J = {
  originSteps: [origin('group', 'rule'), origin('factor')],
};
export const estimateGroupSteps: J = {
  originSteps: [origin('group', 'estimate'), origin('factor', 'rule')],
};
/** 소각이 아닌 줄의 생물기원 칸(엔진 biogenic_fossil_split 의 「해당없음」 꼴 — fcf 없음). */
export const noBiogenicSplit: J = {
  biogenic: {
    fossilCo2e: '0.5',
    biogenicCo2e: '0',
    fcf: null,
    note: '해당없음',
  },
};
const biogenicOf = (biogenic: string | null): J => ({
  fossilCo2e: '0.5',
  biogenicCo2e: biogenic,
  fcf: '0.1',
  note: '지어낸',
});
const amount: J = {
  value: '1.5',
  unit: 'kg',
  baseValue: '1.5',
  baseUnit: 'kg',
  note: null,
};
const activityFactor: J = {
  title: '지어낸 계수',
  value: '0.25',
  unit: 'kgCO2e/kg',
  column: '지어낸 열',
  sheet: '지어낸 시트',
  code: 'X1',
};
/** 줄의 입력 칸(S3R2 — openapi ColabRowInputJson 의 키 열여섯(S3R3 useMonths), 값은 글이거나 null). */
const rowInput: J = {
  country: '지어낸 나라',
  site: '지어낸 사업장',
  name: '지어낸 품목',
  vehicle: '지어낸 수단',
  energy: '지어낸 에너지',
  people: '3.0',
  buildingArea: '100.0',
  usedArea: '25.0',
  buildingPeople: null,
  ownPeople: null,
  productCount: '7.0',
  sales: null,
  weight: '0.5',
  weightUnit: 'kg',
  stores: null,
  useMonths: '18.0',
};

/** C1·C2 줄(kind purchase). */
export function purchaseRow(
  co2e: string | null,
  rowId = 'p1',
  extra: J = {},
): J {
  return {
    rowId,
    kind: 'purchase',
    month: 1,
    amount: '100',
    spendKrw: '100',
    spendNote: '지어낸',
    co2e,
    unit: 'tCO2eq',
    formula: '지어낸 식',
    factor: {
      title: '지어낸 항목',
      value: '0.1',
      unit: 'kgCO2e/KRW',
      column: '2024',
      source: 'db_keyword',
    },
    group: {
      key: 'g1',
      category: '지어낸',
      family: '지어낸',
      name: '지어낸 묶음',
      reason: '지어낸',
      llm: { answer: '지어낸', outcome: 'success', reason: null },
    },
    recommendations: [
      { title: '지어낸 추천', value: '0.2', expectedCo2e: '0.3' },
      { title: '지어낸 둘째 추천', value: '0.4', expectedCo2e: '0.6' },
    ],
    origin: 'ai',
    originSteps: [origin('group')],
    missing: [],
    input: rowInput,
    ...extra,
  };
}

/** C4·C5·C6·C7·C9 줄. biogenic 은 C5 만(아니면 null). */
export function activityRow(
  kind: string,
  co2e: string | null,
  biogenic?: string | null,
  rowId = 'a1',
  extra: J = {},
): J {
  return {
    rowId,
    kind,
    month: null,
    activity: amount,
    factor: activityFactor,
    co2e,
    unit: 'tCO2eq',
    formula: '지어낸 식',
    treatment: '소각',
    biogenic: biogenic === undefined ? null : biogenicOf(biogenic),
    distance: {
      departure: '지어낸 출발',
      arrival: '지어낸 도착',
      km: '12.5',
      roundTrip: '1',
      trips: '2',
      people: '3',
      workdays: '200',
      geoMode: 'ai',
      via: '지어낸',
    },
    mode: { value: 'train', origin: 'rule' },
    origin: 'rule',
    originSteps: [origin('mapping')],
    missing: [],
    input: rowInput,
    ...extra,
  };
}

/** C3·C8·C11~C15 줄. biogenic 은 C12 만(아니면 null). */
export function energyRow(
  kind: string,
  co2e: string | null,
  biogenic?: string | null,
  rowId = 'e1',
  extra: J = {},
): J {
  return {
    rowId,
    kind,
    month: null,
    activity: amount,
    factor: activityFactor,
    co2e,
    unit: 'tCO2eq',
    formula: '지어낸 식',
    match: { type: '지어낸', score: '0.9' },
    allocation: {
      method: '지어낸',
      areaRatio: '0.5',
      personRatio: null,
      buildingTotal: '10',
    },
    product: { totalUsage: '10', years: '5' },
    investment: { share: '0.1', scope1: '1', scope2: '2' },
    biogenic: biogenic === undefined ? null : biogenicOf(biogenic),
    origin: 'estimate',
    originSteps: [origin('unit')],
    missing: ['factorValue'],
    input: rowInput,
    ...extra,
  };
}

export const processedSheet = (
  sheet: string,
  category: string,
  rows: J[],
): J => ({ status: 'processed', sheet, category, rows });
export const failedSheet = (sheet: string, category: string): J => ({
  status: 'failed',
  sheet,
  category,
  error: FAKE_SHEET_ERROR,
});

/** done 결과 본문. sheets·llmCalls 를 바꿔 끼운다. 기본은 카테고리마다 작은 값 하나(C10 없음 — 서버 그대로). */
export function fakeDoneResult({
  sheets,
  llmCalls = { classify: { success: 2 } },
  reportYear = 2025,
}: { sheets?: J[]; llmCalls?: J; reportYear?: number } = {}): J {
  return {
    status: 'done',
    schemaVersion: 'scope3.colab.result@1',
    reportYear,
    factorBook: {
      sheet: '지어낸 계수표',
      column: '2024',
      year: 2024,
      reload: 'reloaded',
      reloadProblem: null,
    },
    factorSheets: [
      { sheet: '지어낸 계수표', header: 1, rows: 3, read: 'reloaded' },
    ],
    llmCalls,
    sheets: sheets ?? [
      processedSheet('s1', 'Category1', [purchaseRow('1.5')]),
      processedSheet('s2', 'Category2', [purchaseRow('2.5')]),
      processedSheet('s3', 'Category3', [energyRow('fuel_energy', '3.5')]),
      processedSheet('s4', 'Category4', [
        activityRow('transport_distance', '4.5'),
      ]),
      processedSheet('s5', 'Category5', [activityRow('waste', '5.5', '0.25')]),
      processedSheet('s6', 'Category6', [activityRow('travel_spend', '6.5')]),
      processedSheet('s7', 'Category7', [activityRow('commute', '7.5')]),
      processedSheet('s8', 'Category8', [energyRow('leased_asset', '8.5')]),
      processedSheet('s9', 'Category9', [
        activityRow('transport_spend', '9.5'),
      ]),
      processedSheet('s11', 'Category11', [energyRow('product_use', '11.5')]),
      processedSheet('s12', 'Category12', [
        energyRow('product_eol', '12.5', '0.75'),
      ]),
      processedSheet('s13', 'Category13', [
        energyRow('leased_out_asset', '13.5'),
      ]),
      processedSheet('s14', 'Category14', [energyRow('franchise', '14.5')]),
      processedSheet('s15', 'Category15', [energyRow('investment', '15.5')]),
    ],
  };
}

/** 지어낸 출처 글(서버 sourceText 자리 — 실제 책 글 0). */
export const FAKE_SOURCE_TEXT = '지어낸 기관 배출계수 고시 2099';
export const FAKE_C3_NOTE = '지어낸 지침 갑(업스트림) 0.5-0.4';
export const FAKE_C12_CODE = '91-01-01';
export const FAKE_C12_NAME = '지어낸 폐용기';

/**
 * C12 처리방법별 값(S3Q1 — openapi ColabC12TreatmentsJson 꼴). 갈래 넷: code·name(비중 셋, used 셋) · average(비중이 하나도 없음 —
 * share null·used false·shareTotal null) · nan(MARC-ISSUE-390 — 빈 비중 칸이 NaN: share null 인데 used true, 합 null, 줄 계수도 null).
 */
export function fakeTreatments(branch: 'code' | 'name' | 'average' | 'nan'): J {
  if (branch === 'average')
    return {
      branch: 'average',
      shareTotal: null,
      parts: [
        { treatment: '매립', share: null, factor: '0.17', used: false },
        { treatment: '소각', share: null, factor: '1.17', used: false },
        { treatment: '재활용', share: null, factor: '0.02', used: false },
      ],
    };
  return {
    branch: branch === 'nan' ? 'code' : branch,
    shareTotal: branch === 'nan' ? null : '1.0',
    parts: [
      {
        treatment: '매립',
        share: branch === 'nan' ? null : '0.1',
        factor: '0.013',
        used: true,
      },
      { treatment: '소각', share: '0.125', factor: '3.4', used: true },
      { treatment: '재활용', share: '0.775', factor: '0.0186', used: true },
    ],
  };
}

/** C12 줄 하나(S3Q1). 계수 값은 가중 계수(줄의 factor.value — 합계 줄이 그대로 쓴다). */
export const c12Row = (
  rowId: string,
  treatments: J | undefined,
  {
    value = '0.5' as string | null,
    code = FAKE_C12_CODE as string | null,
    name = FAKE_C12_NAME as string | null,
  } = {},
): J => ({
  ...energyRow('product_eol', '1.25', '0.5', rowId, {
    factor: {
      ...activityFactor,
      sheet: '폐기물_C12',
      title: null,
      value,
      unit: 'kgCO2eq/kg',
      column: null,
      code,
    },
    input: { ...rowInput, name },
  }),
  ...(treatments === undefined ? {} : { treatments }),
});

/**
 * S3Q1 의 새 칸을 담은 done 본문(가짜 ↔ openapi 대조·창 시험): C12 줄 다섯(code·name·average·nan·옛 줄(칸 없음))과 C3 줄 둘(sourceText
 * 있음·없음)·C5 줄(sourceText 있음).
 */
export function fakeS3Q1Result(): J {
  return fakeDoneResult({
    sheets: [
      processedSheet('c12_지어낸', 'Category12', [
        c12Row('c12_지어낸!3', fakeTreatments('code')),
        c12Row('c12_지어낸!4', fakeTreatments('name'), { code: null }),
        c12Row('c12_지어낸!5', fakeTreatments('average'), { name: null }),
        c12Row('c12_지어낸!6', fakeTreatments('nan'), { value: null }),
        c12Row('c12_지어낸!7', undefined),
      ]),
      processedSheet('c3_지어낸', 'Category3', [
        energyRow('fuel_energy', '3', undefined, 'c3_지어낸!3', {
          factor: {
            ...activityFactor,
            sheet: '에너지_C3',
            title: FAKE_FUEL,
            sourceText: FAKE_C3_NOTE,
          },
        }),
        energyRow('fuel_energy', '4', undefined, 'c3_지어낸!4', {
          factor: { ...activityFactor, sheet: '에너지_C3', title: FAKE_FUEL },
        }),
      ]),
      processedSheet('c5_지어낸', 'Category5', [
        activityRow('waste', '5', '0.25', 'c5_지어낸!3', {
          factor: {
            ...activityFactor,
            sheet: '지어낸 시트',
            sourceText: FAKE_SOURCE_TEXT,
          },
        }),
      ]),
    ],
  });
}

/** 다섯 시트 갈래·줄 kind 열넷을 다 담은 done 본문(가짜 ↔ openapi 대조용). */
export function fakeAllShapesResult(): J {
  return fakeDoneResult({
    llmCalls: { classify: { success: 3, 'failed:refusal': 1 } },
    sheets: [
      processedSheet('s1', 'Category1', [purchaseRow('1e-05')]),
      processedSheet('s4a', 'Category4', [
        activityRow('transport_distance', '1'),
        activityRow('transport_spend', '2'),
      ]),
      processedSheet('s5', 'Category5', [activityRow('waste', '1', '0.5')]),
      processedSheet('s6', 'Category6', [
        activityRow('travel_distance', '1'),
        activityRow('travel_spend', '1'),
        activityRow('commute', '1'),
      ]),
      processedSheet('s3', 'Category3', [
        energyRow('fuel_energy', '1'),
        energyRow('leased_asset', '1'),
        energyRow('leased_out_asset', '1'),
        energyRow('product_use', '1'),
        energyRow('product_eol', '1', '0.5'),
        energyRow('franchise', '1'),
        energyRow('investment', null),
        purchaseRow('1', 'p2', ruleGroupSteps),
        purchaseRow('1', 'p3', { ...estimateGroupSteps, formula: '' }),
        activityRow('waste', '1', '0', 'a2', noBiogenicSplit),
      ]),
      { status: 'not_target', sheet: 's-guide' },
      {
        status: 'not_yet_supported',
        sheet: 's-later',
        category: 'Category11',
        band: 'S3C-c',
      },
      { status: 'empty', sheet: 's-empty', category: 'Category14' },
      failedSheet('s-bad', 'Category15'),
    ],
  });
}

/** 입력 칸 열여섯이 다 null 인 판(openapi ColabRowInputJson 의 키 — 처리기에 없는 열은 null). */
const INPUT_NULLS: J = {
  country: null,
  site: null,
  name: null,
  vehicle: null,
  energy: null,
  people: null,
  buildingArea: null,
  usedArea: null,
  buildingPeople: null,
  ownPeople: null,
  productCount: null,
  sales: null,
  weight: null,
  weightUnit: null,
  stores: null,
  useMonths: null,
};
/** 시트 앞머리 → 그 처리기가 채우는 입력 키(엔진 colab_157/serialize.py 의 원천 표 — S3R2 §C0 표). */
export const FAKE_INPUT_KEYS: Record<string, readonly string[]> = {
  c1: ['country', 'site', 'name'],
  c2: ['country', 'site', 'name'],
  c3: ['country', 'site', 'energy'],
  'c4-1': ['country', 'site', 'name'],
  'c4-2': ['country', 'site', 'name', 'vehicle'],
  c5: ['country', 'site', 'name'],
  'c6-1': ['country', 'site', 'people'],
  'c6-2': ['country', 'site', 'vehicle', 'people'],
  c7: ['country', 'site', 'people'],
  'c8-1': ['country', 'name', 'energy'],
  'c8-2': ['country', 'name', 'energy', 'buildingArea', 'usedArea'],
  'c8-3': ['country', 'name', 'energy', 'buildingPeople', 'ownPeople'],
  'c9-1': ['country', 'site', 'name'],
  'c9-2': ['country', 'site', 'name', 'vehicle'],
  c11: ['country', 'name', 'energy', 'productCount', 'useMonths'],
  c12: ['country', 'name', 'sales', 'weight', 'weightUnit'],
  'c13-1': ['country', 'name', 'energy'],
  'c13-2': ['country', 'name', 'energy', 'buildingArea', 'usedArea'],
  'c13-3': ['country', 'name', 'energy', 'buildingPeople', 'ownPeople'],
  c14: ['country', 'name', 'energy', 'stores'],
  c15: ['name'],
};
const INPUT_WORDS: Record<string, string> = {
  country: '나라',
  site: '사업장',
  name: '이름',
  vehicle: '수단',
  energy: '에너지',
};
/** 수 키의 지어낸 값(서버처럼 repr(float) 글자 — 「13.0」 꼴). */
const INPUT_NUMBERS: Record<string, string> = {
  people: '3.0',
  buildingArea: '120.0',
  usedArea: '30.0',
  buildingPeople: '40.0',
  ownPeople: '4.0',
  productCount: '7.0',
  sales: '1250.0',
  weight: '0.5',
  weightUnit: 'kg',
  stores: '2.0',
  useMonths: '18.0',
};
/** 그 시트 처리기의 입력 칸(글은 「지어낸 나라 c1」 꼴 — 시트마다 다르다). overrides 로 칸을 덮는다(null 섞기). */
export function fakeInput(head: string, overrides: J = {}): J {
  const out: J = { ...INPUT_NULLS };
  for (const key of FAKE_INPUT_KEYS[head] ?? [])
    out[key] = INPUT_NUMBERS[key] ?? `지어낸 ${INPUT_WORDS[key]} ${head}`;
  return { ...out, ...overrides };
}
/** S3R3 앞(093f16c3~)에 저장된 결과의 입력 칸 — 키 열다섯(useMonths 없음, 감독 처분 Q3: 응답은 통과·웹은 null 취급). */
export function fifteenKeyInput(input: J): J {
  const { useMonths: _useMonths, ...rest } = input;
  void _useMonths;
  return rest;
}
/** 옛 결과의 줄(input 칸 없음 — S3R2 앞 결과). */
export function withoutInput(row: J): J {
  const { input: _input, ...rest } = row;
  void _input;
  return rest;
}

/** 상세 표 시험용 이름(지어낸 — 앞머리 c4-1 꼴만 엔진 양식과 같다). */
export const FAKE_GROUP_A = '지어낸 묶음 가';
export const FAKE_GROUP_B = '지어낸 묶음 나';
/** 수단 칸 — 서버는 정규화 코드를 준다(ColabModeJson.value · 엔진 travel_mode.py). 화면은 이름표(GX3 ④). */
export const FAKE_MODE = 'bus';
export const FAKE_TREATMENT = '지어낸 처리';
export const FAKE_FUEL = '지어낸 연료';
/** 시트 이름 — 앞머리(c1·c4-1 …)는 엔진 SHEET_PROCESSOR_MAP 의 앞머리, 뒤는 지어낸 글자(대소문자 섞음 — 실데이터는 대문자 C). */
export const detailSheetName = (head: string) => `${head}_지어낸`;
const mode = (value: string | null): J =>
  value === null ? { mode: null } : { mode: { value, origin: 'rule' } };
const travel = (
  km: string,
  people: string,
  trips: string,
  workdays: string | null,
): J => ({
  distance: {
    departure: null,
    arrival: null,
    km,
    roundTrip: '2',
    people,
    trips,
    workdays,
    geoMode: null,
    via: 'input',
  },
});
const noDistance: J = { distance: null };
const fuel = (title: string): J => ({ factor: { ...activityFactor, title } });

/**
 * 상세 표용 done 본문(S3W2b ① · S3W2c ① 입력 칸): 시트 꼴 21 전부 · 줄 kind 열넷 · empty(C6 의 둘째 c6-2 시트) · failed(C4 의 둘째 c4-2 시트 — C4 일부 실패) ·
 * origin estimate 줄(C3 빼고 에너지 줄 기본·C5 하나) · 같은 엑셀 줄 #n(C1) · 지수 수 글자 · C9-2 수단 null · C15 계수 null. 값은 지어낸 것.
 */
export function fakeDetailResult(): J {
  const body = detailBase();
  // 입력 칸(S3W2c ①): 줄마다 그 시트 처리기의 키에 시트마다 다른 지어낸 값. 갈래 넷을 섞는다 —
  //   C1 둘째 줄 site null · C1 셋째 줄 옛 줄(칸 없음) · C5 둘째 줄 name null · C13-1 옛 줄(에너지 열이 계수 이름으로 물러섬) ·
  //   C13-3 energy null(빈 칸 — 계수 이름으로 메우지 않음) · C11 줄은 키 열다섯 옛 판(S3R3 앞 저장 — useMonths 없음, 감독 처분 Q3).
  for (const sheet of body.sheets as J[]) {
    if (sheet.status !== 'processed') continue;
    const head = /^(c\d{1,2}(?:-\d)?)_/i.exec(String(sheet.sheet))![1]!;
    sheet.rows = (sheet.rows as J[]).map((row) => ({
      ...row,
      input: fakeInput(head.toLowerCase()),
    }));
  }
  const rowsOf = (head: string) =>
    (body.sheets as J[]).find((one) => one.sheet === detailSheetName(head))!
      .rows as J[];
  // 창(밴드 S3W4 ①): C1 첫 줄 AI 그룹 · 둘째 줄 규칙 그룹 · 셋째 줄 물러선 그룹 · C12 줄 「해당없음」·빈 산식.
  const c1 = rowsOf('c1');
  c1[1] = {
    ...c1[1]!,
    ...ruleGroupSteps,
    input: fakeInput('c1', { site: null }),
  };
  c1[2] = withoutInput({ ...c1[2]!, ...estimateGroupSteps });
  const c12 = rowsOf('c12');
  c12[0] = {
    ...c12[0]!,
    biogenic: { ...(noBiogenicSplit.biogenic as J), biogenicCo2e: '0.75' },
    formula: '',
  };
  const c5 = rowsOf('c5');
  c5[1] = { ...c5[1]!, input: fakeInput('c5', { name: null }) };
  const c131 = rowsOf('c13-1');
  c131[0] = withoutInput(c131[0]!);
  const c133 = rowsOf('c13-3');
  c133[0] = { ...c133[0]!, input: fakeInput('c13-3', { energy: null }) };
  const c11 = rowsOf('c11');
  c11[0] = { ...c11[0]!, input: fifteenKeyInput(fakeInput('c11')) };
  return body;
}

/** 상세 표용 done 본문의 뼈(입력 칸은 fakeDetailResult 가 덮는다). */
function detailBase(): J {
  const n = detailSheetName;
  return fakeDoneResult({
    llmCalls: { classify: { success: 9 } },
    sheets: [
      processedSheet(n('c1'), 'Category1', [
        purchaseRow('3', `${n('c1')}!5`, {
          group: { ...(purchaseRow('0').group as J), name: FAKE_GROUP_A },
        }),
        purchaseRow('1', `${n('c1')}!6#1`, {
          group: { ...(purchaseRow('0').group as J), name: FAKE_GROUP_B },
        }),
        purchaseRow('1e-05', `${n('c1')}!6#2`, {
          group: { ...(purchaseRow('0').group as J), name: FAKE_GROUP_A },
        }),
      ]),
      processedSheet(n('C2'), 'Category2', [purchaseRow('2', `${n('C2')}!4`)]),
      processedSheet(n('c3'), 'Category3', [
        energyRow('fuel_energy', '3', undefined, `${n('c3')}!7`, {
          ...fuel(FAKE_FUEL),
          origin: 'rule',
        }),
      ]),
      processedSheet(n('c4-1'), 'Category4', [
        activityRow('transport_distance', '4', undefined, `${n('c4-1')}!8`, {
          ...travel('120.5', '1', '1', null),
          ...mode(FAKE_MODE),
        }),
      ]),
      processedSheet(n('c4-2'), 'Category4', [
        activityRow('transport_spend', '2', undefined, `${n('c4-2')}!3`, {
          ...noDistance,
          ...mode(null),
          origin: 'estimate',
        }),
      ]),
      failedSheet(`${n('c4-2')} 둘`, 'Category4'),
      processedSheet(n('c5'), 'Category5', [
        activityRow('waste', '5', '1.25', `${n('c5')}!9`, {
          treatment: FAKE_TREATMENT,
          origin: 'estimate',
          ...noDistance,
          mode: null,
        }),
        activityRow('waste', '15', '0.5', `${n('c5')}!10`, {
          treatment: '지어낸 다른 처리',
          ...noDistance,
          mode: null,
        }),
      ]),
      processedSheet(n('c6-1'), 'Category6', [
        activityRow('travel_distance', '6', undefined, `${n('c6-1')}!3`, {
          ...travel('300', '2', '4', null),
          ...mode(FAKE_MODE),
        }),
      ]),
      processedSheet(n('c6-2'), 'Category6', [
        activityRow('travel_spend', '0.5', undefined, `${n('c6-2')}!3`, {
          ...noDistance,
          ...mode(FAKE_MODE),
        }),
      ]),
      { status: 'empty', sheet: `${n('c6-2')} 둘`, category: 'Category6' },
      processedSheet(n('c7'), 'Category7', [
        activityRow('commute', '7', undefined, `${n('c7')}!3`, {
          ...travel('12.5', '30', '1', '220'),
          ...mode(FAKE_MODE),
        }),
      ]),
      processedSheet(n('c8-1'), 'Category8', [
        energyRow(
          'leased_asset',
          '8',
          undefined,
          `${n('c8-1')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c8-2'), 'Category8', [
        energyRow(
          'leased_asset',
          '0.5',
          undefined,
          `${n('c8-2')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c8-3'), 'Category8', [
        energyRow(
          'leased_asset',
          '0.25',
          undefined,
          `${n('c8-3')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c9-1'), 'Category9', [
        activityRow('transport_distance', '9', undefined, `${n('c9-1')}!3`, {
          ...travel('45', '1', '1', null),
          ...mode(FAKE_MODE),
        }),
      ]),
      processedSheet(n('c9-2'), 'Category9', [
        activityRow('transport_spend', '1', undefined, `${n('c9-2')}!3`, {
          ...noDistance,
          ...mode(null),
        }),
      ]),
      processedSheet(n('c11'), 'Category11', [
        energyRow(
          'product_use',
          '11',
          undefined,
          `${n('c11')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c12'), 'Category12', [
        energyRow('product_eol', '12', '0.75', `${n('c12')}!3`),
      ]),
      processedSheet(n('c13-1'), 'Category13', [
        energyRow(
          'leased_out_asset',
          '13',
          undefined,
          `${n('c13-1')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c13-2'), 'Category13', [
        energyRow(
          'leased_out_asset',
          '1',
          undefined,
          `${n('c13-2')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c13-3'), 'Category13', [
        energyRow(
          'leased_out_asset',
          '2',
          undefined,
          `${n('c13-3')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c14'), 'Category14', [
        energyRow(
          'franchise',
          '14',
          undefined,
          `${n('c14')}!3`,
          fuel(FAKE_FUEL),
        ),
      ]),
      processedSheet(n('c15'), 'Category15', [
        energyRow('investment', '15', undefined, `${n('c15')}!3`, {
          factor: null,
        }),
      ]),
      { status: 'not_target', sheet: 's-guide' },
    ],
  });
}

/** rejected 결과 본문. */
export const fakeRejectedResult = (reason = 'reader_problem'): J => ({
  status: 'rejected',
  schemaVersion: 'scope3.colab.result@1',
  rejected: { reason, detail: FAKE_REJECT_DETAIL },
});

/** 시험이 심는 앞 실행. */
export interface FakeRunSeed {
  id: number;
  status: RunStatus;
  reportYear: number | null;
  documentId?: number;
  flowId?: string;
  module?: string;
  /** GET /runs/{id} 한 번마다 걷는 대본(없으면 status 하나에 머문다). */
  script?: RunStatus[];
  /** 실패일 때의 errorCode(FAKE_ERROR_CODES 안. 기본 internal). */
  errorCode?: FakeErrorCode;
  /** 결과 본문(null 이면 404). 기본 fakeDoneResult(). */
  result?: unknown;
  /** 이 실행에 미리 둔 사건(S3W3a — 다른 실행에는 안 붙는다). */
  edits?: FakeRowEdit[];
}

/** 미리 둔 줄 사건 하나. excluded 면 제외 사건, factor 면 계수 사건(둘 다면 둘). */
export interface FakeRowEdit {
  rowId: string;
  /** 「C1」 꼴. */
  category: string;
  excluded?: boolean;
  factor?: J;
  /** 고친 사람(null = 못 찾음). 기본 FAKE_EDITOR. */
  by?: J | null;
}

/** 미리 둔 잠금. */
export interface FakeLockSeed {
  year: number;
  category: string;
  runId: number;
  /** 잠근 사람(이름은 빈 글자일 수 있다). 기본 FAKE_EDITOR. */
  by?: { id: string; name: string };
}

export interface FakeScope3ServerOptions {
  server?: 's3k1' | 'base';
  /** 운영 관리자 세션(base 판이면 POST /runs 403). */
  operator?: boolean;
  company?: keyof typeof COMPANY;
  /** 서버 올리기 상한(바이트). 기본 20MB. */
  uploadLimit?: number;
  /** 서울 올해(INVALID_OPTIONS 의 「올해 뒤」). */
  thisYear?: number;
  /** 만든 차례마다 실행 대본(없으면 queued → processing → done). */
  runScripts?: RunStatus[][];
  /** 만든 차례마다 실패 errorCode(기본 internal). */
  runErrors?: FakeErrorCode[];
  /** 만든 차례마다 결과 본문(null 이면 404, 기본 fakeDoneResult()). */
  runResults?: unknown[];
  runs?: FakeRunSeed[];
  /** 미리 둔 잠금(S3W3a). */
  locks?: FakeLockSeed[];
  baseUrl?: string;
}

interface StoredRun {
  id: number;
  module: string;
  flowId: string;
  documentId: number | null;
  options: Record<string, unknown>;
  script: RunStatus[];
  at: number;
  createdAt: string;
  errorCode: FakeErrorCode;
  result: unknown;
}

/** 줄 사건(서버 inventory_scope3_row_events 꼴 — 지우지 않고 쌓는다). */
interface FakeEvent {
  id: number;
  runId: number;
  rowId: string;
  category: string;
  kind: 'exclude' | 'restore' | 'factor';
  reason: string;
  at: string;
  by: J | null;
  batchId: string | null;
  factor: J | null;
}

const DEFAULT_SCRIPT: RunStatus[] = ['queued', 'processing', 'done'];
const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isSafeInteger(value);

const isRecord = (value: unknown): value is J =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** 서버 CATEGORIES(C1~C15, C10 뺌). */
const FAKE_CATEGORIES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15].map(
  (n) => `C${n}`,
);
/** 식이 있는 줄 kind(서버 _FORMULAS + waste). product_eol·investment 는 식이 없어 409 다(sid:MARC-ENT-579). */
const FAKE_FORMULA_KINDS = [
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
const FAKE_FACTOR_KEYS = ['rowId', 'choice', 'rank', 'custom', 'reason'];
const FAKE_CUSTOM_KEYS = ['title', 'value', 'source'];
const FAKE_FACTOR_CHOICES = ['applied', 'recommended', 'custom'];
const FAKE_VALUE = /^[0-9]+(?:\.([0-9]+))?$/;
const YEAR_FIRST = 1990;
const YEAR_LAST = 2100;

/** 고친 사람·잠근 사람 기본. */
export const FAKE_EDITOR = { id: '7', name: '지어낸 담당자' };
/** 추천·직접 입력으로 고른 줄의 배출량(식은 흉내 내지 않는다 — 칸이 모자란 줄·본문과 글자가 다른 줄·schemaVersion·flow 어긋남의 409 도 그래서 없다). */
export const FAKE_EDITED_CO2E = '7.25';
export const FAKE_EDITED_BIOGENIC = '0.75';

/** 계수 사건의 값(Scope3RowEditFactorOut 칸 그대로). 값은 지어낸 것이다. */
export const fakeRowFactor = (overrides: J = {}): J => ({
  choice: 'custom',
  rank: null,
  title: '지어낸 고친 계수',
  value: '0.5',
  source: '지어낸 출처',
  unit: 'kgCO2e/KRW',
  co2e: FAKE_EDITED_CO2E,
  biogenicCo2e: null,
  ai: {
    title: '지어낸 원안 계수',
    value: '0.25',
    source: '지어낸 시트',
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
  const found = typeof text === 'string' ? FAKE_VALUE.exec(text) : null;
  if (found === null || (found[1] ?? '').length > 10) return false;
  const value = Number(text);
  return Number.isFinite(value) && value > 0;
}

/** 서버 _source: 계수의 시트 이름. 구매 줄은 sheet 칸이 없어 factorBook.sheet + factor.column. */
function factorSource(factor: J, book: unknown): string | null {
  if (typeof factor.sheet === 'string') return factor.sheet;
  const name =
    isRecord(book) && typeof book.sheet === 'string' ? book.sheet : null;
  if (name === null || typeof factor.column !== 'string') return name;
  return `${name} ${factor.column.replaceAll('\n', ' ')}`;
}

/** 서버 chosen: 고름 → 사건 값. 그 줄에 없는 추천 순위면 null. */
function chosenFactor(b: J, row: J, book: unknown): J | null {
  const factor = row.factor as J;
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
    co2e: FAKE_EDITED_CO2E,
    biogenicCo2e:
      row.kind !== 'waste' ? null
      : biogenic?.fcf === null || biogenic?.fcf === undefined ? '0.0'
      : FAKE_EDITED_BIOGENIC,
  };
  if (isRecord(b.custom))
    return {
      ...shared,
      ...edited,
      title: reasonText(b.custom.title),
      value: storedValue(b.custom.value as string),
      source: reasonText(b.custom.source),
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

const reasonText = (value: unknown) =>
  typeof value === 'string' ? value.trim() : '';
/** 서버 _custom_problems 의 글 칸: 걷고 1~200자(코드 포인트). */
const badText = (value: unknown) => {
  const size = [...reasonText(value)].length;
  return size < 1 || size > 200;
};

/** 판정 ①(서버 StrictIn + check_factor_body). 칸 이름 → 글. */
function factorBodyFields(b: J): Record<string, string[]> {
  const fields: Record<string, string[]> = {};
  for (const key of FAKE_FACTOR_KEYS)
    if (!(key in b)) fields[key] = ['지어낸-칸 없음'];
  for (const key of Object.keys(b))
    if (!FAKE_FACTOR_KEYS.includes(key)) fields[key] = ['지어낸-더한 칸'];
  if (typeof b.rowId !== 'string') fields.rowId = ['지어낸-줄'];
  if (!FAKE_FACTOR_CHOICES.includes(b.choice as string))
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
      if (!FAKE_CUSTOM_KEYS.includes(key))
        fields[`custom.${key}`] = ['지어낸-더한 칸'];
    for (const cell of ['title', 'source'])
      if (badText(asked[cell])) fields[`custom.${cell}`] = ['지어낸-칸'];
    if (!goodValue(asked.value)) fields['custom.value'] = ['지어낸-값'];
  }
  const size = [...reasonText(b.reason)].length;
  if (size < 1 || size > 300) fields.reason = ['지어낸-사유'];
  return fields;
}

const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/;

/** 수 글자 → (정수, 소수 자리). 서버 number 와 같은 꼴만 — 그 밖은 null. */
function decimalOf(text: unknown): { digits: bigint; scale: number } | null {
  const found = typeof text === 'string' ? DECIMAL.exec(text) : null;
  if (!found) return null;
  const [, sign, whole, fraction = '', exponent = '0'] = found;
  const raw = BigInt(`${whole}${fraction}`);
  const scale = fraction.length - +exponent;
  const digits = sign === '-' ? -raw : raw;
  return scale >= 0 ?
      { digits, scale }
    : { digits: digits * 10n ** BigInt(-scale), scale: 0 };
}

/**
 * 서버 sum_or_none + decimal_text 의 거울: 수 글자들의 정확합을 지수 없는 글자로(끝 0 걷음). 수가 하나도 없으면 null.
 * JS 수로 더하지 않는다(String(1e-7) 은 지수 꼴이고 0.1+0.2 는 어긋난다).
 */
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

/** RunOut.steps 꼴(서버: 실행을 만들 때부터 전부 선언 차례로). 처리 중이면 읽을 때마다 한 단계씩. done·total 은 null 이거나 호출 수(늘 같다). */
function fakeSteps(status: string, at: number, stepFailed: boolean): J[] {
  return RUN_STEP_NAMES.map((step, index) => {
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
    return { step, status: state, done: calls, total: calls, segments: null };
  });
}

export function fakeScope3Server({
  server = 's3k1',
  operator = false,
  company,
  uploadLimit = 20 * 1024 * 1024,
  thisYear = 2026,
  runScripts = [],
  runErrors = [],
  runResults = [],
  runs = [],
  locks = [],
  baseUrl = 'http://test.local/api',
}: FakeScope3ServerOptions = {}) {
  const calls: FakeScope3Call[] = [];
  const override: Record<string, Answer | Answer[]> = {};
  /** 문서: id → 올렸나·확인했나·바이트. */
  const documents = new Map<
    number,
    {
      fileName: string;
      sizeBytes: number;
      reportYear: unknown;
      uploaded: boolean;
      bytes: Uint8Array | null;
    }
  >();
  const stored: StoredRun[] = runs.map((seed) => ({
    id: seed.id,
    module: seed.module ?? SCOPE3_MODULE,
    flowId: seed.flowId ?? SCOPE3_FLOW_ID,
    documentId: seed.documentId ?? null,
    options: seed.reportYear === null ? {} : { reportYear: seed.reportYear },
    script: seed.script ?? [seed.status],
    at: 0,
    createdAt: `2026-01-${String((seed.id % 28) + 1).padStart(2, '0')}T00:00:00Z`,
    errorCode: seed.errorCode ?? 'internal',
    result: seed.result === undefined ? fakeDoneResult() : seed.result,
  }));
  for (const code of [
    ...runs.map((seed) => seed.errorCode ?? 'internal'),
    ...runErrors,
  ])
    if (!FAKE_ERROR_CODES.includes(code))
      throw new Error(`가짜에 없는 errorCode ${code}`);
  for (const seed of runs)
    if (seed.documentId !== undefined && !documents.has(seed.documentId))
      documents.set(seed.documentId, {
        fileName: '지어낸.xlsx',
        sizeBytes: 1,
        reportYear: seed.reportYear,
        uploaded: true,
        bytes: null,
      });
  let nextDocument = 101;
  let nextRun = Math.max(500, ...stored.map((run) => run.id)) + 1;
  let made = 0;
  const keys = new Map<string, { body: string; id: number }>();
  const events: FakeEvent[] = [];
  let nextEvent = 1;
  let nextBatch = 1;
  const addEvent = (
    event: Omit<FakeEvent, 'id' | 'at' | 'by'> & { by?: J | null },
  ) => {
    const id = nextEvent++;
    events.push({
      by: FAKE_EDITOR,
      ...event,
      id,
      at: `2026-03-01T00:${String(Math.floor(id / 60) % 60).padStart(2, '0')}:${String(id % 60).padStart(2, '0')}Z`,
    });
  };
  for (const seed of runs)
    for (const edit of seed.edits ?? []) {
      const line = {
        runId: seed.id,
        rowId: edit.rowId,
        category: edit.category,
        reason: '지어낸 사유',
        batchId: `batch-${nextBatch++}`,
        ...(edit.by === undefined ? {} : { by: edit.by }),
      };
      if (edit.excluded) addEvent({ ...line, kind: 'exclude', factor: null });
      if (edit.factor)
        addEvent({ ...line, kind: 'factor', factor: edit.factor });
    }
  const lockOf = new Map(
    locks.map((seed) => [
      `${seed.year} ${seed.category}`,
      {
        runId: seed.runId,
        at: '2026-03-02T01:02:03Z',
        by: seed.by ?? FAKE_EDITOR,
      },
    ]),
  );

  const pathOf = (request: Request) =>
    new URL(request.url).pathname.slice(new URL(baseUrl).pathname.length);
  const statusOf = (run: StoredRun) =>
    run.script[Math.min(run.at, run.script.length - 1)]!;
  const runOut = (run: StoredRun) => {
    const status = statusOf(run);
    const finished = status === 'done' || status === 'failed';
    return {
      id: run.id,
      module: run.module,
      flowId: run.flowId,
      documentId: run.documentId,
      options: structuredClone(run.options),
      status,
      steps: fakeSteps(
        status,
        run.at,
        STEP_ERROR_CODES.includes(run.errorCode),
      ),
      files: [],
      resultShapes: [],
      resumedFromRunId: null,
      failedStep:
        status === 'failed' && STEP_ERROR_CODES.includes(run.errorCode) ?
          'c1'
        : null,
      errorCode: status === 'failed' ? run.errorCode : null,
      errorMessage: status === 'failed' ? FAKE_ERROR_MESSAGE : null,
      createdAt: run.createdAt,
      startedAt: status === 'queued' ? null : run.createdAt,
      finishedAt: finished ? run.createdAt : null,
    };
  };
  const documentOut = (id: number) => {
    const doc = documents.get(id)!;
    return {
      id,
      fileName: doc.fileName,
      sizeBytes: doc.sizeBytes,
      reportYear: isInt(doc.reportYear) ? doc.reportYear : null,
      previousDocumentId: null,
      status: doc.uploaded ? 'uploaded' : 'awaiting_upload',
      pageCount: null,
      hasText: null,
      etag: null,
      createdAt: '2026-01-01T00:00:00Z',
      uploadedAt: doc.uploaded ? '2026-01-01T00:00:00Z' : null,
    };
  };

  // ── 지금 결과(S3W3a): 서버 fold·excluded_of·co2e_of·edited_rows·base_run·category_value 의 거울 ──

  /** (실행, 줄, 축) → 그 축의 지금 상태 사건(가장 큰 id). */
  const folded = (runId: number) => {
    const found = new Map<string, FakeEvent>();
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
  const isDoneResult = (body: unknown): body is J & { sheets: unknown[] } =>
    isRecord(body) && body.status === 'done' && Array.isArray(body.sheets);
  /** 만든 차례(새 것 먼저) 후보에서 latest 와 R. */
  const baseOf = (year: number) => {
    const candidates = stored
      .filter(
        (run) =>
          run.module === SCOPE3_MODULE &&
          run.flowId === SCOPE3_FLOW_ID &&
          run.options.reportYear === year,
      )
      .sort((a, b) => b.id - a.id);
    return {
      latest: candidates[0] ?? null,
      base:
        candidates.find(
          (run) => statusOf(run) === 'done' && isDoneResult(run.result),
        ) ?? null,
    };
  };
  const sheetsOf = (run: StoredRun, category: string) =>
    (isDoneResult(run.result) ? run.result.sheets : []).filter(
      (sheet): sheet is J =>
        isRecord(sheet) && sheet.category === `Category${category.slice(1)}`,
    );
  const rowsIn = (run: StoredRun, category: string) =>
    sheetsOf(run, category)
      .filter((sheet) => sheet.status === 'processed')
      .flatMap((sheet) => sheet.rows as J[]);
  const currentOf = (year: number, category: string) => {
    const lock = lockOf.get(`${year} ${category}`);
    const runId = lock ? lock.runId : baseOf(year).base?.id;
    if (runId === undefined) return null;
    const run = stored.find((one) => one.id === runId)!;
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
    const lock = lockOf.get(`${year} ${category}`);
    const current = currentOf(year, category);
    const runId = current === null ? null : +current.runId;
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
    const categories = FAKE_CATEGORIES.map((one) => categoryOut(year, one));
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
  /** 사건이 있는 줄의 지금 상태(rowId 차례). only 를 주면 그 줄만. */
  const rowStates = (runId: number, only?: readonly string[]) => {
    const split = new Map<string, FakeEvent[]>();
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
  const historyOut = (runId: number, url: URL) => {
    const rowId = url.searchParams.get('rowId');
    const page = +(url.searchParams.get('page') ?? '1');
    const pageSize = +(url.searchParams.get('pageSize') ?? '20');
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
  const badYear = (year: number) =>
    year < YEAR_FIRST || year > YEAR_LAST ?
      refusal(422, 'VALIDATION_ERROR', { year: ['지어낸-해'] })
    : null;

  /** 잠그기(서버 lock — 자격 없음 → 실행 없음 → 지금 결과 실행 아님). 이미 잠겼으면 그대로. */
  function lockCategory(year: number, category: string, url: URL): Response {
    const bad = badYear(year);
    if (bad) return bad;
    if (!FAKE_CATEGORIES.includes(category)) return refusal(404, 'NOT_FOUND');
    const runId = +(url.searchParams.get('runId') ?? 'x');
    if (!isInt(runId)) return refusal(422, 'VALIDATION_ERROR');
    const current = currentOf(year, category);
    if (current === null || current.sheets === 0)
      return refusal(409, 'NOT_COMPUTED');
    if (!stored.some((run) => run.id === runId))
      return refusal(404, 'NOT_FOUND');
    if (String(runId) !== current.runId) return refusal(409, 'STALE_RUN');
    const key = `${year} ${category}`;
    if (!lockOf.has(key))
      lockOf.set(key, { runId, at: '2026-03-02T01:02:03Z', by: FAKE_EDITOR });
    return json(200, categoryOut(year, category));
  }

  /** 풀기(서버 unlock — 운영 관리자만, 첫 문장에서). 안 잠겼으면 그대로. */
  function unlockCategory(year: number, category: string): Response {
    if (!operator) return refusal(403, 'FORBIDDEN');
    const bad = badYear(year);
    if (bad) return bad;
    if (!FAKE_CATEGORIES.includes(category)) return refusal(404, 'NOT_FOUND');
    lockOf.delete(`${year} ${category}`);
    return json(200, categoryOut(year, category));
  }

  /** 판정 ②~⑥(서버 _held). 지나면 실행과 해, 아니면 거절. */
  function held(
    runId: number,
    category: string,
  ): { run: StoredRun; year: number } | Response {
    if (!FAKE_CATEGORIES.includes(category)) return refusal(404, 'NOT_FOUND');
    const run = stored.find(
      (one) => one.id === runId && one.module === SCOPE3_MODULE,
    );
    if (!run) return refusal(404, 'NOT_FOUND');
    const year = run.options.reportYear;
    if (!isInt(year)) return refusal(409, 'STALE_RUN');
    if (lockOf.has(`${year} ${category}`)) return refusal(409, 'LOCKED');
    if (baseOf(year).base?.id !== runId) return refusal(409, 'STALE_RUN');
    return { run, year };
  }

  const reasonOf = (value: unknown) =>
    typeof value === 'string' ? value.trim() : '';
  const badReason = (reason: string) =>
    [...reason].length < 1 || [...reason].length > 300;

  /** 제외·복구(서버 _edit). 이미 그 상태인 줄은 건너뛴다. */
  function editRows(
    runId: number,
    category: string,
    kind: 'exclude' | 'restore',
    body: unknown,
  ): Response {
    const b = isRecord(body) ? body : {};
    const rowIds = b.rowIds;
    const reason = reasonOf(b.reason);
    const fields: Record<string, string[]> = {};
    if (
      !Array.isArray(rowIds) ||
      rowIds.length === 0 ||
      rowIds.length > 2000 ||
      new Set(rowIds).size !== rowIds.length
    )
      fields.rowIds = ['지어낸-줄'];
    if (badReason(reason)) fields.reason = ['지어낸-사유'];
    if (Object.keys(fields).length > 0)
      return refusal(422, 'VALIDATION_ERROR', fields);
    const found = held(runId, category);
    if (found instanceof Response) return found;
    const ids = rowIds as string[];
    const known = rowsIn(found.run, category).map((row) => row.rowId);
    if (!ids.every((id) => known.includes(id)))
      return refusal(422, 'VALIDATION_ERROR', { rowIds: ['지어낸-줄'] });
    const excluded = excludedOf(runId, category);
    const batchId = `batch-${nextBatch++}`;
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
    return json(200, {
      category: categoryOut(found.year, category),
      rows: rowStates(runId, ids),
    });
  }

  /** 계수 고르기(서버 factor). 판정 차례: 몸 422 → 404 → 잠김 → stale → 줄 없음 422 → 409 → 없는 순위 422 → 같은 고름이면 사건 0. */
  function editFactor(
    runId: number,
    category: string,
    body: unknown,
  ): Response {
    const b = isRecord(body) ? body : {};
    const fields = factorBodyFields(b);
    if (Object.keys(fields).length > 0)
      return refusal(422, 'VALIDATION_ERROR', fields);
    const reason = reasonText(b.reason);
    const found = held(runId, category);
    if (found instanceof Response) return found;
    const row = rowsIn(found.run, category).find(
      (one) => one.rowId === b.rowId,
    );
    if (!row) return refusal(422, 'VALIDATION_ERROR', { rowId: ['지어낸-줄'] });
    if (
      !FAKE_FORMULA_KINDS.includes(row.kind as string) ||
      !isRecord(row.factor) ||
      typeof row.factor.unit !== 'string'
    )
      return refusal(409, 'FACTOR_NOT_EDITABLE');
    const rowId = b.rowId as string;
    const result = found.run.result;
    const factor = chosenFactor(
      { ...b, rank: b.rank ?? null },
      row,
      isRecord(result) ? result.factorBook : null,
    );
    if (factor === null)
      return refusal(422, 'VALIDATION_ERROR', { rank: ['지어낸-순위'] });
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
        batchId: `batch-${nextBatch++}`,
        factor,
      });
    return json(200, {
      category: categoryOut(found.year, category),
      rows: rowStates(runId, [rowId]),
    });
  }

  function createRun(body: unknown, key: string | null): Response {
    const b = (body ?? {}) as Record<string, unknown>;
    if (server === 'base' && operator) return refusal(403, 'FORBIDDEN');
    // resumeFromRunId 422 는 화면이 안 쓰는 길을 막는 가짜 규칙 — 실서버는 이어 돌기.
    if ('resumeFromRunId' in b) return refusal(422, 'VALIDATION_ERROR');
    if (b.module !== SCOPE3_MODULE || b.flowId !== SCOPE3_FLOW_ID)
      return refusal(422, 'UNKNOWN_FLOW');
    if (server === 'base') return refusal(422, 'FLOW_NOT_RUNNABLE');
    if (!isInt(b.documentId)) return refusal(422, 'DOCUMENT_REQUIRED');
    const doc = documents.get(b.documentId);
    if (!doc) return refusal(404, 'NOT_FOUND');
    if (!doc.uploaded) return refusal(409, 'DOCUMENT_NOT_UPLOADED');
    const options = b.options;
    const year =
      typeof options === 'object' && options !== null ?
        (options as Record<string, unknown>).reportYear
      : undefined;
    if (!isInt(year) || year < 1990 || year > thisYear)
      return refusal(400, 'INVALID_OPTIONS');
    const text = JSON.stringify(b);
    if (key !== null) {
      const before = keys.get(key);
      if (before)
        return before.body === text ?
            json(201, { id: before.id, status: 'queued' })
          : refusal(409, 'IDEMPOTENCY_KEY_REUSED');
    }
    const run: StoredRun = {
      id: nextRun++,
      module: SCOPE3_MODULE,
      flowId: SCOPE3_FLOW_ID,
      documentId: b.documentId,
      options: structuredClone(options as Record<string, unknown>),
      script: runScripts[made] ?? DEFAULT_SCRIPT,
      at: 0,
      createdAt: '2026-02-01T00:00:00Z',
      errorCode: runErrors[made] ?? 'internal',
      result:
        runResults[made] === undefined ? fakeDoneResult() : runResults[made],
    };
    made += 1;
    stored.push(run);
    if (key !== null) keys.set(key, { body: text, id: run.id });
    return json(201, { id: run.id, status: statusOf(run) });
  }

  function answer(
    method: string,
    path: string,
    url: URL,
    body: unknown,
    headers: Headers,
  ): Response {
    const key = `${method} ${path}`;
    const companyGate =
      /^\/(documents|runs|inventory\/scope3\/(runs|years))/.test(path) &&
      company;
    if (companyGate) return COMPANY[company]();
    if (key === 'POST /documents') {
      const b = (body ?? {}) as Record<string, unknown>;
      if (typeof b.fileName !== 'string' || !isInt(b.sizeBytes))
        return refusal(422, 'VALIDATION_ERROR');
      if (b.sizeBytes > uploadLimit) return refusal(413, 'upload_too_large');
      const id = nextDocument++;
      documents.set(id, {
        fileName: b.fileName,
        sizeBytes: b.sizeBytes,
        reportYear: b.reportYear,
        uploaded: false,
        bytes: null,
      });
      return json(201, {
        document: documentOut(id),
        upload: {
          url: `https://storage.test/put/${id}`,
          method: 'PUT',
          headers: {},
          expiresAt: '2026-01-01T01:00:00Z',
        },
      });
    }
    const confirm = /^\/documents\/(\d+)\/confirm$/.exec(path);
    if (method === 'POST' && confirm) {
      const id = +confirm[1]!;
      const doc = documents.get(id);
      if (!doc) return refusal(404, 'NOT_FOUND');
      if (doc.bytes === null) return refusal(409, 'OBJECT_MISSING');
      doc.uploaded = true;
      return json(200, { document: documentOut(id) });
    }
    if (key === 'POST /runs')
      return createRun(body, headers.get('Idempotency-Key'));
    if (key === 'GET /runs') {
      // 운영 관리자 목록 — 실서버는 빈 쪽(runs.py).
      const module = url.searchParams.get('module');
      const limit = +(url.searchParams.get('limit') ?? '20');
      const offset = +(url.searchParams.get('offset') ?? '0');
      const rows = stored
        .filter((run) => module === null || run.module === module)
        .sort((a, b) => b.id - a.id);
      return json(200, {
        count: rows.length,
        isNext: offset + limit < rows.length,
        results: rows.slice(offset, offset + limit).map((run) => ({
          id: run.id,
          module: run.module,
          flowId: run.flowId,
          documentId: run.documentId,
          documentName:
            run.documentId === null ?
              null
            : (documents.get(run.documentId)?.fileName ?? null),
          status: statusOf(run),
          createdAt: run.createdAt,
          finishedAt: null,
        })),
      });
    }
    const one = /^\/runs\/(\d+)$/.exec(path);
    if (method === 'GET' && one) {
      const run = stored.find((r) => r.id === +one[1]!);
      if (!run) return refusal(404, 'NOT_FOUND');
      const out = runOut(run);
      run.at += 1;
      return json(200, out);
    }
    const result = /^\/inventory\/scope3\/runs\/(\d+)\/result$/.exec(path);
    if (method === 'GET' && result) {
      const run = stored.find((r) => r.id === +result[1]!);
      if (!run || run.result === null) return refusal(404, 'not_found');
      if (statusOf(run) !== 'done') return refusal(409, 'run_not_done');
      return json(200, structuredClone(run.result));
    }
    const original = /^\/inventory\/scope3\/runs\/(\d+)\/original$/.exec(path);
    if (method === 'GET' && original) {
      // S3Q1: 서버 갈래 거울 — 없음·다른 모듈·문서 없음·안 올라옴은 404(실행 상태는 보지 않는다).
      const run = stored.find((r) => r.id === +original[1]!);
      const doc =
        run && run.module === SCOPE3_MODULE && run.documentId !== null ?
          documents.get(run.documentId)
        : undefined;
      if (!doc || !doc.uploaded) return refusal(404, 'NOT_FOUND'); // 서버 code 는 대문자로 온다(config/api.py)
      return new Response(doc.bytes ?? FAKE_ORIGINAL_BYTES, {
        status: 200,
        headers: {
          'Content-Type': originalMediaType(doc.fileName),
          'Content-Disposition': attachmentOf(doc.fileName),
          'X-Content-Type-Options': 'nosniff',
        },
      });
    }
    const yearPath = /^\/inventory\/scope3\/years\/(\d+)$/.exec(path);
    if (method === 'GET' && yearPath) {
      const year = +yearPath[1]!;
      return badYear(year) ?? json(200, yearOut(year));
    }
    const lockPath =
      /^\/inventory\/scope3\/years\/(\d+)\/categories\/([^/]+)\/lock$/.exec(
        path,
      );
    if (method === 'POST' && lockPath)
      return lockCategory(+lockPath[1]!, lockPath[2]!, url);
    if (method === 'DELETE' && lockPath)
      return unlockCategory(+lockPath[1]!, lockPath[2]!);
    const runRead = /^\/inventory\/scope3\/runs\/(\d+)\/(edits|history)$/.exec(
      path,
    );
    if (method === 'GET' && runRead) {
      const runId = +runRead[1]!;
      if (!stored.some((run) => run.id === runId))
        return refusal(404, 'NOT_FOUND');
      return json(
        200,
        runRead[2] === 'edits' ?
          { runId: String(runId), rows: rowStates(runId) }
        : historyOut(runId, url),
      );
    }
    const edit =
      /^\/inventory\/scope3\/runs\/(\d+)\/categories\/([^/]+)\/(exclusions|restorations|factors)$/.exec(
        path,
      );
    if (method === 'POST' && edit) {
      const [, runId, category, what] = edit;
      if (what === 'factors') return editFactor(+runId!, category!, body);
      return editRows(
        +runId!,
        category!,
        what === 'exclusions' ? 'exclude' : 'restore',
        body,
      );
    }
    if (key === 'GET /inventory/scope3/template') {
      if (server === 'base') return refusal(404, 'NOT_FOUND');
      return new Response(FAKE_TEMPLATE_BYTES, {
        status: 200,
        headers: {
          'Content-Type': XLSX_MEDIA_TYPE,
          'Content-Disposition': `attachment; filename="scope3.xlsx"; filename*=UTF-8''${encodeURIComponent(FAKE_TEMPLATE_NAME)}`,
          'X-Content-Type-Options': 'nosniff',
        },
      });
    }
    return refusal(404, 'NOT_FOUND');
  }

  const send = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = pathOf(request);
    const key = `${request.method} ${path}`;
    const text = await request.clone().text();
    const body: unknown = text === '' ? undefined : JSON.parse(text);
    calls.push({
      method: request.method,
      path,
      query: url.searchParams,
      headers: request.headers,
      body,
    });
    const replaced = override[key];
    if (Array.isArray(replaced)) {
      const next = replaced.shift();
      if (next) return next();
    } else if (replaced) return replaced();
    return answer(request.method, path, url, body, request.headers);
  };

  /** 서명 주소 올리기(경로 컴포넌트의 sendUpload 자리). 문서 id 의 바이트를 쥔다. */
  const sendUpload = async (url: string, method: string, file: File) => {
    calls.push({
      method,
      path: url,
      query: new URL(url).searchParams,
      headers: new Headers(),
      body: undefined,
    });
    const id = /\/put\/(\d+)$/.exec(url);
    const doc = id ? documents.get(+id[1]!) : undefined;
    if (method !== 'PUT' || !doc) throw new Error('upload failed 404');
    doc.bytes = new Uint8Array(await file.arrayBuffer());
  };

  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  /** 그 경로로 나간 본문들(차례대로). */
  const bodies = (key: string) =>
    calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.body);

  return {
    send,
    sendUpload,
    calls,
    count,
    bodies,
    override,
    /** 올린 문서의 바이트(올리지 않았으면 null). */
    uploaded: (id: number) => documents.get(id)?.bytes ?? null,
    /** 지금 실행(만든 차례). */
    runs: () => stored.map((run) => runOut({ ...run })),
  };
}

export type FakeScope3Server = ReturnType<typeof fakeScope3Server>;

/** 가짜 서버 앞에 둔 포트(시험이 진짜 createApi 로 잇는다 — 실어댑터 그대로, 양식 경로도 S3W2a 부터 실어댑터). */
export function portOf(
  server: FakeScope3Server,
  {
    baseUrl = 'http://test.local/api',
    newKey,
    newLaunchKey,
  }: {
    baseUrl?: string;
    newKey?: () => string;
    newLaunchKey?: () => string;
  } = {},
): Scope3Port {
  const api = createApi({ baseUrl, fetch: server.send });
  return createScope3Port({
    api,
    sendUpload: server.sendUpload,
    ...(newKey ? { newKey } : {}),
    ...(newLaunchKey ? { newLaunchKey } : {}),
  });
}
