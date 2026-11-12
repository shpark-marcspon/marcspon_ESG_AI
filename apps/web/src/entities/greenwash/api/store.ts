// 그린워싱 저장소 인터페이스(밴드 FW1b ①). 화면은 이 꼴만 알고, 목(api/mock)과 실제 API(FW2 이후)가 이 꼴을 맞춘다.
//
// 흐름(발주서 §2 ① [B3]):
//   1. 파일을 고르면 createDocument(file) — 업로드에 해당. 서버가 채우는 pageCount 와, 글자 층이 있는지(hasText)를 돌려받는다.
//   2. [점검 시작]은 createRun(documentId, 입력) 만 한다. 보고연도는 파일 뒤에 고르므로 입력에 싣고, 실어댑터가 실행을 만들기 전에
//      문서 PATCH 로 옮긴다(밴드 GW2R ③ — 실행 옵션에는 싣지 않는다). 수정본 대상은 늘 null(v115 — 수정본 칸 없음).
//   3. 처리 상태는 subscribeRun 으로 받는다: 구독하면 현재값을 먼저 한 번 보내고, 그 뒤 바뀔 때마다 보낸다(밴드 FW2 ①, sid:MARC-ISSUE-99 2).
//      훅(useRunStatus)은 getRun 으로 따로 읽지 않는다 — 늦게 온 읽기가 새 상태를 덮는 길을 없앤다. 갱신 방식(폴링·SSE)은 정하지 않는다.
//   4. 실행 전체가 실패하면 rerun(runId) 으로 같은 문서·같은 입력의 새 실행을 처음부터 돌린다(밴드 FW2 ⓪, 2026-10-16 사용자 결정).
//      실패한 실행에만 있다. 서버의 resumeFromRunId(이어 돌기)는 시스템 복구 장치라 화면이 쓰지 않는다.
//      쪽 하나의 실패는 실행 실패가 아니다: 결과의 candidateStats.failedPages 로 남고 실행은 done(GW-04 가 알린다).
// [취소]나 지우기(×)로 남는 문서는 지우지 않는다: 목 단계에서는 버린다(무효 조건: 실제 API 에서 고아 문서를 지울 길이 생기면 여기 더한다).
// 근거 검색 범위는 입력에 없다: 근거는 늘 지정한 파트의 쪽 안에서 찾는다(2026-10-16 사용자 결정, sid:MARC-TICK-73 노트).
// 무효 조건:
//   - hasText 칸은 서버 문서 칸에 없다(인계 4절의 칸 목록). 서버가 글자 층 판정을 다른 이름·단계(실행 실패 등)로 내면 꼴을 바꾼다.
// 결과·검토(밴드 FW2 ①): getResult·getReview·putReview 는 JSON 그대로(unknown)를 준다. 꼴은 훅이 거울(api/contract)로 지킨다.
//   무효 조건: 어댑터는 결과·검토 JSON 을 고치지 않고 그대로 넘긴다 — 꼴 검사는 훅의 거울이 한다(어댑터가 칸을 바꾸거나 거르면 거울이 깨진다).
//   잘못은 StoreError 의 kind 로 가른다: not_found(없는 실행·결과), rejected(그 밖), 검토 PUT 의 409 셋은 서버 code 그대로
//   review_locked(확정된 실행), run_not_done(끝나지 않은 실행), no_review(검토가 없는 실행 — dry-run)(밴드 WC1 ①, GC2).
//   unreachable: 실행 만들기(createRun·rerun 의 POST /runs)의 답이 끊김 — 서버가 실행을 만들었는지 모른다(밴드 GR1, sid:MARC-ISSUE-225).
//   다른 요청의 끊김은 rejected 그대로. 실행 만들기는 열쇠(idempotencyKey — Idempotency-Key, api/idempotency.ts)를 받는다:
//   끊김 뒤 같은 열쇠로 다시 부르면 실행은 하나다(서버가 앞 실행을 돌려준다, 밴드 GR2). 그래서 화면은 같은 단추를 다시 켠다.
//   열쇠는 선택이다(서버 머리도 선택 — 없으면 부를 때마다 새 실행). 화면 훅은 늘 싣는다(useNewCheckForm·useRerunAction).
// id 는 글자다. 서버(main ee18aaa)의 문서·실행 id 는 integer 라 실제 어댑터가 경계에서 바꾼다(보고 「API 짝짓기」).
import type {
  CheckRowsSource,
  PartPages,
  ReviewUpdate,
  RunProgress,
} from '../model/index.ts';

export interface CreatedDocument {
  documentId: string;
  /** 쪽 수(서버가 업로드 뒤 채운다). */
  pageCount: number;
  /** 글자 층이 있는가. 없으면 1차에서 점검하지 않는다(GW-02a). */
  hasText: boolean;
}

