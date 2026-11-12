// 구조 규칙 시험 하나(밴드 FS1 ①②③). apps/web/src 의 층·슬라이스·칸 규칙을 이 파일 하나가 지킨다.
// 옛 layers 시험 다섯(components·api·doc-viewer·review-table·greenwash)을 합쳤다. 그린워싱은 ② 에서 화면 하나 = 폴더 하나로 갈랐다:
//   entities/greenwash(화면 둘 이상이 쓰는 것) · pages/greenwash-*(화면 하나만 쓰는 것) · app/greenwash(그린워싱 틀과 경로 컴포넌트, 경로 표 시험).
// 경로 표는 app/router.tsx 하나다(밴드 RT1, TanStack Router). @tanstack/react-router 는 src/main.tsx 와 src/app/** 만 가져온다(4. 라우터 규칙):
//   화면(pages)은 라우터를 모르고 콜백 props 를 받는다 — 경로 컴포넌트(app/greenwash)가 navigate 로 잇는다.
// 경로는 POSIX('/' 로 가른다) 전제다 [L2]: macOS·Linux 에서 돈다. Windows 에서 돌리게 되면 path.sep 으로 바꾼다.
//
// 표 셋:
//   1. 층 순서      app(main.tsx 포함) > pages > widgets > entities > shared. 위층만 아래층을 가져온다. 같은 층의 다른 슬라이스는 가져오지 않는다
//                   (shared 안은 3 의 칸 규칙이 정한다). pages 는 app 만 가져온다. 예외는 LAYER_EXCEPTIONS·PAGE_ENTRY_EXCEPTIONS 의 줄뿐이다.
//                   상대 import 는 파일 이름과 확장자(.ts/.tsx/.css)를 적는다(폴더째 가져오기는 빨강 [M1]). src 는 src 밖을 가져오지 않는다
//                   (계약 타입 api-py/generated/api.d.ts 만 된다 [M2]).
//   2. 슬라이스 경계  슬라이스 밖(src·tools·e2e)에서는 공개 표면으로만 들어온다(DOORS). node 에서 도는 tools/ 는 화면 없는 표면(model/index.ts)만.
//   3. 칸 규칙      슬라이스 안 칸의 방향은 model ← api ← hooks ← ui 하나다(config 는 ui 만 가져온다. 맨 위 파일은 저마다 ROOT 줄).
//                   칸의 뜻: model = 순수 함수와 타입, api = 서버 꼴 검사·저장소·목, hooks = 훅과 모양 없는 컴포넌트(RowFrame·RowStack·PageCanvas 등) [L5],
//                   ui = 모양, config = 문구 표.
//                   칸마다 쓸 수 있는 패키지와 파일, model(·hooks·api) 의 DOM 낱말, model·hooks(·api) 의 모양(색 값·박은 className·모양 도구,
//                   hooks 는 style 의 모양 키도), model·hooks·api 의 CSS import.
//                   슬라이스마다 다른 것은 SLICES 의 그 줄에 둔다(doc-viewer 의 pdfjs-dist, review-table 의 TanStack 과 모양 키 filter 빼기,
//                   shared/api 의 계약 타입·패칭 기본값 등).
// 주석 지우개·LOOK_VALUE·FIXED_CLASS·LOOK_TOOL·DOM 낱말은 한 벌이다(옛 넷의 합집합).
//
// 파일을 글자로 읽어 import 문을 찾는다(빌드 도구에 기대지 않는다). import 는 원문과 주석 지운 글 둘 다에서 찾는다(옛 넷 중 둘은 원문,
// 둘은 주석 지운 글에서 찾았다. 합집합이라 어느 쪽이 잡던 것도 잃지 않는다. 대신 주석 속의 import 꼴 글자도 import 로 센다).
// 잡는 것과 못 잡는 것:
//   잡는다     허용 밖 패키지·파일의 import(from·import()·require), 거꾸로 가는 층, 공개 표면을 건너뛴 import, model 의 DOM 전역 낱말,
//              model·hooks 의 색 값 글자(#abc, rgb(, hsl(, oklch(, color-mix( …, 캔버스의 fillStyle·strokeStyle), 글자를 박은 className="…",
//              class-variance-authority·@marcspon/ui import, hooks 의 style 모양 키(color, background…, border…, font…, opacity …. 따옴표로 감싼 키도)
//   못 잡는다  문자열을 조립한 import, 변수나 다른 파일에서 건너온 클래스 이름·style 값, 조립한 키, 이름 붙은 색("red"),
//              목록에 없는 키(cursor, padding …)·전역(matchMedia, requestAnimationFrame …), <style> 태그에 글자로 쓴 CSS,
//              쓰는 쪽이 준 className·style 을 흘려보내는 것(일부러 연 길이다)
//   거꾸로, 잘못이 아닌데 걸리는 것: 낱말 목록과 같은 이름(model 의 변수 self·location·Response, hooks 의 타입 필드 color: Tone — string·number 타입만 봐준다,
//              삼항의 글자 "fill"). 걸리면 이름을 바꾼다.
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const SELF = fileURLToPath(import.meta.url);
const here = dirname(SELF);
const src = resolve(here, '../..');
const webRoot = resolve(src, '..');
const CONTRACT = resolve(webRoot, '../api-py/generated/api.d.ts');
/** 고정물 글자로 import 꼴을 품은 구조 시험(이 파일). 진짜 import 로 읽지 않는다. */
const FIXTURE_CARRIERS = [SELF];

function filesUnder(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    if (
      entry.name === 'node_modules' ||
      entry.name === 'dist' ||
      entry.name.startsWith('.')
    )
      return [];
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return filesUnder(path);
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

/** src·tools·e2e 의 .ts/.tsx 전부(고정물을 품은 구조 시험은 뺀다). */
const allFiles = () =>
  ['src', 'tools', 'e2e']
    .flatMap((dir) => filesUnder(join(webRoot, dir)))
    .filter((file) => !FIXTURE_CARRIERS.includes(file));

/**
 * 주석만 지운다. 따옴표 셋(' " `)의 문자열은 건너뛰고 그대로 둔다: 문자열 속의 '//'·'/*' 를 주석의 시작으로 읽어
 * 그 뒤의 코드를 삼키지 않게(예: "http://x" 뒤 같은 줄의 import, '/*' 뒤 여러 줄). 지운 주석 자리에는 줄바꿈만 남긴다.
 * 못 하는 것: 정규식 리터럴(/\/\// 같은 것)은 문자열로 보지 않는다. 틀 문자열 안 ${…} 속의 따옴표도 따로 세지 않는다.
 */
export function withoutComments(source: string): string {
  let out = '';
  let i = 0;
  while (i < source.length) {
    const char = source[i]!;
    const next = source[i + 1];
    if (char === '"' || char === "'" || char === '`') {
      let j = i + 1;
      while (j < source.length && source[j] !== char) {
        if (source[j] === '\\') j++;
        else if (char !== '`' && source[j] === '\n') break; // 닫히지 않은 줄 문자열은 줄 끝에서 끝낸다
        j++;
      }
      out += source.slice(i, j + 1);
      i = j + 1;
    } else if (char === '/' && next === '/') {
      while (i < source.length && source[i] !== '\n') i++;
    } else if (char === '/' && next === '*') {
      const end = source.indexOf('*/', i + 2);
      const stop = end === -1 ? source.length : end + 2;
      out += source.slice(i, stop).replace(/[^\n]/g, '');
      i = stop;
    } else {
      out += char;
      i++;
    }
  }
  return out;
}

interface Import {
  target: string;
  /** `import type … from` / `export type … from` 인가. 지워지는 import 다. */
  typeOnly: boolean;
  /** `import("x")`·`require("x")` 인가(진입 청크 규칙이 게으른 import 를 가른다). */
  dynamic?: true;
}

const STATEMENT =
  /\b(?:import|export)\s+(type\s+)?[^;"'`]*?\bfrom\s*["'`]([^"'`]+)["'`]/g;
const BARE_OR_DYNAMIC =
  /(?:\bimport\s*\(?\s*|\brequire\s*\(\s*)["'`]([^"'`]+)["'`]/g;
const ANY_FROM = /\bfrom\s*["'`]([^"'`]+)["'`]/g;

/** 파일이 가져오는 것들: `from "x"`, `import "x"`, `import("x")`, `require("x")`. 원문과 주석 지운 글의 합집합. */
export function importsOf(source: string): Import[] {
  const found = new Map<string, Import>();
  const add = (target: string, typeOnly: boolean, dynamic = false) =>
    found.set(
      `${typeOnly}\0${dynamic}\0${target}`,
      dynamic ? { target, typeOnly, dynamic } : { target, typeOnly },
    );
  for (const text of [source, withoutComments(source)]) {
    const statements = new Set<string>();
    for (const match of text.matchAll(STATEMENT)) {
      add(match[2]!, Boolean(match[1]));
      statements.add(match[2]!);
    }
    for (const match of text.matchAll(BARE_OR_DYNAMIC))
      add(match[1]!, false, match[0].includes('('));
    for (const match of text.matchAll(ANY_FROM))
      if (!statements.has(match[1]!)) add(match[1]!, false);
  }
  return [...found.values()];
}

const relativeImports = (file: string, source: string) =>
  importsOf(source)
    .filter(({ target }) => target.startsWith('.'))
    .map((imp) => ({ ...imp, path: resolve(dirname(file), imp.target) }));

const isTestFile = (file: string) => /\.test\.tsx?$/.test(file);
const isHelperFile = (file: string) => /(^|\/)testing\.tsx?$/.test(file);
const CSS = /\.css(\?.*)?$/;

/** 테스트 파일만 쓸 수 있는 바깥 것(슬라이스마다 더할 수 있다). */
const TEST_PACKAGES = [
  'vitest',
  '@testing-library/react',
  'node:fs',
  'node:path',
  'node:url',
];
/** model 이 쓰면 안 되는 전역 낱말(옛 넷의 합집합: api 의 sessionStorage·Request·Response·Headers, doc-viewer 의 getComputedStyle·self·location). */
const DOM_WORD =
  /\b(document|window|navigator|HTML\w*Element|localStorage|sessionStorage|globalThis|fetch|Request|Response|Headers|self|location|getComputedStyle)\b/;
/** 모양의 값. model·hooks 에 있으면 안 되는 글자들. */
const LOOK_VALUE =
  /#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?|oklch|oklab|lab|lch|color-mix)\(|\b(fillStyle|strokeStyle)\s*=/;
/** 글자를 박은 클래스 이름. 쓰는 쪽이 준 것을 흘려보내는 className={className} 은 걸리지 않는다. */
const FIXED_CLASS = /\bclassName\s*=\s*["'`]|\bclassName\s*=\s*\{\s*["'`]/;
/** 모양 도구. 패키지 규칙과 따로 한 번 더 본다(규칙을 넓혀도 이 둘은 model·hooks 에 들지 않게). */
const LOOK_TOOL =
  /["'`](class-variance-authority|@marcspon\/ui(\/[^"'`]*)?)["'`]/;
/** hooks 의 style 에 있으면 안 되는 모양 키. */
const LOOK_KEYS = [
  'color',
  'background\\w*',
  'border\\w*',
  'outline\\w*',
  'boxShadow',
  'textShadow',
  'font\\w*',
  'opacity',
  'textDecoration\\w*',
  'fill',
  'stroke',
  'filter',
  'mixBlendMode',
  'accentColor',
  'caretColor',
  'WebkitTextFillColor',
  'letterSpacing',
  'textTransform',
];
const lookKey = (except: readonly string[]) =>
  new RegExp(
    `\\b(${LOOK_KEYS.filter((key) => !except.includes(key)).join('|')})["'\`]?\\s*:(?!\\s*(string|number)\\b)`,
  );
/** 그린워싱 hooks·api 의 DOM 규칙(옛 greenwash headless, 밴드 FW2 ⓪ [B2]): 전역 접근만 잡는다. 칸 이름 `document:`·`history:`·지역 값의 `.document`·메서드 `history(`·경로 글자 `/history` 는 된다(밴드 W12-1a — a8 허락). */
const HOOKS_DOM =
  /\b(window|navigator|localStorage|sessionStorage|location|fetch|globalThis|HTMLElement)\b|(?<![.\w])document\s*\.|(?<![.\w])history\s*(\?\.|\.|\[)/;
/** 목 저장소의 DOM 규칙(옛 greenwash mock, 밴드 FW1b): DOM·location·history 를 모른다(search 는 app/greenwash/GreenwashRoutes.tsx 의 틀이 읽어 넘긴다). */
const MOCK_DOM =
  /\b(document|window|navigator|location|history|HTMLElement|localStorage|globalThis|fetch)\b/;
/**
 * 세션 api 의 DOM 규칙(밴드 LG1, N8): 전역 보관소·창·주소·전역 통신 호출을 모른다(통신 함수와 보관소는 app/ 이 넣는다).
 * 칸 이름 `fetch:`(createApi 의 인자)는 된다 — 전역 fetch 를 부르는 `fetch(` 만 잡는다. Request·Response·Headers 는 된다(감싼 통신 함수가 만든다).
 */
const SESSION_API_DOM =
  /\b(window|document|navigator|localStorage|sessionStorage|location|history|globalThis|HTMLElement)\b|(?<![.\w])fetch\s*\(/;
/**
 * 계정 model·api 의 DOM 규칙(밴드 AD1): 세션 api 의 규칙 + 전역 난수(crypto)·로그(console). 임시 비밀번호를 기록·보관하는 길을 막는다.
 * 난수 함수와 Api 는 app/ 이 넣는다. Request·Response 는 된다(가짜 서버가 만든다 — testing.ts 는 시험으로 본다).
 */
const ACCOUNT_DOM =
  /\b(window|document|navigator|localStorage|sessionStorage|location|history|globalThis|HTMLElement|crypto|console)\b|(?<![.\w])fetch\s*\(/;
/** 어드민 화면 폴더의 낱말 규칙(밴드 AD1): 제품 파일 어디에도 보관소·로그가 없다(임시 비밀번호는 React 상태에만 — 발주서 §2-1). */
const ADMIN_PAGE_WORDS = /\b(localStorage|sessionStorage|indexedDB|console)\b/;
/** 공개 표면이 zod 스키마 값(이름이 …Schema)을 내보내는가(옛 greenwash, 밴드 FW2 ⑤ M3). 거울은 parse* 와 타입만. */
const SCHEMA_EXPORT = /\bexport\s*\{[^}]*\b\w+Schema\b[^}]*\}/;
/** 통째 다시 내보내기(`export *`)는 스키마 값을 이름 없이 내보낼 수 있어 막는다(밴드 FW2 ⑤ N1). */
const STAR_EXPORT = /\bexport\s*\*/;
/** 공개 표면이 PARTS_TEXT(shared/ui/text.ts)를 다시 내보내는가(그 문으로 [B3] 을 돌아가지 못하게). 주석은 지우고 본다. */
export function reexportsPartsText(source: string): boolean {
  return /\bexport\b[^;]*\bPARTS_TEXT\b/.test(withoutComments(source));
}
/** 패칭 기본값의 글자. shared/api 는 품지 않는다(쓰는 화면이 정한다). 주석도 본다. */
const FETCHING_DEFAULT = /new QueryClient|\bretry\b|\bstaleTime\b|\bgcTime\b/;

// ───────────────────────── 1. 층 순서 ─────────────────────────

/** 아래 → 위. */
const LAYERS = ['shared', 'entities', 'widgets', 'pages', 'app'] as const;
type Layer = (typeof LAYERS)[number];
interface Place {
  layer: Layer;
  /** src 기준 폴더: 'app', 'shared/ui', 'widgets/doc-viewer' … */
  slice: string;
}

/** src 안 파일의 층과 슬라이스. src 밖이면 null, 정해진 자리(main.tsx, app/, <층>/<슬라이스>/…) 밖이면 'stray'. */
export function placeOf(file: string): Place | 'stray' | null {
  const rel = relative(src, file);
  if (rel.startsWith('..')) return null;
  if (rel === 'main.tsx') return { layer: 'app', slice: 'app' };
  const [layer, name, ...rest] = rel.split('/');
  if (!(LAYERS as readonly string[]).includes(layer!) || !name) return 'stray';
  if (layer === 'app') return { layer, slice: 'app' };
  if (rest.length === 0) return 'stray';
  return { layer: layer as Layer, slice: `${layer}/${name}` };
}
const rank = (layer: Layer) => LAYERS.indexOf(layer);

/**
 * 층 순서의 예외(src 기준 경로). 쓰이지 않게 된 줄은 빨강이다(낡은 예외를 남기지 않게).
 * ① 의 임시 두 줄(그린워싱 → widgets/doc-viewer)은 ② 에서 없앴다: 진입은 app/greenwash 로, 문서 뷰어는 쓰는 화면(pages)이 직접 가져온다.
 */
const LAYER_EXCEPTIONS: { from: string; to: string; why: string }[] = [];
/** src 밖에서 pages 로 들어올 수 있는 줄(webRoot 기준 경로). */
const PAGE_ENTRY_EXCEPTIONS: { from: string; to: string; why: string }[] = [
  {
    from: 'e2e/review-table.spec.ts',
    to: 'src/pages/demo-table/fakeRows.ts',
    why: '검토 표 e2e 가 데모의 가짜 행을 만들어 견준다',
  },
];

/** 한 파일의 층 순서 위반. */
export function layerViolations(file: string, source: string): string[] {
  const from = placeOf(file);
  if (from === 'stray')
    return [
      `${relative(src, file)} 는 정해진 자리(main.tsx, app/, <층>/<슬라이스>/) 밖에 있다`,
    ];
  const problems: string[] = [];
  const who = relative(webRoot, file);
  for (const { target, path } of relativeImports(file, source)) {
    // [M1] 폴더째 가져오기(`../../widgets/review-table`)와 확장자 없는 경로는 빨강: 공개 표면 검사를 비켜 가지 못하게.
    //   .json 은 ?raw 로만 된다(확장자가 적혀 있어 M1 의 뜻은 그대로. 쓰임: 그린워싱 목의 실호출 fixture, 밴드 FX1). 그 뒤 M2·칸 규칙은 그대로 탄다.
    if (!/\.(ts|tsx|css)(\?.*)?$|\.json\?raw$/.test(target)) {
      problems.push(
        `${who} 가 ${target} 를 확장자 없이 가져온다(파일 이름과 .ts/.tsx/.css 를 적는다)`,
      );
      continue;
    }
    const to = placeOf(path);
    // [M2] src 안의 파일이 src 밖(tools/·e2e/ 등)을 가져오면 빨강. 계약 타입(api-py/generated/api.d.ts)만 된다(칸 규칙이 자리를 본다).
    if (to === null && from !== null && path !== CONTRACT) {
      problems.push(
        `${who} 가 ${relative(webRoot, path)} 를 가져온다(src 는 src 밖을 모른다)`,
      );
      continue;
    }
    if (to === null || to === 'stray') continue; // stray 는 그 파일이 걸린다
    if (from === null) {
      // src 밖(tools·e2e)에서 pages 로: 예외 표의 줄만
      const ok = PAGE_ENTRY_EXCEPTIONS.some(
        (row) =>
          join(webRoot, row.from) === file && join(webRoot, row.to) === path,
      );
      if (to.layer === 'pages' && !ok)
        problems.push(
          `${relative(webRoot, file)} 가 ${relative(webRoot, path)} 를 가져온다(pages 는 app 만 가져온다)`,
        );
      continue;
    }
    if (from.slice === to.slice) continue;
    if (rank(to.layer) < rank(from.layer)) continue;
    if (from.layer === 'shared' && to.layer === 'shared') continue; // shared 안은 칸 규칙이 정한다
    const excepted = LAYER_EXCEPTIONS.some(
      (row) => join(src, row.from) === file && join(src, row.to) === path,
    );
    if (excepted) continue;
    problems.push(
      from.layer === to.layer ?
        `${from.slice} 가 ${relative(src, path)} 를 가져온다(같은 층의 다른 슬라이스)`
      : `${from.slice} 가 ${relative(src, path)} 를 가져온다(${from.layer} 는 ${to.layer} 를 모른다)`,
    );
  }
  return problems;
}

// ───────────────────────── 2. 슬라이스 경계 ─────────────────────────

interface DoorRow {
  /** src 기준 폴더. parts 면 그 아래 폴더 하나하나가 슬라이스(부품)다. */
  dir: string;
  parts?: true;
  /** parts 일 때 슬라이스로 볼 폴더 이름. */
  partFilter?: RegExp;
  /** 가져오는 파일(webRoot 기준)마다 다른 문을 줄 때. null 이면 doors·toolsDoors. */
  doorsFor?: (from: string) => string[] | null;
  /** parts 일 때 슬라이스(폴더 이름)마다 문이 다르면. */
  partDoors?: Record<string, string[]>;
  /** 슬라이스 기준의 공개 표면. */
  doors: string[];
  /** tools/ 가 쓸 수 있는 표면(node 가 읽는 화면 없는 표면). */
  toolsDoors: string[];
  /** 밖에서 실제로 들어오는 import 의 최소 수(빈 검사가 아니게). */
  minEntering: number;
  /** tools/ 에서 실제로 들어오는 import 의 최소 수. */
  minTools: number;
}
/** 로그인 화면 폴더(밴드 LG1 — critic 1 반영 B1 ②). AD1 이 admin-accounts 를 더한다. */
const AUTH_PAGES = /^(login|password-change)$/;
/** 밖에서 entities/session·로그인 화면 폴더로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_SESSION_ENTERING = 15; // 실측 17(② — app/auth 셋, pages/login 셋, e2e 둘)
const MIN_AUTH_PAGE_ENTERING = 2; // 실측 2(app/auth/AuthRoutes.tsx → pages/login·password-change)
/** 계정 슬라이스(밴드 AD1). */
const ACCOUNT = 'entities/account/';
/** entities/account 의 칸 표면(슬라이스 기준). */
const ACCOUNT_SURFACES = ['model/index.ts', 'api/index.ts', 'config/text.ts'];
/** 시험은 가짜 계정 서버(api/testing.ts)도. */
const accountSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'api/testing.ts']
  : [...ACCOUNT_SURFACES];
/** 어드민 화면 폴더(밴드 AD1 — 감독 판단 3). 로그인 줄(AUTH_PAGES)을 넓히지 않고 새 줄. AD2 가 이름만 맞춰 붙는다. 세션 문은 없다. */
const ADMIN_PAGES = /^admin-/;
/** 밖에서 entities/account 로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_ACCOUNT_ENTERING = 8; // 실측 35(UA1W ② — 옛 「실측 9」는 AD1 ② 때 값)
/** 감사 기록 슬라이스(밴드 AD5R — 감독 판단 Q1 (가)): 어드민 목 슬라이스에서 빠져 계정과 같은 꼴의 실서버 줄이 됐다. */
const AUDIT = 'entities/audit-log/';
/** 시험은 가짜 감사 서버(api/testing.ts)도(계정 accountSurfaces 꼴). */
const auditSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'api/testing.ts']
  : [...ACCOUNT_SURFACES];
/** 밖에서 entities/audit-log 로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_AUDIT_ENTERING = 12; // 실측 14(AD5R ①·② 같음 — app/admin, pages/admin-audit, e2e)
/** 실행 기록 슬라이스(밴드 AD4R — 감독 판단 Q1 (가)): 감사 기록 줄을 본떠 어드민 목 슬라이스에서 빠진 실서버 줄. */
const RUN_LOG = 'entities/run-log/';
/** 시험은 가짜 실행 기록 서버(api/testing.ts)도(감사 auditSurfaces 꼴). */
const runLogSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'api/testing.ts']
  : [...ACCOUNT_SURFACES];
/** 밖에서 entities/run-log 로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_RUN_LOG_ENTERING = 12; // 실측 14(AD4R ② — app/admin 셋, pages/admin-runs 열, e2e 하나)
/** 그린워싱 AI 설정 판 슬라이스(밴드 AD2R — 감독 판단 Q1 (다)): 실행 기록 줄을 본뜬 새 실서버 줄. AD2W: 들어오는 것은 app/ 과 e2e 만(화면 껍데기는 모른다). */
const GREENWASH_SETTING = 'entities/greenwash-setting/';
/** 시험은 가짜 그린워싱 AI 설정 서버(api/testing.ts)도(실행 기록 runLogSurfaces 꼴). AS3b ①: ui 칸 표면(대상 단어 슬롯 — 모듈 줄이 가져온다). */
const greenwashSettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'ui/index.ts', 'api/testing.ts']
  : [...ACCOUNT_SURFACES, 'ui/index.ts'];
/** 밖에서 entities/greenwash-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_GREENWASH_SETTING_ENTERING = 4; // 실측 7(AS3b ① — app/admin 셋: 모듈 줄(ui 표면 +1)·그 시험·경로 시험. 옛 「실측 16」은 AD2R ③ 때 값 — 어드민 화면이 빠짐)
/** 영문번역 AI 설정 판 슬라이스(밴드 TRA1 — 그린워싱 AI 설정 판 줄과 같은 꼴). 들어오는 것은 app/ 과 e2e 만(화면 껍데기는 모른다). */
const TRANSLATION_SETTING = 'entities/translation-setting/';
/** 시험은 가짜 영문번역 AI 설정 서버(api/testing.ts)도. ui 칸 표면(흐름 띠 슬롯 — 모듈 줄이 가져온다). */
const translationSettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'ui/index.ts', 'api/testing.ts']
  : [...ACCOUNT_SURFACES, 'ui/index.ts'];
/** 밖에서 entities/translation-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_TRANSLATION_SETTING_ENTERING = 6; // 실측 8(TRA1 — app/admin: 모듈 줄 넷·그 시험 둘·경로 시험 하나, e2e 하나)
/** 데이터 검증 AI 설정 판 슬라이스(밴드 DVA2 — 영문번역 AI 설정 판 줄과 같은 꼴). 들어오는 것은 app/ 과 e2e 만(화면 껍데기는 모른다). */
const DATAVERIFY_SETTING = 'entities/dataverify-setting/';
/** 시험은 가짜 데이터 검증 AI 설정 서버(api/testing.ts)도. ui 칸 표면(흐름 띠 슬롯 — 모듈 줄이 가져온다). */
const dataverifySettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'ui/index.ts', 'api/testing.ts']
  : [...ACCOUNT_SURFACES, 'ui/index.ts'];
/** 밖에서 entities/dataverify-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_DATAVERIFY_SETTING_ENTERING = 7; // 실측 9(DVA2 — app/admin: 모듈 줄 다섯·그 시험 둘·경로 시험 하나, e2e 하나)
/** 중대성평가 IRO AI 설정 판 슬라이스(밴드 IRA2 — 데이터 검증 AI 설정 판 줄과 같은 꼴). 들어오는 것은 app/ 과 e2e 만(화면 껍데기는 모른다). */
const MATERIALITY_SETTING = 'entities/materiality-setting/';
/** 시험은 가짜 중대성평가 IRO AI 설정 서버(api/testing.ts)도. ui 칸 표면(흐름 띠 슬롯 — 모듈 줄이 가져온다). */
const materialitySettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'ui/index.ts', 'api/testing.ts']
  : [...ACCOUNT_SURFACES, 'ui/index.ts'];
/** 밖에서 entities/materiality-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_MATERIALITY_SETTING_ENTERING = 8; // 실측 10(IRA2 — app/admin: 모듈 줄 다섯·그 시험 둘·경로 시험 둘, e2e 하나)
/** 원고작성 AI 설정 판 슬라이스(밴드 RPA3 — 중대성평가 IRO AI 설정 판 줄과 같은 꼴). 들어오는 것은 app/ 과 e2e 만(화면 껍데기는 모른다). entities/drafting(원고작성 화면 칸)과 다른 슬라이스. */
const DRAFTING_SETTING = 'entities/drafting-setting/';
/** 시험은 가짜 원고작성 AI 설정 서버(api/testing.ts)도. ui 칸 표면(흐름 띠 슬롯 — 모듈 줄이 가져온다). */
const draftingSettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'ui/index.ts', 'api/testing.ts']
  : [...ACCOUNT_SURFACES, 'ui/index.ts'];
/** 밖에서 entities/drafting-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_DRAFTING_SETTING_ENTERING = 8; // 실측 10(RPA3 — app/admin: 모듈 줄 다섯·그 시험 둘·경로 시험 둘, e2e 하나)
/**
 * AI 설정 슬라이스(밴드 AD2W — 발주서 §2-1-4): 어드민 목 슬라이스(밴드 AD2)였던 것이 실행 기록 줄을 본뜬 실서버 줄이 됐다.
 * 목 슬라이스 목록·목 문·MOCK_API_DOM 은 이 슬라이스가 마지막이라 함께 걷었다(목 슬라이스 0).
 */
const AI_SETTING = 'entities/ai-setting/';
/** 시험은 가짜 AI 설정 서버(api/testing.ts)도(실행 기록 runLogSurfaces 꼴). */
const aiSettingSurfaces = (from: string) =>
  isTestFile(from) ?
    [...ACCOUNT_SURFACES, 'api/testing.ts']
  : [...ACCOUNT_SURFACES];
