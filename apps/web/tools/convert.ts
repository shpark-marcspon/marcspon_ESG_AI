// 실제 자료(git 밖)를 뷰어의 입력으로 바꿔 VIEWER_DATA_DIR 에 쓴다. 저장소에는 아무것도 남기지 않는다.
//
// 사용:
//   ESG_LAB_OUT=<실측 산출물 폴더> ESG_REPORTS=<PDF 폴더> VIEWER_PLACES=<글자 자리를 낸 분해의 산출 폴더> \
//   VIEWER_DOC_A=<문서 이름> VIEWER_DOC_B=<문서 이름> VIEWER_RUN=<대조 실행의 폴더> \
//   pnpm --filter @esg/web convert
// (상대 경로는 apps/web 을 기준으로 읽는다. pnpm 이 스크립트를 그 폴더에서 돌린다. 절대 경로를 주는 편이 헷갈리지 않는다.)
//
// 읽는 환경 변수는 tools/lab/load.ts 머리말에 있다. 여기서만 읽는 것:
//   VIEWER_DATA_DIR  (선택) 결과를 쓸 폴더. 기본은 apps/web/.local-data (.gitignore 되어 있다)
//
// 칸·숫자·문장의 좁은 상자는 글자 자리(char-places.json)에서 얻는다. PDF 를 열어 글자를 찾지 않는다(PDF 는 복사만 한다).
// PDF 파일이 문서 모델(document.json)을 낸 그 파일이 아니면(source.sha256 이 파일의 sha256 과 다르면) 멈추고 아무것도 쓰지 않는다.
// 글자 자리가 없으면 좁은 상자 없이 표·문단 전체 상자만 넣고, 그 사실을 화면의 알림과 여기 출력에 적는다.
//
// 쓰는 것: a.pdf, b.pdf(복사), reconcile.json(두 문서 대조), sentences.json(문장 강조, 가짜), index.json(목록),
//          places-report.json(강조마다 상자를 얻었는지의 기록. tools/measure-places.ts 가 읽는다)
import { copyFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import {
  innerBoxesOf,
  parseViewerInput,
} from '../src/widgets/doc-viewer/model/index.ts';
import {
  LabInputError,
  assertSamePdf,
  loadOutcome,
  loadSide,
} from './lab/load.ts';
import { buildReconcileInput } from './lab/reconcile.ts';
import { buildSentenceInput } from './lab/sentences.ts';

const outDir = resolve(process.env.VIEWER_DATA_DIR ?? '.local-data');

try {
  const a = loadSide('a');
  const b = loadSide('b');
  // PDF 가 문서 모델을 낸 그 파일인지 먼저 본다. 다르면 여기서 멈춘다(아래의 쓰기까지 가지 않는다).
  for (const side of [a, b]) assertSamePdf(side);
  const outcome = loadOutcome();

  const reconcile = buildReconcileInput(a, b, outcome);
  const sentences = buildSentenceInput(a.document, a.title, a.url, a.places);

  // 뷰어가 받는 것과 같은 검증을 여기서도 돌린다. 통과하지 못하는 자료는 쓰지 않는다.
  for (const [name, input] of [
    ['reconcile', reconcile.input],
    ['sentences', sentences],
  ] as const) {
    const checked = parseViewerInput(input);
    if (!checked.ok)
      throw new LabInputError(
        `${name}: 만든 자료가 입력 계약에 맞지 않는다\n` +
          checked.errors.slice(0, 20).join('\n'),
      );
  }

  mkdirSync(outDir, { recursive: true });
  for (const side of [a, b])
    copyFileSync(side.pdfPath, join(outDir, `${side.id}.pdf`));
  writeFileSync(
    join(outDir, 'reconcile.json'),
    JSON.stringify(reconcile.input),
  );
  writeFileSync(join(outDir, 'sentences.json'), JSON.stringify(sentences));
  writeFileSync(
    join(outDir, 'places-report.json'),
    JSON.stringify(reconcile.records),
  );
  writeFileSync(
    join(outDir, 'index.json'),
    JSON.stringify({
      datasets: [
        { file: 'local/reconcile.json', title: '실제 자료: 두 문서 대조' },
        {
          file: 'local/sentences.json',
          title: '실제 자료: 문장 강조(가짜 자료)',
        },
      ],
    }),
  );

  const placed = reconcile.records.filter(
    (record) => record.result.found,
  ).length;
  const sentenceLines = sentences.highlights.map(
    (highlight) => innerBoxesOf(highlight).length,
  );
  console.log(`convert: ${outDir} 에 썼다`);
  for (const side of [a, b])
    console.log(
      `  글자 자리 ${side.id.toUpperCase()}: ${side.placesPath ?? '없음 → 이 문서의 강조는 표·문단 전체 상자다(분해를 --places 로 돌리고 VIEWER_PLACES 로 그 폴더를 준다)'}`,
    );
  console.log(
    `  두 문서 대조: 항목 ${reconcile.input.items.length}, 강조 ${reconcile.input.highlights.length} (칸·숫자의 상자를 얻은 것 ${placed})`,
  );
  console.log(
    `  문장 강조(가짜): 항목 ${sentences.items.length} (상자를 얻은 문장 ${sentenceLines.filter((n) => n > 0).length}, 두 줄 이상인 문장 ${sentenceLines.filter((n) => n > 1).length})`,
  );
  if (reconcile.problems.length > 0) {
    console.log(
      `  풀지 못한 자리 표기 ${reconcile.problems.length}건:\n    ` +
        reconcile.problems.slice(0, 10).join('\n    '),
    );
  }
} catch (error) {
  if (!(error instanceof LabInputError)) throw error;
  console.error(error.message);
  process.exit(1);
}
