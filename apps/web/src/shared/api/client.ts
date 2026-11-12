// 층 밖의 어댑터 하나. openapi-fetch 와 openapi-react-query 를 아는 파일은 이것뿐이다.
//
// createApi 는 함수다(모듈 맨 위에서 클라이언트를 만들지 않는다). openapi-fetch 는 만드는 순간의 통신 함수를 붙들기 때문에,
// 모듈을 읽을 때 만들어 버리면 테스트가 나중에 바꿔 끼운 것이 쓰이지 않는다. 테스트는 인자로 준다.
//
// ★ 2xx 가 아닌 답은 여기서 반드시 실패로 바꿔 던진다(guarded). 라이브러리에 맡기면 새는 구멍이 둘 있다:
//     502 + Content-Length: 0          → openapi-fetch 가 {error: undefined} 를 낸다 → 조회는 null 로 「성공」, 변경도 「성공」
//     502 + 빈 본문, 길이 없이 chunked → {error: ""} → 변경은 `if (error) throw` 를 지나쳐 「성공」(빈 글자는 거짓이다)
//   둘째가 Vite 의 프록시가 서버에 닿지 못했을 때의 답이다. 그래서 가르는 기준은 error 의 참·거짓이 아니라 response.ok 다.
//   막는 자리를 통신 함수의 감싸개로 고른 까닭: 조회·변경·client.GET 을 직접 부르는 길이 전부 이 한 자리를 지나고,
//   미들웨어의 순서나 openapi-fetch 가 본문을 읽는 법에 기대지 않는다.
import createFetchClient from 'openapi-fetch';
import createQueryHooks from 'openapi-react-query';

import { failureOf } from './model/index.ts';
import type { ApiFailure, paths } from './model/index.ts';

type Fetch = (input: Request) => Promise<Response>;

/** 답을 받지 못하면 network, 2xx 가 아니면 본문을 읽어 갈래로 바꿔 던진다. 2xx 는 그대로 넘긴다. */
function guarded(inner: Fetch): Fetch {
  return async (request) => {
    let response: Response;
    try {
      response = await inner(request);
    } catch {
      throw { kind: 'network' } satisfies ApiFailure;
    }
    if (response.ok) return response;
    const text = await response.text().catch(() => '');
    let body: unknown = text === '' ? undefined : text;
    try {
      if (text !== '') body = JSON.parse(text);
    } catch {
      // JSON 이 아니면 글자 그대로 둔다.
    }
    throw failureOf(response.status, body);
  };
}

export interface CreateApiOptions {
  /** 서버의 바탕 주소. 화면이 정해서 넘긴다(빌드가 상대 주소라 여기에 박아 둘 수 없다). */
  baseUrl: string;
  /** 통신 함수. 안 주면 지금의 전역 것을 쓴다. 테스트가 가짜를 준다. */
  fetch?: (input: Request) => Promise<Response>;
}

/** 계약 타입이 입혀진 클라이언트(client)와 TanStack Query 용 도우미($api)를 만든다. 패칭 기본값은 품지 않는다. */
export function createApi({ baseUrl, fetch: given }: CreateApiOptions) {
  const inner: Fetch = given ?? ((request) => globalThis.fetch(request));
  // 프록시 덕에 같은 출처다. 쿠키는 같은 출처에만 싣는다.
  const client = createFetchClient<paths>({
    baseUrl,
    credentials: 'same-origin',
    fetch: guarded(inner),
  });
  return { client, $api: createQueryHooks(client) };
}

export type Api = ReturnType<typeof createApi>;
