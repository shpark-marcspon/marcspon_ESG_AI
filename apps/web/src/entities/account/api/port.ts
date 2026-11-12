// 계정 관리의 어댑터(밴드 AD1 ②, 실서버 마저 UA1W ①). 실서버 넷 — 목록(GET /users)·만들기(POST /users)·비밀번호 초기화(POST /users/{id}/password-reset)·
//   계정 수정(PATCH /users/{id} — 이름·사용 여부).
// 통신은 넣어 준 Api(세션의 session.api — Bearer·444 refresh 가 이미 실림)만 쓴다. 전역 통신·난수·창은 모른다(app/ 이 넣는다).
//
// 임시 비밀번호(남의 계정 열쇠):
//   - 여기서 makeTemporaryPassword 로 만들어 요청 본문에만 싣고, 성공한 결과(outcome)로 한 번 돌려준다. 저장·기록하지 않는다.
//     결과를 받은 화면이 React 상태 하나에만 둔다(TanStack Query 를 쓰지 않는다 — 쿼리·뮤테이션 캐시에 남지 않게).
//   - 400 PASSWORD_REJECTED(서버 검사기는 8자 미만만 거절한다 — UA1. 12자는 늘 지나지만 서버에 갈래가 남아 방어로 둔다. 행은 생기지 않았다)면
//     새로 만들어 한 번만 다시 보낸다. 또 거절이면 failed.
//   - 실패 결과에는 비밀번호를 싣지 않는다. 서버 message 는 화면에 보이지 않는다(code 로만 가른다).
// companyId 는 보내지 않는다(MARC-ENT-251 — 회사가 하나면 생략). GET 쿼리에도 PATCH 본문에도.
// 목록: limit=100 으로 isNext 가 거짓일 때까지 이어 받는다(상한 10쪽 = 1,000건, 넘으면 failed — 1차는 회사 하나라 넘지 않는다).
//   거르기(q·status — accountQuery 가 만든 것)를 쪽마다 싣는다. count 는 거른 뒤의 수다.
//   꼴 틀림·404 COMPANY_NOT_FOUND·400 COMPANY_AMBIGUOUS·403·5xx·연결 끊김은 모두 failed 하나(MARC-ENT-260 3 「둘로만」).
// 전체 수(total): GET /users?limit=1&offset=0 의 count(거르지 않은 수 — 설명 줄의 개수. 감독 판단 Q2).
// 계정 수정(PATCH /users/{id}): 본문은 정확히 한 칸 — 이름이면 {name}, 사용 여부면 {isActive}(null 칸·다른 칸 0).
//   rename: 200 → renamed · 404 USER_NOT_FOUND → missing · 422 → invalid · 그 밖(꼴 틀림 포함) → failed.
//   setActive: 여럿은 id 마다 차례로(병렬 아님 — 감독 판단 Q3) 보내고 {done, failed} 를 돌려준다(던지지 않는다). 404 도 failed 에 센다.
import { asFailure } from '../../../shared/api/index.ts';
import type { Api, ApiFailure } from '../../../shared/api/index.ts';
import { makeTemporaryPassword } from '../model/index.ts';
import type { Account, AccountQuery, RandomFill } from '../model/index.ts';

/** 한 쪽의 크기(서버 상한). */
export const LIST_PAGE_SIZE = 100;
/** 이어 받는 쪽의 상한. */
export const LIST_PAGE_LIMIT = 10;

export type ListOutcome =
  { kind: 'ok'; count: number; accounts: Account[] } | { kind: 'failed' };

export type TotalOutcome = { kind: 'ok'; total: number } | { kind: 'failed' };

export type RenameOutcome =
  | { kind: 'renamed'; account: Account }
  /** 404 USER_NOT_FOUND(없는 id·남의 회사). */
  | { kind: 'missing' }
  /** 422(이름 꼴). */
  | { kind: 'invalid' }
  | { kind: 'failed' };

/** 여럿 사용 여부 바꿈의 결과(id 차례 그대로). */
export interface SetActiveOutcome {
  done: number[];
  failed: number[];
}

