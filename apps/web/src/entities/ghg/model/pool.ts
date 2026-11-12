// 온실가스 인덱스 풀(S19)·시설별 배출계수 풀(S20)의 꼴과 셈(밴드 W12-0b1 ② — 서버 K1b-2a, sid:MARC-ENT-469 3). React·DOM·통신을 모른다.
//   - 꼴: 서버 GhgNodeOut·GhgFacilityOut·GhgFactorSummaryOut·GhgFactorOut·GhgOptionsOut 그대로(응답 id 는 글자 — 거울은 api/contract).
//   - 단 글자는 넷(scope·source_type·activity·facility) — 거울이 이 넷만 받는다(모르면 읽기 failed).
//   - 숫자(배출계수·GWP·순발열량)는 Decimal 글자로 주고받는다: 검사도 글자 그대로 하고 숫자로 바꿔 보내지 않는다.
//     기준연도·Tier 만 정수다(GhgFactorIn).
import type { EntryCustomFactor } from './entries.ts';
import { toRequestId } from './ids.ts';

/** 풀의 단 넷(왼쪽 열부터). */
export const POOL_LEVELS = [
  'scope',
  'source_type',
  'activity',
  'facility',
] as const;
export type PoolLevel = (typeof POOL_LEVELS)[number];

export const isPoolLevel = (text: string): text is PoolLevel =>
  (POOL_LEVELS as readonly string[]).includes(text);

export interface PoolNode {
  id: string;
  level: PoolLevel;
  /** 잎(facility)은 시설 코드의 이름. */
  name: string;
  parentId: string | null;
  sortOrder: number;
  childCount: number;
  /** 잎만 — 코드 글자(F0001 꼴, 화면에 보이지 않는다)·코드 id. 그 밖은 null. */
  facilityCode: string | null;
  facilityCodeId: string | null;
}

export interface PoolUnit {
  kind: string;
  unit: string;
}

export interface FactorSummary {
  id: string;
  name: string;
  inputUnit: PoolUnit;
  isDefault: boolean;
  sortOrder: number;
  version: number;
}

export interface PoolFacility {
  id: string;
  parentId: string;
  facilityCodeId: string;
  facilityCode: string;
  facilityName: string;
  unit: PoolUnit;
  tooltip: string;
  factors: FactorSummary[];
}

export interface PoolGas {
  gas: string;
  enabled: boolean;
  factor: string | null;
  gwp: string | null;
}

export interface PoolFactor {
  id: string;
  facilityNodeId: string;
  version: number;
  /** 있는 판 번호들. */
  versions: number[];
  name: string;
  source: string;
  baseYear: number;
  tier: number;
  countryCode: string;
  industryCode: string;
  inputUnit: PoolUnit;
  emissionUnit: PoolUnit;
  ncvEnabled: boolean;
  ncv: string | null;
  ncvUnit: PoolUnit | null;
  factorUnit: string;
  gases: PoolGas[];
  note: string;
  isDefault: boolean;
  sortOrder: number;
}

export interface CodeName {
  code: string;
  name: string;
}

export interface PoolOptions {
  gases: string[];
  units: { kind: string; units: string[] }[];
  countries: CodeName[];
  industries: CodeName[];
  defaults: {
    emissionUnit: PoolUnit;
    factorUnitWithNcv: string;
    factorUnitWithoutNcv: string;
  };
}

// ── 열 엮기(S19 4열) ─────────────────────────────────────────

const byOrder = (a: PoolNode, b: PoolNode) =>
  a.sortOrder - b.sortOrder || toRequestId(a.id) - toRequestId(b.id);

/**
 * 읽어 둔 노드(열마다 읽은 것을 모은 것, 또는 검색 q 의 답)와 고른 길(path — 왼쪽 열부터 고른 id)로 4열을 엮는다.
 * 열 0 = 부모 없는 배출범위, 열 i = path[i-1] 의 자식(그 길이 없으면 빈 열). 차례는 sortOrder → id(서버와 같다).
 */
export function columnsOf(
  nodes: readonly PoolNode[],
  path: readonly string[],
): PoolNode[][] {
  return POOL_LEVELS.map((level, index) => {
    const parent = index === 0 ? null : (path[index - 1] ?? undefined);
    if (parent === undefined) return [];
    return nodes
      .filter((node) => node.level === level && node.parentId === parent)
      .sort(byOrder);
  });
}

/**
 * 처음 고름: 고른 길을 왼쪽부터 각 열의 첫 항목으로 잇는다 — 배출활동(열 3)까지만(잎은 고르지 않는다 — 판은 잎을 고를 때만, Q7).
 * 고른 길의 id 가 그 열에 없으면(지워짐·검색 밖) 거기서부터 첫 항목으로 다시 잇는다.
 */
