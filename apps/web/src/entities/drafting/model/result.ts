// 원고작성 결과 꼴(drafting.bullets@3 — 밴드 RPW1 ①, 고정 파일 apps/api-py/esgapi/drafting/tests/data/flow-shapes/drafting.bullets@3.schema.json).
//   api/contract 의 거울이 이 꼴을 지킨다. 서버 message·reason 은 꼴에만 있고 화면에 싣지 않는다(발주서 §1-4 ③).
//   좌표는 PDF pt · CropBox 왼쪽 위 원점, 쪽 번호는 1부터. /Rotate≠0 쪽은 맞추지 않는다(sid:MARC-ISSUE-493).

export type Box = [number, number, number, number];

export interface Sentence {
  index: number;
  boxes: Box[];
}

export interface Source {
  documentId: number;
  blockId: string;
  page: number;
  blockBox: Box;
  sentence: Sentence | null;
}

export interface Bullet {
  text: string;
  unsupported: boolean;
  sources: Source[];
}

export type LeafOutcome =
  | { status: 'done'; bullets: Bullet[] }
  | { status: 'no_material' }
  | { status: 'failed'; failure: { kind: string; message: string } }
  | { status: 'not_run'; reason: string };

export interface Leaf {
  key: string;
  titlePath: string[];
  pages: number[];
  reusedFrom: { runId: number; outlineId: number } | null;
  outcome: LeafOutcome;
}

export interface DraftingResult {
  schemaVersion: 'drafting.bullets@3';
  projectId: number;
  outlineId: number;
  outlineSha256: string;
  base: {
    runId: number;
    outlineId: number;
    matched: boolean;
    /** 이어 받지 못한 까닭(서버 enum — 화면 0, 받아 두기만). */
    reason: string | null;
  } | null;
  status:
    | { status: 'done' }
    | {
        status: 'rejected';
        code: 'over_budget' | 'too_large';
        stage: 'before_map' | 'before_draft';
        message: string;
      };
  /** 서버 칸 `document`(DraftingDocument) — 거울(api/contract)이 `pdf` 로 옮겨 싣는다(model 은 DOM 낱말을 쓰지 않는다 — 영문번역 batch.ts 꼴). */
  pdf: {
    documentId: number;
    fileName: string;
    pageCount: number;
    textPages: number;
    pages: { page: number; width: number; height: number }[];
  };
  leaves: Leaf[];
  mapping: { failedBatches: unknown[] };
  warnings: {
    code: string;
    key: string | null;
    page: number | null;
    message: string;
  }[];
}

/** 목차 차이(DraftingOutlineChanges). */
export interface OutlineChanges {
  baseRunId: number;
  baseOutlineId: number;
  outlineId: number;
  /** 서버 칸 `document` — 거울이 `pdf` 로 옮겨 싣는다. */
  pdf: 'same' | 'changed';
  leaves: { key: string; change: 'same' | 'changed' | 'added' }[];
  removed: string[];
}

/** 실행 옵션(drafting.options@2 — openapi 밖, 고정 파일 options/drafting.options@2.schema.json). */
export interface RunOptions {
  projectId: number;
  base?: { runId: number; rebuild: string[] };
}
