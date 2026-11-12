// 결과 표 줄·정하지 못함·1-1 합침·카드(밴드 IRW1 ① — 발주서 §3-1-5, 최종 엑셀 규칙 apps/api-py/esgapi/materiality/outputs/final_xlsx.py).
import { describe, expect, it } from 'vitest';

import { parseResult } from '../api/contract/index.ts';
import {
  impactLines,
  mergedItems,
  pathwayLines,
  resultCards,
  riskTypeView,
  shortlistLines,
  subtopicTotal,
  summariesOf,
  undecidedImpact,
  undecidedPathway,
  undecidedSubtopics,
} from './result.ts';
import type { MaterialityResult } from './result.ts';
import {
  ctx,
  done,
  failed,
  fakeResult,
  financialRow,
  impactRow,
  item,
  notRun,
  part1Topic,
  pathwayRow,
  subtopic,
} from './testing.ts';

type Json = Record<string, unknown>;
const view = (raw: Json): MaterialityResult => {
  const parsed = parseResult(raw);
  if (!parsed.ok) throw new Error(parsed.issues);
  return parsed.value;
};
const topic = (name: string, subtopics: Json[]) => ({
  topic: name,
  description: `${name} 설명`,
  subtopics,
});

describe('2-1·2-2 줄', () => {
  it('서브토픽 차례 · No 는 거르기 전 시트 순번(서브토픽을 넘어 이어짐) · rows 그대로', () => {
    const result = view(
      fakeResult({}, [
        topic('A', [
          subtopic('가', {
            impact: done([impactRow('가1', '긍정'), impactRow('가2', '부정')]),
          }),
          subtopic('나', { impact: done([impactRow('나1', '중립')]) }),
        ]),
        topic('B', [subtopic('다')]),
      ]),
    );
    const lines = impactLines(result);
    expect(lines.map((l) => [l.no, l.topic, l.subtopic, l.definition])).toEqual(
      [
        [1, 'A', '가', '가1'],
        [2, 'A', '가', '가2'],
        [3, 'A', '나', '나1'],
        [4, 'B', '다', '다 영향'],
      ],
    );
    expect(lines.map((l) => l.tone)).toEqual([
      'positive',
      'negative',
      'other',
      'negative',
    ]);
    expect(pathwayLines(result).map((l) => l.no)).toEqual([1, 2, 3]);
  });

  it('2-2 줄 = pathway rows(재무 rows 아님) · 리스크 종류 접두 뗌 · 기회·null 은 null', () => {
    const result = view(
      fakeResult({}, [
        topic('A', [
          subtopic('가', {
            financial: done([
              financialRow('재무만 1'),
              financialRow('재무만 2'),
            ]),
            pathway: done([
              pathwayRow('경로 1'),
              pathwayRow('경로 2', '기회', '리스크-평판'),
              pathwayRow('경로 3', '리스크', null),
              pathwayRow('경로 4', '리스크', '평판'),
            ]),
          }),
        ]),
      ]),
    );
    const lines = pathwayLines(result);
    expect(lines.map((l) => l.definition)).toEqual([
      '경로 1',
      '경로 2',
      '경로 3',
      '경로 4',
    ]);
    expect(lines.map((l) => l.riskType)).toEqual([
      '규제 및 법률',
      null,
      null,
      '평판',
    ]);
    expect(lines.map((l) => l.kind)).toEqual([
      'risk',
      'opportunity',
      'risk',
      'risk',
    ]);
    expect(riskTypeView(null, null)).toBeNull();
  });

  it('가치사슬 활동(IRW10): 2-1 = 그 줄 valueChainActivities · 2-2 = pathway i(1부터)로 같은 서브토픽 재무 rows[i-1] · i null·0·범위 밖·재무 done 아님 → 빈 목록', () => {
    const result = view(
      fakeResult({}, [
        topic('A', [
          subtopic('가', {
            impact: done([
              {
                ...impactRow('가1'),
                valueChainActivities: ['활동 1', '활동 2'],
              },
              impactRow('가2'),
            ]),
            financial: done([
              { ...financialRow('재1'), valueChainActivities: ['재무 활동 1'] },
              { ...financialRow('재2'), valueChainActivities: ['재무 활동 2'] },
            ]),
            pathway: done([
              { ...pathwayRow('경로 i2'), i: 2 },
              { ...pathwayRow('경로 i1'), i: 1 },
              { ...pathwayRow('경로 null'), i: null },
              { ...pathwayRow('경로 0'), i: 0 },
              { ...pathwayRow('경로 3'), i: 3 },
            ]),
          }),
          subtopic('나', {
            financial: notRun(),
            pathway: done([{ ...pathwayRow('재무 없음'), i: 1 }]),
          }),
        ]),
      ]),
    );
    expect(impactLines(result).map((l) => l.activities)).toEqual([
      ['활동 1', '활동 2'],
      [],
      [],
    ]);
    expect(pathwayLines(result).map((l) => l.activities)).toEqual([
      ['재무 활동 2'],
      ['재무 활동 1'],
      [],
      [],
      [],
      [],
    ]);
  });

  it('컨텍스트 요약: 규제 → 컨트로버시 차례로 셋까지, null 뺌', () => {
    expect(
      summariesOf({
        regulations: [item('r1'), item('r2', null, null)],
        controversies: [item('c1'), item('c2'), item('c3')],
      }),
    ).toEqual(['r1 요약', 'c1 요약', 'c2 요약']);
  });
});

