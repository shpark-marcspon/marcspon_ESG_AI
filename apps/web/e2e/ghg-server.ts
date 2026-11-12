// e2e 의 온실가스 조직구조 흉내 서버(밴드 W12-0a ② — e2e/materiality-server.ts 꼴, 테스트 d9 알림 H12). 빌드한 웹의 실어댑터가 부르는
// 경로 열하나를 page.route 로 채운다. 답의 값은 전부 지어낸 것이다(「제1공장」 꼴 — 실재 기업명 0). 포트는 쥐지 않는다.
// e2e 는 웹 코드에서 문구 표(config/text.ts)만 들이므로(app/guards/layers.test.ts) 꼴은 여기서 짓는다(K1b-1 경로 표 그대로):
//   - 응답 id 는 글자, 요청 id(ids[]·facilities[].id·facilityCodeId·경로 id)는 정수만 받는다(글자면 422 VALIDATION_ERROR — sid:MARC-ISSUE-92).
//   - GET /api/branches?q=&page=&pageSize= · GET·PUT /api/branches/{id} · POST /api/branches · POST /api/branches/inventory · POST /api/branches/delete ·
//     GET /api/facility-codes · GET·POST /api/admin/facility-codes · PATCH /api/admin/facility-codes/{id} · POST /api/admin/facility-codes/delete.
//   - 본사: 끄기·지우기 409 HEADQUARTERS_LOCKED. 빈 이름·겹침 422(fields.name·facilities). 고객사의 /admin/** 403. company 를 주면 /branches·
//     /facility-codes 가 그 회사 거절(400).
//   - 코드 지우기는 삭제 표시(밴드 W12-0b1 ① L3 — api/testing.ts 와 같은 규칙): 두 목록에서 빠지고, 그 코드를 그대로 두는 기존 줄은 이름 그대로
//     저장을 지나며, 새로 고르면(새 줄·코드 바꿈) 422 fields.facilityCodeId. /facility-codes = 이름 가나다 → id · /admin/facility-codes = 만든 차례 ·
//     /branches q = 대소문자 무시 부분 일치.
// 밴드 W12-0b1 ③: 인덱스 풀(S19·S20, 운영 관리자만) 경로 열둘도 — /api/inventory/admin/ghg-index/** · ghg-factors/** · ghg-options.
//   씨앗은 api/testing.ts 의 fakePool 과 같은 꼴(범위 둘·유형 둘·활동 둘·잎 셋·계수 둘). q 는 맞는 노드 + 조상 · 같은 부모 같은 이름 422 ·
//   요청 밖 자식 409 HAS_CHILDREN · 잎 PUT defaultFactorId 는 그 잎의 계수 · 계수 PUT 은 새 판 · 기본을 지우면 남은 첫 행. 「쓰이는 표」는 없다(vitest 몫).
// 밴드 W12-0b2 ③: 고객사 인덱스 선택(S17·S2 자리, 고객사·운영 관리자) 경로 둘도 — GET /api/inventory/scope12/index-tree?year= ·
//   PUT /api/inventory/scope12/index-selections/{year}. 규칙은 api/testing.ts 의 선택 가짜와 같다: 트리는 위 풀 노드(단 → id), 잎
//   availableCount = 인벤토리 켠 사업장의 그 코드 줄 수(위 단 = 아래 합) · hasFactor = 기본 계수 있음 · 위 단 selected = 아래 고를 수 있는 잎이
//   다 골라짐(고를 수 있음 = 기본 계수 있음 — S12-05) · 해마다 따로 · 연도 1990~올해(Asia/Seoul) 밖·글자 422 fields.year · 본문 열쇠 하나·정수·1,000·
//   없는(잎 아닌) id · 새로 고르는 잎의 기본 없음 422 fields.facilityNodeIds(J1 — 이미 고른 잎은 지남. 시설 0 은 거절 아님 — S12-05) · 빈 목록도 해를 만듦 · company 를 주면 회사 거절(400).
//   hasData 는 늘 거짓(지금 서버 — S12a), 「쓰이는 표」는 없다(vitest 몫).
// 밴드 W12-1a ③: 입력 리스트(S2) 경로 둘도 — GET /api/inventory/scope12/years · GET /api/inventory/scope12/rows?year=&q=. 줄 = 그 해 고른 잎
//   (풀 트리 차례 — 범위 → 유형 → 활동 → 잎), path 넷은 이름, q(≤100자, 넘으면 422 fields.q)는 경로 이름 부분 일치(대소문자 무시).
//   years = 서버처럼 Y-2·Y-1·Y. 값·메모·추정·잠금은 셈하지 않고 spec 이 심는 표(entryValues·scopeValues·entryMarks — 지어낸 글자)에서.
//   고른 잎 0 → configured 거짓·scopes []. company 를 주면 회사 거절(400).
// 밴드 K1b-3: 사업장마다 판 버전 updatedAt(지어낸 µs 글자 — POST·PUT 200·토글·bumpBranch 마다 늘 더 큰 글자). PUT 본문 updatedAt 이 없으면
//   422 fields.updatedAt, 지금 판과 글자가 다르면 409 STALE(없는 id 404 가 먼저) · POST 본문에 있으면 422 · bumpBranch(id, line?) 가 「다른 탭이
//   저장」을 흉내 낸다(api/testing.ts 의 같은 이름과 같은 규칙).
// 밴드 DB1 ②: 대시보드(S1) GET /api/inventory/scope12/dashboard?year= — dashboards 에 심은 답(openapi 꼴), 없는 해는 빈 판.
// 이 흉내는 위 경로만 받는다 — 그 밖 /api/ 는 다음 route(spec 의 덫 503)로 넘긴다. 로그인은 e2e/session.ts 의 signIn 을 뒤에 부른다.
import type { Page, Route } from '@playwright/test';

export interface GhgCall {
  method: string;
  path: string;
  query: string;
  body: unknown;
  /** 올리기의 본문 바이트 수와 Content-Type(W12-5 ①). */
  size?: number;
  contentType?: string | null;
}

/** 올리기 심는 답(W12-5 ① — xlsx 를 읽지 않는다). apply 는 답 앞에 표를 바꾼다(끊김도 「표를 바꾼 뒤」가 된다). */
export type GhgUploadAnswer = { apply?: () => void } & (
  | { status: 200; body: Json }
  | { status: number; code: string; fields?: Record<string, string[]> }
  | { abort: true }
);

type Json = Record<string, unknown>;
interface Line {
  id: number;
  codeId: number;
  detailName: string;
}
interface Branch {
  id: number;
  name: string;
  isHeadquarters: boolean;
  inventoryEnabled: boolean;
  lines: Line[];
  /** 판 버전(밴드 K1b-3). */
  updatedAt: string;
}
interface Code {
  id: number;
  name: string;
  /** 삭제 표시(지운 코드도 줄 이름을 위해 남긴다). */
  deleted?: true;
}

const CREATED = '2026-10-28T09:00:00+09:00';
/** 올리기 상한(서버 올리기 경로의 GHG_UPLOAD_MAX_BYTES 20MB — MARC-ENT-593)과 xlsx 미디어 타입. */
const UPLOAD_MAX = 20 * 1024 * 1024;
const XLSX_TYPE =
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
/** 씨앗 사업장의 판(밴드 K1b-3) — 바뀌면 stamp 가 그 뒤 글자를 낸다. */
const SEEDED = '2026-10-28T09:00:00.000001+09:00';

const answer = (route: Route, status: number, body: unknown) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
const refusal = (
  route: Route,
  status: number,
  code: string,
  fields: Record<string, string[]> | null = null,
) =>
  answer(route, status, {
    error: {
      code,
      message: `지어낸-${code}`,
      fields,
      legacyCode: code.toLowerCase(),
    },
  });

const isInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0;
const codeText = (id: number) => `F${String(id).padStart(4, '0')}`;

export interface GhgApiOptions {
  /** 거짓이면 /admin/** 이 403(고객사 사용자). */
  admin?: boolean;
  company?: 'COMPANY_AMBIGUOUS' | 'COMPANY_INACTIVE' | 'COMPANY_NOT_FOUND';
}

