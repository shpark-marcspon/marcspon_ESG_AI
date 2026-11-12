// 골든 덤프 (TS 쪽). esg-lab 의 규칙을 그대로 불러 문서 하나의 구획들을 JSON 으로 표준 출력에 낸다.
// 이 파일은 esg-app 에 있고 esg-lab 안에는 아무것도 두지 않는다. esg-lab 의 자리는 환경 변수 ESG_LAB 에서 읽는다.
//   실행: cd "$ESG_LAB/ts" && pnpm -s -F reconcile exec tsx <이 파일의 절대 경로> --doc <document.json> --id <문서 이름> [--places <char-places.json>] [--cases <cases.json>]
// 확장자가 .mts 인 까닭: esg-app 에는 "type": "module" 인 package.json 이 없어 .ts 는 tsx 가 CJS 로 바꾸고 최상위 await 에서 죽는다.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const lab = process.env["ESG_LAB"];
if (!lab) throw new Error("ESG_LAB(esg-lab 저장소의 경로)가 없다");
const src = (rel: string): string => pathToFileURL(join(lab, "ts/reconcile/src", rel)).href;
// index.ts 가 내보내지 않는 것(kinds·render)은 파일 경로로 따로 읽는다.
const api = await import(src("index.ts"));
const kindsMod = await import(src("domain/kinds.ts"));
const render = await import(src("compare/render.ts"));

const { values: args } = parseArgs({ options: { doc: { type: "string" }, places: { type: "string" }, id: { type: "string" }, cases: { type: "string" } } });
if (!args.doc || !args.id) throw new Error("--doc 과 --id 가 필요하다");
const readJson = (path: string): any => JSON.parse(readFileSync(path, "utf8"));

const document = api.documentSchema.parse(readJson(args.doc));
const places = args.places ? readJson(args.places) : null;
const extraction = api.extractDocument(document, args.id);
const own = api.extractDocument(document, args.id, { titles: "own" });
const withKinds = api.extractDocument(document, args.id, { kinds: true });
if (JSON.stringify(withKinds.facts) !== JSON.stringify(extraction.facts)) throw new Error("종류를 켰더니 값 후보 목록이 달라졌다");

const factMap = new Map(extraction.facts.map((fact: any) => [fact.id, fact]));
const maskBlocks: Record<string, string> = {};
for (const block of document.blocks) if (block.kind !== "table" && block.text !== undefined) maskBlocks[block.id] = render.maskText(block.text);
const maskCells: Record<string, string> = {};
for (const grid of extraction.grids)
  grid.cells.forEach((cells: string[], row: number) =>
    cells.forEach((raw: string, col: number) => {
      if (api.normalizeText(raw) !== "") maskCells[`${grid.id}:r${row}c${col}`] = render.cellText(grid, row, col, raw, factMap, true);
    }),
  );

const index = places ? api.indexPlaces(places) : null;
const out: Record<string, unknown> = {
  facts: extraction.facts,
  nonValues: extraction.nonValues.map((item: any) => ({ where: item.where, raw: item.raw, class: item.class })),
  grids: extraction.grids.map((grid: any, i: number) => ({
    id: grid.id,
    page: grid.page,
    header: grid.header,
    status: grid.status,
    innerHeaders: grid.innerHeaders,
    footnoteMarks: grid.footnoteMarks,
    titleCandidates: grid.titleCandidates,
    unitLines: grid.unitLines,
    titleCandidatesOwn: own.grids[i].titleCandidates,
  })),
  failed: { failedTables: extraction.failedTables, pagesWithoutText: extraction.pagesWithoutText },
  kinds: withKinds.kinds,
  count: api.countRatio(extraction),
  masks: { blocks: maskBlocks, cells: maskCells },
  places: {
    sameSource: places ? api.sameSource(document, places) : null,
    facts: extraction.facts.map((fact: any) => api.locatePlace(fact.id, extraction, index)),
    nonValues: extraction.nonValues.map((item: any) => api.placeOfWhere(item.where, index)),
  },
};

// 지은 문서에만: 네 문서로는 TS 와 견줄 길이 없는 것(십진 도우미, 표기 규칙의 낱개 본보기).
if (args.cases) {
  const cases = readJson(args.cases);
  const attempt = (run: () => unknown): unknown => {
    try {
      return run();
    } catch {
      return "(예외)";
    }
  };
  out["dec"] = {
    shift10: cases.dec.shift10.map(([value, exp]: [string, number]) => attempt(() => api.show(api.shift10(api.dec(value), exp)))),
    roundToPow10: cases.dec.roundToPow10.map(([value, exp, mode]: [string, number, string]) => attempt(() => api.show(api.roundToPow10(api.dec(value), exp, mode)))),
    compare: cases.dec.compare.map(([a, b]: [string, string]) => attempt(() => api.compare(api.dec(a), api.dec(b)))),
    sub: cases.dec.sub.map(([a, b]: [string, string]) => attempt(() => api.show(api.sub(api.dec(a), api.dec(b))))),
  };
  out["notation"] = {
    normalize: cases.notation.cells.map((text: string) => api.normalizeText(text)),
    cells: cases.notation.cells.map((text: string) => api.classifyCell(text)),
    texts: cases.notation.texts.map((text: string) => api.scanNumbers(text)),
    masks: cases.notation.texts.map((text: string) => render.maskText(text)),
    quotes: cases.notation.quotes.map(([text, quote, occurrence]: [string, string, number]) => api.locateQuote(text, quote, occurrence)),
    kindOf: cases.notation.kindOf.map(([text, raw]: [string, string]) => {
      const token = api.scanNumbers(text).find((item: any) => item.raw === raw && item.kind === "value");
      if (!token) return null;
      const fact = { bucket: "sentence", raw: token.raw, ...token.number };
      return kindsMod.kindOf(fact, { text, start: token.start, end: token.end, columnHeaders: [] });
    }),
  };
}
process.stdout.write(JSON.stringify(out));
