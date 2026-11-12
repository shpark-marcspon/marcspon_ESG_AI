// 감사 기록 model(밴드 AD5R ①): KST 「오늘」·기간 → 날짜 범위(조임)·거르기 → 서버 쿼리(값 있는 칸만, 빈 q 뺌)·서버 줄 → 화면 줄·행위자 선택지.
import { describe, expect, expectTypeOf, it } from 'vitest';

import { AUDIT_TEXT } from '../config/text.ts';
import {
  AUDIT_ACTIONS,
  AUDIT_NO_FILTER,
  actorOptions,
  auditQuery,
  formatAuditTime,
  kstToday,
  periodRange,
  targetText,
  toEntry,
} from './index.ts';
import type {
  AuditAction,
  AuditActorRow,
  AuditEventRow,
  AuditFilter,
} from './index.ts';

const words = AUDIT_TEXT.entry;
const at = (iso: string) => new Date(iso);
const query = (filter: Partial<AuditFilter>, now = '2026-10-15T03:00:00Z') =>
  auditQuery({ ...AUDIT_NO_FILTER, ...filter }, at(now));

/** 지어낸 서버 줄(시험만). */
const row = (overrides: Partial<AuditEventRow> = {}): AuditEventRow => ({
  id: 1,
  at: '2026-10-15T16:02:00+09:00',
  companyId: 1,
  actorKind: 'service',
  actorUserId: 11,
  actorName: '담당자 가',
  actorUsername: 'user11',
  action: 'login',
  event: 'login_succeeded',
  result: 'success',
  reason: null,
  targetKind: null,
  targetId: null,
  targetLabel: null,
  changedFields: null,
  module: null,
  requestId: null,
  ...overrides,
});
const actor = (
  actorUserId: number,
  actorName: string | null,
  overrides: Partial<AuditActorRow> = {},
): AuditActorRow => ({
  actorKind: 'service',
  actorUserId,
  actorName,
  actorUsername: actorName === null ? null : `id${actorUserId}`,
  ...overrides,
});

describe('행동 아홉', () => {
  it('계약 enum 과 집합이 같다(타입)·표시 차례', () => {
    expectTypeOf<(typeof AUDIT_ACTIONS)[number]>().toEqualTypeOf<AuditAction>();
    expect(AUDIT_ACTIONS).toEqual([
      'login',
      'logout',
      'upload',
      'run',
      'download',
      'setting_change',
      'adopt',
      'exclude',
      'confirm',
    ]);
    expect(Object.keys(AUDIT_TEXT.actions)).toEqual([...AUDIT_ACTIONS]);
  });
});

describe('KST 오늘', () => {
  it.each([
    ['2026-10-18T14:59:59Z', '2026-10-18'],
    ['2026-10-18T15:00:00Z', '2026-10-19'],
    ['2026-10-19T00:00:00+09:00', '2026-10-19'],
  ])('%s → %s', (now, today) => {
    expect(kstToday(at(now))).toBe(today);
  });
});

describe('기간 → 날짜 범위(둘 다 포함)', () => {
  it.each([
    ['week', '2026-10-14', '2026-10-12', '2026-10-14'], // 수요일
    ['week', '2026-10-12', '2026-10-12', '2026-10-12'], // 월요일 → 그날 하루
    ['week', '2026-10-18', '2026-10-12', '2026-10-18'], // 일요일
    ['week', '2026-11-01', '2026-10-26', '2026-11-01'], // 달을 넘는 주
    ['month', '2026-10-14', '2026-10-01', '2026-10-14'],
    ['month', '2026-10-01', '2026-10-01', '2026-10-01'],
  ] as const)('%s · 오늘 %s → %s ~ %s', (period, today, from, to) => {
    expect(periodRange(period, today)).toEqual({ dateFrom: from, dateTo: to });
  });

  it('전체 → null', () => {
    expect(periodRange('all', '2026-10-14')).toBeNull();
  });

  it('조임: 시계가 범위 밖이어도 두 값이 [2000-01-01, 2999-12-31] 안', () => {
    for (const period of ['week', 'month'] as const) {
      const early = query({ period }, '1999-12-31T03:00:00Z');
      expect(early.dateFrom! >= '2000-01-01', period).toBe(true);
      expect(early.dateTo! >= '2000-01-01', period).toBe(true);
      const late = query({ period }, '3000-01-02T03:00:00Z');
      expect(late.dateFrom! <= '2999-12-31', period).toBe(true);
      expect(late.dateTo! <= '2999-12-31', period).toBe(true);
    }
    expect(query({}, '1999-12-31T03:00:00Z')).toEqual({
      dateFrom: '2000-01-01',
      dateTo: '2000-01-01',
    });
    // 「오늘」이 먼저 2999-12-31 로 조여져 그달 1일부터.
    expect(query({ period: 'month' }, '3000-01-02T03:00:00Z')).toEqual({
      dateFrom: '2999-12-01',
      dateTo: '2999-12-31',
    });
  });
});

