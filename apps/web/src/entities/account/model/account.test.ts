// 계정 model: 상태 접기(앞섬 차례), 서버 쿼리(검색 글·상태 — UA1W ①), 만든 날 꼴, 임시 비밀번호 생성(고정 난수), 아이디 검사, 이름 셈(코드 포인트), 마지막 로그인 꼴.
// 시험 이름·단언 글에 생성된 비밀번호 값을 싣지 않는다(꼴로만 본다).
import { describe, expect, expectTypeOf, it } from 'vitest';

import type { paths } from '../../../shared/api/index.ts';
import {
  ACCOUNT_QUERY_MAX,
  ACCOUNT_STATUSES,
  NAME_MAX,
  NO_FILTER,
  PASSWORD_GROUPS,
  STATUS_FILTERS,
  TEMPORARY_PASSWORD_LENGTH,
  accountQuery,
  formatCreatedDate,
  formatLastLogin,
  isFiltered,
  makeTemporaryPassword,
  nameLength,
  nameToSend,
  searchText,
  statusOf,
  uniformIndex,
  usernameProblem,
} from './index.ts';
import type { AccountQuery, AccountStatus, RandomFill } from './index.ts';

const base = { isActive: true, isLocked: false, isInitial: false };

describe('statusOf — 사용 중지 > 잠김 > 초기화 대기 > 사용 중', () => {
  it('사용 중지 + 초기화 대기 → 사용 중지', () => {
    expect(statusOf({ ...base, isActive: false, isInitial: true })).toBe(
      'inactive',
    );
  });
  it('사용 중지 + 잠김 → 사용 중지, 잠김 + 초기화 대기 → 잠김', () => {
    expect(statusOf({ ...base, isActive: false, isLocked: true })).toBe(
      'inactive',
    );
    expect(statusOf({ ...base, isLocked: true, isInitial: true })).toBe(
      'locked',
    );
  });
  it('초기화 대기(새로 만든 계정도) → 초기화 대기, 그 밖 → 사용 중', () => {
    expect(statusOf({ ...base, isInitial: true })).toBe('initial');
    expect(statusOf(base)).toBe('active');
  });
  it('서버 값 하나만 받는다(덧칠 인자 없음 — UA1W)', () => {
    expectTypeOf(statusOf).parameters.toEqualTypeOf<
      [{ isActive: boolean; isLocked: boolean; isInitial: boolean }]
    >();
  });
});

type ServerStatus = NonNullable<
  NonNullable<paths['/users']['get']['parameters']['query']>['status']
>;

describe('accountQuery — 거르기 → GET /users 쿼리(값 있는 칸만)', () => {
  it('배지 넷과 계약 status enum 이 같은 집합, 상태 고르기는 전체 + 넷', () => {
    expectTypeOf<AccountStatus>().toEqualTypeOf<ServerStatus>();
    expect([...ACCOUNT_STATUSES].sort()).toEqual(
      ['active', 'inactive', 'initial', 'locked'].sort(),
    );
    expect(STATUS_FILTERS).toEqual([
      'all',
      'active',
      'initial',
      'locked',
      'inactive',
    ]);
  });

  it('쿼리 타입에 limit·offset·companyId 칸이 없다', () => {
    expectTypeOf<keyof AccountQuery>().toEqualTypeOf<'q' | 'status'>();
  });

  it('기본값이면 {}(키 없음), isFiltered 거짓', () => {
    expect(accountQuery(NO_FILTER)).toEqual({});
    expect(isFiltered(NO_FILTER)).toBe(false);
  });

  it.each([
    ['   ', '공백만'],
    ['\u0000', 'NUL 하나'],
    [' \u0000 ', '공백·NUL'],
  ])('%j(%s) → q 키 없음', (query) => {
    const sent = accountQuery({ query, status: 'all' });
    expect(sent).toEqual({});
    expect('q' in sent).toBe(false);
    expect(isFiltered({ query, status: 'all' })).toBe(false);
  });

  it('앞뒤 빈칸을 걷는다', () => {
    expect(accountQuery({ query: ' 담당 ', status: 'all' })).toEqual({
      q: '담당',
    });
  });

  it('NUL 을 지운다', () => {
    expect(accountQuery({ query: 'a\u0000b', status: 'all' })).toEqual({
      q: 'ab',
    });
  });

  it(`코드 포인트 ${ACCOUNT_QUERY_MAX}자에서 자른다(이모지 섞어 151 → 150)`, () => {
    const long = '😀가'.repeat(75) + 'x'; // 151 코드 포인트
    expect([...long].length).toBe(151);
    const q = searchText(long)!;
    expect([...q].length).toBe(ACCOUNT_QUERY_MAX);
    expect(q).toBe('😀가'.repeat(75));
    expect(accountQuery({ query: long, status: 'all' }).q).toBe(q);
    expect(searchText('😀'.repeat(150))).toBe('😀'.repeat(150));
  });

  it("status 'all' → 키 없음, 'locked' → status: 'locked'(넷 다 그대로)", () => {
    expect('status' in accountQuery({ query: '', status: 'all' })).toBe(false);
    for (const status of ACCOUNT_STATUSES)
      expect(accountQuery({ query: '', status })).toEqual({ status });
    expect(accountQuery({ query: ' kim ', status: 'locked' })).toEqual({
      q: 'kim',
      status: 'locked',
    });
  });

  it('companyId 는 어떤 거르기에도 없다', () => {
    for (const status of STATUS_FILTERS)
      expect(
        Object.keys(accountQuery({ query: 'a', status })).every((key) =>
          ['q', 'status'].includes(key),
        ),
      ).toBe(true);
  });
});

