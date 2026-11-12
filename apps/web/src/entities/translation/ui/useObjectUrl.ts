// File → object URL(밴드 TRW6 ③ — PDF 보기의 원본 PDF). entities/greenwash/ui/useObjectUrl.ts 를 옮겨 적었다(그린워싱은 가져오지 않는다 — 공통화는 후속).
// 파일이 바뀌거나 내려가면 그 URL 을 revokeObjectURL 한다. 첫 그리기는 null 이다(effect 에서 연다) —
// 쓰는 쪽은 null 이면 그리지 않고, URL 을 key 로 써서 파일이 바뀌면 PDF 를 새로 연다.
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
