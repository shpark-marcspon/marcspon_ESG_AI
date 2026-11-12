// layout@1 거울(밴드 TRW6 ① S1): 고정 파일(서버 정본)의 `$defs` 칸 이름 == 거울 칸 이름(G8 전 「LayoutX」·후 「TranslationLayoutX」 둘 다) ·
// TRS3 §1-2 예(done)·거절 예 통과 · 안쪽 모르는 키 거절 · 맨 위 모르는 키는 버림.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { fakeLayout, fakeRejectedLayout } from '../testing.ts';
import { parseLayout } from './index.ts';
import { LAYOUT_DEFS, LAYOUT_ROOT_KEYS } from './layout.ts';

const SCHEMA = fileURLToPath(
  new URL(
    '../../../../../../api-py/esgapi/translation/tests/data/flow-shapes/translation.layout@1.schema.json',
    import.meta.url,
  ),
);
const schema = JSON.parse(readFileSync(SCHEMA, 'utf8')) as {
  $defs: Record<string, { properties: Record<string, unknown> }>;
};
/** G8(TRS3) 뒤에는 이름이 TranslationLayout… 접두 — 둘 다 받는다. */
const defOf = (name: string) =>
  schema.$defs[name] ??
  schema.$defs[`Translation${name}`] ??
  schema.$defs[`TranslationLayout${name}`];

describe('layout@1 거울', () => {
  it('칸 이름이 고정 파일의 $defs 와 같다', () => {
    expect(LAYOUT_ROOT_KEYS.sort()).toEqual(
      Object.keys(schema.$defs.TranslationLayout!.properties).sort(),
    );
    for (const [name, mirror] of Object.entries(LAYOUT_DEFS)) {
      if (mirror === null) continue;
      const def = defOf(name);
      expect(def, name).toBeDefined();
      expect(Object.keys(mirror.shape).sort(), name).toEqual(
        Object.keys(def!.properties).sort(),
      );
    }
  });

  it('§1-2 예(done)를 지나 화면 꼴로 줄인다', () => {
    const parsed = parseLayout(fakeLayout());
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.value.status).toBe('done');
    expect(parsed.value.units).toHaveLength(3);
    expect(parsed.value.variants[0]!.units[1]!.level).toBe('cell');
    expect(Object.keys(parsed.value).sort()).toEqual(
      ['pages', 'skipped', 'status', 'units', 'variants', 'warnings'].sort(),
    );
  });

  it('거절 예(variants 빈 목록·파서 null)를 지난다', () => {
    const parsed = parseLayout(fakeRejectedLayout());
    expect(parsed.ok).toBe(true);
    if (parsed.ok) expect(parsed.value.variants).toEqual([]);
  });

  it('안쪽 모르는 키는 거절, 맨 위 모르는 키는 버림', () => {
    const inner = fakeLayout();
    (inner.pages as Record<string, unknown>[])[0]!.extra = 1;
    expect(parseLayout(inner).ok).toBe(false);
    const top = { ...fakeLayout(), extra: 1 };
    expect(parseLayout(top).ok).toBe(true);
  });

  it('level·좌표 꼴이 틀리면 거절', () => {
    const bad = fakeLayout();
    (
      (bad.variants as Record<string, unknown>[])[0]!.units as Record<
        string,
        unknown
      >[]
    )[0]!.level = 'paragraph';
    expect(parseLayout(bad).ok).toBe(false);
    const box = fakeLayout();
    (
      (box.units as Record<string, unknown>[])[0]!.members as Record<
        string,
        unknown
      >[]
    )[0]!.bbox = [1, 2, 3];
    expect(parseLayout(box).ok).toBe(false);
  });

  // 검증 권고 R2(TRW6 ②): 고정 파일의 $defs 이름 전부가 거울 묶음에 있다(빠진 칸 묶음은 견주지 못한다).
  it('고정 파일의 $defs 이름 전부가 LAYOUT_DEFS 에 있다', () => {
    const mirrored = new Set(
      Object.keys(LAYOUT_DEFS).map((name) => defOf(name)),
    );
    for (const [name, def] of Object.entries(schema.$defs))
      expect(mirrored.has(def), name).toBe(true);
  });

  // 검증 권고 R1(TRW6 ②): null 을 받는 칸(cells bbox · warning page/tag/variant · member key)을 null 로 둔 layout 이 지난다.
  it('null 을 받는 칸을 null 로 둔 layout 이 지난다', () => {
    const value = fakeLayout();
    const units = value.units as Record<string, unknown>[];
    (units[0]!.members as Record<string, unknown>[])[0]!.key = null;
    (units[1]!.cells as Record<string, unknown>[])[0]!.bbox = null;
    value.warnings = [
      { code: 'tag_missing', page: null, tag: null, variant: null },
    ];
    const parsed = parseLayout(value);
    expect(parsed.ok).toBe(true);
    if (!parsed.ok) return;
    expect(parsed.value.units[0]!.members[0]!.key).toBeNull();
    expect(parsed.value.units[1]!.cells![0]!.bbox).toBeNull();
    expect(parsed.value.warnings[0]).toMatchObject({
      page: null,
      tag: null,
      variant: null,
    });
  });
});
