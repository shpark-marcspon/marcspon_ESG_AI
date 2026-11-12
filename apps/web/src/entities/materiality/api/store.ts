// 중대성평가 저장소 꼴(밴드 IRW1 ①). 화면·훅은 이 꼴만 안다 — 기본 저장소는 실어댑터(server.ts), 시험은 가짜 서버(testing.ts)를 그 앞에 둔다.
// 목 저장소는 없다(발주서 §1-3 — CreateMaterialityStore 는 시험 주입 자리로만).
// 읽기의 거절은 MaterialityStoreError(kind): not_found(없음·꼴 밖 id·중대성평가 아님) · not_done(결과 409 RUN_NOT_DONE) ·
//   rejected(서버 거절·꼴 틀림) · unreachable(답을 받지 못함). [다시 실행](rerun)은 갈래를 값으로 돌려준다. 서버 message 는 싣지 않는다.
import type {
  MaterialityInput,
  MaterialityResult,
  MaterialityRun,
  RunStatus,
} from '../model/index.ts';
import type {
  MaterialityRunPage,
  MaterialityValueChainRead,
  ResultEditsView,
} from './contract/index.ts';

export type {
  MaterialityRunPage,
  MaterialityRunRow,
  MaterialityValueChainRead,
  MaterialityValueChainReadRow,
  ResultEditsView,
} from './contract/index.ts';

/** 목록 한 쪽의 줄 수(서버 limit 상한 20 — 쪽 넘김 0, 새 것 20만: 발주서 §2-3). */
export const RUN_PAGE_LIMIT = 20;

/** GET /materiality/runs 의 거르기(status 는 여러 개 — 「대기·처리 중」 = queued·processing 한 요청). */
export interface RunListQuery {
  status?: readonly RunStatus[];
  /** 참일 때만 싣는다(운영 관리자는 화면이 늘 거짓으로 — 판 IR-01a 에 칸이 없다). */
  mine?: boolean;
  offset: number;
}

export type StoreErrorKind =
  'not_found' | 'not_done' | 'rejected' | 'unreachable';

export class MaterialityStoreError extends Error {
  readonly kind: StoreErrorKind;
  constructor(kind: StoreErrorKind, message: string) {
    super(message);
    this.name = 'MaterialityStoreError';
    this.kind = kind;
  }
}

/** 거절의 갈래(저장소 거절이 아닌 것은 rejected). */
export function storeErrorKind(error: unknown): StoreErrorKind {
  return error instanceof MaterialityStoreError ? error.kind : 'rejected';
}

/** [다시 실행]의 끝: started · failed(읽기 실패·서버 거절) · unreachable(답 없음 — 만들었는지 모른다, 같은 열쇠로 다시 보내면 앞 실행). */
export type RerunResult =
  | { kind: 'started'; runId: string }
  | { kind: 'failed' }
  | { kind: 'unreachable' };

/** [평가 시작]의 끝(밴드 IRW2 ②): started · failed(서버 거절 — 422 포함) · unreachable(답 없음 — 같은 입력으로 다시 누르면 같은 열쇠). */
export type CreateRunResult = RerunResult;

/** 결과 글 칸 고침 하나(보내는 꼴 — 바른 주소와 새 값, null = 빈 칸). */
export interface ResultEditChange {
  pointer: string;
  value: string | null;
}

/** 고침 저장의 끝(밴드 IRW11): saved(새 revision·고침) · conflict(409 EDIT_CONFLICT — 다시 읽고 다시) · invalid(400 INVALID_EDIT) ·
 *  failed(그 밖 거절·꼴 틀림) · unreachable(답 없음). 서버 message 는 싣지 않는다. */
export type SaveEditsResult =
  | { kind: 'saved'; edits: ResultEditsView }
  | { kind: 'conflict' }
  | { kind: 'invalid' }
  | { kind: 'failed' }
  | { kind: 'unreachable' };

export interface FileDownload {
  blob: Blob;
  fileName: string;
}

export interface MaterialityStore {
  /** GET /materiality/runs?status=…&mine=true&limit=20&offset= → 쪽(거울). 거절은 MaterialityStoreError. */
  listRuns(query: RunListQuery): Promise<MaterialityRunPage>;
  getRun(runId: string): Promise<MaterialityRun>;
  /**
   * 실행 폴링: 곧바로 한 번, 답을 받은 뒤 pollMs 뒤 다음(겹침 없음), done·failed 에서 멈춤, 404 → onMissing 한 번.
   * 실패는 처음 읽기면 곧바로, 값을 받은 뒤면 연속 3번째에 onFailed 한 번(그린워싱 subscribeRun 규칙). 해제 뒤 온 답은 버린다.
   */
  subscribeRun(
    runId: string,
    listener: (run: MaterialityRun) => void,
    onMissing?: () => void,
    onFailed?: () => void,
  ): () => void;
  /** GET /materiality/runs/{id}/result → result@2 를 거울로 지킨 화면 꼴. 거절은 MaterialityStoreError. */
  getResult(runId: string): Promise<MaterialityResult>;
  /** 결과 엑셀 — 고친 판(GET /materiality/runs/{id}/report, 이름 materiality-final-report.xlsx — 밴드 IRW11 Q11). */
  reportFile(runId: string): Promise<FileDownload>;
  /** GET /materiality/runs/{id}/result/edits → result-edits@1 거울(revision·고침). 거절은 MaterialityStoreError. */
  getEdits(runId: string): Promise<ResultEditsView>;
  /** POST /materiality/runs/{id}/result/edits {baseRevision, changes} → 갈래(값). */
  saveEdits(
    runId: string,
    baseRevision: number,
    changes: readonly ResultEditChange[],
  ): Promise<SaveEditsResult>;
  /** 1부 리서치 엑셀(GET /runs/{id}/files/materiality-websearch.xlsx — sid:MARC-ENT-449). */
  researchFile(runId: string): Promise<FileDownload>;
  /**
   * GET /runs/{id} 의 options 그대로 새 POST /runs(처음부터 — resumeFromRunId 0) + 새 Idempotency-Key·launchKey.
   * 실패 뒤 같은 실행·같은 options 로 다시 누르면 같은 열쇠(서버가 앞 실행을 돌려준다), 만들어지면 버린다.
   */
  rerun(runId: string): Promise<RerunResult>;
  /**
   * [평가 시작](밴드 IRW2 ②): POST /runs {module:'materiality', launchKey, options:{input}} + Idempotency-Key. 열쇠·launchKey 는 첫 누름·
   * 입력이 바뀔 때 새로, 실패 뒤 같은 입력이면 둘 다 같은 값(rerun 의 열쇠 규칙), 만들어지면 버린다.
   */
  createRun(input: MaterialityInput): Promise<CreateRunResult>;
  /**
   * 가치사슬 표 엑셀 읽기(POST /materiality/value-chain/read — 맨 바이트, 밴드 IRW2). 읽었든 못 읽었든 200 의 두 갈래(거울).
   * 거절(5xx·413·꼴 틀림 rejected)·끊김(unreachable)은 MaterialityStoreError. 아무것도 저장하지 않는 경로다.
   */
  readValueChain(file: Blob): Promise<MaterialityValueChainRead>;
  /** 쥐고 있는 「아직 만들어지지 않은 본문 + 열쇠」를 버린다(세션이 끝날 때 — 틀이 부른다). 다음 누름은 새 열쇠. */
  forget(): void;
}
