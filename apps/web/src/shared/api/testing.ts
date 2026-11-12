// 테스트용 가짜 통신 함수. 이 폴더의 테스트만 쓴다(공개 표면이 아니다).
// 답의 값은 전부 지어낸 것이다.

export interface FakeCall {
  method: string;
  url: string;
  path: string;
  credentials: RequestCredentials;
  contentType: string | null;
  body: string;
}

type Answer = Response | (() => Response | Promise<Response>);

export const json = (status: number, body: unknown) => () =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

/**
 * 서버가 정한 꼴의 거절 `{error:{code,message,fields,legacyCode}}`. 실서버처럼 옛 소문자를 legacyCode 에 싣는다(웹은 읽지 않는다).
 * fields 는 422 의 칸 오류이고, 안 주면 null(실서버의 그 밖의 실패와 같다).
 */
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

/** 글자 본문의 500. */
export const textFailure = () =>
  new Response('Internal Server Error', {
    status: 500,
    headers: { 'Content-Type': 'text/plain' },
  });

/** 빈 본문의 502, 첫째 꼴: 길이가 0 이라고 적혀 있다. */
export const emptyWithLength = () =>
  new Response(null, { status: 502, headers: { 'Content-Length': '0' } });

/** 빈 본문의 502, 둘째 꼴: 길이 없이 chunked. Vite 의 프록시가 서버에 닿지 못했을 때의 답이다. */
export const emptyChunked = () =>
  new Response('', {
    status: 502,
    headers: { 'Content-Type': 'text/plain', 'Transfer-Encoding': 'chunked' },
  });

/** 답을 받지 못함. */
export const unreachable = () => {
  throw new TypeError('fetch failed');
};

/** 「메서드 경로」 → 답. 경로는 바탕 주소 뒤의 것(쿼리 제외). 부른 것을 calls 에 적는다. */
export function fakeFetch(baseUrl: string, routes: Record<string, Answer>) {
  const calls: FakeCall[] = [];
  const fetch = async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = url.pathname.slice(new URL(baseUrl).pathname.length);
    calls.push({
      method: request.method,
      url: request.url,
      path,
      credentials: request.credentials,
      contentType: request.headers.get('Content-Type'),
      body: await request.clone().text(),
    });
    const answer = routes[`${request.method} ${path}`];
    if (!answer) throw new Error(`가짜에 없는 경로: ${request.method} ${path}`);
    return typeof answer === 'function' ? answer() : answer.clone();
  };
  const count = (key: string) =>
    calls.filter((call) => `${call.method} ${call.path}` === key).length;
  return { fetch, calls, count, routes };
}
