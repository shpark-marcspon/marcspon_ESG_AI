// Scope 1·2 입력의 꼴과 셈(밴드 W12-1a ② — 서버 S12a, sid:MARC-ENT-469 2·4). React·DOM·통신을 모른다. W12-1b(S3 상세)가 그대로 쓴다.
//   - 꼴: 서버 Entry*Out 그대로(응답 id 는 글자 — sid:MARC-ISSUE-92). 금액·배출량은 **글자**로 들고 다니고 숫자로 바꾸지 않는다
//     (표시 반올림·합도 글자 셈 — 단 cardOf 의 고리 비율 한 줄만 표시용 수).
//   - 보내는 칸 규칙(발주서 1-4 B1): 서버는 「준 칸만 바꿈」이 칸 단위라 칸 안에서 빠진 열쇠는 기본값으로 덮인다 —
//     그래서 실는 칸은 늘 amount(지금 글자 또는 null)·estimated 둘 다, 행은 늘 unit·na·siteFacilityId. 바뀌지 않은 칸은 싣지 않는다.
//     새 행은 rowId 없이. 요청 id 는 정수(toRequestId — 정수 글자가 아니면 던진다, 어댑터가 failed 로 받음). 이 규칙은 rowBody 한 곳.
//   - 422 칸 열쇠(서버 config/api.py field_name): rows.<i>.values.<j>.amount · rows.<i>.unit · rows.<i>.siteFacilityId · rows.<i>.rowId ·
//     memo · decimals · q — i·j 는 보낸 본문 차례(화면 차례 아님). fieldOf 가 본문으로 행·칸을 되찾는다.
//   - 칸은 서버가 블록마다 주는 slots(S12a-2 — 월 12·분기 4·연 1). 화면은 그것으로 그린다. slotsOf(year) 는 월 칸 셈 도우미로만 남았다(W12-1b).
import { toRequestId } from './ids.ts';

/** 한 번 저장의 행 수 상한(서버 MAX_ROWS_PER_SAVE). */
export const ENTRY_SAVE_MAX = 200;
/** 메모 글자 수 상한(서버 MEMO_MAX). */
export const ENTRY_MEMO_MAX = 2000;
/** 계수 바꿈·계수 줄 복구 사유 글자 수 상한(서버 REASON_MAX — 앞뒤 빈칸을 지운 뒤, W12-3 ③). */
export const ENTRY_REASON_MAX = 500;
/** 리스트 검색 q 글자 수 상한(서버 Q_MAX). */
export const ENTRY_SEARCH_MAX = 100;
/** 표시 소수 자릿수 범위·기본(서버 DECIMALS_RANGE·DEFAULT_DECIMALS). */
export const DECIMALS_RANGE = { min: 0, max: 3 } as const;
export const DECIMALS_DEFAULT = 2;
/** 금액 소수 자릿수 상한(서버 AMOUNT_DECIMALS). */
export const AMOUNT_DECIMALS = 6;
/** 히스토리 종류 가운데 웹이 아는 것(서버 HISTORY_KINDS). 밖의 종류도 받아 넘긴다(S12a-2 가 늘림). */
export const HISTORY_KINDS = [
  'value',
  'na_on',
  'na_off',
  'unit',
  'period',
  'factor',
] as const;
export type KnownHistoryKind = (typeof HISTORY_KINDS)[number];
/** 입력주기(서버 PERIODS — EntryPeriodIn.period). S7 이 고르는 셋(W12-2). */
export const ENTRY_PERIODS = ['month', 'quarter', 'year'] as const;
export type EntryPeriod = (typeof ENTRY_PERIODS)[number];

/** 해 → 글자|null(열쇠는 해 글자 「2025」). */
export type EntryValues = Readonly<Record<string, string | null>>;

export interface EntryYear {
  year: number;
  configured: boolean;
}

