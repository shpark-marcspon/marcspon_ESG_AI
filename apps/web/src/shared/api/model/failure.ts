// 서버 호출이 실패했을 때의 갈래. React, DOM, 통신을 모른다: 받는 것은 상태 코드와 이미 파싱된 본문뿐이다.
//
// 왜 따로 가르는가. 이 라이브러리 조합(openapi-fetch + openapi-react-query)은 실패를 「파싱된 본문 그대로」 던진다.
// 상태 코드가 같이 오지 않고, 본문이 빈 실패는 실패로 잡히지도 않는다(client.ts 의 머리말). 그래서 2xx 가 아닌 답은
// 전부 여기의 합 하나로 바꿔서 던진다.
import type { components } from '../../../../../api-py/generated/api.d.ts';

/**
 * 서버가 정한 오류 본문 `{error:{code,message,fields,legacyCode}}`. 계약에서 온 타입이다.
 * code 는 대문자 세부 이름이다(NO_SESSION, REVIEW_LOCKED, VALIDATION_ERROR …. 세부 이름이 없으면 BAD_REQUEST·UNAUTHORIZED 같은 일반 이름).
 * legacyCode(옛 소문자)는 한 판만 오고 C1 에서 걷힌다. 여기서는 읽지 않는다.
 */
export type ErrorBody = components['schemas']['ErrorBody'];

/** 422 VALIDATION_ERROR 의 칸 오류. `{칸 경로: 문장[]}`(예 `rows.0.factorYear`). 그 밖의 실패에서는 빈 객체다. */
export type FailureFields = NonNullable<
  components['schemas']['ErrorDetail']['fields']
>;

/**
 * 실패의 갈래 셋.
 *   api         서버가 정한 꼴로 거절했다(401 NO_SESSION, 403 FORBIDDEN, 409 REVIEW_LOCKED, 444 TOKEN_NOT_VALID, 400 COMPANY_AMBIGUOUS …). code 로 가른다.
 *               fields 는 422 의 칸 오류이고, 서버가 null 을 주거나 칸이 없으면 빈 객체다
 *   unexpected  2xx 가 아닌데 그 꼴이 아니다: 글자 본문, 빈 본문(앞의 프록시가 서버에 닿지 못했을 때의 502 가 여기다)
 *   network     답을 받지 못했다(연결이 끊겼다, 주소가 틀렸다)
 */
export type ApiFailure =
  | {
      kind: 'api';
      status: number;
      code: string;
      message: string;
      fields: FailureFields;
    }
  | { kind: 'unexpected'; status: number; body?: unknown }
  | { kind: 'network' };

const KINDS: readonly string[] = ['api', 'unexpected', 'network'];

function isErrorBody(body: unknown): body is ErrorBody {
  if (typeof body !== 'object' || body === null) return false;
  const detail = (body as { error?: unknown }).error;
  if (typeof detail !== 'object' || detail === null) return false;
  const { code, message } = detail as { code?: unknown; message?: unknown };
  return typeof code === 'string' && typeof message === 'string';
}

/** 칸 오류만 옮긴다: 글자 목록인 칸만 싣고, null·없음·다른 꼴은 빈 객체로. */
function fieldsOf(raw: unknown): FailureFields {
  const fields: FailureFields = {};
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw))
    return fields;
  for (const [path, messages] of Object.entries(raw))
    if (
      Array.isArray(messages) &&
      messages.every((message) => typeof message === 'string')
    )
      fields[path] = [...(messages as string[])];
  return fields;
}

/** 2xx 가 아닌 답 하나를 갈래로. body 는 파싱된 것(객체, 글자, 비었으면 undefined). */
export function failureOf(status: number, body: unknown): ApiFailure {
  if (isErrorBody(body))
    return {
      kind: 'api',
      status,
      code: body.error.code,
      message: body.error.message,
      fields: fieldsOf(body.error.fields),
    };
  if (body === undefined || body === '') return { kind: 'unexpected', status };
  return { kind: 'unexpected', status, body };
}

/**
 * 세션을 다시 받아야 하는 실패인가: 444 TOKEN_NOT_VALID(토큰이 맞지 않음)와 401 NO_SESSION(세션 없음).
 * 화면 동작은 아직 이것으로 가르지 않는다(로그인 화면이 없다). 가름의 자리를 하나로 두려고 먼저 둔다.
 */
export function needsReauth(failure: ApiFailure): boolean {
  return (
    failure.kind === 'api' &&
    (failure.status === 444 ||
      failure.code === 'TOKEN_NOT_VALID' ||
      failure.code === 'NO_SESSION')
  );
}

/** 운영 관리자 회사 업무의 작업 회사를 정하지 못한 거절(sid:MARC-ENT-374 — 서버 user/service/apis/users.py operator_work_company). */
export type CompanyRefusal = 'ambiguous' | 'inactive' | 'not_found';

/**
 * 회사 거절의 갈래. code 로만 가른다: COMPANY_NOT_FOUND 는 업무 경로에서 400, 사용자 관리 경로에서 404 로 온다.
 * 그 밖의 실패는 null. 화면 글은 쓰는 모듈이 정한다(1차 웹에서는 시드 전·회사 둘·사용 중지 같은 설정 잘못에서만 난다).
 * needsReauth 처럼 가름의 자리를 하나로 두려고 먼저 둔다.
 */
export function companyRefusalOf(failure: ApiFailure): CompanyRefusal | null {
  if (failure.kind !== 'api') return null;
  switch (failure.code) {
    case 'COMPANY_AMBIGUOUS':
      return 'ambiguous';
    case 'COMPANY_INACTIVE':
      return 'inactive';
    case 'COMPANY_NOT_FOUND':
      return 'not_found';
    default:
      return null;
  }
}

export function isApiFailure(value: unknown): value is ApiFailure {
  return (
    typeof value === 'object' &&
    value !== null &&
    KINDS.includes((value as { kind?: unknown }).kind as string)
  );
}

/**
 * 조회·변경의 error 를 갈래로 읽는다. 라이브러리의 타입은 error 를 계약의 오류 본문이라고 말하지만, 실제로 던져지는 것은
 * client.ts 가 바꿔 던진 ApiFailure 다. 그 밖의 것(이 층을 거치지 않은 예외)은 「답을 받지 못했다」로 본다.
 */
export function asFailure(error: unknown): ApiFailure {
  return isApiFailure(error) ? error : { kind: 'network' };
}
