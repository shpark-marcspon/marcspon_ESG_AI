// 예시 PDF 의 문단에서 글자 자리를 만든다. 실제 자료에서는 문서를 분해하는 쪽이 내는 것(char-places.json 의 그릇 하나)과 같은 꼴이다.
// 예시 PDF 는 이 저장소의 코드가 글자를 놓으므로(tools/sample-layout.ts) 글자마다의 자리를 셈으로 안다.
//
// 세로 범위: 실제 자료의 글자 자리는 글꼴의 줄 높이(위로 글자 크기의 0.905, 아래로 0.212 쯤. Helvetica 의 값)를 쓴다. 여기서도 같게 흉내 낸다.
// 그래서 상자는 글자의 잉크보다 위아래로 조금 넉넉하다. 좌표는 실제처럼 소수 한 자리로 깎는다.
import type { PlaceContainer } from './lab/places.ts';
import { glyphWidth } from './sample-layout.ts';
import type { SampleParagraph } from './sample-layout.ts';

const round = (value: number) => Math.round(value * 10) / 10;

export function sampleContainer(
  paragraph: SampleParagraph,
  page: number,
): { text: string; container: PlaceContainer } {
  const runs: PlaceContainer['runs'] = [];
  let text = '';
  for (const line of paragraph.lines) {
    // 줄과 줄은 빈칸 하나로 잇는다. 그 빈칸은 어느 토막에도 들지 않는다(좌표가 없다).
    if (text !== '') text += ' ';
    const x0: number[] = [];
    const x1: number[] = [];
    let x = line.x;
    for (const char of line.str) {
      x0.push(round(x));
      x += glyphWidth(char, line.size);
      x1.push(round(x));
    }
    // pdf-writer 는 글자의 밑줄을 윗변에서 글자 크기의 0.8 내려온 곳에 둔다.
    const baseline = line.top + line.size * 0.8;
    runs.push({
      start: text.length,
      y0: round(baseline - line.size * 0.905),
      y1: round(baseline + line.size * 0.212),
      x0,
      x1,
    });
    text += line.str;
  }
  const bbox: PlaceContainer['bbox'] = [
    Math.min(...runs.map((run) => run.x0[0]!)),
    runs[0]!.y0,
    Math.max(...runs.map((run) => run.x1.at(-1)!)),
    runs.at(-1)!.y1,
  ];
  return {
    text,
    container: { id: paragraph.id, kind: 'block', page, bbox, runs },
  };
}