export function firstPath(
  nodes: readonly PoolNode[],
  path: readonly string[],
): string[] {
  const out: string[] = [];
  let following = true;
  for (let index = 0; index < 3; index += 1) {
    const column = columnsOf(nodes, out)[index]!;
    const kept =
      following ? column.find((node) => node.id === path[index]) : undefined;
    const next = kept ?? column[0];
    if (!next) return out;
    if (!kept) following = false;
    out.push(next.id);
  }
  const leaf = following ? path[3] : undefined;
  if (
    leaf !== undefined &&
    columnsOf(nodes, out)[3]!.some((n) => n.id === leaf)
  )
    out.push(leaf);
  return out;
}

// ── 자산/시설 판(S19 아래 판) ─────────────────────────────────

export interface FacilityForm {
  facilityCodeId: string;
  unitKind: string;
  unit: string;
  tooltip: string;
  /** 기본 배출계수 id(토글). 계수가 없으면 null. */
  defaultFactorId: string | null;
}

export const emptyFacilityForm = (): FacilityForm => ({
  facilityCodeId: '',
  unitKind: '',
  unit: '',
  tooltip: '',
  defaultFactorId: null,
});

export function facilityFormOf(facility: PoolFacility): FacilityForm {
  return {
    facilityCodeId: facility.facilityCodeId,
    unitKind: facility.unit.kind,
    unit: facility.unit.unit,
    tooltip: facility.tooltip,
    defaultFactorId:
      facility.factors.find((factor) => factor.isDefault)?.id ?? null,
  };
}

/** 판 [저장]을 켤지: 고친 것이 있는가(스펙 [확인] — 고친 것이 없으면 흐림). */
export function facilityChanged(
  before: FacilityForm,
  draft: FacilityForm,
): boolean {
  return (
    before.facilityCodeId !== draft.facilityCodeId ||
    before.unitKind !== draft.unitKind ||
    before.unit !== draft.unit ||
    before.tooltip !== draft.tooltip ||
    before.defaultFactorId !== draft.defaultFactorId
  );
}

export type FacilityProblem = 'facilityCodeId' | 'unit' | null;

/** 판 [저장]의 검사(필수 둘) — 첫 오류 칸. */
export function validateFacility(form: FacilityForm): FacilityProblem {
  if (form.facilityCodeId === '') return 'facilityCodeId';
  if (form.unitKind === '' || form.unit === '') return 'unit';
  return null;
}

/** 새 잎의 본문 판(id 는 글자 — 정수 바꿈은 어댑터가 toRequestId 로). */
export interface FacilityCreateDraft {
  parentId: string;
  facilityCodeId: string;
  unit: PoolUnit;
  tooltip: string;
}

/** 잎 PUT 의 본문 판. defaultFactorId 는 바뀌었을 때만(아니면 null — 싣지 않는다). */
export interface FacilitySaveDraft {
  facilityCodeId: string;
  unit: PoolUnit;
  tooltip: string;
  defaultFactorId: string | null;
}

export function facilityCreateDraft(
  parentId: string,
  form: FacilityForm,
): FacilityCreateDraft {
  return {
    parentId,
    facilityCodeId: form.facilityCodeId,
    unit: { kind: form.unitKind, unit: form.unit },
    tooltip: form.tooltip,
  };
}

/** 기본 계수 토글만 바꿔도 저장된다 — 바뀐 기본만 싣는다. */
export function facilitySaveDraft(
  before: FacilityForm,
  form: FacilityForm,
): FacilitySaveDraft {
  return {
    facilityCodeId: form.facilityCodeId,
    unit: { kind: form.unitKind, unit: form.unit },
    tooltip: form.tooltip,
    defaultFactorId:
      form.defaultFactorId !== before.defaultFactorId ?
        form.defaultFactorId
      : null,
  };
}

// ── 배출계수(S20) ─────────────────────────────────────────

export interface GasForm {
  enabled: boolean;
  factor: string;
  gwp: string;
}

/** S20 모달이 들고 있는 판(글자 칸 그대로). 빈 드롭다운은 ''. */
export interface FactorForm {
  name: string;
  source: string;
  baseYear: string;
  tier: string;
  countryCode: string;
  industryCode: string;
  inputKind: string;
  inputUnit: string;
  emissionKind: string;
  emissionUnit: string;
  ncvEnabled: boolean;
  ncv: string;
  ncvKind: string;
  ncvUnit: string;
  note: string;
  /** 계수 단위(있는 계수의 값 — 새로면 null, 순발열량을 바꾸면 null 로 → 서버 기본). */
  factorUnit: string | null;
  /** 가스 차례 = options.gases. */
  gases: Record<string, GasForm>;
}

