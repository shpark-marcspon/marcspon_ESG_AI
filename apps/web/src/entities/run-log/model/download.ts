// 실행 기록 엑셀 파일 이름(밴드 AD4X ② — 감독 처분 Q1 (가)). 순수 함수만.
// 서버 GET /run-logs/export 의 Content-Disposition(attachment)에서 파일 이름을 뽑는다:
//   filename*=UTF-8''<퍼센트 꼴>(RFC 5987, 대소문자 무시)이 있으면 그것, 깨졌거나 없으면 filename="…"(따옴표) 또는 filename=…(따옴표 없음).
//   읽을 수 없으면 null — 어댑터가 RUN_EXPORT_FALLBACK_NAME 으로 메운다.
// 경로 글자(/ \)는 지운다(내려받는 이름에 폴더가 섞이지 않게).
// 같은 셈이 그린워싱 엑셀(entities/greenwash/model/report.ts)에도 있다 — entities 끼리는 가져오지 않아 따로 둔다(세 번째 쓰는 곳이 오면 shared 로 함께 올린다).

/** 이름을 모를 때의 파일 이름(초안 — 디자인 확인 전). */
export const RUN_EXPORT_FALLBACK_NAME = '실행기록.xlsx';

/** Content-Disposition → 파일 이름. 없거나 읽을 수 없으면 null. */
export function fileNameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  const star = /filename\*\s*=\s*utf-8''([^;]+)/i.exec(header);
  if (star) {
    try {
      return clean(decodeURIComponent(star[1]!.trim()));
    } catch {
      // 퍼센트 꼴이 깨졌으면 아래 filename= 으로
    }
  }
  const quoted = /filename\s*=\s*"((?:[^"\\]|\\.)*)"/i.exec(header);
  if (quoted) return clean(quoted[1]!.replace(/\\(.)/g, '$1'));
  const bare = /filename\s*=\s*([^;\s]+)/i.exec(header);
  if (bare) return clean(bare[1]!);
  return null;
}

function clean(name: string): string | null {
  const trimmed = name.replace(/[/\\]/g, '').trim();
  return trimmed === '' ? null : trimmed;
}
