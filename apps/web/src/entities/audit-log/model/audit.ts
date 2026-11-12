// 감사 기록의 꼴과 순수 함수(밴드 AD2 ①, 실서버 AD5R ①). React·DOM·통신을 모른다.
// 계약 타입(AuditEventOut·AuditActorOut·GET /audit-logs 의 쿼리)은 shared/api 가 다시 내보낸 것을 타입으로만 가져온다.
//   - auditQuery: 화면의 거르기 → 서버 쿼리. 값이 있는 칸만 담는다(빈·공백 q 는 뺀다 — 서버가 빈 q 를 422 로 막는다, AU1b-1).
//     기간은 KST 「오늘」(now + 9시간의 UTC 날짜)에서 센다. dateTo 는 오늘 그대로 — 서버가 「KST 그날 끝까지(포함)」다.
//     두 날짜는 서버가 받는 [2000-01-01, 2999-12-31] 안으로 조인다(시계가 틀려도 422 가 나지 않게).
//   - toEntry: 서버 줄 하나 → 화면 줄(사람·대상·결과 글). 글은 넣어 받는다(model 은 문구 표를 모른다 — 화면이 AUDIT_TEXT 를 넣는다).
//     AI 설정 두 사건(ai_setting_created·ai_setting_applied — 밴드 AD4X ③)은 「AI 설정(링크) · <모듈 이름> · <판> 만듦/적용」.
//     링크는 판 번호(v<n>)가 있으면 그 판, 기본 판 적용(targetId null)이나 v<n> 꼴이 아닌 이름이면 판 없이(AD-02 주소는 ?version=v<n> 만 받는다).
//   - actorOptions: 행위자 목록 → 사람 고르기의 선택지. 서버는 아이디 차례(대소문자 구분)라 화면의 이름 차례로 다시 센다.
import type { Schemas, paths } from '../../../shared/api/index.ts';

/** GET /audit-logs 의 줄 하나. */
export type AuditEventRow = Schemas['AuditEventOut'];
/** GET /audit-logs/actors 의 사람 하나. */
export type AuditActorRow = Schemas['AuditActorOut'];
/** 행동(서버 action 값 그대로 — 옮기는 표가 없다). */
export type AuditAction = AuditEventRow['action'];

/** 행동 아홉(표시 차례 — 감독 판단 Q5). 계약 enum 과 집합이 같다(model 시험). */
export const AUDIT_ACTIONS = [
  'login',
  'logout',
  'upload',
  'run',
  'download',
  'setting_change',
  'adopt',
  'exclude',
  'confirm',
] as const satisfies readonly AuditAction[];

/**
 * 대상 토막이 이어지는 자리: AD-01 계정 관리 · AD-02 AI 설정(module = 감사 줄의 module 값 또는 null, version = 「v<n>」 또는 null — 판 없이).
 * 화면은 라우터를 모른다 — 경로 컴포넌트가 주소로 바꾼다(module 이 그 모듈 주소 — 밴드 AM1).
 */
export type AuditLink =
  | { kind: 'accounts' }
  | { kind: 'ai-settings'; module: string | null; version: string | null };

/** 대상 글의 한 토막(「 · 」로 잇는다). link 가 있으면 그 토막이 링크. */
export interface AuditTargetPart {
  text: string;
  link?: AuditLink;
}

export interface AuditEntry {
  id: string;
  /** 시각(+09:00 글자). */
  at: string;
  /** 사람(이름 또는 아이디, 못 찾으면 대체 글). */
  actor: string;
  /** 사람을 찾지 못해 대체 글을 쓴 줄(관리 명령·없는 아이디·알 수 없는 사람 — 화면이 회색으로). */
  actorMissing?: boolean;
  action: AuditAction;
  /** 대상. 빈 배열이면 「—」. */
  target: readonly AuditTargetPart[];
  /** 실패 까닭 글. null 이면 성공, 빈 글자면 까닭 없는 실패. */
  failure: string | null;
}

export const AUDIT_PERIODS = ['week', 'month', 'all'] as const;
export type AuditPeriod = (typeof AUDIT_PERIODS)[number];

/** 화면의 거르기(서버 쿼리로 옮긴다 — auditQuery). */
export interface AuditFilter {
  query: string;
  period: AuditPeriod;
  /** 'all' 또는 행위자 id. */
  actorUserId: number | 'all';
  action: AuditAction | 'all';
}

/** 처음 거르기(시안 「기간: 이번 주 · 사람: 전체 · 행동: 전체」). */
export const AUDIT_NO_FILTER: AuditFilter = {
  query: '',
  period: 'week',
  actorUserId: 'all',
  action: 'all',
};

/** GET /audit-logs 의 쿼리 중 화면이 정하는 칸(쪽·회사는 어댑터가 — companyId 는 보내지 않는다). */
export type AuditQuery = Omit<
  NonNullable<paths['/audit-logs']['get']['parameters']['query']>,
  'limit' | 'offset' | 'companyId'
>;