export interface RunRequest {
  /** 파트별 쪽 집합(PDF 쪽 기준). */
  parts: PartPages;
  /** 이 점검에서만 더할 단어(백엔드 POST /runs 의 options.extraTerms, 결과 꼴 extraTerms). */
  extraTerms: readonly string[];
  /** 보고연도(선택). */
  reportYear: number | null;
  /** 수정본이면 원 문서 id. 새 문서면 null. */
  previousDocumentId: string | null;
}

export interface RunSnapshot {
  runId: string;
  documentId: string;
  /** 시작 시각(ISO 8601). 아직 시작하지 않았으면(queued) null. 꾸미는 것은 ui(밴드 FW2 ①, [N6]). */
  startedAt: string | null;
  /**
   * 끝난 시각(ISO 8601, 서버 RunOut.finishedAt — 밴드 GW2R ② Q4). 끝나지 않았거나 모르면 null. 목은 끝나면 값.
   * GW-03 끝남의 「{끝난 때} 끝남」에 쓴다(꾸미는 것은 ui).
   */
  finishedAt: string | null;
  /** 문서 전체 쪽 수(텍스트 추출 단계의 글에 쓴다. 밴드 FW1b ③). 실행 응답에 없으면 null — useRunStatus 가 getDocument 로 채운다 [R5]. */
  pageCount: number | null;
  /** 점검할 쪽 수(파트 합집합). */
  checkedPages: number;
  progress: RunProgress;
  /** [다시 실행]으로 만든 실행이면 그 앞(실패한) 실행 id. */
  rerunOf: string | null;
  /**
   * 실행 실패의 code(서버 RunOut.errorCode, 밴드 GW1R ① Q6). 실패가 아니거나 모르면 null. 목은 늘 null.
   * 화면은 `no_text_layer`(글자 층 없는 PDF — GW-03 의 [새 점검] 카드)만 가른다. 그 밖의 값은 일반 실패다.
   */
  errorCode: string | null;
}

/** 수정본 대상으로 고를 수 있는 기존 문서. */
export interface ExistingDocument {
  documentId: string;
  fileName: string;
  uploadedAt: string;
}

