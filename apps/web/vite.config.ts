import { createReadStream, existsSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import type { Plugin } from "vite";

// 실제 자료(변환한 JSON 과 PDF)가 놓이는 폴더. git 밖이거나 .gitignore 된 곳이어야 한다.
// tools/convert.ts 가 여기에 쓰고, 아래 플러그인이 /local/ 주소로 내준다.
const dataDir = resolve(process.env.VIEWER_DATA_DIR ?? ".local-data");

// 다른 프로젝트와 포트가 겹치면 WEB_PORT 로 바꾼다. 겹칠 때 조용히 옆 포트로 가지 않고 멈춘다(strictPort).
const port = Number(process.env.WEB_PORT ?? 15173);

// 브라우저가 api-py 를 부르는 길. 쪽과 같은 출처의 /api/… 를 여기로 넘긴다(api-py 에는 CORS 가 없고, 같은 출처여야 세션 쿠키가 실린다).
// api-py 는 서버 안에서도 /api 아래(/api/me, /api/sites …)에 API 를 둔다(밴드 SW1, MARC-ENT-198). 그래서 접두를 떼지 않고 그대로 넘긴다
// — 운영(같은 서버)과 같은 주소다. 키는 경계가 있는 정규식이라 /apix 나 /api-py 는 타지 않는다(tools/vite-config.test.ts).
// preview 는 server.proxy 를 물려받는다(vite 8 의 preview.proxy 기본값이 server.proxy).
export const API_PROXY_KEY = "^/api(/|$)";
const apiPy = process.env.API_PY_ORIGIN ?? "http://127.0.0.1:18081";

const TYPES: Record<string, string> = { ".json": "application/json", ".pdf": "application/pdf" };

/** /local/<파일> 을 dataDir 에서 읽어 준다. 없으면 404(그러면 화면에는 예시 자료만 보인다). */
function localData(): Plugin {
  function serve(request: IncomingMessage, response: ServerResponse, next: () => void) {
    const path = decodeURIComponent((request.url ?? "").split("?")[0]!);
    if (!path.startsWith("/local/")) return next();
    const file = normalize(join(dataDir, path.slice("/local/".length)));
    const type = TYPES[extname(file)];
    // dataDir 밖을 가리키는 주소(../)와, JSON·PDF 가 아닌 것은 주지 않는다.
    if (!file.startsWith(dataDir + sep) || !type || !existsSync(file) || !statSync(file).isFile()) {
      response.statusCode = 404;
      response.end("not found");
      return;
    }
    response.setHeader("Content-Type", type);
    response.setHeader("Content-Length", statSync(file).size);
    createReadStream(file).pipe(response);
  }
  return {
    name: "local-data",
    configureServer: (server) => void server.middlewares.use(serve),
    configurePreviewServer: (server) => void server.middlewares.use(serve),
  };
}

export default defineConfig({
  plugins: [react(), localData()],
  // 앱은 루트(/)에 서빙된다(밴드 RT1). 깊은 주소(/greenwash/runs/x/review)에서도 자산이 /assets/… 로 풀리게 절대 주소로 빌드한다
  // (상대 "./" 면 /greenwash/runs/x/assets/… 로 풀려 SPA fallback 의 HTML 을 받는다). 하위 경로 서빙이 필요해지면 base 와
  // 라우터의 basepath(src/app/router.tsx)를 같이 바꾼다.
  base: "/",
  server: { port, strictPort: true, proxy: { [API_PROXY_KEY]: { target: apiPy } } },
  preview: { port, strictPort: true },
});