describe('거르기 → 서버 쿼리', () => {
  it('처음 거르기(이번 주) → 키가 정확히 dateFrom·dateTo, dateTo 는 오늘(다음 날 아님)', () => {
    expect(query({})).toEqual({ dateFrom: '2026-10-12', dateTo: '2026-10-15' });
  });

  it('KST 로 센다: UTC 로는 아직 14일이어도 KST 15일이면 dateTo 는 15일', () => {
    expect(query({}, '2026-10-14T15:00:00Z').dateTo).toBe('2026-10-15');
    expect(query({}, '2026-10-14T14:59:59Z').dateTo).toBe('2026-10-14');
  });

  it('빈·공백 q 는 키째 빼고, 앞뒤 빈칸은 걷는다', () => {
    expect('q' in query({ query: '' })).toBe(false);
    expect('q' in query({ query: '   ' })).toBe(false);
    expect('q' in query({ query: '\t\n ' })).toBe(false);
    expect(query({ query: ' kim ' }).q).toBe('kim');
  });

  it('q 는 코드 포인트 150자에서 자른다(서로게이트 쌍을 가르지 않는다)', () => {
    expect([...query({ query: '가'.repeat(151) }).q!]).toHaveLength(150);
    const emoji = '😀'.repeat(151);
    const sent = query({ query: emoji }).q!;
    expect([...sent]).toHaveLength(150);
    expect(sent).toBe('😀'.repeat(150));
  });

  it("사람·행동 'all' → 키 없음, 고르면 그 값. 전체 기간 → 날짜 키 없음. companyId 는 늘 없음", () => {
    expect(query({ actorUserId: 'all', action: 'all', period: 'all' })).toEqual(
      {},
    );
    expect(
      query({ actorUserId: 7, action: 'setting_change', period: 'all' }),
    ).toEqual({ actorUserId: 7, action: 'setting_change' });
    for (const filter of [{}, { actorUserId: 3 }, { period: 'all' as const }])
      expect('companyId' in query(filter)).toBe(false);
  });
});