export interface GreenwashStore {
  /** 파일을 올린다. 받을 수 없는 파일이면 거절된다. */
  createDocument(file: File): Promise<CreatedDocument>;
  /**
   * 실행을 만든다. 답이 끊기면 StoreError unreachable(만들어졌는지 모른다).
   * 같은 idempotencyKey·같은 입력으로 다시 부르면 앞 실행을 돌려준다(새 실행 0). 같은 열쇠·다른 입력은 거절(rejected).
   */
  createRun(
    documentId: string,
    request: RunRequest,
    idempotencyKey?: string,
  ): Promise<{ runId: string }>;
  /** 실행 상태를 읽는다. 없는 실행이면 거절된다(StoreError not_found). */
  getRun(runId: string): Promise<RunSnapshot>;
  /**
   * 실행 상태를 받는다. 계약(sid:MARC-ISSUE-99 2):
   * - 구독하면 현재값을 **먼저 한 번** listener 로 보낸다(곧바로든 조금 뒤든). 그 뒤 바뀔 때마다 차례대로 보낸다.
   * - 없는 실행이면 listener 를 부르지 않고 onMissing 을 한 번 부른다.
   * - 해제 함수를 부른 뒤에는 아무것도 부르지 않는다.
   * - 읽기가 실패하면(밴드 GW1R ① Q5) onFailed 를 한 번 부르고 멈춘다: 처음 읽기 실패면 곧바로, 값을 받은 뒤에는 연속 3번 실패면.
   *   성공하면 셈은 0 으로. 목은 실패하지 않아 부르지 않는다. 화면은 「불러오지 못함」 + [다시 시도](다시 구독)를 보인다.
   */
  subscribeRun(
    runId: string,
    listener: (run: RunSnapshot) => void,
    onMissing?: () => void,
    onFailed?: () => void,
  ): () => void;
  /**
   * 실패한 실행과 같은 문서·같은 입력으로 새 실행을 처음부터 돌린다. 실패한 실행이 아니면 거절된다.
   * 열쇠는 createRun 과 같다: 끊김 뒤 같은 열쇠로 다시 부르면 앞에 만든 새 실행을 돌려준다.
   */
  rerun(runId: string, idempotencyKey?: string): Promise<{ runId: string }>;
  /** 수정본 대상으로 고를 기존 문서 목록. */
  listDocuments(): Promise<readonly ExistingDocument[]>;
  /** 기본 단어 목록(추가 단어가 이미 들었는지 볼 때, 빈도의 「추가」 표시를 가를 때 쓴다). 실제 경로는 GET /greenwash/terms/default(계약에 있다 — apps/api-py/generated/api.d.ts). */
  listDefaultTerms(): Promise<readonly string[]>;
  // ── 밴드 FW2 ① ──
  /** 문서 하나(쪽 수 채우기 [R5]). 없으면 StoreError not_found. */
  getDocument(documentId: string): Promise<DocumentInfo>;
  /** 목록(GW-01) 줄의 원재료: 문서·실행·검토 요약. */
  listCheckRows(): Promise<CheckRowsSource>;
  /** 한 실행의 결과 JSON(greenwash.result@1, 거울은 훅이 댄다). 끝나지 않았거나 없으면 StoreError not_found. */
  getResult(runId: string): Promise<unknown>;
  /** 한 실행의 검토 JSON(greenwash.review@3). 없으면 StoreError not_found. */
  getReview(runId: string): Promise<unknown>;
  /** 검토 표시 저장. 본문의 marks 는 그 실행의 표시 전부를 갈아 넣는다. 확정된 실행이면 StoreError review_locked, 끝나지 않은 실행이면 run_not_done, 검토가 없으면 no_review(서버 409). 돌려받는 것은 저장 뒤 검토 JSON. */
  putReview(runId: string, update: ReviewUpdate): Promise<unknown>;
  /**
   * 문장 하나를 지금 근거로 다시 판단하는 실행을 만든다(GRJ1 — POST /greenwash/runs/{id}/items/{i}/rejudge, 202). 진행·결과는
   * 검토 GET 의 rejudges 로 읽는다. 거절: 문장·실행 없음 not_found · done 아님 run_not_done · 검토 없음 no_review · 확정됨 review_locked ·
   * 도는 중 rejudge_running · 근거 같음 nothing_to_rejudge · 그 밖 rejected.
   */
  rejudge(runId: string, itemIndex: number): Promise<{ rejudgeRunId: string }>;
  /** 쪽 그림용 PDF. 없으면 null(목의 씨앗 문서 등). */
  openDocumentPdf(documentId: string): Promise<File | null>;
  /**
   * 엑셀 보고서(밴드 GW2R ③ Q9 — GET /greenwash/runs/{id}/report). confirmed 면 확정본(채택한 문장만), 아니면 확정 전 결과.
   * 파일을 저장하지는 않는다(Blob 만 — 저장은 ui 층). 끝나지 않음·확정 전 확정본·dry-run·끊김은 거절(StoreError).
   */
  getReport(runId: string, confirmed: boolean): Promise<ReportFile>;
}

/** 내려받은 엑셀(밴드 GW2R ③). fileName 은 서버 Content-Disposition, 없으면 「greenwash-<runId>.xlsx」. */
export interface ReportFile {
  blob: Blob;
  fileName: string;
}

/** 문서 하나(쪽 수 채우기에 쓰는 칸만). */
export interface DocumentInfo {
  documentId: string;
  fileName: string;
  /** 쪽 수. 모르면 null(실어댑터: 서버 값 → 이 탭에서 올리며 센 값 → null, 밴드 GW1R ① Q2). */
  pageCount: number | null;
}

export type StoreErrorKind =
  | 'not_found'
  | 'review_locked'
  | 'run_not_done'
  | 'no_review'
  | 'unreachable'
  /** 파일이 올리기 한도를 넘음(413 — 서버 UPLOAD_TOO_LARGE 나 앞단 프록시). 다시 해도 같다. */
  | 'too_large'
  /** 실행 만들기의 409 IDEMPOTENCY_KEY_REUSED — 같은 열쇠에 다른 본문. 앞 요청이 실행을 만들었을 수 있다(sid:MARC-ISSUE-312). */
  | 'key_reused'
  /** 재판단 만들기(GRJ1)의 409 REJUDGE_RUNNING — 그 문장의 재판단이 아직 돈다. */
  | 'rejudge_running'
  /** 재판단 만들기(GRJ1)의 409 NOTHING_TO_REJUDGE — 근거가 기준 판단에 보낸 것과 같다. */
  | 'nothing_to_rejudge'
  | 'rejected';

/** 저장소의 거절. 훅은 kind 로 갈래를 가른다. */
export class StoreError extends Error {
  readonly kind: StoreErrorKind;
  constructor(kind: StoreErrorKind, message: string) {
    super(message);
    this.name = 'StoreError';
    this.kind = kind;
  }
}

/** 거절의 갈래. StoreError 가 아니면 rejected. */
export function storeErrorKind(error: unknown): StoreErrorKind {
  return error instanceof StoreError ? error.kind : 'rejected';
}