describe('정하지 못함', () => {
  const result = view(
    fakeResult({}, [
      topic('A', [
        subtopic('impact 실패', { impact: failed() }),
        subtopic('재무 실패', {
          financial: failed(),
          pathway: notRun(),
        }),
        subtopic('경로 실패', { pathway: failed() }),
        subtopic('둘 다', {
          impact: notRun(),
          financial: notRun(),
          pathway: notRun(),
        }),
        subtopic('재무 0 줄', { financial: done([]), pathway: notRun() }),
        subtopic('멀쩡'),
      ]),
    ]),
  );

  it('2-1 = impact done 아님 · 2-2 = financial done 아님 또는 pathway failed(재무 done·0 줄의 pathway not_run 은 정함)', () => {
    expect(undecidedImpact(result).map((r) => r.subtopic)).toEqual([
      'impact 실패',
      '둘 다',
    ]);
    expect(undecidedPathway(result).map((r) => r.subtopic)).toEqual([
      '재무 실패',
      '경로 실패',
      '둘 다',
    ]);
  });

  it('m 은 겹침 하나 · {전체} 는 지어 넣은 것 포함 전부', () => {
    expect(undecidedSubtopics(result).map((r) => r.subtopic)).toEqual([
      'impact 실패',
      '재무 실패',
      '경로 실패',
      '둘 다',
    ]);
    expect(subtopicTotal(result)).toBe(6);
    const auto = view(
      fakeResult({}, [topic('A', [subtopic('지음', { autofilled: true })])]),
    );
    expect(subtopicTotal(auto)).toBe(1);
  });
});

describe('찾은 글 없이 정함', () => {
  it('그 토픽 1부 규제·컨트로버시가 둘 다 done 아님일 때만', () => {
    const raw = fakeResult({}, [
      topic('A', [subtopic('가')]),
      topic('B', [subtopic('나')]),
      topic('C', [subtopic('다')]),
    ]);
    (raw.part1 as { topics: Json[] }).topics = [
      part1Topic('A', 'failed', 'not_run'),
      part1Topic('B', 'done', 'failed'),
      part1Topic('C'),
    ];
    const result = view(raw);
    expect(impactLines(result).map((l) => l.researchMissing)).toEqual([
      true,
      false,
      false,
    ]);
    expect(pathwayLines(result).map((l) => l.researchMissing)).toEqual([
      true,
      false,
      false,
    ]);
  });
});

describe('1-1 줄', () => {
  it('2-1 rows → [환경·사회], 재무 rows(pathway 아님) → [재무], url 같으면(공백 뗌) 처음 것 하나에 양쪽', () => {
    const result = view(
      fakeResult({}, [
        topic('A', [
          subtopic('가', {
            impact: done([
              impactRow(
                '가',
                '부정',
                ctx(
                  [item('규 하나', 'https://e.test/1'), item('규 둘', null)],
                  [item('컨 하나', 'https://e.test/c')],
                ),
              ),
            ]),
            financial: done([
              financialRow(
                '재',
                '리스크',
                null,
                ctx(
                  [item('규 하나 재', ' https://e.test/1 '), item('규 셋', '')],
                  [],
                ),
              ),
            ]),
            pathway: done([
              pathwayRow('경로', '리스크', null, ctx([item('경로 글')], [])),
            ]),
          }),
        ]),
      ]),
    );
    const [line] = shortlistLines(result);
    expect(
      line!.regulation.items.map((i) => [i.label, i.title, i.url]),
    ).toEqual([
      ['both', '규 하나', 'https://e.test/1'],
      ['social', '규 둘', null],
      ['financial', '규 셋', ''],
    ]);
    expect(line!.controversy.items.map((i) => i.label)).toEqual(['social']);
    expect(line!.regulation.researched).toBe(true);
  });

  it('null·빈 url 은 합치지 않는다', () => {
    expect(
      mergedItems(
        [item('a', null), item('b', '  ')],
        [item('c', null), item('d', '  ')],
      ).map((i) => i.label),
    ).toEqual(['social', 'social', 'financial', 'financial']);
  });

  it('1부 그 쪽이 done 아님 → researched false · part2 not_run → 줄 0', () => {
    const raw = fakeResult({}, [topic('A', [subtopic('가')])]);
    (raw.part1 as { topics: Json[] }).topics = [
      part1Topic('A', 'done', 'failed'),
    ];
    const [line] = shortlistLines(view(raw));
    expect([line!.regulation.researched, line!.controversy.researched]).toEqual(
      [true, false],
    );
    expect(
      shortlistLines(
        view(fakeResult({ part2: { status: 'not_run', message: 'x' } })),
      ),
    ).toEqual([]);
  });
});

