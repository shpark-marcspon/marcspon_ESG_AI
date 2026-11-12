// 새 검증 화면의 칸 셈(밴드 DV2a ② — 순수 함수, DOM·글을 모른다). 글은 화면이 DV_TEXT 에서 고른다.
//   - 데이터: 파일(File.text())·붙여 넣기 글 → readEdk → 꼴 갈래. 크기 갈래는 파일 바이트·글 바이트 > 256KiB, 또는 보낼 options 의 서버 셈 > 상한.
//   - 엑셀(밴드 DVX1 ②): 서버 읽기 답(ok)의 data 를 JSON 글로 바꿔 위와 같은 readData 한 길로 읽는다(판별·미리 읽기·256KiB 셈 하나).
//     그 글이 256KiB 를 넘으면 converted_too_large, 판별을 못 지나면 xlsx_unreachable(답의 꼴 틀림과 같은 글). 보고연도는 답의 마지막 연도를
//     회사 칸으로 실어 화면의 「빈 칸만 채움」(DV5)에 넘긴다. 거절은 kind·행 번호만(서버 글 0).
//   - 기업 칸 넷: 빈 칸 · 짝 없는 서로게이트(서버 utf-8 이 실패 — 보내지 않는다) · 보고연도 고르기(올해−5~올해, 기본 올해−1 — 2e ⑤).
import {
  OPTIONS_MAX_OCTETS,
  buildInput,
  buildOptions,
  isTooLarge,
  isWellFormed,
  readEdk,
} from '../../../entities/dataverify/model/index.ts';
import type {
  Company,
  EdkData,
  EdkPreview,
  InputSource,
} from '../../../entities/dataverify/model/index.ts';

/** 데이터 칸의 끝: 읽음 · 크기 넘음 · JSON 아님 · 꼴 틀림. */
export type DataRead =
  | {
      kind: 'ok';
      data: EdkData;
      preview: EdkPreview;
      /** 서버 입력 꼴 파일의 회사 칸(꼴에 맞는 칸만, 밴드 DV5). 엑셀이면 마지막 연도의 보고연도만. */
      company?: Partial<Company>;
      /** 엑셀에서 읽었으면 뺀 테마의 수(DVX1). */
      xlsx?: { skipped: { themes: number; items: number } };
    }
  | { kind: 'too_large' }
  | { kind: 'not_json' }
  | { kind: 'shape' };

const octets = (text: string) => new TextEncoder().encode(text).length;

/** 글 하나를 읽는다(바이트가 상한을 넘으면 읽지 않고 too_large). bytes 는 파일 크기(없으면 글의 UTF-8 바이트). */
export function readData(text: string, bytes = octets(text)): DataRead {
  if (bytes > OPTIONS_MAX_OCTETS) return { kind: 'too_large' };
  const read = readEdk(text);
  if (!read.ok) return { kind: read.kind };
  const ok = { kind: 'ok' as const, data: read.data, preview: read.preview };
  return read.company ? { ...ok, company: read.company } : ok;
}

/**
 * 엑셀 읽기 답에서 이 칸이 보는 몫(entities api 의 DataverifyEdkRead — model 칸은 api 를 가져오지 않아 받는 꼴만 적는다).
 * K 는 거절 갈래(api 의 EdkReadKind 를 화면이 넣는다).
 */
export type XlsxAnswer<K extends string> =
  | {
      ok: true;
      data: unknown;
      years: readonly string[];
      skipped: { themes: number; items: number };
    }
  | { ok: false; kind: K; row: number | null; column: number | null };

/** 파일 칸의 끝: 글 읽기의 끝 + 엑셀 읽기의 거절(kind·엑셀 행 번호) · 답 없음·꼴 틀림 · 바꾼 글이 256KiB 넘음. */
export type FileRead<K extends string = string> =
  | DataRead
  | {
      kind: 'xlsx_rejected';
      reason: K;
      row: number | null;
      column: number | null;
    }
  | { kind: 'xlsx_unreachable' }
  | { kind: 'converted_too_large' };

