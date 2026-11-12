// 글자 자리 → 상자. 작은 가짜 글자 자리로 본다. 실제 자료는 쓰지 않는다.
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

import { LabInputError, loadSide } from './load.ts';
import {
  charPlacesSchema,
  indexPlaces,
  sameSource,
  spanBoxes,
} from './places.ts';
import type { CharPlaces, PlaceContainer } from './places.ts';

// 글 「합계 59,498명 (전년 대비 3%)」 가 두 줄로 놓인 그릇. 첫 줄 「합계 59,498명」(0~9), 줄을 이은 빈칸(10, 좌표 없음), 둘째 줄 「(전년 대비 3%)」(11~21).
// 숫자는 지어낸 것이다.
const TEXT = '합계 59,498명 (전년 대비 3%)';
const container: PlaceContainer = {
  id: 'p1-b1',
  kind: 'block',
  page: 1,
  bbox: [100, 50, 190, 82],
  runs: [
    {
      start: 0,
      y0: 50,
      y1: 62,
      x0: [100, 112, 124, 128, 134, 140, 143, 149, 155, 161],
      x1: [112, 124, 128, 134, 140, 143, 149, 155, 161, 173],
    },
    {
      start: 11,
      y0: 70,
      y1: 82,
      x0: [100, 104, 116, 128, 132, 144, 156, 160, 166, 176],
      x1: [104, 116, 128, 132, 144, 156, 160, 166, 176, 180],
    },
  ],
};

describe('spanBoxes', () => {
  it('글자 범위의 상자: 한글에 붙은 숫자는 숫자만 덮는다', () => {
    // 「59,498」 은 글의 3~9번째 자리다. 뒤의 「명」(9번째)은 들지 않는다.
    expect(TEXT.slice(3, 9)).toBe('59,498');
    expect(spanBoxes(container, 3, 9)).toEqual({
      boxes: [[128, 50, 161, 62]],
      covered: 6,
    });
  });
  it('시작 자리가 하나 밀리면 상자도 한 글자만큼 밀린다(자리와 상자가 1:1 이다)', () => {
    expect(spanBoxes(container, 4, 10).boxes).toEqual([[134, 50, 173, 62]]);
    expect(spanBoxes(container, 2, 8).boxes).toEqual([[124, 50, 155, 62]]);
  });
  it('범위를 안 주면 그릇의 글 전체: 줄마다 상자 하나', () => {
    expect(spanBoxes(container)).toEqual({
      boxes: [
        [100, 50, 173, 62],
        [100, 70, 180, 82],
      ],
      covered: 20,
    });
  });
  it('범위가 두 줄에 걸치면 상자가 둘이다. 둘을 감싸는 큰 상자 하나가 아니다. 줄을 이은 빈칸에는 좌표가 없다', () => {
    // 「498명 (전년」: 6~14번째 자리. 첫 줄의 498명, 빈칸, 둘째 줄의 (전년.
    expect(TEXT.slice(6, 14)).toBe('498명 (전년');
    expect(spanBoxes(container, 6, 14)).toEqual({
      boxes: [
        [143, 50, 173, 62],
        [100, 70, 128, 82],
      ],
      covered: 7,
    });
  });
  it('한 줄 안에서 세로 범위가 조금 다른 토막(글자 크기가 다른 조각)은 한 상자로 묶는다', () => {
    const mixed: PlaceContainer = {
      ...container,
      runs: [
        { start: 0, y0: 50, y1: 62, x0: [100, 110], x1: [110, 120] },
        { start: 2, y0: 52, y1: 61, x0: [120, 128], x1: [128, 136] }, // 같은 줄의 작은 글자
        { start: 5, y0: 70, y1: 82, x0: [100], x1: [110] }, // 다음 줄
      ],
    };
    expect(spanBoxes(mixed).boxes).toEqual([
      [100, 50, 136, 62],
      [100, 70, 110, 82],
    ]);
  });
  it('줄 사이가 좁아 위아래 줄의 세로 범위가 조금 겹쳐도 다른 줄이다. 상자를 하나로 뭉치지 않는다', () => {
    // 줄 높이 12 에 겹친 높이 2. 한 줄로 보려면 겹친 높이가 낮은 쪽 높이의 절반을 넘어야 한다.
    const tight: PlaceContainer = {
      ...container,
      runs: [
        { start: 0, y0: 50, y1: 62, x0: [160, 170], x1: [170, 180] },
        { start: 3, y0: 60, y1: 72, x0: [100, 110], x1: [110, 120] }, // 다음 줄. 윗줄의 아래 끝과 2 만큼 겹친다
      ],
    };
    expect(spanBoxes(tight).boxes).toEqual([
      [160, 50, 180, 62],
      [100, 60, 120, 72],
    ]);
  });
  it('범위에 좌표 있는 글자가 없으면 상자가 없다', () => {
    expect(spanBoxes(container, 10, 11)).toEqual({ boxes: [], covered: 0 });
    expect(spanBoxes(container, 40, 45)).toEqual({ boxes: [], covered: 0 });
  });
  it('자리의 단위는 UTF-16 자리다: 보충 평면 글자(이모지)는 두 자리를 차지한다', () => {
    const text = '가😀12';
    expect(text.length).toBe(5);
    const emoji: PlaceContainer = {
      ...container,
      runs: [
        {
          start: 0,
          y0: 0,
          y1: 10,
          x0: [0, 10, 10, 20, 26],
          x1: [10, 20, 20, 26, 32],
        },
      ],
    };
    expect(text.slice(3, 5)).toBe('12');
    expect(spanBoxes(emoji, 3, 5).boxes).toEqual([[20, 0, 32, 10]]);
  });
  it('토막이 아주 길어도 된다(글자 수만큼 인자를 펼치지 않는다)', () => {
    const n = 300_000;
    const long: PlaceContainer = {
      ...container,
      runs: [
        {
          start: 0,
          y0: 0,
          y1: 10,
          x0: Array.from({ length: n }, (_, k) => k),
          x1: Array.from({ length: n }, (_, k) => k + 1),
        },
      ],
    };
    expect(spanBoxes(long).boxes).toEqual([[0, 0, n, 10]]);
  });
});

