// 실제 자료(git 밖)를 환경 변수가 가리키는 곳에서 읽는다. tools/convert.ts 와 tools/measure-places.ts 가 같이 쓴다.
//
//   ESG_LAB_OUT      parse-<문서 이름>/document.json 과 <VIEWER_RUN>/outcome.json 이 있는 폴더
//   ESG_REPORTS      <문서 이름>.pdf 가 있는 폴더. 분해할 때 쓴 바로 그 파일이어야 한다(assertSamePdf)
//   VIEWER_DOC_A/B   문서 이름
//   VIEWER_RUN       대조 실행의 폴더. ESG_LAB_OUT 아래의 경로
//   VIEWER_PLACES    (선택) parse-<문서 이름>/char-places.json 이 있는 폴더. 안 주면 ESG_LAB_OUT 에서 찾는다.
//                    분해를 `parse --places` 로 돌린 산출 폴더다. 파일이 없으면 좁힌 상자 없이 변환한다(짐작하지 않는다)
//   VIEWER_EXAM      (선택) 시험지 폴더. ESG_LAB_OUT 아래의 경로. a.document.json, b.document.json 을 읽는다
//   VIEWER_TITLE_A/B (선택) 화면에 보일 문서 이름. 기본은 「문서 A」「문서 B」
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { labDocumentSchema, labExamSchema, labOutcomeSchema } from './model.ts';
import type { LabOutcome } from './model.ts';
import { charPlacesSchema, indexPlaces, sameSource } from './places.ts';
import type { Side } from './reconcile.ts';

export class LabInputError extends Error {}

function env(name: string): string {
  const value = process.env[name];
  if (!value)
    throw new LabInputError(
      `환경 변수 ${name} 가 필요하다. 사용법은 tools/lab/load.ts 머리말에 있다.`,
    );
  return value;
}
const readJson = (path: string): unknown =>
  JSON.parse(readFileSync(path, 'utf8'));

export interface LoadedSide extends Side {
  /** 문서 이름(VIEWER_DOC_A/B). */
  name: string;
  pdfPath: string;
  /** 글자 자리를 읽었으면 그 파일의 경로, 못 읽었으면 null. */
  placesPath: string | null;
}

/**
 * 한쪽 문서를 읽는다. 글자 자리 파일이 있으면 같이 읽는다.
 * 글자 자리와 문서 모델이 서로 다른 PDF 의 것이면(해시가 다르면) 멈춘다. 그대로 쓰면 상자가 엉뚱한 글자를 가리킨다.
 */
export function loadSide(id: 'a' | 'b'): LoadedSide {
  const labOut = resolve(env('ESG_LAB_OUT'));
  const name = env(`VIEWER_DOC_${id.toUpperCase()}`);
  const exam = process.env.VIEWER_EXAM;
  const document = labDocumentSchema.parse(
    readJson(join(labOut, `parse-${name}`, 'document.json')),
  );

  const placesFile = join(
    resolve(process.env.VIEWER_PLACES ?? labOut),
    `parse-${name}`,
    'char-places.json',
  );
  let places: Side['places'];
  if (existsSync(placesFile)) {
    const parsed = charPlacesSchema.parse(readJson(placesFile));
    if (!sameSource(document, parsed)) {
      throw new LabInputError(
        `${placesFile}: 글자 자리와 문서 모델이 서로 다른 PDF 의 것이다(source.sha256 이 다르다: ${parsed.source.sha256.slice(0, 12)} / ${document.source.sha256.slice(0, 12)}). 같은 PDF 로 분해를 다시 돌린다.`,
      );
    }
    places = indexPlaces(parsed);
  }

  return {
    id,
    name,
    title:
      process.env[`VIEWER_TITLE_${id.toUpperCase()}`] ??
      `문서 ${id.toUpperCase()}`,
    url: `local/${id}.pdf`,
    pdfPath: join(resolve(env('ESG_REPORTS')), `${name}.pdf`),
    document,
    exam:
      exam ?
        labExamSchema.parse(readJson(join(labOut, exam, `${id}.document.json`)))
      : undefined,
    places,
    placesPath: places ? placesFile : null,
  };
}

/**
 * PDF 파일이 문서 모델을 낸 바로 그 파일인가. 아니면 멈춘다(LabInputError).
 * 문서 모델의 source.sha256 은 분해한 PDF 파일 바이트의 sha256 이다(분해 도구가 파일을 통째로 읽어 낸다).
 * 같은 이름의 다른 판(다시 내려받은 것, 고쳐 낸 것)이면 쪽과 좌표가 달라 상자가 엉뚱한 자리를 가리킨다.
 * PDF 를 복사하는 변환(tools/convert.ts)이 쓰기 전에 부른다. PDF 를 쓰지 않는 측정(tools/measure-places.ts)은 부르지 않는다.
 */
export function assertSamePdf(side: {
  name: string;
  pdfPath: string;
  document: { source: { sha256: string } };
}): void {
  if (!existsSync(side.pdfPath))
    throw new LabInputError(
      `${side.pdfPath}: PDF 가 없다. ESG_REPORTS 에 ${side.name}.pdf 가 있어야 한다.`,
    );
  const actual = createHash('sha256')
    .update(readFileSync(side.pdfPath))
    .digest('hex');
  const expected = side.document.source.sha256;
  if (actual !== expected) {
    throw new LabInputError(
      `${side.pdfPath}: 문서 모델(parse-${side.name}/document.json)을 낸 PDF 와 다른 파일이다(sha256 이 다르다: 이 파일 ${actual.slice(0, 12)} / 문서 모델 ${expected.slice(0, 12)}). 분해할 때 쓴 PDF 를 두거나, 이 PDF 로 분해를 다시 돌린다.`,
    );
  }
}

export function loadOutcome(): LabOutcome {
  return labOutcomeSchema.parse(
    readJson(
      join(resolve(env('ESG_LAB_OUT')), env('VIEWER_RUN'), 'outcome.json'),
    ),
  );
}
