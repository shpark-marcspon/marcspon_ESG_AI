// greenwash.review@3 의 confirmedBy 칸(밴드 FW2a, 필수로 바꿈 WC1 ①). 필수 칸이고 nullable 이다(confirmed 가 아니면 null). 이름은 빈 글자가 아니다.
// 예시는 백엔드 저장소 자리를 읽기만 한다(contract.test.ts 와 같은 자리).
// 심은 파손: review.ts 의 confirmedBy 를 obj 대신 z.object 로 바꾸면 「모르는 키」 시험이 빨강이다.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { parseReview } from './index.ts';

const examples = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../../../../../api-py/esgapi/greenwash/tests/data/contract-examples',
);
type Json = Record<string, unknown>;
const confirmed = (): Json =>
  JSON.parse(
    readFileSync(resolve(examples, 'review/review-confirmed.json'), 'utf8'),
  ) as Json;

describe('confirmedBy 거울', () => {
  it('칸이 없으면 거절(필수)', () => {
    const value = confirmed();
    delete value.confirmedBy;
    expect(parseReview(value).ok).toBe(false);
  });

  it('null 이어도 지난다', () => {
    const value = confirmed();
    value.confirmedBy = null;
    const parsed = parseReview(value);
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
    expect(parsed.ok && parsed.value.confirmedBy).toBeNull();
  });

  it('값이 있으면 지나고 그대로 남는다', () => {
    const value = confirmed();
    value.confirmedBy = { id: 7, name: '검토자' };
    const parsed = parseReview(value);
    expect(parsed.ok ? 'ok' : parsed.issues).toBe('ok');
    expect(parsed.ok && parsed.value.confirmedBy).toEqual({
      id: 7,
      name: '검토자',
    });
  });

  it('confirmedBy 안의 모르는 키는 거절', () => {
    const value = confirmed();
    value.confirmedBy = { id: 7, name: '검토자', email: 'a@b.c' };
    expect(parseReview(value).ok).toBe(false);
  });

  it('이름이 빈 글자면 거절', () => {
    const value = confirmed();
    value.confirmedBy = { id: 7, name: '' };
    expect(parseReview(value).ok).toBe(false);
  });

  it('id 가 글자면 거절', () => {
    const value = confirmed();
    value.confirmedBy = { id: '7', name: '검토자' };
    expect(parseReview(value).ok).toBe(false);
  });
});
