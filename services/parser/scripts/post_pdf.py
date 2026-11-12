"""PDF 하나를 파서의 새 약속(`POST /parse`, 본문 = PDF 바이트)으로 보내고 답의 본문을 표준 출력에 쓴다.

    python post_pdf.py http://parser:8000/parse /reports/kb_2025_kor.pdf > answer.json

표준 라이브러리만 쓴다(파서 이미지 안에서 돌린다). 상태 코드와 걸린 시간은 표준 오류로 낸다.
200 이 아니면 종료 코드 1 이고 그때도 본문은 표준 출력에 쓴다. 넷째 인자로 Content-Type 을 바꿀 수 있다(거절 갈래를 볼 때).
"""

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main(argv):
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    url, path = argv[1], Path(argv[2])
    content_type = argv[3] if len(argv) == 4 else "application/pdf"
    data = path.read_bytes()
    # file_name 은 UTF-8 percent-encoding 으로 보낸다 (공백은 %20, 더하기는 %2B).
    target = f"{url}?file_name={urllib.parse.quote(path.name, safe='')}"
    # S310: 주소는 이 스크립트를 부르는 사람이 준다(§4 의 curl 대신 쓰는 손 도구). 서비스가 받은 값이 아니다.
    request = urllib.request.Request(target, data=data, method="POST", headers={"Content-Type": content_type})  # noqa: S310
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=600) as response:  # noqa: S310
            status, body = response.status, response.read()
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read()
    took = time.monotonic() - started
    print(f"status={status} seconds={took:.2f} sent_bytes={len(data)} received_bytes={len(body)}", file=sys.stderr)
    sys.stdout.buffer.write(body)
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