/** 422 VALIDATION_ERROR 가 가리킨 칸. */
export type AccountField = 'username' | 'name';

export type CreateOutcome =
  | { kind: 'created'; account: Account; password: string }
  /** 409 USERNAME_TAKEN. */
  | { kind: 'taken' }
  /** 422 VALIDATION_ERROR — 칸 오류. */
  | { kind: 'invalid'; fields: AccountField[] }
  | { kind: 'failed' };

export type ResetOutcome =
  | { kind: 'reset'; account: Account; password: string }
  /** 404 USER_NOT_FOUND(남의 회사·없는 id). */
  | { kind: 'missing' }
  | { kind: 'failed' };

export interface CreateAccountInput {
  username: string;
  /** 다듬은 이름(nameToSend). */
  name: string;
}

export interface AccountsPort {
  /** 거른 목록(쿼리가 없으면 전부). */
  list(query?: AccountQuery): Promise<ListOutcome>;
  /** 거르지 않은 전체 수. */
  total(): Promise<TotalOutcome>;
  rename(account: Pick<Account, 'id'>, name: string): Promise<RenameOutcome>;
  setActive(
    accounts: readonly Pick<Account, 'id'>[],
    isActive: boolean,
  ): Promise<SetActiveOutcome>;
  create(input: CreateAccountInput): Promise<CreateOutcome>;
  resetPassword(account: Pick<Account, 'id'>): Promise<ResetOutcome>;
}

export interface CreateAccountsPortOptions {
  /** 세션의 Api(Bearer·444 refresh). */
  api: Api;
  /** 난수 함수(crypto.getRandomValues 의 꼴 — app/ 이 넣는다, 시험은 고정 난수). */
  random: RandomFill;
}

const codeOf = (failure: ApiFailure) =>
  failure.kind === 'api' ? failure.code : null;

const FIELDS: readonly AccountField[] = ['username', 'name'];
/** 422 의 칸 경로(`username`·`body.username` 꼴)에서 아는 칸만. */
function fieldsOf(failure: ApiFailure): AccountField[] {
  if (failure.kind !== 'api') return [];
  const paths = Object.keys(failure.fields);
  return FIELDS.filter((field) =>
    paths.some((path) => path === field || path.endsWith(`.${field}`)),
  );
}

/** 줄 하나가 계약 꼴인가(꼴 틀림은 실패로 — 틀린 정보를 그리지 않는다). */
function isAccount(value: unknown): value is Account {
  if (typeof value !== 'object' || value === null) return false;
  const row = value as Record<string, unknown>;
  return (
    typeof row.id === 'number' &&
    typeof row.username === 'string' &&
    typeof row.name === 'string' &&
    typeof row.isActive === 'boolean' &&
    typeof row.isInitial === 'boolean' &&
    typeof row.isLocked === 'boolean' &&
    (row.lastLoginAt === null || typeof row.lastLoginAt === 'string') &&
    typeof row.createdAt === 'string' &&
    typeof row.companyName === 'string' &&
    typeof row.companyId === 'number' &&
    (row.branchId === null || typeof row.branchId === 'number')
  );
}

