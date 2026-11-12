"""경로 설정. 스키마는 패키지 곁의 `schemas/`(사본)에서 읽고, 원본 PDF 와 정답 표는 저장소에 두지 않고 환경 변수로
가리킨다.

`PARSER_REPORTS_DIR`(공개 보고서 PDF)·`PARSER_GOLD_DIR`(정답 표)는 없어도 import 때 죽지 않는다.
그 경로를 쓰는 함수가 불릴 때 `MissingPathError` 로 실패한다. 분해 길(`parse`)은 둘 다 쓰지 않는다.
"""

import os
from pathlib import Path

# services/parser (컨테이너에서는 /app). `docparse/` 와 `schemas/` 가 나란히 있다.
PARSER_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PARSER_ROOT / "schemas" / "document.schema.json"
PLACES_SCHEMA_PATH = PARSER_ROOT / "schemas" / "char-places.schema.json"
CHARTS_SCHEMA_PATH = PARSER_ROOT / "schemas" / "chart-labels.schema.json"  # 도표 라벨(layout 2, 밴드 CHL1)

# 정답 표의 report 키 -> 국문판 파일명
REPORT_FILES = {
    "samsung": "samsung_2026_kor.pdf",
    "kb": "kb_2025_kor.pdf",
    "kb_databook": "kb_2025_databook_kor.pdf",
    "cosmax": "cosmax_2025_kor.pdf",
}


class MissingPathError(ValueError):
    """환경 변수로 가리켜야 하는 경로가 주어지지 않았다."""


def _env_dir(name, what):
    env = os.environ.get(name)
    if not env:
        raise MissingPathError(f"환경 변수 {name} 가 없다 ({what}의 폴더를 가리킨다. 저장소에는 두지 않는다)")
    return Path(env)


def reports_dir() -> Path:
    """환경 변수 PARSER_REPORTS_DIR 의 경로. 없으면 `MissingPathError`."""
    return _env_dir("PARSER_REPORTS_DIR", "공개 보고서 PDF")


def gold_dir() -> Path:
    """환경 변수 PARSER_GOLD_DIR 의 경로. 없으면 `MissingPathError`."""
    return _env_dir("PARSER_GOLD_DIR", "정답 표")


def report_path(report: str) -> Path:
    return reports_dir() / REPORT_FILES[report]