export interface EntryListRow {
  /** 잎(자산/시설 코드) id. */
  nodeId: string;
  /** 배출범위 → 배출원 유형 → 배출활동 → 자산/시설(넷). */
  path: string[];
  values: EntryValues;
  hasMemo: boolean;
  estimated: boolean;
  locked: boolean;
}

export interface EntryScope {
  scopeId: string;
  scopeName: string;
  values: EntryValues;
  rows: EntryListRow[];
}

/** 리스트 응답(EntryRowsOut). configured 거짓 = 그 해에 숨기지 않은 고른 잎 0(scopes 빔). */
export interface EntryRows {
  year: number;
  /** 표 머리 세 해(Y-2·Y-1·Y — 서버가 정함). */
  years: number[];
  decimals: number;
  unit: string;
  configured: boolean;
  scopes: EntryScope[];
}

export interface EntrySlot {
  /** 「YYYY-MM」. */
  slot: string;
  amount: string | null;
  estimated: boolean;
}

export interface EntryRow {
  rowId: string;
  siteFacilityId: string;
  detailName: string;
  unit: string;
  na: boolean;
  values: EntrySlot[];
  emission: string | null;
  emissionProblem: string | null;
  /** 이 행만의 계수(null 이면 상세 factor — 밴드 W12-1b, 서버 S12a-2). */
  factor: EntryFactor | EntryCustomFactor | null;
}

export interface EntryFacility {
  /** 사업장 자산/시설(siteFacilityId). */
  id: string;
  detailName: string;
  /** 이미 행이 있음(새 행을 세울 수 없음). */
  hasRow: boolean;
}

export interface EntrySite {
  siteId: string;
  siteName: string;
  facilities: EntryFacility[];
  rows: EntryRow[];
  /** 입력주기(month·quarter·year — 바꿈은 port.period, S7). */
  period: string;
  /** 그 주기의 칸(행 values 는 이 칸만 — 웹이 셈하지 않는다). */
  slots: string[];
}

export interface EntryUnit {
  kind: string;
  unit: string;
}

export interface EntryGas {
  gas: string;
  enabled: boolean;
  factor: string | null;
  gwp: string | null;
}

export interface EntryFactor {
  factorId: string;
  versionId: string;
  version: number;
  name: string;
  source: string;
  isCustom: boolean;
  inputUnit: EntryUnit;
  ncvEnabled: boolean;
  ncv: string | null;
  ncvUnit: EntryUnit | null;
  factorUnit: string;
  gases: EntryGas[];
}

/** 직접입력 계수(판 version 이 없다). */
export interface EntryCustomFactor {
  customId: string;
  name: string;
  source: string;
  baseYear: number;
  tier: number;
  countryCode: string;
  industryCode: string;
  inputUnit: EntryUnit;
  ncvEnabled: boolean;
  ncv: string | null;
  ncvUnit: EntryUnit | null;
  factorUnit: string;
  gases: EntryGas[];
  note: string;
  isCustom: boolean;
}

/** 히스토리 factor 줄의 계수 이름표. */
export interface EntryFactorRef {
  versionId: string | null;
  customId: string | null;
  name: string;
  isCustom: boolean;
}

export interface EntrySiteTotal {
  siteId: string;
  siteName: string;
  values: EntryValues;
}

export interface EntryTotals {
  years: number[];
  all: EntryValues;
  bySite: EntrySiteTotal[];
}

/** 상세 응답(EntryIndexOut). */
export interface EntryIndex {
  year: number;
  nodeId: string;
  name: string;
  path: string[];
  decimals: number;
  unit: string;
  unitOptions: string[];
  factor: EntryFactor;
  locked: boolean;
  lockedAt: string | null;
  lockedBy: { id: string; name: string } | null;
  memo: string;
  sites: EntrySite[];
  totals: EntryTotals;
}