/** 밖에서 entities/ai-setting 으로 들어오는 import 의 최소 수(빈 검사가 아니게). */
const MIN_AI_SETTING_ENTERING = 17; // 실측 19(AD2W ① — app/admin 셋, pages/admin-ai-settings 다섯 파일, e2e 하나)
const DOORS: DoorRow[] = [
  {
    dir: 'shared/ui',
    parts: true,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 45, // [L1] 실측 51(FS1 ③)
    minTools: 0,
  },
  {
    dir: 'shared/api',
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 4, // [L1] 실측 4(데모 api 셋, 그린워싱 계약 타입 시험 하나)
    minTools: 0,
  },
  {
    dir: 'widgets/doc-viewer',
    doors: ['index.ts', 'model/index.ts', 'pdfjs.ts'],
    toolsDoors: ['model/index.ts'],
    minEntering: 24, // [L1] 실측 27
    minTools: 8, // [L1] 실측 8
  },
  {
    dir: 'widgets/review-table',
    doors: ['index.ts'],
    toolsDoors: ['model/index.ts'],
    // [S3W2a ① Q3] Scope 3 화면만 화면 없는 표면(배출량 표기 — sid:MARC-ENT-272). 끝 `/` 까지(앞붙음 sid:MARC-ISSUE-483).
    doorsFor: (from) =>
      // [DB1] 대시보드도 같은 표기(a8 허락 11-07)
      (
        from.startsWith('src/pages/ghg-scope3/') ||
        from.startsWith('src/pages/ghg-dashboard/')
      ) ?
        ['index.ts', 'model/index.ts']
      : null,
    minEntering: 16, // [L1] 실측 18
    minTools: 4, // [L1] 실측 4
  },
  {
    // 옛 greenwash 의 「폴더 밖 입구」: 밖은 ui/index.ts(옛 ui/parts/index.ts, demo-parts 가 쓴다)만, e2e 는 config/text.ts 도 [B2].
    // 그린워싱 화면(pages/greenwash-*)과 app/greenwash 는 칸 표면 다섯으로, 목 저장소 표면은 app/greenwash 와 화면의 시험만.
    dir: 'entities/greenwash',
    doors: ['ui/index.ts'],
    toolsDoors: ['ui/index.ts'],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'ui/index.ts',
        'config/text.ts',
      ];
      // [GW1R] 가짜 그린워싱 서버(api/testing.ts)는 시험만: 화면 시험·그린워싱 경로 시험·어드민 경로 시험(함정 ① — 기본 저장소가 실어댑터).
      if (from.startsWith('src/app/greenwash/'))
        return isTestFile(from) ?
            [...surfaces, 'api/mock/index.ts', 'api/testing.ts']
          : [...surfaces, 'api/mock/index.ts'];
      if (/^src\/pages\/greenwash-[a-z]+\//.test(from))
        return isTestFile(from) ?
            [
              ...surfaces,
              'api/mock/index.ts',
              'api/mock/testing.ts',
              'api/testing.ts',
            ]
          : surfaces;
      if (from === 'src/app/admin/router.test.tsx') return ['api/testing.ts'];
      if (from.startsWith('e2e/')) return ['config/text.ts', 'ui/index.ts'];
      return null;
    },
    minEntering: 120, // [L1] 실측 131
    minTools: 0,
  },
  {
    // 영문번역(밴드 TRW0a ② — 그린워싱 줄과 같은 꼴). 영문번역 화면(pages/translation-*)과 app/translation 은 칸 표면 셋으로
    //   (시험은 시험 도우미 model/testing.ts 도), e2e 는 문구 표와 ui 표면. 그 밖은 들어오지 않는다.
    //   doors 는 디스크에 있는 문만 적는다(아래 「폴더는 디스크에 있다」 시험) — ui/ 는 TRW0b 가 만들며 'ui/index.ts' 를 더했다(감독 판단).
    dir: 'entities/translation',
    // [TRW1a ① H3 ⓑ] api·hooks 칸(실어댑터·읽기 훅)의 문 둘을 더했다. 목 저장소는 없다 — 시험은 가짜 서버 api/testing.ts 를 더 쓴다.
    doors: ['ui/index.ts', 'api/index.ts', 'hooks/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'ui/index.ts',
        'config/text.ts',
      ];
      if (
        /^src\/pages\/translation-[a-z-]+\//.test(from) ||
        from.startsWith('src/app/translation/')
      )
        return isTestFile(from) ?
            [...surfaces, 'model/testing.ts', 'api/testing.ts']
          : surfaces;
      if (from.startsWith('e2e/')) return ['config/text.ts', 'ui/index.ts'];
      return null;
    },
    minEntering: 16, // 실측 18(TRW0a ② — pages/translation-new 의 model·ui·시험)
    minTools: 0,
  },
  {
    // 데이터 검증(밴드 DV2a ① H3 ⓐ — 영문번역 줄과 같은 꼴). 데이터 검증 화면(pages/dataverify-*)과 app/dataverify 는 칸 표면으로
    //   (시험은 시험 도우미 model/testing.ts·가짜 서버 api/testing.ts 도), e2e 는 문구 표. 그 밖은 들어오지 않는다.
    //   doors 는 디스크에 있는 문만 적는다 — ui/ 는 두 화면 이상이 쓰는 것이 생길 때 그 밴드가 더한다.
    dir: 'entities/dataverify',
    doors: ['api/index.ts', 'hooks/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'config/text.ts',
      ];
      if (
        /^src\/pages\/dataverify-[a-z-]+\//.test(from) ||
        from.startsWith('src/app/dataverify/')
      )
        return isTestFile(from) ?
            [...surfaces, 'model/testing.ts', 'api/testing.ts']
          : surfaces;
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: 34, // [DV2a ③] 실측 38(pages/dataverify-*·app/dataverify·e2e)
    minTools: 0,
  },
  {
    // 중대성평가(밴드 IRW1 ① H3 ⓐ — 데이터 검증 줄과 같은 꼴). 중대성평가 화면(pages/materiality-*)과 app/materiality 는 칸 표면으로
    //   (시험은 시험 도우미 model/testing.ts·가짜 서버 api/testing.ts 도), e2e 는 문구 표. 그 밖은 들어오지 않는다.
    //   doors 는 디스크에 있는 문만 적는다 — [IRW1 ② H3 ⓚ] ui/ 는 IroFlow(STEP 띠)와 함께 더했다(영문번역 줄 꼴).
    dir: 'entities/materiality',
    doors: ['ui/index.ts', 'api/index.ts', 'hooks/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'ui/index.ts',
        'config/text.ts',
      ];
      if (
        /^src\/pages\/materiality-[a-z-]+\//.test(from) ||
        from.startsWith('src/app/materiality/')
      )
        return isTestFile(from) ?
            [...surfaces, 'model/testing.ts', 'api/testing.ts']
          : surfaces;
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: 34, // [IRW1 ③ H3 ⓙ] 실측 38(pages/materiality-*·app/materiality·e2e — 데이터 검증 줄과 같은 여유)
    minTools: 0,
  },
  {
    // 온실가스(밴드 W12-0a ① H4 — 중대성평가 줄과 같은 꼴). 온실가스 화면(pages/ghg-*)과 app/ghg 는 칸 표면으로
    //   (시험은 가짜 서버 api/testing.ts 도), e2e 는 문구 표. 그 밖은 들어오지 않는다. ui 칸은 없다(화면 부품은 pages 에).
    dir: 'entities/ghg',
    doors: ['api/index.ts', 'hooks/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'config/text.ts',
      ];
      if (
        /^src\/pages\/ghg-[a-z0-9-]+\//.test(from) ||
        from.startsWith('src/app/ghg/')
      )
        return isTestFile(from) ? [...surfaces, 'api/testing.ts'] : surfaces;
      // [W12-0a ③] app/admin(「선택항목」 경로 컴포넌트)은 api 표면, 경로 시험은 가짜 서버도.
      if (from.startsWith('src/app/admin/'))
        return isTestFile(from) ?
            ['api/index.ts', 'api/testing.ts']
          : ['api/index.ts'];
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: 38, // [W12-0a ③ H4] 실측 42(pages/ghg-*·app/ghg·app/admin·e2e — 중대성평가 줄과 같은 여유)
    minTools: 0,
  },
  {
    // [S3W1 ① H2] 온실가스 Scope 3(entities/ghg 줄 꼴): pages/ghg-scope3·Scope3Routes(·그 시험 — 가짜 서버도)만 칸 표면, e2e 는 문구 표.
    dir: 'entities/ghg-scope3',
    doors: ['api/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = ['model/index.ts', 'api/index.ts', 'config/text.ts'];
      if (GHG_S3_FROM.test(from))
        return isTestFile(from) ? [...surfaces, 'api/testing.ts'] : surfaces;
      return from.startsWith('e2e/') ? ['config/text.ts'] : [];
    },
    minEntering: 0, // [S3W1 ①] 실측 0(화면·경로는 ②③ 이 단다)
    minTools: 0,
  },
  {
    // [RPW1 ① A4] 원고작성(온실가스 줄과 같은 꼴). 원고작성 화면(pages/drafting-*)과 app/drafting 은 칸 표면으로
    //   (시험은 가짜 서버 api/testing.ts 도), e2e 는 문구 표. 그 밖은 들어오지 않는다(끝은 [] — sid:MARC-ISSUE-486). ui 칸은 없다.
    dir: 'entities/drafting',
    doors: ['api/index.ts', 'hooks/index.ts'],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'config/text.ts',
      ];
      if (
        /^src\/pages\/drafting-[a-z-]+\//.test(from) ||
        from.startsWith('src/app/drafting/')
      )
        return isTestFile(from) ? [...surfaces, 'api/testing.ts'] : surfaces;
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return [];
    },
    minEntering: 53, // [RPW1 ④ A4] 실측 59(pages/drafting-*·app/drafting — 온실가스 줄과 같은 여유)
    minTools: 0,
  },
  {
    // 로그인 세션(밴드 LG1). 밖은 칸 표면으로만: app/ 과 로그인 화면 폴더(pages/login·password-change)는 칸 표면 다섯
    //   (시험은 가짜 서버 api/testing.ts 도), e2e 는 문구 표와 model(보관소 키 — N10). 그 밖은 들어오지 않는다.
    dir: 'entities/session',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      const surfaces = [
        'model/index.ts',
        'api/index.ts',
        'hooks/index.ts',
        'ui/index.ts',
        'config/text.ts',
      ];
      if (
        from.startsWith('src/app/') ||
        /^src\/pages\/(login|password-change)\//.test(from)
      )
        return isTestFile(from) ? [...surfaces, 'api/testing.ts'] : surfaces;
      if (from.startsWith('e2e/')) return ['config/text.ts', 'model/index.ts'];
      return null;
    },
    minEntering: MIN_SESSION_ENTERING,
    minTools: 0,
  },
  {
    // 계정(밴드 AD1). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 /users 도 — ② 부터), e2e 는 문구 표. 그 밖은 들어오지 않는다.
    dir: 'entities/account',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (
        from.startsWith('src/app/') ||
        /^src\/pages\/admin-[a-z-]+\//.test(from)
      )
        return accountSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_ACCOUNT_ENTERING,
    minTools: 0,
  },
  {
    // 감사 기록(밴드 AD5R — 계정 줄과 같은 꼴). 밖은 칸 표면으로만: app/·어드민 화면은 칸 표면(시험은 가짜 감사 서버도), e2e 는 문구 표.
    dir: 'entities/audit-log',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (
        from.startsWith('src/app/') ||
        /^src\/pages\/admin-[a-z-]+\//.test(from)
      )
        return auditSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_AUDIT_ENTERING,
    minTools: 0,
  },
  {
    // 실행 기록(밴드 AD4R — 감사 기록 줄과 같은 꼴). 밖은 칸 표면으로만: app/·어드민 화면은 칸 표면(시험은 가짜 실행 기록 서버도), e2e 는 문구 표.
    dir: 'entities/run-log',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (
        from.startsWith('src/app/') ||
        /^src\/pages\/admin-[a-z-]+\//.test(from)
      )
        return runLogSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_RUN_LOG_ENTERING,
    minTools: 0,
  },
  {
    // 그린워싱 AI 설정 판(밴드 AD2R — 실행 기록 줄과 같은 꼴). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    // 밴드 AD2W(발주서 §2-1-4 ⓐ): 어드민 화면(pages/admin-*)은 더 들어오지 않는다 — 모듈은 app/admin/ai-setting-modules.ts 가 잇는다.
    dir: 'entities/greenwash-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (from.startsWith('src/app/')) return greenwashSettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_GREENWASH_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // 영문번역 AI 설정 판(밴드 TRA1 — 그린워싱 AI 설정 판 줄과 같은 꼴). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    dir: 'entities/translation-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (from.startsWith('src/app/')) return translationSettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_TRANSLATION_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // 데이터 검증 AI 설정 판(밴드 DVA2 — 영문번역 AI 설정 판 줄과 같은 꼴). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    dir: 'entities/dataverify-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (from.startsWith('src/app/')) return dataverifySettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_DATAVERIFY_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // 중대성평가 IRO AI 설정 판(밴드 IRA2 — 데이터 검증 AI 설정 판 줄과 같은 꼴). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    dir: 'entities/materiality-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (from.startsWith('src/app/')) return materialitySettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_MATERIALITY_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // 원고작성 AI 설정 판(밴드 RPA3 — 중대성평가 IRO AI 설정 판 줄과 같은 꼴). 밖은 칸 표면으로만: app/ 은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    //   그 밖 자리는 문 0(빈 목록 — null 이 아니다, sid:MARC-ISSUE-486).
    dir: 'entities/drafting-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (from.startsWith('src/app/')) return draftingSettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return [];
    },
    minEntering: MIN_DRAFTING_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // AI 설정(밴드 AD2W — 실행 기록 줄과 같은 꼴, 옛 어드민 목 슬라이스 줄을 갈음). 밖은 칸 표면으로만: app/·어드민 화면은 칸 표면(시험은 가짜 서버도), e2e 는 문구 표.
    dir: 'entities/ai-setting',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) => {
      if (
        from.startsWith('src/app/') ||
        /^src\/pages\/admin-[a-z-]+\//.test(from)
      )
        return aiSettingSurfaces(from);
      if (from.startsWith('e2e/')) return ['config/text.ts'];
      return null;
    },
    minEntering: MIN_AI_SETTING_ENTERING,
    minTools: 0,
  },
  {
    // shared/lib 은 칸 없는 파일 모음이라 파일 하나하나가 문이다. 시험 도우미(testing/)는 시험만 쓴다(옛 review-table 의 test-support 규칙을 넓힘).
    // useLoad.ts = 읽기 훅 하나(밴드 CW1 ①). 들어올 수 있는 칸은 3. 칸 규칙의 also 가 정한다(그린워싱 hooks 만).
    // saveBlob.ts·time.ts = 내려받기·한국 시각(밴드 TRW0a ① — 그린워싱·실행 기록에서 올림). 칸 규칙의 also 가 들어올 칸을 정한다.
    dir: 'shared/lib',
    // safeUrl.ts = 안전 링크 판별(밴드 MD1).
    doors: ['address.ts', 'useLoad.ts', 'saveBlob.ts', 'time.ts', 'safeUrl.ts'],
    toolsDoors: [
      'address.ts',
      'useLoad.ts',
      'saveBlob.ts',
      'time.ts',
      'safeUrl.ts',
    ],
    doorsFor: (from) =>
      isTestFile(from) ?
        [
          'address.ts',
          'useLoad.ts',
          'saveBlob.ts',
          'time.ts',
          'safeUrl.ts',
          'testing/layout.ts',
        ]
      : null,
    minEntering: 7, // 실측 24(TRW0a ① — BASE 4e28a54 에서 19, 옛 「실측 7」은 CW1 때 값)
    minTools: 0,
  },
  {
    // 화면 폴더는 index.ts 로만(층 순서상 app 만 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: /^greenwash-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 6, // 실측 6(app/greenwash 의 경로 컴포넌트)
    minTools: 0,
  },
  {
    // 영문번역 화면 폴더(밴드 TRW0a ① — 그린워싱 줄과 같은 꼴). index.ts 로만(app/translation 의 경로 컴포넌트가 가져온다 — 경로는 TRW1).
    dir: 'pages',
    parts: true,
    partFilter: /^translation-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 0, // 실측 0(TRW0a — 경로 컴포넌트는 TRW1 이 단다)
    minTools: 0,
  },
  {
    // 데이터 검증 화면 폴더(밴드 DV2a ② H3 ⓑ — 영문번역 줄과 같은 꼴). index.ts 로만(app/dataverify 의 경로 컴포넌트가 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: /^dataverify-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 4, // 실측 4(DV2a ③ — DataverifyRoutes 가 intro·new·status·result)
    minTools: 0,
  },
  {
    // 중대성평가 화면 폴더(밴드 IRW1 ② H3 ⓑ — 데이터 검증 줄과 같은 꼴). index.ts 로만(app/materiality 의 경로 컴포넌트가 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: /^materiality-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 3, // 실측 3(IRW1 ③ — MaterialityRoutes 가 list·status·result)
    minTools: 0,
  },
  {
    // 온실가스 화면 폴더(밴드 W12-0a ② H4 — 중대성평가 줄과 같은 꼴). index.ts 로만(app/ghg 의 경로 컴포넌트가 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: /^ghg-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 4, // [W12-0b1 ③ H6] 실측 4(GhgRoutes 가 organization·branch, AdminRoutes 가 facility-codes·index-pool)
    minTools: 0,
  },
  {
    // [RPW1 ① A4] 원고작성 화면 폴더(온실가스 줄과 같은 꼴). index.ts 로만(app/drafting 의 경로 컴포넌트가 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: /^drafting-/,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 5, // [RPW6] 실측 5(DraftingRoutes 가 list·intro·new·outline·draft — RPW1 ② A4 의 4 에 intro)
    minTools: 0,
  },
  {
    // 모듈 메뉴 한 자리(밴드 DV2a ② H3 ⓗ — app/shell/moduleMenu.tsx). 들어올 수 있는 쪽은 app/<모듈> 넷(그린워싱·영문번역·데이터 검증·중대성평가)뿐.
    dir: 'app/shell',
    doors: [],
    toolsDoors: [],
    doorsFor: (from) =>
      (
        /^src\/app\/(greenwash|translation|dataverify|materiality|ghg|drafting)\//.test(
          from,
        )
      ) ?
        ['moduleMenu.tsx']
      : [],
    minEntering: 6, // 실측 6(RPW1 ① A4 — *Routes.tsx 여섯)
    minTools: 0,
  },
  {
    // 로그인 화면 폴더(밴드 LG1 — critic 1 반영 B1 ②). index.ts 로만(app/auth 의 경로 컴포넌트가 가져온다). AD1 이 admin-accounts 를 더한다.
    dir: 'pages',
    parts: true,
    partFilter: AUTH_PAGES,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: MIN_AUTH_PAGE_ENTERING,
    minTools: 0,
  },
  {
    // 어드민 화면 폴더(밴드 AD1). index.ts 로만(app/admin 의 경로 컴포넌트가 가져온다).
    dir: 'pages',
    parts: true,
    partFilter: ADMIN_PAGES,
    doors: ['index.ts'],
    toolsDoors: ['index.ts'],
    minEntering: 1, // 실측 1(app/admin/AdminRoutes.tsx → pages/admin-accounts)
    minTools: 0,
  },
  {
    // [L-b] 데모 넷(DEV·VITE_DEMOS 에만)은 index.ts 를 두지 않고 경로 표(app/router.tsx)가 화면 파일을 게으르게 부른다(check-no-demos.sh 가 그 파일의 표식을 본다).
    // 그래서 문은 데모마다 화면 파일 하나다. 검토 표 데모만 e2e 가 가짜 행(fakeRows.ts)을 쓴다(층 순서의 PAGE_ENTRY_EXCEPTIONS 와 같은 줄).
    dir: 'pages',
    parts: true,
    partFilter: /^demo-/,
    doors: [],
    toolsDoors: [],
    partDoors: {
      'demo-viewer': ['App.tsx'],
      'demo-table': ['TablePage.tsx', 'fakeRows.ts'],
      'demo-api': ['ApiPage.tsx'],
      'demo-parts': ['PartsPage.tsx'],
    },
    minEntering: 5, // 실측 5(app/router.tsx 넷, e2e 하나)
    minTools: 0,
  },
];

/** 밖의 파일 하나가 공개 표면 아닌 문으로 row 의 슬라이스에 들어오는 자리들. */
export function sideDoors(
  row: DoorRow,
  file: string,
  source: string,
): { entering: number; tools: number; problems: string[] } {
  const base = join(src, row.dir);
  const fromTools = file.startsWith(join(webRoot, 'tools') + '/');
  const problems: string[] = [];
  let entering = 0;
  let tools = 0;
  if (file.startsWith(base + '/')) {
    // parts 면 다른 부품에서 들어오는 것도 본다(같은 부품 안만 뺀다).
    if (!row.parts) return { entering, tools, problems };
  }
  const own =
    row.parts && file.startsWith(base + '/') ?
      join(base, relative(base, file).split('/')[0]!) + '/'
    : null;
  for (const { path } of relativeImports(file, source)) {
    if (!path.startsWith(base + '/')) continue;
    if (own && path.startsWith(own)) continue;
    const rel = relative(base, path);
    if (row.parts && row.partFilter && !row.partFilter.test(rel.split('/')[0]!))
      continue;
    if (own && !row.partFilter) continue; // shared/ui 부품끼리는 칸 규칙이 본다(옛 components 와 같이)
    entering++;
    if (fromTools) tools++;
    const inSlice = row.parts ? rel.split('/').slice(1).join('/') : rel;
    const doors =
      row.partDoors?.[rel.split('/')[0]!] ??
      row.doorsFor?.(relative(webRoot, file)) ??
      (fromTools ? row.toolsDoors : row.doors);
    if (!doors.includes(inSlice) || (row.parts && !rel.includes('/')))
      problems.push(`${relative(webRoot, file)} → ${relative(webRoot, path)}`);
  }
  return { entering, tools, problems };
}

/** shared/lib 의 시험 도우미 폴더(testing/). */
const LIB_HELPERS = 'shared/lib/testing';
/**
 * shared/lib 안의 제품 파일이 시험 도우미(testing/)를 가져오는 자리들(sid:MARC-ISSUE-145).
 * 문(DOORS)은 밖에서 들어오는 것만 보고, shared/lib 은 칸 없는 파일 모음이라 칸 규칙(SliceRule)의 같은 칸 testing.ts 규칙도 닿지 않는다.
 * 시험과 testing/ 안의 도우미는 된다. 폴더째(./testing)도 잡는다([M1] 과 겹쳐 빨강).
 */
export function libHelperViolations(file: string, source: string): string[] {
  const base = join(src, 'shared/lib') + '/';
  const helpers = join(src, LIB_HELPERS);
  if (
    !file.startsWith(base) ||
    file.startsWith(helpers + '/') ||
    isTestFile(file)
  )
    return [];
  return relativeImports(file, source)
    .filter(({ path }) => path === helpers || path.startsWith(helpers + '/'))
    .map(
      ({ path }) =>
        `${relative(src, file)} 가 시험 도우미 ${relative(src, path)} 를 가져온다(시험과 testing/ 만 쓴다)`,
    );
}

// ───────────────────────── 3. 칸 규칙 ─────────────────────────

/** 칸의 차례(아래 → 위). 위 칸만 아래 칸의 표면을 가져온다. config 는 ui 만 가져온다. */
const SEGMENTS = ['model', 'api', 'hooks', 'ui', 'config'] as const;
type Segment = (typeof SEGMENTS)[number];
const ORDER: Segment[] = ['model', 'api', 'hooks', 'ui'];
const surfaceOf = (segment: Segment) =>
  segment === 'config' ? 'config/text.ts' : `${segment}/index.ts`;

interface RootRule {
  packages: RegExp;
  /** 가져올 수 있는 파일(슬라이스 기준). '*' 는 슬라이스 안 아무것. */
  files: string[] | '*';
  /** 슬라이스 밖에서 더 가져와도 되는 파일(src 기준). */
  also?: (rel: string) => boolean;
}
interface SliceRule {
  /** src 기준 폴더. parts 면 그 아래 폴더 하나하나가 슬라이스(부품)다. */
  dir: string;
  parts?: true;
  /** parts 일 때 슬라이스로 볼 폴더 이름(나머지 폴더는 이 줄이 보지 않는다). */
  partFilter?: RegExp;
  /** 있을 수 있는 칸과 칸마다 쓸 수 있는 패키지. */
  packages: Partial<Record<Segment, RegExp>>;
  /** 칸 안 자리(슬라이스 기준)마다 패키지를 덮어쓸 때. */
  packagesAt?: (inSlice: string, part: string) => RegExp | undefined;
  /** 슬라이스 맨 위 파일(규칙을 받는 것). */
  roots: Record<string, RootRule>;
  /** 슬라이스 맨 위의 시험·도우미(rootTestRule 이 없으면 규칙 밖). */
  rootTests: string[];
  rootTestRule?: RootRule;
  /** parts 의 부모 맨 위에 있어도 되는 파일. */
  groupFiles: string[];
  /** 칸마다 슬라이스 밖에서 더 가져와도 되는 파일(src 기준). part 는 parts 일 때 자기 부품 이름. */
  also: Partial<Record<Segment, (rel: string, part: string) => boolean>>;
  /** ui 칸은 CSS 를 어디서든 가져와도 되는가(아니면 자기 ui 안의 CSS 만). */
  uiAnyCss: boolean;
  /** hooks 칸이 타입으로만 가져와도 되는 파일(슬라이스 기준). */
  hooksTypeOnly: string[];
  /** 시험·도우미가 더 가져와도 되는 파일(src 기준). */
  testAlso: (rel: string) => boolean;
  /** 칸마다 시험이 타입으로만 가져와도 되는 파일(src 기준). */
  testTypeOnly: Partial<Record<Segment, string[]>>;
  /** 시험만 더 쓸 수 있는 패키지. */
  testPackages: string[];
  /** testing.ts 도 시험으로 보는가(시험 패키지를 쓰고 모양·DOM 검사를 받지 않는다). */
  helperIsTest: boolean;
  /** hooks 의 style 모양 키 목록에서 뺄 키. */
  lookKeyExcept: string[];
  /** 모양 값·박은 className·모양 도구를 보는 칸(hooks 는 style 의 모양 키도). */
  looksIn: Segment[];
  /** 모양 검사에서 뺄 자리(슬라이스 기준 접두). */
  noLooksUnder: string[];
  /** 칸마다의 DOM 낱말(없으면 보지 않는다). */
  dom: Partial<Record<Segment, RegExp>>;
  /** 칸 안 자리(슬라이스 기준)마다 DOM 낱말을 덮어쓸 때. */
  domAt?: (inSlice: string) => RegExp | undefined;
  /** model 이 계약 타입(api-py/generated/api.d.ts)을 타입으로만 가져와도 되는가. */
  contractModel: boolean;
  /** 이 슬라이스에만 있는 규칙. */
  extra: (file: string, rel: string, source: string) => string[];
}

const UI_PACKAGES =
  /^(react|react-dom|@radix-ui\/react-slot|@radix-ui\/react-dialog|class-variance-authority|@marcspon\/ui\/(components\/[a-z-]+|lib\/utils)|@marcspon\/common\/generated\/icons\/(MyIcons|icon-base))$/;
/** 마크다운을 그리는 문은 shared/ui/markdown 의 ui 칸 하나다(밴드 MD1). */
const MARKDOWN_UI_PACKAGES = new RegExp(
  `${UI_PACKAGES.source}|^(react-markdown|remark-gfm)$`,
);
/** 그린워싱 ui 의 패키지(옛 greenwash ui: radix 는 shared/ui 부품을 거쳐 쓴다). */
const GW_UI_PACKAGES =
  /^(react|react-dom|class-variance-authority|@marcspon\/ui\/(components\/[a-z-]+|lib\/utils)|@marcspon\/common\/generated\/icons\/(MyIcons|icon-base))$/;
const nothing = () => false;
const noExtra = () => [];
const ENTITY = 'entities/greenwash/';
/** 로그인 세션 슬라이스(밴드 LG1). */
const SESSION = 'entities/session/';
/** entities/session 의 칸 표면(src 기준). */
const sessionDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === SESSION + surfaceOf(segment));
const SESSION_SEGMENTS: Segment[] = ['model', 'api', 'hooks', 'ui', 'config'];
/** entities/account 의 칸 표면(src 기준, 밴드 AD1). */
const accountDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === ACCOUNT + surfaceOf(segment));
/** entities/audit-log 의 칸 표면(src 기준, 밴드 AD5R). */
const auditDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === AUDIT + surfaceOf(segment));
/** entities/run-log 의 칸 표면(src 기준, 밴드 AD4R). */
const runLogDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === RUN_LOG + surfaceOf(segment));
/** entities/greenwash-setting 의 칸 표면(src 기준, 밴드 AD2R). */
const greenwashSettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === GREENWASH_SETTING + surfaceOf(segment));
/** entities/translation-setting 의 칸 표면(src 기준, 밴드 TRA1). */
const translationSettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === TRANSLATION_SETTING + surfaceOf(segment));
/** entities/dataverify-setting 의 칸 표면(src 기준, 밴드 DVA2). */
const dataverifySettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === DATAVERIFY_SETTING + surfaceOf(segment));
/** entities/materiality-setting 의 칸 표면(src 기준, 밴드 IRA2). */
const materialitySettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === MATERIALITY_SETTING + surfaceOf(segment));
/** entities/drafting-setting 의 칸 표면(src 기준, 밴드 RPA3). */
const draftingSettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === DRAFTING_SETTING + surfaceOf(segment));
/** entities/ai-setting 의 칸 표면(src 기준, 밴드 AD2W). */
const aiSettingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === AI_SETTING + surfaceOf(segment));
/** 읽기 훅 하나(밴드 CW1 ①). 그린워싱의 hooks 칸만 가져온다(ui 는 훅을 거친다). */
const LOAD_HOOK = 'shared/lib/useLoad.ts';
/** entities/greenwash 의 칸 표면(src 기준). */
const entityDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === ENTITY + surfaceOf(segment));
/** 영문번역 슬라이스(밴드 TRW0a ②). */
const TRANSLATION = 'entities/translation/';
/** entities/translation 의 칸 표면(src 기준, entityDoor 꼴). */
const translationDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === TRANSLATION + surfaceOf(segment));
/** 데이터 검증 슬라이스(밴드 DV2a ①). */
const DATAVERIFY = 'entities/dataverify/';
/** entities/dataverify 의 칸 표면(src 기준, entityDoor 꼴 — 밴드 DV2a ② H3 ⓒ). */
const dataverifyDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === DATAVERIFY + surfaceOf(segment));
/** 중대성평가 슬라이스(밴드 IRW1 ①). */
const MATERIALITY = 'entities/materiality/';
/** entities/materiality 의 칸 표면(src 기준, entityDoor 꼴 — 밴드 IRW1 ② H3 ⓒ). */
const materialityDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === MATERIALITY + surfaceOf(segment));
/** 온실가스 슬라이스(밴드 W12-0a ①). */
const GHG = 'entities/ghg/';
/** entities/ghg 의 칸 표면(src 기준, entityDoor 꼴 — 밴드 W12-0a ② H4). */
const ghgDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === GHG + surfaceOf(segment));
/** 온실가스 Scope 3 슬라이스(밴드 S3W1 ① H2)와 그 칸 표면에 들어올 수 있는 파일(src 기준). */
const GHG_S3 = 'entities/ghg-scope3/';
const ghgScope3Door = (rel: string) =>
  /^entities\/ghg-scope3\/(model\/index|api\/index|config\/text)\.ts$/.test(
    rel,
  );
// [DB1] 대시보드 화면도 Scope 3 글(scopeTotalMissing·카테고리 이름)을 쓴다(a8 허락 11-07).
const GHG_S3_FROM =
  /^src\/(pages\/ghg-scope3\/|pages\/ghg-dashboard\/|app\/ghg\/(GhgRoutes|Scope3Routes|scope3\.router\.test)\.tsx$)/;
/** 원고작성 슬라이스(밴드 RPW1 ①). */
const DRAFTING = 'entities/drafting/';
/** entities/drafting 의 칸 표면(src 기준, entityDoor 꼴 — 밴드 RPW1 ① A4). */
const draftingDoor = (rel: string, ...segments: Segment[]) =>
  segments.some((segment) => rel === DRAFTING + surfaceOf(segment));
/** shared/ui 부품의 공개 표면(text.ts 는 아니다 [B3]). */
const sharedUiDoor = (rel: string) =>
  /^shared\/ui\/[a-z-]+\/index\.ts$/.test(rel);
/** app/greenwash(틀·경로 컴포넌트)의 패키지: 그린워싱 ui 의 것과 라우터(밴드 RT1). */
const APP_GW_PACKAGES =
  /^(react|react-dom|class-variance-authority|@marcspon\/ui\/(components\/[a-z-]+|lib\/utils)|@marcspon\/common\/generated\/icons\/(MyIcons|icon-base)|@tanstack\/react-router)$/;
/** app/greenwash 가 화면과 함께 쓰는 것: 화면 폴더 표면, entities 표면, shared/ui 부품, 문서 뷰어 표면. */
const appGreenwashAlso = (rel: string) =>
  /^pages\/greenwash-[a-z]+\/index\.ts$/.test(rel) ||
  entityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
  sharedUiDoor(rel) ||
  rel === 'widgets/doc-viewer/index.ts';
/** app/translation(밴드 TRW1a ② H3 ⓒ)이 화면과 함께 쓰는 것: 영문번역 화면 폴더 표면, 영문번역 칸 표면, shared/ui 부품. */
const appTranslationAlso = (rel: string) =>
  /^pages\/translation-[a-z]+\/index\.ts$/.test(rel) ||
  translationDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
  sharedUiDoor(rel);
/** app/dataverify(밴드 DV2a ② H3 ⓒ)가 화면과 함께 쓰는 것: 데이터 검증 화면 폴더 표면, 데이터 검증 칸 표면, shared/ui 부품. */
const appDataverifyAlso = (rel: string) =>
  /^pages\/dataverify-[a-z]+\/index\.ts$/.test(rel) ||
  dataverifyDoor(rel, 'model', 'api', 'hooks', 'config') ||
  sharedUiDoor(rel);
/** app/materiality(밴드 IRW1 ② H3 ⓒⓚ)가 화면과 함께 쓰는 것: 중대성평가 화면 폴더 표면, 중대성평가 칸 표면(ui 포함), shared/ui 부품. */
const appMaterialityAlso = (rel: string) =>
  /^pages\/materiality-[a-z]+\/index\.ts$/.test(rel) ||
  materialityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
  sharedUiDoor(rel);
/** app/ghg(밴드 W12-0a ② H4)가 화면과 함께 쓰는 것: 온실가스 화면 폴더 표면, 온실가스 칸 표면(ui 칸 없음), shared/ui 부품. */
const appGhgAlso = (rel: string) =>
  /^pages\/ghg-[a-z-]+\/index\.ts$/.test(rel) ||
  ghgDoor(rel, 'model', 'api', 'hooks', 'config') ||
  sharedUiDoor(rel);
