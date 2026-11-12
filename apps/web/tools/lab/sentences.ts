// ★ 가짜 자료를 만든다. 「의심 문장 검출」을 흉내 낸 것이지 검출이 아니다.
// 문서에서 문장 몇 개를 고정 규칙으로 고를 뿐이다. 뷰어가 「문서 하나 + 문장 강조」 배치에서 어떻게 보이는지 보려는 것이다.
//
// 규칙: 숫자가 들어 있고 40자 이상인 문단을 차례로 모은 뒤, 일곱째마다 하나씩, 많아야 25개.
//       고른 문단마다 문장 하나: 숫자가 든 첫 문장.
// 강조의 box 는 문단 전체다. 글자 자리(places)를 주면 그 문장의 상자를 줄마다 하나씩 innerBoxes 로 넣는다
// (여러 줄에 걸친 문장이면 상자가 여럿이다). 안 주면 문단 전체 상자만 있다.
import type { ViewerInput } from '../../src/widgets/doc-viewer/model/index.ts';
import type { LabDocument } from './model.ts';
import { spanBoxes } from './places.ts';
import type { PlaceContainer } from './places.ts';

const EVERY = 7;
const MAX = 25;

/**
 * 글을 문장으로 가른다. 문장의 끝 = 마침표·물음표·느낌표(. ? ! 。) 뒤에 공백이 오거나 글이 끝나는 자리. 바로 붙은 닫는 따옴표·괄호는 그 문장에 넣는다.
 * 「3.5」의 점은 뒤에 공백이 없어 끝이 아니다. 줄바꿈으로는 가르지 않는다(분해가 줄을 이을 때 빈칸 하나로 바꿔 글에 줄바꿈이 없다).
 * 알고 있는 구멍: 「No. 3」 같은 줄임말의 점에서 잘린다. 마침표 없이 끝나는 글머리표 문장들은 한 문장이 된다. 가짜 자료를 고르는 데는 충분하다.
 * 돌려주는 자리는 글에서의 [start, end) 이고 앞뒤 공백은 뺀다.
 */
export function splitSentences(text: string): { start: number; end: number }[] {
  const sentences: { start: number; end: number }[] = [];
  let from = 0;
  const push = (to: number) => {
    let start = from;
    let end = to;
    while (start < end && /\s/u.test(text[start]!)) start += 1;
    while (end > start && /\s/u.test(text[end - 1]!)) end -= 1;
    if (end > start) sentences.push({ start, end });
    from = to;
  };
  for (const match of text.matchAll(/[.?!。]+["'”’)\]]*(?=\s|$)/gu))
    push(match.index + match[0].length);
  push(text.length);
  return sentences;
}

export function buildSentenceInput(
  document: LabDocument,
  title: string,
  url: string,
  places?: ReadonlyMap<string, PlaceContainer>,
): ViewerInput {
  const candidates = document.blocks.filter(
    (block) =>
      block.kind === 'paragraph' &&
      block.text !== undefined &&
      block.text.length >= 40 &&
      /\d/.test(block.text),
  );
  const chosen = candidates
    .filter((_, index) => index % EVERY === 0)
    .slice(0, MAX)
    .map((block) => {
      const text = block.text!;
      const sentences = splitSentences(text);
      const span =
        sentences.find((sentence) =>
          /\d/.test(text.slice(sentence.start, sentence.end)),
        ) ?? sentences[0]!;
      const container = places?.get(block.id);
      const boxes =
        container && container.page === block.page ?
          spanBoxes(container, span.start, span.end).boxes
        : [];
      return { block, sentence: text.slice(span.start, span.end), boxes };
    });
  const placed = chosen.filter((entry) => entry.boxes.length > 0).length;

  return {
    version: 1,
    notice:
      '★ 가짜 자료다. 「의심 문장」을 찾아낸 것이 아니라, 숫자가 든 문단을 일곱째마다 하나씩 골라 그 안의 숫자가 든 첫 문장을 강조만 해 본 것이다. 검출 로직은 없다.\n' +
      (places ?
        `문장의 상자는 문서를 분해할 때 나온 글자 좌표다. 여러 줄에 걸친 문장은 줄마다 상자 하나다(${chosen.length}문장 중 ${placed}문장이 상자를 얻었다).`
      : '글자 자리(char-places.json) 없이 변환했다. 그래서 상자가 문단 전체다.'),
    documents: [
      {
        id: 'a',
        title,
        url,
        pages: document.pages.map((page) => ({
          width: page.width,
          height: page.height,
        })),
      },
    ],
    kinds: [{ kind: 'sentence', label: '강조한 문장(가짜)', color: '#d97706' }],
    highlights: chosen.map(({ block, sentence, boxes }) => ({
      id: block.id,
      documentId: 'a',
      page: block.page,
      box: [...block.bbox],
      ...(boxes.length > 0 ?
        {
          innerBoxes: boxes.map(
            (box) => [...box] as [number, number, number, number],
          ),
        }
      : {}),
      kind: 'sentence',
      text: sentence,
    })),
    items: chosen.map(({ block, sentence }) => ({
      id: block.id,
      title: `${block.page}쪽 · ${sentence.replace(/\s+/g, ' ').slice(0, 60)}`,
      detail: block.text!.replace(/\s+/g, ' ').slice(0, 200),
      highlightIds: [block.id],
      review: { status: 'pending' as const },
    })),
  };
}
