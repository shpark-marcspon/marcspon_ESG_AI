// 옵션 크기 셈(밴드 DV2a ① — 발주서 §3-1-2 · ★A). 서버는 파이썬 json.dumps(ensure_ascii=False) 기본 구분자의 UTF-8 바이트로 잰다.
import { describe, expect, it } from 'vitest';

import {
  OPTIONS_MAX_OCTETS,
  buildInput,
  buildOptions,
  isTooLarge,
  pyJson,
  pyJsonOctets,
  pyNumber,
} from './options.ts';
import { FAKE_COMPANY, edkData } from './testing.ts';

// ★A: 이 글을 JSON.parse 한 입력을 {input} 으로 감싸 JSON.stringify 로 보낸 것을 서버가 json.loads 한 뒤 잰 바이트.
//   잰 법(2026-10-23, 러너): node 로 JSON.stringify(JSON.parse(글)) → apps/api-py 에서
//   `uv run python -c` 꼴로 len(json.dumps({"input": json.loads(글)}, ensure_ascii=False).encode()) = 1008 (stringify 셈은 930).
//   입력 꼴은 apps/api-py/esgapi/dataverify/tests/contracts/test_shapes.py:61 an_input() 을 따랐고 수 꼴 넷을 더했다.
const MEASURED_TEXT = String.raw`{"schemaVersion":"dataverify.input@1","company":{"name":"가상건설","sasbIndustry":"Engineering & Construction Services","materialTopics":["기후변화 대응","안전보건"],"reportingYear":"2025"},"data":{"환경":[{"ID":"E-001","테마":"환경","항목":"기후변화","대분류":"온실가스 배출량","중분류":"직접 배출량","소분류":"Scope 1","입력 방식":"직접 입력","단위":"tCO2eq","values":{"2022":"1,200","2023":1300,"2024":null,"2025":" 12 "},"핵심데이터":"Y","메모":""},{"ID":2,"테마":"환경","항목":"기후변화","대분류":"온실가스 배출량","중분류":"직접 배출량","소분류":"Scope 1","입력 방식":"직접 입력","단위":"tCO2eq","values":{"2022":0.00001,"2023":123.45,"2024":1e+21,"2025":0.0001,"2026":1200.0,"2027":1e16},"핵심데이터":"N","메모":"줄\n바꿈 \"따옴\" \\ \u0001","담당자":"가상 담당"}],"사회":[]}}`;
const PYTHON_OCTETS = 1008;
const STRINGIFY_OCTETS = 930;

const octets = (text: string) => new TextEncoder().encode(text).length;

describe('pyJsonOctets — 서버 셈', () => {
  it('★A: 파이썬이 잰 바이트와 같고 JSON.stringify 셈과 다르다', () => {
    const options = { input: JSON.parse(MEASURED_TEXT) as unknown };
    expect(pyJsonOctets(options)).toBe(PYTHON_OCTETS);
    expect(octets(JSON.stringify(options))).toBe(STRINGIFY_OCTETS);
  });

  it('구분자는 ", "·": " 이다', () => {
    expect(pyJson({ a: [1, 2], b: null })).toBe('{"a": [1, 2], "b": null}');
    expect(pyJson([])).toBe('[]');
    expect(pyJson({})).toBe('{}');
    expect(pyJson([true, false])).toBe('[true, false]');
  });

  it('한글은 글자당 3바이트(ensure_ascii=False)', () => {
    expect(pyJson('환경')).toBe('"환경"');
    expect(pyJsonOctets('환경')).toBe(8);
  });

  it('글자 escape 는 파이썬 꼴', () => {
    expect(pyJson('a"b\\c\nd\te\u0001')).toBe('"a\\"b\\\\c\\nd\\te\\u0001"');
  });

  it.each([
    [0.00001, '1e-05'],
    [0.0001, '0.0001'],
    [123.45, '123.45'],
    [1e21, '1e+21'],
    [1.5e-7, '1.5e-07'],
    [1e16, '10000000000000000'],
    [1200, '1200'],
    [-0, '0'],
    [-2.5, '-2.5'],
    [1e15 + 0.5, '1000000000000000.5'],
    [5e-324, '5e-324'],
    [1.7976931348623157e308, '1.7976931348623157e+308'],
  ])('수 %s → %s', (value, text) => expect(pyNumber(value)).toBe(text));

  it('상한은 「>」: 같으면 보내고 하나 넘으면 막는다', () => {
    const at = (n: number) => {
      const base = pyJsonOctets({ input: '' });
      return { input: 'x'.repeat(n - base) };
    };
    expect(pyJsonOctets(at(OPTIONS_MAX_OCTETS))).toBe(OPTIONS_MAX_OCTETS);
    expect(isTooLarge(at(OPTIONS_MAX_OCTETS))).toBe(false);
    expect(isTooLarge(at(OPTIONS_MAX_OCTETS + 1))).toBe(true);
  });
});

describe('buildInput · buildOptions', () => {
  it('schemaVersion 이 첫 열쇠, data 는 받은 그대로, options 열쇠는 input 하나', () => {
    const data = edkData();
    const input = buildInput(FAKE_COMPANY, data as never);
    expect(Object.keys(input)).toEqual(['schemaVersion', 'company', 'data']);
    expect(input.data).toBe(data);
    expect(input.company).toEqual(FAKE_COMPANY);
    expect(Object.keys(buildOptions(input))).toEqual(['input']);
  });
});