export interface EntryHistory {
  historyId: string;
  at: string;
  /** 아는 것은 HISTORY_KINDS — 그 밖도 글자 그대로(화면은 「변경했어요」 한 줄). */
  kind: string;
  slot: string | null;
  unit: string;
  before: string | null;
  after: string | null;
  actor: { kind: string; id: string | null; name: string | null };
  reason: string | null;
  /** 서버가 셈한 복구 가능(value·period·factor · 안 잠김 · 그 행의 맨 위 줄 아님 · 낡지 않음). 보는 사람 kind 는 모른다. */
  restorable: boolean;
  beforeFactor: EntryFactorRef | null;
  afterFactor: EntryFactorRef | null;
}

export interface EntryHistoryPage {
  count: number;
  totalPages: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrevious: boolean;
  results: EntryHistory[];
}

// ── 요청 본문(EntrySaveIn·EntryRowIn·EntrySlotIn) ──────────────────────────
export interface EntrySlotBody {
  slot: string;
  amount: string | null;
  estimated: boolean;
}

export interface EntryRowBody {
  /** 있는 행만(새 행은 싣지 않는다). */
  rowId?: number;
  siteFacilityId: number;
  unit: string;
  na: boolean;
  values: EntrySlotBody[];
}

export interface EntrySaveBody {
  rows: EntryRowBody[];
}

/** 화면이 고친 행 하나(있는 행이면 rowId, 새 행이면 null). */
export interface EntryRowEdit {
  rowId: string | null;
  siteFacilityId: string;
  unit: string;
  na: boolean;
  values: readonly EntrySlot[];
}

export const isKnownHistoryKind = (kind: string): kind is KnownHistoryKind =>
  (HISTORY_KINDS as readonly string[]).includes(kind);

/** 그 해의 월 칸 열둘(「YYYY-MM」 — 서버 slots). */
export function slotsOf(year: number): string[] {
  const head = `${year}`.padStart(4, '0');
  return Array.from(
    { length: 12 },
    (_, index) => `${head}-${`${index + 1}`.padStart(2, '0')}`,
  );
}

/** 리스트 한 줄의 세로 합침 칸 수(배출원 유형·배출활동) — 묶음 첫 줄은 그 묶음 줄 수, 덮인 줄은 0. */
export interface ListSpan {
  source: number;
  activity: number;
}

/**
 * 리스트 묶음(발주서 2-2): 서버 차례 그대로 이웃한 줄끼리 배출원 유형(path[1])을, 그 안에서 배출활동(path[2])을 세로로 합친다.
 * 차례를 다시 매기지 않는다 — 떨어진 같은 이름은 다른 묶음.
 */
export function listSpans(rows: readonly EntryListRow[]): ListSpan[] {
  const spans: ListSpan[] = rows.map(() => ({ source: 0, activity: 0 }));
  let source = 0;
  let activity = 0;
  for (let index = 1; index <= rows.length; index += 1) {
    const prev = rows[index - 1]!;
    const row = rows[index];
    const sameSource = row !== undefined && row.path[1] === prev.path[1];
    if (!sameSource || row.path[2] !== prev.path[2]) {
      spans[activity]!.activity = index - activity;
      activity = index;
    }
    if (!sameSource) {
      spans[source]!.source = index - source;
      source = index;
    }
  }
  return spans;
}

const EMPTY_SLOT = { amount: null, estimated: false } as const;

/**
 * 고친 행 → 보낼 행(보내는 칸 규칙 — 머리 글). before 는 서버에 있는 그 행(새 행이면 null).
 * 바뀐 칸(금액이나 추정이 다름)만 싣고, 실는 칸은 amount·estimated 둘 다. 행은 늘 unit·na·siteFacilityId.
 * 있는 행에서 단위·N/A·칸이 하나도 안 바뀌었으면 null(보낼 것 없음). 새 행은 늘 보낸다(rowId 없이).
 */
