// PDF 입력의 쪽 칸(밴드 TRW9): 고른 파일을 열어 PageGrid 에 넘긴다. 그린워싱 PageThumbnails → ThumbGrid 의 두 겹 꼴(옮겨 적음 — 공통화 0).
//
// - 파일은 useObjectUrl 로 object URL 을 열고, 파일이 바뀌거나 내려가면 revoke 한다. url 을 key 로 써서 파일이 바뀌면 새로 연다.
// - PDF 를 여는 구현(openPdf)은 props 로 받는다(ui 는 widgets/doc-viewer/pdfjs.ts 를 가져오지 못한다. 층 시험).
// - 그린워싱과 달리 열기 전·실패에도 칸을 그린다(범위 칠하기는 계속 된다, 글 0).
import { useObjectUrl } from '../../../entities/translation/ui/index.ts';
import { usePdf } from '../../../widgets/doc-viewer/index.ts';
import type { OpenPdf } from '../../../widgets/doc-viewer/index.ts';
import { PageGrid } from './PageGrid.tsx';
import type { PageGridProps } from './PageGrid.tsx';

export interface PdfPageGridProps extends Omit<PageGridProps, 'thumbs'> {
  file: File;
  openPdf: OpenPdf;
}

export function PdfPageGrid({ file, openPdf, ...grid }: PdfPageGridProps) {
  const url = useObjectUrl(file);
  if (url === null) return <PageGrid {...grid} />;
  return <Opened key={url} url={url} openPdf={openPdf} {...grid} />;
}

function Opened({
  url,
  openPdf,
  ...grid
}: Omit<PdfPageGridProps, 'file'> & { url: string }) {
  const loaded = usePdf(url, openPdf);
  return <PageGrid {...grid} thumbs={loaded} />;
}
