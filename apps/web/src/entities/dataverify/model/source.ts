// 입력 출처 options.source(밴드 DV2b — DV1f 계약 소비, sid:MARC-ENT-420·sid:MARC-ISSUE-336). 파일로 넣었으면 {kind:'file', name: File.name},
// 붙여 넣었으면 {kind:'paste'}(이름 0 — 주면 서버가 모르는 열쇠로 거절). 꼴은 apps/api-py/esgapi/dataverify/contracts/options_shapes.py:41·56·65.
// 이름 거울: 고정 apps/api-py/esgapi/dataverify/tests/data/flow-shapes/options/dataverify.options@1.schema.json:54
//   $defs.DataverifyFileSource.properties.name.pattern 을 옮겨 적음(source.test.ts 가 그 파일과 글자째 맞춘다). 길이는 code point 1~255.
// 확장자는 보지 않는다(서버와 같음). 화면 글: 파일은 그 이름, 붙여 넣기는 「붙여 넣은 데이터」(목록은 「· 시각」을 붙인다 — 판 DV-01).

/** 출처(generated DataverifyFileSource | DataverifyPasteSource 와 같은 꼴 — api/store.ts 가 서로 넣어지는지 타입으로 본다). */
export type InputSource = { kind: 'file'; name: string } | { kind: 'paste' };

/** 이름 pattern(options@1.schema.json:54 그대로 — `/`·`\`·C0·DEL·C1·U+061C·U+200E·U+200F·U+202A~202E·U+2066~2069 거절). */
export const SOURCE_NAME_PATTERN = String.raw`^[^/\\\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]+$`;
/** 이름 길이 상한(code point). */
export const SOURCE_NAME_MAX = 255;

const NAME = new RegExp(SOURCE_NAME_PATTERN, 'u');

/** 서버가 받는 파일 이름인가(pattern + code point 1~255). */
export const isSourceName = (name: string) =>
  NAME.test(name) && [...name].length <= SOURCE_NAME_MAX;

/** 파일 출처(이름은 받은 그대로). */
export const fileSource = (name: string): InputSource => ({
  kind: 'file',
  name,
});
export const PASTE_SOURCE: InputSource = { kind: 'paste' };