export function rowBody(
  before: EntryRow | null,
  edited: EntryRowEdit,
): EntryRowBody | null {
  const old = new Map((before?.values ?? []).map((slot) => [slot.slot, slot]));
  const values: EntrySlotBody[] = [];
  for (const slot of edited.values) {
    const was = old.get(slot.slot) ?? EMPTY_SLOT;
    if (was.amount === slot.amount && was.estimated === slot.estimated)
      continue;
    values.push({
      slot: slot.slot,
      amount: slot.amount,
      estimated: slot.estimated,
    });
  }
  if (
    before !== null &&
    values.length === 0 &&
    before.unit === edited.unit &&
    before.na === edited.na
  )
    return null;
  const body: EntryRowBody = {
    siteFacilityId: toRequestId(edited.siteFacilityId),
    unit: edited.unit,
    na: edited.na,
    values,
  };
  if (before !== null) body.rowId = toRequestId(before.rowId);
  return body;
}

/** 고친 행들 → 저장 본문(보낼 것 없는 행은 뺀다, 차례 그대로 — fieldOf 의 i). */
export function saveBody(
  pairs: readonly { before: EntryRow | null; edited: EntryRowEdit }[],
): EntrySaveBody {
  const rows: EntryRowBody[] = [];
  for (const { before, edited } of pairs) {
    const row = rowBody(before, edited);
    if (row !== null) rows.push(row);
  }
  return { rows };
}

/** 422 의 rows 칸 하나가 가리키는 자리(본문 차례로 되찾음). */
export interface EntryFieldSpot {
  /** 본문의 행 차례. */
  row: number;
  rowId: string | null;
  siteFacilityId: string;
  /** values 칸이면 그 칸의 「YYYY-MM」, 행 칸이면 null. */
  slot: string | null;
  /** 끝 칸 이름(amount·slot·estimated·unit·na·siteFacilityId·rowId·values …). */
  field: string;
}

const ROW_KEY = /^rows\.([0-9]+)(?:\.values\.([0-9]+))?\.([A-Za-z]+)$/;

/** 열쇠의 차례 글자 → 정수(숫자 글자만 — ROW_KEY 가 거른 것). */
const indexOf = (digits: string) =>
  [...digits].reduce((n, digit) => n * 10 + digit.charCodeAt(0) - 48, 0);

/** 422 칸 열쇠 → 본문의 행·칸. rows.… 꼴이 아니거나 본문에 그 자리가 없으면 null(memo·decimals·q 는 부르는 쪽이 열쇠로 가른다). */
export function fieldOf(
  key: string,
  body: EntrySaveBody,
): EntryFieldSpot | null {
  const match = ROW_KEY.exec(key);
  if (!match) return null;
  const index = indexOf(match[1]!);
  const row = body.rows[index];
  if (!row) return null;
  let slot: string | null = null;
  if (match[2] !== undefined) {
    const value = row.values[indexOf(match[2])];
    if (!value) return null;
    slot = value.slot;
  }
  return {
    row: index,
    rowId: row.rowId === undefined ? null : `${row.rowId}`,
    siteFacilityId: `${row.siteFacilityId}`,
    slot,
    field: match[3]!,
  };
}

const AMOUNT = /^[0-9]{1,18}(\.[0-9]{1,12})?$/;

/**
 * 금액 글자 검사(서버 parse_decimal·amount_problem 사본): 0 이상·지수 0·정수 18자리·소수 6자리. 맞으면 null.
 * 쉼표가 있으면 'comma'(GX2 S12-03 — 글만 가른다. 쉼표를 지워 받지 않는다: 칸은 글자 그대로).
 */
export function checkAmount(
  text: string,
): 'format' | 'comma' | 'decimals' | null {
  if (text.includes(',')) return 'comma';
  if (!AMOUNT.test(text)) return 'format';
  const frac = text.split('.')[1] ?? '';
  return frac.length > AMOUNT_DECIMALS ? 'decimals' : null;
}

/** 새 행을 세울 수 있는 자산/시설(행이 아직 없는 것, 서버 차례). */
export const addable = (site: EntrySite): EntryFacility[] =>
  site.facilities.filter((facility) => !facility.hasRow);

const DECIMAL = /^(-?)([0-9]+)(?:\.([0-9]+))?$/;