describe('만든 날 — KST YYYY-MM-DD', () => {
  it('+09:00 이면 그날, UTC 로 와도 KST 날짜, 꼴이 아니면 null', () => {
    expect(formatCreatedDate('2026-10-01T09:00:00+09:00')).toBe('2026-10-01');
    expect(formatCreatedDate('2026-10-01T00:30:00+09:00')).toBe('2026-10-01');
    expect(formatCreatedDate('2026-09-30T15:30:00Z')).toBe('2026-10-01');
    expect(formatCreatedDate('어제')).toBeNull();
    expect(formatCreatedDate('')).toBeNull();
  });
});

/** 고정 난수: 주어진 값을 차례로(다 쓰면 처음부터). */
const fixed = (...values: number[]): RandomFill => {
  let at = 0;
  return (array) => {
    for (let i = 0; i < array.length; i++)
      array[i] = values[at++ % values.length]!;
    return array;
  };
};
/** 고정 씨앗의 32비트 선형 합동(시험마다 같은 열). */
const seeded = (seed: number): RandomFill => {
  let state = seed >>> 0;
  return (array) => {
    for (let i = 0; i < array.length; i++) {
      state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
      array[i] = state;
    }
    return array;
  };
};

const CONFUSING = /[0Oo1lI]/;

describe('makeTemporaryPassword — 고정 난수', () => {
  it('12자, 네 갈래(대문자·소문자·숫자·기호)를 하나 이상씩, 헷갈리는 글자 없음, 숫자만 아님 — 씨앗 200개', () => {
    for (let seed = 1; seed <= 200; seed++) {
      const password = makeTemporaryPassword(seeded(seed));
      expect(password).toHaveLength(TEMPORARY_PASSWORD_LENGTH);
      for (const group of PASSWORD_GROUPS)
        expect([...password].some((char) => group.includes(char))).toBe(true);
      expect(CONFUSING.test(password)).toBe(false);
      expect(/^\d+$/.test(password)).toBe(false);
      expect(
        [...password].every((char) => PASSWORD_GROUPS.join('').includes(char)),
      ).toBe(true);
    }
  });

  it('난수가 늘 0 이어도 네 갈래가 다 든다(갈래 보장)', () => {
    const password = makeTemporaryPassword(fixed(0));
    for (const group of PASSWORD_GROUPS)
      expect([...password].some((char) => group.includes(char))).toBe(true);
  });

  it('같은 난수 열이면 같은 값, 다른 씨앗이면 다른 값', () => {
    expect(makeTemporaryPassword(seeded(7))).toBe(
      makeTemporaryPassword(seeded(7)),
    );
    expect(makeTemporaryPassword(seeded(7))).not.toBe(
      makeTemporaryPassword(seeded(8)),
    );
  });
});

describe('uniformIndex — 거절 표본', () => {
  it('끝자리 값(2^32 - 2^32 % n 이상)은 버리고 다시 뽑는다', () => {
    const n = 61;
    const limit = 2 ** 32 - (2 ** 32 % n);
    expect(uniformIndex(fixed(limit, limit + 1, 5), n)).toBe(5);
    expect(uniformIndex(fixed(limit - 1), n)).toBe((limit - 1) % n);
  });
});

describe('아이디 검사(시안 도움 글 — 영문·숫자와 . @ + - _, 서버 패턴과 같다)', () => {
  it.each(['user07', 'a.b@c+d-e_f', 'A9', 'x'.repeat(150)])(
    '%s 는 된다',
    (username) => expect(usernameProblem(username)).toBeNull(),
  );
  it.each(['담당자', 'user 07', ' user07', 'user07 ', 'a/b', 'x'.repeat(151)])(
    '%s 는 쓸 수 없는 글자(한글·공백 포함)',
    (username) => expect(usernameProblem(username)).toBe('format'),
  );
  it('빈 칸은 empty', () => expect(usernameProblem('')).toBe('empty'));
});

describe('이름 — 코드 포인트로 센다, 다듬어 보낸다', () => {
  it('이모지·한글 한 글자가 하나', () => {
    expect(nameLength('담당자 G')).toBe(5);
    expect(nameLength('😀😀')).toBe(2);
    expect('😀😀'.length).toBe(4);
  });
  it('앞뒤 공백을 다듬고, 다듬어 비면·20자를 넘으면 보내지 않는다', () => {
    expect(nameToSend('  담당자 A  ')).toBe('담당자 A');
    expect(nameToSend('   ')).toBeNull();
    expect(nameToSend('가'.repeat(NAME_MAX))).toBe('가'.repeat(NAME_MAX));
    expect(nameToSend('😀'.repeat(NAME_MAX))).toBe('😀'.repeat(NAME_MAX));
    expect(nameToSend('가'.repeat(NAME_MAX + 1))).toBeNull();
  });
});

describe('마지막 로그인', () => {
  it('+09:00 그대로 YYYY-MM-DD HH:mm, 없으면 null', () => {
    expect(formatLastLogin('2026-10-15T14:20:31+09:00')).toBe(
      '2026-10-15 14:20',
    );
    expect(formatLastLogin(null)).toBeNull();
    expect(formatLastLogin('어제')).toBeNull();
  });
});
