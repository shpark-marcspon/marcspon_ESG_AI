// 판 IR-03 줄 여섯(밴드 IRW1 ① — 발주서 §3-1-4).
import { describe, expect, it } from 'vitest';

import type { RunStep, StepStatus } from './result.ts';
import {
  STEP_LINES,
  UnknownStepError,
  currentLine,
  stepLines,
} from './steps.ts';

const ALL = STEP_LINES.flatMap(({ steps }) => steps);
const steps = (status: Record<string, StepStatus> = {}): RunStep[] =>
  ALL.map((step) => ({
    step,
    status: status[step] ?? 'pending',
    done: null,
    total: null,
  }));
/** 단계 열에 done·total 을 얹는다(IRW6). */
const counted = (
  status: Record<string, StepStatus>,
  counts: Record<string, [number, number]>,
): RunStep[] =>
  steps(status).map((s) => ({
    ...s,
    done: counts[s.step]?.[0] ?? null,
    total: counts[s.step]?.[1] ?? null,
  }));
const countOf = (input: RunStep[], line: number) =>
  stepLines(input)[line]!.count;
const statusOf = (input: RunStep[]) =>
  stepLines(input).map((view) => view.status);

describe('stepLines', () => {
  it('서버 단계 열(★B)이 줄 여섯에 빠짐없이 한 번씩 든다 · report 는 줄 2', () => {
    expect(ALL).toEqual([
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
    ]);
    expect(STEP_LINES[1]!.steps).toContain('report');
    expect(STEP_LINES[5]!.steps).toEqual(['report_iro']);
  });

  it('네 갈래: 대기 · 진행 중(running·done 섞임) · 완료 · 실패', () => {
    expect(statusOf(steps())).toEqual(Array(6).fill('pending'));
    expect(
      statusOf(
        steps({ load: 'done', regulation: 'done', keywords: 'done' }),
      ).slice(0, 3),
    ).toEqual(['done', 'running', 'pending']);
    expect(statusOf(steps({ load: 'running' }))[0]).toBe('running');
    expect(statusOf(steps({ load: 'done', regulation: 'failed' }))[0]).toBe(
      'failed',
    );
    expect(
      statusOf(steps(Object.fromEntries(ALL.map((s) => [s, 'done'])))),
    ).toEqual(Array(6).fill('done'));
  });

  it('줄 6 은 report_iro 하나 — 1부 report 가 done 이어도 줄 6 은 대기', () => {
    const view = statusOf(
      steps({
        load: 'done',
        regulation: 'done',
        keywords: 'done',
        controversy: 'done',
        report: 'done',
      }),
    );
    expect(view[1]).toBe('running');
    expect(view[5]).toBe('pending');
  });

  it('모르는 단계 이름은 던진다 · 주지 않은 단계는 대기', () => {
    expect(() =>
      stepLines([
        ...steps(),
        { step: 'later_step', status: 'pending', done: null, total: null },
      ]),
    ).toThrow(UnknownStepError);
    expect(stepLines([]).map((v) => v.status)).toEqual(
      Array(6).fill('pending'),
    );
  });
});

describe('currentLine', () => {
  it('진행 중·실패 줄, 없으면 끝난 줄 다음, 다 끝났으면 마지막', () => {
    expect(currentLine(stepLines(steps()))).toBe('regulation');
    expect(
      currentLine(
        stepLines(
          steps({ load: 'done', regulation: 'done', keywords: 'running' }),
        ),
      ),
    ).toBe('controversy');
    expect(
      currentLine(stepLines(steps({ load: 'done', regulation: 'done' }))),
    ).toBe('controversy');
    expect(
      currentLine(
        stepLines(steps(Object.fromEntries(ALL.map((s) => [s, 'done'])))),
      ),
    ).toBe('report');
  });
});

describe('stepLines count (IRW6, sid:MARC-ISSUE-378)', () => {
  const PART1 = { load: 'done', regulation: 'done', keywords: 'done' } as const;

  it('controversy running (1,2) → 줄 2 「1 / 2토픽」', () => {
    expect(
      countOf(
        counted(
          { ...PART1, controversy: 'running' },
          { regulation: [2, 2], controversy: [1, 2] },
        ),
        1,
      ),
    ).toEqual({ done: 1, total: 2, unit: 'topic' });
  });

  it('keywords 만 running(controversy pending) → null · 끝난 regulation (2,2) → null(Q3)', () => {
    const input = counted(
      { load: 'done', regulation: 'done', keywords: 'running' },
      { regulation: [2, 2], controversy: [0, 2] },
    );
    expect(countOf(input, 1)).toBeNull();
    expect(countOf(input, 0)).toBeNull();
  });

  it('impact running (3,5) → 서브토픽 · financial·pathway 도 서브토픽', () => {
    const before = {
      ...PART1,
      controversy: 'done',
      report: 'done',
      part2_seed: 'done',
    } as const;
    expect(
      countOf(counted({ ...before, impact: 'running' }, { impact: [3, 5] }), 2),
    ).toEqual({ done: 3, total: 5, unit: 'subtopic' });
    expect(
      countOf(
        counted(
          { ...before, impact: 'done', financial: 'done', pathway: 'running' },
          { pathway: [1, 5] },
        ),
        4,
      ),
    ).toEqual({ done: 1, total: 5, unit: 'subtopic' });
  });

  it('failed 단계 → null · total 0 → null · report 줄은 늘 null', () => {
    expect(
      countOf(
        counted({ ...PART1, controversy: 'failed' }, { controversy: [1, 2] }),
        1,
      ),
    ).toBeNull();
    expect(
      countOf(
        counted({ ...PART1, controversy: 'running' }, { controversy: [0, 0] }),
        1,
      ),
    ).toBeNull();
    expect(
      countOf(
        counted(
          Object.fromEntries(
            ALL.map((s) => [s, s === 'report_iro' ? 'running' : 'done']),
          ),
          { report_iro: [1, 2] },
        ),
        5,
      ),
    ).toBeNull();
  });
});
