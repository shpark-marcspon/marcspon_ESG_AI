// EDK 키트 부품을 들인 범위를 지킨다(밴드 FK1, 사용자 결정 2026-10-15: 컴포넌트는 25 만).
//
//   1) apps/web/src 가 `@marcspon/ui/…` 에서 가져오는 것은 아래 25 부품과 lib/utils 뿐이다.
//      button·table-empty 는 키트 것을 쓰지 않고 다시 만들 부품이다(빨강). 목록 밖의 다른 이름도 빨강.
//   2) packages/ui/src/components/ 의 파일은 26 이다(25 + scroll-up-button 이 끌고 오는 button).
//      키트 파일을 하나 더 옮겨 오면 빨강이다.
// 파일을 글자로 읽어 import 문을 찾는다(app/guards/layers.test.ts 와 같은 방식). 주석은 지우고 읽는다.
// 못 잡는 것: 문자열을 조립한 import, 별칭(tsconfig paths)으로 우회한 import, 이 파일 자신(고정물 문자열이 import 처럼 보여 검사에서 뺀다).
//
// 지금은 화면이 키트를 쓰지 않는다. 검사가 빈 채로 초록이 되지 않게 고정물(문자열)로 「목록 밖이면 빨강」을 직접 보인다.
// 무효 조건: 업무 부품이나 다시 만든 부품을 packages/ui 에 들이게 되면(사용자 결정이 바뀌면) 목록과 26 을 같은 커밋에서 고친다.
import { readFileSync, readdirSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, '../../..');
const uiComponents = resolve(webRoot, '../../packages/ui/src/components');

/** 들이기로 한 부품 25. 그대로 22 + 감싸기 2(tooltip·tabs) + dialog(Header·Body·Footer·Close 를 쓴다). */
export const ALLOWED_COMPONENTS = [
  'accordion',
  'badge',
  'checkbox',
  'dialog',
  'dots-three-vertical-icon',
  'dropdown-menu',
  'edit-icon',
  'form',
  'icon',
  'input',
  'label',
  'radio-group',
  'scroll-up-button',
  'search-input',
  'sheet',
  'skeleton',
  'sort-indicator',
  'spinner',
  'switch',
  'table',
  'table-skeleton',
  'tabs',
  'textarea',
  'tooltip',
  'xls-icon',
] as const;
const ALLOWED = new Set<string>([
  ...ALLOWED_COMPONENTS.map((name) => `@marcspon/ui/components/${name}`),
  '@marcspon/ui/lib/utils',
]);
/** packages/ui/src/components/ 에 있어야 하는 파일 수: 25 + button. */
const KIT_COMPONENT_FILES = 26;

const withoutComments = (source: string) =>
  source.replace(/\/\/.*|\/\*[\s\S]*?\*\//g, '');

/** 파일이 가져오는 것들: `from "x"`, `import "x"`, `import("x")`, `require("x")`. */
function importsOf(source: string): string[] {
  const found: string[] = [];
  for (const match of withoutComments(source).matchAll(
    /(?:\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)["'`]([^"'`]+)["'`]/g,
  ))
    found.push(match[1]!);
  return found;
}

/** 한 파일에서 허용 목록 밖의 `@marcspon/ui` import 를 찾는다. 테스트가 규칙 자체도 시험할 수 있게 함수로 뺐다. */
export function disallowedKitImports(source: string): string[] {
  return importsOf(source).filter(
    (target) =>
      (target === '@marcspon/ui' || target.startsWith('@marcspon/ui/')) &&
      !ALLOWED.has(target),
  );
}

function filesUnder(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return filesUnder(path);
    return /\.(ts|tsx)$/.test(entry.name) ? [path] : [];
  });
}

/** 허용 목록 안의 import 만 든 고정물. 여기에 목록 밖의 한 줄(예: components/button)을 넣으면 아래 「고정물은 초록」이 빨강이 된다. */
const ALLOWED_FIXTURE = `
import { Badge } from "@marcspon/ui/components/badge";
import { Dialog, DialogHeader } from "@marcspon/ui/components/dialog";
import { cn } from "@marcspon/ui/lib/utils";
`;

describe('EDK 키트 부품을 들인 범위', () => {
  it('고정물: 허용 목록 안의 import 만 있으면 초록', () => {
    expect(disallowedKitImports(ALLOWED_FIXTURE)).toEqual([]);
  });

  it('고정물: 다시 만들 부품(button·table-empty)과 목록 밖의 경로는 빨강', () => {
    const source = `
import { Button } from "@marcspon/ui/components/button";
import { TableEmpty } from '@marcspon/ui/components/table-empty';
import { Select } from "@marcspon/ui/components/select";
import { useDisclosure } from "@marcspon/ui/hooks/use-disclosure";
const lazy = import("@marcspon/ui/components/slider");
// import { Ignored } from "@marcspon/ui/components/button";  ← 주석은 세지 않는다
import { Badge } from "@marcspon/ui/components/badge";
`;
    expect(disallowedKitImports(source)).toEqual([
      '@marcspon/ui/components/button',
      '@marcspon/ui/components/table-empty',
      '@marcspon/ui/components/select',
      '@marcspon/ui/hooks/use-disclosure',
      '@marcspon/ui/components/slider',
    ]);
  });

  it('apps/web/src 는 허용 목록 밖의 @marcspon/ui 를 가져오지 않는다', () => {
    const self = fileURLToPath(import.meta.url);
    const problems = filesUnder(resolve(webRoot, 'src'))
      .filter((file) => file !== self)
      .flatMap((file) =>
        disallowedKitImports(readFileSync(file, 'utf8')).map(
          (target) => `${relative(webRoot, file)}: ${target}`,
        ),
      );
    expect(problems).toEqual([]);
  });

  it('타입 검사 파일(kit-typecheck.tsx)이 25 부품을 모두 가져온다', () => {
    const imported = importsOf(
      readFileSync(resolve(here, 'kit-typecheck.tsx'), 'utf8'),
    );
    const missing = ALLOWED_COMPONENTS.filter(
      (name) => !imported.includes(`@marcspon/ui/components/${name}`),
    );
    expect(missing).toEqual([]);
  });

  it(`packages/ui/src/components/ 의 파일은 ${KIT_COMPONENT_FILES} 이다(25 + button)`, () => {
    const files = readdirSync(uiComponents).sort();
    expect(files).toHaveLength(KIT_COMPONENT_FILES);
    expect(files).toEqual(
      [...ALLOWED_COMPONENTS.map((name) => `${name}.tsx`), 'button.tsx'].sort(),
    );
  });
});