/** 새 계수의 빈 판: 가스 토글 모두 끔 · 순발열량 끔 · 배출량 기준단위만 기본값(스펙 「처음 등록」). */
export function emptyFactorForm(options: PoolOptions): FactorForm {
  return {
    name: '',
    source: '',
    baseYear: '',
    tier: '',
    countryCode: '',
    industryCode: '',
    inputKind: '',
    inputUnit: '',
    emissionKind: options.defaults.emissionUnit.kind,
    emissionUnit: options.defaults.emissionUnit.unit,
    ncvEnabled: false,
    ncv: '',
    ncvKind: '',
    ncvUnit: '',
    note: '',
    factorUnit: null,
    gases: Object.fromEntries(
      options.gases.map((gas) => [
        gas,
        { enabled: false, factor: '', gwp: '' },
      ]),
    ),
  };
}

export function factorFormOf(
  factor: PoolFactor,
  options: PoolOptions,
): FactorForm {
  const gases = emptyFactorForm(options).gases;
  for (const one of factor.gases)
    gases[one.gas] = {
      enabled: one.enabled,
      factor: one.factor ?? '',
      gwp: one.gwp ?? '',
    };
  return {
    name: factor.name,
    source: factor.source,
    baseYear: String(factor.baseYear),
    tier: String(factor.tier),
    countryCode: factor.countryCode,
    industryCode: factor.industryCode,
    inputKind: factor.inputUnit.kind,
    inputUnit: factor.inputUnit.unit,
    emissionKind: factor.emissionUnit.kind,
    emissionUnit: factor.emissionUnit.unit,
    ncvEnabled: factor.ncvEnabled,
    ncv: factor.ncv ?? '',
    ncvKind: factor.ncvUnit?.kind ?? '',
    ncvUnit: factor.ncvUnit?.unit ?? '',
    note: factor.note,
    factorUnit: factor.factorUnit,
    gases,
  };
}

/**
 * S12-03a [수정](e6 ④ — sid:MARC-ENT-644, 발주서 Q12): 저장된 직접입력 계수 → 직접 입력 판(저장 값으로 채움).
 * 직접입력 계수에는 배출량 기준단위가 없어(EntryCustomFactorOut) 빈 판의 기본값 그대로 — 직접 입력 화면에도 그 칸이 없다.
 */
export function customFactorFormOf(
  factor: EntryCustomFactor,
  options: PoolOptions,
): FactorForm {
  const empty = emptyFactorForm(options);
  const gases = { ...empty.gases };
  for (const one of factor.gases)
    gases[one.gas] = {
      enabled: one.enabled,
      factor: one.factor ?? '',
      gwp: one.gwp ?? '',
    };
  return {
    ...empty,
    name: factor.name,
    source: factor.source,
    baseYear: String(factor.baseYear),
    tier: String(factor.tier),
    countryCode: factor.countryCode,
    industryCode: factor.industryCode,
    inputKind: factor.inputUnit.kind,
    inputUnit: factor.inputUnit.unit,
    ncvEnabled: factor.ncvEnabled,
    ncv: factor.ncv ?? '',
    ncvKind: factor.ncvUnit?.kind ?? '',
    ncvUnit: factor.ncvUnit?.unit ?? '',
    note: factor.note,
    factorUnit: factor.factorUnit,
    gases,
  };
}

/** 두 판이 같은가(모달 [취소]·✕ 의 확인 창). */
export function sameFactorForm(a: FactorForm, b: FactorForm): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** 계수 칸 머리의 단위 글자: 계수의 factorUnit, 없으면 옵션 기본(순발열량 켬·끔) — 값을 바꾸어 보이지 않는다(sid:MARC-ENT-474 답 전). */
export function factorUnitOf(form: FactorForm, options: PoolOptions): string {
  return (
    form.factorUnit ??
    (form.ncvEnabled ?
      options.defaults.factorUnitWithNcv
    : options.defaults.factorUnitWithoutNcv)
  );
}

export interface FactorGasBody {
  gas: string;
  enabled: boolean;
  factor?: string;
  gwp?: string;
}

