// 엑셀 보고서 파일 이름(밴드 GW2R ③ Q9). 순수 함수만.
// 서버 GET /greenwash/runs/{id}/report 의 Content-Disposition(attachment)에서 파일 이름을 뽑는다:
//   filename*=UTF-8''<퍼센트 꼴>(RFC 5987)이 있으면 그것, 없으면 filename="…"(따옴표) 또는 filename=…(따옴표 없음).
//   읽을 수 없으면 null — 쓰는 쪽(어댑터)이 「greenwash-<runId>.xlsx」로 메운다(디자인 답 D3, 가정).
// 경로 글자(/ \)는 지운다(내려받는 이름에 폴더가 섞이지 않게).

/** Content-Disposition → 파일 이름. 없거나 읽을 수 없으면 null. */
export function fileNameFromDisposition(header: string | null): string | null {
  if (header === null) return null;
  const star = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (star) {
    try {
      return clean(decodeURIComponent(star[1]!.trim()));
    } catch {
      // 퍼센트 꼴이 깨졌으면 아래 filename= 으로
    }
  }
  const quoted = /filename\s*=\s*"((?:[^"\\]|\\.)*)"/.exec(header);
  if (quoted) return clean(quoted[1]!.replace(/\\(.)/g, '$1'));
  const bare = /filename\s*=\s*([^;\s]+)/.exec(header);
  if (bare) return clean(bare[1]!);
  return null;
}

function clean(name: string): string | null {
  const trimmed = name.replace(/[/\\]/g, '').trim();
  return trimmed === '' ? null : trimmed;
}

/** 이름을 모를 때의 파일 이름. */
export const fallbackReportName = (runId: string) => `greenwash-${runId}.xlsx`;