/** 엑셀 읽기 답 → 파일 칸의 끝(ok 는 data 를 JSON 글로 바꿔 readData 로). */
export function readXlsxAnswer<K extends string>(
  answer: XlsxAnswer<K>,
): FileRead<K> {
  if (!answer.ok)
    return {
      kind: 'xlsx_rejected',
      reason: answer.kind,
      row: answer.row,
      column: answer.column,
    };
  const read = readData(JSON.stringify(answer.data));
  if (read.kind === 'too_large') return { kind: 'converted_too_large' };
  if (read.kind !== 'ok') return { kind: 'xlsx_unreachable' };
  const last = answer.years.at(-1);
  return {
    kind: 'ok',
    data: read.data,
    preview: read.preview,
    ...(last === undefined ? {} : { company: { reportingYear: last } }),
    xlsx: { skipped: { ...answer.skipped } },
  };
}

/** 파일 줄의 크기 글(0.1MB 부터 MB 한 자리, 그 아래는 KB). */
export function sizeText(bytes: number): string {
  const mb = bytes / (1024 * 1024);
  if (mb >= 0.1) return `${mb.toFixed(1)}MB`;
  return `${Math.max(1, Math.round(bytes / 1024))}KB`;
}

/** 보고연도 고르기: 올해부터 올해−5 까지(새것 먼저), 기본 올해−1. */
export function yearChoices(now: Date): {
  years: readonly string[];
  fallback: string;
} {
  const year = now.getFullYear();
  return {
    years: Array.from({ length: 6 }, (_, index) => String(year - index)),
    fallback: String(year - 1),
  };
}

export interface CompanyDraft {
  name: string;
  sasbIndustry: string;
  materialTopics: readonly string[];
  reportingYear: string;
}

/** 칸 문제(차례 = 화면 차례). ill_formed 는 짝 없는 서로게이트가 든 칸(글 없이 칸만 빨강 — 판·2e 에 글이 없다). */
export type Problem =
  | { code: 'name' | 'sasb' | 'topics' }
  | { code: 'ill_formed'; field: 'name' | 'sasb' | 'topics' };

/** 기업 칸 넷의 문제. 앞뒤 빈칸은 빼고 본다. */
export function companyProblems(draft: CompanyDraft): Problem[] {
  const problems: Problem[] = [];
  if (draft.name.trim() === '') problems.push({ code: 'name' });
  else if (!isWellFormed(draft.name))
    problems.push({ code: 'ill_formed', field: 'name' });
  if (draft.sasbIndustry.trim() === '') problems.push({ code: 'sasb' });
  else if (!isWellFormed(draft.sasbIndustry))
    problems.push({ code: 'ill_formed', field: 'sasb' });
  if (draft.materialTopics.length === 0) problems.push({ code: 'topics' });
  else if (!draft.materialTopics.every(isWellFormed))
    problems.push({ code: 'ill_formed', field: 'topics' });
  return problems;
}

/** 보낼 회사(앞뒤 빈칸을 뺀다). */
export const companyOf = (draft: CompanyDraft): Company => ({
  name: draft.name.trim(),
  sasbIndustry: draft.sasbIndustry.trim(),
  materialTopics: draft.materialTopics,
  reportingYear: draft.reportingYear,
});

/** 토픽 하나 더하기: 앞뒤 빈칸을 빼고, 비었거나 이미 있으면 그대로. */
export function addTopic(
  topics: readonly string[],
  draft: string,
): readonly string[] {
  const topic = draft.trim();
  if (topic === '' || topics.includes(topic)) return topics;
  return [...topics, topic];
}

/** 이 데이터·회사·출처로 지은 options 가 서버 셈 상한을 넘는가(source 까지 넣고 잰다 — DV2b). */
export const optionsTooLarge = (
  data: EdkData,
  draft: CompanyDraft,
  source?: InputSource,
) => isTooLarge(buildOptions(buildInput(companyOf(draft), data), source));