/** GhgFactorIn 꼴(서버 본문 — 숫자는 글자, 기준연도·Tier 정수). */
export interface FactorBody {
  name: string;
  source: string;
  baseYear: number;
  tier: number;
  countryCode: string;
  industryCode: string;
  inputUnit: PoolUnit;
  emissionUnit: PoolUnit;
  ncvEnabled: boolean;
  ncv: string | null;
  ncvUnit: PoolUnit | null;
  factorUnit: string | null;
  note: string;
  gases: FactorGasBody[];
}

/**
 * 모달 판 → 본문. 가스는 options 차례로 일곱 줄: 켠 줄은 factor·gwp 글자 그대로, 끈 줄은 {gas, enabled:false}.
 * 순발열량 끔 = ncvEnabled false + ncv·ncvUnit null, 켬 = 값·단위. 검사(validateFactor)를 지난 판만 넘긴다.
 */
export function factorDraft(
  form: FactorForm,
  gasOrder: readonly string[],
): FactorBody {
  return {
    name: form.name.trim(),
    source: form.source.trim(),
    baseYear: toInteger(form.baseYear),
    tier: toInteger(form.tier),
    countryCode: form.countryCode,
    industryCode: form.industryCode,
    inputUnit: { kind: form.inputKind, unit: form.inputUnit },
    emissionUnit: { kind: form.emissionKind, unit: form.emissionUnit },
    ncvEnabled: form.ncvEnabled,
    ncv: form.ncvEnabled ? form.ncv.trim() : null,
    ncvUnit:
      form.ncvEnabled ? { kind: form.ncvKind, unit: form.ncvUnit } : null,
    factorUnit: form.factorUnit,
    note: form.note,
    gases: gasOrder.map((gas) => {
      const one = form.gases[gas] ?? { enabled: false, factor: '', gwp: '' };
      return one.enabled ?
          {
            gas,
            enabled: true,
            factor: one.factor.trim(),
            gwp: one.gwp.trim(),
          }
        : { gas, enabled: false };
    }),
  };
}

function toInteger(text: string): number {
  if (!/^[0-9]{1,4}$/.test(text))
    throw new RangeError(`not a year/tier: ${text}`);
  return Number(text);
}

/** Decimal 글자(정수 18자리·소수 12자리까지, 지수·부호 없음 — 서버 _DECIMAL)이고 0 보다 큰가. 숫자로 바꾸지 않는다. */
export function isPositiveDecimal(text: string): boolean {
  const trimmed = text.trim();
  return /^[0-9]{1,18}(\.[0-9]{1,12})?$/.test(trimmed) && /[1-9]/.test(trimmed);
}

/** S20 검사의 오류 칸 열쇠 — 서버 fields 와 같은 이름(gases.<가스>.factor 꼴 포함). */
export type FactorField = string;
export type FactorProblem = 'required' | 'number';

/**
 * S20 [저장]의 검사(누를 때 — Policy). 칸 차례(위 → 아래)대로 {칸: 까닭}. 빈 객체면 지남.
 * 필수 칸 · 켠 가스 ≥ 1(「gases」) · 켠 줄 배출계수·GWP 가 0 초과 Decimal 글자 · 순발열량 켬이면 값(0 초과)·단위.
 */
export function validateFactor(
  form: FactorForm,
  gasOrder: readonly string[],
): [FactorField, FactorProblem][] {
  const out: [FactorField, FactorProblem][] = [];
  const need = (field: string, value: string) => {
    if (value.trim() === '') out.push([field, 'required']);
  };
  need('name', form.name);
  need('source', form.source);
  need('baseYear', form.baseYear);
  need('tier', form.tier);
  need('countryCode', form.countryCode);
  need('industryCode', form.industryCode);
  if (form.inputKind === '' || form.inputUnit === '')
    out.push(['inputUnit', 'required']);
  if (form.emissionKind === '' || form.emissionUnit === '')
    out.push(['emissionUnit', 'required']);
  if (form.ncvEnabled) {
    if (form.ncv.trim() === '') out.push(['ncv', 'required']);
    else if (!isPositiveDecimal(form.ncv)) out.push(['ncv', 'number']);
    if (form.ncvKind === '' || form.ncvUnit === '')
      out.push(['ncvUnit', 'required']);
  }
  const enabled = gasOrder.filter((gas) => form.gases[gas]?.enabled);
  if (enabled.length === 0) out.push(['gases', 'required']);
  for (const gas of enabled) {
    const one = form.gases[gas]!;
    for (const key of ['factor', 'gwp'] as const) {
      const field = `gases.${gas}.${key}`;
      if (one[key].trim() === '') out.push([field, 'required']);
      else if (!isPositiveDecimal(one[key])) out.push([field, 'number']);
    }
  }
  return out;
}
