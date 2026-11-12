// react-markdown 앞처리와 트리 읽기(보드 CM-04 r1 구현 메모). 꼴이 안 맞으면 그냥 둔다.
// 맨 글자 주소만 손댄다. 명시 링크 [x](주소) 의 주소는 건드리지 않는다.
export interface TreeNode {
  type: string;
  value?: string;
  url?: string;
  alt?: string;
  children?: TreeNode[];
  position?: { start: { offset?: number }; end: { offset?: number } };
}

// 믿지 않는 긴 글이 들어오므로 끝을 찾는 일은 정규식이 아니라 거꾸로 훑는 루프로 한다(되짚기로 시간이 터지지 않게).
const HANGUL = /^\p{Script=Hangul}$/u;
const PLAIN_NUMBER = /^[+-]?[\d,]+(\.\d+)?%?$/;
/** 「출처: 이름 (」 에서 이름 앞을 가르는 글자. 한 줄에 여럿이면 쉼표 등이 가른다. */
const NAME_SEPARATORS = ':：,，;；·';

export function isPlainNumber(text: string): boolean {
  return PLAIN_NUMBER.test(text.trim());
}

/** 마디 아래 글자를 잇는다. 그림은 대체 글자로 친다. */
export function nodeText(node: TreeNode | undefined): string {
  if (node === undefined) return '';
  if (node.value !== undefined) return node.value;
  if (node.alt !== undefined) return node.alt;
  return (node.children ?? []).map(nodeText).join('');
}

/** gfm 이 맨 글자에서 만든 링크인가: 글자가 주소와 같고 원문 길이도 그 글자만큼이다(꺾쇠·[…](…) 는 더 길다). */
function isLiteral(link: TreeNode): boolean {
  const only = link.children?.length === 1 ? link.children[0] : undefined;
  if (link.type !== 'link' || only?.type !== 'text') return false;
  const text = only.value ?? '';
  if (link.url !== text && link.url !== `http://${text}`) return false;
  const start = link.position?.start.offset;
  const end = link.position?.end.offset;
  return (
    start === undefined || end === undefined || end - start === text.length
  );
}

function isOpenParen(url: string): boolean {
  const count = (mark: string) => url.split(mark).length - 1;
  return count('(') > count(')');
}

/** 끝의 한글 덩어리와 바로 앞 「)」 하나가 시작하는 자리. 끝이 한글이 아니면 글자 길이. */
function hangulTailStart(text: string): number {
  let start = text.length;
  while (start > 0 && HANGUL.test(text[start - 1]!)) start -= 1;
  if (start === text.length) return start;
  return text[start - 1] === ')' ? start - 1 : start;
}

/** 주소 바로 뒤에 붙은 한글(·「)」 뒤 글)을 주소에서 떼어 뒤 글로 돌린다. */
function trimHangulTail(children: TreeNode[], index: number) {
  const link = children[index]!;
  const text = link.children![0]!;
  const value = text.value ?? '';
  const start = hangulTailStart(value);
  if (start === value.length) return;
  const whole = value.slice(start);
  const rest = value.slice(0, start);
  const tail =
    whole.startsWith(')') && isOpenParen(rest) ? whole.slice(1) : whole;
  const cut = (url: string) => url.slice(0, url.length - tail.length);
  link.url = cut(link.url ?? '');
  text.value = cut(value);
  const next = children[index + 1];
  if (next?.type === 'text') next.value = tail + (next.value ?? '');
  else children.splice(index + 1, 0, { type: 'text', value: tail });
}

/** 「… 이름」 을 이름 앞 글과 이름으로 가른다. 이름 자리에 괄호가 있으면 꼴이 아니다. */
function splitName(head: string): [before: string, name: string] | null {
  let cut = head.length;
  while (cut > 0 && !NAME_SEPARATORS.includes(head[cut - 1]!)) cut -= 1;
  const rest = head.slice(cut);
  if (rest.includes('(') || rest.includes(')')) return null;
  const lead = rest.length - rest.trimStart().length;
  return [head.slice(0, cut + lead), rest.trim()];
}

/** 「이름 (주소)」 를 이름이 글자인 링크 하나로 묶는다. */
function bindName(children: TreeNode[], index: number) {
  const before = children[index - 1];
  const after = children[index + 1];
  if (before?.type !== 'text' || after?.type !== 'text') return;
  const head = before.value ?? '';
  if (!head.endsWith('(') || !(after.value ?? '').startsWith(')')) return;
  const found = splitName(head.slice(0, -1));
  if (found === null || found[1] === '') return;
  before.value = found[0];
  after.value = (after.value ?? '').slice(1);
  children[index]!.children = [{ type: 'text', value: found[1] }];
}

function visit(node: TreeNode) {
  const children = node.children;
  if (children === undefined || node.type === 'link') return;
  for (let index = 0; index < children.length; index += 1) {
    if (!isLiteral(children[index]!)) continue;
    trimHangulTail(children, index);
    bindName(children, index);
  }
  children.forEach(visit);
}

/** remark 플러그인. */
export function remarkLinks() {
  return visit;
}