/** 숫자 글자들(같은 길이)에 1 을 더한다 — 넘치면 앞에 1. */
function bump(digits: string): string {
  const out = digits.split('');
  for (let index = out.length - 1; index >= 0; index -= 1) {
    if (out[index] !== '9') {
      out[index] = String.fromCharCode(out[index]!.charCodeAt(0) + 1);
      return out.join('');
    }
    out[index] = '0';
  }
  return `1${out.join('')}`;
}

/** 정수부·소수부 → 글자(앞 0·끝 0 걷음, 0 이면 「0」). */
function join(sign: string, int: string, frac: string): string {
  const head = int.replace(/^0+(?=[0-9])/, '');
  const tail = frac.replace(/0+$/, '');
  const text = tail === '' ? head : `${head}.${tail}`;
  return /^0(\.0*)?$/.test(text) ? '0' : `${sign}${text}`;
}

/**
 * 표시 금액(Q5): 서버 글자를 소수 decimals 자리로 반올림(반 올림 — half-up, 글자 셈). null → 「-」, 0 → 「0」.
 * 끝 0 은 붙이지 않는다(서버 글자·시안 「1354.6」 꼴). 숫자 글자가 아니면 그대로.
 */
export function formatAmount(text: string | null, decimals: number): string {
  if (text === null) return '-';
  const match = DECIMAL.exec(text);
  if (!match) return text;
  const [, sign = '', int = '0', frac = ''] = match;
  const places = Math.max(0, Math.min(decimals, 12));
  if (frac.length <= places) return join(sign, int, frac);
  const kept = `${int}${frac.slice(0, places)}`;
  const rounded = frac.charAt(places) >= '5' ? bump(kept) : kept;
  const cut = rounded.length - places;
  return join(sign, rounded.slice(0, cut), rounded.slice(cut));
}

/** 0 이상 십진 글자 둘의 합(글자 셈 — 뜨는 소수 오차 0, 자릿수 제한 0). 하나라도 꼴이 아니면 null. */
export function addAmounts(a: string, b: string): string | null {
  const x = /^([0-9]+)(?:\.([0-9]+))?$/.exec(a);
  const y = /^([0-9]+)(?:\.([0-9]+))?$/.exec(b);
  if (!x || !y) return null;
  const places = Math.max((x[2] ?? '').length, (y[2] ?? '').length);
  const width = Math.max(x[1]!.length, y[1]!.length) + places + 1;
  const left = `${x[1]}${(x[2] ?? '').padEnd(places, '0')}`.padStart(
    width,
    '0',
  );
  const right = `${y[1]}${(y[2] ?? '').padEnd(places, '0')}`.padStart(
    width,
    '0',
  );
  let carry = 0;
  let out = '';
  for (let index = width - 1; index >= 0; index -= 1) {
    const sum =
      left.charCodeAt(index) - 48 + (right.charCodeAt(index) - 48) + carry;
    out = String.fromCharCode(48 + (sum % 10)) + out;
    carry = sum >= 10 ? 1 : 0;
  }
  return join('', out.slice(0, width - places), out.slice(width - places));
}

/** 현황 카드 한 줄(배출범위 하나). */
export interface CardScope {
  scopeId: string;
  scopeName: string;
  /** 그 해 배출량 글자(없으면 null). */
  value: string | null;
  /** 고리에서 차지하는 몫(0~1, 합이 0·없음이면 0) — 표시만. */
  share: number;
}

export interface EmissionCard {
  scopes: CardScope[];
  /** 배출범위 합(글자 십진 더하기 — 값이 하나도 없으면 null). */
  total: string | null;
}

/**
 * 현황 카드(Q11): 배출범위마다 그 해 값 · 합(글자 셈) · 고리 몫. 리스트의 q 없는 응답 scopes 로 부른다(검색은 표만 바꾼다).
 * 합·몫의 자리는 여기 하나다.
 */