// ── 파일에서 읽기: 해시가 다르면 멈춘다, 글자 자리가 없으면 없는 채로 읽는다 ──
describe('loadSide', () => {
  const hashA = 'a'.repeat(64);
  const hashB = 'b'.repeat(64);
  const document = (sha256: string) => ({
    source: { sha256 },
    pages: [{ page: 1, width: 600, height: 800 }],
    blocks: [],
    tables: [],
  });
  const charPlaces = (sha256: string): CharPlaces => ({
    schema_version: '0.1',
    source: { sha256 },
    unit: 'utf16',
    containers: [container],
    unlinked: [],
  });
  const dirs: string[] = [];
  const saved = { ...process.env };

  /** 임시 폴더에 산출물 꼴로 파일을 놓고 환경 변수를 맞춘다. places 를 안 주면 글자 자리 파일을 만들지 않는다. */
  function arrange(places?: CharPlaces) {
    const root = mkdtempSync(join(tmpdir(), 'web-places-test-'));
    dirs.push(root);
    mkdirSync(join(root, 'out', 'parse-doc'), { recursive: true });
    writeFileSync(
      join(root, 'out', 'parse-doc', 'document.json'),
      JSON.stringify(document(hashA)),
    );
    if (places) {
      mkdirSync(join(root, 'places', 'parse-doc'), { recursive: true });
      writeFileSync(
        join(root, 'places', 'parse-doc', 'char-places.json'),
        JSON.stringify(places),
      );
    }
    Object.assign(process.env, {
      ESG_LAB_OUT: join(root, 'out'),
      ESG_REPORTS: join(root, 'reports'),
      VIEWER_DOC_A: 'doc',
      VIEWER_PLACES: join(root, 'places'),
    });
    delete process.env.VIEWER_EXAM;
  }
  afterEach(() => {
    for (const dir of dirs.splice(0))
      rmSync(dir, { recursive: true, force: true });
    for (const key of Object.keys(process.env))
      if (!(key in saved)) delete process.env[key];
    Object.assign(process.env, saved);
  });

  it('글자 자리와 문서 모델의 원본 해시가 같으면 읽는다', () => {
    arrange(charPlaces(hashA));
    const side = loadSide('a');
    expect(side.places?.get('p1-b1')?.page).toBe(1);
    expect(side.placesPath).toContain('char-places.json');
  });
  it('해시가 다르면 멈춘다(다른 PDF 의 글자 자리로 상자를 치지 않는다)', () => {
    arrange(charPlaces(hashB));
    expect(() => loadSide('a')).toThrow(LabInputError);
    expect(() => loadSide('a')).toThrow(/서로 다른 PDF/);
  });
  it('글자 자리 파일이 없으면 없는 채로 읽는다(변환은 좁은 상자 없이 간다)', () => {
    arrange();
    const side = loadSide('a');
    expect(side.places).toBeUndefined();
    expect(side.placesPath).toBeNull();
  });
  it('sameSource, 그리고 꼴이 다른 파일은 받지 않는다', () => {
    expect(sameSource(document(hashA), charPlaces(hashA))).toBe(true);
    expect(sameSource(document(hashA), charPlaces(hashB))).toBe(false);
    expect(
      charPlacesSchema.safeParse({ ...charPlaces(hashA), unit: 'codepoint' })
        .success,
    ).toBe(false);
    expect(
      charPlacesSchema.safeParse({
        ...charPlaces(hashA),
        schema_version: '0.2',
      }).success,
    ).toBe(false);
    expect(indexPlaces(charPlaces(hashA)).size).toBe(1);
  });
});
