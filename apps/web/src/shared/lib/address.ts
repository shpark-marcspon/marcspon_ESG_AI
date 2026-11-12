// 주소 도우미. 띄워 보는 화면들(pages/demo-*)이 같이 쓴다.
//   - withParams: 주소의 인자(?이름=값&…)를 고친다. 규칙은 하나다: 바꾸려는 인자만 바꾸고 나머지는 그대로 둔다(이 앱이 모르는 인자도 지우지 않는다).
//     전에는 화면마다 주소를 「아는 인자 몇 개」로 새로 만들어서, 그때 적지 않은 인자(예: screen=compact)가 빠졌다.

/**
 * 지금의 인자에서 patch 에 적힌 것만 바꾼 주소("?…")를 돌려준다. 값이 null 이면 그 인자를 뺀다.
 * 남는 인자의 순서는 그대로고, 새 인자는 뒤에 붙는다.
 */
export function withParams(
  search: string,
  patch: Record<string, string | null>,
): string {
  const params = new URLSearchParams(search);
  for (const [name, value] of Object.entries(patch)) {
    if (value === null) params.delete(name);
    else params.set(name, value);
  }
  return `?${params.toString()}`;
}

// 앱 뿌리 주소(밴드 CW1 ②, sid:MARC-ISSUE-119 1). 앱이 하위 경로(vite base, 예 /sub/)에 놓여도 맞게 import.meta.env.BASE_URL 을 붙인다.
// 쪽 주소(/dev/viewer 등) 기준으로 풀면 /dev/… 아래를 가리켜 SPA fallback 의 HTML 을 받는다(밴드 RT1). BASE_URL 은 부를 때마다 읽는다.

/** 앱 뿌리 기준 경로 글자. appPath('dev/table') → '/dev/table'(base /sub/ 면 '/sub/dev/table'). 앞의 '/' 는 떼고 붙인다. */
export function appPath(path: string): string {
  return `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`;
}

/**
 * 앱 뿌리 기준 절대 URL. 상대 경로는 앱 뿌리에 붙이고, 이미 절대 URL(http:…)이면 그대로 둔다.
 * appHref('api-py') → 'http://host/api-py'(base /sub/ 면 'http://host/sub/api-py').
 * 앞 / 가 붙은 경로는 앱 뿌리가 아니라 origin 기준이다(appPath 와 다름): base /sub/ 에서 appHref('/api-py') → 'http://host/api-py'.
 */
export function appHref(path: string): string {
  return new URL(path, new URL(import.meta.env.BASE_URL, document.baseURI))
    .href;
}