export function cardOf(
  scopes: readonly EntryScope[],
  year: number,
): EmissionCard {
  let total: string | null = null;
  let broken = false;
  for (const scope of scopes) {
    const value = scope.values[`${year}`] ?? null;
    if (value === null || broken) continue;
    // 꼴이 아닌 글자가 하나라도 있으면 합은 null 로 끝까지(다시 시작하지 않음 — 검증 A5).
    total = total === null ? addAmounts(value, '0') : addAmounts(total, value);
    broken = total === null;
  }
  return {
    total,
    scopes: scopes.map((scope) => {
      const value = scope.values[`${year}`] ?? null;
      // 표시 비율만(발주서 Q11 — 이 한 줄만 수로 셈)
      const share =
        value === null || total === null ? 0 : Number(value) / Number(total);
      return {
        scopeId: scope.scopeId,
        scopeName: scope.scopeName,
        value,
        share: Number.isFinite(share) ? share : 0,
      };
    }),
  };
}

// ── 밴드 W12-1b ①: S3 상세 입력 도움(칸 머리·행 초안). 본문은 그대로 saveBody — 여기서 본문을 짓지 않는다. ──

const KST_MS = 9 * 3_600_000;

/** 서버 시각 글자 → 「2026-01-02 12:04」(한국 시각). 읽을 수 없으면 받은 글자 그대로. */
export function entryAtText(iso: string): string {
  const time = Date.parse(iso);
  if (Number.isNaN(time)) return iso;
  const text = new Date(time + KST_MS).toISOString();
  return `${text.slice(0, 10)} ${text.slice(11, 16)}`;
}

/** 칸 글자의 뜻(월 「2025-03」 · 분기 「2025-Q2」 · 연 「2025」). 꼴이 아니면 null. */
export type SlotHead =
  | { kind: 'month'; n: number }
  | { kind: 'quarter'; n: number }
  | { kind: 'year' };

const SLOT = /^[0-9]{4}(?:-(?:([0-9]{2})|Q([1-4])))?$/;

export function slotHeadOf(slot: string): SlotHead | null {
  const match = SLOT.exec(slot);
  if (!match) return null;
  if (match[1] !== undefined) return { kind: 'month', n: indexOf(match[1]) };
  if (match[2] !== undefined) return { kind: 'quarter', n: indexOf(match[2]) };
  return { kind: 'year' };
}

/** 화면 표의 행 하나: 서버 행(before — 새 행이면 null)과 고친 값(edited — 칸은 블록 slots 하나마다 하나). */
export interface EntryRowDraft {
  /** 화면 안 열쇠(있는 행 r<id> · 새 행 n<자산/시설 id>). */
  key: string;
  detailName: string;
  before: EntryRow | null;
  edited: EntryRowEdit;
}

export const rowKeyOf = (rowId: string | null, siteFacilityId: string) =>
  rowId === null ? `n${siteFacilityId}` : `r${rowId}`;

/** 서버 행 → 초안. 없는 칸은 빈 칸, slots 밖 칸(옛 주기)은 싣지 않는다. */
export function rowDraftOf(
  row: EntryRow,
  slots: readonly string[],
): EntryRowDraft {
  const old = new Map(row.values.map((value) => [value.slot, value]));
  return {
    key: rowKeyOf(row.rowId, row.siteFacilityId),
    detailName: row.detailName,
    before: row,
    edited: {
      rowId: row.rowId,
      siteFacilityId: row.siteFacilityId,
      unit: row.unit,
      na: row.na,
      values: slots.map((slot) => old.get(slot) ?? { slot, ...EMPTY_SLOT }),
    },
  };
}

/** 고르기로 더한 새 행(화면에만 — 저장 때 rowId 없이 나간다). */
export function newRowDraft(
  facility: EntryFacility,
  unit: string,
  slots: readonly string[],
): EntryRowDraft {
  return {
    key: rowKeyOf(null, facility.id),
    detailName: facility.detailName,
    before: null,
    edited: {
      rowId: null,
      siteFacilityId: facility.id,
      unit,
      na: false,
      values: slots.map((slot) => ({ slot, ...EMPTY_SLOT })),
    },
  };
}