export function createAccountsPort({
  api,
  random,
}: CreateAccountsPortOptions): AccountsPort {
  const { client } = api;

  /** 한 번 보낸다. 실패는 갈래로(던지지 않는다). */
  async function attempt<T>(
    send: () => Promise<{ data?: T }>,
  ): Promise<{ data: T } | { failure: ApiFailure }> {
    try {
      const { data } = await send();
      if (data === undefined) return { failure: { kind: 'network' } };
      return { data };
    } catch (error) {
      return { failure: asFailure(error) };
    }
  }

  /** 임시 비밀번호를 만들어 보내고, 서버 검사기가 거절하면 새로 만들어 한 번만 다시. */
  async function withTemporaryPassword<T>(
    send: (password: string) => Promise<{ data?: T }>,
  ): Promise<
    { data: T; password: string } | { failure: ApiFailure; password: null }
  > {
    for (let round = 0; round < 2; round++) {
      const password = makeTemporaryPassword(random);
      const result = await attempt(() => send(password));
      if ('data' in result) return { data: result.data, password };
      if (codeOf(result.failure) !== 'PASSWORD_REJECTED' || round === 1)
        return { failure: result.failure, password: null };
    }
    throw new Error('닿지 않는다');
  }

  /** PATCH /users/{id} 한 번. 본문은 넣은 한 칸 그대로. */
  const patch = (id: number, body: { name: string } | { isActive: boolean }) =>
    attempt(() =>
      client.PATCH('/users/{user_id}', {
        params: { path: { user_id: id } },
        body,
      }),
    );

  return {
    async list(query = {}) {
      const accounts: Account[] = [];
      let count = 0;
      for (let page = 0; page < LIST_PAGE_LIMIT; page++) {
        const result = await attempt(() =>
          client.GET('/users', {
            params: {
              query: {
                limit: LIST_PAGE_SIZE,
                offset: accounts.length,
                ...query,
              },
            },
          }),
        );
        if ('failure' in result) return { kind: 'failed' };
        const body: unknown = result.data;
        if (typeof body !== 'object' || body === null)
          return { kind: 'failed' };
        const {
          count: total,
          isNext,
          results,
        } = body as Record<string, unknown>;
        if (
          typeof total !== 'number' ||
          typeof isNext !== 'boolean' ||
          !Array.isArray(results) ||
          !results.every(isAccount)
        )
          return { kind: 'failed' };
        count = total;
        accounts.push(...results);
        // 다음 쪽이 있다는데 이 쪽이 비었으면 끝없이 돈다 — 꼴 틀림으로 본다.
        if (!isNext) return { kind: 'ok', count, accounts };
        if (results.length === 0) return { kind: 'failed' };
      }
      return { kind: 'failed' };
    },

    async total() {
      const result = await attempt(() =>
        client.GET('/users', { params: { query: { limit: 1, offset: 0 } } }),
      );
      if ('failure' in result) return { kind: 'failed' };
      const body: unknown = result.data;
      if (typeof body !== 'object' || body === null) return { kind: 'failed' };
      const { count } = body as Record<string, unknown>;
      return typeof count === 'number' ?
          { kind: 'ok', total: count }
        : { kind: 'failed' };
    },

    async rename({ id }, name) {
      const result = await patch(id, { name });
      if ('data' in result)
        return isAccount(result.data) ?
            { kind: 'renamed', account: result.data }
          : { kind: 'failed' };
      const code = codeOf(result.failure);
      if (code === 'USER_NOT_FOUND') return { kind: 'missing' };
      if (code === 'VALIDATION_ERROR') return { kind: 'invalid' };
      return { kind: 'failed' };
    },

    async setActive(targets, isActive) {
      const outcome: SetActiveOutcome = { done: [], failed: [] };
      for (const { id } of targets) {
        const result = await patch(id, { isActive });
        if ('data' in result && isAccount(result.data)) outcome.done.push(id);
        else outcome.failed.push(id);
      }
      return outcome;
    },

    async create({ username, name }) {
      const result = await withTemporaryPassword((password) =>
        client.POST('/users', { body: { username, name, password } }),
      );
      if (result.password !== null) {
        if (!isAccount(result.data)) return { kind: 'failed' };
        return {
          kind: 'created',
          account: result.data,
          password: result.password,
        };
      }
      const code = codeOf(result.failure);
      if (code === 'USERNAME_TAKEN') return { kind: 'taken' };
      if (code === 'VALIDATION_ERROR') {
        const fields = fieldsOf(result.failure);
        if (fields.length > 0) return { kind: 'invalid', fields };
      }
      return { kind: 'failed' };
    },

    async resetPassword({ id }) {
      const result = await withTemporaryPassword((password) =>
        client.POST('/users/{user_id}/password-reset', {
          params: { path: { user_id: id } },
          body: { password },
        }),
      );
      if (result.password !== null) {
        if (!isAccount(result.data)) return { kind: 'failed' };
        return {
          kind: 'reset',
          account: result.data,
          password: result.password,
        };
      }
      if (codeOf(result.failure) === 'USER_NOT_FOUND')
        return { kind: 'missing' };
      return { kind: 'failed' };
    },
  };
}