/** 검색 글의 상한(서버 q 의 maxLength — 코드 포인트). */
export const AUDIT_QUERY_MAX = 150;
/** 서버가 받는 날짜의 끝(밖은 422 — AU1b-1). */
export const AUDIT_DATE_MIN = '2000-01-01';
export const AUDIT_DATE_MAX = '2999-12-31';

const DAY = 86_400_000;
const KST = 9 * 3_600_000;
const MIN_DAY = Date.UTC(2000, 0, 1);
const MAX_DAY = Date.UTC(2999, 11, 31);

/** UTC 자정 밀리초 → 'YYYY-MM-DD'(조인 범위 안에서만 부른다). */
const dateOf = (day: number) => new Date(day).toISOString().slice(0, 10);
/** 'YYYY-MM-DD' → UTC 자정 밀리초. */
function dayOf(date: string): number {
  const [y, m, d] = date.slice(0, 10).split('-').map(Number);
  return Date.UTC(y!, m! - 1, d!);
}
const clampDay = (day: number) => Math.min(MAX_DAY, Math.max(MIN_DAY, day));

/** KST 「오늘」의 날짜(now + 9시간의 UTC 날짜). 조이지 않은 날 그대로의 UTC 자정 밀리초. */
function kstDay(now: Date): number {
  const shifted = now.getTime() + KST;
  return shifted - (((shifted % DAY) + DAY) % DAY);
}

/** KST 「오늘」('YYYY-MM-DD'). 서버가 받는 범위 밖이면 그 끝으로 조인다. */
export const kstToday = (now: Date): string => dateOf(clampDay(kstDay(now)));

/**
 * 기간 → 날짜 범위(둘 다 포함). 이번 주 = 오늘이 든 주(월요일 시작)의 월요일 ~ 오늘, 이번 달 = 그달 1일 ~ 오늘, 전체 = null.
 * 두 값은 [2000-01-01, 2999-12-31] 안으로 조인다.
 */
export function periodRange(
  period: AuditPeriod,
  today: string,
): { dateFrom: string; dateTo: string } | null {
  if (period === 'all') return null;
  const end = dayOf(today);
  const start =
    period === 'month' ?
      Date.UTC(new Date(end).getUTCFullYear(), new Date(end).getUTCMonth(), 1)
    : end - ((new Date(end).getUTCDay() + 6) % 7) * DAY; // 월 0 … 일 6
  return {
    dateFrom: dateOf(clampDay(start)),
    dateTo: dateOf(clampDay(end)),
  };
}

/** 검색 글: 앞뒤 빈칸을 걷고 코드 포인트 150자에서 자른다. 비면 null(보내지 않는다). */
export function searchText(query: string): string | null {
  const text = [...query.trim()].slice(0, AUDIT_QUERY_MAX).join('');
  return text === '' ? null : text;
}

/** 거르기 → 서버 쿼리. 값이 있는 칸만(빈 q·'all'·전체 기간의 키는 만들지 않는다). */
export function auditQuery(filter: AuditFilter, now: Date): AuditQuery {
  const query: AuditQuery = {};
  const range = periodRange(filter.period, kstToday(now));
  if (range) {
    query.dateFrom = range.dateFrom;
    query.dateTo = range.dateTo;
  }
  const q = searchText(filter.query);
  if (q !== null) query.q = q;
  if (filter.actorUserId !== 'all') query.actorUserId = filter.actorUserId;
  if (filter.action !== 'all') query.action = filter.action;
  return query;
}

/** 줄·선택지를 그리는 글(화면이 문구 표 AUDIT_TEXT.entry 를 넣는다). */
export interface AuditEntryWords {
  actor: {
    /** 관리 명령(사람이 없는 줄). */
    command: string;
    /** 없는 아이디로 로그인을 시도한 줄. */
    anonymous: string;
    /** 지운 사람·남의 회사로 옮긴 사람. */
    unknown: string;
    /** 운영 관리자 꼬리(사람 고르기). */
    admin: string;
  };
  target: {
    /** 계정 토막(AD-01 링크). */
    account: string;
    created(label: string | null): string;
    reset(label: string | null): string;
    updated(label: string | null): string;
    passwordChanged: string;
    /** AI 설정 토막(AD-02 링크). */
    aiSetting: string;
    /** 판을 만듦(「v3 만듦」, 이름이 없으면 「만듦」). */
    settingCreated(label: string | null): string;
    /** 판을 적용함(「v2 적용」). */
    settingApplied(label: string): string;
    /** 기본 판 적용의 판 글. */
    defaultSetting: string;
  };
  /** 모듈 id → 이름(표에 없는 id 는 id 그대로). */
  modules: Readonly<Record<string, string>>;
  /** 실패 까닭 코드 → 글. 모르는 코드는 까닭 없이. */
  reasons: Readonly<Record<string, string>>;
}

/** 사람의 이름 글(이름 → 아이디). 둘 다 없으면 null. */
export const actorLabel = (
  actor: Pick<AuditActorRow, 'actorName' | 'actorUsername'>,
) => actor.actorName ?? actor.actorUsername ?? null;