/** app/drafting(밴드 RPW1 ① A4)이 화면과 함께 쓰는 것: 원고작성 화면 폴더 표면, 원고작성 칸 표면(ui 칸 없음), shared/ui 부품. */
const appDraftingAlso = (rel: string) =>
  /^pages\/drafting-[a-z-]+\/index\.ts$/.test(rel) ||
  draftingDoor(rel, 'model', 'api', 'hooks', 'config') ||
  sharedUiDoor(rel);
/** 모듈 메뉴 한 자리(밴드 DV2a ② H3 ⓗ — app/<모듈> 넷의 틀이 가져온다). */
const MODULE_MENU = 'app/shell/moduleMenu.tsx';
/** app/admin(어드민 틀·경로 컴포넌트, 밴드 AD1)이 가져오는 것: 계정 칸 표면, shared/ui 부품. */
const appAdminAlso = (rel: string) =>
  ACCOUNT_SURFACES.some((door) => rel === ACCOUNT + door) ||
  /^pages\/admin-[a-z-]+\/index\.ts$/.test(rel) ||
  sharedUiDoor(rel);
/**
 * app/admin/AdminRoutes.tsx 가 더 가져오는 것(밴드 AD5R·AD4R): 감사 기록·실행 기록 칸 표면(실서버).
 * 밴드 AD2W(발주서 §2-1-4 ⓖ): 그린워싱 AI 설정 판은 AdminRoutes 가 직접 모른다 — ai-setting-modules.ts 가 잇는다.
 */
const appAdminLiveAlso = (rel: string) =>
  appAdminAlso(rel) ||
  auditDoor(rel, 'model', 'api', 'config') ||
  runLogDoor(rel, 'model', 'api', 'config') ||
  // 밴드 W12-0a ③: 「선택항목」(S18) — 온실가스 코드 목록 어댑터와 그 화면 폴더(공개 index 로만).
  ghgDoor(rel, 'api') ||
  rel === 'pages/ghg-facility-codes/index.ts' ||
  // 밴드 W12-0b1 ③: 「온실가스 인덱스」(S19·S20) — 풀 어댑터는 위 api 표면, 화면 폴더도 공개 index 로만.
  rel === 'pages/ghg-index-pool/index.ts';
/** app/admin/ai-setting-modules.ts(AD-02 의 모듈 줄, 밴드 AD2W ⓖ)가 가져오는 것: 그린워싱 AI 설정 판·AI 설정 칸 표면과 Api 타입. */
const appAdminAiModulesAlso = (rel: string) =>
  greenwashSettingDoor(rel, 'model', 'api', 'ui', 'config') ||
  // 밴드 TRA1: 영문번역 AI 설정 판(그린워싱 줄과 같은 칸 표면).
  translationSettingDoor(rel, 'model', 'api', 'ui', 'config') ||
  // 밴드 DVA2: 데이터 검증 AI 설정 판(영문번역 줄과 같은 칸 표면).
  dataverifySettingDoor(rel, 'model', 'api', 'ui', 'config') ||
  // 밴드 IRA2: 중대성평가 IRO AI 설정 판(데이터 검증 줄과 같은 칸 표면).
  materialitySettingDoor(rel, 'model', 'api', 'ui', 'config') ||
  // 밴드 RPA3: 원고작성 AI 설정 판(중대성평가 줄과 같은 칸 표면).
  draftingSettingDoor(rel, 'model', 'api', 'ui', 'config') ||
  aiSettingDoor(rel, 'model', 'api', 'config') ||
  rel === 'shared/api/index.ts';
/** AD-02 껍데기 폴더(밴드 AD2W ⓕ). */
const AI_SETTINGS_SHELL = 'pages/admin-ai-settings/';
/**
 * AD-02 껍데기(pages/admin-ai-settings/**, 시험 포함)가 entities 에서 가져오는 것은 entities/ai-setting/ 아래뿐이다(허용 목록 — 밴드 AD2W ⓕ, sid:MARC-ENT-386
 * 「껍데기는 모듈을 import 하지 않는다」). 그린워싱(entities/greenwash·greenwash-setting)·데이터 검증 같은 모듈 슬라이스는 app/admin/ai-setting-modules.ts 가 잇는다.
 */
export function aiSettingsShellViolations(
  file: string,
  source: string,
): string[] {
  const rel = relative(src, file);
  if (!rel.startsWith(AI_SETTINGS_SHELL)) return [];
  const reached = new Set(
    relativeImports(file, source)
      .map(({ path }) => relative(src, path))
      .filter((to) => to.startsWith('entities/') && !to.startsWith(AI_SETTING)),
  );
  return [...reached].map(
    (to) =>
      `${rel} 가 ${to} 를 가져온다(AD-02 껍데기는 entities 중 ${AI_SETTING} 만)`,
  );
}
/** app/admin 의 패키지: 키트 아이콘·react·라우터. */
const APP_ADMIN_PACKAGES =
  /^(react|@marcspon\/common\/generated\/icons\/MyIcons|@tanstack\/react-router)$/;

