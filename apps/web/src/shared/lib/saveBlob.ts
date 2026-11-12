// 받은 파일을 이 탭에서 내려받게 한다(밴드 AD4X ② — 감독 처분 Q1 (가)). DOM 은 ui 층과 이 shared/lib 함수에서만 — api·hooks 는 Blob 만 돌려준다(app/guards/layers.test.ts 의 HOOKS_DOM).
// TRW0a ① 에서 shared 로 올림 — 그린워싱·실행 기록·영문번역이 쓴다(그린워싱 엑셀 단추의 같은 꼴은 shared/ui/download-button 이 이것을 부른다).

/** Blob 을 이 탭에서 내려받게 한다(<a download> 를 잠깐 붙여 누르고 뗀다). */
export function saveBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  link.rel = 'noopener';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
  // 누름이 내려받기를 시작한 뒤에 놓는다(같은 틱에 놓으면 일부 브라우저가 내려받지 못한다).
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