/**
 * S12-03 추정치 단추 하나(sid:MARC-ENT-644, 발주서 Q6): 켜짐 = N/A 아닌 줄의 칸 가운데 하나라도 추정(목록 「추정치」 뜻 — 칸 하나라도).
 * 추정은 서버에 칸마다 저장된다 — 단추는 칸 전부를 한꺼번에 바꾸는 손잡이일 뿐이다.
 */
export function estimatedOn(drafts: readonly EntryRowDraft[]): boolean {
  return drafts.some(
    ({ edited }) =>
      !edited.na && edited.values.some((value) => value.estimated),
  );
}

/**
 * 단추 누름: 켬 = N/A 아닌 줄의 모든 칸(빈 칸 포함)을 추정으로 · 끔 = 모든 줄의 모든 칸 추정 끔(N/A 줄에 남은 옛 추정도).
 * 금액·단위·N/A 는 그대로. 바뀌는 칸이 없으면 같은 초안을 돌려준다.
 */
export function withEstimated(
  draft: EntryRowDraft,
  on: boolean,
): EntryRowDraft {
  if (on && draft.edited.na) return draft;
  if (draft.edited.values.every((value) => value.estimated === on))
    return draft;
  return {
    ...draft,
    edited: {
      ...draft.edited,
      values: draft.edited.values.map((value) =>
        value.estimated === on ? value : { ...value, estimated: on },
      ),
    },
  };
}

/** 고침이 있는 행인가(새 행은 늘 참). rowBody 와 같은 잣대지만 요청 id 를 셈하지 않아 던지지 않는다. */
export function draftEdited({ before, edited }: EntryRowDraft): boolean {
  if (before === null) return true;
  if (before.unit !== edited.unit || before.na !== edited.na) return true;
  const old = new Map(before.values.map((value) => [value.slot, value]));
  return edited.values.some((value) => {
    const was = old.get(value.slot) ?? EMPTY_SLOT;
    return was.amount !== value.amount || was.estimated !== value.estimated;
  });
}

/** 사용자가 고친 것(옛 before 와 다른 칸·unit·na)만 새 서버 행 위에 얹는다 — 손대지 않은 것은 새 값(남이 바꾼 칸을 옛 값으로 되돌려 보내지 않게). */
function rebaseDraft(
  { before, edited }: EntryRowDraft,
  fresh: EntryRowDraft,
): EntryRowDraft {
  const was = new Map(before?.values.map((value) => [value.slot, value]));
  const typed = new Map(edited.values.map((value) => [value.slot, value]));
  return {
    ...fresh,
    edited: {
      ...fresh.edited,
      unit: edited.unit !== before?.unit ? edited.unit : fresh.edited.unit,
      na: edited.na !== before?.na ? edited.na : fresh.edited.na,
      values: fresh.edited.values.map((value) => {
        const mine = typed.get(value.slot);
        if (!mine) return value;
        const old = was.get(value.slot) ?? EMPTY_SLOT;
        return old.amount !== mine.amount || old.estimated !== mine.estimated ?
            mine
          : value;
      }),
    },
  };
}

/**
 * 서버 응답의 블록 위에 아직 저장 안 한 고침을 다시 얹는다(다른 블록·같은 블록의 고침을 지킨다 — 고친 칸만, rebaseDraft).
 * 서버에 없어진 행은 사라지고, 새 행은 그 자산/시설이 아직 비었을 때만 남는다.
 */
export function mergeSiteDraft(
  drafts: readonly EntryRowDraft[],
  site: EntrySite,
): EntryRowDraft[] {
  const kept = new Map(
    drafts.filter(draftEdited).map((draft) => [draft.key, draft]),
  );
  const rows = site.rows.map((row) => {
    const fresh = rowDraftOf(row, site.slots);
    const old = kept.get(fresh.key);
    return old ? rebaseDraft(old, fresh) : fresh;
  });
  const free = new Set(addable(site).map((facility) => facility.id));
  return [
    ...rows,
    ...drafts.filter(
      (draft) => draft.before === null && free.has(draft.edited.siteFacilityId),
    ),
  ];
}

