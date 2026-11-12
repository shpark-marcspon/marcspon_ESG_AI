// 올릴 파일 거름(밴드 S3W1 ①). 웹은 확장자·크기만 본다 — 행 수·검증 규칙은 서버에 없어 보지 않는다(발주서 1-4 ④).
// 상한 20MB(RPT-21 §3.3 — 기획 40쪽). 서버 상한은 따로(413 upload_too_large). 0바이트는 서버가 받지 않는다(sizeBytes ≥ 1 — GX1 M-5).

/** 올릴 수 있는 크기 상한(바이트) — 같으면 받는다. */
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;
const EXTENSIONS = ['xls', 'xlsx'];

export type FileProblem = 'type' | 'empty' | 'size';

/** 받으면 null, 아니면 까닭 하나(형식 → 빈 파일 → 크기 차례). */
export function acceptFile(file: {
  name: string;
  size: number;
}): FileProblem | null {
  const dot = file.name.lastIndexOf('.');
  const extension = dot < 0 ? '' : file.name.slice(dot + 1).toLowerCase();
  if (!EXTENSIONS.includes(extension)) return 'type';
  if (file.size <= 0) return 'empty';
  if (file.size > MAX_UPLOAD_BYTES) return 'size';
  return null;
}
