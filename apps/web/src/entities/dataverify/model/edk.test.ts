// EDK 정량 데이터 읽기(밴드 DV2a ① — 발주서 §3-1-2·3).
import { describe, expect, it } from 'vitest';

import { readEdk } from './edk.ts';
import { FAKE_COMPANY, edkData, edkItem, fakeInput } from './testing.ts';

const text = (value: unknown) => JSON.stringify(value);

describe('readEdk', () => {
  it('JSON 아님 → not_json', () => {
    expect(readEdk('{"환경": [')).toEqual({ ok: false, kind: 'not_json' });
    expect(readEdk('')).toEqual({ ok: false, kind: 'not_json' });
  });

  it('맨 위가 객체가 아니면 shape', () => {
    for (const value of [[edkItem()], 'x', 3, null])
      expect(readEdk(text(value))).toEqual({ ok: false, kind: 'shape' });
  });

  it('항목 열쇠가 하나라도 빠지면 shape', () => {
    for (const key of Object.keys(edkItem())) {
      const item = edkItem();
      delete item[key];
      expect(readEdk(text({ 환경: [item] })), key).toEqual({
        ok: false,
        kind: 'shape',
      });
    }
  });

  it('값 꼴: 참/거짓·객체 값·values 가 배열이면 shape', () => {
    expect(readEdk(text({ 환경: [edkItem({ 메모: true })] })).ok).toBe(false);
    expect(readEdk(text({ 환경: [edkItem({ 단위: {} })] })).ok).toBe(false);
    expect(readEdk(text({ 환경: [edkItem({ values: [1] })] })).ok).toBe(false);
    expect(
      readEdk(text({ 환경: [edkItem({ values: { '2024': [1] } })] })).ok,
    ).toBe(false);
    expect(readEdk(text({ 환경: edkItem() })).ok).toBe(false);
  });

  it('모르는 열쇠는 받는다(값은 아무 JSON)', () => {
    const read = readEdk(
      text({ 환경: [edkItem({ 담당자: { 이름: '가상' }, 비고: [1, null] })] }),
    );
    expect(read.ok).toBe(true);
  });

  it('짝 없는 서로게이트(값·열쇠)·유한하지 않은 수 → shape', () => {
    expect(readEdk('{"환경": [], "a\\ud800": []}').ok).toBe(false);
    const item = JSON.stringify(edkItem()).replace(
      '"메모":""',
      '"메모":"\\udc00x"',
    );
    expect(readEdk(`{"환경": [${item}]}`)).toEqual({
      ok: false,
      kind: 'shape',
    });
    const big = JSON.stringify(edkItem()).replace(
      '"2023":1300',
      '"2023":1e400',
    );
    expect(readEdk(`{"환경": [${big}]}`)).toEqual({ ok: false, kind: 'shape' });
    // 짝 맞은 서로게이트는 된다.
    const pair = JSON.stringify(edkItem()).replace(
      '"메모":""',
      '"메모":"\\ud83d\\ude00"',
    );
    expect(readEdk(`{"환경": [${pair}]}`).ok).toBe(true);
  });

  it('미리 읽기: 테마·항목 수, 환경 항목·핵심(Y 정확히)·연도 정렬', () => {
    const read = readEdk(text(edkData()));
    expect(read).toMatchObject({
      ok: true,
      preview: {
        themes: 3,
        items: 4,
        envItems: 2,
        envKeyItems: 1,
        years: ['2022', '2023', '2024'],
      },
    });
    const lower = readEdk(text({ 환경: [edkItem({ 핵심데이터: 'y' })] }));
    expect(lower).toMatchObject({ ok: true, preview: { envKeyItems: 0 } });
  });

  it('환경 0: 빈 목록이나 테마 없음도 읽는다(막지 않음)', () => {
    expect(readEdk(text({ 환경: [] }))).toMatchObject({
      ok: true,
      preview: { themes: 1, items: 0, envItems: 0, years: [] },
    });
    expect(readEdk(text({ 사회: [edkItem()] }))).toMatchObject({
      ok: true,
      preview: { themes: 1, items: 1, envItems: 0, envKeyItems: 0 },
    });
  });

  it('data 는 받은 그대로(값을 고치지 않는다)', () => {
    const read = readEdk(text(edkData()));
    expect(read.ok && read.data).toEqual(edkData());
  });

  describe('서버 입력 꼴(dataverify.input@1, 밴드 DV5)', () => {
    it('data 를 데이터만 든 꼴과 같게 읽고 company 칸 넷을 싣는다', () => {
      const read = readEdk(text(fakeInput()));
      const plain = readEdk(text(edkData()));
      expect(read.ok && plain.ok).toBe(true);
      if (!read.ok || !plain.ok) return;
      expect(read.data).toEqual(plain.data);
      expect(read.preview).toEqual(plain.preview);
      expect(read.company).toEqual({
        ...FAKE_COMPANY,
        materialTopics: [...FAKE_COMPANY.materialTopics],
      });
    });

    it('company 칸 하나가 꼴 밖이면 그 칸만 빠진다', () => {
      const cases: [string, unknown][] = [
        ['reportingYear', '24'],
        ['reportingYear', 2025],
        ['name', 3],
        ['sasbIndustry', null],
        ['materialTopics', ['기후변화 대응', 1]],
        ['materialTopics', '안전보건'],
        // 짝 없는 서로게이트(JSON.stringify 는 \ud800 꼴로 적는다)
        ['name', 'a\uD800'],
      ];
      for (const [field, bad] of cases) {
        const input = fakeInput();
        (input.company as Record<string, unknown>)[field] = bad;
        const read = readEdk(text(input));
        expect(read.ok, `${field} ${String(bad)}`).toBe(true);
        if (!read.ok) continue;
        expect(Object.keys(read.company ?? {}).sort()).toEqual(
          ['materialTopics', 'name', 'reportingYear', 'sasbIndustry']
            .filter((key) => key !== field)
            .sort(),
        );
      }
    });

    it('company 가 없거나 객체가 아니면 company 없이 읽는다', () => {
      const rest = fakeInput();
      delete rest.company;
      const none = readEdk(text(rest));
      expect(none).toMatchObject({ ok: true });
      expect(none.ok && 'company' in none).toBe(false);
      const list = readEdk(text({ ...fakeInput(), company: [] }));
      expect(list.ok && 'company' in list).toBe(false);
    });

    it('schemaVersion 이 다른 값이면 shape', () => {
      for (const schemaVersion of [
        'dataverify.input@2',
        'dataverify.options@1',
      ])
        expect(readEdk(text({ ...fakeInput(), schemaVersion }))).toEqual({
          ok: false,
          kind: 'shape',
        });
    });

    it('data 가 데이터 꼴이 아니면(목록·빠짐·항목 꼴 틀림) shape', () => {
      for (const data of [[edkItem()], undefined, { 환경: [{ ID: 'E-1' }] }])
        expect(readEdk(text({ ...fakeInput(), data }))).toEqual({
          ok: false,
          kind: 'shape',
        });
    });

    it('데이터만 든 꼴의 결과에는 company 열쇠가 없다', () => {
      const read = readEdk(text(edkData()));
      expect(read.ok && 'company' in read).toBe(false);
    });
  });
});