/** 계정 사건의 대상: 「계정」 토막(대상이 사용자면 링크) + 사건 글. */
function accountTarget(
  row: AuditEventRow,
  words: AuditEntryWords['target'],
  rest: string,
): AuditTargetPart[] {
  const account: AuditTargetPart =
    row.targetKind === 'user' ?
      { text: words.account, link: { kind: 'accounts' } }
    : { text: words.account };
  return [account, { text: rest }];
}

/** AD-02 주소가 받는 판 꼴(「v숫자」). */
const VERSION = /^v\d+$/;

/** AI 설정 사건의 대상: 「AI 설정」 링크 토막 + (있으면) 모듈 이름 + 사건 글. */
function settingTarget(
  row: AuditEventRow,
  words: AuditEntryWords,
): AuditTargetPart[] {
  const label = row.targetLabel;
  const version =
    row.targetId !== null && label !== null && VERSION.test(label) ?
      label
    : null;
  const parts: AuditTargetPart[] = [
    {
      text: words.target.aiSetting,
      link: { kind: 'ai-settings', module: row.module, version },
    },
  ];
  if (row.module !== null)
    parts.push({
      text:
        Object.hasOwn(words.modules, row.module) ?
          words.modules[row.module]!
        : row.module,
    });
  parts.push({
    text:
      row.event === 'ai_setting_created' ? words.target.settingCreated(label)
      : row.targetId === null ?
        words.target.settingApplied(words.target.defaultSetting)
      : words.target.settingApplied(label ?? words.target.defaultSetting),
  });
  return parts;
}

/** 대상 글. 로그인·로그아웃은 대상이 자기 자신이라 빈 대상(「—」). */
function targetOf(row: AuditEventRow, all: AuditEntryWords): AuditTargetPart[] {
  const words = all.target;
  const label = row.targetLabel;
  switch (row.event) {
    case 'user_created':
      return accountTarget(row, words, words.created(label));
    case 'password_reset':
      return accountTarget(row, words, words.reset(label));
    case 'user_updated':
      return accountTarget(row, words, words.updated(label));
    case 'password_changed':
      return accountTarget(row, words, words.passwordChanged);
    case 'login_succeeded':
    case 'login_failed':
    case 'login_locked':
    case 'logout':
      return [];
    case 'ai_setting_created':
    case 'ai_setting_applied':
      return settingTarget(row, all);
    default:
      // 파일 줄(document_uploaded·run_created·run_file_downloaded)과 모르는 사건: 대상 글자 그대로.
      return label === null ? [] : [{ text: label }];
  }
}

/** 서버 줄 하나 → 화면 줄. */
export function toEntry(
  row: AuditEventRow,
  words: AuditEntryWords,
): AuditEntry {
  const name = actorLabel(row);
  const actor =
    name ??
    (row.actorKind === 'command' ? words.actor.command
    : row.actorKind === 'anonymous' ? words.actor.anonymous
    : words.actor.unknown);
  return {
    id: String(row.id),
    at: row.at,
    actor,
    actorMissing: name === null,
    action: row.action,
    target: targetOf(row, words),
    failure:
      row.result === 'success' ? null
      : row.reason !== null && Object.hasOwn(words.reasons, row.reason) ?
        words.reasons[row.reason]!
      : '',
  };
}

/** 사람 고르기의 선택지 하나. */
export interface AuditActorOption {
  value: number;
  label: string;
}

/**
 * 행위자 목록 → 선택지. 이름이 풀린 사람은 이름 글 차례(대소문자·악센트 무시, 같으면 id 차례), 풀리지 않은 사람은 맨 뒤에 서버 차례 그대로.
 * 같은 글이 둘 이상이면 「글 (아이디)」(아이디가 없으면 id). 운영 관리자는 꼬리 「 · 운영 관리자」.
 */
export function actorOptions(
  actors: readonly AuditActorRow[],
  words: AuditEntryWords['actor'],
): AuditActorOption[] {
  const named = actors
    .filter((actor) => actorLabel(actor) !== null)
    .map((actor) => ({ actor, text: actorLabel(actor)! }))
    .sort(
      (a, b) =>
        a.text.localeCompare(b.text, 'ko', { sensitivity: 'base' }) ||
        a.actor.actorUserId - b.actor.actorUserId,
    );
  const unnamed = actors
    .filter((actor) => actorLabel(actor) === null)
    .map((actor) => ({ actor, text: words.unknown }));
  const all = [...named, ...unnamed];
  const seen = new Map<string, number>();
  for (const { text } of all) seen.set(text, (seen.get(text) ?? 0) + 1);
  return all.map(({ actor, text }) => {
    const plain =
      seen.get(text)! > 1 ?
        `${text} (${actor.actorUsername ?? actor.actorUserId})`
      : text;
    return {
      value: actor.actorUserId,
      label: actor.actorKind === 'admin' ? plain + words.admin : plain,
    };
  });
}

/** 대상 글 하나(토막을 「 · 」로). */
export const targetText = (target: readonly AuditTargetPart[]) =>
  target.map((part) => part.text).join(' · ');

/** 화면의 시각 글(「2026-10-15 16:02」 — 서버 at 은 +09:00 글자). */
export const formatAuditTime = (at: string) =>
  `${at.slice(0, 10)} ${at.slice(11, 16)}`;