describe('숫자 카드', () => {
  it('다섯 칸 · 그 밖 유형 값은 합에만 · 1-1 합 · 서브토픽 {전체}', () => {
    const result = view(
      fakeResult({}, [
        topic('A', [
          subtopic('가', {
            impact: done([
              impactRow('1', '긍정', ctx([item('r')], [item('c')])),
              impactRow('2', '부정'),
              impactRow('3', '중립'),
            ]),
            pathway: done([
              pathwayRow('p1', '리스크'),
              pathwayRow('p2', '기회'),
              pathwayRow('p3', '모름'),
            ]),
          }),
          subtopic('나', { impact: failed() }),
        ]),
      ]),
    );
    expect(resultCards(result)).toEqual({
      topics: 1,
      subtopics: 2,
      regulation: 1,
      controversy: 1,
      impact: { total: 3, positive: 1, negative: 1 },
      pathway: { total: 4, risk: 2, opportunity: 1 },
    });
  });

  it('part2 not_run 이면 토픽 수만, 나머지 null', () => {
    expect(
      resultCards(
        view(fakeResult({ part2: { status: 'not_run', message: 'x' } })),
      ),
    ).toEqual({
      topics: 2,
      subtopics: null,
      regulation: null,
      controversy: null,
      impact: null,
      pathway: null,
    });
  });
});

describe('줄·항목의 자리(밴드 IRW11 — 칸 주소 짓기)', () => {
  const result = view(
    fakeResult({}, [
      topic('A', [
        subtopic('가', {
          impact: done([
            impactRow('가1', '부정'),
            impactRow(
              '가2',
              '부정',
              ctx(
                [item('r0', null, null), item('r1')],
                [item('c0'), item('c1'), item('c2')],
              ),
            ),
          ]),
          financial: done([financialRow('가 재무')]),
          pathway: done([
            { ...pathwayRow('경로 1'), i: 1 },
            { ...pathwayRow('경로 2'), i: 2 },
            { ...pathwayRow('경로 3'), i: null },
          ]),
        }),
      ]),
      topic('B', [
        subtopic('나', { impact: failed() }),
        subtopic('다', {
          financial: failed(),
          pathway: done([{ ...pathwayRow('경로 다'), i: 1 }]),
        }),
      ]),
    ]),
  );

  it('ImpactLine.at·summaryAt(summaries 와 같은 길이 — null 뺀 차례) · 값·차례는 그대로', () => {
    const lines = impactLines(result);
    expect(lines.map((l) => l.at)).toEqual([
      { topic: 0, subtopic: 0, row: 0 },
      { topic: 0, subtopic: 0, row: 1 },
      { topic: 1, subtopic: 1, row: 0 },
    ]);
    expect(lines[1]!.summaries).toEqual(['r1 요약', 'c0 요약', 'c1 요약']);
    expect(lines[1]!.summaryAt).toEqual([
      { side: 'regulations', k: 1 },
      { side: 'controversies', k: 0 },
      { side: 'controversies', k: 1 },
    ]);
    expect(lines[0]!.summaryAt).toEqual([]);
  });

  it('PathwayLine.at·fin: i(1부터) → 재무 rows 차례, null·범위 밖·재무 done 아님 → null', () => {
    const lines = pathwayLines(result);
    expect(lines.map((l) => [l.at, l.fin])).toEqual([
      [{ topic: 0, subtopic: 0, row: 0 }, 0],
      [{ topic: 0, subtopic: 0, row: 1 }, null],
      [{ topic: 0, subtopic: 0, row: 2 }, null],
      [{ topic: 1, subtopic: 0, row: 0 }, 0],
      [{ topic: 1, subtopic: 1, row: 0 }, null],
    ]);
  });

  it('MergedItem.at = 묶음 첫 자리(토픽 안 — 서브토픽·갈래·줄·쪽·k), 자리 목록 없이 부르면 null', () => {
    const [line] = shortlistLines(result);
    expect(line!.regulation.items.map((i) => [i.title, i.at])).toEqual([
      [
        'r0',
        { subtopic: 0, phase: 'impact', row: 1, side: 'regulations', k: 0 },
      ],
      [
        'r1',
        { subtopic: 0, phase: 'impact', row: 1, side: 'regulations', k: 1 },
      ],
    ]);
    expect(line!.controversy.items[2]!.at).toEqual({
      subtopic: 0,
      phase: 'impact',
      row: 1,
      side: 'controversies',
      k: 2,
    });
    expect(mergedItems([item('a')], []).map((i) => i.at)).toEqual([null]);
  });
});
