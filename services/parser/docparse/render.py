"""쪽을 PNG로 렌더링한다 (나중에 비전 모델 입력용, 정답 표 육안 대조용)."""

from pathlib import Path

from .engine import open_pdf


def render_page(pdf_path, page_no, out_path, dpi=200, clip=None, engine=None):
    """page_no 는 1부터. clip=(x0,y0,x1,y1) pt 좌표. 쓴 파일 경로를 돌려준다."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open_pdf(pdf_path, engine) as doc:
        if not 1 <= page_no <= len(doc):
            raise ValueError(f"쪽 번호 {page_no} 는 범위 밖이다 (1~{len(doc)})")
        doc[page_no - 1].render_png(out_path, dpi, clip)
    return out_path


def render_pages(pdf_path, out_dir, pages=None, dpi=200, engine=None):
    """pages 가 None 이면 전 쪽. 쓴 파일 경로 목록을 돌려준다."""
    out_dir = Path(out_dir)
    with open_pdf(pdf_path, engine) as doc:
        n = len(doc)
    pages = list(pages) if pages else list(range(1, n + 1))
    return [render_page(pdf_path, p, out_dir / f"p{p:04d}.png", dpi=dpi, engine=engine) for p in pages]
