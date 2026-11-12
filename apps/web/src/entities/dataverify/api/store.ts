// 데이터 검증 저장소 꼴(밴드 DV2a ①). 화면·훅은 이 꼴만 안다 — 기본 저장소는 실어댑터(server.ts), 시험은 가짜 서버(testing.ts)를 그 앞에 둔다.
// 목 저장소는 없다(발주서 §1-3 — CreateDataverifyStore 는 시험 주입 자리로만).
// 읽기의 거절은 DataverifyStoreError(kind): not_found(없음·꼴 밖 id·데이터 검증 아님) · not_done(결과 409 RUN_NOT_DONE) ·
//   rejected(서버 거절·꼴 틀림) · unreachable(답을 받지 못함). 실행 만들기(startRun·rerun)는 갈래를 값으로 돌려준다. 서버 message 는 싣지 않는다.
import type { Schemas } from '../../../shared/api/index.ts';
import type {
  DataverifyInput,
  DataverifyResult,
  DataverifyRun,
  InputSource,
  RunStatus,
} from '../model/index.ts';
import type {
  DataverifyEdkRead,
  DataverifyEdkReadOk,
  DataverifyEdkReadRejected,
  DataverifyRunPage,
} from './contract/index.ts';

export type {
  DataverifyEdkRead,
  DataverifyEdkReadOk,
  DataverifyEdkReadRejected,
  DataverifyRunPage,
  DataverifyRunRow,
  EdkReadKind,
} from './contract/index.ts';

/** model 의 출처 꼴과 generated 출처 꼴이 서로 넣어지는가(어긋나면 tsc 가 여기서 멈춘다 — 손으로 다시 적은 꼴의 지킴). */
type GeneratedSource =
  Schemas['DataverifyFileSource'] | Schemas['DataverifyPasteSource'];
export const SOURCE_SHAPES_AGREE: [
  InputSource extends GeneratedSource ? true : false,
  GeneratedSource extends InputSource ? true : false,
] = [true, true];

/**
 * 엑셀 읽기 답의 거울 꼴과 generated 꼴이 서로 넣어지는가(밴드 DVX1 ②, 위와 같은 지킴). data 는 뺀다 — 거울은 항목 꼴을 보지 않고
 * (readEdk 가 본다) generated 는 항목 열쇠 열하나를 적는다. 거절 갈래(kind 열 포함)는 통째로.
 */
type Same<A, B> =
  [A] extends [B] ?
    [B] extends [A] ?
      true
    : false
  : false;
export const EDK_READ_SHAPES_AGREE: [
  Same<
    Omit<DataverifyEdkReadOk, 'data'>,
    Omit<Schemas['DataverifyEdkReadOk'], 'data'>
  >,
  Same<DataverifyEdkReadRejected, Schemas['DataverifyEdkReadRejected']>,
  Schemas['DataverifyEdkReadOk']['data'] extends DataverifyEdkReadOk['data'] ?
    true
  : false,
] = [true, true, true];

/** 목록 한 쪽의 줄 수(서버 limit 상한 20 — 쪽 넘김 0, 새 것 20만: 발주서 QB4 (가)). */
export const RUN_PAGE_LIMIT = 20;

/** GET /dataverify/runs 의 거르기(status 는 여러 개 — 「대기·처리 중」 = queued·processing 한 요청, QB3 (가)). */
export interface RunListQuery {
  status?: readonly RunStatus[];
  /** 참일 때만 싣는다(운영 관리자는 화면이 늘 거짓으로). */
  mine?: boolean;
  offset: number;
}

export type StoreErrorKind =
  'not_found' | 'not_done' | 'rejected' | 'unreachable';

export class DataverifyStoreError extends Error {
  readonly kind: StoreErrorKind;
  constructor(kind: StoreErrorKind, message: string) {
    super(message);
    this.name = 'DataverifyStoreError';
    this.kind = kind;
  }
}

/** 거절의 갈래(저장소 거절이 아닌 것은 rejected). */
export function storeErrorKind(error: unknown): StoreErrorKind {
  return error instanceof DataverifyStoreError ? error.kind : 'rejected';
}

/**
 * [검증 시작]·[다시 실행]의 끝: started · too_large(옵션 셈이 상한을 넘음 — 보내지 않았거나 400 을 다시 재서 넘음) ·
 * unreadable(400 INVALID_OPTIONS 인데 셈은 상한 안 — 꼴 거절) · failed(그 밖 거절) · unreachable(답 없음 — 만들었는지 모른다).
 */
export type StartResult =
  | { kind: 'started'; runId: string }
  | { kind: 'too_large' }
  | { kind: 'unreadable' }
  | { kind: 'failed' }
  | { kind: 'unreachable' };

export interface FileDownload {
  blob: Blob;
  fileName: string;
}

export interface DataverifyStore {
  /**
   * POST /runs {module:'dataverify', options:{input, source?}} + 머리 Idempotency-Key. 열쇠는 첫 누름과 본문이 바뀔 때만 새로 짓고,
   * 실패 뒤 같은 본문으로 다시 누르면 같은 열쇠, 만들어지면 버린다(그린워싱 GR2 꼴).
   */
  startRun(input: DataverifyInput, source?: InputSource): Promise<StartResult>;
  /** GET /dataverify/runs?status=…&mine=true&limit=20&offset= → 쪽(거울). 거절은 DataverifyStoreError. */
  listRuns(query: RunListQuery): Promise<DataverifyRunPage>;
  getRun(runId: string): Promise<DataverifyRun>;
  /**
   * 실행 폴링: 곧바로 한 번, 답을 받은 뒤 pollMs 뒤 다음(겹침 없음), done·failed 에서 멈춤, 404 → onMissing 한 번.
   * 실패는 처음 읽기면 곧바로, 값을 받은 뒤면 연속 3번째에 onFailed 한 번(그린워싱 subscribeRun 규칙). 해제 뒤 온 답은 버린다.
   */
  subscribeRun(
    runId: string,
    listener: (run: DataverifyRun) => void,
    onMissing?: () => void,
    onFailed?: () => void,
  ): () => void;
  getResult(runId: string): Promise<DataverifyResult>;
  /** 결과 엑셀(GET /runs/{id}/files/dataverify-report.xlsx). */
  reportFile(runId: string): Promise<FileDownload>;
  /** GET /runs/{id} 의 options 그대로 새 POST /runs(처음부터 — resumeFromRunId 0). 읽지 못하면 failed·unreachable. */
  rerun(runId: string): Promise<StartResult>;
  /**
   * POST /dataverify/edk/read — 올린 EDK 인벤토리 .xlsx 를 맨 바이트(Content-Type xlsx)로 보내 data 로 바꾼 답(저장 0). 서버 거절은
   * 값(ok:false·kind)으로, 꼴 틀림은 rejected·답 없음은 unreachable 로 던진다(DataverifyStoreError).
   */
  readEdkXlsx(file: Blob): Promise<DataverifyEdkRead>;
  /** GET /dataverify/edk/template[?year=] — 빈 양식 엑셀(이름은 Content-Disposition). year 를 주지 않으면 서버가 해−1. */
  downloadEdkTemplate(year?: string): Promise<FileDownload>;
  /** 쥐고 있는 「아직 만들어지지 않은 본문 + 열쇠」를 버린다(세션이 끝날 때 — 틀이 부른다). 다음 누름은 새 열쇠. */
  forget(): void;
}
