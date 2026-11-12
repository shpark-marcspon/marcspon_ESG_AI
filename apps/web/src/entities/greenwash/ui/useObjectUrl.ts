// File → object URL(밴드 WC1 ③: 쪽 썸네일 PageThumbnails 와 검토 쪽 칸 ReviewPagePane 의 두 벌을 하나로. 동작은 둘의 것 그대로).
// 파일이 바뀌거나 내려가면 그 URL 을 revokeObjectURL 한다. 첫 그리기는 null 이다(effect 에서 연다) —
// 쓰는 쪽은 null 이면 그리지 않고, URL 을 key 로 써서 파일이 바뀌면 PDF 를 새로 연다.
// 파일이 바뀐 직후 한 그리기 동안은 앞 URL(이미 revoke 됨)을 돌려준다 — 쓰는 쪽이 key={url} 이라 다음 그리기에서 새 URL 로 다시 연다.
import { useEffect, useState } from 'react';

export function useObjectUrl(file: File): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);
  return url;
}