/** 저장 전 칸 검사의 걸림 하나. */
export interface EntryDraftProblem {
  key: string;
  slot: string;
  problem: 'format' | 'comma' | 'decimals';
}

/** 누를 때 검사(화면 차례 — 첫 줄이 초점 갈 칸). 바뀐 칸만 본다. */
export function draftProblems(
  drafts: readonly EntryRowDraft[],
): EntryDraftProblem[] {
  const out: EntryDraftProblem[] = [];
  for (const { key, before, edited } of drafts) {
    const old = new Map(
      (before?.values ?? []).map((value) => [value.slot, value]),
    );
    for (const value of edited.values) {
      if (value.amount === null) continue;
      if (old.get(value.slot)?.amount === value.amount) continue;
      const problem = checkAmount(value.amount);
      if (problem !== null) out.push({ key, slot: value.slot, problem });
    }
  }
  return out;
}

// ── 일괄 올리기(밴드 W12-5 ① — S4). 서버 판정은 actions/scope12_upload.py, 여기는 올리기 전 거름과 답 읽기뿐이다. ──

/** 올리기 본문 상한(바이트, 20MB — 결정 MARC-ENT-593). 서버 이 경로의 상한 GHG_UPLOAD_MAX_BYTES(inventory/tools/xlsx_reader.py)와 같은 값 — 넘으면 413. */
export const ENTRY_UPLOAD_MAX_BYTES = 20 * 1024 * 1024;

/** 올리기 답(EntryUploadOut). added 는 새 행, filled 는 채운 칸, unresolved 는 파일에 나온 잎 전체의 셈 못 한 행. */
export interface EntryUploadResult {
  added: number;
  filled: number;
  unchanged: number;
  unresolved: number;
}

/** 오류 목록 한 줄. where 는 「<시트> 시트 <칸>」, 자리가 없는 줄(file·more·그 밖 열쇠)은 null. */
export interface EntryUploadProblem {
  where: string | null;
  text: string;
}

/** 요청 전에 거른다: 형식 먼저, 그다음 크기(.xlsx 만 — 서버가 .xls 를 NOT_XLSX 로 거절한다). 통과면 null. */
export function acceptEntryUpload(file: {
  name: string;
  size: number;
}): 'type' | 'size' | null {
  if (!/\.xlsx$/i.test(file.name)) return 'type';
  return file.size > ENTRY_UPLOAD_MAX_BYTES ? 'size' : null;
}

const UPLOAD_ADDRESS = /^(.+)!([A-Z]+[0-9]+)$/;

/**
 * 422 fields → 화면 줄. 받은 차례 그대로(서버가 시트·행·열 차례로 준다), more 는 맨 끝, 글이 여럿이면 줄 여럿.
 * 시트 이름은 주소에 있을 때만 쓴다 — 없으면 자리 없는 줄이다(지어내지 않는다).
 */
export function uploadProblems(
  fields: Readonly<Record<string, readonly string[]>>,
): EntryUploadProblem[] {
  const lines: EntryUploadProblem[] = [];
  const tail: EntryUploadProblem[] = [];
  for (const [key, texts] of Object.entries(fields)) {
    const address = UPLOAD_ADDRESS.exec(key);
    const where = address ? `${address[1]} 시트 ${address[2]}` : null;
    for (const text of texts)
      (key === 'more' ? tail : lines).push({ where, text });
  }
  return [...lines, ...tail];
}

/** 200 답의 갈래. 값 안 든 200 둘은 오류가 아니지만 「됐다」도 아니다. */
export function uploadOutcome(
  result: EntryUploadResult,
): 'filled' | 'noValues' | 'sameValues' {
  if (result.filled > 0) return 'filled';
  return result.unchanged > 0 ? 'sameValues' : 'noValues';
}
