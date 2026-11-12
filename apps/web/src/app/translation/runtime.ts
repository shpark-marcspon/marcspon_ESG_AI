// 영문번역 틀이 router context 로 받는 것의 꼴(밴드 TRW1a ② — 그린워싱 app/greenwash/runtime.ts 꼴). 타입만 둔다 — app/router.tsx 가
// `import type` 으로 가져와도 진입 청크에 아무것도 들지 않는다. 값(실어댑터)은 게으른 틀 모듈(TranslationRoutes.tsx)이 기본값으로 가져온다.
import type {
  TranslationServerDeps,
  TranslationStore,
} from '../../entities/translation/api/index.ts';
import type {
  LayoutVariantLabel,
  PartKey,
} from '../../entities/translation/model/index.ts';

/** 묶음 화면의 파트 탭 search(router.tsx 의 검사가 고른 것만 — 모르는 값은 버린다). */
export interface TranslationSearch {
  part?: 'all' | 'ceo' | 'story' | 'general';
}

/** PDF 보기로 들고 가는 자리(요약 표 줄 → 그 쪽·그 짝, pair null 이면 쪽만). from 은 머리 띠 글(검수 이슈 줄만 — 「12페이지 둘째 문단 · 숫자·단위 오류」). */
export interface PdfFocus {
  runId: string;
  page: number;
  pair: number | null;
  /** 요약에서 고른 문체(짝 자리의 셈 기준 — 보기가 이 문체로 연다). */
  label: LayoutVariantLabel;
  from: { where: string; type: string } | null;
  /** 처음 쪽 목록 거르기(밴드 TRW7 ③a — 「확인할 곳」 칸). */
  filter?: 'checks';
}

/** PDF 보기에서 [← 결과 요약]으로 돌아왔을 때 강조할 요약 표 줄(밴드 TRW7 ② — 그 묶음·실행·문체·표·입력 차례). 다른 묶음 화면은 쓰지 않고 지운다. */
export interface SummaryFocus {
  documentId: string;
  batchKey: string;
  runId: string;
  label: LayoutVariantLabel;
  table: 'issues' | 'misses';
  index: number;
}

/** 틀이 처음 그려질 때 한 번 부른다(세션 Api·서명 PUT 으로). 시험은 가짜 서버를 앞에 둔 실어댑터를 넣는다. 목 저장소는 없다. */
export type CreateTranslationStore = (
  deps: TranslationServerDeps,
) => TranslationStore;

/**
 * 라우터 하나에 하나 있는 영문번역의 메모리 칸(createAppRouter 가 만든다).
 * - control: 틀이 처음 그려질 때 만든 저장소. 화면 사이 이동에서 살아남는다.
 *   pdfFocus(밴드 TRW6 ③): 요약 표 줄을 눌러 PDF 보기로 갈 때 남기는 한 번 쓰는 표식(그 실행·쪽·짝). PDF 보기가 한 번 읽고 지운다 —
 *   [PDF로 보기]·새로 고침이면 없어 첫 쪽(그린워싱 confirmRunId 꼴).
 *   summaryFocus(밴드 TRW7 ②): 그때 누른 표 줄. 묶음 화면이 다시 그려질 때 한 번 읽고 지운다 — 그 줄을 옅은 파랑으로 남기고 화면 안으로.
 * - notStarted: [번역 시작]에서 일부 파트만 만들어졌을 때 못 만든 파트(감독 판단 4 ⓐ). 서버 묶음에 없으니 화면이 기억해 묶음 화면 띠로
 *   넘긴다. 열쇠는 「문서 id/묶음 열쇠」. 새로 고침이면 비어 띠가 없다. 세션이 끝나면 비운다.
 */
export interface TranslationRuntime {
  control: {
    store: TranslationStore;
    pdfFocus: PdfFocus | null;
    summaryFocus: SummaryFocus | null;
  } | null;
  notStarted: Map<string, { started: PartKey[]; failed: PartKey[] }>;
}

/** router context 의 영문번역 칸. createTranslationStore 는 시험용 선택 인자(없으면 틀 모듈의 기본값 — 실어댑터). */
export interface TranslationRouterContext {
  createTranslationStore?: CreateTranslationStore;
  translation: TranslationRuntime;
}