describe('서버 줄 → 화면 줄', () => {
  it('시각·이름(이름 → 아이디)·성공', () => {
    const entry = toEntry(row(), words);
    expect(entry).toEqual({
      id: '1',
      at: '2026-10-15T16:02:00+09:00',
      actor: '담당자 가',
      actorMissing: false,
      action: 'login',
      target: [],
      failure: null,
    });
    expect(formatAuditTime(entry.at)).toBe('2026-10-15 16:02');
    expect(toEntry(row({ actorName: null }), words).actor).toBe('user11');
  });

  it.each([
    ['command', '관리 명령'],
    ['anonymous', '없는 아이디'],
    ['service', '알 수 없는 사람'],
    ['admin', '알 수 없는 사람'],
  ] as const)('이름이 없는 %s 줄 → 「%s」(회색 표시)', (actorKind, text) => {
    const entry = toEntry(
      row({ actorKind, actorName: null, actorUsername: null }),
      words,
    );
    expect(entry.actor).toBe(text);
    expect(entry.actorMissing).toBe(true);
  });

  it.each([
    ['user_created', 'kim', '계정 · kim 만듦'],
    ['password_reset', 'kim', '계정 · kim 비밀번호 초기화'],
    ['user_updated', 'kim', '계정 · kim 고침'],
    ['password_changed', 'kim', '계정 · 비밀번호 바꿈'],
    ['user_created', null, '계정 · 만듦'],
  ] as const)(
    '계정 사건 %s(label %s) → 「%s」, 「계정」만 링크',
    (event, label, text) => {
      const entry = toEntry(
        row({
          action: 'setting_change',
          event,
          targetKind: 'user',
          targetId: 3,
          targetLabel: label,
        }),
        words,
      );
      expect(targetText(entry.target)).toBe(text);
      expect(entry.target[0]).toEqual({
        text: '계정',
        link: { kind: 'accounts' },
      });
      expect(entry.target.slice(1).every((part) => !part.link)).toBe(true);
    },
  );

  it('대상이 사용자가 아니면 「계정」 토막에 링크가 없다', () => {
    const entry = toEntry(
      row({ event: 'user_updated', targetKind: null, targetLabel: 'kim' }),
      words,
    );
    expect(entry.target.some((part) => part.link)).toBe(false);
  });

  it.each([
    ['document_uploaded', 'upload', '보고서_예시.pdf'],
    ['run_created', 'run', '보고서_예시.pdf'],
    ['run_file_downloaded', 'download', 'EDK_정량데이터_예시.xlsx'],
    ['some_future_event', 'confirm', '지어낸 대상'],
  ] as const)(
    '파일·모르는 사건 %s → 대상 글자 그대로(링크 없음)',
    (event, action, label) => {
      const entry = toEntry(
        row({ event, action, targetKind: 'run', targetLabel: label }),
        words,
      );
      expect(entry.target).toEqual([{ text: label }]);
    },
  );

  it('로그인 셋·로그아웃·대상 글자 없는 모르는 사건 → 빈 대상(「—」)', () => {
    for (const event of [
      'login_succeeded',
      'login_failed',
      'login_locked',
      'logout',
    ])
      expect(
        toEntry(row({ event, targetKind: 'user', targetLabel: 'kim' }), words)
          .target,
        event,
      ).toEqual([]);
    expect(
      toEntry(row({ event: 'x', targetLabel: null }), words).target,
    ).toEqual([]);
  });

  it.each([
    ['wrong_password', '비밀번호 틀림'],
    ['unknown_user', '없는 아이디'],
    ['inactive_user', '사용 중지된 계정'],
    ['account_locked', '잠긴 계정'],
    ['toString', ''],
    ['some_new_reason', ''],
    [null, ''],
  ] as const)('실패 까닭 %s → 「%s」', (reason, text) => {
    const entry = toEntry(row({ result: 'failure', reason }), words);
    expect(entry.failure).toBe(text);
    expect(AUDIT_TEXT.failure(entry.failure!)).toBe(
      text === '' ? '실패' : `실패 · ${text}`,
    );
  });
});

describe('행위자 → 사람 고르기 선택지', () => {
  it('이름 차례(대소문자 무시), 풀리지 않은 사람은 맨 뒤 서버 차례', () => {
    const options = actorOptions(
      [
        actor(1, 'Zed'),
        actor(2, 'alpha'),
        actor(7, null),
        actor(3, 'Bob'),
        actor(4, null),
      ],
      words.actor,
    );
    expect(options).toEqual([
      { value: 2, label: 'alpha' },
      { value: 3, label: 'Bob' },
      { value: 1, label: 'Zed' },
      { value: 7, label: '알 수 없는 사람 (7)' },
      { value: 4, label: '알 수 없는 사람 (4)' },
    ]);
  });

  it('이름 → 아이디로 라벨, 같은 라벨 둘은 「라벨 (아이디)」, 같으면 id 차례', () => {
    const options = actorOptions(
      [
        actor(9, '담당자', { actorUsername: 'kim2' }),
        actor(5, '담당자', { actorUsername: 'kim' }),
        actor(6, null, { actorUsername: 'onlyid' }),
      ],
      words.actor,
    );
    expect(options).toEqual([
      { value: 5, label: '담당자 (kim)' },
      { value: 9, label: '담당자 (kim2)' },
      { value: 6, label: 'onlyid' },
    ]);
  });

  it('운영 관리자는 꼬리 「 · 운영 관리자」, 하나뿐인 「알 수 없는 사람」은 아이디 없이', () => {
    expect(
      actorOptions(
        [actor(1, '관리자 가', { actorKind: 'admin' }), actor(2, null)],
        words.actor,
      ),
    ).toEqual([
      { value: 1, label: '관리자 가 · 운영 관리자' },
      { value: 2, label: '알 수 없는 사람' },
    ]);
  });
});

