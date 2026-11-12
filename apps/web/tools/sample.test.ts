// 저장소에 든 예시 자료가 (가) 입력 계약에 맞고 (나) 예시 PDF 에 칠해 둔 표시와 같은 자리를 가리키는지 지킨다.
// (나)가 깨지면 브라우저 테스트의 「상자 아래의 색」 확인이 뜻을 잃는다.
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import {
  innerBoxesOf,
  parseViewerInput,
} from '../src/widgets/doc-viewer/model/index.ts';
import { spanBoxes } from './lab/places.ts';
import { splitSentences } from './lab/sentences.ts';
import { SAMPLE_A, SAMPLE_B } from './sample-layout.ts';
import { sampleContainer } from './sample-places.ts';

const read = (name: string) =>
  parseViewerInput(
    JSON.parse(
      readFileSync(
        new URL(`../public/sample/${name}`, import.meta.url),
        'utf8',
      ),
    ),
  );

describe('예시 자료', () => {
  it('compare.json 이 입력 계약에 맞다', () => {
    expect(read('compare.json')).toMatchObject({ ok: true });
  });
  it('sentences.json 이 입력 계약에 맞고, 가짜 자료라고 적혀 있다', () => {
    const result = read('sentences.json');
    expect(result.ok && result.input.notice).toContain('가짜 자료');
  });

  it('compare.json 의 강조마다, 예시 PDF 의 같은 쪽 같은 자리에 표시가 있다', () => {
    const result = read('compare.json');
    if (!result.ok) throw new Error(result.errors.join('\n'));
    const layout = { a: SAMPLE_A, b: SAMPLE_B };
    for (const h of result.input.highlights) {
      const page = layout[h.documentId as 'a' | 'b'][h.page - 1]!;
      expect(
        page.marks.map((mark) => mark.box),
        `강조 ${h.id}`,
      ).toContainEqual(innerBoxesOf(h)[0] ?? h.box);
    }
    // 쪽 크기도 같아야 한다.
    for (const doc of result.input.documents) {
      expect(doc.pages).toEqual(
        layout[doc.id as 'a' | 'b'].map(({ width, height }) => ({
          width,
          height,
        })),
      );
    }
  });

  it('sentences.json 의 두 줄 문장(s4): 상자가 예시 PDF 의 글자 자리에서 실제 변환과 같은 셈으로 나온 것과 같다', () => {
    const result = read('sentences.json');
    if (!result.ok) throw new Error(result.errors.join('\n'));
    const s4 = result.input.highlights.find((h) => h.id === 's4')!;
    // 예시 PDF 의 2쪽 문단 → 글자 자리 → 둘째 문장의 글자 범위 → 줄마다 상자. 변환(tools/lab/sentences.ts)이 실제 자료에 하는 것과 같은 길이다.
    const { text, container } = sampleContainer(
      SAMPLE_A[s4.page - 1]!.paragraphs![0]!,
      s4.page,
    );
    const sentence = splitSentences(text)[1]!;
    expect(text.slice(sentence.start, sentence.end)).toBe(s4.text);
    const { boxes, covered } = spanBoxes(
      container,
      sentence.start,
      sentence.end,
    );
    expect(boxes).toHaveLength(2);
    expect(innerBoxesOf(s4)).toEqual(boxes);
    expect(s4.box).toEqual(container.bbox);
    // 범위의 글자 가운데 하나(줄을 이은 빈칸)에는 좌표가 없다.
    expect(covered).toBe(sentence.end - sentence.start - 1);
  });
});