export async function fakeGhgApi(
  page: Page,
  { admin = true, company }: GhgApiOptions = {},
) {
  const calls: GhgCall[] = [];
  const branches: Branch[] = [
    {
      id: 1,
      name: '본사',
      isHeadquarters: true,
      inventoryEnabled: true,
      lines: [{ id: 1, codeId: 1, detailName: '1호기' }],
      updatedAt: SEEDED,
    },
    {
      id: 2,
      name: '제1공장',
      isHeadquarters: false,
      inventoryEnabled: true,
      lines: [],
      updatedAt: SEEDED,
    },
    {
      id: 3,
      name: '제2공장',
      isHeadquarters: false,
      inventoryEnabled: true,
      lines: [],
      updatedAt: SEEDED,
    },
  ];
  const codes: Code[] = [
    { id: 1, name: '지어낸 보일러' },
    { id: 2, name: '지어낸 발전기' },
    { id: 3, name: '지어낸 사업장 차량' },
  ];
  let branchSeq = 10;
  let lineSeq = 10;
  let codeSeq = 10;
  const alive = () => codes.filter((c) => !c.deleted);
  let tick = 0;
  /** 판을 올린다 — 씨앗(10-28)보다 늘 뒤, 1µs 씩. */
  const bump = (b: Branch) => {
    tick += 1;
    b.updatedAt = `2026-10-29T09:00:00.${String(tick).padStart(6, '0')}+09:00`;
  };

  const codeOut = (code: Code) => ({
    id: String(code.id),
    code: codeText(code.id),
    name: code.name,
  });
  const branchOut = (b: Branch) => ({
    id: String(b.id),
    name: b.name,
    isHeadquarters: b.isHeadquarters,
    inventoryEnabled: b.inventoryEnabled,
    externalId: null,
    createdAt: CREATED,
  });
  const detailOut = (b: Branch) => ({
    ...branchOut(b),
    updatedAt: b.updatedAt,
    facilities: b.lines.map((line) => {
      const code = codes.find((c) => c.id === line.codeId);
      return {
        id: String(line.id),
        facilityCodeId: String(line.codeId),
        facilityCode: codeText(line.codeId),
        facilityName: code?.name ?? '지어낸 지운 코드',
        detailName: line.detailName,
      };
    }),
  });
  const pageOf = (rows: unknown[], page: number, pageSize: number) => {
    const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
    return {
      count: rows.length,
      totalPages,
      page,
      pageSize,
      hasNext: page < totalPages,
      hasPrevious: page > 1,
      results: rows.slice((page - 1) * pageSize, page * pageSize),
    };
  };

  /** 사업장 본문 검사 → 거절(이미 답함) 이면 null, 아니면 새 줄. */
  const linesOf = async (
    route: Route,
    body: Json,
    branch: Branch | null,
  ): Promise<Line[] | null> => {
    const { name, inventoryEnabled, facilities = [] } = body;
    if (typeof name !== 'string' || name.trim() === '') {
      await refusal(route, 422, 'VALIDATION_ERROR', { name: ['빈 이름'] });
      return null;
    }
    if (branches.some((b) => b !== branch && b.name === name.trim())) {
      await refusal(route, 422, 'VALIDATION_ERROR', { name: ['겹침'] });
      return null;
    }
    if (typeof inventoryEnabled !== 'boolean' || !Array.isArray(facilities)) {
      await refusal(route, 422, 'VALIDATION_ERROR');
      return null;
    }
    const out: Line[] = [];
    for (const raw of facilities as Json[]) {
      if (raw.id !== undefined && raw.id !== null) {
        if (!isInt(raw.id)) {
          await refusal(route, 422, 'VALIDATION_ERROR');
          return null;
        }
        if (!branch?.lines.some((l) => l.id === raw.id)) {
          await refusal(route, 404, 'NOT_FOUND');
          return null;
        }
      }
      // 그 줄이 쓰던 코드를 그대로 두면 지운 코드여도 지난다 — 새로 고른 코드만 살아 있어야 한다.
      const kept = branch?.lines.some(
        (l) => l.id === raw.id && l.codeId === raw.facilityCodeId,
      );
      if (
        !isInt(raw.facilityCodeId) ||
        !(kept ? codes : alive()).some((c) => c.id === raw.facilityCodeId) ||
        typeof raw.detailName !== 'string' ||
        raw.detailName.trim() === ''
      ) {
        await refusal(route, 422, 'VALIDATION_ERROR', {
          facilityCodeId: ['틀림'],
        });
        return null;
      }
      out.push({
        id: isInt(raw.id) ? raw.id : lineSeq++,
        codeId: raw.facilityCodeId,
        detailName: raw.detailName.trim(),
      });
    }
    return out;
  };

  await page.route(
    /\/api\/(branches|facility-codes|admin\/facility-codes)(\/|\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      const method = request.method();
      let body: Json = {};
      try {
        body = request.postData() ? (request.postDataJSON() as Json) : {};
      } catch {
        body = {};
      }
      calls.push({
        method,
        path,
        query: url.search,
        body: request.postData() ? body : undefined,
      });

      if (path.startsWith('/admin/')) {
        if (!admin) return refusal(route, 403, 'FORBIDDEN');
        if (method === 'GET' && path === '/admin/facility-codes') {
          const p = Number(url.searchParams.get('page') ?? 1);
          const size = Number(url.searchParams.get('pageSize') ?? 20);
          return answer(
            route,
            200,
            pageOf(
              alive().map((c) => ({ ...codeOut(c), inUse: false })),
              p,
              size,
            ),
          );
        }
        if (method === 'POST' && path === '/admin/facility-codes') {
          const name = typeof body.name === 'string' ? body.name.trim() : '';
          if (name === '')
            return refusal(route, 422, 'VALIDATION_ERROR', { name: ['빈'] });
          if (alive().some((c) => c.name === name))
            return refusal(route, 422, 'VALIDATION_ERROR', { name: ['겹침'] });
          const code = { id: codeSeq++, name };
          codes.push(code);
          return answer(route, 201, codeOut(code));
        }
        if (method === 'POST' && path === '/admin/facility-codes/delete') {
          const ids = body.ids;
          if (!Array.isArray(ids) || !ids.every(isInt))
            return refusal(route, 422, 'VALIDATION_ERROR');
          const found = ids.map((id) => alive().find((c) => c.id === id));
          if (found.some((c) => !c)) return refusal(route, 404, 'NOT_FOUND');
          for (const c of found) c!.deleted = true;
          return answer(route, 200, { count: ids.length });
        }
        const match = /^\/admin\/facility-codes\/([^/]+)$/.exec(path);
        if (match && method === 'PATCH') {
          if (!/^[1-9][0-9]*$/.test(match[1]!))
            return refusal(route, 422, 'VALIDATION_ERROR');
          const code = alive().find((c) => c.id === Number(match[1]));
          if (!code) return refusal(route, 404, 'NOT_FOUND');
          const name = typeof body.name === 'string' ? body.name.trim() : '';
          if (name === '')
            return refusal(route, 422, 'VALIDATION_ERROR', { name: ['빈'] });
          if (alive().some((c) => c !== code && c.name === name))
            return refusal(route, 422, 'VALIDATION_ERROR', { name: ['겹침'] });
          code.name = name;
          return answer(route, 200, codeOut(code));
        }
        return route.fallback();
      }

      if (company) return refusal(route, 400, company);
      if (method === 'GET' && path === '/facility-codes')
        return answer(route, 200, {
          items: alive()
            .sort(
              (a, b) =>
                (a.name < b.name ? -1
                : a.name > b.name ? 1
                : 0) || a.id - b.id,
            )
            .map(codeOut),
        });
      if (method === 'GET' && path === '/branches') {
        const q = url.searchParams.get('q') ?? '';
        const p = Number(url.searchParams.get('page') ?? 1);
        const size = Number(url.searchParams.get('pageSize') ?? 20);
        const rows = [...branches]
          .sort(
            (a, b) =>
              Number(b.isHeadquarters) - Number(a.isHeadquarters) ||
              a.id - b.id,
          )
          .filter((b) => b.name.toLowerCase().includes(q.toLowerCase()))
          .map(branchOut);
        return answer(route, 200, pageOf(rows, p, size));
      }
      if (method === 'POST' && path === '/branches') {
        if ('updatedAt' in body)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            updatedAt: ['모르는 칸'],
          });
        const lines = await linesOf(route, body, null);
        if (!lines) return;
        const made: Branch = {
          id: branchSeq++,
          name: (body.name as string).trim(),
          isHeadquarters: false,
          inventoryEnabled: body.inventoryEnabled as boolean,
          lines,
          updatedAt: SEEDED,
        };
        bump(made);
        branches.push(made);
        return answer(route, 201, detailOut(made));
      }
      if (
        method === 'POST' &&
        (path === '/branches/inventory' || path === '/branches/delete')
      ) {
        const ids = body.ids;
        if (!Array.isArray(ids) || ids.length === 0 || !ids.every(isInt))
          return refusal(route, 422, 'VALIDATION_ERROR');
        const found = ids.map((id) => branches.find((b) => b.id === id));
        if (found.some((b) => !b)) return refusal(route, 404, 'NOT_FOUND');
        const disabling = path === '/branches/delete' || body.enabled === false;
        if (disabling && found.some((b) => b!.isHeadquarters))
          return refusal(route, 409, 'HEADQUARTERS_LOCKED');
        for (const b of found)
          if (path === '/branches/delete')
            branches.splice(branches.indexOf(b!), 1);
          else {
            b!.inventoryEnabled = body.enabled === true;
            bump(b!);
          }
        return answer(route, 200, { count: found.length });
      }
      const match = /^\/branches\/([^/]+)$/.exec(path);
      if (match && (method === 'GET' || method === 'PUT')) {
        if (!/^[1-9][0-9]*$/.test(match[1]!))
          return refusal(route, 422, 'VALIDATION_ERROR');
        // 본문 꼴(판 없음 422)은 서버처럼 404 보다 먼저, 낡은 판(409)은 404 뒤.
        if (
          method === 'PUT' &&
          (typeof body.updatedAt !== 'string' || body.updatedAt === '')
        )
          return refusal(route, 422, 'VALIDATION_ERROR', {
            updatedAt: ['판 없음'],
          });
        const branch = branches.find((b) => b.id === Number(match[1]));
        if (!branch) return refusal(route, 404, 'NOT_FOUND');
        if (method === 'GET') return answer(route, 200, detailOut(branch));
        if (body.updatedAt !== branch.updatedAt)
          return refusal(route, 409, 'STALE');
        const lines = await linesOf(route, body, branch);
        if (!lines) return;
        if (branch.isHeadquarters && body.inventoryEnabled === false)
          return refusal(route, 409, 'HEADQUARTERS_LOCKED');
        branch.name = (body.name as string).trim();
        branch.inventoryEnabled = body.inventoryEnabled as boolean;
        branch.lines = lines;
        bump(branch);
        return answer(route, 200, detailOut(branch));
      }
      return route.fallback();
    },
  );

  // ── 밴드 W12-0b1 ③: 인덱스 풀(/inventory/admin/…) ──
  const GASES = ['CO2', 'CH4', 'N2O', 'HFCs', 'PFCs', 'SF6', 'NF3'];
  const UNITS: Record<string, string[]> = {
    mass: ['g', 'kg', 't'],
    volume: ['L', 'kL', 'm3', 'Nm3', 'kNm3'],
    energy: ['MJ', 'GJ', 'TJ'],
    electricity: ['kWh', 'MWh', 'GWh'],
  };
  const LEVELS = ['scope', 'source_type', 'activity', 'facility'];
  interface PoolNode {
    id: number;
    level: string;
    name: string;
    parentId: number | null;
    codeId?: number;
    unit?: { kind: string; unit: string };
    tooltip?: string;
  }
  interface PoolFactor {
    id: number;
    leafId: number;
    isDefault: boolean;
    versions: Json[];
  }
  const factorBody = (name: string): Json => ({
    name,
    source: '지어낸 출처',
    baseYear: 2024,
    tier: 1,
    countryCode: 'KR',
    industryCode: 'energy_industries',
    inputUnit: { kind: 'volume', unit: 'kL' },
    emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
    ncvEnabled: false,
    ncv: null,
    ncvUnit: null,
    factorUnit: null,
    note: '',
    gases: GASES.map((gas, i) =>
      i === 0 ?
        { gas, enabled: true, factor: '2.5', gwp: '1' }
      : { gas, enabled: false },
    ),
  });
  const leafSeed = (
    id: number,
    parentId: number,
    codeId: number,
  ): PoolNode => ({
    id,
    level: 'facility',
    name: '',
    parentId,
    codeId,
    unit: { kind: 'volume', unit: 'kL' },
    tooltip: '지어낸 툴팁',
  });
  const poolNodes: PoolNode[] = [
    { id: 1, level: 'scope', name: '지어낸 직접배출', parentId: null },
    { id: 2, level: 'scope', name: '지어낸 간접배출', parentId: null },
    { id: 3, level: 'source_type', name: '지어낸 고정연소', parentId: 1 },
    { id: 4, level: 'source_type', name: '지어낸 이동연소', parentId: 1 },
    { id: 5, level: 'activity', name: '지어낸 액체연료', parentId: 3 },
    { id: 6, level: 'activity', name: '지어낸 도로수송', parentId: 4 },
    leafSeed(20, 5, 1),
    leafSeed(22, 5, 2),
    leafSeed(24, 6, 3),
  ];
  const poolFactors: PoolFactor[] = [
    {
      id: 21,
      leafId: 20,
      isDefault: true,
      versions: [factorBody('지어낸 경유 계수')],
    },
    {
      id: 23,
      leafId: 20,
      isDefault: false,
      versions: [factorBody('지어낸 등유 계수')],
    },
  ];
  let poolSeq = 100;
  const nameOf = (n: PoolNode) =>
    n.level === 'facility' ?
      (codes.find((c) => c.id === n.codeId)?.name ?? '')
    : n.name;
  const kids = (id: number) => poolNodes.filter((n) => n.parentId === id);
  const poolOrder = (a: PoolNode, b: PoolNode) =>
    LEVELS.indexOf(a.level) - LEVELS.indexOf(b.level) || a.id - b.id;
  const nodeOut = (n: PoolNode) => ({
    id: String(n.id),
    level: n.level,
    name: nameOf(n),
    parentId: n.parentId === null ? null : String(n.parentId),
    sortOrder: n.id,
    childCount: kids(n.id).length,
    facilityCode: n.level === 'facility' ? codeText(n.codeId!) : null,
    facilityCodeId: n.level === 'facility' ? String(n.codeId) : null,
  });
  const leafFactors = (id: number) =>
    poolFactors.filter((f) => f.leafId === id).sort((a, b) => a.id - b.id);
  const facilityOut = (n: PoolNode) => ({
    id: String(n.id),
    parentId: String(n.parentId),
    facilityCodeId: String(n.codeId),
    facilityCode: codeText(n.codeId!),
    facilityName: nameOf(n),
    unit: n.unit,
    tooltip: n.tooltip ?? '',
    factors: leafFactors(n.id).map((f) => ({
      id: String(f.id),
      name: f.versions.at(-1)!.name,
      inputUnit: f.versions.at(-1)!.inputUnit,
      isDefault: f.isDefault,
      sortOrder: f.id,
      version: f.versions.length,
    })),
  });
  const factorOut = (f: PoolFactor, version = f.versions.length) => {
    const body = f.versions[version - 1]!;
    return {
      ...body,
      id: String(f.id),
      facilityNodeId: String(f.leafId),
      version,
      versions: f.versions.map((_, i) => i + 1),
      emissionUnit: body.emissionUnit ?? { kind: 'mass', unit: 'tCO2-eq' },
      factorUnit:
        body.factorUnit ??
        (body.ncvEnabled ? 'kg/TJ' : `kg/${(body.inputUnit as Json).unit}`),
      gases: GASES.map((gas) => {
        const one = (body.gases as Json[]).find((g) => g.gas === gas) ?? {};
        return {
          gas,
          enabled: one.enabled === true,
          factor: one.factor ?? null,
          gwp: one.gwp ?? null,
        };
      }),
      isDefault: f.isDefault,
      sortOrder: f.id,
      seedGwpSetId: null,
      seedRecordIds: [],
      createdAt: CREATED,
      updatedAt: CREATED,
    };
  };
  const isUnit = (value: unknown) => {
    const u = value as { kind?: string; unit?: string } | null;
    return !!u && (UNITS[u.kind ?? ''] ?? []).includes(u.unit ?? '');
  };
  const isDecimal = (value: unknown) =>
    typeof value === 'string' &&
    /^[0-9]{1,18}(\.[0-9]{1,12})?$/.test(value) &&
    /[1-9]/.test(value);
  /** S20 검사의 줄인 꼴(필수·켠 가스 ≥1·켠 줄 Decimal 글자) → fields 나 null. */
  const factorFields = (body: Json): Record<string, string[]> | null => {
    const out: Record<string, string[]> = {};
    if (typeof body.name !== 'string' || body.name.trim() === '')
      out.name = ['빈'];
    if (typeof body.source !== 'string' || body.source.trim() === '')
      out.source = ['빈'];
    if (!isInt(body.baseYear)) out.baseYear = ['틀림'];
    if (![1, 2, 3].includes(body.tier as number)) out.tier = ['틀림'];
    if (!isUnit(body.inputUnit)) out.inputUnit = ['틀림'];
    const gases = Array.isArray(body.gases) ? (body.gases as Json[]) : [];
    for (const g of gases.filter((one) => one.enabled === true)) {
      if (!isDecimal(g.factor)) out[`gases.${String(g.gas)}.factor`] = ['틀림'];
      if (!isDecimal(g.gwp)) out[`gases.${String(g.gas)}.gwp`] = ['틀림'];
    }
    if (!gases.some((g) => g.enabled === true)) out.gases = ['켠 가스 0'];
    return Object.keys(out).length > 0 ? out : null;
  };
  const sameName = (parentId: number | null, name: string, self?: PoolNode) =>
    poolNodes.some(
      (n) => n !== self && n.parentId === parentId && nameOf(n) === name,
    );

  await page.route(
    /\/api\/inventory\/admin\/ghg-(index|factors|options)(\/|\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      const method = request.method();
      let body: Json = {};
      try {
        body = request.postData() ? (request.postDataJSON() as Json) : {};
      } catch {
        body = {};
      }
      calls.push({
        method,
        path,
        query: url.search,
        body: request.postData() ? body : undefined,
      });
      if (!admin) return refusal(route, 403, 'FORBIDDEN');
      const P = '/inventory/admin';
      const key = `${method} ${path}`;
      const int = (text: string | undefined) =>
        /^[1-9][0-9]*$/.test(text ?? '') ? Number(text) : null;

      if (key === `GET ${P}/ghg-options`)
        return answer(route, 200, {
          gases: GASES,
          units: Object.entries(UNITS).map(([kind, units]) => ({
            kind,
            units,
          })),
          countries: [
            { code: 'GLOBAL', name: '지어낸 전 세계' },
            { code: 'KR', name: '지어낸 국내' },
          ],
          industries: [
            { code: 'energy_industries', name: '지어낸 에너지' },
            { code: 'other', name: '지어낸 기타' },
          ],
          defaults: {
            emissionUnit: { kind: 'mass', unit: 'tCO2-eq' },
            factorUnitWithNcv: 'kg/TJ',
            factorUnitWithoutNcv: 'kg/<투입 단위>',
          },
        });
      if (key === `GET ${P}/ghg-index/nodes`) {
        const q = url.searchParams.get('q');
        if (q !== null) {
          const hit = new Set(
            poolNodes
              .filter((n) => nameOf(n).toLowerCase().includes(q.toLowerCase()))
              .map((n) => n.id),
          );
          for (const id of [...hit]) {
            let up = poolNodes.find((n) => n.id === id)?.parentId ?? null;
            while (up !== null) {
              hit.add(up);
              up = poolNodes.find((n) => n.id === up)?.parentId ?? null;
            }
          }
          return answer(route, 200, {
            items: poolNodes
              .filter((n) => hit.has(n.id))
              .sort(poolOrder)
              .map(nodeOut),
          });
        }
        const raw = url.searchParams.get('parentId');
        const parent = raw === null ? null : int(raw);
        if (raw !== null && parent === null)
          return refusal(route, 422, 'VALIDATION_ERROR');
        return answer(route, 200, {
          items: poolNodes
            .filter((n) => n.parentId === parent)
            .sort(poolOrder)
            .map(nodeOut),
        });
      }
      if (key === `POST ${P}/ghg-index/nodes`) {
        const level = String(body.level);
        const at = LEVELS.indexOf(level);
        if (at < 0 || at > 2)
          return refusal(route, 422, 'VALIDATION_ERROR', { level: ['틀림'] });
        const parentId = body.parentId ?? null;
        if (
          (at === 0) !== (parentId === null) ||
          (parentId !== null && !isInt(parentId))
        )
          return refusal(route, 422, 'VALIDATION_ERROR', {
            parentId: ['틀림'],
          });
        const name = typeof body.name === 'string' ? body.name.trim() : '';
        if (name === '' || sameName(parentId as number | null, name))
          return refusal(route, 422, 'VALIDATION_ERROR', { name: ['겹침'] });
        const made: PoolNode = {
          id: poolSeq++,
          level,
          name,
          parentId: parentId as number | null,
        };
        poolNodes.push(made);
        return answer(route, 201, nodeOut(made));
      }
      if (key === `POST ${P}/ghg-index/nodes/delete`) {
        const ids = body.ids;
        if (!Array.isArray(ids) || !ids.every(isInt))
          return refusal(route, 422, 'VALIDATION_ERROR');
        const found = ids.map((id) => poolNodes.find((n) => n.id === id));
        if (found.some((n) => !n)) return refusal(route, 404, 'NOT_FOUND');
        if (found.some((n) => kids(n!.id).some((c) => !ids.includes(c.id))))
          return refusal(route, 409, 'HAS_CHILDREN');
        for (const n of found) {
          poolNodes.splice(poolNodes.indexOf(n!), 1);
          for (const f of leafFactors(n!.id))
            poolFactors.splice(poolFactors.indexOf(f), 1);
        }
        return answer(route, 200, { count: found.length });
      }
      const nodeMatch = new RegExp(`^PATCH ${P}/ghg-index/nodes/([^/]+)$`).exec(
        key,
      );
      if (nodeMatch) {
        const node = poolNodes.find(
          (n) => n.id === int(nodeMatch[1]) && n.level !== 'facility',
        );
        if (!node) return refusal(route, 404, 'NOT_FOUND');
        const name = typeof body.name === 'string' ? body.name.trim() : '';
        if (name === '' || sameName(node.parentId, name, node))
          return refusal(route, 422, 'VALIDATION_ERROR', { name: ['겹침'] });
        node.name = name;
        return answer(route, 200, nodeOut(node));
      }
      if (key === `POST ${P}/ghg-index/facilities`) {
        const parent = poolNodes.find(
          (n) => n.id === body.parentId && n.level === 'activity',
        );
        if (!isInt(body.parentId) || !parent)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            parentId: ['틀림'],
          });
        if (!isUnit(body.unit))
          return refusal(route, 422, 'VALIDATION_ERROR', { unit: ['틀림'] });
        if (
          !isInt(body.facilityCodeId) ||
          !alive().some((c) => c.id === body.facilityCodeId) ||
          kids(parent.id).some((n) => n.codeId === body.facilityCodeId)
        )
          return refusal(route, 422, 'VALIDATION_ERROR', {
            facilityCodeId: ['틀림'],
          });
        const made: PoolNode = {
          ...leafSeed(poolSeq++, parent.id, body.facilityCodeId),
          unit: body.unit as PoolNode['unit'],
          tooltip: typeof body.tooltip === 'string' ? body.tooltip : '',
        };
        poolNodes.push(made);
        return answer(route, 201, facilityOut(made));
      }
      const leafMatch = new RegExp(
        `^(GET|PUT|POST) ${P}/ghg-index/facilities/([^/]+)(/factors)?$`,
      ).exec(key);
      if (leafMatch) {
        const leaf = poolNodes.find(
          (n) => n.id === int(leafMatch[2]) && n.level === 'facility',
        );
        if (!leaf) return refusal(route, 404, 'NOT_FOUND');
        if (leafMatch[1] === 'GET' && !leafMatch[3])
          return answer(route, 200, facilityOut(leaf));
        if (leafMatch[1] === 'POST' && leafMatch[3]) {
          const fields = factorFields(body);
          if (fields) return refusal(route, 422, 'VALIDATION_ERROR', fields);
          const made = {
            id: poolSeq++,
            leafId: leaf.id,
            isDefault: leafFactors(leaf.id).length === 0,
            versions: [body],
          };
          poolFactors.push(made);
          return answer(route, 201, factorOut(made));
        }
        if (leafMatch[1] === 'PUT' && !leafMatch[3]) {
          if (!isUnit(body.unit))
            return refusal(route, 422, 'VALIDATION_ERROR', { unit: ['틀림'] });
          if (!isInt(body.facilityCodeId))
            return refusal(route, 422, 'VALIDATION_ERROR', {
              facilityCodeId: ['틀림'],
            });
          let target: PoolFactor | undefined;
          if (body.defaultFactorId !== undefined) {
            target = leafFactors(leaf.id).find(
              (f) => f.id === body.defaultFactorId,
            );
            if (!isInt(body.defaultFactorId) || !target)
              return refusal(route, 422, 'VALIDATION_ERROR', {
                defaultFactorId: ['틀림'],
              });
          }
          leaf.codeId = body.facilityCodeId;
          leaf.unit = body.unit as PoolNode['unit'];
          leaf.tooltip = typeof body.tooltip === 'string' ? body.tooltip : '';
          if (target)
            for (const f of leafFactors(leaf.id)) f.isDefault = f === target;
          return answer(route, 200, facilityOut(leaf));
        }
      }
      if (key === `POST ${P}/ghg-factors/delete`) {
        const ids = body.ids;
        if (!Array.isArray(ids) || !ids.every(isInt))
          return refusal(route, 422, 'VALIDATION_ERROR');
        const found = ids.map((id) => poolFactors.find((f) => f.id === id));
        if (found.some((f) => !f)) return refusal(route, 404, 'NOT_FOUND');
        const orphaned = found
          .filter((f) => f!.isDefault)
          .map((f) => f!.leafId);
        for (const f of found) poolFactors.splice(poolFactors.indexOf(f!), 1);
        for (const leafId of orphaned) {
          const heir = leafFactors(leafId)[0];
          if (heir) heir.isDefault = true;
        }
        return answer(route, 200, { count: found.length });
      }
      const factorMatch = new RegExp(
        `^(GET|PUT) ${P}/ghg-factors/([^/]+)$`,
      ).exec(key);
      if (factorMatch) {
        const factor = poolFactors.find((f) => f.id === int(factorMatch[2]));
        if (!factor) return refusal(route, 404, 'NOT_FOUND');
        if (factorMatch[1] === 'GET')
          return answer(route, 200, factorOut(factor));
        const fields = factorFields(body);
        if (fields) return refusal(route, 422, 'VALIDATION_ERROR', fields);
        factor.versions.push(body);
        return answer(route, 200, factorOut(factor));
      }
      return route.fallback();
    },
  );

  // ── 밴드 W12-0b2 ③: 고객사 인덱스 선택(/inventory/scope12/…) ──
  const thisYear = Number(
    new Intl.DateTimeFormat('en', {
      timeZone: 'Asia/Seoul',
      year: 'numeric',
    }).format(new Date()),
  );
  /** 해 → 고른 잎 id(빈 선택 저장도 해를 만든다). */
  const selections = new Map<number, Set<number>>();
  const facilityCount = (codeId: number | undefined) =>
    branches
      .filter((b) => b.inventoryEnabled)
      .flatMap((b) => b.lines)
      .filter((line) => line.codeId === codeId).length;
  const hasDefault = (leafId: number) =>
    poolFactors.some((f) => f.leafId === leafId && f.isDefault);
  const canPick = (n: PoolNode) => hasDefault(n.id); // S12-05: 시설 수는 보지 않는다
  const treeOut = (year: number) => {
    const chosen = selections.get(year) ?? new Set<number>();
    const nodes = [...poolNodes].sort(poolOrder);
    const leavesUnder = (n: PoolNode): PoolNode[] =>
      n.level === 'facility' ? [n] : kids(n.id).flatMap(leavesUnder);
    return {
      year,
      nodes: nodes.map((n) => {
        const leaves = leavesUnder(n);
        const line = {
          id: String(n.id),
          level: n.level,
          name: nameOf(n),
          parentId: n.parentId === null ? null : String(n.parentId),
          availableCount: leaves.reduce(
            (sum, leaf) => sum + facilityCount(leaf.codeId),
            0,
          ),
        };
        if (n.level === 'facility')
          return {
            ...line,
            facilityCodeId: String(n.codeId),
            selected: chosen.has(n.id),
            hasFactor: hasDefault(n.id),
            hasData: false,
          };
        const can = leaves.filter(canPick);
        return {
          ...line,
          facilityCodeId: null,
          selected: can.length > 0 && can.every((leaf) => chosen.has(leaf.id)),
        };
      }),
    };
  };
  const yearOf = (text: string) => {
    const year = /^-?[0-9]+$/.test(text) ? Number(text) : null;
    return year === null || year < 1990 || year > thisYear ? null : year;
  };

  await page.route(
    /\/api\/inventory\/scope12\/index-(tree|selections)(\/|\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      const method = request.method();
      let body: Json = {};
      try {
        body = request.postData() ? (request.postDataJSON() as Json) : {};
      } catch {
        body = {};
      }
      calls.push({
        method,
        path,
        query: url.search,
        body: request.postData() ? body : undefined,
      });
      if (company) return refusal(route, 400, company);
      const badYear = () =>
        refusal(route, 422, 'VALIDATION_ERROR', { year: ['지어낸 연도'] });
      const badNodes = (why: string) =>
        refusal(route, 422, 'VALIDATION_ERROR', { facilityNodeIds: [why] });
      if (method === 'GET' && path === '/inventory/scope12/index-tree') {
        const year = yearOf(url.searchParams.get('year') ?? '');
        if (year === null) return badYear();
        return answer(route, 200, treeOut(year));
      }
      const save = /^\/inventory\/scope12\/index-selections\/([^/]+)$/.exec(
        path,
      );
      if (method === 'PUT' && save) {
        const year = yearOf(save[1]!);
        if (year === null) return badYear();
        const ids = body.facilityNodeIds;
        if (
          Object.keys(body).some((k) => k !== 'facilityNodeIds') ||
          !Array.isArray(ids) ||
          !ids.every(isInt)
        )
          return badNodes('지어낸 꼴');
        if (ids.length > 1000) return badNodes('지어낸 1,000 넘음');
        const current = selections.get(year) ?? new Set<number>();
        const wanted = [...new Set(ids as number[])];
        const leaves = new Map(
          poolNodes.filter((n) => n.level === 'facility').map((n) => [n.id, n]),
        );
        if (wanted.some((id) => !leaves.has(id)))
          return badNodes('지어낸 잎 아님');
        const fresh = wanted.filter((id) => !current.has(id));
        if (fresh.some((id) => !hasDefault(id)))
          return badNodes('지어낸 기본 계수 없음');
        selections.set(year, new Set(wanted));
        return answer(route, 200, {
          selected: wanted.length,
          hiddenWithData: 0,
        });
      }
      return route.fallback();
    },
  );

  // ── 밴드 W12-1a ③: 입력 리스트(/inventory/scope12/years·rows) ──
  /** 잎 id → 해 글자 → 배출량 글자(셈 흉내 0 — spec 이 심는다). */
  const entryValues = new Map<number, Record<string, string | null>>();
  /** 범위 노드 id → 해 글자 → 합 글자. */
  const scopeValues = new Map<number, Record<string, string | null>>();
  /** 잎 id → 메모·추정·잠금 표시. */
  const entryMarks = new Map<
    number,
    { hasMemo?: boolean; estimated?: boolean; locked?: boolean }
  >();
  /** 풀 트리 차례(범위 → 유형 → 활동 → 잎, 같은 부모 안 id 차례)의 잎. */
  const treeLeaves = (): PoolNode[] => {
    const walk = (n: PoolNode): PoolNode[] =>
      n.level === 'facility' ?
        [n]
      : kids(n.id)
          .sort((a, b) => a.id - b.id)
          .flatMap(walk);
    return poolNodes
      .filter((n) => n.parentId === null)
      .sort((a, b) => a.id - b.id)
      .flatMap(walk);
  };
  const pathOf = (leaf: PoolNode): PoolNode[] => {
    const out: PoolNode[] = [];
    for (
      let n: PoolNode | undefined = leaf;
      n;
      n = poolNodes.find((p) => p.id === n!.parentId)
    )
      out.unshift(n);
    return out;
  };
  const rowsOut = (year: number, q: string | null) => {
    const years = [year - 2, year - 1, year];
    const chosen = selections.get(year) ?? new Set<number>();
    const leaves = treeLeaves().filter((leaf) => chosen.has(leaf.id));
    const base = { year, years, decimals: 2, unit: 'tCO2-eq' };
    if (leaves.length === 0) return { ...base, configured: false, scopes: [] };
    const needle = q === null || q === '' ? null : q.toLowerCase();
    const groups = new Map<number, Json[]>();
    for (const leaf of leaves) {
      const path = pathOf(leaf);
      if (
        needle !== null &&
        !path.some((n) => nameOf(n).toLowerCase().includes(needle))
      )
        continue;
      const seeded = entryValues.get(leaf.id) ?? {};
      const marks = entryMarks.get(leaf.id) ?? {};
      const list = groups.get(path[0]!.id) ?? [];
      list.push({
        nodeId: String(leaf.id),
        path: path.map(nameOf),
        values: Object.fromEntries(
          years.map((y) => [`${y}`, seeded[`${y}`] ?? null]),
        ),
        hasMemo: marks.hasMemo ?? false,
        estimated: marks.estimated ?? false,
        locked: marks.locked ?? false,
      });
      groups.set(path[0]!.id, list);
    }
    return {
      ...base,
      configured: true,
      scopes: [...groups].map(([scopeId, rows]) => {
        const seeded = scopeValues.get(scopeId) ?? {};
        return {
          scopeId: String(scopeId),
          scopeName: nameOf(poolNodes.find((n) => n.id === scopeId)!),
          values: Object.fromEntries(
            years.map((y) => [`${y}`, seeded[`${y}`] ?? null]),
          ),
          rows,
        };
      }),
    };
  };

  await page.route(
    /\/api\/inventory\/scope12\/(years|rows)(\/|\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      const method = request.method();
      calls.push({ method, path, query: url.search, body: undefined });
      if (company) return refusal(route, 400, company);
      if (method === 'GET' && path === '/inventory/scope12/years')
        return answer(route, 200, {
          years: [...selections.keys()]
            .sort((a, b) => b - a)
            .map((year) => ({
              year,
              configured: (selections.get(year)?.size ?? 0) > 0,
            })),
        });
      if (method === 'GET' && path === '/inventory/scope12/rows') {
        const year = yearOf(url.searchParams.get('year') ?? '');
        if (year === null)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            year: ['지어낸 연도'],
          });
        const q = url.searchParams.get('q');
        if (q !== null && q.length > 100)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            q: ['지어낸 100자 넘음'],
          });
        return answer(route, 200, rowsOut(year, q));
      }
      return route.fallback();
    },
  );

  // ── 밴드 W12-1b ②: S3 상세 입력 경로(서버 actions/entries.py 를 따름). 뒤에 건 route 가 먼저라 위 years·rows 자리와 겹치지 않는다.
  //    블록 = 켠 사업장 가운데 그 잎 코드 줄이 있는 곳 · 칸 = 블록 주기(entryPeriods) · 모르는 본문 칸 422 · 값 저장 뒤 S2 값은 entrySavedValue(셈 흉내 0).
  //    밴드 W12-2 ①: 총합 = 사업장별 행 emission 의 sum_or_none · all = 사업장 합의 sum_or_none · PUT X/sites/{s}/period(옛 칸 값 숨김 · 행마다
  //    period 줄) · POST X/rows/{r}/history/{h}/restore(404 → 422 historyId 종류 → 403 factor → 422 reason → 422 맨 위 → 409 LOCKED →
  //    409 RESTORE_STALE) · 히스토리 restorable 은 같은 규칙으로 읽을 때 셈.
  type EntryLine = {
    id: number;
    lineId: number;
    unit: string;
    na: boolean;
    values: Map<string, { amount: string | null; estimated: boolean }>;
    /** 계수 바꿈·복구가 정한 행 계수(응답 factor 꼴 — 없으면 선택의 계수, W12-3 ②). */
    factor?: Json | null;
  };
  type EntryState = {
    memo: string;
    lockedAt: string | null;
    rows: EntryLine[];
    history: Map<number, Json[]>;
  };
  const entryStates = new Map<string, EntryState>();
  /** 블록 주기 — 열쇠 `${year}:${leafId}:${branchId}`(서버 InventoryEntryPeriod 는 선택(해·잎) × 사업장 — W12-3 ② R1). */
  const entryPeriods = new Map<string, 'month' | 'quarter' | 'year'>();
  const periodKey = (year: number, leafId: number, branchId: number) =>
    `${year}:${leafId}:${branchId}`;
  const entryDecimals = new Map<number, number>();
  /** 저장 뒤 S2 가 보일 값(지어낸 글자 — spec 이 정한다). */
  const entrySaved = { value: '42.5' };
  let entryRowSeq = 1;
  let historySeq = 1;
  const entryStateOf = (year: number, leafId: number) => {
    const key = `${year}:${leafId}`;
    const state = entryStates.get(key) ?? {
      memo: '',
      lockedAt: null,
      rows: [],
      history: new Map<number, Json[]>(),
    };
    entryStates.set(key, state);
    return state;
  };
  const slotsOfBlock = (year: number, leafId: number, branchId: number) => {
    const period =
      entryPeriods.get(periodKey(year, leafId, branchId)) ?? 'month';
    if (period === 'year') return [`${year}`];
    if (period === 'quarter') return [1, 2, 3, 4].map((q) => `${year}-Q${q}`);
    return Array.from(
      { length: 12 },
      (_, i) => `${year}-${String(i + 1).padStart(2, '0')}`,
    );
  };
  const entryBlocks = (leaf: PoolNode) =>
    branches
      .filter((b) => b.inventoryEnabled)
      .map((branch) => ({
        branch,
        lines: branch.lines.filter((line) => line.codeId === leaf.codeId),
      }))
      .filter((block) => block.lines.length > 0);
  const entryFactorOut = (leaf: PoolNode): Json =>
    poolFactorOut(poolFactors.find((f) => f.leafId === leaf.id && f.isDefault));
  /** 풀 계수의 응답 꼴(EntryFactorOut — 지금 판). 상세 factor 와 행 factor 가 같이 쓴다. */
  const poolFactorOut = (factor: PoolFactor | undefined): Json => {
    const body = (factor?.versions.at(-1) ?? factorBody('지어낸 계수')) as Json;
    return {
      factorId: String(factor?.id ?? 0),
      versionId: `${factor?.id ?? 0}01`,
      version: factor?.versions.length ?? 1,
      name: body.name,
      source: body.source,
      isCustom: false,
      inputUnit: body.inputUnit,
      ncvEnabled: body.ncvEnabled,
      ncv: body.ncv,
      ncvUnit: body.ncvUnit,
      factorUnit: 'kgGHG/kL',
      gases: (body.gases as Json[]).map((gas) => ({
        gas: gas.gas,
        enabled: gas.enabled,
        factor: gas.factor ?? null,
        gwp: gas.gwp ?? null,
      })),
    };
  };
  /** 0 이상 십진 글자 합(서버 sum_or_none — 셈한 값이 하나도 없으면 null · 뒤 0 걷음). */
  const sumOrNone = (values: readonly (string | null)[]) => {
    const found = values.filter((v): v is string => v !== null);
    if (found.length === 0) return null;
    const places = Math.max(
      ...found.map((v) => (v.split('.')[1] ?? '').length),
    );
    const total = found.reduce((sum, v) => {
      const [whole, frac = ''] = v.split('.');
      return sum + BigInt(`${whole}${frac.padEnd(places, '0')}`);
    }, 0n);
    const text = total.toString().padStart(places + 1, '0');
    const head = text.slice(0, text.length - places);
    const tail = text.slice(text.length - places).replace(/0+$/, '');
    return tail === '' ? head : `${head}.${tail}`;
  };
  /** 지금 주기 칸의 값만(옛 칸 값은 숨김 — 서버 set_period). */
  const shownOf = (row: EntryLine, allowed: readonly string[]) =>
    [...row.values]
      .filter(([slot]) => allowed.includes(slot))
      .sort(([a], [b]) => a.localeCompare(b));
  /** 셈 흉내 0 — 기본 '1.5', 계수를 바꾼 행은 계수마다 다른 지어낸 글자(critic B1 — 풀 2.<id> · 직접입력 3.<id>). */
  const emissionOf = (row: EntryLine, allowed: readonly string[]) => {
    if (row.na || !shownOf(row, allowed).some(([, v]) => v.amount !== null))
      return null;
    if (!row.factor) return '1.5';
    return row.factor.isCustom ?
        `3.${row.factor.customId as string}`
      : `2.${row.factor.factorId as string}`;
  };
  const entryIndexOut = (year: number, leaf: PoolNode): Json => {
    const state = entryStateOf(year, leaf.id);
    const years = [year - 2, year - 1, year];
    const blocks = entryBlocks(leaf);
    /** 그 해 블록 행 배출량 합(지난 해는 그 해 상태가 있을 때만). */
    const siteTotal = (y: number, branchId: number, lines: readonly Line[]) => {
      const rows = entryStates.get(`${y}:${leaf.id}`)?.rows ?? [];
      const allowed = slotsOfBlock(y, leaf.id, branchId);
      return sumOrNone(
        rows
          .filter((row) => lines.some((line) => line.id === row.lineId))
          .map((row) => emissionOf(row, allowed)),
      );
    };
    const bySite = blocks.map(({ branch, lines }) => ({
      siteId: String(branch.id),
      siteName: branch.name,
      values: Object.fromEntries(
        years.map((y) => [`${y}`, siteTotal(y, branch.id, lines)]),
      ),
    }));
    return {
      year,
      nodeId: String(leaf.id),
      name: nameOf(leaf),
      path: pathOf(leaf).map(nameOf),
      decimals: entryDecimals.get(year) ?? 2,
      unit: 'tCO2-eq',
      unitOptions: ['kL', 'L'],
      factor: entryFactorOut(leaf),
      locked: state.lockedAt !== null,
      lockedAt: state.lockedAt,
      lockedBy:
        state.lockedAt === null ? null : { id: '1', name: '지어낸-사람' },
      memo: state.memo,
      sites: blocks.map(({ branch, lines }) => ({
        siteId: String(branch.id),
        siteName: branch.name,
        period:
          entryPeriods.get(periodKey(year, leaf.id, branch.id)) ?? 'month',
        slots: slotsOfBlock(year, leaf.id, branch.id),
        facilities: lines.map((line) => ({
          id: String(line.id),
          detailName: line.detailName,
          hasRow: state.rows.some((row) => row.lineId === line.id),
        })),
        rows: state.rows
          .filter((row) => lines.some((line) => line.id === row.lineId))
          .map((row) => ({
            rowId: String(row.id),
            siteFacilityId: String(row.lineId),
            detailName: lines.find((line) => line.id === row.lineId)!
              .detailName,
            unit: row.unit,
            na: row.na,
            values: shownOf(row, slotsOfBlock(year, leaf.id, branch.id)).map(
              ([slot, value]) => ({ slot, ...value }),
            ),
            emission: emissionOf(row, slotsOfBlock(year, leaf.id, branch.id)),
            emissionProblem: null,
            factor: row.factor ?? null,
          })),
      })),
      totals: {
        years,
        all: Object.fromEntries(
          years.map((y) => [
            `${y}`,
            sumOrNone(bySite.map((site) => site.values[`${y}`] ?? null)),
          ]),
        ),
        bySite,
      },
    };
  };
  const stray = (raw: unknown, known: readonly string[], at: string) =>
    typeof raw !== 'object' || raw === null ?
      []
    : Object.keys(raw)
        .filter((key) => !known.includes(key))
        .map((key) => `${at}${key}`);
  const entryRecord = (state: EntryState, rowId: number, line: Json) => {
    const list = state.history.get(rowId) ?? [];
    list.unshift({
      historyId: String(historySeq++),
      at: '2026-01-02T03:04:05Z',
      slot: null,
      before: null,
      after: null,
      actor: {
        kind: admin ? 'admin' : 'service',
        id: '1',
        name: '지어낸-사람',
      },
      reason: null,
      beforeFactor: null,
      afterFactor: null,
      ...line,
    });
    state.history.set(rowId, list);
  };
  /** 서버 set_period 의 바꿈: 같으면 0 · 블록 주기를 바꾸고(옛 칸 값 그대로 — 숨김) 블록 행마다 period 줄. */
  const changePeriod = (
    year: number,
    leafId: number,
    state: EntryState,
    branchId: number,
    lines: readonly Line[],
    period: 'month' | 'quarter' | 'year',
    reason: string | null,
  ) => {
    const key = periodKey(year, leafId, branchId);
    const old = entryPeriods.get(key) ?? 'month';
    if (old === period) return;
    entryPeriods.set(key, period);
    for (const row of state.rows)
      if (lines.some((line) => line.id === row.lineId))
        entryRecord(state, row.id, {
          kind: 'period',
          unit: row.unit,
          before: old,
          after: period,
          reason,
        });
  };
  /** 서버 restore_problem — 종류 → 맨 위 → 잠금 → 낡음(value 칸이 지금 주기 밖·단위 다름). null = 복구 가능. */
  const restoreProblem = (
    year: number,
    leaf: PoolNode,
    state: EntryState,
    rowId: number,
    line: Json,
  ): 'kind' | 'top' | 'locked' | 'stale' | null => {
    if (!['value', 'period', 'factor'].includes(line.kind as string))
      return 'kind';
    if (state.history.get(rowId)?.[0]?.historyId === line.historyId)
      return 'top';
    if (state.lockedAt !== null) return 'locked';
    const row = state.rows.find((r) => r.id === rowId);
    if (line.kind === 'value' && row) {
      const block = entryBlocks(leaf).find(({ lines }) =>
        lines.some((l) => l.id === row.lineId),
      );
      const allowed = block ? slotsOfBlock(year, leaf.id, block.branch.id) : [];
      if (!allowed.includes(line.slot as string) || line.unit !== row.unit)
        return 'stale';
    }
    return null;
  };
  const entryMark = (year: number, leaf: PoolNode, state: EntryState) => {
    if (year !== thisYear) return;
    entryMarks.set(leaf.id, {
      hasMemo: state.memo !== '',
      locked: state.lockedAt !== null,
      estimated: state.rows.some((row) =>
        [...row.values.values()].some((v) => v.estimated),
      ),
    });
  };
  /** 행 저장(서버 save_rows) — 걸리면 0 씀. 값은 칸 단위 덮음. 없으면 fields. */
  const entrySave = (
    year: number,
    leaf: PoolNode,
    state: EntryState,
    branchId: number,
    body: Json,
    lines: readonly Line[],
  ): Record<string, string[]> | null => {
    const fields: Record<string, string[]> = {};
    const bad = (key: string) => {
      fields[key] = ['지어낸 거절'];
    };
    for (const key of stray(body, ['rows'], '')) bad(key);
    const rows = body.rows as Json[];
    const allowed = new Set(slotsOfBlock(year, leaf.id, branchId));
    const seen = new Set<unknown>();
    rows.forEach((row, i) => {
      for (const key of stray(
        row,
        ['rowId', 'siteFacilityId', 'unit', 'na', 'values'],
        `rows.${i}.`,
      ))
        bad(key);
      if (
        !isInt(row.siteFacilityId) ||
        !lines.some((line) => line.id === row.siteFacilityId) ||
        seen.has(row.siteFacilityId)
      )
        bad(`rows.${i}.siteFacilityId`);
      seen.add(row.siteFacilityId);
      if (row.rowId === undefined || row.rowId === null) {
        if (state.rows.some((r) => r.lineId === row.siteFacilityId))
          bad(`rows.${i}.siteFacilityId`);
      } else if (
        !isInt(row.rowId) ||
        !state.rows.some((r) => r.id === row.rowId)
      )
        bad(`rows.${i}.rowId`);
      if (row.unit !== 'kL' && row.unit !== 'L') bad(`rows.${i}.unit`);
      const slots = new Set<unknown>();
      (row.values as Json[]).forEach((value, j) => {
        for (const key of stray(
          value,
          ['slot', 'amount', 'estimated'],
          `rows.${i}.values.${j}.`,
        ))
          bad(key);
        if (!allowed.has(value.slot as string) || slots.has(value.slot))
          bad(`rows.${i}.values.${j}.slot`);
        slots.add(value.slot);
        if (
          value.amount !== undefined &&
          value.amount !== null &&
          !(
            typeof value.amount === 'string' &&
            /^[0-9]{1,18}(\.[0-9]{1,6})?$/.test(value.amount) &&
            value.amount !== entryRejectAmount.value
          )
        )
          bad(`rows.${i}.values.${j}.amount`);
      });
    });
    if (Object.keys(fields).length > 0) return fields;
    for (const raw of rows) {
      let row = state.rows.find((r) => r.id === raw.rowId);
      if (!row) {
        row = {
          id: entryRowSeq++,
          lineId: raw.siteFacilityId as number,
          unit: raw.unit as string,
          na: false,
          values: new Map(),
        };
        state.rows.push(row);
      }
      if (row.unit !== raw.unit)
        entryRecord(state, row.id, {
          kind: 'unit',
          unit: raw.unit,
          before: row.unit,
          after: raw.unit,
        });
      row.unit = raw.unit as string;
      const na = (raw.na as boolean | undefined) ?? false;
      if (na !== row.na)
        entryRecord(state, row.id, {
          kind: na ? 'na_on' : 'na_off',
          unit: row.unit,
        });
      row.na = na;
      for (const value of raw.values as Json[]) {
        const slot = value.slot as string;
        const was = row.values.get(slot);
        const amount = (value.amount as string | null | undefined) ?? null;
        const estimated = (value.estimated as boolean | undefined) ?? false;
        if (was === undefined && amount === null && !estimated) continue;
        if ((was?.amount ?? null) !== amount)
          entryRecord(state, row.id, {
            kind: 'value',
            slot,
            unit: row.unit,
            before: was?.amount ?? null,
            after: amount,
          });
        row.values.set(slot, { amount, estimated });
      }
    }
    if (year === thisYear) {
      const seeded = entryValues.get(leaf.id) ?? {};
      entryValues.set(leaf.id, { ...seeded, [`${year}`]: entrySaved.value });
    }
    entryMark(year, leaf, state);
    return null;
  };
  // ── 밴드 W12-3 ②: 행 계수 바꿈(PUT X/rows/{r}/factor)·factor 줄 복구 — 서버 set_row_factor·_change_factor 를 따름(값은 지어낸 것).
  const REASON_MAX = 500;
  const FACTOR_IN_FIELDS = [
    'name',
    'source',
    'baseYear',
    'tier',
    'countryCode',
    'industryCode',
    'inputUnit',
    'emissionUnit',
    'ncvEnabled',
    'ncv',
    'ncvUnit',
    'factorUnit',
    'gases',
    'note',
  ];
  /** 서버 환산표(unit-conversions.json) 쌍 그대로 「from>to」 — critic R2. */
  const UNIT_PAIRS = [
    'L>kL',
    'kL>L',
    'm3>L',
    'L>m3',
    'm3>kL',
    'kL>m3',
    'kNm3>Nm3',
    'Nm3>kNm3',
    'g>kg',
    'kg>g',
    'kg>t',
    't>kg',
    'g>t',
    'kWh>MWh',
    'MWh>kWh',
    'GWh>MWh',
    'kWh>MJ',
    'MWh>MJ',
    'MWh>GJ',
    'MJ>GJ',
    'GJ>MJ',
    'MJ>TJ',
    'TJ>MJ',
    'GJ>TJ',
    'TJ>GJ',
  ];
  /** 상세 unitOptions 와 같은 행 단위(잎 kL 의 선택지). */
  const entryUnitOptions = ['kL', 'L'];
  /** 서버 custom_unit_problem(sid:MARC-ISSUE-548) 흉내. */
  const customUnitProblem = (rowUnits: readonly string[], custom: Json) => {
    const ok = (a: string, b: string) =>
      a === b || UNIT_PAIRS.includes(`${a}>${b}`);
    const input = (custom.inputUnit as Json).unit as string;
    const ncvOn = custom.ncvEnabled === true;
    const ncvUnit = custom.ncvUnit as Json | null | undefined;
    const factorUnit =
      (custom.factorUnit as string | null | undefined) ??
      (ncvOn ? 'kg/TJ' : `kg/${input}`);
    const [numerator = '', denominator = ''] = factorUnit.split('/');
    const out: Record<string, string> = {};
    if (rowUnits.some((unit) => !ok(unit, input)))
      out['custom.inputUnit'] = '지어낸 거절';
    if (ncvOn && ncvUnit) {
      if (!ok(ncvUnit.unit as string, denominator))
        out['custom.ncvUnit'] = '지어낸 거절';
    } else if (!ok(input, denominator))
      out['custom.factorUnit'] = '지어낸 거절';
    if (!ok(numerator, 't')) out['custom.factorUnit'] = '지어낸 거절';
    return out;
  };
  let customSeq = 1;
  /** 직접입력 본문 → EntryCustomFactorOut 꼴(늘 새 행). */
  const customOut = (custom: Json): Json => {
    const ncvOn = custom.ncvEnabled === true;
    const input = (custom.inputUnit as Json).unit as string;
    return {
      customId: `${customSeq++}`,
      name: custom.name,
      source: custom.source,
      baseYear: custom.baseYear ?? 0,
      tier: custom.tier ?? 0,
      countryCode: custom.countryCode,
      industryCode: custom.industryCode,
      inputUnit: custom.inputUnit,
      ncvEnabled: ncvOn,
      ncv: ncvOn ? (custom.ncv ?? null) : null,
      ncvUnit: ncvOn ? (custom.ncvUnit ?? null) : null,
      factorUnit:
        (custom.factorUnit as string | null | undefined) ??
        (ncvOn ? 'kg/TJ' : `kg/${input}`),
      gases: (custom.gases as Json[]).map((gas) => ({
        gas: gas.gas,
        enabled: gas.enabled,
        factor: gas.factor ?? null,
        gwp: gas.gwp ?? null,
      })),
      note: custom.note ?? '',
      isCustom: true,
    };
  };
  /** 히스토리 참조(EntryFactorRefOut) — null 행 계수는 선택의 판(서버 _ref_or_pinned). */
  const factorRefOf = (leaf: PoolNode, factor: Json | null): Json => {
    const shown = factor ?? entryFactorOut(leaf);
    return shown.isCustom ?
        {
          versionId: null,
          customId: shown.customId,
          name: shown.name,
          isCustom: true,
        }
      : {
          versionId: shown.versionId,
          customId: null,
          name: shown.name,
          isCustom: false,
        };
  };
  const refKey = (ref: Json) =>
    ref.customId ?
      `c:${ref.customId as string}`
    : `v:${ref.versionId as string}`;
  const factorByRef = new Map<string, Json>();
  /** 서버 _change_factor: 같은 계수면 0 · 아니면 factor 줄(before = 그 행 지금 계수 — R3) + 행 계수 바꿈. */
  const changeRowFactor = (
    leaf: PoolNode,
    state: EntryState,
    row: EntryLine,
    target: Json | null,
    reason: string | null,
  ) => {
    const before = factorRefOf(leaf, row.factor ?? null);
    const after = factorRefOf(leaf, target);
    if (refKey(before) === refKey(after)) return;
    if (target !== null) factorByRef.set(refKey(after), target);
    entryRecord(state, row.id, {
      kind: 'factor',
      unit: row.unit,
      reason,
      beforeFactor: before,
      afterFactor: after,
    });
    row.factor = target;
  };
  /** 올리기 심는 답(앞에서 하나씩 꺼냄, 비면 넷 다 0 인 200). */
  const uploadAnswers: GhgUploadAnswer[] = [];
  /** 서버 판정 차례: 회사 거절 400 → 413 → 해 없음·선택 0 404 → 빈 바이트 422 file → 심는 답. */
  const uploadFile = async (route: Route, year: number, size: number) => {
    if (company) return refusal(route, 400, company);
    if (size > UPLOAD_MAX) return refusal(route, 413, 'BODY_TOO_LARGE');
    if ((selections.get(year)?.size ?? 0) === 0)
      return refusal(route, 404, 'NOT_FOUND');
    if (size === 0)
      return refusal(route, 422, 'INVALID_UPLOAD', {
        file: ['지어낸 빈 파일'],
      });
    const next = uploadAnswers.shift();
    if (!next)
      return answer(route, 200, {
        added: 0,
        filled: 0,
        unchanged: 0,
        unresolved: 0,
      });
    next.apply?.();
    if ('abort' in next) return route.abort('connectionreset');
    if ('body' in next) return answer(route, next.status, next.body);
    return refusal(route, next.status, next.code, next.fields ?? null);
  };
  /** 양식·데이터 엑셀(서버 차례): scope 422 → 켠 사업장 아닌 siteId 404 → 해 없음·선택 0 404 → 양식은 채울 줄 0 404. */
  const excelFile = (
    route: Route,
    year: number,
    what: 'template' | 'export',
    url: URL,
  ) => {
    const scope = url.searchParams.get('scope');
    const allowed = what === 'template' ? ['1', '2'] : ['all', '1', '2'];
    if (scope !== null && !allowed.includes(scope))
      return refusal(route, 422, 'VALIDATION_ERROR', {
        scope: ['지어낸 scope'],
      });
    const siteId = Number(url.searchParams.get('siteId'));
    const hasSite = url.searchParams.has('siteId');
    if (
      what === 'template' &&
      hasSite &&
      !branches.some((b) => b.id === siteId && b.inventoryEnabled)
    )
      return refusal(route, 404, 'NOT_FOUND');
    const chosen = selections.get(year) ?? new Set<number>();
    if (chosen.size === 0) return refusal(route, 404, 'NOT_FOUND');
    const roots = poolNodes.filter((n) => n.parentId === null);
    const root =
      scope === null || scope === 'all' ? null : roots[Number(scope) - 1];
    if (root === undefined) return refusal(route, 404, 'NOT_FOUND');
    if (what === 'template') {
      const lines = treeLeaves()
        .filter((leaf) => chosen.has(leaf.id))
        .filter((leaf) => root === null || pathOf(leaf)[0]!.id === root.id)
        .flatMap(entryBlocks)
        .filter(({ branch }) => !hasSite || branch.id === siteId);
      if (lines.length === 0) return refusal(route, 404, 'NOT_FOUND');
    }
    const name =
      what === 'template' ? '지어낸 양식.xlsx' : '지어낸 데이터.xlsx';
    return route.fulfill({
      status: 200,
      contentType: XLSX_TYPE,
      headers: {
        'Content-Disposition': `attachment; filename*=utf-8''${encodeURIComponent(name)}`,
        'X-Content-Type-Options': 'nosniff',
      },
      body: Buffer.from([0x50, 0x4b, 0x03, 0x04]),
    });
  };
  /** 시험이 심는 「서버가 거절하는 금액」(웹 검사는 통과, 서버 422 갈래). */
  const entryRejectAmount: { value: string | null } = { value: null };

  await page.route(
    /\/api\/inventory\/scope12\/years\/[^/]+\/(indexes|decimals|template|export|uploads)(\/|\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      const method = request.method();
      // 올리기는 맨 바이트라 JSON 으로 읽지 않는다 — 앞에서 가른다(W12-5 ①).
      const upload = /^\/inventory\/scope12\/years\/(\d+)\/uploads$/.exec(path);
      if (upload && method === 'POST') {
        const bytes = request.postDataBuffer();
        calls.push({
          method,
          path,
          query: url.search,
          body: undefined,
          size: bytes?.length ?? 0,
          contentType: request.headers()['content-type'] ?? null,
        });
        return uploadFile(route, Number(upload[1]), bytes?.length ?? 0);
      }
      const excel =
        /^\/inventory\/scope12\/years\/(\d+)\/(template|export)$/.exec(path);
      if (excel && method === 'GET') {
        calls.push({ method, path, query: url.search, body: undefined });
        if (company) return refusal(route, 400, company);
        return excelFile(
          route,
          Number(excel[1]),
          excel[2] as 'template' | 'export',
          url,
        );
      }
      const body = (request.postDataJSON() ?? undefined) as Json | undefined;
      calls.push({ method, path, query: url.search, body });
      if (company) return refusal(route, 400, company);
      const decimals = /^\/inventory\/scope12\/years\/(\d+)\/decimals$/.exec(
        path,
      );
      if (decimals && method === 'PUT') {
        const out = stray(body, ['decimals'], '');
        const n = body?.decimals;
        if (out.length > 0 || typeof n !== 'number' || n < 0 || n > 3)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            [out[0] ?? 'decimals']: ['지어낸 거절'],
          });
        entryDecimals.set(Number(decimals[1]), n);
        return answer(route, 200, { decimals: n });
      }
      const match =
        /^\/inventory\/scope12\/years\/(\d+)\/indexes\/(\d+)(\/.*)?$/.exec(
          path,
        );
      if (!match) return route.fallback();
      const year = Number(match[1]);
      const leafId = Number(match[2]);
      const rest = match[3] ?? '';
      const leaf = poolNodes.find((n) => n.id === leafId);
      if (!leaf || !(selections.get(year) ?? new Set()).has(leafId))
        return refusal(route, 404, 'NOT_FOUND');
      const state = entryStateOf(year, leafId);
      if (method === 'GET' && rest === '')
        return answer(route, 200, entryIndexOut(year, leaf));
      const site = /^\/sites\/(\d+)\/rows$/.exec(rest);
      if (method === 'PUT' && site) {
        const block = entryBlocks(leaf).find(
          ({ branch }) => branch.id === Number(site[1]),
        );
        if (!block) return refusal(route, 404, 'NOT_FOUND');
        if (state.lockedAt !== null) return refusal(route, 409, 'LOCKED');
        const fields = entrySave(
          year,
          leaf,
          state,
          block.branch.id,
          body as Json,
          block.lines,
        );
        if (fields) return refusal(route, 422, 'VALIDATION_ERROR', fields);
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      if (method === 'POST' && rest === '/rows/delete') {
        const ids = body?.ids;
        if (
          stray(body, ['ids'], '').length > 0 ||
          !Array.isArray(ids) ||
          ids.length === 0 ||
          !ids.every(isInt)
        )
          return refusal(route, 422, 'VALIDATION_ERROR', {
            ids: ['지어낸 거절'],
          });
        if (state.lockedAt !== null) return refusal(route, 409, 'LOCKED');
        if (ids.some((id) => !state.rows.some((row) => row.id === id)))
          return refusal(route, 404, 'NOT_FOUND');
        state.rows = state.rows.filter((row) => !ids.includes(row.id));
        return answer(route, 200, { count: ids.length });
      }
      if (method === 'PUT' && rest === '/memo') {
        if (
          stray(body, ['memo'], '').length > 0 ||
          typeof body?.memo !== 'string' ||
          body.memo.length > 2000
        )
          return refusal(route, 422, 'VALIDATION_ERROR', {
            memo: ['지어낸 거절'],
          });
        if (state.lockedAt !== null) return refusal(route, 409, 'LOCKED');
        state.memo = body.memo;
        entryMark(year, leaf, state);
        return answer(route, 200, { memo: state.memo });
      }
      if (method === 'POST' && rest === '/lock') {
        state.lockedAt ??= '2026-01-02T03:04:05Z';
        entryMark(year, leaf, state);
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      if (method === 'DELETE' && rest === '/lock') {
        if (!admin) return refusal(route, 403, 'FORBIDDEN');
        state.lockedAt = null;
        entryMark(year, leaf, state);
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      const history = /^\/rows\/(\d+)\/history$/.exec(rest);
      if (method === 'GET' && history) {
        const rowId = Number(history[1]);
        if (!state.rows.some((row) => row.id === rowId))
          return refusal(route, 404, 'NOT_FOUND');
        const all = (state.history.get(rowId) ?? []).map((line) => ({
          ...line,
          restorable: restoreProblem(year, leaf, state, rowId, line) === null,
        }));
        const pageNo = Number(url.searchParams.get('page') ?? '1');
        const size = Number(url.searchParams.get('pageSize') ?? '20');
        const totalPages = Math.max(1, Math.ceil(all.length / size));
        return answer(route, 200, {
          count: all.length,
          totalPages,
          page: pageNo,
          pageSize: size,
          hasNext: pageNo < totalPages,
          hasPrevious: pageNo > 1,
          results: all.slice((pageNo - 1) * size, pageNo * size),
        });
      }
      const period = /^\/sites\/(\d+)\/period$/.exec(rest);
      if (method === 'PUT' && period) {
        const value = body?.period;
        if (stray(body, ['period'], '').length > 0)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            [stray(body, ['period'], '')[0]!]: ['지어낸 거절'],
          });
        if (value !== 'month' && value !== 'quarter' && value !== 'year')
          return refusal(route, 422, 'VALIDATION_ERROR', {
            period: ['지어낸 거절'],
          });
        const block = entryBlocks(leaf).find(
          ({ branch }) => branch.id === Number(period[1]),
        );
        if (!block) return refusal(route, 404, 'NOT_FOUND');
        if (state.lockedAt !== null) return refusal(route, 409, 'LOCKED');
        changePeriod(
          year,
          leaf.id,
          state,
          block.branch.id,
          block.lines,
          value,
          null,
        );
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      const restore = /^\/rows\/(\d+)\/history\/(\d+)\/restore$/.exec(rest);
      if (method === 'POST' && restore) {
        if (typeof body !== 'object' || body === null)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            body: ['지어낸 거절'],
          });
        if (stray(body, ['reason'], '').length > 0)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            [stray(body, ['reason'], '')[0]!]: ['지어낸 거절'],
          });
        const rowId = Number(restore[1]);
        const row = state.rows.find((r) => r.id === rowId);
        const line = (state.history.get(rowId) ?? []).find(
          (l) => l.historyId === restore[2],
        );
        if (!row || !line) return refusal(route, 404, 'NOT_FOUND');
        const problem = restoreProblem(year, leaf, state, rowId, line);
        const historyId = { historyId: ['지어낸 거절'] };
        if (problem === 'kind')
          return refusal(route, 422, 'VALIDATION_ERROR', historyId);
        if (line.kind === 'factor' && !admin)
          return refusal(route, 403, 'FORBIDDEN');
        const raw = body.reason;
        const reason = typeof raw === 'string' ? raw.trim() || null : null;
        if (line.kind === 'factor' && reason === null)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            reason: ['지어낸 거절'],
          });
        if (reason !== null && reason.length > REASON_MAX)
          return refusal(route, 422, 'VALIDATION_ERROR', {
            reason: ['지어낸 거절'],
          }); // R4 — 서버 _reason_problem
        if (problem === 'top')
          return refusal(route, 422, 'VALIDATION_ERROR', historyId);
        if (problem === 'locked') return refusal(route, 409, 'LOCKED');
        if (problem === 'stale') return refusal(route, 409, 'RESTORE_STALE');
        const block = entryBlocks(leaf).find(({ lines }) =>
          lines.some((l) => l.id === row.lineId),
        )!;
        if (line.kind === 'value') {
          const slot = line.slot as string;
          const was = row.values.get(slot);
          const amount = (line.after as string | null) ?? null;
          if ((was?.amount ?? null) !== amount) {
            row.values.set(slot, {
              amount,
              estimated: was?.estimated ?? false,
            });
            entryRecord(state, rowId, {
              kind: 'value',
              slot,
              unit: row.unit,
              before: was?.amount ?? null,
              after: amount,
              reason,
            });
          }
        } else if (line.kind === 'period') {
          const after = line.after as 'month' | 'quarter' | 'year' | null;
          if (after !== null)
            changePeriod(
              year,
              leaf.id,
              state,
              block.branch.id,
              block.lines,
              after,
              reason,
            );
        } else {
          const after = (line.afterFactor ?? null) as Json | null;
          const pinned = factorRefOf(leaf, null);
          const target =
            after === null || refKey(after) === refKey(pinned) ?
              null
            : (factorByRef.get(refKey(after)) ??
              poolFactors
                .filter((f) => f.leafId === leaf.id)
                .map((f) => poolFactorOut(f))
                .find((out) => out.versionId === after.versionId) ??
              null);
          changeRowFactor(leaf, state, row, target, reason);
        }
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      const rowFactor = /^\/rows\/(\d+)\/factor$/.exec(rest);
      if (method === 'PUT' && rowFactor) {
        // 서버 차례(W12-3 ② · critic R1 실측): 스키마 422 → 403 → 본문 422 → 404 → 422 단위(548) → 409 → 다른 잎 422 → 같은 계수 0 바뀜.
        const bad = (fields: Record<string, string>) =>
          refusal(
            route,
            422,
            'VALIDATION_ERROR',
            Object.fromEntries(
              Object.entries(fields).map(([k, v]) => [k, [v]]),
            ),
          );
        if (typeof body !== 'object' || body === null)
          return bad({ body: '지어낸 거절' });
        const custom = (body.custom ?? null) as Json | null;
        const strays = [
          ...stray(body, ['factorId', 'custom', 'reason'], ''),
          ...(custom ? stray(custom, FACTOR_IN_FIELDS, 'custom.') : []),
        ];
        if (strays.length > 0) return bad({ [strays[0]!]: '지어낸 거절' });
        const factorId = body.factorId ?? null;
        if (factorId !== null && (!isInt(factorId) || (factorId as number) < 1))
          return bad({ factorId: '지어낸 거절' });
        if (!admin) return refusal(route, 403, 'FORBIDDEN');
        const reason =
          typeof body.reason === 'string' ? body.reason.trim() || null : null;
        const problems: Record<string, string> = {};
        if (reason === null || reason.length > REASON_MAX)
          problems.reason = '지어낸 거절';
        if ((factorId === null) === (custom === null))
          problems.factorId = '지어낸 거절';
        else if (custom) {
          if (typeof custom.name !== 'string' || custom.name.trim() === '')
            problems['custom.name'] = '지어낸 거절';
          const emission = custom.emissionUnit as Json | null | undefined;
          if (emission && emission.unit !== 'tCO2-eq')
            problems['custom.emissionUnit'] = '지어낸 거절';
        }
        if (Object.keys(problems).length > 0) return bad(problems);
        const row = state.rows.find((r) => r.id === Number(rowFactor[1]));
        if (!row) return refusal(route, 404, 'NOT_FOUND');
        if (custom) {
          const mismatch = customUnitProblem(entryUnitOptions, custom);
          if (Object.keys(mismatch).length > 0) return bad(mismatch); // 548 흉내
        }
        if (state.lockedAt !== null) return refusal(route, 409, 'LOCKED');
        let target: Json | null;
        if (factorId !== null) {
          const found = poolFactors.find(
            (f) => f.leafId === leaf.id && f.id === factorId,
          );
          if (!found) return bad({ factorId: '지어낸 거절' });
          target = found.isDefault ? null : poolFactorOut(found);
        } else target = customOut(custom!);
        changeRowFactor(leaf, state, row, target, reason);
        return answer(route, 200, entryIndexOut(year, leaf));
      }
      return route.fallback();
    },
  );

  /** 히스토리 줄 하나를 심는다(밴드 W12-2 ② — 고객사 화면엔 계수를 바꿀 길이 없어 factor 줄은 이렇게만 생긴다). */
  const entryNote = (year: number, leafId: number, rowId: number, line: Json) =>
    entryRecord(entryStateOf(year, leafId), rowId, line);

  /** 그 경로로 나간 본문들(차례대로). */
  const bodies = (key: string) =>
    calls
      .filter((call) => `${call.method} ${call.path}` === key)
      .map((call) => call.body);
  // 밴드 DB1 ②: 대시보드(S1) — GET /api/inventory/scope12/dashboard?year= (openapi Scope12DashboardOut 꼴 그대로, 셈 흉내 0).
  //   dashboards 에 심은 해는 그 답, 없는 해는 빈 판(configured 거짓 · Scope 3 없음). 연도가 네 자리 정수가 아니면 422.
  const dashboards = new Map<number, unknown>();
  const emptyDashboard = (year: number) => ({
    year,
    configured: false,
    decimals: 2,
    basis: 'location',
    unit: 'tCO2-eq',
    complete: true,
    scopes: [],
    total: {
      scope12: null,
      scope2Market: null,
      scope3: null,
      sum: null,
      scope3FailedSheets: 0,
    },
    bySite: [],
    scope3Categories: [],
  });
  await page.route(
    /\/api\/inventory\/scope12\/dashboard(\?|$)/,
    async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      const path = url.pathname.replace(/^.*?\/api(?=\/)/, '');
      calls.push({
        method: request.method(),
        path,
        query: url.search,
        body: undefined,
      });
      if (request.method() !== 'GET') return route.fallback();
      if (company) return refusal(route, 400, company);
      const year = yearOf(url.searchParams.get('year') ?? '');
      if (year === null)
        return refusal(route, 422, 'VALIDATION_ERROR', {
          year: ['지어낸 연도'],
        });
      return answer(route, 200, dashboards.get(year) ?? emptyDashboard(year));
    },
  );

  /** 「다른 탭이 저장」(밴드 K1b-3): 판을 올리고, line 을 주면 줄 하나를 더한다(검사 없음). */
  const bumpBranch = (
    id: number,
    line?: { codeId: number; detailName: string },
  ) => {
    const branch = branches.find((b) => b.id === id);
    if (!branch) throw new Error(`흉내에 없는 사업장: ${id}`);
    if (line) branch.lines.push({ id: lineSeq++, ...line });
    bump(branch);
  };
  return {
    calls,
    bodies,
    bumpBranch,
    branches,
    codes,
    poolNodes,
    poolFactors,
    selections,
    thisYear,
    entryValues,
    scopeValues,
    entryMarks,
    entryPeriods,
    entrySaved,
    entryRejectAmount,
    entryNote,
    uploadAnswers,
    dashboards,
  };
}
