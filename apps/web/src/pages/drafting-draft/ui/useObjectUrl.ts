// File → object URL(밴드 RPW1 ③ — 원문 보기의 원본 PDF). entities/translation/ui/useObjectUrl.ts 를 옮겨 적었다(영문번역은 가져오지 않는다).
// 파일이 바뀌거나 내려가면 그 URL 을 revokeObjectURL 한다. 첫 그리기는 null 이다(effect 에서 연다).
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
