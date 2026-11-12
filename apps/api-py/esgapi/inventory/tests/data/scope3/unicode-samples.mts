// ★ 나: esg-lab 의 함수를 그대로 불러, 표본마다 Node 가 내는 글자를 JSON 으로 낸다(make-golden.sh 가 돌린다).
// 쓰임: (esg-lab/ts 에서) pnpm -F scope3 exec tsx <이 파일> <esg-lab 의 절대 경로> <표본 json>
import { readFileSync } from "node:fs";

const [lab, input] = process.argv.slice(2) as [string, string];
const scope3 = await import(`${lab}/ts/scope3/src/index.ts`);
const { rankLexicalV1 } = await import(`${lab}/ts/scope3/src/domain/lexicalV1.ts`);
const samples = JSON.parse(readFileSync(input, "utf8")) as string[];

// lexical-v1 의 낱말 자르기는 밖으로 나와 있지 않다. 이름이 그 표본인 후보 하나에 표본으로 물어 겹친 것을 본다.
function v1Matched(text: string): string[] {
  const factor = { id: "x", name: text, categoryPath: [] };
  return rankLexicalV1([factor], { texts: [text], keywords: [] })[0].matched;
}

const out = samples.map((text) => ({
  text,
  normalized: scope3.normalizeItemName(text),
  unitDim: scope3.unitDim(text),
  tokens: scope3.tokenize(text, { bigrams: true }),
  tokensNoBigrams: scope3.tokenize(text, { bigrams: false }),
  v1Matched: v1Matched(text),
}));
process.stdout.write(`${JSON.stringify({ node: process.version, unicode: process.versions.unicode, samples: out }, null, 1)}\n`);