describe('AI 설정 줄(밴드 AD4X ③) → 「AI 설정(링크) · 모듈 · 판 만듦/적용」', () => {
  const setting = (overrides: Partial<AuditEventRow>) =>
    row({
      action: 'setting_change',
      event: 'ai_setting_created',
      targetKind: 'ai_setting',
      targetId: 3,
      targetLabel: 'v3',
      module: 'greenwash',
      ...overrides,
    });
  const target = (overrides: Partial<AuditEventRow>) =>
    toEntry(setting(overrides), words).target;

  it('만듦: 「AI 설정」 링크(version v3) · 「그린워싱」 · 「v3 만듦」', () => {
    expect(target({})).toEqual([
      {
        text: 'AI 설정',
        link: { kind: 'ai-settings', module: 'greenwash', version: 'v3' },
      },
      { text: '그린워싱' },
      { text: 'v3 만듦' },
    ]);
    expect(targetText(target({}))).toBe('AI 설정 · 그린워싱 · v3 만듦');
  });

  it('적용: 판 있음 「v2 적용」(version v2) · 기본 판(targetId null) 「기본 설정 적용」(version 없음)', () => {
    expect(
      target({ event: 'ai_setting_applied', targetId: 2, targetLabel: 'v2' }),
    ).toEqual([
      {
        text: 'AI 설정',
        link: { kind: 'ai-settings', module: 'greenwash', version: 'v2' },
      },
      { text: '그린워싱' },
      { text: 'v2 적용' },
    ]);
    expect(
      target({
        event: 'ai_setting_applied',
        targetId: null,
        targetLabel: 'colab-2026-01-15-v1',
      }),
    ).toEqual([
      {
        text: 'AI 설정',
        link: { kind: 'ai-settings', module: 'greenwash', version: null },
      },
      { text: '그린워싱' },
      { text: '기본 설정 적용' },
    ]);
  });

  it('적용인데 targetId null 이면 이름이 v<n> 꼴이어도 판 없이(기본 판 적용 — 링크는 판을 고르지 않는다)', () => {
    expect(
      target({
        event: 'ai_setting_applied',
        targetId: null,
        targetLabel: 'v2',
      }),
    ).toEqual([
      {
        text: 'AI 설정',
        link: { kind: 'ai-settings', module: 'greenwash', version: null },
      },
      { text: '그린워싱' },
      { text: '기본 설정 적용' },
    ]);
  });

  it('링크의 module 은 감사 줄의 module 그대로(밴드 AM1 — AD-02 모듈 주소, sid:MARC-ISSUE-291). 옛 줄은 null', () => {
    expect(target({ module: 'translation' })[0]!.link).toEqual({
      kind: 'ai-settings',
      module: 'translation',
      version: 'v3',
    });
    expect(target({ module: null })[0]!.link).toEqual({
      kind: 'ai-settings',
      module: null,
      version: 'v3',
    });
  });

  it('module null(옛 줄)이면 모듈 토막 없음, 표에 없는 id 는 id 그대로', () => {
    expect(targetText(target({ module: null }))).toBe('AI 설정 · v3 만듦');
    expect(targetText(target({ module: 'x.y' }))).toBe(
      'AI 설정 · x.y · v3 만듦',
    );
    expect(targetText(target({ module: 'dataverify' }))).toBe(
      'AI 설정 · 데이터 검증 · v3 만듦',
    );
  });

  it('label null 이면 「만듦」·링크 판 없음, v<n> 꼴이 아닌 이름(id 있어도)은 판 없이', () => {
    expect(target({ targetLabel: null })).toEqual([
      {
        text: 'AI 설정',
        link: { kind: 'ai-settings', module: 'greenwash', version: null },
      },
      { text: '그린워싱' },
      { text: '만듦' },
    ]);
    expect(target({ targetLabel: 'colab-2026-01-15-v1' })[0]).toEqual({
      text: 'AI 설정',
      link: { kind: 'ai-settings', module: 'greenwash', version: null },
    });
    expect(target({ targetLabel: 'v3x' })[0]!.link).toEqual({
      kind: 'ai-settings',
      module: 'greenwash',
      version: null,
    });
  });

  it('다른 사건은 그대로(모듈이 있어도 파일 줄은 대상 글자 그대로, 계정 줄은 「계정」)', () => {
    expect(
      toEntry(
        row({
          event: 'run_created',
          action: 'run',
          targetLabel: '지어낸 문서.pdf',
          module: 'greenwash',
        }),
        words,
      ).target,
    ).toEqual([{ text: '지어낸 문서.pdf' }]);
    expect(
      toEntry(
        row({
          event: 'password_reset',
          action: 'setting_change',
          targetKind: 'user',
          targetId: 12,
          targetLabel: 'user12',
        }),
        words,
      ).target,
    ).toEqual([
      { text: '계정', link: { kind: 'accounts' } },
      { text: 'user12 비밀번호 초기화' },
    ]);
  });
});
