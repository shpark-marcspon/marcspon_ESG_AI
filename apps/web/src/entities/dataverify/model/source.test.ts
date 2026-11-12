// 입력 출처(밴드 DV2b — 발주서 §3): 이름 거울이 고정 스키마 pattern 과 글자째 같고, 서버 규칙대로 거절하며, 옵션 셈에 source 가 든다.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import type { EdkData } from './edk.ts';
import {
  OPTIONS_MAX_OCTETS,
  buildInput,
  buildOptions,
  isTooLarge,
  pyJson,
  pyJsonOctets,
} from './options.ts';
import {
  PASTE_SOURCE,
  SOURCE_NAME_MAX,
  SOURCE_NAME_PATTERN,
  fileSource,
  isSourceName,
} from './source.ts';
import { FAKE_COMPANY, edkItem } from './testing.ts';

// 백엔드 고정 파일을 읽기만 한다(옮기지 않는다).
const schema = JSON.parse(
  readFileSync(
    resolve(
      dirname(fileURLToPath(import.meta.url)),
      '../../../../../api-py/esgapi/dataverify/tests/data/flow-shapes/options/dataverify.options@1.schema.json',
    ),
    'utf8',
  ),
) as {
  $defs: Record<
    string,
    { properties: Record<string, { pattern?: string; maxLength?: number }> }
  >;
};

describe('출처 이름 거울', () => {
  it('pattern·길이 상한이 options@1.schema.json 과 같다', () => {
    const name = schema.$defs.DataverifyFileSource!.properties.name!;
    expect(SOURCE_NAME_PATTERN).toBe(name.pattern);
    expect(SOURCE_NAME_MAX).toBe(name.maxLength);
    expect(Object.keys(schema.$defs.DataverifyPasteSource!.properties)).toEqual(
      ['kind'],
    );
  });

  it('받는 이름 · 거절하는 이름(`/`·`\\`·C0·DEL·C1·양방향 제어·빈 이름·256자)', () => {
    for (const ok of [
      'EDK_정량데이터_2025.json',
      'a',
      'x.JSON',
      '공백 있는 이름.txt',
      '😀'.repeat(255),
    ])
      expect(isSourceName(ok), ok).toBe(true);
    for (const bad of [
      '',
      'a/b.json',
      'a\\b.json',
      'a\u0000b',
      'tab\there',
      'del\u007f',
      'c1\u0085',
      'alm؜',
      'lrm‎',
      'rlo‮',
      'fsi⁨',
      'x'.repeat(256),
      '😀'.repeat(256),
    ])
      expect(isSourceName(bad), JSON.stringify(bad)).toBe(false);
  });
});

describe('options 에 source', () => {
  const input = buildInput(FAKE_COMPANY, {
    환경: [edkItem()],
  } as unknown as EdkData);

  it('source 를 주면 {input, source}, 안 주면 {input}', () => {
    expect(Object.keys(buildOptions(input))).toEqual(['input']);
    expect(buildOptions(input, fileSource('a.json'))).toEqual({
      input,
      source: { kind: 'file', name: 'a.json' },
    });
    expect(buildOptions(input, PASTE_SOURCE).source).toEqual({ kind: 'paste' });
  });

  it('셈에 source 가 든다 — 경계: source 없이 상한, 있으면 넘음', () => {
    const at = (memo: string) =>
      buildInput(FAKE_COMPANY, {
        환경: [edkItem({ 메모: memo })],
      } as unknown as EdkData);
    const base = pyJsonOctets(buildOptions(at('')));
    const exact = at('x'.repeat(OPTIONS_MAX_OCTETS - base));
    expect(pyJsonOctets(buildOptions(exact))).toBe(OPTIONS_MAX_OCTETS);
    expect(isTooLarge(buildOptions(exact))).toBe(false);
    expect(isTooLarge(buildOptions(exact, PASTE_SOURCE))).toBe(true);
    // 파이썬 꼴 그대로: , "source": {"kind": "paste"}
    expect(
      pyJsonOctets(buildOptions(exact, PASTE_SOURCE)) -
        pyJsonOctets(buildOptions(exact)),
    ).toBe(', "source": {"kind": "paste"}'.length);
  });

  it('값이 undefined 인 열쇠는 셈에서 빠진다(JSON.stringify 와 같음 — DV2a 가지 리뷰 후속)', () => {
    expect(pyJson({ a: 1, b: undefined })).toBe('{"a": 1}');
    expect(pyJson({ a: 1, b: undefined })).toBe(
      pyJson(JSON.parse(JSON.stringify({ a: 1, b: undefined }))),
    );
    expect(pyJson([undefined])).toBe('[null]');
  });
});
