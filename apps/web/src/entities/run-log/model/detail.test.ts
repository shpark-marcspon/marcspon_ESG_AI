// 실행 상세의 순수 함수(밴드 AD4W — AD-04a). 상태 집합·짧은 시간 글·단계 숫자 칸·단계 이름·시각 두 토막.
import { describe, expect, expectTypeOf, it } from 'vitest';

import type { Schemas } from '../../../shared/api/index.ts';
import { RUN_LOG_TEXT } from '../config/text.ts';
import {
  RUN_STEP_STATUSES,
  detailTimes,
  downloadable,
  shortDurationText,
  shownFiles,
  stepFigures,
  stepLabel,
} from './index.ts';
import type { RunLogDetail, RunStepStatus } from './index.ts';

const t = RUN_LOG_TEXT;
const labels = t.detail.steps;

describe('AD-04a 실행 상세 model', () => {
  it('단계 상태: 계약 enum 과 집합이 같다(타입)·차례 대기·처리 중·완료·실패, 문구 표 키도 그 차례', () => {
    expectTypeOf<
      (typeof RUN_STEP_STATUSES)[number]
    >().toEqualTypeOf<RunStepStatus>();
    expect(RUN_STEP_STATUSES).toEqual(['pending', 'running', 'done', 'failed']);
    expect(Object.keys(t.detail.stepStatus)).toEqual([...RUN_STEP_STATUSES]);
  });

  it('상세 타입은 계약(RunLogDetailOut) 그대로 — 웹 넓힘 사본 0(ND1W)', () => {
    expectTypeOf<RunLogDetail>().toEqualTypeOf<Schemas['RunLogDetailOut']>();
  });

  it('상세 문서 두 칸은 null 도 받는다(ND1)', () => {
    expectTypeOf<RunLogDetail['documentId']>().toEqualTypeOf<number | null>();
    expectTypeOf<RunLogDetail['documentName']>().toEqualTypeOf<string | null>();
  });

  it('shortDurationText: 0 「0초」·42 「42초」·60 「1분 00초」·65 「1분 05초」·331 「5분 31초」·null → null(60 이상은 목록 꼴 0 채움)', () => {
    expect(shortDurationText(0)).toBe('0초');
    expect(shortDurationText(42)).toBe('42초');
    expect(shortDurationText(60)).toBe('1분 00초');
    expect(shortDurationText(65)).toBe('1분 05초');
    expect(shortDurationText(331)).toBe('5분 31초');
    expect(shortDurationText(null)).toBeNull();
  });

  describe('stepFigures', () => {
    const step = { durationSec: 58, tokens: 21_300, costUsd: 0.01 };

    it('기록 있음 + 값: 시간·토큰 쉼표·비용', () => {
      expect(stepFigures(step, true, t)).toEqual({
        duration: '58초',
        tokens: '21,300',
        cost: '$0.01',
      });
    });

    it('토큰 0 · 비용 0(AI 를 부르지 않은 단계) → 토큰·비용 「–」, 시간은 값', () => {
      expect(
        stepFigures({ durationSec: 42, tokens: 0, costUsd: 0 }, true, t),
      ).toEqual({ duration: '42초', tokens: '–', cost: '–' });
    });

    it('토큰 null → 토큰·비용 「–」', () => {
      expect(stepFigures({ ...step, tokens: null }, true, t)).toEqual({
        duration: '58초',
        tokens: '–',
        cost: '–',
      });
    });

    it('기록 없음(stepUsageRecorded 거짓) + 값 → 토큰·비용 「–」, 시간은 값', () => {
      expect(stepFigures(step, false, t)).toEqual({
        duration: '58초',
        tokens: '–',
        cost: '–',
      });
    });

    it('시간 null → 「–」', () => {
      expect(stepFigures({ ...step, durationSec: null }, true, t)).toEqual({
        duration: '–',
        tokens: '21,300',
        cost: '$0.01',
      });
    });
  });

  describe('stepLabel', () => {
    it('표에 있으면 그 글(그린워싱 judge → 「판정」)', () => {
      expect(stepLabel('greenwash', 'judge', labels)).toBe('판정');
    });
    it('그 모듈에 없는 단계 → 서버 이름(scope3 pipeline 은 일부러 뺐다)', () => {
      expect(stepLabel('inventory.scope3', 'pipeline', labels)).toBe(
        'pipeline',
      );
      expect(stepLabel('greenwash', 'calculate', labels)).toBe('calculate');
    });
    it('표에 없는 모듈 → 서버 이름', () => {
      expect(stepLabel('inventory.scope12', 'calculate', labels)).toBe(
        'calculate',
      );
    });
    it('AD6: 모듈 여섯의 단계 이름 표 — 흐름 단계 전부(발주서 §1 ② 목록)', () => {
      const keys = Object.fromEntries(
        Object.entries(labels).map(([module, steps]) => [
          module,
          Object.keys(steps),
        ]),
      );
      expect(keys).toEqual({
        greenwash: [
          'extract',
          'index',
          'judge',
          'wordcount',
          'locate',
          'report',
          'rewrite',
        ],
        dataverify: ['load', 'plan', 'review', 'insight', 'report'],
        translation: ['prepare', 'translate', 'report'],
        materiality: [
          'load',
          'regulation',
          'keywords',
          'controversy',
          'report',
          'part2_seed',
          'impact',
          'financial',
          'pathway',
          'report_iro',
        ],
        'inventory.scope3': [
          'c1',
          'c2',
          'c3',
          'c4',
          'c5',
          'c6',
          'c7',
          'c8',
          'c9',
          'c11',
          'c12',
          'c13',
          'c14',
          'c15',
          'assemble',
        ],
        drafting: ['extract', 'map', 'draft', 'report'],
      });
      expect(stepLabel('translation', 'translate', labels)).toBe(
        '번역 · 검수 · 자동 수정',
      );
      expect(stepLabel('drafting', 'extract', labels)).toBe(
        '전년도 보고서 읽기',
      );
      expect(stepLabel('inventory.scope3', 'c11', labels)).toBe(
        '판매된 제품의 사용',
      );
      for (const steps of Object.values(labels))
        for (const label of Object.values(steps))
          expect(label).toMatch(/[가-힣]/);
    });
    it('constructor 는 새지 않는다', () => {
      expect(stepLabel('constructor', 'constructor', labels)).toBe(
        'constructor',
      );
      expect(stepLabel('greenwash', 'constructor', labels)).toBe('constructor');
    });
  });

  describe('detailTimes', () => {
    it('같은 날: 시작 「YYYY-MM-DD HH:MM」, 끝 「HH:MM」', () => {
      expect(
        detailTimes({
          startedAt: '2026-10-15T14:20:05+09:00',
          finishedAt: '2026-10-15T14:28:10+09:00',
        }),
      ).toEqual({ start: '2026-10-15 14:20', end: '14:28' });
    });
    it('날짜가 다르면 끝에도 날짜', () => {
      expect(
        detailTimes({
          startedAt: '2026-10-15T23:58:00+09:00',
          finishedAt: '2026-10-16T00:03:00+09:00',
        }),
      ).toEqual({ start: '2026-10-15 23:58', end: '2026-10-16 00:03' });
    });
    it('끝나지 않음 → end null', () => {
      expect(
        detailTimes({
          startedAt: '2026-10-15T14:20:05+09:00',
          finishedAt: null,
        }),
      ).toEqual({ start: '2026-10-15 14:20', end: null });
    });
    it('시작 전 → 둘 다 null', () => {
      expect(detailTimes({ startedAt: null, finishedAt: null })).toEqual({
        start: null,
        end: null,
      });
    });
  });
});