export const SLICES: SliceRule[] = [
  {
    // 옛 components/layers.test.ts. 부품마다 폴더 하나, 모양만 있는 부품은 ui/ 와 index.ts 만.
    dir: 'shared/ui',
    parts: true,
    packages: {
      model: /^$/,
      hooks: /^(react|@tanstack\/react-table)$/,
      ui: UI_PACKAGES,
    },
    packagesAt: (inSlice, part) =>
      part === 'markdown' && inSlice.startsWith('ui/') ?
        MARKDOWN_UI_PACKAGES
      : undefined,
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: ['text.ts', 'text.test.ts'],
    also: {
      ui: (rel, part) =>
        rel === 'shared/ui/text.ts' ||
        rel === 'shared/lib/saveBlob.ts' ||
        rel === 'shared/lib/safeUrl.ts' ||
        (sharedUiDoor(rel) && !rel.startsWith(`shared/ui/${part}/`)),
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    // 옛 greenwash: 부품의 공개 표면은 PARTS_TEXT 를 다시 내보내지 않는다(그 문으로 [B3] 을 돌아가지 못하게).
    extra: (file, rel, source) =>
      (
        /^shared\/ui\/[a-z-]+\/index\.ts$/.test(rel) &&
        reexportsPartsText(source)
      ) ?
        [`${rel} 가 PARTS_TEXT 를 다시 내보낸다`]
      : [],
  },
  {
    // 옛 api/layers.test.ts. client.ts 는 openapi-* 를 아는 유일한 어댑터, ui 칸은 없다.
    dir: 'shared/api',
    packages: { model: /^$/, hooks: /^(react|@tanstack\/react-query)$/ },
    roots: {
      'index.ts': {
        packages: /^$/,
        files: ['model/index.ts', 'hooks/index.ts', 'client.ts'],
      },
      'client.ts': {
        packages: /^(openapi-fetch|openapi-react-query)$/,
        files: ['model/index.ts'],
      },
    },
    rootTests: ['client.test.ts', 'testing.ts'],
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: ['client.ts'],
    testAlso: (rel) =>
      rel === 'shared/api/testing.ts' || rel === 'shared/api/client.ts',
    testTypeOnly: {},
    testPackages: ['react', '@tanstack/react-query'],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: true,
    extra: (file, rel, source) => {
      const hit = FETCHING_DEFAULT.exec(source);
      return hit && !isTestFile(file) && !isHelperFile(file) ?
          [`${rel} 가 패칭 기본값을 품는다: ${hit[0]}`]
        : [];
    },
  },
  {
    // 옛 doc-viewer/layers.test.ts. pdfjs.ts 는 층 밖의 어댑터 하나(hooks 의 공개 표면과 pdfjs-dist 만).
    dir: 'widgets/doc-viewer',
    packages: { model: /^zod$/, hooks: /^react$/, ui: /^react$/ },
    roots: {
      'index.ts': {
        packages: /^$/,
        files: ['model/index.ts', 'hooks/index.ts', 'ui/DocumentViewer.tsx'],
      },
      'pdfjs.ts': {
        packages: /^pdfjs-dist(\/.*)?$/,
        files: ['hooks/index.ts'],
      },
    },
    rootTests: [],
    groupFiles: [],
    also: {},
    uiAnyCss: true,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === 'widgets/doc-viewer/model/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    // model/kinds.ts 가 강조 색 표(HIGHLIGHT_COLORS·MIXED_COLOR)를 품는다. 옛 doc-viewer 시험도 model 의 모양은 보지 않았다.
    looksIn: ['hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: (file, rel, source) =>
      // 쓰는 곳이 없던 내보내기다. 다시 내보내려면 쓰는 화면이 먼저 있어야 한다.
      (
        rel === 'widgets/doc-viewer/hooks/index.ts' &&
        /\bZOOM_STEPS\b/.test(source)
      ) ?
        [
          `${rel} 가 배율 단계(ZOOM_STEPS)를 내보낸다(화면은 zoomIn·zoomOut·canZoomIn·canZoomOut 으로 쓴다)`,
        ]
      : [],
  },
  {
    // 옛 review-table/layers.test.ts. ui 는 TanStack 을 직접 부르지 않는다.
    // 모양 키에서 filter 를 뺐다: 이 부품에서 filter 는 CSS 의 filter 가 아니라 걸러 보기의 이름이다(`filter: RowFilter`).
    dir: 'widgets/review-table',
    packages: {
      model: /^zod$/,
      hooks: /^(react|@tanstack\/react-table|@tanstack\/react-virtual)$/,
      ui: /^react$/,
    },
    roots: {
      'index.ts': {
        packages: /^$/,
        files: ['model/index.ts', 'hooks/index.ts', 'ui/ReviewTable.tsx'],
      },
    },
    rootTests: [],
    groupFiles: [],
    // 셀렉터 한 꼴 ENT-430 — ui 는 shared/ui/filter-select 공개 표면만(그 밖 shared 는 그대로 막힘, 밴드 WS1 D).
    also: {
      ui: (rel) => rel === 'shared/ui/filter-select/index.ts',
    },
    uiAnyCss: true,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      rel === 'widgets/review-table/model/testing.ts' ||
      rel.startsWith('shared/lib/testing/'),
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: ['filter'],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 옛 greenwash/layers.test.ts 의 domain·headless·mock·ui·text.ts. 화면 둘 이상이 쓰는 그린워싱 것.
    //   api/  = 옛 headless 의 store.ts·contract/(zod 거울, zod 는 여기만)와 mock/(목 저장소: 패키지 없음, DOM·location 모름)
    //   hooks/ = 화면 둘 이상이 쓰는 훅. 문서 뷰어를 다시 내보내지 않는다(② 감독 결정: 쓰는 화면이 widgets 를 직접 가져온다)
    //   ui/   = 옛 ui/parts(데모 parts 가 쓰는 표면)와 화면 둘이 쓰는 useObjectUrl,  config/ = 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다)
    dir: 'entities/greenwash',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      ui: GW_UI_PACKAGES,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      // [TRW0a ①] 시각 꼴(formatKst*)은 shared/lib 으로 올렸다 — model 표면이 다시 내보낸다.
      model: (rel) => rel === 'shared/lib/time.ts',
      hooks: (rel) => rel === LOAD_HOOK,
      ui: sharedUiDoor,
      // [GW1R ①] 실어댑터(api/server.ts)는 세션의 Api 를 받는다 — shared/api 의 표면만(account·run-log 꼴).
      api: (rel) => rel === 'shared/api/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    // [WC1 ①] model 의 시험만 shared/api 의 계약 생성 타입을 타입으로만 견준다(contract-types.test.ts).
    testTypeOnly: { model: ['shared/api/index.ts'] },
    testPackages: [],
    // api/mock/testing.ts = 화면 시험이 같이 쓰는 가짜 저장소(밴드 CW1 ②). 시험처럼 vitest 를 가져온다.
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: ['api/mock/'],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    domAt: (inSlice) =>
      inSlice.startsWith('api/mock/') ? MOCK_DOM : undefined,
    contractModel: false,
    extra: (file, rel, source) => {
      const code = withoutComments(source);
      const problems: string[] = [];
      if (
        rel === ENTITY + 'api/index.ts' ||
        rel === ENTITY + 'hooks/index.ts'
      ) {
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      if (rel.startsWith(ENTITY + 'config/'))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      return problems;
    },
  },
  {
    // 영문번역(밴드 TRW0a ② — 그린워싱 줄과 같은 꼴). model = 순수 함수와 타입(쪽 범위 셈), config = 문구 표(아무것도 가져오지 않는다).
    //   ui = 두 화면 이상이 쓰는 모양 부품과 상태 글(TRW0b — 그린워싱 ui 칸과 같은 패키지·shared/ui 부품 표면). model/testing.ts = 시험 도우미(ui 시험이 쓴다).
    dir: 'entities/translation',
    // [TRW1a ① H3 ⓐ] api = 저장소 꼴·실어댑터(shared/api 표면만 — 그린워싱 api 칸 꼴)·contract/(zod 거울, zod 는 여기만),
    //   hooks = 화면 둘 이상이 쓰는 읽기 훅(shared/lib/useLoad). api/testing.ts = 시험이 같이 쓰는 가짜 서버(helperIsTest).
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      ui: GW_UI_PACKAGES,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      // 시각 꼴(formatKst*)은 shared/lib 에서(그린워싱 also.model 과 같은 줄).
      model: (rel) => rel === 'shared/lib/time.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      hooks: (rel) => rel === LOAD_HOOK,
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // [TRW1a ①] hooks 시험은 가짜 서버(api/testing.ts)도 쓴다.
    testAlso: (rel) =>
      rel === TRANSLATION + 'model/testing.ts' ||
      rel === TRANSLATION + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    // 문구 표는 아무것도 가져오지 않는다 — 그 시험(config/text.test.ts)은 vitest 와 문구 표만 가져온다(칸 규칙의 같은 칸 허용).
    // [TRW1a ①] api·hooks 표면은 zod 스키마 값·export * 를 내보내지 않는다(그린워싱 extra 와 같은 줄).
    extra: (file, rel, source) => {
      const problems: string[] = [];
      if (rel.startsWith(TRANSLATION + 'config/') && !isTestFile(file))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      if (
        rel === TRANSLATION + 'api/index.ts' ||
        rel === TRANSLATION + 'hooks/index.ts'
      ) {
        const code = withoutComments(source);
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      return problems;
    },
  },
  {
    // 데이터 검증(밴드 DV2a ① H3 ⓓ — 영문번역 줄과 같은 꼴). model = 순수 함수와 타입(입력 읽기·옵션 크기 셈·검사 줄·상태 글 키),
    //   config = 문구 표(아무것도 가져오지 않는다), api = 저장소 꼴·실어댑터(shared/api 표면만)·contract/(zod 거울, zod 는 여기만),
    //   hooks = 화면 둘 이상이 쓰는 읽기 훅(react·shared/lib/useLoad). ui 칸은 두 화면 이상이 쓰는 것이 생길 때 그 밴드가 더한다. api/testing.ts·model/testing.ts = 시험이 같이 쓰는 가짜 서버·도우미(helperIsTest).
    dir: 'entities/dataverify',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/lib/time.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      hooks: (rel) => rel === LOAD_HOOK,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 지어낸 결과를 계약 거울(api/contract)로 화면 꼴로 바꿔 쓴다.
    testAlso: (rel) =>
      rel === DATAVERIFY + 'model/testing.ts' ||
      rel === DATAVERIFY + 'api/testing.ts' ||
      rel === DATAVERIFY + 'api/contract/index.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    // 문구 표는 아무것도 가져오지 않는다. api·hooks 표면은 zod 스키마 값·export * 를 내보내지 않는다(영문번역 extra 와 같은 줄).
    extra: (file, rel, source) => {
      const problems: string[] = [];
      if (rel.startsWith(DATAVERIFY + 'config/') && !isTestFile(file))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      if (
        rel === DATAVERIFY + 'api/index.ts' ||
        rel === DATAVERIFY + 'hooks/index.ts'
      ) {
        const code = withoutComments(source);
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      return problems;
    },
  },
  {
    // 중대성평가(밴드 IRW1 ① H3 ⓓ — 데이터 검증 줄과 같은 꼴). model = 순수 함수와 타입(서버 값 글자는 model/wire.ts 한 곳·결과 표 줄·
    //   단계 줄·경고 줄·기간), config = 문구 표(아무것도 가져오지 않는다), api = 저장소 꼴·실어댑터(shared/api 표면만)·contract/(zod 거울,
    //   zod 는 여기만), hooks = 화면 둘 이상이 쓰는 읽기 훅(react·shared/lib/useLoad). [IRW1 ② H3 ⓚ] ui = 두 화면 이상이 쓰는 모양
    //   부품(IroFlow — 영문번역 ui 칸 꼴: 그린워싱 ui 칸과 같은 패키지·shared/ui 부품 표면).
    //   api/testing.ts·model/testing.ts = 시험이 같이 쓰는 가짜 서버·도우미(helperIsTest).
    dir: 'entities/materiality',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      ui: GW_UI_PACKAGES,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/lib/time.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      hooks: (rel) => rel === LOAD_HOOK,
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 지어낸 결과를 계약 거울(api/contract)로 화면 꼴로 바꿔 쓴다.
    testAlso: (rel) =>
      rel === MATERIALITY + 'model/testing.ts' ||
      rel === MATERIALITY + 'api/testing.ts' ||
      rel === MATERIALITY + 'api/contract/index.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    // 문구 표는 아무것도 가져오지 않는다. api·hooks 표면은 zod 스키마 값·export * 를 내보내지 않는다(데이터 검증 extra 와 같은 줄).
    extra: (file, rel, source) => {
      const problems: string[] = [];
      if (rel.startsWith(MATERIALITY + 'config/') && !isTestFile(file))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      if (
        rel === MATERIALITY + 'api/index.ts' ||
        rel === MATERIALITY + 'hooks/index.ts'
      ) {
        const code = withoutComments(source);
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      return problems;
    },
  },
  {
    // 온실가스(밴드 W12-0a ① H4 — 중대성평가 줄과 같은 꼴). model = 순수 함수와 타입(요청 id 바꿈 toRequestId 한 곳), config = 문구 표
    //   (아무것도 가져오지 않는다), api = 실어댑터 둘(shared/api 표면만)·contract/(zod 거울, zod 는 여기만), hooks = 화면 둘 이상이 쓰는
    //   읽기 훅(react·shared/lib/useLoad). ui 칸은 없다. api/testing.ts = 시험이 같이 쓰는 가짜 서버(helperIsTest).
    dir: 'entities/ghg',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      api: (rel) => rel === 'shared/api/index.ts',
      hooks: (rel) => rel === LOAD_HOOK,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === GHG + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    // 문구 표는 아무것도 가져오지 않는다. api·hooks 표면은 zod 스키마 값·export * 를 내보내지 않는다(중대성평가 extra 와 같은 줄).
    extra: (file, rel, source) => {
      const problems: string[] = [];
      if (rel.startsWith(GHG + 'config/') && !isTestFile(file))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      if (rel === GHG + 'api/index.ts' || rel === GHG + 'hooks/index.ts') {
        const code = withoutComments(source);
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      return problems;
    },
  },
  {
    // [S3W1 ① H2] 온실가스 Scope 3(entities/ghg 줄 꼴 — hooks·contract 없음). config 는 아무것도 가져오지 않는다.
    dir: 'entities/ghg-scope3',
    packages: { model: /^$/, api: /^$/, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: { api: (rel) => rel === 'shared/api/index.ts' },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === GHG_S3 + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(GHG_S3 + 'config/') && !isTestFile(file) ?
        importsOf(source).map(({ target }) => `${rel} 가 ${target} 를 가져온다`)
      : (
        rel === GHG_S3 + 'api/index.ts' &&
        STAR_EXPORT.test(withoutComments(source))
      ) ?
        [`${rel} 가 export * 로 내보낸다`]
      : [],
  },
  {
    // [RPW1 ① A4] 원고작성(온실가스 줄과 같은 꼴). model = 순수 함수와 타입(주소 id 바꿈 idOf 한 곳), config = 문구 표(아무것도 가져오지 않는다),
    //   api = 실어댑터 하나(shared/api 표면만)·contract/(zod 거울, zod 는 여기만), hooks = 화면 둘 이상이 쓰는 읽기 훅(react·shared/lib/useLoad).
    //   ui 칸은 없다. api/testing.ts = 시험이 같이 쓰는 가짜 서버(helperIsTest).
    dir: 'entities/drafting',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      config: /^$/,
    },
    packagesAt: (inSlice) =>
      inSlice.startsWith('api/contract/') ? /^zod$/ : undefined,
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      api: (rel) => rel === 'shared/api/index.ts',
      hooks: (rel) => rel === LOAD_HOOK,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === DRAFTING + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: HOOKS_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    // 문구 표는 아무것도 가져오지 않는다. api·hooks 표면은 zod 스키마 값·export * 를 내보내지 않는다(온실가스 extra 와 같은 줄).
    extra: (file, rel, source) => {
      const problems: string[] = [];
      if (rel.startsWith(DRAFTING + 'config/') && !isTestFile(file))
        for (const { target } of importsOf(source))
          problems.push(
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
          );
      if (
        rel === DRAFTING + 'api/index.ts' ||
        rel === DRAFTING + 'hooks/index.ts'
      ) {
        const code = withoutComments(source);
        if (SCHEMA_EXPORT.test(code))
          problems.push(`${rel} 가 zod 스키마 값을 내보낸다`);
        if (STAR_EXPORT.test(code))
          problems.push(`${rel} 가 export * 로 내보낸다`);
      }
      return problems;
    },
  },
  {
    // 로그인 세션(밴드 LG1 ①). model = 상태·첫 화면·가드의 순수 함수(계약 타입은 shared/api 의 재수출을 import type 으로만),
    //   api = 세션 저장소(토큰 보관·Bearer·444 에 refresh 한 번·login/refresh/revoke/me/password. 통신 함수와 보관소는 app/ 이 넣는다 — N8),
    //   hooks = useSession(useSyncExternalStore).
    dir: 'entities/session',
    packages: {
      model: /^$/,
      api: /^$/,
      hooks: /^react$/,
      ui: GW_UI_PACKAGES,
      config: /^$/,
    },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === SESSION + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    // api/testing.ts = 가짜 로그인 서버(저장소·훅·경로 시험이 같이 쓴다).
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: SESSION_API_DOM, hooks: HOOKS_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(SESSION + 'config/') ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(SESSION + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 계정(밴드 AD1). model = 꼴·상태 접기·임시 비밀번호 생성·칸 검사(계약 타입은 shared/api 의 재수출을 import type 으로만),
    //   api = 어댑터(넣어 준 Api 만 — 전역 통신·난수·창·보관소·로그를 모른다)와 시험용 가짜 서버(testing.ts),
    //   config = 어드민 틀과 AD-01 의 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다).
    // 임시 비밀번호를 다루는 슬라이스라 model·api 의 제품 파일에 console·storage 낱말이 있으면 빨강이다(ACCOUNT_DOM).
    dir: 'entities/account',
    packages: { model: /^$/, api: /^$/, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) => rel === ACCOUNT + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    // 문구 표의 시험(text.test.ts — 원문을 글자로 박는다)은 vitest 를 가져온다.
    extra: (file, rel, source) =>
      rel.startsWith(ACCOUNT + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(ACCOUNT + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 감사 기록(밴드 AD5R — 감독 판단 Q1 (가), 계정 줄과 같은 꼴). model = 꼴·쿼리·줄 글(순수 함수 — 계약 타입은 shared/api 의 재수출을
    //   import type 으로만), api = 실어댑터(넣어 준 Api 만 — 전역 통신·창·보관소·로그를 모른다)와 시험용 가짜 서버(testing.ts),
    //   config = AD-05 의 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다).
    dir: 'entities/audit-log',
    packages: { model: /^$/, api: /^$/, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 문구 표를 넣어 줄 글을 본다(toEntry 의 글은 넣어 받는다).
    testAlso: (rel) =>
      rel === AUDIT + 'api/testing.ts' || rel === AUDIT + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(AUDIT + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(AUDIT + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 실행 기록(밴드 AD4R — 감독 판단 Q1 (가), 감사 기록 줄과 같은 꼴). model = 꼴·쿼리·표시 글(순수 함수 — 계약 타입은 shared/api 의 재수출을
    //   import type 으로만), api = 실어댑터(넣어 준 Api 만 — 전역 통신·창·보관소·로그를 모른다)와 시험용 가짜 서버(testing.ts),
    //   config = AD-04 의 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다).
    dir: 'entities/run-log',
    packages: { model: /^$/, api: /^$/, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 문구 표를 넣어 표시 글을 본다(글은 넣어 받는다).
    testAlso: (rel) =>
      rel === RUN_LOG + 'api/testing.ts' || rel === RUN_LOG + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(RUN_LOG + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(RUN_LOG + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 그린워싱 AI 설정 판(밴드 AD2R — 감독 판단 Q1 (다), 실행 기록 줄과 같은 꼴). model = 계약 꼴 별칭·판 열 줄·기준 글 검사·저장 본문(순수 함수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만 — 전역 통신·창·보관소·로그를 모른다)와 시험용 가짜 서버(testing.ts),
    //   config = AD-02 실서버 판의 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다).
    //   ui = AD-02 그린워싱 탭의 대상 단어 카드·모듈 초안 슬롯(밴드 AS3b ① — 그린워싱 ui 칸과 같은 패키지·shared/ui 부품 표면. entities/ai-setting 도
    //   이 슬라이스의 api 칸도 가져오지 않는다 — 읽기 함수는 모듈 줄이 넘긴다. 칸 차례로는 ui 가 api 를 가져올 수 있어 extra 가 따로 막는다).
    dir: 'entities/greenwash-setting',
    packages: { model: /^$/, api: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      // AS3b ①: 대상 단어 카드 — shared/ui 부품은 공개 표면(index)만(깊은 경로·새 부품 0, 8e 답 10-23).
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 가짜 서버의 지어낸 판으로 본다.
    testAlso: (rel) =>
      rel === GREENWASH_SETTING + 'api/testing.ts' ||
      rel === GREENWASH_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(GREENWASH_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(GREENWASH_SETTING + 'ui/') && !isTestFile(file) ?
        relativeImports(file, source)
          .filter(({ path }) =>
            relative(src, path).startsWith(GREENWASH_SETTING + 'api/'),
          )
          .map(
            ({ path }) =>
              `${rel} 가 ${relative(src, path)} 를 가져온다(대상 단어 ui 는 api 를 모른다 — 읽기 함수는 모듈 줄이 넘긴다)`,
          )
      : rel.startsWith(GREENWASH_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 영문번역 AI 설정 판(밴드 TRA1 — 그린워싱 AI 설정 판 줄과 같은 꼴). model = 계약 꼴 별칭·나가는 id·거절 code 표·흐름 마디 차례와 번역 소묶음 표(순수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만)와 시험용 가짜 서버(testing.ts), config = 문구 표(아무것도
    //   가져오지 않는다. e2e 가 쓴다), ui = 처리 흐름 띠 + 칸 고름(그린워싱 ui 칸과 같은 패키지 — entities/ai-setting 도 이 슬라이스의 api 칸도 가져오지 않는다).
    dir: 'entities/translation-setting',
    packages: { model: /^$/, api: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      rel === TRANSLATION_SETTING + 'api/testing.ts' ||
      rel === TRANSLATION_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(TRANSLATION_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(TRANSLATION_SETTING + 'ui/') && !isTestFile(file) ?
        relativeImports(file, source)
          .filter(({ path }) =>
            relative(src, path).startsWith(TRANSLATION_SETTING + 'api/'),
          )
          .map(
            ({ path }) =>
              `${rel} 가 ${relative(src, path)} 를 가져온다(흐름 띠 ui 는 api 를 모른다)`,
          )
      : rel.startsWith(TRANSLATION_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 데이터 검증 AI 설정 판(밴드 DVA2 — 영문번역 AI 설정 판 줄과 같은 꼴). model = 계약 꼴 별칭·나가는 id·거절 code 표·흐름 마디 차례와 입력 글 자리 표(순수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만)와 시험용 가짜 서버(testing.ts), config = 문구 표(아무것도
    //   가져오지 않는다. e2e 가 쓴다), ui = 처리 흐름 띠 + 칸 고름(영문번역 ui 칸과 같은 패키지 — entities/ai-setting 도 이 슬라이스의 api 칸도 가져오지 않는다).
    dir: 'entities/dataverify-setting',
    packages: { model: /^$/, api: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      rel === DATAVERIFY_SETTING + 'api/testing.ts' ||
      rel === DATAVERIFY_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(DATAVERIFY_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(DATAVERIFY_SETTING + 'ui/') && !isTestFile(file) ?
        relativeImports(file, source)
          .filter(({ path }) =>
            relative(src, path).startsWith(DATAVERIFY_SETTING + 'api/'),
          )
          .map(
            ({ path }) =>
              `${rel} 가 ${relative(src, path)} 를 가져온다(흐름 띠 ui 는 api 를 모른다)`,
          )
      : rel.startsWith(DATAVERIFY_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 중대성평가 IRO AI 설정 판(밴드 IRA2 — 데이터 검증 AI 설정 판 줄과 같은 꼴). model = 계약 꼴 별칭·나가는 id·거절 code 표·흐름 마디 차례와 자리 표(순수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만)와 시험용 가짜 서버(testing.ts), config = 문구 표(아무것도
    //   가져오지 않는다. e2e 가 쓴다), ui = 처리 흐름 띠 + 칸 고름(데이터 검증 ui 칸과 같은 패키지 — entities/ai-setting 도 이 슬라이스의 api 칸도 가져오지 않는다).
    dir: 'entities/materiality-setting',
    packages: { model: /^$/, api: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      rel === MATERIALITY_SETTING + 'api/testing.ts' ||
      rel === MATERIALITY_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(MATERIALITY_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(MATERIALITY_SETTING + 'ui/') && !isTestFile(file) ?
        relativeImports(file, source)
          .filter(({ path }) =>
            relative(src, path).startsWith(MATERIALITY_SETTING + 'api/'),
          )
          .map(
            ({ path }) =>
              `${rel} 가 ${relative(src, path)} 를 가져온다(흐름 띠 ui 는 api 를 모른다)`,
          )
      : rel.startsWith(MATERIALITY_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // 원고작성 AI 설정 판(밴드 RPA3 — 중대성평가 IRO AI 설정 판 줄과 같은 꼴). entities/drafting(원고작성 화면 칸)은 가져오지 않는다. model = 계약 꼴 별칭·나가는 id·거절 code 표·흐름 마디 차례와 자리 표(순수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만)와 시험용 가짜 서버(testing.ts), config = 문구 표(아무것도
    //   가져오지 않는다. e2e 가 쓴다), ui = 처리 흐름 띠 + 칸 고름(중대성평가 ui 칸과 같은 패키지 — entities/ai-setting 도 이 슬라이스의 api 칸도 가져오지 않는다).
    dir: 'entities/drafting-setting',
    packages: { model: /^$/, api: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
      ui: sharedUiDoor,
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      rel === DRAFTING_SETTING + 'api/testing.ts' ||
      rel === DRAFTING_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: ACCOUNT_DOM, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(DRAFTING_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(DRAFTING_SETTING + 'ui/') && !isTestFile(file) ?
        relativeImports(file, source)
          .filter(({ path }) =>
            relative(src, path).startsWith(DRAFTING_SETTING + 'api/'),
          )
          .map(
            ({ path }) =>
              `${rel} 가 ${relative(src, path)} 를 가져온다(흐름 띠 ui 는 api 를 모른다)`,
          )
      : rel.startsWith(DRAFTING_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
      : [],
  },
  {
    // AI 설정(밴드 AD2W — 발주서 §2-1-4 ⓑ, 실행 기록 줄과 같은 꼴. 옛 어드민 목 슬라이스 줄을 갈음). model = 모듈 슬롯 꼴·프롬프트·모델 꼴(순수 함수 —
    //   계약 타입은 shared/api 의 재수출을 import type 으로만), api = 실어댑터(넣어 준 Api 만 — 전역 통신·창·보관소·로그를 모른다)와 시험용 가짜 서버(testing.ts),
    //   config = AD-02 껍데기의 문구 표(아무것도 가져오지 않는다. e2e 가 쓴다).
    dir: 'entities/ai-setting',
    packages: { model: /^react$/, api: /^$/, config: /^$/ },
    roots: {},
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => rel === 'shared/api/index.ts',
      api: (rel) => rel === 'shared/api/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // model 시험은 가짜 서버의 지어낸 자료와 문구 표로 본다.
    testAlso: (rel) =>
      rel === AI_SETTING + 'api/testing.ts' ||
      rel === AI_SETTING + 'config/text.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: true,
    lookKeyExcept: [],
    looksIn: ['model', 'api'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, api: ACCOUNT_DOM },
    contractModel: false,
    extra: (file, rel, source) =>
      rel.startsWith(AI_SETTING + 'config/') && !isTestFile(file) ?
        importsOf(source).map(
          ({ target }) =>
            `${rel} 가 ${target} 를 가져온다(문구 표는 아무것도 가져오지 않는다)`,
        )
      : rel.startsWith(AI_SETTING + 'model/') ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(model 은 계약 타입만 — import type)`,
          )
          .concat(
            // AP1W ③: 모듈 초안 슬롯의 카드 꼴(ReactNode) 하나 때문에 react 를 연다 — 타입만(import type), 값 import 는 빨강.
            importsOf(source)
              .filter(({ target, typeOnly }) => !typeOnly && target === 'react')
              .map(
                ({ target }) =>
                  `${rel} 가 ${target} 를 값으로 가져온다(model 은 react 타입만 — import type)`,
              ),
          )
      : [],
  },
  {
    // 그린워싱 화면 하나 = 폴더 하나(GW-00~05). 그 화면만 쓰는 model·hooks·ui 와 공개 표면 index.ts(app/greenwash 가 가져온다).
    // ui 는 pdfjs.ts 를 직접 부르지 않는다(openPdf 는 props 로, [R8]).
    dir: 'pages',
    parts: true,
    partFilter: /^greenwash-/,
    packages: { model: /^$/, hooks: /^react$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => entityDoor(rel, 'model'),
      hooks: (rel) =>
        entityDoor(rel, 'model', 'api', 'hooks') ||
        rel === 'widgets/doc-viewer/index.ts' ||
        rel === LOAD_HOOK,
      ui: (rel) =>
        entityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
        sharedUiDoor(rel) ||
        rel === 'widgets/doc-viewer/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // 화면 하나만 쓰는 시험은 목 저장소 표면과 시험용 가짜 저장소(api/mock/testing.ts, 밴드 CW1 ②)도 쓴다.
    testAlso: (rel) =>
      entityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
      rel === ENTITY + 'api/mock/index.ts' ||
      rel === ENTITY + 'api/mock/testing.ts' ||
      // [GW1R] 가짜 그린워싱 서버(진짜 실어댑터 + 가짜 — 발주서 §3 ⓑ).
      rel === ENTITY + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    // 목록 화면의 filter 는 CSS 의 filter 가 아니라 걸러 보기의 이름이다(useCheckList 의 `filter: CheckRowFilter`). review-table 과 같다.
    lookKeyExcept: ['filter'],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, hooks: HOOKS_DOM },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 영문번역 화면 하나 = 폴더 하나(밴드 TRW0a ② — 그린워싱 화면 줄과 같은 꼴, 새 줄). 라우터를 모르고 콜백 props 를 받는다.
    // 영문번역의 칸 표면과 shared/ui 부품을 쓴다. 그린워싱(entities/greenwash·pages/greenwash-*)은 가져오지 않는다.
    dir: 'pages',
    parts: true,
    partFilter: /^translation-/,
    packages: { model: /^$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    // [TRW1a ② — 플랫폼-웹 78 허락 (가), 223 노트] 화면 ui·시험은 영문번역 api(저장소 꼴·storeErrorKind)·hooks(읽기 훅) 문도 쓴다.
    //   시험은 가짜 서버 api/testing.ts 도. 깊은 경로(api/server.ts 등 직접)는 여전히 빨강이다.
    also: {
      model: (rel) => translationDoor(rel, 'model'),
      ui: (rel) =>
        translationDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
        sharedUiDoor(rel) ||
        // [TRW6 ③ H1 — 플랫폼-웹 71 허락, sid:MARC-TICK-378 노트] PDF 보기(translation-run ui/pdf)가 공용 문서 뷰어 부품을 문으로만 쓴다.
        rel === 'widgets/doc-viewer/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      translationDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
      rel === TRANSLATION + 'model/testing.ts' ||
      rel === TRANSLATION + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 데이터 검증 화면 하나 = 폴더 하나(밴드 DV2a ② H3 ⓔ — 영문번역 화면 줄과 같은 꼴). 라우터를 모르고 콜백 props 를 받는다.
    // 데이터 검증의 칸 표면과 shared/ui 부품을 쓴다. 그린워싱·영문번역(entities·pages)은 가져오지 않는다. 시험은 가짜 서버·도우미도.
    dir: 'pages',
    parts: true,
    partFilter: /^dataverify-/,
    packages: { model: /^$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => dataverifyDoor(rel, 'model'),
      ui: (rel) =>
        dataverifyDoor(rel, 'model', 'api', 'hooks', 'config') ||
        sharedUiDoor(rel),
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      dataverifyDoor(rel, 'model', 'api', 'hooks', 'config') ||
      rel === DATAVERIFY + 'model/testing.ts' ||
      rel === DATAVERIFY + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 중대성평가 화면 하나 = 폴더 하나(밴드 IRW1 ② H3 ⓔ — 데이터 검증 화면 줄과 같은 꼴). 라우터를 모르고 콜백 props 를 받는다.
    // 중대성평가의 칸 표면(ui 포함)과 shared/ui 부품을 쓴다. 남의 모듈(entities·pages)은 가져오지 않는다. 시험은 가짜 서버·도우미도.
    dir: 'pages',
    parts: true,
    partFilter: /^materiality-/,
    // 화면 폴더에 model 칸은 없다(셈은 entities/materiality/model — ③ 목록이 필요하면 그 밴드가 더한다).
    packages: { ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      ui: (rel) =>
        materialityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
        sharedUiDoor(rel) ||
        // [IRW12 — 1-1 줄이 칩·「제목 · 회색 주소」를 가르는 판별(공통 링크 칩과 같은 규칙), sid:MARC-TICK-498]
        rel === 'shared/lib/safeUrl.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      materialityDoor(rel, 'model', 'api', 'hooks', 'ui', 'config') ||
      rel === MATERIALITY + 'model/testing.ts' ||
      rel === MATERIALITY + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // 온실가스 화면 하나 = 폴더 하나(밴드 W12-0a ② H4 — 중대성평가 화면 줄과 같은 꼴). 라우터·세션을 모르고 콜백 props 를 받는다.
    // 온실가스의 칸 표면과 shared/ui 부품을 쓴다. 남의 모듈(entities·pages)은 가져오지 않는다. 시험은 가짜 서버도.
    dir: 'pages',
    parts: true,
    partFilter: /^ghg-/,
    packages: { ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      ui: (rel) =>
        rel === 'widgets/review-table/model/index.ts' || // [S3W2a ① Q3] 문은 DOORS 의 doorsFor 가 pages/ghg-scope3 로 좁힌다
        ghgDoor(rel, 'model', 'api', 'hooks', 'config') ||
        sharedUiDoor(rel) ||
        ghgScope3Door(rel) ||
        rel === 'shared/lib/saveBlob.ts', // [W12-5] S5 받기 줄·양식 받기(DownloadButton 꼴이 아니라 직접 — ui 칸만, a8 허락)
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      ghgDoor(rel, 'model', 'api', 'hooks', 'config') ||
      // [S3W1 ② H2] Scope 3 칸(문은 DOORS 의 GHG_S3_FROM 이 pages/ghg-scope3 로 좁힌다).
      ghgScope3Door(rel) ||
      rel === GHG_S3 + 'api/testing.ts' ||
      rel === GHG + 'api/testing.ts' ||
      rel === 'shared/api/index.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [RPW1 ① A4] 원고작성 화면 하나 = 폴더 하나(온실가스 화면 줄과 같은 꼴). 라우터·세션을 모르고 콜백 props 를 받는다.
    // 원고작성의 칸 표면과 shared/ui 부품을 쓴다. 남의 모듈(entities·pages)은 가져오지 않는다. 시험은 가짜 서버도.
    //   공용 문서 뷰어(widgets/doc-viewer/index.ts)는 RP-04(pages/drafting-draft)만 — 아래 줄([RPW1 ③ A4])이 그 폴더를 맡는다.
    dir: 'pages',
    parts: true,
    partFilter: /^drafting-(?!draft$)/,
    // [RPW1 ② A4] model = 화면 하나의 순수 셈(RP-03 목차 트리 — DOM 0, 원고작성 model 표면만).
    packages: { model: /^$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => draftingDoor(rel, 'model'),
      ui: (rel) =>
        draftingDoor(rel, 'model', 'api', 'hooks', 'config') ||
        sharedUiDoor(rel),
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      draftingDoor(rel, 'model', 'api', 'hooks', 'config') ||
      rel === DRAFTING + 'api/testing.ts' ||
      rel === 'shared/api/index.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: noExtra,
  },
  {
    // [RPW1 ③ A4] RP-04 개조식 초안(pages/drafting-draft) — 위 원고작성 화면 줄과 같은 꼴에 공용 문서 뷰어 표면 하나를 더한다
    //   (원문 보기: PageCanvas·usePdf·OpenPdf — pdf.js 여는 함수는 틀이 props 로, pdfjs.ts 는 가져오지 않는다). 영문번역 화면 줄과 같은 한 줄.
    dir: 'pages',
    parts: true,
    partFilter: /^drafting-draft$/,
    // [RPW1 ② A4] model = 화면 하나의 순수 셈(RP-03 목차 트리 — DOM 0, 원고작성 model 표면만).
    packages: { model: /^$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      model: (rel) => draftingDoor(rel, 'model'),
      ui: (rel) =>
        draftingDoor(rel, 'model', 'api', 'hooks', 'config') ||
        sharedUiDoor(rel) ||
        rel === 'widgets/doc-viewer/index.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      draftingDoor(rel, 'model', 'api', 'hooks', 'config') ||
      rel === DRAFTING + 'api/testing.ts' ||
      rel === 'widgets/doc-viewer/index.ts' ||
      rel === 'shared/api/index.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model'],
    noLooksUnder: [],
    dom: { model: DOM_WORD },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 로그인 화면 하나 = 폴더 하나(밴드 LG1 — CM-01·01a·01b 는 login, CM-02 는 password-change). 라우터를 모르고 콜백 props 를 받는다.
    // 세션의 칸 표면과 shared/ui 부품을 쓴다. 그린워싱 줄(/^greenwash-/)은 넓히지 않고 새 줄로 둔다(critic 1 반영 B1 ②).
    dir: 'pages',
    parts: true,
    partFilter: AUTH_PAGES,
    packages: { model: /^$/, hooks: /^react$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    also: {
      hooks: (rel) => sessionDoor(rel, 'model', 'api', 'hooks'),
      ui: (rel) => sessionDoor(rel, ...SESSION_SEGMENTS) || sharedUiDoor(rel),
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: (rel) =>
      sessionDoor(rel, ...SESSION_SEGMENTS) ||
      rel === SESSION + 'api/testing.ts',
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, hooks: HOOKS_DOM },
    contractModel: false,
    extra: noExtra,
  },
  {
    // 어드민 화면 하나 = 폴더 하나(밴드 AD1 — 감독 판단 3, AD-01 은 admin-accounts). 라우터를 모르고 어댑터·콜백 props 를 받는다.
    // 계정의 칸 표면과 shared/ui 부품을 쓴다. 세션 문은 없다(세션은 app/admin 이 넣는다). 로그인 줄(AUTH_PAGES)은 넓히지 않는다.
    dir: 'pages',
    parts: true,
    partFilter: ADMIN_PAGES,
    // model = 웹 안 거르기(③ — 감독 판단 4).
    packages: { model: /^$/, hooks: /^react$/, ui: GW_UI_PACKAGES },
    roots: { 'index.ts': { packages: /^$/, files: '*' } },
    rootTests: [],
    groupFiles: [],
    // AD2: 어드민 목 슬라이스 셋의 문을 더한다(감독 판단 4 — 이 줄의 허용 넓힘, 빼거나 다른 줄을 넓히지 않음).
    // AD5R: 감사 기록은 목 셋에서 빠져 실서버 줄이 됐다 — 같은 칸 표면을 auditDoor 로(허용은 그대로, 이름만 옮김).
    // AD4R: 실행 기록도 — 같은 칸 표면을 runLogDoor 로(허용은 그대로, 이름만 옮김).
    // AD2R: 그린워싱 AI 설정 판(새 실서버 줄)의 칸 표면을 greenwashSettingDoor 로 더했다(실행 기록과 같은 칸).
    // AD2W(발주서 §2-1-4 ⓐ·ⓑ): 그 문을 걷고(화면 껍데기는 모듈을 모른다 — sid:MARC-ENT-386), 목 문(adminMockDoor)을 실서버 aiSettingDoor 로 갈음.
    also: {
      model: (rel) =>
        accountDoor(rel, 'model') ||
        auditDoor(rel, 'model') ||
        runLogDoor(rel, 'model') ||
        aiSettingDoor(rel, 'model'),
      hooks: (rel) =>
        accountDoor(rel, 'model', 'api') ||
        auditDoor(rel, 'model', 'api') ||
        runLogDoor(rel, 'model', 'api') ||
        aiSettingDoor(rel, 'model', 'api'),
      ui: (rel) =>
        accountDoor(rel, 'model', 'api', 'config') ||
        auditDoor(rel, 'model', 'api', 'config') ||
        runLogDoor(rel, 'model', 'api', 'config') ||
        aiSettingDoor(rel, 'model', 'api', 'config') ||
        sharedUiDoor(rel) ||
        rel === 'shared/lib/saveBlob.ts',
    },
    uiAnyCss: false,
    hooksTypeOnly: [],
    // 화면 시험은 진짜 어댑터에 가짜 계정·감사·실행 기록·AI 설정 서버를 물린다(createApi — shared/api 의 문).
    // AD2W: 그린워싱 AI 설정 판(문·가짜 서버)은 걷었다 — 그 모듈은 app/admin 의 시험이 본다.
    testAlso: (rel) =>
      accountDoor(rel, 'model', 'api', 'config') ||
      rel === ACCOUNT + 'api/testing.ts' ||
      auditDoor(rel, 'model', 'api', 'config') ||
      rel === AUDIT + 'api/testing.ts' ||
      runLogDoor(rel, 'model', 'api', 'config') ||
      rel === RUN_LOG + 'api/testing.ts' ||
      aiSettingDoor(rel, 'model', 'api', 'config') ||
      rel === AI_SETTING + 'api/testing.ts' ||
      rel === 'shared/api/index.ts' ||
      sharedUiDoor(rel),
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: ['model', 'hooks'],
    noLooksUnder: [],
    dom: { model: DOM_WORD, hooks: HOOKS_DOM },
    contractModel: false,
    // AD2W(발주서 §2-1-4 ⓕ): AD-02 껍데기(pages/admin-ai-settings)는 시험까지 entities 중 entities/ai-setting 만(허용 목록 — aiSettingsShellViolations).
    extra: (file, rel, source) => {
      const shell = aiSettingsShellViolations(file, source);
      if (isTestFile(file)) return shell;
      const word = ADMIN_PAGE_WORDS.exec(withoutComments(source));
      return word ?
          [...shell, `${rel} 가 보관소·로그를 쓴다: ${word[0]}`]
        : shell;
    },
  },
  {
    // 로그인 경로(밴드 LG1). guard.ts = 세션 저장소에 전역 통신·보관소를 넣고 beforeLoad 가드를 둔다(app/router.tsx 가 정적으로 가져온다 —
    // 진입 청크). AuthRoutes.tsx = 경로 컴포넌트(app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다). router.test.tsx = 가드·로그인 경로 시험.
    dir: 'app/auth',
    packages: {},
    roots: {
      'guard.ts': {
        packages: /^@tanstack\/react-router$/,
        files: [],
        also: (rel) =>
          sessionDoor(rel, 'model', 'api') || rel === 'shared/lib/address.ts',
      },
      'AuthRoutes.tsx': {
        packages: /^(react|@tanstack\/react-router)$/,
        files: ['guard.ts'],
        also: (rel) =>
          /^pages\/(login|password-change)\/index\.ts$/.test(rel) ||
          sessionDoor(rel, ...SESSION_SEGMENTS) ||
          sharedUiDoor(rel),
      },
    },
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: /^(react|@tanstack\/react-router)$/,
      files: '*',
      also: (rel) =>
        rel === 'app/router.tsx' ||
        sessionDoor(rel, ...SESSION_SEGMENTS) ||
        rel === SESSION + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // 그린워싱 틀과 경로 컴포넌트(GreenwashRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 router context 의 꼴(runtime.ts, 타입만),
    // 경로 표 시험(router.test.tsx — 화면 여럿과 목을 함께 본다). 밴드 RT1 이 옛 GreenwashPage(진입)·GreenwashApp(화면 전환)·index.ts 를 갈음했다.
    // 옛 greenwash 맨 위 파일의 상한 [R8]: pdfjs.ts·목 저장소 표면을 가져오는 것은 GreenwashRoutes 하나(기본값). 화면(ui)은 openPdf 를 props 로 받는다.
    dir: 'app/greenwash',
    packages: {},
    roots: {
      'GreenwashRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: ['runtime.ts'],
        also: (rel) =>
          rel === MODULE_MENU ||
          appGreenwashAlso(rel) ||
          rel === 'widgets/doc-viewer/pdfjs.ts' ||
          rel === ENTITY + 'api/mock/index.ts' ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(밴드 SV1 — 감독 판단 4, 이 한 줄만).
          sessionDoor(rel, 'hooks'),
      },
      // 타입만(router.tsx 가 import type 으로 가져온다 — 진입 청크에 값이 들지 않게).
      'runtime.ts': {
        packages: /^$/,
        files: [],
        also: (rel) =>
          entityDoor(rel, 'api') || rel === 'widgets/doc-viewer/index.ts',
      },
    },
    // [L-c] 화면 여럿을 함께 보는 시험만 여기에 둔다: 경로 표 시험(밴드 RT1). 경로 표(../router.tsx)와 목 저장소 표면도 쓴다.
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appGreenwashAlso(rel) ||
        rel === 'app/router.tsx' ||
        rel === ENTITY + 'api/mock/index.ts' ||
        // [GW1R] 기본 저장소(실어댑터)를 가짜 그린워싱 서버로 잰다.
        rel === ENTITY + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [TRW1a ② H3 ⓒ] 영문번역 틀과 경로 컴포넌트(TranslationRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 router context 의 꼴
    // (runtime.ts, 타입만), 경로 표 시험(router.test.tsx). app/greenwash 줄을 옮겨 적었다 — 그린워싱(entities/greenwash·pages/greenwash-*·app/greenwash)은 가져오지 않는다.
    dir: 'app/translation',
    packages: {},
    roots: {
      'TranslationRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: ['runtime.ts'],
        also: (rel) =>
          rel === MODULE_MENU ||
          appTranslationAlso(rel) ||
          // [TRW6 ③ H2 — 71 허락] PDF 보기 경로가 pdf.js 여는 함수를 틀에서 화면 props 로 넘긴다(그린워싱 틀과 같은 한 줄).
          rel === 'widgets/doc-viewer/pdfjs.ts' ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(그린워싱 틀과 같은 한 줄).
          sessionDoor(rel, 'hooks'),
      },
      // 타입만(router.tsx 가 import type 으로 가져온다 — 진입 청크에 값이 들지 않게).
      'runtime.ts': {
        packages: /^$/,
        files: [],
        also: (rel) => translationDoor(rel, 'model', 'api'),
      },
    },
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appTranslationAlso(rel) ||
        rel === 'app/router.tsx' ||
        // 기본 저장소(실어댑터)를 가짜 영문번역 서버로 잰다.
        rel === TRANSLATION + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [DV2a ② H3 ⓕ] 데이터 검증 틀과 경로 컴포넌트(DataverifyRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 router context 의 꼴
    // (runtime.ts, 타입만), 경로 표 시험(router.test.tsx). app/translation 줄을 옮겨 적었다 — 그린워싱·영문번역(entities·pages·app)은 가져오지 않는다.
    dir: 'app/dataverify',
    packages: {},
    roots: {
      'DataverifyRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: ['runtime.ts'],
        also: (rel) =>
          rel === MODULE_MENU ||
          appDataverifyAlso(rel) ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(영문번역 틀과 같은 한 줄).
          sessionDoor(rel, 'hooks'),
      },
      // 타입만(router.tsx 가 import type 으로 가져온다 — 진입 청크에 값이 들지 않게).
      'runtime.ts': {
        packages: /^$/,
        files: [],
        also: (rel) => dataverifyDoor(rel, 'model', 'api'),
      },
    },
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appDataverifyAlso(rel) ||
        rel === 'app/router.tsx' ||
        // 기본 저장소(실어댑터)를 가짜 데이터 검증 서버로 잰다.
        rel === DATAVERIFY + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [IRW1 ② H3 ⓕ] 중대성평가 틀과 경로 컴포넌트(MaterialityRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 router context 의 꼴
    // (runtime.ts, 타입만), 경로 표 시험(router.test.tsx). app/dataverify 줄을 옮겨 적었다 — 남의 모듈(entities·pages·app)은 가져오지 않는다.
    dir: 'app/materiality',
    packages: {},
    roots: {
      'MaterialityRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: ['runtime.ts'],
        also: (rel) =>
          rel === MODULE_MENU ||
          appMaterialityAlso(rel) ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(데이터 검증 틀과 같은 한 줄).
          sessionDoor(rel, 'hooks'),
      },
      // 타입만(router.tsx 가 import type 으로 가져온다 — 진입 청크에 값이 들지 않게).
      'runtime.ts': {
        packages: /^$/,
        files: [],
        also: (rel) => materialityDoor(rel, 'model', 'api'),
      },
    },
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appMaterialityAlso(rel) ||
        rel === 'app/router.tsx' ||
        // 기본 저장소(실어댑터)를 가짜 중대성평가 서버로 잰다.
        rel === MATERIALITY + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [W12-0a ② H4] 온실가스 틀과 경로 컴포넌트(GhgRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 경로 표 시험(router.test.tsx).
    // app/materiality 줄을 옮겨 적었다 — router context 칸(runtime.ts)은 없다(실어댑터는 세션 api). 남의 모듈(entities·pages·app)은 가져오지 않는다.
    dir: 'app/ghg',
    packages: {},
    roots: {
      'GhgRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: [],
        also: (rel) =>
          rel === MODULE_MENU ||
          appGhgAlso(rel) ||
          // [S3W1 ③ H2] Scope 탭 줄의 글(문은 DOORS 의 GHG_S3_FROM).
          ghgScope3Door(rel) ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(중대성평가 틀과 같은 한 줄).
          sessionDoor(rel, 'hooks'),
      },
      // [S3W1 ③ H2] Scope 3 경로 컴포넌트(게으르게) — 틀의 ScopeTabs·useOperator 를 쓴다.
      'Scope3Routes.tsx': {
        packages: APP_GW_PACKAGES,
        files: ['GhgRoutes.tsx'],
        also: (rel) =>
          appGhgAlso(rel) ||
          ghgScope3Door(rel) ||
          rel === 'pages/ghg-scope3/index.ts', // appGhgAlso 의 [a-z-] 는 숫자 든 폴더를 안 받는다
      },
    },
    rootTests: ['router.test.tsx', 'scope3.router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appGhgAlso(rel) ||
        rel === 'app/router.tsx' ||
        // [S3W1 ③ H2] Scope 3 칸과 그 가짜 서버.
        ghgScope3Door(rel) ||
        rel === GHG_S3 + 'api/testing.ts' ||
        // 세션 send 뒤에 가짜 온실가스 서버를 둔다.
        rel === GHG + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [RPW1 ① A4] 원고작성 틀과 경로 컴포넌트(DraftingRoutes: app/router.tsx 가 lazyRouteComponent 로 게으르게 부른다)와 경로 표 시험(router.test.tsx).
    // app/ghg 줄을 옮겨 적었다 — router context 칸(runtime.ts)은 없다(실어댑터는 세션 api). 남의 모듈(entities·pages·app)은 가져오지 않는다.
    dir: 'app/drafting',
    packages: {},
    roots: {
      'DraftingRoutes.tsx': {
        packages: APP_GW_PACKAGES,
        files: [],
        also: (rel) =>
          rel === MODULE_MENU ||
          appDraftingAlso(rel) ||
          // [RPW1 A4] RP-04 원문 보기가 pdf.js 여는 함수를 틀에서 화면 props 로 넘긴다(영문번역 틀과 같은 한 줄 — 화면은 pdfjs.ts 를 모른다).
          rel === 'widgets/doc-viewer/pdfjs.ts' ||
          // 운영 관리자 갈래를 세션 스냅샷에서 읽는다(온실가스 틀과 같은 한 줄).
          sessionDoor(rel, 'hooks'),
      },
    },
    rootTests: ['router.test.tsx'],
    rootTestRule: {
      packages: APP_GW_PACKAGES,
      files: '*',
      also: (rel) =>
        appDraftingAlso(rel) ||
        rel === 'app/router.tsx' ||
        // 세션 send 뒤에 가짜 원고작성 서버를 둔다.
        rel === DRAFTING + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // [DV2a ② H3 ⓗ] 모듈 메뉴 한 자리(moduleMenu.tsx — 셸 메뉴 여섯·누른 항목의 주소)와 그 시험. shared 만 가져온다(키트 아이콘·AppShell 항목 꼴).
    //   들어올 수 있는 쪽은 app/<모듈> 넷뿐이다(DOORS 의 app/shell 줄).
    dir: 'app/shell',
    packages: {},
    roots: {
      'moduleMenu.tsx': {
        packages: /^(react|@marcspon\/common\/generated\/icons\/MyIcons)$/,
        files: [],
        also: sharedUiDoor,
      },
    },
    rootTests: ['moduleMenu.test.ts'],
    rootTestRule: {
      packages: /^(react|@marcspon\/common\/generated\/icons\/MyIcons)$/,
      files: ['moduleMenu.tsx'],
      also: nothing,
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    extra: noExtra,
  },
  {
    // 어드민 틀과 경로 컴포넌트(밴드 AD1). AdminRoutes.tsx = 틀(AppShell·머리 인사말+로그아웃)과 경로 컴포넌트(app/router.tsx 가 게으르게 부른다).
    // runtime.ts = router context 의 어드민 칸 꼴(타입만 — router.tsx 가 import type 으로). router.test.tsx = 어드민 가드·경로 시험.
    dir: 'app/admin',
    packages: {},
    roots: {
      'AdminRoutes.tsx': {
        packages: APP_ADMIN_PACKAGES,
        // AD2W ⓖ: AD-02 의 모듈은 ai-setting-modules.ts 한 줄로 받는다(그린워싱 AI 설정 판을 직접 모른다).
        files: ['runtime.ts', 'ai-setting-modules.ts'],
        // AD5R·AD4R: AD-05 감사 기록·AD-04 실행 기록(실서버)의 경로 컴포넌트도 여기 — 두 슬라이스의 칸 표면.
        also: appAdminLiveAlso,
      },
      // AD2W ⓒ: 옛 목 덧칠 타입(entities/ai-setting/api)을 걷어 아무것도 가져오지 않는다(아래 extra 가 값 import 도 잡는다).
      'runtime.ts': {
        packages: /^$/,
        files: [],
      },
      // AD2W ⓖ: AD-02 의 모듈 줄(sid:MARC-ENT-386). 그린워싱 AI 설정 판·AI 설정의 칸 표면과 Api 타입(shared/api 는 import type 만 — 아래 extra).
      'ai-setting-modules.ts': {
        packages: /^$/,
        files: [],
        also: appAdminAiModulesAlso,
      },
    },
    rootTests: ['router.test.tsx', 'ai-setting-modules.test.ts'],
    rootTestRule: {
      packages: /^(react|@tanstack\/react-router)$/,
      files: '*',
      also: (rel) =>
        appAdminLiveAlso(rel) ||
        // AD2W ⓖ: 모듈 줄 시험(ai-setting-modules.test.ts)과 경로 시험은 두 슬라이스의 칸 표면·가짜 서버와 createApi 를 쓴다.
        appAdminAiModulesAlso(rel) ||
        rel === 'app/router.tsx' ||
        sessionDoor(rel, ...SESSION_SEGMENTS) ||
        rel === SESSION + 'api/testing.ts' ||
        rel === ACCOUNT + 'api/testing.ts' ||
        rel === AUDIT + 'api/testing.ts' ||
        rel === RUN_LOG + 'api/testing.ts' ||
        rel === GREENWASH_SETTING + 'api/testing.ts' ||
        rel === AI_SETTING + 'api/testing.ts' ||
        rel === TRANSLATION_SETTING + 'api/testing.ts' ||
        rel === DATAVERIFY_SETTING + 'api/testing.ts' ||
        rel === MATERIALITY_SETTING + 'api/testing.ts' ||
        rel === DRAFTING_SETTING + 'api/testing.ts' ||
        // [W12-0a ③] /admin/options 의 코드 목록을 가짜 온실가스 서버로.
        rel === GHG + 'api/testing.ts' ||
        // [GW1R] 고객사 사용자가 /greenwash 를 열면 기본 저장소가 실어댑터다(함정 ① — 가짜 그린워싱 서버를 잇는다).
        rel === ENTITY + 'api/testing.ts',
    },
    groupFiles: [],
    also: {},
    uiAnyCss: false,
    hooksTypeOnly: [],
    testAlso: nothing,
    testTypeOnly: {},
    testPackages: [],
    helperIsTest: false,
    lookKeyExcept: [],
    looksIn: [],
    noLooksUnder: [],
    dom: {},
    contractModel: false,
    // runtime.ts 는 타입 자리 — 가져오는 것은 모두 import type(밴드 AD2 ②).
    // ai-setting-modules.ts 는 shared/api 를 import type 으로만(Api 꼴 — 통신은 AdminRoutes 가 넣는다, 밴드 AD2W ⓖ).
    extra: (file, rel, source) =>
      rel === 'app/admin/runtime.ts' ?
        importsOf(source)
          .filter(({ typeOnly }) => !typeOnly)
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(타입 자리 — import type 만)`,
          )
      : rel === 'app/admin/ai-setting-modules.ts' ?
        importsOf(source)
          .filter(
            ({ target, typeOnly }) =>
              !typeOnly && /shared\/api\/index\.ts$/.test(target),
          )
          .map(
            ({ target }) =>
              `${rel} 가 ${target} 를 값으로 가져온다(Api 는 꼴만 — import type)`,
          )
      : [],
  },
];

type Where =
  | {
      kind: 'segment';
      segment: Segment;
      slice: string;
      label: string;
      inSlice: string;
    }
  | { kind: 'root'; name: string; slice: string; label: string }
  | { kind: 'rootTest'; name: string; slice: string; label: string }
  | { kind: 'group' }
  | { kind: 'stray'; label: string };

/** 슬라이스 안 파일의 자리. slice 는 src 기준 슬라이스 폴더, label 은 메시지 머리. */
export function whereIn(rule: SliceRule, file: string): Where | null {
  const rel = relative(join(src, rule.dir), file);
  if (rel.startsWith('..')) return null;
  let parts = rel.split('/');
  let slice = rule.dir;
  if (rule.parts) {
    if (parts.length === 1)
      return (
        rule.partFilter ? null
        : rule.groupFiles.includes(rel) ? { kind: 'group' }
        : { kind: 'stray', label: `${rule.dir}/${rel}` }
      );
    if (rule.partFilter && !rule.partFilter.test(parts[0]!)) return null;
    slice = `${rule.dir}/${parts[0]}`;
    parts = parts.slice(1);
  }
  const inSlice = parts.join('/');
  const label = `${slice}/${inSlice}`;
  if (parts.length === 1) {
    if (rule.roots[inSlice])
      return { kind: 'root', name: inSlice, slice, label };
    if (rule.rootTests.includes(inSlice))
      return { kind: 'rootTest', name: inSlice, slice, label };
    return { kind: 'stray', label };
  }
  const segment = parts[0] as Segment;
  if (rule.packages[segment])
    return {
      kind: 'segment',
      segment,
      slice,
      label: `${slice}/${segment}`,
      inSlice,
    };
  return { kind: 'stray', label };
}

/** 한 파일의 칸 규칙 위반. 시험이 규칙 자체도 시험할 수 있게 함수로 뺐다. */
export function violations(
  rule: SliceRule,
  file: string,
  source: string,
): string[] {
  const where = whereIn(rule, file);
  if (!where || where.kind === 'group') return [];
  if (where.kind === 'rootTest' && !rule.rootTestRule) return [];
  if (where.kind === 'stray')
    return [
      `${where.label} 는 정해진 자리(${rule.parts ? '<슬라이스>/' : ''}${[...Object.keys(rule.roots), ...rule.rootTests].join('·')}${Object.keys(rule.packages).length ? `, {${Object.keys(rule.packages).join(',')}}/` : ''}) 밖에 있다`,
    ];
  const { slice, label } = where;
  const base = join(src, slice);
  const test =
    where.kind === 'rootTest' ||
    isTestFile(file) ||
    (rule.helperIsTest && isHelperFile(file));
  const part = rule.parts ? slice.split('/').pop()! : '';
  const root =
    where.kind === 'root' ? rule.roots[where.name]!
    : where.kind === 'rootTest' ? rule.rootTestRule!
    : null;
  const problems: string[] = [];
  const packages =
    root ? root.packages
    : where.kind === 'segment' ?
      (rule.packagesAt?.(where.inSlice, part) ?? rule.packages[where.segment]!)
    : /^$/;
  for (const { target, typeOnly } of importsOf(source)) {
    if (!target.startsWith('.')) {
      if (
        !packages.test(target) &&
        !(
          test &&
          (TEST_PACKAGES.includes(target) || rule.testPackages.includes(target))
        )
      )
        problems.push(`${label} 가 ${target} 를 가져온다`);
      continue;
    }
    const path = resolve(dirname(file), target);
    const relSrc = relative(src, path);
    const relSlice = relative(base, path);
    // 같은 슬라이스의 시험 도우미(testing.ts)는 시험과 도우미만 가져온다 — 칸 방향·같은 칸 허용보다 먼저 본다(sid:MARC-ISSUE-128).
    // 슬라이스 밖의 testing.ts 는 문(DOORS)과 testAlso 가 막는다. 확장자 없는 import 도 여기서 같이 잡는다([M1] 과 겹쳐 빨강).
    if (
      !test &&
      !isHelperFile(file) &&
      path.startsWith(base + '/') &&
      /(^|\/)testing(\.tsx?)?$/.test(path)
    ) {
      problems.push(
        `${label} 가 시험 도우미 ${relSrc} 를 가져온다(시험과 testing.ts 만 쓴다)`,
      );
      continue;
    }
    if (path === CONTRACT) {
      // 계약 타입은 model 만, 타입으로만 가져온다.
      if (!(
        rule.contractModel &&
        where.kind === 'segment' &&
        where.segment === 'model'
      ))
        problems.push(`${label} 가 계약 타입을 직접 가져온다`);
      else if (!typeOnly)
        problems.push(`${label} 가 계약 타입을 값으로 가져온다`);
      continue;
    }
    if (CSS.test(target)) {
      const ok =
        where.kind === 'segment' &&
        where.segment === 'ui' &&
        (rule.uiAnyCss || relSlice.startsWith('ui/'));
      if (!ok) problems.push(`${label} 가 CSS 를 가져온다: ${target}`);
      continue;
    }
    if (root) {
      const ok =
        root.files === '*' ?
          path.startsWith(base + '/')
        : root.files.includes(relSlice);
      if (!ok && !root.also?.(relSrc))
        problems.push(`${label} 가 ${relSrc} 를 가져온다`);
      continue;
    }
    if (where.kind !== 'segment') continue;
    const segment = where.segment;
    if (relSlice.startsWith(`${segment}/`)) continue;
    const typeOnlyForTests = rule.testTypeOnly[segment] ?? [];
    if (test && typeOnlyForTests.includes(relSrc)) {
      if (!typeOnly)
        problems.push(
          `${label} 가 ${relSrc} 를 값으로 가져온다(import type 만 된다)`,
        );
      continue;
    }
    if (test && rule.testAlso(relSrc)) continue;
    if (segment === 'hooks' && rule.hooksTypeOnly.includes(relSlice)) {
      if (!typeOnly)
        problems.push(
          `${label} 가 ${relSrc} 를 값으로 가져온다(import type 만 된다)`,
        );
      continue;
    }
    // 자기 슬라이스의 아래 칸 표면(config 는 ui 만).
    const below =
      segment === 'config' ? [] : ORDER.slice(0, ORDER.indexOf(segment));
    const allowed = below
      .filter((lower) => rule.packages[lower])
      .map(surfaceOf);
    if (segment === 'ui' && rule.packages.config)
      allowed.push(surfaceOf('config'));
    if (allowed.includes(relSlice)) continue;
    if (rule.also[segment]?.(relSrc, part)) continue;
    problems.push(`${label} 가 ${relSrc} 를 가져온다`);
  }
  if (where.kind === 'segment' && !test) {
    const code = withoutComments(source);
    const looks =
      rule.looksIn.includes(where.segment) &&
      !rule.noLooksUnder.some((prefix) => where.inSlice.startsWith(prefix));
    if (looks) {
      const value = LOOK_VALUE.exec(code);
      if (value) problems.push(`${label} 가 모양을 품는다: ${value[0]}`);
      if (FIXED_CLASS.test(code))
        problems.push(`${label} 가 클래스 이름을 박는다`);
      const tool = LOOK_TOOL.exec(code);
      if (tool) problems.push(`${label} 가 모양 도구를 쓴다: ${tool[1]}`);
      if (where.segment === 'hooks') {
        const key = lookKey(rule.lookKeyExcept).exec(code);
        if (key) problems.push(`${label} 가 모양을 품는다: ${key[1]}`);
      }
    }
    const dom = rule.domAt?.(where.inSlice) ?? rule.dom[where.segment];
    const word = dom?.exec(code);
    if (word) problems.push(`${label} 가 DOM·통신을 쓴다: ${word[0]}`);
  }
  problems.push(...rule.extra(file, relative(src, file), source));
  return problems;
}

/** 칸 규칙을 받는 파일 하나하나의 자리(시험 줄을 가르려고). */
function rowOf(rule: SliceRule, file: string): Segment | 'root' | null {
  const where = whereIn(rule, file);
  if (!where) return null;
  if (where.kind === 'segment') return where.segment;
  if (where.kind === 'root' || where.kind === 'stray') return 'root';
  if (where.kind === 'rootTest' && rule.rootTestRule) return 'root';
  return null;
}

/** 규칙의 슬라이스 폴더들(src 기준). */
const slicesOf = (rule: SliceRule) =>
  rule.parts ?
    readdirSync(join(src, rule.dir), { withFileTypes: true })
      .filter(
        (entry) =>
          entry.isDirectory() &&
          (!rule.partFilter || rule.partFilter.test(entry.name)),
      )
      .map((entry) => `${rule.dir}/${entry.name}`)
  : [rule.dir];

const ruleOf = (dir: string) => SLICES.find((rule) => rule.dir === dir)!;
const at = (path: string) => join(src, path);
const read = (file: string) => readFileSync(file, 'utf8');

// ───────────────────────── 표와 폴더(밴드 WS2, sid:MARC-ISSUE-377) ─────────────────────────

/** 슬라이스 폴더를 표와 견주는 층(src 기준). 그 아래 폴더 하나하나가 슬라이스다. */
const SLICE_LAYERS = ['entities', 'pages', 'widgets', 'shared/ui'];
/** 표(SLICES·DOORS)의 줄 가운데 폴더를 덮는 칸만. */
type CoverRow = Pick<SliceRule & DoorRow, 'dir' | 'parts' | 'partFilter'> & {
  partDoors?: Record<string, string[]>;
};
const rowLabel = (row: CoverRow) =>
  `${row.dir}${row.partFilter ? `/${row.partFilter.source}` : ''}`;
/** 줄이 슬라이스 폴더(src 기준) 하나를 덮는가. parts 면 바로 아래 폴더 중 partFilter 에 맞는 것. */
const covers = (row: CoverRow, folder: string) => {
  if (!row.parts) return row.dir === folder;
  if (dirname(folder) !== row.dir) return false;
  const name = folder.slice(row.dir.length + 1);
  return (
    (!row.partFilter || row.partFilter.test(name)) &&
    (!row.partDoors || name in row.partDoors)
  );
};

/** SLICE_LAYERS 의 실제 슬라이스 폴더(src 기준). 없는 층은 건너뛴다. */
const sliceFolders = () =>
  SLICE_LAYERS.filter((layer) => existsSync(at(layer))).flatMap((layer) =>
    readdirSync(at(layer), { withFileTypes: true })
      .filter((entry) => entry.isDirectory())
      .map((entry) => `${layer}/${entry.name}`),
  );

/** 어느 줄도 덮지 않는 슬라이스 폴더(표에 없는 슬라이스). */
export function unknownSlices(
  folders: readonly string[],
  rows: readonly CoverRow[],
): string[] {
  return folders.filter((folder) => !rows.some((row) => covers(row, folder)));
}

/**
 * 덮는 폴더가 없는 줄(낡은 줄). SLICE_LAYERS 밖의 줄(shared/api·shared/lib·app/*)은 폴더가 있는지(exists)만 본다.
 * partDoors 의 이름도 폴더마다 있어야 한다.
 */
export function staleRows(
  folders: readonly string[],
  rows: readonly CoverRow[],
  exists: (dir: string) => boolean,
): string[] {
  return rows.flatMap((row) => {
    const inLayers = SLICE_LAYERS.some(
      (layer) => row.dir === layer || dirname(row.dir) === layer,
    );
    const alive =
      inLayers ?
        folders.some((folder) => covers(row, folder))
      : exists(row.dir);
    return [
      ...(alive ? [] : [rowLabel(row)]),
      ...Object.keys(row.partDoors ?? {})
        .filter((name) => !folders.includes(`${row.dir}/${name}`))
        .map((name) => `${row.dir}/${name}`),
    ];
  });
}

describe('구조 규칙 — 1. 층 순서', () => {
  it('src 의 모든 파일이 층 순서를 지킨다(위층만 아래층을, 같은 층의 다른 슬라이스는 안 된다). 층마다 파일이 있다', () => {
    const files = allFiles().filter((file) => placeOf(file) !== null);
    for (const layer of LAYERS)
      expect(
        files.filter((file) => {
          const place = placeOf(file);
          return place !== 'stray' && place?.layer === layer;
        }).length,
        layer,
      ).toBeGreaterThan(0);
    expect(files.flatMap((file) => layerViolations(file, read(file)))).toEqual(
      [],
    );
  });

  it('src 밖(tools·e2e)에서 pages 로는 예외 표의 줄로만 들어온다', () => {
    const outside = allFiles().filter((file) => placeOf(file) === null);
    expect(outside.length).toBeGreaterThanOrEqual(35); // [L1] 실측 38(tools·e2e)
    expect(
      outside.flatMap((file) => layerViolations(file, read(file))),
    ).toEqual([]);
  });

  it('예외 표의 줄은 저마다 실제로 쓰인다(낡은 예외를 남기지 않는다)', () => {
    const uses = (from: string, to: string) =>
      relativeImports(from, read(from)).some(({ path }) => path === to);
    for (const row of LAYER_EXCEPTIONS)
      expect(uses(at(row.from), at(row.to)), row.from).toBe(true);
    for (const row of PAGE_ENTRY_EXCEPTIONS)
      expect(
        uses(join(webRoot, row.from), join(webRoot, row.to)),
        row.from,
      ).toBe(true);
  });
});

describe('구조 규칙 — 2. 슬라이스 경계', () => {
  for (const row of DOORS)
    it(`${row.dir}${
      row.parts ?
        row.partFilter ?
          `/${row.partFilter.source.slice(1)}*`
        : '/<부품>'
      : ''
    } 에는 밖에서 공개 표면(${
      row.partDoors ?
        Object.entries(row.partDoors)
          .map(([part, doors]) => `${part}: ${doors.join('·')}`)
          .join(', ')
      : row.doors.join(', ')
    }${row.toolsDoors.join() === row.doors.join() ? '' : `, tools/ 는 ${row.toolsDoors.join(', ')} 만`})으로만 들어온다`, () => {
      const outside = allFiles().filter(
        (file) => !file.startsWith(join(src, row.dir) + '/'),
      );
      expect(outside.length).toBeGreaterThanOrEqual(200); // [L1] 실측 212~283
      let entering = 0;
      let tools = 0;
      const problems: string[] = [];
      for (const file of outside) {
        const found = sideDoors(row, file, read(file));
        entering += found.entering;
        tools += found.tools;
        problems.push(...found.problems);
      }
      expect(problems).toEqual([]);
      // 빈 검사가 아니다: 데모·다른 화면·변환 스크립트가 실제로 들어온다.
      expect(entering).toBeGreaterThanOrEqual(row.minEntering);
      expect(tools).toBeGreaterThanOrEqual(row.minTools);
    });

  it('shared/ui 의 부품 폴더와 그린워싱 화면 폴더(pages/greenwash-*)마다 공개 표면 index.ts 가 있다', () => {
    for (const [rule, min] of [
      [ruleOf('shared/ui'), 2],
      [SLICES.find((row) => row.dir === 'pages')!, 6],
    ] as const) {
      const slices = slicesOf(rule);
      expect(slices.length, rule.dir).toBeGreaterThanOrEqual(min);
      for (const slice of slices)
        expect(readdirSync(at(slice)), slice).toContain('index.ts');
    }
  });

  it('shared/lib 의 제품 파일은 시험 도우미(testing/)를 가져오지 않는다(sid:MARC-ISSUE-145)', () => {
    const products = filesUnder(at('shared/lib')).filter(
      (file) => !isTestFile(file) && !file.startsWith(at(LIB_HELPERS) + '/'),
    );
    expect(products.length).toBeGreaterThanOrEqual(2); // 실측 2(address.ts·useLoad.ts)
    expect(
      products.flatMap((file) => libHelperViolations(file, read(file))),
    ).toEqual([]);
  });
});

describe('구조 규칙 — 3. 칸 규칙', () => {
  for (const rule of SLICES) {
    const hasRoot =
      Object.keys(rule.roots).length > 0 || Boolean(rule.rootTestRule);
    const rows = [
      ...Object.keys(rule.packages),
      ...(hasRoot ? ['root'] : []),
    ] as (Segment | 'root')[];
    for (const row of rows)
      it(`${rule.dir}${rule.parts ? `/${rule.partFilter ? 'greenwash-*' : '<부품>'}` : ''} 의 ${row === 'root' ? '맨 위 파일' : `${row}/`} 은 정해진 것만 가져온다`, () => {
        const files = filesUnder(at(rule.dir)).filter(
          (file) => rowOf(rule, file) === row,
        );
        expect(files.length).toBeGreaterThan(0);
        expect(
          files.flatMap((file) =>
            violations(rule, file, read(file)).map(
              (problem) => `${relative(src, file)}: ${problem}`,
            ),
          ),
        ).toEqual([]);
      });
  }

  it('슬라이스 맨 위에는 정해 둔 파일만 있고, 폴더는 칸뿐이다', () => {
    for (const rule of SLICES) {
      const slices = slicesOf(rule);
      if (rule.parts && !rule.partFilter)
        expect(
          readdirSync(at(rule.dir), { withFileTypes: true })
            .filter((entry) => entry.isFile())
            .map((entry) => entry.name)
            .sort(),
          rule.dir,
        ).toEqual([...rule.groupFiles].sort());
      for (const slice of slices) {
        const entries = readdirSync(at(slice), { withFileTypes: true });
        const names = entries
          .filter((entry) => entry.isFile())
          .map((entry) => entry.name);
        for (const name of names)
          expect(
            [...Object.keys(rule.roots), ...rule.rootTests],
            `${slice}/${name}`,
          ).toContain(name);
        for (const entry of entries.filter((entry) => entry.isDirectory()))
          expect(
            Object.keys(rule.packages),
            `${slice}/${entry.name}/`,
          ).toContain(entry.name);
      }
    }
    // 옛 api 시험의 단언: 파일 넷이 다 있고 ui/ 는 없다.
    expect(
      readdirSync(at('shared/api'), { withFileTypes: true })
        .map((entry) => entry.name)
        .sort(),
    ).toEqual([
      'client.test.ts',
      'client.ts',
      'hooks',
      'index.ts',
      'model',
      'testing.ts',
    ]);
  });

  it('계약 타입(api-py/generated/api.d.ts)을 가져오는 파일은 shared/api 안에만 있다(src·e2e·tools 전부를 훑는다)', () => {
    const all = allFiles();
    const importers = all.filter((file) =>
      relativeImports(file, read(file)).some(({ path }) => path === CONTRACT),
    );
    // 빈 검사가 아니다: model 이 실제로 가져온다.
    expect(importers.length).toBeGreaterThan(0);
    expect(
      importers
        .filter((file) => !file.startsWith(at('shared/api') + '/'))
        .map((file) => relative(webRoot, file)),
    ).toEqual([]);
    // 경로를 다르게 적어 위의 견줌을 비켜 간 것(글자로 한 번 더).
    expect(
      all
        .filter(
          (file) =>
            !file.startsWith(at('shared/api') + '/') &&
            /from\s*["'][^"']*api-py\/generated/.test(read(file)),
        )
        .map((file) => relative(webRoot, file)),
    ).toEqual([]);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다', () => {
  const ui = ruleOf('shared/ui');
  const api = ruleOf('shared/api');
  const viewer = ruleOf('widgets/doc-viewer');
  const table = ruleOf('widgets/review-table');

  it('마크다운의 문은 shared/ui/markdown 의 ui 칸 하나다(밴드 MD1)', () => {
    const source = `import Markdown from "react-markdown"; import remarkGfm from "remark-gfm";`;
    expect(
      violations(ui, join(src, 'shared/ui/markdown/ui/X.tsx'), source),
    ).toEqual([]);
    for (const path of [
      'shared/ui/empty/ui/X.tsx',
      'shared/ui/markdown/model/X.ts',
    ])
      expect(
        violations(ui, join(src, path), source).length,
      ).toBeGreaterThanOrEqual(1);
  });

  it('층 순서: 아래층이 위층을, 같은 층의 다른 슬라이스를 가져오면 빨강', () => {
    expect(
      layerViolations(
        at('shared/ui/x/ui/a.tsx'),
        `import { ReviewTable } from "../../../../widgets/review-table/index.ts";`,
      ),
    ).toEqual([
      'shared/ui 가 widgets/review-table/index.ts 를 가져온다(shared 는 widgets 를 모른다)',
    ]);
    expect(
      layerViolations(
        at('widgets/doc-viewer/ui/a.tsx'),
        `import { ReviewTable } from "../../review-table/index.ts";`,
      ),
    ).toEqual([
      'widgets/doc-viewer 가 widgets/review-table/index.ts 를 가져온다(같은 층의 다른 슬라이스)',
    ]);
    expect(
      layerViolations(
        at('pages/demo-parts/a.tsx'),
        `import { App } from "../demo-viewer/App.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      layerViolations(
        at('entities/greenwash/ui/a.tsx'),
        `import { App } from "../../../pages/demo-viewer/App.tsx";`,
      ),
    ).toHaveLength(1);
    // 예외 표 밖의 그린워싱 → widgets 는 빨강
    expect(
      layerViolations(
        at('entities/greenwash/ui/screens/a.tsx'),
        `import { DocumentViewer } from "../../../../widgets/doc-viewer/index.ts";`,
      ),
    ).toHaveLength(1);
    // 정해진 자리 밖
    expect(layerViolations(at('helpers.ts'), `export {};`)).toHaveLength(1);
    expect(layerViolations(at('features/x/a.ts'), `export {};`)).toHaveLength(
      1,
    );
    expect(layerViolations(at('shared/a.ts'), `export {};`)).toHaveLength(1);
    // 되는 것: 위층이 아래층을, 같은 슬라이스 안, app 은 무엇이든, shared 안끼리(칸 규칙이 따로 본다)
    expect(
      layerViolations(
        at('main.tsx'),
        `import { App } from "./pages/demo-viewer/App.tsx"; import "./app/styles/app.css";`,
      ),
    ).toEqual([]);
    expect(
      layerViolations(
        at('pages/demo-table/a.tsx'),
        `import { ReviewTable } from "../../widgets/review-table/index.ts"; import { a } from "../../shared/lib/address.ts"; import { b } from "./b.ts";`,
      ),
    ).toEqual([]);
    expect(
      layerViolations(
        at('shared/ui/x/ui/a.tsx'),
        `import { Button } from "../../button/index.ts";`,
      ),
    ).toEqual([]);
    // src 밖에서 pages 로: 예외 표의 줄만
    expect(
      layerViolations(
        join(webRoot, 'e2e/x.spec.ts'),
        `import { a } from "../src/pages/demo-table/fakeRows.ts";`,
      ),
    ).toEqual([
      'e2e/x.spec.ts 가 src/pages/demo-table/fakeRows.ts 를 가져온다(pages 는 app 만 가져온다)',
    ]);
    expect(
      layerViolations(
        join(webRoot, 'e2e/review-table.spec.ts'),
        `import { a } from "../src/pages/demo-table/fakeRows.ts";`,
      ),
    ).toEqual([]);
  });

  it('슬라이스 경계: 밖에서 공개 표면을 건너뛰면 빨강(tools/ 는 화면 없는 표면만)', () => {
    const doors = (dir: string) => DOORS.find((row) => row.dir === dir)!;
    const screen = at('pages/some-screen/Page.tsx');
    const tool = join(webRoot, 'tools/x.ts');
    const problems = (row: DoorRow, file: string, source: string) =>
      sideDoors(row, file, source).problems;
    // shared/api: index.ts 만
    expect(
      problems(
        doors('shared/api'),
        screen,
        `import { createApi } from "../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      problems(
        doors('shared/api'),
        screen,
        `import { createApi } from "../../shared/api/client.ts";`,
      ),
    ).toEqual(['src/pages/some-screen/Page.tsx → src/shared/api/client.ts']);
    expect(
      problems(
        doors('shared/api'),
        screen,
        `import type { ApiFailure } from "../../shared/api/model/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      problems(
        doors('shared/api'),
        screen,
        `const { fakeFetch } = await import("../../shared/api/testing.ts");`,
      ),
    ).toHaveLength(1);
    // shared/ui: <부품>/index.ts 만(text.ts·속 파일은 안 된다)
    expect(
      problems(
        doors('shared/ui'),
        screen,
        `import { Button } from "../../shared/ui/button/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      problems(
        doors('shared/ui'),
        screen,
        `import { Button } from "../../shared/ui/button/ui/Button.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      problems(
        doors('shared/ui'),
        screen,
        `import { PARTS_TEXT } from "../../shared/ui/text.ts";`,
      ),
    ).toHaveLength(1);
    // doc-viewer: index.ts·model/index.ts·pdfjs.ts, tools 는 model/index.ts 만
    expect(
      problems(
        doors('widgets/doc-viewer'),
        screen,
        `import { D } from "../../widgets/doc-viewer/index.ts"; import { b } from "../../widgets/doc-viewer/model/index.ts"; import { openPdf } from "../../widgets/doc-viewer/pdfjs.ts";`,
      ),
    ).toEqual([]);
    expect(
      problems(
        doors('widgets/doc-viewer'),
        screen,
        `import { usePdf } from "../../widgets/doc-viewer/hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      problems(
        doors('widgets/doc-viewer'),
        tool,
        `import { D } from "../src/widgets/doc-viewer/index.ts";`,
      ),
    ).toEqual(['tools/x.ts → src/widgets/doc-viewer/index.ts']);
    expect(
      problems(
        doors('widgets/doc-viewer'),
        tool,
        `import { b } from "../src/widgets/doc-viewer/model/index.ts";`,
      ),
    ).toEqual([]);
    // review-table: index.ts 만, tools 는 model/index.ts 만
    expect(
      problems(
        doors('widgets/review-table'),
        screen,
        `import { parseTableInput } from "../../widgets/review-table/model/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      problems(
        doors('widgets/review-table'),
        tool,
        `import { R } from "../src/widgets/review-table/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      problems(
        doors('widgets/review-table'),
        tool,
        `import { parseTableInput } from "../src/widgets/review-table/model/index.ts";`,
      ),
    ).toEqual([]);
  });

  it('[S3W2a ① Q3] review-table 의 화면 없는 표면은 pages/ghg-scope3 만(앞붙음 ghg-scope3x·다른 화면은 null)', () => {
    const door = DOORS.find((row) => row.dir === 'widgets/review-table')!;
    expect([
      door.doorsFor!('src/pages/ghg-scope3/ui/emission.ts'),
      door.doorsFor!('src/pages/ghg-scope3x/ui/Card.tsx'),
      door.doorsFor!('src/pages/ghg-inventory/ui/Card.tsx'),
    ]).toEqual([['index.ts', 'model/index.ts'], null, null]);
  });

  it('[DB5 · 감독 판단 2] entities/ghg 표면은 pages/ghg-scope3 도 받는다(숫자 든 폴더) · 앞붙음 ghg-/·ghgx 는 null', () => {
    const door = DOORS.find((row) => row.dir === 'entities/ghg')!;
    expect(door.doorsFor!('src/pages/ghg-scope3/ui/ResultView.tsx')).toEqual([
      'model/index.ts',
      'api/index.ts',
      'hooks/index.ts',
      'config/text.ts',
    ]);
    expect([
      door.doorsFor!('src/pages/ghg-/x.ts'),
      door.doorsFor!('src/pages/ghgx/x.ts'),
    ]).toEqual([null, null]);
  });

  it('칸 규칙: 칸마다 허용 밖 패키지는 빨강', () => {
    // shared/ui (옛 components)
    expect(
      violations(
        ui,
        at('shared/ui/x/model/a.ts'),
        `import { useState } from "react";`,
      ),
    ).toEqual(['shared/ui/x/model 가 react 를 가져온다']);
    expect(
      violations(
        ui,
        at('shared/ui/x/model/a.ts'),
        `const z = await import("zod");`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `import { useState } from "react"; import { useReactTable } from "@tanstack/react-table";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `import { useVirtualizer } from "@tanstack/react-virtual";`,
      ),
    ).toEqual(['shared/ui/x/hooks 가 @tanstack/react-virtual 를 가져온다']);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { flexRender } from "@tanstack/react-table";`,
      ),
    ).toEqual(['shared/ui/x/ui 가 @tanstack/react-table 를 가져온다']);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { X } from "lucide-react";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { twMerge } from "tailwind-merge";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { Slot } from "@radix-ui/react-slot"; import { cva } from "class-variance-authority"; import { cn } from "@marcspon/ui/lib/utils"; import { Spinner } from "@marcspon/ui/components/spinner"; import { CloseIcon } from "@marcspon/common/generated/icons/MyIcons";`,
      ),
    ).toEqual([]);
    // 키트의 허용 밖 경로. 글자를 조립한다: 그대로 쓰면 app/guards/kit-imports.test.ts 가 이 고정물을 진짜 import 로 읽는다.
    const kitHook = ['@marcspon/ui', 'hooks', 'use-disclosure'].join('/');
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { useDisclosure } from "${kitHook}";`,
      ),
    ).toEqual([`shared/ui/x/ui 가 ${kitHook} 를 가져온다`]);
    // 테스트 파일만 vitest 를 쓸 수 있다.
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { it } from "vitest";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.test.tsx'),
        `import { it } from "vitest";`,
      ),
    ).toEqual([]);
    // 공개 표면은 패키지를 부르지 않는다.
    expect(
      violations(ui, at('shared/ui/x/index.ts'), `export * from "react";`),
    ).toHaveLength(1);
    // shared/api
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `import createClient from "openapi-react-query";`,
      ),
    ).toEqual(['shared/api/model 가 openapi-react-query 를 가져온다']);
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `import createClient from "openapi-react-query";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/client.ts'),
        `import { QueryClient } from "@tanstack/react-query";`,
      ),
    ).toHaveLength(1);
    // doc-viewer
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `import { useState } from "react";`,
      ),
    ).toEqual(['widgets/doc-viewer/model 가 react 를 가져온다']);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `import * as pdfjs from "pdfjs-dist";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `const r = require("react");`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `const r = await import("react");`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.ts'),
        `import * as pdfjs from "pdfjs-dist";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/ui/x.tsx'),
        `import * as pdfjs from "pdfjs-dist";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/pdfjs.ts'),
        `import u from "pdfjs-dist/build/pdf.worker.min.mjs?url"; import type { x } from "./hooks/index.ts";`,
      ),
    ).toEqual([]);
    // review-table
    expect(
      violations(
        table,
        at('widgets/review-table/model/x.ts'),
        `import { x } from "@tanstack/react-table";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/ui/x.tsx'),
        `import { useTable } from "@tanstack/react-table";`,
      ),
    ).toEqual(['widgets/review-table/ui 가 @tanstack/react-table 를 가져온다']);
  });

  it('칸 규칙: 허용 밖 파일(거꾸로 가는 칸, 표면 건너뛰기, 자리 밖)은 빨강', () => {
    // shared/ui
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `import { A } from "../ui/A.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `import { a } from "../model/a.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `import { a } from "../model/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        ui,
        at('shared/ui/x/model/a.ts'),
        `import { PARTS_TEXT } from "../../text.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { a } from "../model/index.ts"; import { b } from "../hooks/index.ts"; import { Button } from "../../button/index.ts"; import { PARTS_TEXT } from "../../text.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { Button } from "../../button/ui/Button.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { h } from "../hooks/useX.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { ReviewTable } from "../../../../widgets/review-table/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/ui/a.tsx'),
        `import { createApi } from "../../../api/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        ui,
        at('shared/ui/x/index.ts'),
        `export * from "../button/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(ui, at('shared/ui/x/helpers.ts'), `export const a = 1;`),
    ).toHaveLength(1);
    expect(
      violations(ui, at('shared/ui/x/lib/a.ts'), `export const a = 1;`),
    ).toHaveLength(1);
    expect(
      violations(ui, at('shared/ui/helpers.ts'), `export const a = 1;`),
    ).toHaveLength(1);
    // shared/api
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `import { x } from "../hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `import type { Api } from "../client.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `import { createApi } from "../client.ts";`,
      ),
    ).toEqual([
      'shared/api/hooks 가 shared/api/client.ts 를 값으로 가져온다(import type 만 된다)',
    ]);
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `import type { Api } from "../client.ts"; import { useQueryClient } from "@tanstack/react-query"; import { x } from "../model/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `import { x } from "../model/failure.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/client.ts'),
        `import { x } from "./hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/index.ts'),
        `export * from "./model/failure.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(api, at('shared/api/ui/a.tsx'), `export {};`),
    ).toHaveLength(1);
    // doc-viewer
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `import { x } from "../hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.ts'),
        `import { x } from "../ui/DocumentViewer.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.ts'),
        `import { x } from "../model/geometry.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.ts'),
        `import { x } from "../pdfjs.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/ui/x.tsx'),
        `import { x } from "../hooks/useDocViewer.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/ui/x.tsx'),
        `import { x } from "../model/contract.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/ui/x.tsx'),
        `import { x } from "../model/index.ts"; import { y } from "../hooks/index.ts"; import "./x.css";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/pdfjs.ts'),
        `import { x } from "./ui/DocumentViewer.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/a.test.ts'),
        `import { a } from "../model/testing.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(viewer, at('widgets/doc-viewer/lib/a.ts'), `export {};`),
    ).toHaveLength(1);
    // review-table
    expect(
      violations(
        table,
        at('widgets/review-table/model/x.ts'),
        `import { x } from "../hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/x.ts'),
        `import { x } from "../ui/ReviewTable.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/x.ts'),
        `import { x } from "../model/row.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/ui/x.tsx'),
        `import { x } from "../hooks/useReviewRows.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/ui/x.tsx'),
        `import { x } from "../model/index.ts"; import "./x.css";`,
      ),
    ).toEqual([]);
    // 시험만 shared/lib/testing 의 도우미를 쓴다
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/a.test.ts'),
        `import { box } from "../../../shared/lib/testing/layout.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/a.ts'),
        `import { box } from "../../../shared/lib/testing/layout.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('칸 규칙: model 은 DOM·통신을, model·hooks 는 CSS 를 모른다', () => {
    expect(
      violations(
        ui,
        at('shared/ui/x/model/a.ts'),
        `export const w = window.innerWidth;`,
      ),
    ).toEqual(['shared/ui/x/model 가 DOM·통신을 쓴다: window']);
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `export const load = () => fetch("/x");`,
      ),
    ).toEqual(['shared/api/model 가 DOM·통신을 쓴다: fetch']);
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `export const ok = (r: Response) => r.ok;`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `export const s = sessionStorage.getItem("x");`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `export const base = document.baseURI;`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `export const isCanvas = (x: unknown) => x instanceof HTMLCanvasElement;`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `export const q = location.search;`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `export const s = getComputedStyle(el);`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/model/x.ts'),
        `export const load = () => fetch("/x");`,
      ),
    ).toHaveLength(1);
    // 주석 속 낱말, 시험 파일은 된다
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `// fetch 는 주석에서는 된다\nexport const a = 1;`,
      ),
    ).toEqual([]);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.test.ts'),
        `document.body;`,
      ),
    ).toEqual([]);
    // CSS: model·hooks·맨 위 파일은 안 된다(꼬리가 붙어도), ui 는 된다
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.tsx'),
        `import "./x.css";`,
      ),
    ).toEqual(['widgets/doc-viewer/hooks 가 CSS 를 가져온다: ./x.css']);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/x.tsx'),
        `import "../ui/viewer.css";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/x.tsx'),
        `import css from "./x.css?inline";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/hooks/x.tsx'),
        `import "../ui/review-table.css";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(ui, at('shared/ui/x/hooks/a.ts'), `import "./a.css";`),
    ).toHaveLength(1);
  });

  it('칸 규칙: model·hooks 는 모양을 모른다(마크업과 자리는 된다)', () => {
    const hooks = (rule: SliceRule, dir: string) => (source: string) =>
      violations(rule, at(`${dir}/hooks/x.tsx`), source);
    const uiHooks = hooks(ui, 'shared/ui/x');
    const viewerHooks = hooks(viewer, 'widgets/doc-viewer');
    const tableHooks = hooks(table, 'widgets/review-table');
    const uiModel = (source: string) =>
      violations(ui, at('shared/ui/x/model/a.ts'), source);
    // 색 값
    expect(uiHooks(`const line = "#D1D5D9";`)).toEqual([
      'shared/ui/x/hooks 가 모양을 품는다: #D1D5D9',
    ]);
    expect(uiModel(`const tone = "rgb(0 0 0 / 20%)";`)).toHaveLength(1);
    expect(viewerHooks(`const tone = "#2563eb";`)).toEqual([
      'widgets/doc-viewer/hooks 가 모양을 품는다: #2563eb',
    ]);
    expect(viewerHooks(`const tone = "oklch(60% 0.2 30)";`)).toHaveLength(1);
    expect(viewerHooks(`context.fillStyle = tone;`)).toHaveLength(1);
    expect(tableHooks(`const tone = "rgb(0 0 0 / 30%)";`)).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/model/x.ts'),
        `const tone = "#0969da";`,
      ),
    ).toHaveLength(1);
    // doc-viewer 의 model 은 강조 색 표를 품는다(modelLooks: false)
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `const tone = "#2563eb";`,
      ),
    ).toEqual([]);
    // 박은 className
    expect(uiHooks(`<td className="border-b" />`)).toEqual([
      'shared/ui/x/hooks 가 클래스 이름을 박는다',
    ]);
    expect(uiHooks(`<td className={'px-4'} />`)).toHaveLength(1);
    expect(uiHooks(`<td className={\`px-4\`} />`)).toHaveLength(1);
    expect(viewerHooks(`<div className="absolute" />`)).toEqual([
      'widgets/doc-viewer/hooks 가 클래스 이름을 박는다',
    ]);
    // 모양 도구(패키지 규칙과 따로)
    expect(
      uiHooks(`import { cva } from "class-variance-authority";`),
    ).toContain(
      'shared/ui/x/hooks 가 모양 도구를 쓴다: class-variance-authority',
    );
    expect(uiHooks(`import { cn } from "@marcspon/ui/lib/utils";`)).toContain(
      'shared/ui/x/hooks 가 모양 도구를 쓴다: @marcspon/ui/lib/utils',
    );
    // style 의 모양 키
    expect(viewerHooks(`<div style={{ background: tone }} />`)).toEqual([
      'widgets/doc-viewer/hooks 가 모양을 품는다: background',
    ]);
    for (const source of [
      `<div style={{ backgroundColor: tone }} />`,
      `<div style={{ color: look.color }} />`,
      `<div style={{ outline: line }} />`,
      `<div style={{ borderRadius: 4 }} />`,
      `<div style={{ boxShadow: shadow }} />`,
      `<div style={{ fontWeight: 600 }} />`,
      `<div style={{ opacity: 0.5 }} />`,
      `<div style={{ "background": tone, "fontWeight": 700 }} />`,
      `<div style={{ mixBlendMode: "multiply" }} />`,
      `<div style={{ WebkitTextFillColor: tone }} />`,
      `<div style={{ filter: blur }} />`,
    ])
      expect(viewerHooks(source), source).toHaveLength(1);
    expect(tableHooks(`<div style={{ borderBottom: line }} />`)).toHaveLength(
      1,
    );
    expect(uiHooks(`<div style={{ opacity: 0.5 }} />`)).toHaveLength(1);
    // review-table 만 filter 를 봐준다(걸러 보기의 이름)
    expect(
      tableHooks(
        `export interface T { filter: RowFilter; setFilter(patch: Partial<RowFilter>): void }`,
      ),
    ).toEqual([]);
    // 못 잡는 것(머리말에 적은 한계): 이름 붙은 색, 조립한 키, 다른 파일에서 건너온 값. review-table 의 CSS filter.
    expect(
      viewerHooks(
        `const tone = "red"; const key = "back" + "ground"; <div style={{ [key]: tone }} />`,
      ),
    ).toEqual([]);
    expect(tableHooks(`<div style={{ filter: blur }} />`)).toEqual([]);
    // 되는 것: 마크업, 자리와 크기, 쓰는 쪽이 준 것을 흘려보내기, 주석 속 낱말, 타입 필드
    expect(
      viewerHooks(
        `<div className={classNames?.layer} style={{ position: "absolute", inset: 0, boxSizing: "border-box", pointerEvents: "none", overflow: "auto", display: "block", margin: "0 auto" }} />`,
      ),
    ).toEqual([]);
    expect(
      viewerHooks(
        `<button className={look?.className} style={{ ...look?.style, position: "absolute", left, top, width, height }} />`,
      ),
    ).toEqual([]);
    expect(
      tableHooks(
        `<div className={classNames?.scroller} role="grid" tabIndex={0} style={{ overflowY: "auto", height: total, position: "relative", transform: move }} />`,
      ),
    ).toEqual([]);
    expect(
      tableHooks(
        `<div ref={measureRef} role="row" className={className} data-index={index} aria-selected={selected} />`,
      ),
    ).toEqual([]);
    expect(
      uiHooks(
        `// 색(#D1D5D9)과 테두리(border: 1px)는 ui 가 입힌다\n<td className={className} aria-sort={sort} data-align="right" />`,
      ),
    ).toEqual([]);
    expect(
      viewerHooks(`export interface P { color: string; width: number }`),
    ).toEqual([]);
    // 같은 글자라도 ui 에서는 된다
    expect(
      violations(ui, at('shared/ui/x/ui/a.tsx'), `<td className="border-b" />`),
    ).toEqual([]);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/ui/x.tsx'),
        `<i style={{ background: look.color }} />`,
      ),
    ).toEqual([]);
    expect(
      violations(
        table,
        at('widgets/review-table/ui/x.tsx'),
        `<i style={{ background: tone }} />`,
      ),
    ).toEqual([]);
  });

  it('주석 지우개는 문자열 속의 // 와 /* 를 주석으로 읽지 않는다', () => {
    // (가) 주소 문자열 뒤 같은 줄의 금지 import
    expect(
      violations(
        ui,
        at('shared/ui/x/model/a.ts'),
        `const u = "http://x"; import { useState } from "react";`,
      ),
    ).toEqual(['shared/ui/x/model 가 react 를 가져온다']);
    // (나) '/*' 문자열 뒤 줄의 색 값
    expect(
      violations(
        ui,
        at('shared/ui/x/hooks/a.ts'),
        `const wild = '/*';\nconst line = '#D1D5D9';\n/** 설명 */\nexport const x = 1;`,
      ),
    ).toEqual(['shared/ui/x/hooks 가 모양을 품는다: #D1D5D9']);
    // 진짜 주석은 여전히 지운다(줄 수는 지킨다)
    expect(withoutComments(`a // b\n/* c\nd */e 'f//g' "h/*i"`)).toBe(
      `a \n\ne 'f//g' "h/*i"`,
    );
  });

  it('shared/api 만의 규칙: 계약 타입은 model 이 타입으로만, 패칭 기본값은 품지 않는다', () => {
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `import { paths } from "../../../../../api-py/generated/api.d.ts";`,
      ),
    ).toEqual(['shared/api/model 가 계약 타입을 값으로 가져온다']);
    expect(
      violations(
        api,
        at('shared/api/model/x.ts'),
        `import type { paths } from "../../../../../api-py/generated/api.d.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `import type { paths } from "../../../../../api-py/generated/api.d.ts";`,
      ),
    ).toEqual(['shared/api/hooks 가 계약 타입을 직접 가져온다']);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/x.ts'),
        `import type { paths } from "../../../../../api-py/generated/api.d.ts";`,
      ),
    ).toEqual(['widgets/doc-viewer/model 가 계약 타입을 직접 가져온다']);
    const client = (source: string) =>
      violations(api, at('shared/api/client.ts'), source);
    expect(client(`export const queryClient = new QueryClient();`)).toEqual([
      'shared/api/client.ts 가 패칭 기본값을 품는다: new QueryClient',
    ]);
    expect(client(`export const defaults = { retry: false };`)).toHaveLength(1);
    expect(client(`export const defaults = { staleTime: 1000 };`)).toHaveLength(
      1,
    );
    expect(
      violations(
        api,
        at('shared/api/hooks/x.ts'),
        `export const defaults = { gcTime: 0 };`,
      ),
    ).toHaveLength(1);
    // doc-viewer 만의 규칙: hooks 의 공개 표면은 ZOOM_STEPS 를 내보내지 않는다
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/hooks/index.ts'),
        `export { ZOOM_STEPS } from "./zoom.ts";`,
      ),
    ).toHaveLength(1);
    // import 는 원문에서도 찾는다: 주석 지운 글에만 기대지 않는다(옛 doc-viewer·review-table·api 의 방식)
    expect(
      importsOf(`// import { x } from "./y.ts";`).map((i) => i.target),
    ).toEqual(['./y.ts']);
  });

  it('같은 칸의 제품 파일이 시험 도우미 testing.ts 를 가져오면 빨강, 시험·도우미는 된다(sid:MARC-ISSUE-128)', () => {
    const gw = ruleOf('entities/greenwash');
    const mockTesting = `import { fakeStore } from "./testing.ts";`;
    expect(
      violations(gw, at(ENTITY + 'api/mock/index.ts'), mockTesting),
    ).toEqual([
      'entities/greenwash/api 가 시험 도우미 entities/greenwash/api/mock/testing.ts 를 가져온다(시험과 testing.ts 만 쓴다)',
    ]);
    expect(
      violations(gw, at(ENTITY + 'api/mock/mockStore.ts'), mockTesting),
    ).toHaveLength(1);
    expect(
      violations(
        table,
        at('widgets/review-table/model/row.ts'),
        `import { makeRow } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
    // 확장자 없는 꼴도 이 규칙의 글로 빨강
    expect(
      violations(
        table,
        at('widgets/review-table/model/row.ts'),
        `import './testing';`,
      ),
    ).toEqual([
      'widgets/review-table/model 가 시험 도우미 widgets/review-table/model/testing 를 가져온다(시험과 testing.ts 만 쓴다)',
    ]);
    // 맨 위 파일(shared/api/client.ts)도
    expect(
      violations(
        api,
        at('shared/api/client.ts'),
        `import { fakeFetch } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
    // 시험과 도우미 자신은 된다
    expect(
      violations(
        table,
        at('widgets/review-table/model/row.test.ts'),
        `import { makeRow } from "./testing.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(gw, at(ENTITY + 'api/mock/a.test.ts'), mockTesting),
    ).toEqual([]);
    expect(
      violations(
        viewer,
        at('widgets/doc-viewer/model/testing.ts'),
        `import { a } from "./testing.ts";`,
      ),
    ).toEqual([]);
  });

  it('shared/lib 의 제품 파일이 시험 도우미 testing/ 를 가져오면 빨강, 시험·도우미는 된다(sid:MARC-ISSUE-145)', () => {
    const layout = `import { box } from "./testing/layout.ts";`;
    expect(libHelperViolations(at('shared/lib/useLoad.ts'), layout)).toEqual([
      'shared/lib/useLoad.ts 가 시험 도우미 shared/lib/testing/layout.ts 를 가져온다(시험과 testing/ 만 쓴다)',
    ]);
    expect(
      libHelperViolations(at('shared/lib/address.ts'), `import './testing';`),
    ).toEqual([
      'shared/lib/address.ts 가 시험 도우미 shared/lib/testing 를 가져온다(시험과 testing/ 만 쓴다)',
    ]);
    // 시험과 도우미 자신은 된다. shared/lib 밖은 문(DOORS)이 본다
    expect(
      libHelperViolations(at('shared/lib/useLoad.test.tsx'), layout),
    ).toEqual([]);
    expect(
      libHelperViolations(
        at('shared/lib/testing/other.ts'),
        `import { box } from "./layout.ts";`,
      ),
    ).toEqual([]);
    expect(
      libHelperViolations(
        at('pages/demo-table/TablePage.tsx'),
        `import { box } from "../../shared/lib/testing/layout.ts";`,
      ),
    ).toEqual([]);
  });
});

describe('구조 규칙 — 표와 폴더(밴드 WS2, sid:MARC-ISSUE-377)', () => {
  const ROWS = [...SLICES, ...DOORS];
  it('entities·pages·widgets·shared/ui 의 슬라이스 폴더는 모두 표(SLICES·DOORS)의 줄이 덮는다(모르는 슬라이스 0)', () => {
    const folders = sliceFolders();
    expect(folders.length).toBeGreaterThanOrEqual(50); // 실측 57(WS2 BASE c547dd88 — entities 10·pages 25·widgets 2·shared/ui 20)
    expect(unknownSlices(folders, ROWS)).toEqual([]);
    // 양성 대조: 표에 없는 폴더는 그 이름으로 잡힌다(pages 는 앞머리, demo-* 는 partDoors 이름까지).
    expect(
      unknownSlices(
        [
          'entities/zz-fake',
          'pages/zz-fake',
          'pages/demo-zz',
          'widgets/zz-fake',
          'pages/greenwash-zz',
          'shared/ui/zz-fake',
        ],
        ROWS,
      ),
    ).toEqual([
      'entities/zz-fake',
      'pages/zz-fake',
      'pages/demo-zz',
      'widgets/zz-fake',
    ]);
  });

  it('표(SLICES·DOORS)의 줄은 저마다 실제 폴더를 덮는다(낡은 줄 0)', () => {
    const exists = (dir: string) => existsSync(at(dir));
    expect(staleRows(sliceFolders(), ROWS, exists)).toEqual([]);
    // 양성 대조: 폴더 없는 줄·맞는 폴더 없는 앞머리·없는 partDoors 이름·층 밖의 없는 폴더.
    expect(
      staleRows(
        ['entities/account', 'pages/demo-api'],
        [
          { dir: 'entities/account' },
          { dir: 'entities/zz-gone' },
          { dir: 'pages', parts: true, partFilter: /^zz-/ },
          {
            dir: 'pages',
            parts: true,
            partFilter: /^demo-/,
            partDoors: { 'demo-api': [], 'demo-zz': [] },
          },
          { dir: 'app/zz-gone' },
          { dir: 'shared/api' },
        ],
        exists,
      ),
    ).toEqual([
      'entities/zz-gone',
      'pages/^zz-',
      'pages/demo-zz',
      'app/zz-gone',
    ]);
  });
});

describe('구조 규칙 — 모듈 메뉴 한 자리(밴드 DV2a ② H3 ⓗ)', () => {
  const ROUTES = [
    'app/greenwash/GreenwashRoutes.tsx',
    'app/translation/TranslationRoutes.tsx',
    'app/dataverify/DataverifyRoutes.tsx',
    // [IRW1 ② H3 ⓗ]
    'app/materiality/MaterialityRoutes.tsx',
    // [W12-0a ② H4]
    'app/ghg/GhgRoutes.tsx',
    // [RPW1 ① A4]
    'app/drafting/DraftingRoutes.tsx',
  ];
  it('*Routes.tsx 셋에 MENU 사본(AppShellMenuItem[] = [)이 없고 셋 다 app/shell/moduleMenu.tsx 를 가져온다', () => {
    for (const rel of ROUTES) {
      const source = read(at(rel));
      expect(
        /AppShellMenuItem\[\]\s*=\s*\[/.test(withoutComments(source)),
        rel,
      ).toBe(false);
      expect(
        relativeImports(at(rel), source).some(
          ({ path }) => path === at(MODULE_MENU),
        ),
        rel,
      ).toBe(true);
    }
    // 양성 대조: 무늬는 사본 한 줄을 잡는다.
    expect(
      /AppShellMenuItem\[\]\s*=\s*\[/.test(
        'const MENU: readonly AppShellMenuItem[] = [',
      ),
    ).toBe(true);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 그린워싱(옛 greenwash/layers.test.ts)', () => {
  const gw = ruleOf('entities/greenwash');
  const page = SLICES.find((row) => row.dir === 'pages')!;
  const app = ruleOf('app/greenwash');
  const e = (path: string) => at(ENTITY + path);

  it('칸마다 허용 밖 패키지는 빨강(zod 는 api/contract/ 만, radix 는 shared/ui 부품을 거친다)', () => {
    expect(
      violations(gw, e('model/a.ts'), `import { useState } from "react";`),
    ).toEqual(['entities/greenwash/model 가 react 를 가져온다']);
    expect(
      violations(gw, e('model/a.ts'), `const z = await import("zod");`),
    ).toHaveLength(1);
    expect(
      violations(gw, e('hooks/a.ts'), `import { useState } from "react";`),
    ).toEqual([]);
    expect(
      violations(
        gw,
        e('hooks/a.ts'),
        `import { useReactTable } from "@tanstack/react-table";`,
      ),
    ).toEqual([
      'entities/greenwash/hooks 가 @tanstack/react-table 를 가져온다',
    ]);
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { cva } from "class-variance-authority"; import { cn } from "@marcspon/ui/lib/utils"; import { Badge } from "@marcspon/ui/components/badge"; import { LockIcon } from "@marcspon/common/generated/icons/MyIcons"; import { createPortal } from "react-dom";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { Slot } from "@radix-ui/react-slot";`,
      ),
    ).toEqual(['entities/greenwash/ui 가 @radix-ui/react-slot 를 가져온다']);
    expect(
      violations(gw, e('ui/a.tsx'), `import { z } from "zod";`),
    ).toHaveLength(1);
    expect(
      violations(gw, e('ui/a.tsx'), `import { it } from "vitest";`),
    ).toHaveLength(1);
    expect(
      violations(gw, e('ui/a.test.tsx'), `import { it } from "vitest";`),
    ).toEqual([]);
    // zod 는 api/contract/ 자리만(밴드 FW2 ①)
    expect(
      violations(gw, e('api/contract/a.ts'), `import { z } from "zod";`),
    ).toEqual([]);
    expect(violations(gw, e('api/a.ts'), `import { z } from "zod";`)).toEqual([
      'entities/greenwash/api 가 zod 를 가져온다',
    ]);
    expect(
      violations(gw, e('api/contractual/a.ts'), `import { z } from "zod";`),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('api/contract/a.ts'),
        `import { useState } from "react";`,
      ),
    ).toEqual(['entities/greenwash/api 가 react 를 가져온다']);
    // 계약 시험은 node 로 예시 파일을 읽는다
    expect(
      violations(
        gw,
        e('api/contract/a.test.ts'),
        `import { readFileSync } from "node:fs"; import { z } from "zod";`,
      ),
    ).toEqual([]);
    // 목 저장소는 패키지를 쓰지 않는다
    expect(
      violations(gw, e('api/mock/a.ts'), `import { useState } from "react";`),
    ).toEqual(['entities/greenwash/api 가 react 를 가져온다']);
    // 화면 폴더의 칸
    expect(
      violations(
        page,
        at('pages/greenwash-list/model/a.ts'),
        `import { useState } from "react";`,
      ),
    ).toEqual(['pages/greenwash-list/model 가 react 를 가져온다']);
    expect(
      violations(
        page,
        at('pages/greenwash-list/ui/a.tsx'),
        `import { Slot } from "@radix-ui/react-slot";`,
      ),
    ).toHaveLength(1);
  });

  it('칸 방향과 표면: 허용 밖 파일은 빨강', () => {
    // [WC1 ①] model 의 시험만 shared/api 의 표면을 타입으로만 가져온다
    expect(
      violations(
        gw,
        e('model/a.test.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        gw,
        e('model/a.test.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/greenwash/model 가 shared/api/index.ts 를 값으로 가져온다(import type 만 된다)',
    ]);
    expect(
      violations(
        gw,
        e('model/a.test.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts"; const m = await import("../../../shared/api/index.ts");`,
      ),
    ).toContain(
      'entities/greenwash/model 가 shared/api/index.ts 를 값으로 가져온다(import type 만 된다)',
    );
    expect(
      violations(
        gw,
        e('model/a.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual(['entities/greenwash/model 가 shared/api/index.ts 를 가져온다']);
    expect(
      violations(
        gw,
        e('hooks/a.test.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toHaveLength(1);
    // [B3] shared/ui/text.ts 는 그린워싱 어느 칸도 가져오지 않는다
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { PARTS_TEXT } from "../../../shared/ui/text.ts";`,
      ),
    ).toEqual(['entities/greenwash/ui 가 shared/ui/text.ts 를 가져온다']);
    expect(
      violations(
        page,
        at('pages/greenwash-list/ui/a.tsx'),
        `import { PARTS_TEXT } from "../../../shared/ui/text.ts";`,
      ),
    ).toHaveLength(1);
    // ui: 자기 아래 칸 표면, shared/ui 부품 표면, config/text.ts, 같은 ui 안의 파일은 된다
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { a } from "../model/index.ts"; import { s } from "../api/index.ts"; import { b } from "../hooks/index.ts"; import { Button } from "../../../shared/ui/button/index.ts"; import { GW_TEXT } from "../config/text.ts"; import { R } from "./RiskBadge.tsx";`,
      ),
    ).toEqual([]);
    // ui: shared/ui 부품의 속 파일, 자기 model 의 속 파일, 문서 뷰어는 안 된다
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { Button } from "../../../shared/ui/button/ui/Button.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { a } from "../model/pageRange.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('ui/a.tsx'),
        `import { Viewer } from "../../../widgets/doc-viewer/index.ts";`,
      ),
    ).toHaveLength(1);
    // hooks: 아래 칸(model·api) 표면만. ui·config·shared/ui·문서 뷰어는 안 된다(② 감독 결정: 문서 뷰어는 화면이 직접 가져온다)
    expect(
      violations(
        gw,
        e('hooks/a.ts'),
        `import { a } from "../model/index.ts"; import type { S } from "../api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(gw, e('hooks/a.ts'), `import { A } from "../ui/index.ts";`),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('hooks/a.ts'),
        `import { GW_TEXT } from "../config/text.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('hooks/a.ts'),
        `import { B } from "../../../shared/ui/button/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('hooks/a.ts'),
        `import { usePdf } from "../../../widgets/doc-viewer/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      layerViolations(
        e('hooks/index.ts'),
        `export { usePdf } from "../../../widgets/doc-viewer/index.ts";`,
      ),
    ).toEqual([
      'entities/greenwash 가 widgets/doc-viewer/index.ts 를 가져온다(entities 는 widgets 를 모른다)',
    ]);
    // model: 바깥 파일 없음(config 도)
    expect(
      violations(
        gw,
        e('model/a.ts'),
        `import { GW_TEXT } from "../config/text.ts";`,
      ),
    ).toHaveLength(1);
    // api: model 표면만. mock 은 같은 api 안의 store.ts 를 쓴다
    expect(
      violations(
        gw,
        e('api/mock/a.ts'),
        `import { totalPages } from "../../model/index.ts"; import type { GreenwashStore } from "../store.ts"; import { x } from "./b.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        gw,
        e('api/mock/a.ts'),
        `import { a } from "../../model/pageRange.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('api/mock/a.ts'),
        `import { A } from "../../ui/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('api/mock/a.ts'),
        `import { GW_TEXT } from "../../config/text.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        gw,
        e('api/mock/a.ts'),
        `import { u } from "../../hooks/index.ts";`,
      ),
    ).toHaveLength(1);
    // config 는 아무것도 가져오지 않는다. 경로를 조립한다: 그대로 쓰면 이 파일이 고정물을 진짜 import 로 읽는 일이 없게(FIXTURE_CARRIERS 와 같은 뜻)
    const partsText = ['..', '..', '..', 'shared', 'ui', 'text.ts'].join('/');
    expect(
      violations(
        gw,
        e('config/text.ts'),
        `import { PARTS_TEXT } from "${partsText}";`,
      ),
    ).toContain(
      'entities/greenwash/config/text.ts 가 ../../../shared/ui/text.ts 를 가져온다(문구 표는 아무것도 가져오지 않는다)',
    );
    // 화면 폴더: 아래 칸·entities 표면·문서 뷰어 표면은 되고, pdfjs.ts·다른 화면·entities 속 파일은 안 된다
    const screen = (source: string) =>
      violations(page, at('pages/greenwash-review/ui/a.tsx'), source);
    expect(
      screen(
        `import { a } from "../model/index.ts"; import { h } from "../hooks/index.ts"; import { m } from "../../../entities/greenwash/model/index.ts"; import { R } from "../../../entities/greenwash/ui/index.ts"; import { GW_TEXT } from "../../../entities/greenwash/config/text.ts"; import { PageCanvas } from "../../../widgets/doc-viewer/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      screen(`import { openPdf } from "../../../widgets/doc-viewer/pdfjs.ts";`),
    ).toEqual([
      'pages/greenwash-review/ui 가 widgets/doc-viewer/pdfjs.ts 를 가져온다',
    ]);
    expect(
      screen(`import { s } from "../../../entities/greenwash/api/store.ts";`),
    ).toHaveLength(1);
    expect(
      screen(
        `import { s } from "../../../entities/greenwash/api/mock/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      screen(`import { h } from "../hooks/useDocumentPdf.ts";`),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/greenwash-review/model/a.ts'),
        `import { s } from "../../../entities/greenwash/api/index.ts";`,
      ),
    ).toHaveLength(1);
    // 정해진 자리 밖의 파일(entities 맨 위의 파일, 칸 아닌 폴더, 화면 맨 위의 다른 파일)
    expect(violations(gw, e('helpers.ts'), `export const a = 1;`)).toHaveLength(
      1,
    );
    expect(violations(gw, e('lib/a.ts'), `export const a = 1;`)).toHaveLength(
      1,
    );
    expect(violations(gw, e('other.test.ts'), `export {};`)).toHaveLength(1);
    expect(
      violations(page, at('pages/greenwash-list/helpers.ts'), `export {};`),
    ).toHaveLength(1);
    expect(
      violations(app, at('app/greenwash/other.ts'), `export {};`),
    ).toHaveLength(1);
  });

  it('model·api·hooks 는 모양을, model 은 DOM 을, hooks·api 는 전역 DOM 을, 목 저장소는 DOM·location 을 모른다', () => {
    const hooks = (source: string) => violations(gw, e('hooks/a.tsx'), source);
    const model = (source: string) => violations(gw, e('model/a.ts'), source);
    expect(hooks(`const red = "#A72027";`)).toEqual([
      'entities/greenwash/hooks 가 모양을 품는다: #A72027',
    ]);
    expect(model(`const tone = "rgb(0 0 0 / 20%)";`)).toHaveLength(1);
    expect(
      violations(gw, e('api/store.ts'), `const tone = "#A72027";`),
    ).toHaveLength(1);
    expect(hooks(`<span className="bg-support-error-subtle" />`)).toEqual([
      'entities/greenwash/hooks 가 클래스 이름을 박는다',
    ]);
    expect(hooks(`import { cn } from "@marcspon/ui/lib/utils";`)).toContain(
      'entities/greenwash/hooks 가 모양 도구를 쓴다: @marcspon/ui/lib/utils',
    );
    expect(
      violations(
        page,
        at('pages/greenwash-list/hooks/a.ts'),
        `const tone = "#A72027";`,
      ),
    ).toHaveLength(1);
    expect(model(`export const w = window.innerWidth;`)).toEqual([
      'entities/greenwash/model 가 DOM·통신을 쓴다: window',
    ]);
    // 주석 속 값과 흘려보낸 className 은 된다. 문자열 속 '//' 뒤의 import 는 잡는다
    expect(
      hooks(`// 색(#A72027)은 ui 가 입힌다\n<span className={className} />`),
    ).toEqual([]);
    expect(
      model(`const u = "http://x"; import { useState } from "react";`),
    ).toEqual(['entities/greenwash/model 가 react 를 가져온다']);
    // 같은 글자라도 ui 에서는 된다
    expect(violations(gw, e('ui/a.tsx'), `<span className="bg-x" />`)).toEqual(
      [],
    );
    // hooks(그리고 api·화면 hooks)는 전역 DOM 을 쓰지 않는다. 칸 이름 document 는 된다(밴드 FW2 ⓪ [B2])
    expect(hooks(`const x = { document: a };`)).toEqual([]);
    expect(hooks(`return { document: uploaded };`)).toEqual([]);
    expect(hooks(`const b = document.body;`)).toEqual([
      'entities/greenwash/hooks 가 DOM·통신을 쓴다: document.',
    ]);
    expect(hooks(`const w = window.innerWidth;`)).toHaveLength(1);
    expect(hooks(`await fetch("/runs");`)).toHaveLength(1);
    // history 도 document 와 같은 꼴 — 메서드·칸 이름·경로 글자는 되고 전역 history. 만 잡는다(밴드 W12-1a)
    expect(hooks(`history(rowId) {}`)).toEqual([]);
    expect(hooks(`const x = { history: a };`)).toEqual([]);
    expect(hooks(`"/rows/{row_id}/history"`)).toEqual([]);
    expect(hooks(`history.back();`)).toHaveLength(1);
    expect(hooks(`const n = history .length;`)).toHaveLength(1);
    expect(hooks(`history?.back();`)).toHaveLength(1);
    expect(hooks(`history['x'];`)).toHaveLength(1);
    expect(hooks(`// window 는 ui 가 본다\nexport {};`)).toEqual([]);
    expect(violations(gw, e('hooks/a.test.ts'), `document.body;`)).toEqual([]);
    expect(
      violations(gw, e('api/store.ts'), `const w = window.innerWidth;`),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/greenwash-review/hooks/a.ts'),
        `const b = document.body;`,
      ),
    ).toHaveLength(1);
    // 목 저장소: DOM·location·history 를 모른다. 모양 검사는 하지 않는다(옛 mock 과 같다)
    const mock = (source: string) => violations(gw, e('api/mock/a.ts'), source);
    expect(mock(`const q = location.search;`)).toEqual([
      'entities/greenwash/api 가 DOM·통신을 쓴다: location',
    ]);
    expect(mock(`history.replaceState(null, "", "?x");`)).toHaveLength(1);
    expect(mock(`const d = { document: a };`)).toHaveLength(1);
    expect(
      mock(`// location 은 GreenwashRoutes 가 읽는다\nexport {};`),
    ).toEqual([]);
  });

  it('api·hooks 의 공개 표면은 zod 스키마 값과 export * 를 내보내지 않는다, shared/ui 부품 표면은 PARTS_TEXT 를 다시 내보내지 않는다', () => {
    expect(
      violations(
        gw,
        e('api/index.ts'),
        `export { parseResult, resultSchema } from './contract/index.ts';`,
      ),
    ).toEqual(['entities/greenwash/api/index.ts 가 zod 스키마 값을 내보낸다']);
    expect(
      violations(
        gw,
        e('api/index.ts'),
        `export { parseResult, parseReview } from './contract/index.ts';`,
      ),
    ).toEqual([]);
    expect(
      violations(gw, e('api/index.ts'), `export * from './contract/index.ts';`),
    ).toEqual(['entities/greenwash/api/index.ts 가 export * 로 내보낸다']);
    expect(
      violations(gw, e('hooks/index.ts'), `export * from './useResult.ts';`),
    ).toHaveLength(1);
    expect(reexportsPartsText(`export { PARTS_TEXT } from './ui/A.tsx';`)).toBe(
      true,
    );
    expect(
      reexportsPartsText(
        `export { PARTS_TEXT as T, Button } from './ui/B.tsx';`,
      ),
    ).toBe(true);
    expect(
      reexportsPartsText(
        `// PARTS_TEXT 는 내보내지 않는다\nexport { Button } from './ui/B.tsx';`,
      ),
    ).toBe(false);
    expect(
      violations(
        ruleOf('shared/ui'),
        at('shared/ui/x/index.ts'),
        `export { PARTS_TEXT } from '../text.ts';`,
      ),
    ).toContain('shared/ui/x/index.ts 가 PARTS_TEXT 를 다시 내보낸다');
    // 실제 파일: 문구 표는 아무것도 가져오지 않고, 목 저장소 자리에 파일이 있다
    expect(importsOf(read(e('config/text.ts')))).toEqual([]);
    expect(filesUnder(e('api/mock')).length).toBeGreaterThan(0);
  });

  it('app/greenwash 의 상한(pdfjs.ts·목 저장소 표면은 GreenwashRoutes 만 [R8], runtime.ts 는 타입 자리)과 그린워싱 입구', () => {
    const routes = (source: string) =>
      violations(app, at('app/greenwash/GreenwashRoutes.tsx'), source);
    expect(
      routes(
        `import { Outlet, getRouteApi } from "@tanstack/react-router"; import { useState } from "react"; import { openPdf } from "../../widgets/doc-viewer/pdfjs.ts"; import { createMockStore } from "../../entities/greenwash/api/mock/index.ts"; import { ListScreen } from "../../pages/greenwash-list/index.ts"; import { GW_TEXT } from "../../entities/greenwash/config/text.ts"; import { AppShell } from "../../shared/ui/app-shell/index.ts"; import type { GreenwashRuntime } from "./runtime.ts";`,
      ),
    ).toEqual([]);
    expect(routes(`import { createRoot } from "react-dom/client";`)).toEqual([
      'app/greenwash/GreenwashRoutes.tsx 가 react-dom/client 를 가져온다',
    ]);
    expect(
      routes(`import { useQuery } from "@tanstack/react-query";`),
    ).toHaveLength(1);
    expect(
      routes(
        `import { s } from "../../entities/greenwash/api/mock/mockStore.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      routes(
        `import { L } from "../../pages/greenwash-list/ui/ListScreen.tsx";`,
      ),
    ).toHaveLength(1);
    expect(routes(`import { r } from "../router.tsx";`)).toHaveLength(1);
    // runtime.ts: 타입 자리 — 패키지 없음, entities api 표면과 문서 뷰어 표면만
    const runtime = (source: string) =>
      violations(app, at('app/greenwash/runtime.ts'), source);
    expect(
      runtime(
        `import type { GreenwashStore } from "../../entities/greenwash/api/index.ts"; import type { OpenPdf } from "../../widgets/doc-viewer/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      runtime(
        `import { createMockStore } from "../../entities/greenwash/api/mock/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      runtime(`import type { O } from "../../widgets/doc-viewer/pdfjs.ts";`),
    ).toHaveLength(1);
    expect(
      runtime(`import { redirect } from "@tanstack/react-router";`),
    ).toEqual([
      'app/greenwash/runtime.ts 가 @tanstack/react-router 를 가져온다',
    ]);
    // 옛 이름은 자리 밖
    expect(
      violations(app, at('app/greenwash/GreenwashPage.tsx'), `export {};`),
    ).toHaveLength(1);
    // 경로 표 시험은 경로 표와 목 저장소 표면도 쓴다
    expect(
      violations(
        app,
        at('app/greenwash/router.test.tsx'),
        `import { createMemoryHistory } from "@tanstack/react-router"; import { it } from "vitest"; import { createAppRouter } from "../router.tsx"; import { createMockStore } from "../../entities/greenwash/api/mock/index.ts";`,
      ),
    ).toEqual([]);
    // 입구: 밖은 ui/index.ts 만, e2e 는 config/text.ts 도, 화면과 app 은 칸 표면, 목 저장소 표면은 app 과 화면의 시험만
    const doors = DOORS.find((row) => row.dir === 'entities/greenwash')!;
    const enter = (from: string, target: string) =>
      sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(
      enter(
        'src/pages/demo-parts/PartsPage.tsx',
        '../../entities/greenwash/ui/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/demo-parts/PartsPage.tsx',
        '../../entities/greenwash/config/text.ts',
      ),
    ).toEqual([
      'src/pages/demo-parts/PartsPage.tsx → src/entities/greenwash/config/text.ts',
    ]);
    expect(
      enter(
        'e2e/greenwash.spec.ts',
        '../src/entities/greenwash/config/text.ts',
      ),
    ).toEqual([]);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/greenwash/api/index.ts'),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/greenwash/hooks/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/greenwash/api/mock/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/greenwash-list/ui/a.test.tsx',
        '../../../entities/greenwash/api/mock/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/greenwash/GreenwashRoutes.tsx',
        '../../entities/greenwash/api/mock/index.ts',
      ),
    ).toEqual([]);
    // 화면 시험이 같이 쓰는 가짜 저장소(api/mock/testing.ts)는 화면 시험만 — 제품(화면·경로 컴포넌트)은 못 가져온다
    expect(
      enter(
        'src/pages/greenwash-list/ui/a.test.tsx',
        '../../../entities/greenwash/api/mock/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/greenwash/api/mock/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/greenwash/GreenwashRoutes.tsx',
        '../../entities/greenwash/api/mock/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter('src/main.tsx', './entities/greenwash/api/mock/index.ts'),
    ).toHaveLength(1);
    expect(
      enter('src/app/router.tsx', '../entities/greenwash/api/mock/index.ts'),
    ).toHaveLength(1);
    // shared/lib: address.ts 는 누구나, testing/ 도우미는 시험만, 그 밖의 속 파일은 안 된다
    const lib = DOORS.find((row) => row.dir === 'shared/lib')!;
    const libEnter = (from: string, target: string) =>
      sideDoors(lib, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(
      libEnter(
        'src/pages/demo-table/TablePage.tsx',
        '../../shared/lib/address.ts',
      ),
    ).toEqual([]);
    expect(
      libEnter(
        'src/pages/demo-table/a.test.tsx',
        '../../shared/lib/testing/layout.ts',
      ),
    ).toEqual([]);
    expect(
      libEnter(
        'src/pages/demo-table/TablePage.tsx',
        '../../shared/lib/testing/layout.ts',
      ),
    ).toEqual([
      'src/pages/demo-table/TablePage.tsx → src/shared/lib/testing/layout.ts',
    ]);
    expect(
      libEnter(
        'src/pages/demo-table/TablePage.tsx',
        '../../shared/lib/other.ts',
      ),
    ).toHaveLength(1);
    // shared/lib/useLoad.ts(읽기 훅 하나, 밴드 CW1 ①): 문은 열려 있고, 칸 규칙이 그린워싱 hooks 만 들인다(ui 는 훅을 거친다)
    expect(
      libEnter(
        'src/pages/greenwash-list/hooks/useCheckList.ts',
        '../../../shared/lib/useLoad.ts',
      ),
    ).toEqual([]);
    const loadFrom = (dir: string, file: string) =>
      violations(
        SLICES.find((row) => row.dir === dir)!,
        at(file),
        `import { useLoad } from "${relative(dirname(at(file)), at('shared/lib/useLoad.ts'))}";`,
      );
    expect(loadFrom('pages', 'pages/greenwash-list/hooks/a.ts')).toEqual([]);
    expect(
      loadFrom('entities/greenwash', 'entities/greenwash/hooks/a.ts'),
    ).toEqual([]);
    expect(loadFrom('pages', 'pages/greenwash-list/ui/A.tsx')).toEqual([
      'pages/greenwash-list/ui 가 shared/lib/useLoad.ts 를 가져온다',
    ]);
    expect(
      loadFrom('entities/greenwash', 'entities/greenwash/ui/A.tsx'),
    ).toEqual(['entities/greenwash/ui 가 shared/lib/useLoad.ts 를 가져온다']);
    // 화면 폴더는 index.ts 로만
    const pages = DOORS.find((row) => row.dir === 'pages')!;
    expect(
      sideDoors(
        pages,
        at('app/greenwash/GreenwashRoutes.tsx'),
        `import { L } from "../../pages/greenwash-list/index.ts";`,
      ).problems,
    ).toEqual([]);
    expect(
      sideDoors(
        pages,
        at('app/greenwash/GreenwashRoutes.tsx'),
        `import { L } from "../../pages/greenwash-list/ui/ListScreen.tsx";`,
      ).problems,
    ).toHaveLength(1);
    // 화면끼리는 층 순서가 막는다(같은 층의 다른 슬라이스)
    expect(
      layerViolations(
        at('pages/greenwash-result/ui/a.tsx'),
        `import { R } from "../../greenwash-review/index.ts";`,
      ),
    ).toEqual([
      'pages/greenwash-result 가 pages/greenwash-review/index.ts 를 가져온다(같은 층의 다른 슬라이스)',
    ]);
    expect(
      layerViolations(
        e('ui/a.tsx'),
        `import { L } from "../../../pages/greenwash-list/index.ts";`,
      ),
    ).toHaveLength(1);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: ③ 리뷰 지적(M1·M2·L-a·L-b)', () => {
  it('[M1] 폴더째·확장자 없는 import 는 빨강', () => {
    expect(
      layerViolations(
        at('pages/demo-table/a.tsx'),
        `import { ReviewTable } from "../../widgets/review-table";`,
      ),
    ).toEqual([
      'src/pages/demo-table/a.tsx 가 ../../widgets/review-table 를 확장자 없이 가져온다(파일 이름과 .ts/.tsx/.css 를 적는다)',
    ]);
    expect(
      layerViolations(at('pages/demo-table/a.tsx'), `import { x } from "./b";`),
    ).toHaveLength(1);
    expect(
      layerViolations(
        join(webRoot, 'tools/x.ts'),
        `import { p } from "../src/widgets/review-table/model";`,
      ),
    ).toHaveLength(1);
    // 되는 것: 확장자와 꼬리가 붙은 파일
    expect(
      layerViolations(
        at('pages/demo-table/a.tsx'),
        `import { R } from "../../widgets/review-table/index.ts"; import "./cards.css"; import c from "./x.css?inline";`,
      ),
    ).toEqual([]);
    // .json 은 ?raw 로만 된다(밴드 FX1): ?raw 없는 .json 과 확장자 없는 경로는 빨강
    expect(
      layerViolations(
        at('pages/demo-table/a.tsx'),
        `import r from "./a.json?raw";`,
      ),
    ).toEqual([]);
    expect(
      layerViolations(
        at('pages/demo-table/a.tsx'),
        `import r from "./a.json";`,
      ),
    ).toHaveLength(1);
    expect(
      layerViolations(at('pages/demo-table/a.tsx'), `import r from "./a";`),
    ).toHaveLength(1);
  });

  it('[M2] src 의 파일이 src 밖(tools/·e2e/)을 가져오면 빨강, 계약 타입은 된다', () => {
    expect(
      layerViolations(
        at('pages/demo-viewer/a.ts'),
        `import { SAMPLE_A } from "../../../tools/sample-layout.ts";`,
      ),
    ).toEqual([
      'src/pages/demo-viewer/a.ts 가 tools/sample-layout.ts 를 가져온다(src 는 src 밖을 모른다)',
    ]);
    expect(
      layerViolations(
        at('shared/ui/x/ui/a.tsx'),
        `import { t } from "../../../../../e2e/x.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      layerViolations(
        at('shared/api/model/x.ts'),
        `import type { paths } from "../../../../../api-py/generated/api.d.ts";`,
      ),
    ).toEqual([]);
  });

  it('[L-a] 화면 폴더(pages/greenwash-*)에는 api/·config/ 칸이 없다 — 만들면 자리 밖(stray)', () => {
    const page = SLICES.find((row) => row.dir === 'pages')!;
    expect(
      violations(page, at('pages/greenwash-list/api/a.ts'), `export {};`),
    ).toEqual([
      'pages/greenwash-list/api/a.ts 는 정해진 자리(<슬라이스>/index.ts, {model,hooks,ui}/) 밖에 있다',
    ]);
    expect(
      violations(page, at('pages/greenwash-list/config/text.ts'), `export {};`),
    ).toHaveLength(1);
    // 데모 폴더는 이 줄이 보지 않는다(partFilter)
    expect(violations(page, at('pages/demo-table/a.ts'), `export {};`)).toEqual(
      [],
    );
  });

  it('[L-b] 데모 넷은 화면 파일 하나로만 들어온다(검토 표 데모는 e2e 의 가짜 행도)', () => {
    const demo = DOORS.find((row) => row.partFilter?.source === '^demo-')!;
    const enter = (from: string, target: string) =>
      sideDoors(demo, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(enter('src/main.tsx', './pages/demo-table/TablePage.tsx')).toEqual(
      [],
    );
    expect(enter('src/main.tsx', './pages/demo-viewer/App.tsx')).toEqual([]);
    expect(
      enter('src/main.tsx', './pages/demo-viewer/CompactViewer.tsx'),
    ).toEqual(['src/main.tsx → src/pages/demo-viewer/CompactViewer.tsx']);
    expect(
      enter('src/main.tsx', './pages/demo-table/columns.tsx'),
    ).toHaveLength(1);
    expect(
      enter('e2e/review-table.spec.ts', '../src/pages/demo-table/fakeRows.ts'),
    ).toEqual([]);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 로그인 세션(밴드 LG1)', () => {
  const session = ruleOf('entities/session');
  const doors = DOORS.find((row) => row.dir === 'entities/session')!;

  it('model 은 계약 타입을 import type 으로만, api 는 전역 보관소·창·전역 fetch 호출을 모른다', () => {
    expect(
      violations(
        session,
        at('entities/session/model/a.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        session,
        at('entities/session/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/session/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    expect(
      violations(
        session,
        at('entities/session/api/a.ts'),
        `export const r = sessionStorage.getItem("k");`,
      ),
    ).toEqual(['entities/session/api 가 DOM·통신을 쓴다: sessionStorage']);
    expect(
      violations(
        session,
        at('entities/session/api/a.ts'),
        `export const go = (r: Request) => fetch(r);`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        session,
        at('entities/session/api/a.ts'),
        `export const g = globalThis;`,
      ),
    ).toHaveLength(1);
    // 되는 것: createApi 의 칸 이름 fetch:, 감싼 통신 함수가 만드는 Request·Headers
    expect(
      violations(
        session,
        at('entities/session/api/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts"; export const m = (send: (r: Request) => Promise<Response>) => createApi({ baseUrl: "/api", fetch: send }); export const h = new Headers();`,
      ),
    ).toEqual([]);
    // 제품 파일은 가짜 서버(testing.ts)를 가져오지 않는다
    expect(
      violations(
        session,
        at('entities/session/hooks/a.ts'),
        `import { fakeAuthServer } from "../api/testing.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(session, at('entities/session/lib/a.ts'), `export {};`),
    ).toHaveLength(1);
  });

  it('로그인 화면 폴더(pages/login·password-change)는 index.ts 로만, 세션 칸 표면만 쓴다. 진입 청크는 가드만 정적으로', () => {
    const pages = DOORS.find(
      (row) => row.partFilter?.source === AUTH_PAGES.source,
    )!;
    const page = SLICES.find(
      (row) => row.partFilter?.source === AUTH_PAGES.source,
    )!;
    const enter = (from: string, target: string) =>
      sideDoors(pages, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(
      enter('src/app/auth/AuthRoutes.tsx', '../../pages/login/index.ts'),
    ).toEqual([]);
    expect(
      enter(
        'src/app/auth/AuthRoutes.tsx',
        '../../pages/login/ui/LoginScreen.tsx',
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/login/ui/A.tsx'),
        `import { SESSION_TEXT } from "../../../entities/session/config/text.ts"; import { AuthCard } from "../../../entities/session/ui/index.ts"; import { Button } from "../../../shared/ui/button/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        page,
        at('pages/login/ui/A.tsx'),
        `import { createSessionStore } from "../../../entities/session/api/store.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/login/hooks/a.ts'),
        `export const s = sessionStorage.getItem("k");`,
      ),
    ).toHaveLength(1);
    // 그린워싱 화면 줄은 로그인 폴더를 보지 않는다(넓히지 않았다)
    expect(
      violations(
        SLICES.find((row) => row.partFilter?.source === '^greenwash-')!,
        at('pages/login/ui/A.tsx'),
        `import { x } from "../../../entities/session/config/text.ts";`,
      ),
    ).toEqual([]);
    const router = (source: string) =>
      entryViolations(at('app/router.tsx'), source);
    expect(
      router(
        `import { guardSession } from "./auth/guard.ts"; const a = () => import("./auth/AuthRoutes.tsx");`,
      ),
    ).toEqual([]);
    expect(
      router(`import { LoginRoute } from "./auth/AuthRoutes.tsx";`),
    ).toHaveLength(1);
    expect(
      router(`import { LoginScreen } from "../pages/login/index.ts";`),
    ).toHaveLength(1);
    expect(
      router(`import { x } from "../entities/session/api/index.ts";`),
    ).toHaveLength(1);
  });

  it('밖에서는 app/·로그인 화면·e2e 만 칸 표면으로 들어온다(가짜 서버는 시험만)', () => {
    const enter = (from: string, target: string) =>
      sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(
      enter('src/app/auth/guard.ts', '../../entities/session/api/index.ts'),
    ).toEqual([]);
    expect(
      enter('src/app/auth/guard.ts', '../../entities/session/api/store.ts'),
    ).toHaveLength(1);
    expect(
      enter('src/app/auth/guard.ts', '../../entities/session/api/testing.ts'),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/auth/router.test.tsx',
        '../../entities/session/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/widgets/doc-viewer/ui/a.tsx',
        '../../../entities/session/model/index.ts',
      ),
    ).toHaveLength(1);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 계정·어드민(밴드 AD1)', () => {
  const account = ruleOf('entities/account');
  const page = SLICES.find(
    (row) => row.partFilter?.source === ADMIN_PAGES.source,
  )!;

  it('계정 model·api 는 전역 난수·로그·보관소·전역 fetch 를 모른다(임시 비밀번호를 기록·보관하는 길)', () => {
    for (const source of [
      `export const r = crypto.getRandomValues(new Uint32Array(1));`,
      `export const log = (p: string) => console.log(p);`,
      `export const s = (p: string) => sessionStorage.setItem("k", p);`,
      `export const f = (r: Request) => fetch(r);`,
    ])
      expect(
        violations(account, at('entities/account/api/a.ts'), source),
        source,
      ).toHaveLength(1);
    expect(
      violations(
        account,
        at('entities/account/model/a.ts'),
        `export const c = console;`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        account,
        at('entities/account/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/account/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    // 되는 것: 넣어 받은 난수 함수, 칸 이름 random:, shared/api 의 asFailure
    expect(
      violations(
        account,
        at('entities/account/api/a.ts'),
        `import { asFailure } from "../../../shared/api/index.ts"; export const m = ({ random }: { random: (a: Uint32Array) => Uint32Array }) => random(new Uint32Array(1));`,
      ),
    ).toEqual([]);
    // 제품 파일은 가짜 서버를 가져오지 않는다
    expect(
      violations(
        account,
        at('entities/account/api/a.ts'),
        `import { fakeAccountsServer } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('어드민 화면 폴더는 index.ts 로만 들어오고, 보관소·로그 낱말이 없고, 세션 문을 쓰지 않는다', () => {
    expect(
      violations(
        page,
        at('pages/admin-accounts/ui/A.tsx'),
        `export const s = (p: string) => localStorage.setItem("k", p);`,
      ),
    ).toEqual([
      'pages/admin-accounts/ui/A.tsx 가 보관소·로그를 쓴다: localStorage',
    ]);
    expect(
      violations(
        page,
        at('pages/admin-accounts/hooks/a.ts'),
        `export const l = (p: string) => console.info(p);`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/admin-accounts/ui/A.tsx'),
        `import { SESSION_TEXT } from "../../../entities/session/config/text.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/admin-accounts/ui/A.tsx'),
        `import { ACCOUNT_TEXT } from "../../../entities/account/config/text.ts"; import { Button } from "../../../shared/ui/button/index.ts";`,
      ),
    ).toEqual([]);
    const pages = DOORS.find(
      (row) => row.partFilter?.source === ADMIN_PAGES.source,
    )!;
    expect(
      sideDoors(
        pages,
        at('app/admin/AdminRoutes.tsx'),
        `import { A } from "../../pages/admin-accounts/ui/AccountsScreen.tsx";`,
      ).problems,
    ).toHaveLength(1);
    // 로그인 줄은 어드민 폴더를 보지 않는다(넓히지 않았다)
    expect(
      violations(
        SLICES.find((row) => row.partFilter?.source === AUTH_PAGES.source)!,
        at('pages/admin-accounts/ui/A.tsx'),
        `import { x } from "../../../entities/account/config/text.ts";`,
      ),
    ).toEqual([]);
  });

  it('밖에서 계정 슬라이스로는 app/·어드민 화면·e2e 만 칸 표면으로(가짜 서버는 시험만)', () => {
    const doors = DOORS.find((row) => row.dir === 'entities/account')!;
    const enter = (from: string, target: string) =>
      sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
        .problems;
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/account/api/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/account/api/port.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/account/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/account/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/account/model/index.ts'),
    ).toHaveLength(1);
  });
});

// 밴드 AD2W: 어드민 목 화면(밴드 AD2)의 목 시험은 목 슬라이스가 0 이 되어 걷었다(AI 설정은 아래 AD2W describe 의 실서버 시험). 진입 청크 시험만 남는다.
describe('구조 규칙 — 규칙이 실제로 잡는다: 어드민 진입(밴드 AD2)', () => {
  it('진입 청크는 어드민 화면 모듈을 게으르게만 부른다', () => {
    const router = (source: string) =>
      entryViolations(at('app/router.tsx'), source);
    expect(
      router(`const m = () => import("./admin/AdminRoutes.tsx");`),
    ).toEqual([]);
    expect(
      router(`import { AuditRoute } from "./admin/AdminRoutes.tsx";`),
    ).toHaveLength(1);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 감사 기록 실서버(밴드 AD5R)', () => {
  const audit = ruleOf('entities/audit-log');
  const admin = ruleOf('app/admin');
  const page = SLICES.find(
    (row) => row.partFilter?.source === ADMIN_PAGES.source,
  )!;
  const doors = DOORS.find((row) => row.dir === 'entities/audit-log')!;
  const enter = (from: string, target: string) =>
    sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
      .problems;

  // AD2W: 목 슬라이스 목록이 걷혀 그 단언은 AD2W describe 의 「목 슬라이스 0」 하나로 모았다.
  it('목 슬라이스에서 빠져 감사 기록 줄은 하나', () => {
    expect(
      SLICES.filter((row) => row.dir === 'entities/audit-log'),
    ).toHaveLength(1);
  });

  it('api 는 넣어 준 Api 로만: 전역 fetch 부름·창·보관소·로그는 빨강, createApi·asFailure import 와 칸 이름 fetch: 는 초록', () => {
    for (const source of [
      `export const f = () => globalThis.fetch('/api/audit-logs');`,
      `export const f = () => fetch('/api/audit-logs');`,
      `export const w = () => window.location.href;`,
      `export const s = () => sessionStorage.getItem('k');`,
      `export const l = () => console.log(1);`,
      `import { ACCOUNT_TEXT } from "../../account/config/text.ts";`,
    ])
      expect(
        violations(audit, at('entities/audit-log/api/a.ts'), source).length,
        source,
      ).toBeGreaterThan(0);
    expect(
      violations(
        audit,
        at('entities/audit-log/api/a.ts'),
        `import { asFailure, createApi } from "../../../shared/api/index.ts"; import type { Api } from "../../../shared/api/index.ts"; export const m = ({ fetch }: { fetch: (r: Request) => Promise<Response> }) => createApi({ baseUrl: "/api", fetch });`,
      ),
    ).toEqual([]);
    // 제품 파일은 가짜 서버를 가져오지 않는다
    expect(
      violations(
        audit,
        at('entities/audit-log/api/a.ts'),
        `import { fakeAuditServer } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('model 은 계약 타입을 import type 으로만, 문구 표는 아무것도 가져오지 않는다', () => {
    expect(
      violations(
        audit,
        at('entities/audit-log/model/a.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        audit,
        at('entities/audit-log/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/audit-log/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    expect(
      violations(
        audit,
        at('entities/audit-log/model/a.ts'),
        `import { AUDIT_TEXT } from "../config/text.ts";`,
      ).length,
    ).toBeGreaterThan(0);
    expect(
      violations(
        audit,
        at('entities/audit-log/config/text.ts'),
        `import { x } from "../model/index.ts";`,
      ),
    ).toContain(
      'entities/audit-log/config/text.ts 가 ../model/index.ts 를 가져온다(문구 표는 아무것도 가져오지 않는다)',
    );
  });

  it('경로 컴포넌트: AdminRoutes.tsx 는 감사 api 를 가져온다', () => {
    expect(
      violations(
        admin,
        at('app/admin/AdminRoutes.tsx'),
        `import { createAuditServerPort } from "../../entities/audit-log/api/index.ts";`,
      ),
    ).toEqual([]);
    // AdminRoutes 는 AI 설정 슬라이스를 직접 모른다(밴드 AD2W — 옛 목 슬라이스. 모듈은 ai-setting-modules.ts 가 잇는다)
    expect(
      violations(
        admin,
        at('app/admin/AdminRoutes.tsx'),
        `import { c } from "../../entities/ai-setting/api/index.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('밖에서는 칸 표면으로만, 가짜 서버는 시험만', () => {
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/audit-log/api/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/audit-log/api/server.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/audit-log/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/admin-audit/ui/AuditScreen.test.tsx',
        '../../../entities/audit-log/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/audit-log/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/audit-log/model/index.ts'),
    ).toHaveLength(1);
    // 어드민 화면 폴더: 칸 표면은 되고, 시험만 가짜 서버
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { AUDIT_TEXT } from "../../../entities/audit-log/config/text.ts"; import { toEntry } from "../../../entities/audit-log/model/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { fakeAuditServer } from "../../../entities/audit-log/api/testing.ts";`,
      ),
    ).toHaveLength(1);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 실행 기록 실서버(밴드 AD4R)', () => {
  const runLog = ruleOf('entities/run-log');
  const admin = ruleOf('app/admin');
  const page = SLICES.find(
    (row) => row.partFilter?.source === ADMIN_PAGES.source,
  )!;
  const doors = DOORS.find((row) => row.dir === 'entities/run-log')!;
  const enter = (from: string, target: string) =>
    sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
      .problems;

  // AD2W: 목 슬라이스 목록이 걷혀 그 단언은 AD2W describe 의 「목 슬라이스 0」 하나로 모았다.
  it('목 슬라이스에서 빠져 실행 기록 줄은 하나', () => {
    expect(SLICES.filter((row) => row.dir === 'entities/run-log')).toHaveLength(
      1,
    );
    expect(DOORS.filter((row) => row.dir === 'entities/run-log')).toHaveLength(
      1,
    );
  });

  it('api 는 넣어 준 Api 로만: 전역 fetch 부름·창·보관소·로그는 빨강, createApi·asFailure import 와 칸 이름 fetch: 는 초록', () => {
    for (const source of [
      `export const f = () => globalThis.fetch('/api/run-logs');`,
      `export const f = () => fetch('/api/run-logs');`,
      `export const w = () => window.location.href;`,
      `export const s = () => sessionStorage.getItem('k');`,
      `export const l = () => console.log(1);`,
      `import { AUDIT_TEXT } from "../../audit-log/config/text.ts";`,
    ])
      expect(
        violations(runLog, at('entities/run-log/api/a.ts'), source).length,
        source,
      ).toBeGreaterThan(0);
    expect(
      violations(
        runLog,
        at('entities/run-log/api/a.ts'),
        `import { asFailure, createApi } from "../../../shared/api/index.ts"; import type { Api } from "../../../shared/api/index.ts"; export const m = ({ fetch }: { fetch: (r: Request) => Promise<Response> }) => createApi({ baseUrl: "/api", fetch });`,
      ),
    ).toEqual([]);
    // 제품 파일은 가짜 서버를 가져오지 않는다
    expect(
      violations(
        runLog,
        at('entities/run-log/api/a.ts'),
        `import { fakeRunLogServer } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('model 은 계약 타입을 import type 으로만, 문구 표는 아무것도 가져오지 않는다', () => {
    expect(
      violations(
        runLog,
        at('entities/run-log/model/a.ts'),
        `import type { Schemas, paths } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        runLog,
        at('entities/run-log/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/run-log/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    expect(
      violations(
        runLog,
        at('entities/run-log/model/a.ts'),
        `import { RUN_LOG_TEXT } from "../config/text.ts";`,
      ).length,
    ).toBeGreaterThan(0);
    expect(
      violations(
        runLog,
        at('entities/run-log/config/text.ts'),
        `import { x } from "../model/index.ts";`,
      ),
    ).toContain(
      'entities/run-log/config/text.ts 가 ../model/index.ts 를 가져온다(문구 표는 아무것도 가져오지 않는다)',
    );
  });

  it('경로 컴포넌트: AdminRoutes.tsx 는 실행 기록 api 를 가져온다', () => {
    expect(
      violations(
        admin,
        at('app/admin/AdminRoutes.tsx'),
        `import { createRunLogServerPort } from "../../entities/run-log/api/index.ts";`,
      ),
    ).toEqual([]);
  });

  it('밖에서는 칸 표면으로만, 가짜 서버는 시험만', () => {
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/run-log/api/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/run-log/api/server.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/run-log/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/router.test.tsx',
        '../../entities/run-log/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/admin-runs/ui/RunsScreen.test.tsx',
        '../../../entities/run-log/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/run-log/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/run-log/model/index.ts'),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/run-log/config/text.ts'),
    ).toEqual([]);
    // 어드민 화면 폴더: 칸 표면은 되고, 시험만 가짜 서버
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { RUN_LOG_TEXT } from "../../../entities/run-log/config/text.ts"; import { runQuery } from "../../../entities/run-log/model/index.ts"; import type { RunLogServerPort } from "../../../entities/run-log/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { fakeRunLogServer } from "../../../entities/run-log/api/testing.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.test.tsx'),
        `import { fakeRunLogServer } from "../../../entities/run-log/api/testing.ts";`,
      ),
    ).toEqual([]);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: 그린워싱 AI 설정 판 실서버(밴드 AD2R)', () => {
  const setting = ruleOf('entities/greenwash-setting');
  const admin = ruleOf('app/admin');
  const page = SLICES.find(
    (row) => row.partFilter?.source === ADMIN_PAGES.source,
  )!;
  const doors = DOORS.find((row) => row.dir === 'entities/greenwash-setting')!;
  const enter = (from: string, target: string) =>
    sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
      .problems;

  // AD2W: 목 슬라이스 목록이 걷혀 그 단언은 AD2W describe 의 「목 슬라이스 0」 하나로 모았다.
  it('새 실서버 줄은 하나씩', () => {
    expect(
      SLICES.filter((row) => row.dir === 'entities/greenwash-setting'),
    ).toHaveLength(1);
    expect(
      DOORS.filter((row) => row.dir === 'entities/greenwash-setting'),
    ).toHaveLength(1);
  });

  it('api 는 넣어 준 Api 로만: 전역 fetch 부름·창·보관소·로그·다른 entities 는 빨강, createApi·asFailure 는 초록', () => {
    for (const source of [
      `export const f = () => globalThis.fetch('/api/ai-settings/greenwash');`,
      `export const f = () => fetch('/api/ai-settings/greenwash');`,
      `export const w = () => window.location.href;`,
      `export const s = () => localStorage.getItem('k');`,
      `export const l = () => console.log(1);`,
      `import { AI_SETTING_TEXT } from "../../ai-setting/config/text.ts";`,
      `import type { CriterionRow } from "../../ai-setting/model/index.ts";`,
    ])
      expect(
        violations(setting, at('entities/greenwash-setting/api/a.ts'), source)
          .length,
        source,
      ).toBeGreaterThan(0);
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/api/a.ts'),
        `import { asFailure, createApi } from "../../../shared/api/index.ts"; import type { Api } from "../../../shared/api/index.ts"; export const m = ({ fetch }: { fetch: (r: Request) => Promise<Response> }) => createApi({ baseUrl: "/api", fetch });`,
      ),
    ).toEqual([]);
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/api/a.ts'),
        `import { fakeGreenwashSettingServer } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
  });

  it('model 은 계약 타입을 import type 으로만, 문구 표는 아무것도 가져오지 않는다', () => {
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/model/a.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/greenwash-setting/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/config/text.ts'),
        `import { x } from "../model/index.ts";`,
      ),
    ).toContain(
      'entities/greenwash-setting/config/text.ts 가 ../model/index.ts 를 가져온다(문구 표는 아무것도 가져오지 않는다)',
    );
  });

  it('AS3b ①: ui 칸 — 키트 부품·shared/ui 공개 표면·model·config 는 초록, entities/ai-setting·이 슬라이스 api 칸·shared/ui 깊은 경로는 빨강(시험은 칸 규칙 그대로)', () => {
    const card = (source: string) =>
      violations(setting, at('entities/greenwash-setting/ui/A.tsx'), source);
    expect(
      card(
        `import { useState } from "react"; import { Switch } from "@marcspon/ui/components/switch"; import { Checkbox } from "@marcspon/ui/components/checkbox"; import { Card } from "../../../shared/ui/card/index.ts"; import { termsCount } from "../model/index.ts"; import type { GREENWASH_SETTING_TEXT } from "../config/text.ts";`,
      ),
    ).toEqual([]);
    expect(
      card(
        `import { createGreenwashSettingServerPort } from "../api/index.ts";`,
      ),
    ).toEqual([
      'entities/greenwash-setting/ui/A.tsx 가 entities/greenwash-setting/api/index.ts 를 가져온다(대상 단어 ui 는 api 를 모른다 — 읽기 함수는 모듈 줄이 넘긴다)',
    ]);
    for (const source of [
      `import type { ModuleDraftSlot } from "../../ai-setting/model/index.ts";`,
      `import { Card } from "../../../shared/ui/card/ui/Card.tsx";`,
      `import { Slot } from "@radix-ui/react-slot";`,
    ])
      expect(card(source).length, source).toBeGreaterThan(0);
    // 시험 파일에는 ui→api 갈래를 걸지 않는다(칸 규칙의 testAlso — 가짜 서버만)
    expect(
      violations(
        setting,
        at('entities/greenwash-setting/ui/A.test.tsx'),
        `import { fakeGreenwashSettingServer } from "../api/testing.ts";`,
      ),
    ).toEqual([]);
  });

  // AD2W ⓖ: 그 api 를 가져오는 자리는 AdminRoutes.tsx 에서 ai-setting-modules.ts 로 옮겼다.
  it('모듈 줄: ai-setting-modules.ts 는 그 api 를 가져오고, AdminRoutes.tsx 는 직접 가져오면 빨강', () => {
    expect(
      violations(
        admin,
        at('app/admin/ai-setting-modules.ts'),
        `import { createGreenwashSettingServerPort } from "../../entities/greenwash-setting/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        admin,
        at('app/admin/AdminRoutes.tsx'),
        `import { createGreenwashSettingServerPort } from "../../entities/greenwash-setting/api/index.ts";`,
      ),
    ).toEqual([
      'app/admin/AdminRoutes.tsx 가 entities/greenwash-setting/api/index.ts 를 가져온다',
    ]);
  });

  it('밖에서는 칸 표면으로만, 가짜 서버는 시험만', () => {
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/greenwash-setting/api/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/greenwash-setting/api/server.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/AdminRoutes.tsx',
        '../../entities/greenwash-setting/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/router.test.tsx',
        '../../entities/greenwash-setting/api/testing.ts',
      ),
    ).toEqual([]);
    // AD2W ⓐ: 어드민 화면(시험 포함)은 더 들어오지 않는다
    expect(
      enter(
        'src/pages/admin-ai-settings/ui/AiSettingsScreen.test.tsx',
        '../../../entities/greenwash-setting/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/admin-x/ui/A.tsx',
        '../../../entities/greenwash-setting/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/ai-setting-modules.test.ts',
        '../../entities/greenwash-setting/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/greenwash-setting/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'e2e/x.spec.ts',
        '../src/entities/greenwash-setting/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'e2e/x.spec.ts',
        '../src/entities/greenwash-setting/config/text.ts',
      ),
    ).toEqual([]);
    // 어드민 화면 폴더(칸 규칙): AD2W ⓐ 부터 칸 표면도 시험의 가짜 서버도 빨강
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { GREENWASH_SETTING_TEXT } from "../../../entities/greenwash-setting/config/text.ts"; import { versionRows } from "../../../entities/greenwash-setting/model/index.ts"; import type { GreenwashSettingServerPort } from "../../../entities/greenwash-setting/api/index.ts";`,
      ),
    ).toHaveLength(3);
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.tsx'),
        `import { fakeGreenwashSettingServer } from "../../../entities/greenwash-setting/api/testing.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/admin-x/ui/A.test.tsx'),
        `import { fakeGreenwashSettingServer } from "../../../entities/greenwash-setting/api/testing.ts";`,
      ),
    ).toHaveLength(1);
  });
});

describe('구조 규칙 — 규칙이 실제로 잡는다: AI 설정 실서버·모듈 줄(밴드 AD2W)', () => {
  const setting = ruleOf('entities/ai-setting');
  const admin = ruleOf('app/admin');
  const page = SLICES.find(
    (row) => row.partFilter?.source === ADMIN_PAGES.source,
  )!;
  const doors = DOORS.find((row) => row.dir === 'entities/ai-setting')!;
  const enter = (from: string, target: string) =>
    sideDoors(doors, join(webRoot, from), `import { x } from "${target}";`)
      .problems;

  // ⓑ: 옛 「목 슬라이스 목록 = [entities/ai-setting/]」 단언 셋(AD5R·AD4R·AD2R)을 갈음한다.
  it('목 슬라이스 0: AI 설정은 실서버 줄 하나씩이고, 목 어댑터 꼴(api/mock/·통신 낱말째 금지)의 줄이 없다', () => {
    expect(SLICES.filter((row) => row.dir === 'entities/ai-setting')).toEqual([
      setting,
    ]);
    expect(DOORS.filter((row) => row.dir === 'entities/ai-setting')).toEqual([
      doors,
    ]);
    // 실서버 꼴: api 는 실행 기록 줄과 같은 DOM 규칙, model 은 순수 함수 칸이라 DOM_WORD 그대로(검증 R2)·도우미 취급
    expect(setting.dom).toEqual({ model: DOM_WORD, api: ACCOUNT_DOM });
    expect(setting.helperIsTest).toBe(true);
    // 목 꼴의 흔적이 없다: api 칸에서 칸 이름 fetch: 를 빨강으로 잡는 줄(옛 MOCK_API_DOM)과 api/mock/ 을 시험에 여는 줄
    expect(
      setting.dom.api!.test(
        `export const p = ({ fetch }: { fetch: F }) => fetch;`,
      ),
    ).toBe(false);
    expect(existsSync(at(AI_SETTING + 'api/mock'))).toBe(false);
    expect(setting.testAlso(AI_SETTING + 'api/mock/fixtures.ts')).toBe(false);
  });

  it('api 는 넣어 준 Api 로만: 전역 fetch 부름·창·보관소·로그·다른 entities 는 빨강, createApi·asFailure 는 초록', () => {
    for (const source of [
      `export const f = () => globalThis.fetch('/api/ai-settings');`,
      `export const f = () => fetch('/api/ai-settings');`,
      `export const w = () => window.location.href;`,
      `export const s = () => localStorage.getItem('k');`,
      `export const l = () => console.log(1);`,
      `import { GREENWASH_SETTING_TEXT } from "../../greenwash-setting/config/text.ts";`,
      `import type { SettingList } from "../../greenwash-setting/model/index.ts";`,
    ])
      expect(
        violations(setting, at('entities/ai-setting/api/a.ts'), source).length,
        source,
      ).toBeGreaterThan(0);
    expect(
      violations(
        setting,
        at('entities/ai-setting/api/a.ts'),
        `import { asFailure, createApi } from "../../../shared/api/index.ts"; import type { Api } from "../../../shared/api/index.ts"; import { DEFAULT_VERSION_KEY } from "../model/index.ts"; export const m = ({ fetch }: { fetch: (r: Request) => Promise<Response> }) => createApi({ baseUrl: "/api", fetch });`,
      ),
    ).toEqual([]);
    // 제품 파일은 가짜 서버를 가져오지 않는다(testing.ts 는 시험만)
    expect(
      violations(
        setting,
        at('entities/ai-setting/api/a.ts'),
        `import { fakePromptModelServer } from "./testing.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        setting,
        at('entities/ai-setting/api/a.test.ts'),
        `import { fakePromptModelServer } from "./testing.ts";`,
      ),
    ).toEqual([]);
  });

  it('model 은 react 를 타입으로만(AP1W ③ — 모듈 초안 슬롯의 ReactNode): import type 초록, 값 import·이름 앞 type 은 빨강', () => {
    expect(
      violations(
        setting,
        at('entities/ai-setting/model/a.ts'),
        `import type { ReactNode } from 'react';`,
      ),
    ).toEqual([]);
    for (const source of [
      `import { useState } from 'react';`,
      `import { type ReactNode } from 'react';`,
    ])
      expect(
        violations(setting, at('entities/ai-setting/model/a.ts'), source),
        source,
      ).toContain(
        'entities/ai-setting/model/a.ts 가 react 를 값으로 가져온다(model 은 react 타입만 — import type)',
      );
  });

  it('model 은 계약 타입을 import type 으로만, 문구 표는 아무것도 가져오지 않는다', () => {
    expect(
      violations(
        setting,
        at('entities/ai-setting/model/a.ts'),
        `import type { Schemas } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        setting,
        at('entities/ai-setting/model/a.ts'),
        `import { createApi } from "../../../shared/api/index.ts";`,
      ),
    ).toEqual([
      'entities/ai-setting/model/a.ts 가 ../../../shared/api/index.ts 를 값으로 가져온다(model 은 계약 타입만 — import type)',
    ]);
    expect(
      violations(
        setting,
        at('entities/ai-setting/model/a.ts'),
        `export const w = () => window.location.href;`,
      ).length,
    ).toBeGreaterThan(0);
    expect(
      violations(
        setting,
        at('entities/ai-setting/config/text.ts'),
        `import { x } from "../model/index.ts";`,
      ),
    ).toContain(
      'entities/ai-setting/config/text.ts 가 ../model/index.ts 를 가져온다(문구 표는 아무것도 가져오지 않는다)',
    );
  });

  it('밖에서는 칸 표면으로만, 가짜 서버는 시험만', () => {
    expect(
      enter(
        'src/app/admin/ai-setting-modules.ts',
        '../../entities/ai-setting/api/index.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/app/admin/ai-setting-modules.ts',
        '../../entities/ai-setting/api/server.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/ai-setting-modules.ts',
        '../../entities/ai-setting/api/testing.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/app/admin/ai-setting-modules.test.ts',
        '../../entities/ai-setting/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/admin-ai-settings/ui/AiSettingsScreen.test.tsx',
        '../../../entities/ai-setting/api/testing.ts',
      ),
    ).toEqual([]);
    expect(
      enter(
        'src/pages/admin-ai-settings/ui/AiSettingsScreen.tsx',
        '../../../entities/ai-setting/model/slot.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter(
        'src/pages/greenwash-list/ui/A.tsx',
        '../../../entities/ai-setting/model/index.ts',
      ),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/ai-setting/model/index.ts'),
    ).toHaveLength(1);
    expect(
      enter('e2e/x.spec.ts', '../src/entities/ai-setting/config/text.ts'),
    ).toEqual([]);
    // 어드민 화면 폴더(칸 규칙): 칸 표면은 되고, 시험만 가짜 서버
    expect(
      violations(
        page,
        at('pages/admin-ai-settings/ui/A.tsx'),
        `import { AI_SETTING_TEXT } from "../../../entities/ai-setting/config/text.ts"; import { DEFAULT_VERSION_KEY } from "../../../entities/ai-setting/model/index.ts"; import type { PromptModelReader } from "../../../entities/ai-setting/api/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      violations(
        page,
        at('pages/admin-ai-settings/ui/A.tsx'),
        `import { fakePromptModelServer } from "../../../entities/ai-setting/api/testing.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      violations(
        page,
        at('pages/admin-ai-settings/ui/A.test.tsx'),
        `import { fakePromptModelServer } from "../../../entities/ai-setting/api/testing.ts";`,
      ),
    ).toEqual([]);
  });

  // ⓕ: 껍데기는 모듈을 import 하지 않는다(sid:MARC-ENT-386) — entities 중 ai-setting 만(허용 목록).
  it('AD-02 껍데기(pages/admin-ai-settings)는 entities 중 entities/ai-setting 만 가져온다(다른 어드민 화면은 그대로)', () => {
    const shell = (source: string, file = 'pages/admin-ai-settings/ui/A.tsx') =>
      violations(page, at(file), source);
    expect(
      shell(`import { G } from "../../../entities/greenwash/ui/index.ts";`),
    ).toContain(
      'pages/admin-ai-settings/ui/A.tsx 가 entities/greenwash/ui/index.ts 를 가져온다(AD-02 껍데기는 entities 중 entities/ai-setting/ 만)',
    );
    expect(
      shell(
        `import { x } from "../../../entities/greenwash-setting/model/index.ts";`,
      ),
    ).toContain(
      'pages/admin-ai-settings/ui/A.tsx 가 entities/greenwash-setting/model/index.ts 를 가져온다(AD-02 껍데기는 entities 중 entities/ai-setting/ 만)',
    );
    expect(
      shell(`import { x } from "../../../entities/dv-setting/model/index.ts";`),
    ).toContain(
      'pages/admin-ai-settings/ui/A.tsx 가 entities/dv-setting/model/index.ts 를 가져온다(AD-02 껍데기는 entities 중 entities/ai-setting/ 만)',
    );
    // 시험도 같다(허용 목록은 시험을 봐주지 않는다)
    expect(
      shell(
        `import { fakeGreenwashSettingServer } from "../../../entities/greenwash-setting/api/testing.ts";`,
        'pages/admin-ai-settings/ui/A.test.tsx',
      ),
    ).toContain(
      'pages/admin-ai-settings/ui/A.test.tsx 가 entities/greenwash-setting/api/testing.ts 를 가져온다(AD-02 껍데기는 entities 중 entities/ai-setting/ 만)',
    );
    expect(
      shell(`import { x } from "../../../entities/ai-setting/model/index.ts";`),
    ).toEqual([]);
    // 다른 어드민 화면은 이 허용 목록을 받지 않는다
    expect(
      violations(
        page,
        at('pages/admin-runs/ui/A.tsx'),
        `import { x } from "../../../entities/run-log/model/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      aiSettingsShellViolations(
        at('pages/admin-runs/ui/A.tsx'),
        `import { x } from "../../../entities/run-log/model/index.ts";`,
      ),
    ).toEqual([]);
  });

  // ⓖ: AD-02 의 모듈 줄. AdminRoutes 는 그 파일을 가져오고 그린워싱 AI 설정 판을 직접 모른다.
  it('모듈 줄(ai-setting-modules.ts): 두 슬라이스의 칸 표면과 Api 타입만, shared/api 는 import type 만, AdminRoutes 는 그 파일로만', () => {
    const modules = (source: string) =>
      violations(admin, at('app/admin/ai-setting-modules.ts'), source);
    expect(
      modules(
        `import { createPromptModelReader } from "../../entities/ai-setting/api/index.ts"; import { AI_SETTING_TEXT } from "../../entities/ai-setting/config/text.ts"; import { DEFAULT_VERSION_KEY } from "../../entities/ai-setting/model/index.ts"; import { createGreenwashSettingServerPort } from "../../entities/greenwash-setting/api/index.ts"; import { GREENWASH_SETTING_TEXT } from "../../entities/greenwash-setting/config/text.ts"; import type { SettingList } from "../../entities/greenwash-setting/model/index.ts"; import type { Api } from "../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
    // AS3b ①: 대상 단어 슬롯은 그린워싱 AI 설정 판의 ui 칸 표면에서
    expect(
      modules(
        `import { termsDraftSlot } from "../../entities/greenwash-setting/ui/index.ts";`,
      ),
    ).toEqual([]);
    expect(
      modules(
        `import { TermsCard } from "../../entities/greenwash-setting/ui/TermsCard.tsx";`,
      ),
    ).toHaveLength(1);
    expect(
      modules(`import { createApi } from "../../shared/api/index.ts";`),
    ).toEqual([
      'app/admin/ai-setting-modules.ts 가 ../../shared/api/index.ts 를 값으로 가져온다(Api 는 꼴만 — import type)',
    ]);
    for (const source of [
      `import { useMemo } from "react";`,
      `import { x } from "../../entities/greenwash/api/index.ts";`,
      `import { x } from "../../entities/run-log/api/index.ts";`,
      `import { x } from "../../entities/ai-setting/api/server.ts";`,
      `import { x } from "../../entities/ai-setting/api/testing.ts";`,
      `import { x } from "./AdminRoutes.tsx";`,
    ])
      expect(modules(source).length, source).toBeGreaterThan(0);
    // AdminRoutes.tsx: 모듈 줄은 되고, 두 슬라이스는 직접 모른다
    const routes = (source: string) =>
      violations(admin, at('app/admin/AdminRoutes.tsx'), source);
    expect(
      routes(`import { aiSettingModules } from "./ai-setting-modules.ts";`),
    ).toEqual([]);
    expect(
      routes(
        `import { GREENWASH_SETTING_TEXT } from "../../entities/greenwash-setting/config/text.ts";`,
      ),
    ).toHaveLength(1);
    expect(
      routes(
        `import { AI_SETTING_TEXT } from "../../entities/ai-setting/config/text.ts";`,
      ),
    ).toHaveLength(1);
    // runtime.ts 는 이제 아무것도 가져오지 않는다(옛 목 덧칠 타입 허락을 걷음 — ⓒ)
    expect(
      violations(
        admin,
        at('app/admin/runtime.ts'),
        `import type { PromptModelReader } from "../../entities/ai-setting/api/index.ts";`,
      ),
    ).toHaveLength(1);
    // 시험(ai-setting-modules.test.ts)은 두 가짜 서버와 createApi 를 쓴다
    expect(
      violations(
        admin,
        at('app/admin/ai-setting-modules.test.ts'),
        `import { describe } from "vitest"; import { aiSettingModules } from "./ai-setting-modules.ts"; import { fakePromptModelServer } from "../../entities/ai-setting/api/testing.ts"; import { fakeGreenwashSettingServer } from "../../entities/greenwash-setting/api/testing.ts"; import { createApi } from "../../shared/api/index.ts";`,
      ),
    ).toEqual([]);
  });

  // ⓔ: 규칙이 이름 대는 경로가 디스크에 있다(없는 파일 이름을 허락해 두지 않게).
  it('칸 규칙의 맨 위 파일·시험 이름과 슬라이스 경계의 폴더는 디스크에 있다', () => {
    // 맨 위 파일·시험 이름 + 그 파일이 가져와도 되는 슬라이스 안 파일(files — '*' 빼고) + parts 아닌 경계 줄의 문(doors·toolsDoors).
    const named = [
      ...SLICES.filter((rule) => !rule.parts).flatMap((rule) =>
        [
          ...Object.keys(rule.roots),
          ...rule.rootTests,
          ...Object.values(rule.roots).flatMap((root) =>
            root.files === '*' ? [] : root.files,
          ),
        ].map((name) => `${rule.dir}/${name}`),
      ),
      ...DOORS.filter((row) => !row.parts).flatMap((row) =>
        [...row.doors, ...row.toolsDoors].map((door) => `${row.dir}/${door}`),
      ),
    ];
    // 빈 검사가 아니다: app/admin 의 넷(AdminRoutes·runtime·ai-setting-modules·router.test)이 들어 있다
    expect(named).toEqual(
      expect.arrayContaining([
        'app/admin/AdminRoutes.tsx',
        'app/admin/runtime.ts',
        'app/admin/ai-setting-modules.ts',
        'app/admin/router.test.tsx',
        'app/admin/ai-setting-modules.test.ts',
      ]),
    );
    expect(named.filter((path) => !existsSync(at(path)))).toEqual([]);
    expect(
      DOORS.map((row) => row.dir).filter((dir) => !existsSync(at(dir))),
    ).toEqual([]);
    for (const segment of ['model', 'api', 'config'] as const)
      expect(existsSync(at(AI_SETTING + surfaceOf(segment))), segment).toBe(
        true,
      );
  });
});

// ───────────────────────── 4. 라우터 (밴드 RT1) ─────────────────────────

/** 라우터 패키지(@tanstack/react-router 와 그 아래 경로). */
const ROUTER_PACKAGE = /^@tanstack\/react-router(\/|$)/;

/**
 * @tanstack/react-router 는 src/main.tsx 와 src/app/** 만 가져온다. 화면(pages)·widgets·entities·shared·tools·e2e 는 모른다 —
 * 화면은 콜백 props(onBack·onViewResult·onOpen…)를 받고, 경로 컴포넌트(app/greenwash)가 navigate 로 잇는다.
 * 칸 규칙이 없는 자리(tools·e2e)도 이 규칙이 본다. apps/web 뿌리의 설정 파일(vite·playwright·vitest config)은 훑지 않는다(allFiles 는 src·tools·e2e 만).
 */
export function routerImportViolations(file: string, source: string): string[] {
  const rel = relative(webRoot, file);
  if (rel === 'src/main.tsx' || rel.startsWith('src/app/')) return [];
  return importsOf(source)
    .filter(({ target }) => ROUTER_PACKAGE.test(target))
    .map(
      ({ target }) =>
        `${rel} 가 ${target} 를 가져온다(라우터는 src/main.tsx 와 src/app/** 만 — 화면은 콜백 props 를 받고 경로 컴포넌트(app)가 잇는다)`,
    );
}

/** 진입 청크의 파일과 가져와도 되는 것(src 기준). 그린워싱 화면·pdfjs.ts·목 저장소는 정적으로 가져오지 않는다(게으르게 부른다). */
const ENTRY_RULES: Record<
  string,
  {
    packages: RegExp;
    values: string[];
    types: string[];
    dynamic: (rel: string) => boolean;
    css: boolean;
  }
> = {
  'main.tsx': {
    packages: /^(react|react-dom\/client|@tanstack\/react-router)$/,
    values: ['app/router.tsx'],
    types: [],
    dynamic: () => false,
    css: true,
  },
  'app/router.tsx': {
    packages: ROUTER_PACKAGE,
    // 가드(밴드 LG1 — critic 1 반영 B1 ①): 세션 저장소와 beforeLoad 는 화면보다 먼저 돌아 진입 청크에 든다. 로그인 화면은 게으르게(AuthRoutes).
    values: ['app/auth/guard.ts'],
    types: [
      'app/greenwash/runtime.ts',
      'widgets/doc-viewer/index.ts',
      'app/admin/runtime.ts',
      // [TRW1a ②] 영문번역 router context 의 꼴(타입만).
      'app/translation/runtime.ts',
      // [DV2a ②] 데이터 검증 router context 의 꼴(타입만).
      'app/dataverify/runtime.ts',
      // [IRW1 ②] 중대성평가 router context 의 꼴(타입만).
      'app/materiality/runtime.ts',
    ],
    dynamic: (rel) =>
      rel === 'app/greenwash/GreenwashRoutes.tsx' ||
      // [TRW1a ②] 영문번역 틀(게으르게).
      rel === 'app/translation/TranslationRoutes.tsx' ||
      // [DV2a ②] 데이터 검증 틀(게으르게).
      rel === 'app/dataverify/DataverifyRoutes.tsx' ||
      // [IRW1 ②] 중대성평가 틀(게으르게).
      rel === 'app/materiality/MaterialityRoutes.tsx' ||
      // [W12-0a ②] 온실가스 틀(게으르게).
      rel === 'app/ghg/GhgRoutes.tsx' ||
      // [S3W1 ③] 온실가스 Scope 3 경로(게으르게).
      rel === 'app/ghg/Scope3Routes.tsx' ||
      // [RPW1 ① A4] 원고작성 틀(게으르게).
      rel === 'app/drafting/DraftingRoutes.tsx' ||
      rel === 'app/auth/AuthRoutes.tsx' ||
      rel === 'app/admin/AdminRoutes.tsx' ||
      /^pages\/demo-[a-z]+\/[A-Za-z]+\.tsx$/.test(rel),
    css: false,
  },
};
/**
 * 진입 청크 파일(main.tsx·app/router.tsx) 하나의 위반. import 는 importsOf 로 찾는다(정적 값·타입·게으른 import 를 가른다).
 * 못 보는 것: import.meta.glob·new URL(…, import.meta.url) 꼴 — 빌드 표식 검사(scripts/check-no-demos.sh)와 진입 청크 글자 확인이 지킨다.
 */
export function entryViolations(file: string, source: string): string[] {
  const rel = relative(src, file);
  const rule = ENTRY_RULES[rel];
  if (!rule) return [];
  const problems: string[] = [];
  const check = (target: string, kind: 'value' | 'type' | 'dynamic') => {
    if (!target.startsWith('.')) {
      if (!rule.packages.test(target))
        problems.push(`${rel} 가 ${target} 를 가져온다(진입 청크)`);
      return;
    }
    if (CSS.test(target)) {
      if (!rule.css) problems.push(`${rel} 가 CSS 를 가져온다: ${target}`);
      return;
    }
    const to = relative(src, resolve(dirname(file), target));
    const ok =
      kind === 'dynamic' ? rule.dynamic(to)
      : kind === 'type' ? rule.types.includes(to) || rule.values.includes(to)
      : rule.values.includes(to);
    if (!ok)
      problems.push(
        kind === 'dynamic' ?
          `${rel} 가 ${to} 를 게으르게 가져온다(진입 청크가 부를 수 있는 화면이 아니다)`
        : `${rel} 가 ${to} 를 정적으로 가져온다(진입 청크 — 화면·pdfjs.ts·목 저장소는 lazyRouteComponent 로 게으르게)`,
      );
  };
  for (const { target, typeOnly, dynamic } of importsOf(source))
    check(
      target,
      dynamic ? 'dynamic'
      : typeOnly ? 'type'
      : 'value',
    );
  return problems;
}

describe('구조 규칙 — 4. 라우터', () => {
  it('@tanstack/react-router 는 src/main.tsx 와 src/app/** 만 가져온다(src·tools·e2e 전부를 훑는다). 빈 검사가 아니다', () => {
    const all = allFiles();
    expect(
      all.flatMap((file) => routerImportViolations(file, read(file))),
    ).toEqual([]);
    const users = all.filter((file) =>
      importsOf(read(file)).some(({ target }) => ROUTER_PACKAGE.test(target)),
    );
    expect(users.map((file) => relative(webRoot, file)).sort()).toEqual(
      expect.arrayContaining([
        'src/app/greenwash/GreenwashRoutes.tsx',
        'src/app/router.tsx',
        'src/main.tsx',
      ]),
    );
  });

  it('진입 청크(main.tsx·app/router.tsx)는 그린워싱 화면·pdfjs.ts·목 저장소를 정적으로 가져오지 않는다', () => {
    for (const rel of Object.keys(ENTRY_RULES))
      expect(entryViolations(at(rel), read(at(rel))), rel).toEqual([]);
  });

  it('규칙이 실제로 잡는다: 칸 규칙이 없는 자리(e2e·tools)와 화면의 라우터 import 는 새 규칙의 글로 빨강', () => {
    const line = `import { useNavigate } from '@tanstack/react-router';`;
    expect(
      routerImportViolations(join(webRoot, 'e2e/x.spec.ts'), line),
    ).toEqual([
      'e2e/x.spec.ts 가 @tanstack/react-router 를 가져온다(라우터는 src/main.tsx 와 src/app/** 만 — 화면은 콜백 props 를 받고 경로 컴포넌트(app)가 잇는다)',
    ]);
    expect(
      routerImportViolations(join(webRoot, 'tools/x.ts'), line),
    ).toHaveLength(1);
    expect(
      routerImportViolations(at('pages/greenwash-list/ui/A.tsx'), line),
    ).toHaveLength(1);
    expect(
      routerImportViolations(
        at('shared/ui/x/ui/a.tsx'),
        `const r = await import("@tanstack/react-router/x");`,
      ),
    ).toHaveLength(1);
    // 되는 것: main.tsx 와 app 아래, 다른 TanStack 패키지
    expect(routerImportViolations(at('main.tsx'), line)).toEqual([]);
    expect(routerImportViolations(at('app/greenwash/a.tsx'), line)).toEqual([]);
    expect(
      routerImportViolations(
        at('pages/greenwash-list/ui/A.tsx'),
        `import { useQuery } from '@tanstack/react-query';`,
      ),
    ).toEqual([]);
  });

  it('규칙이 실제로 잡는다: 진입 청크의 정적 import', () => {
    const router = (source: string) =>
      entryViolations(at('app/router.tsx'), source);
    expect(
      router(
        `import { createRouter } from "@tanstack/react-router"; import type { AppRouterContext } from "./greenwash/runtime.ts"; import type { OpenPdf } from "../widgets/doc-viewer/index.ts"; const a = () => import("./greenwash/GreenwashRoutes.tsx"); const b = () => import("../pages/demo-viewer/App.tsx");`,
      ),
    ).toEqual([]);
    expect(
      router(
        `import { GreenwashLayout } from "./greenwash/GreenwashRoutes.tsx";`,
      ),
    ).toEqual([
      'app/router.tsx 가 app/greenwash/GreenwashRoutes.tsx 를 정적으로 가져온다(진입 청크 — 화면·pdfjs.ts·목 저장소는 lazyRouteComponent 로 게으르게)',
    ]);
    expect(
      router(`import { openPdf } from "../widgets/doc-viewer/pdfjs.ts";`),
    ).toHaveLength(1);
    expect(
      router(
        `import { MOCK_SCENARIOS } from "../entities/greenwash/api/mock/index.ts";`,
      ),
    ).toHaveLength(1);
    expect(router(`import { A } from "./greenwash/runtime.ts";`)).toHaveLength(
      1,
    );
    expect(
      router(`import { App } from "../pages/demo-viewer/App.tsx";`),
    ).toHaveLength(1);
    expect(
      router(`const m = () => import("../widgets/doc-viewer/pdfjs.ts");`),
    ).toHaveLength(1);
    expect(
      router(`import { useQuery } from "@tanstack/react-query";`),
    ).toHaveLength(1);
    const main = (source: string) => entryViolations(at('main.tsx'), source);
    expect(
      main(
        `import { StrictMode } from "react"; import { createAppRouter } from "./app/router.tsx"; import "./app/styles/app.css";`,
      ),
    ).toEqual([]);
    expect(
      main(`import { L } from "./pages/greenwash-list/index.ts";`),
    ).toHaveLength(1);
    expect(
      main(`const p = () => import("./app/greenwash/GreenwashRoutes.tsx");`),
    ).toHaveLength(1);
  });
});