// 밴드 AD4P: 결과 파일 줄 — 같은 이름 한 줄(디자인 2e 답 ⓑ)·실패 실행은 [내려받기] 없음(시안 v138).
describe('결과 파일 줄(밴드 AD4P)', () => {
  const file = (name: string, step: string | null) => ({
    name,
    step,
    mediaType: 'application/octet-stream',
    sizeBytes: 1,
  });

  describe('shownFiles', () => {
    it('같은 이름(단계 중간 report + 흐름 출력) → 흐름 출력 한 줄만', () => {
      const files = [
        file('지어낸 결과.xlsx', 'report'),
        file('지어낸 결과.xlsx', null),
      ];
      expect(shownFiles(files)).toEqual([file('지어낸 결과.xlsx', null)]);
    });
    it('이름이 다른 중간 파일은 남고 차례는 받은 그대로', () => {
      const files = [
        file('지어낸 판정.jsonl', 'judge'),
        file('지어낸 결과.xlsx', 'report'),
        file('지어낸 표시.pdf', null),
        file('지어낸 결과.xlsx', null),
      ];
      expect(shownFiles(files)).toEqual([
        file('지어낸 판정.jsonl', 'judge'),
        file('지어낸 표시.pdf', null),
        file('지어낸 결과.xlsx', null),
      ]);
    });
    it('같은 이름이 중간 파일끼리만 둘이면 둘 다 남는다', () => {
      const files = [
        file('지어낸 중간.json', 'judge'),
        file('지어낸 중간.json', 'locate'),
      ];
      expect(shownFiles(files)).toEqual(files);
    });
    it('빈 목록 → 빈 목록', () => {
      expect(shownFiles([])).toEqual([]);
    });
  });

  describe('downloadable', () => {
    it('흐름 출력 + 완료 실행 → 참, 단계 중간 파일 → 거짓', () => {
      expect(downloadable({ status: 'done' }, { step: null })).toBe(true);
      expect(downloadable({ status: 'done' }, { step: 'report' })).toBe(false);
    });
    it('실패 실행은 흐름 출력이어도 거짓, 대기·처리 중은 그대로(감독 답 Q5)', () => {
      expect(downloadable({ status: 'failed' }, { step: null })).toBe(false);
      expect(downloadable({ status: 'queued' }, { step: null })).toBe(true);
      expect(downloadable({ status: 'processing' }, { step: null })).toBe(true);
    });
  });
});
